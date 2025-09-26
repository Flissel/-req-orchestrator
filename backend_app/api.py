# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import logging
import concurrent.futures as futures
from typing import Any, Dict, List, Tuple
import requests  # HTTP delegation to agent worker

from flask import Blueprint, jsonify, request, g, make_response
from .logging_ext import _json_log as json_log

from . import settings
from .db import get_db, load_criteria, get_latest_rewrite_row_for_eval, get_latest_evaluation_by_checksum
from .llm import llm_evaluate, llm_suggest, llm_rewrite, llm_apply_with_suggestions
from .utils import compute_verdict, sha256_text, weighted_score, parse_requirements_md, chunked
from .batch import process_evaluations, process_rewrites, process_suggestions, ensure_evaluation_exists

# RAG/Vector-Ingest
from .ingest import extract_texts, chunk_payloads
from .embeddings import build_embeddings, get_embeddings_dim
from .vector_store import (
    get_qdrant_client,
    upsert_points,
    search as vs_search,
    list_collections as vs_list_collections,
    healthcheck as vs_health,
    fetch_window_by_source_and_index,
    reset_collection as vs_reset_collection,
)
from .memory import MemoryStore
from .rag import StructuredRequirement

api_bp = Blueprint("api", __name__)

# Lightweight Memory (Agent policies/outcomes)
_mem_store = MemoryStore()

# Explizite Preflight-Handler für CORS; Antworten leer (204), Header liefert Flask-CORS
@api_bp.route("/api/v1/validate/suggest", methods=["OPTIONS"], strict_slashes=False)
def options_validate_suggest():
    return ("", 204)

@api_bp.route("/api/<path:_>", methods=["OPTIONS"], strict_slashes=False)
def options_cors_catch_all(_):
    resp = make_response("", 204)
    try:
        resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    except Exception:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "600"
    return resp

# Spezifischer OPTIONS-Handler für Reset (ermöglicht DELETE/POST Preflight)
@api_bp.route("/api/v1/vector/reset", methods=["OPTIONS"], strict_slashes=False)
def options_vector_reset():
    resp = make_response("", 204)
    try:
        resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    except Exception:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = "POST,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Max-Age"] = "600"
    return resp

@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@api_bp.get("/api/runtime-config")
def runtime_config():
    """
    Liefert die effektive Runtime-Konfiguration (Snapshot) als JSON.
    Hinweis: Zeigt nur an, ob OPENAI_API_KEY gesetzt ist (boolean), nicht den Schlüssel selbst.
    """
    try:
        return jsonify(settings.get_runtime_config()), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/criteria")
def list_criteria():
    try:
        conn = get_db()
        crits = load_criteria(conn)
        return jsonify({"items": crits}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/evaluations")
def create_evaluation():
    ts_start = time.time()
    try:
        data = request.get_json(silent=True) or {}
        requirement_text = data.get("requirementText")
        context = data.get("context", {}) or {}
        criteria_keys = data.get("criteriaKeys")

        if not isinstance(requirement_text, str) or not requirement_text.strip():
            return jsonify({"error": "invalid_request", "message": "requirementText fehlt oder ist leer"}), 400

        conn = get_db()

        # Kriterien laden: angefordert oder alle aktiven
        if criteria_keys is None:
            crits = load_criteria(conn)
            criteria_keys = [c["key"] for c in crits]
        elif not isinstance(criteria_keys, list) or not all(isinstance(k, str) for k in criteria_keys):
            return jsonify({"error": "invalid_request", "message": "criteriaKeys muss eine Liste von Strings sein"}), 400
        else:
            crits = load_criteria(conn, criteria_keys)
            if not crits:
                return jsonify({"error": "invalid_request", "message": "keine gültigen Kriterien gefunden"}), 400

        # Evaluierung (LLM oder Mock)
        details = llm_evaluate(requirement_text, criteria_keys, context)

        # Score/Verdict
        agg_score = weighted_score(details, crits)
        verdict = compute_verdict(agg_score, settings.VERDICT_THRESHOLD)

        # Speichern nur Metadaten
        latency_ms = int((time.time() - ts_start) * 1000)
        requirement_checksum = sha256_text(requirement_text)
        eval_id = f"ev_{int(time.time())}_{requirement_checksum[:8]}"

        with conn:
            conn.execute(
                "INSERT INTO evaluation(id, requirement_checksum, model, latency_ms, score, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                (eval_id, requirement_checksum, settings.OPENAI_MODEL, latency_ms, agg_score, verdict),
            )
            for d in details:
                conn.execute(
                    "INSERT INTO evaluation_detail(evaluation_id, criterion_key, score, passed, feedback) VALUES (?, ?, ?, ?, ?)",
                    (eval_id, d["criterion"], float(d["score"]), 1 if d["passed"] else 0, d.get("feedback", "")),
                )

            # Platzhalter-Heuristik für spontane Vorschläge (optional)
            suggestions: List[Tuple[str, str]] = []
            if verdict == "fail":
                suggestions.append(
                    ("Schwellwerte konkretisieren, z B Antwortzeit, Fehlertoleranzen und Lastprofil spezifizieren.", "high")
                )
            elif agg_score < 0.8:
                suggestions.append(
                    ("Begriffe präzisieren und Randbedingungen definieren, um Eindeutigkeit zu erhöhen.", "medium")
                )
            for text_sug, prio in suggestions:
                conn.execute(
                    "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                    (eval_id, text_sug, prio),
                )

        response = {
            "evaluationId": eval_id,
            "verdict": verdict,
            "score": round(agg_score, 4),
            "latencyMs": latency_ms,
            "model": settings.OPENAI_MODEL,
            "details": details,
            "suggestions": [{"text": s[0], "priority": s[1]} for s in suggestions],
        }
        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/corrections/decision")
def set_correction_decision():
    """
    Setzt die Entscheidung accepted|rejected für die jüngste Korrektur einer Evaluation.
    Body: { "evaluationId": "...", "decision": "accepted"|"rejected", "decidedBy": "optional" }
    """
    try:
        data = request.get_json(silent=True) or {}
        evaluation_id = data.get("evaluationId")
        decision = str(data.get("decision", "")).lower()
        decided_by = data.get("decidedBy")

        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            return jsonify({"error": "invalid_request", "message": "evaluationId fehlt oder ist leer"}), 400
        if decision not in ("accepted", "rejected"):
            return jsonify({"error": "invalid_request", "message": "decision muss accepted oder rejected sein"}), 400

        conn = get_db()
        # Prüfe, dass es eine Umschreibung gibt
        rw = get_latest_rewrite_row_for_eval(conn, evaluation_id)
        if not rw:
            return jsonify({"error": "not_found", "message": "keine Correction vorhanden"}), 404

        # Upsert ohne ON CONFLICT (kompatibel, falls kein UNIQUE Index existiert)
        with conn:
            existing = conn.execute(
                "SELECT id FROM correction_decision WHERE evaluation_id = ? LIMIT 1",
                (evaluation_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE correction_decision SET rewritten_id = ?, decision = ?, decided_by = ?, decided_at = CURRENT_TIMESTAMP WHERE evaluation_id = ?",
                    (rw["id"], decision, decided_by, evaluation_id),
                )
            else:
                conn.execute(
                    "INSERT INTO correction_decision(evaluation_id, rewritten_id, decision, decided_by) VALUES (?, ?, ?, ?)",
                    (evaluation_id, rw["id"], decision, decided_by),
                )
        return jsonify({"evaluationId": evaluation_id, "decision": decision}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/corrections/text")
def save_correction_text():
    """
    Speichert eine manuell eingegebene Korrektur (Correction) zu einer bestehenden Evaluation.
    Body: { "originalText": string, "text": string }
    - originalText: Der ursprüngliche Requirement-Text, um die Evaluation per checksum zu finden
    - text: Die manuelle Korrektur (wird in rewritten_requirement gespeichert)
    """
    try:
        data = request.get_json(silent=True) or {}
        original_text = data.get("originalText")
        text = data.get("text")

        if not isinstance(original_text, str) or not original_text.strip():
            return jsonify({"error": "invalid_request", "message": "originalText fehlt oder ist leer"}), 400
        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "invalid_request", "message": "text fehlt oder ist leer"}), 400

        conn = get_db()
        checksum = sha256_text(original_text)
        row = get_latest_evaluation_by_checksum(conn, checksum)
        if not row:
            return jsonify({"error": "not_found", "message": "keine Evaluation für diesen originalText gefunden"}), 404

        eval_id = row["id"]
        with conn:
            conn.execute(
                "INSERT INTO rewritten_requirement(evaluation_id, text) VALUES (?, ?)",
                (eval_id, text),
            )

        return jsonify({"evaluationId": eval_id, "status": "saved"}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/corrections/apply")
def apply_corrections():
    """
    Wendet ausgewählte Suggestions (Atoms) auf eine Anforderung an und erzeugt 1..N neue Umschreibungen.
    Body:
      {
        "originalText": "string",              # erforderlich, wenn evaluationId fehlt
        "evaluationId": "ev_...",              # optional; wenn nicht gesetzt, wird Evaluation erzeugt/ermittelt
        "selectedSuggestions": [ {...}, ... ], # Liste von Atom-Objekten (mind. correction/acceptance_criteria/metrics)
        "mode": "merge" | "split",             # optional, default "merge"
        "context": {}                          # optional
      }
    Response:
      {
        "evaluationId": "ev_...",
        "items": [ { "rewrittenId": number, "redefinedRequirement": "..." }, ... ]
      }
    """
    try:
        data = request.get_json(silent=True) or {}
        original_text = data.get("originalText")
        evaluation_id = data.get("evaluationId")
        selected = data.get("selectedSuggestions") or data.get("selectedAtoms") or []
        mode = str(data.get("mode", "merge")).lower()
        context = data.get("context") or {}

        if not isinstance(selected, list) or not selected:
            return jsonify({"error": "invalid_request", "message": "selectedSuggestions muss eine nicht-leere Liste sein"}), 400

        if not evaluation_id and not (isinstance(original_text, str) and original_text.strip()):
            return jsonify({"error": "invalid_request", "message": "originalText oder evaluationId erforderlich"}), 400

        conn = get_db()
        # Kriterien laden für ensure_evaluation_exists
        crits = load_criteria(conn)
        criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

        # Falls evaluationId fehlt → Evaluation sicherstellen/erzeugen
        if not evaluation_id:
            evaluation_id, _ = ensure_evaluation_exists(original_text, context, criteria_keys)

        # Für LLM-Apply benötigen wir den Originaltext (strikt)
        if not (isinstance(original_text, str) and original_text.strip()):
            return jsonify({"error": "invalid_request", "message": "originalText fehlt"}), 400

        # LLM-gestützte Umschreibung(en) erzeugen
        items = llm_apply_with_suggestions(original_text, context, selected, mode)
        results = []
        with conn:
            for it in items or []:
                txt = str(it.get("redefinedRequirement", "")).strip()
                if not txt:
                    continue
                cur = conn.execute(
                    "INSERT INTO rewritten_requirement(evaluation_id, text) VALUES (?, ?)",
                    (evaluation_id, txt),
                )
                rw_id = cur.lastrowid
                results.append({"rewrittenId": rw_id, "redefinedRequirement": txt})

        return jsonify({"evaluationId": evaluation_id, "items": results}), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/corrections/decision/batch")
def set_correction_decision_batch():
    """
    Setzt Entscheidungen im Batch.
    Body: { "items": [ { "evaluationId": "...", "decision": "accepted"|"rejected", "decidedBy": "optional" }, ... ] }
    """
    try:
        data = request.get_json(silent=True) or {}
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return jsonify({"error": "invalid_request", "message": "items ist erforderlich und muss eine Liste sein"}), 400

        conn = get_db()
        updated = 0
        errors = []

        with conn:
            for it in items:
                try:
                    evaluation_id = it.get("evaluationId")
                    decision = str(it.get("decision", "")).lower()
                    decided_by = it.get("decidedBy")

                    if not isinstance(evaluation_id, str) or not evaluation_id.strip():
                        raise ValueError("evaluationId fehlt oder ist leer")
                    if decision not in ("accepted", "rejected"):
                        raise ValueError("decision muss accepted oder rejected sein")

                    rw = get_latest_rewrite_row_for_eval(conn, evaluation_id)
                    if not rw:
                        raise ValueError("keine Correction vorhanden")

                    existing = conn.execute(
                        "SELECT id FROM correction_decision WHERE evaluation_id = ? LIMIT 1",
                        (evaluation_id,),
                    ).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE correction_decision SET rewritten_id = ?, decision = ?, decided_by = ?, decided_at = CURRENT_TIMESTAMP WHERE evaluation_id = ?",
                            (rw["id"], decision, decided_by, evaluation_id),
                        )
                    else:
                        conn.execute(
                            "INSERT INTO correction_decision(evaluation_id, rewritten_id, decision, decided_by) VALUES (?, ?, ?, ?)",
                            (evaluation_id, rw["id"], decision, decided_by),
                        )
                    updated += 1
                except Exception as ie:
                    errors.append({"evaluationId": it.get("evaluationId"), "error": str(ie)})
        return jsonify({"updated": updated, "errors": errors}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
# --- Added validate endpoint for array-based evaluation ---
@api_bp.get("/api/v1/demo/requirements")
def demo_requirements():
    """
    Liest eine Markdown-Tabelle aus und liefert die Requirements als Liste zurück.
    bevorzugter Pfad: settings.REQUIREMENTS_MD_PATH
    Fallbacks: /data/requirements.md, /app/docs/requirements.md
    Response:
      { "items": [ { "id": "R1", "requirementText": "...", "context": "..." }, ... ] }
    """
    try:
        candidates = [
            getattr(settings, "REQUIREMENTS_MD_PATH", None),
            "/app/data/requirements.md",
            "/app/data/docs/requirements.md",
            "/app/docs/requirements.md",
        ]
        md_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if not md_path:
            # Fallback: nimm den ersten existierenden Pfad
            for p in candidates[1:]:  # Skip None settings path
                if p and os.path.exists(p):
                    md_path = p
                    break
        if not md_path:
            md_path = "/app/data/requirements.md"  # Default path
        items = parse_requirements_md(md_path)
        # nur id, requirementText, context zurückgeben
        return jsonify({"items": items}), 200
    except FileNotFoundError as e:
        return jsonify({"error": "not_found", "message": str(e)}), 404
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# Entfernt: veraltete /api/validate (konsolidiert unter /api/v1/validate/batch)
# (frühere Implementierung entfernt zur Vereinheitlichung der API)
    """
    Erhält ein Array von Requirement-Strings und liefert eine detaillierte Auswertung
    pro Requirement inklusive Korrekturvorschlag zurück.

    Request:
      [
        "The vehicle attendant must have the ability to monitor the status of the shuttle.",
        "Das Shuttle muss manuell rückwärts fahren können."
      ]

    Response (Beispielstruktur):
      [
        {
          "id": 1,
          "originalText": "...",
          "correctedText": "...",
          "status": "accepted" | "rejected",
          "evaluation": [
            {"criterion": "clarity", "isValid": true, "reason": ""},
            {"criterion": "measurability", "isValid": false, "reason": "..." }
          ]
        },
        ...
      ]
    """
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, list) or not all(isinstance(x, str) for x in payload):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400

        conn = get_db()
        crits = load_criteria(conn)
        criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

        results: List[Dict[str, Any]] = []
        for idx, txt in enumerate(payload, start=1):
            details = llm_evaluate(txt, criteria_keys, {})
            score = weighted_score(details, crits)
            verdict = compute_verdict(score, settings.VERDICT_THRESHOLD)
            rewritten = llm_rewrite(txt, {})
            eval_items: List[Dict[str, Any]] = []
            for d in details:
                eval_items.append(
                    {
                        "criterion": d["criterion"],
                        "isValid": bool(d.get("passed", False)),
                        "reason": "" if d.get("passed") else str(d.get("feedback", "")),
                    }
                )
            status = "accepted" if verdict == "pass" else "rejected"
            results.append(
                {
                    "id": idx,
                    "originalText": txt,
                    "correctedText": rewritten if rewritten else txt,
                    "status": status,
                    "evaluation": eval_items,
                }
            )

        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# --- Optimierte Endpoints aus api_optimized zusammengeführt ---

def process_requirement_parallel(requirement_text: str, criteria_keys: List[str], req_id: int) -> Dict[str, Any]:
    """
    Verarbeitet ein einzelnes Requirement parallel mit beiden LLM-Aufrufen
    """
    context: Dict[str, Any] = {}

    # Parallele Ausführung von evaluate und rewrite
    with futures.ThreadPoolExecutor(max_workers=5) as executor:
        eval_future = executor.submit(llm_evaluate, requirement_text, criteria_keys, context)
        rewrite_future = executor.submit(llm_rewrite, requirement_text, context)

        # Warte auf beide Ergebnisse
        try:
            details = eval_future.result(timeout=30)  # 30s timeout
            rewritten = rewrite_future.result(timeout=30)
        except Exception as e:
            # Fallback bei Fehlern
            details = [{"criterion": c, "score": 0.5, "passed": False, "feedback": f"Error: {str(e)}"} for c in criteria_keys]
            rewritten = requirement_text

    # Score berechnen
    conn = get_db()
    crits = load_criteria(conn, criteria_keys)
    score = weighted_score(details, crits)
    verdict = compute_verdict(score, settings.VERDICT_THRESHOLD)

    # Evaluation Items formatieren
    eval_items: List[Dict[str, Any]] = []
    for d in details:
        eval_items.append({
            "criterion": d["criterion"],
            "isValid": bool(d.get("passed", False)),
            "reason": "" if d.get("passed") else str(d.get("feedback", "")),
        })

    status = "accepted" if verdict == "pass" else "rejected"

    return {
        "id": req_id,
        "originalText": requirement_text,
        "correctedText": rewritten if rewritten else requirement_text,
        "status": status,
        "evaluation": eval_items,
        "score": score,
        "verdict": verdict
    }


# Entfernt: veraltete /api/validate/parallel (in api.py konsolidiert/ersetzt)
    """
    Optimierter Endpoint für parallele Verarbeitung von Requirements
    """
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, list) or not all(isinstance(x, str) for x in payload):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400

        conn = get_db()
        crits = load_criteria(conn)
        criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

        results: List[Dict[str, Any]] = []

        # Verarbeite in Batches für bessere Kontrolle
        for batch in chunked(payload, settings.BATCH_SIZE):
            with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as executor:
                futures_list = []
                for idx, txt in enumerate(batch):
                    req_id = len(results) + idx + 1
                    future = executor.submit(process_requirement_parallel, txt, criteria_keys, req_id)
                    futures_list.append(future)

                for future in futures.as_completed(futures_list):
                    try:
                        result = future.result(timeout=60)  # 60s timeout pro Requirement
                        results.append(result)
                    except Exception as e:
                        error_result = {
                            "id": len(results) + 1,
                            "originalText": "Error processing requirement",
                            "correctedText": "Error processing requirement",
                            "status": "rejected",
                            "evaluation": [{"criterion": c, "isValid": False, "reason": f"Processing error: {str(e)}"} for c in criteria_keys],
                            "score": 0.0,
                            "verdict": "fail"
                        }
                        results.append(error_result)

        results.sort(key=lambda x: x["id"])
        return jsonify(results), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.route("/api/v1/validate/suggest", methods=["POST"], strict_slashes=False)
def validate_suggest():
    """
    Erwartet Array[String] und liefert Atoms (Suggestions) je Requirement zurück.
    Response: {"items": {"REQ_1": {"suggestions": [...]}, ...}}
    """
    try:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict) and "items" in payload and isinstance(payload["items"], list):
            items = payload["items"]
        else:
            items = payload
        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400

        rows: List[Dict[str, str]] = []
        for idx, txt in enumerate(items, start=1):
            rows.append({
                "id": f"REQ_{idx}",
                "requirementText": txt,
                "context": "{}"
            })
        sug_map = process_suggestions(rows)
        return jsonify({"items": sug_map}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/validate/batch")
def validate_batch_optimized():
    """
    Nutzt die vorhandene Batch-Infrastruktur (process_evaluations/process_rewrites).
    Optional: includeSuggestions=1 (Query oder Body) liefert zusätzlich Suggestions (Atoms).
    """
    try:
        payload = request.get_json(silent=True)
        lg = logging.getLogger("app")
        corr = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or "n/a"
        op_id = f"{corr}:validate_batch"
        start_ts = time.time()
        # Unterstütze sowohl reines Array als auch Objekt mit {items: [...], includeSuggestions: ...}
        include_flag = False
        if isinstance(payload, dict):
            include_flag = str(payload.get("includeSuggestions", "")).lower() in ("1", "true", "yes")
            items = payload.get("items")
        else:
            items = payload

        if not include_flag:
            q = request.args.get("includeSuggestions")
            if isinstance(q, str):
                include_flag = q.lower() in ("1", "true", "yes")

        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400

        # Domain-Event: requirements.process.start
        json_log(
            lg, logging.INFO, "requirements.process.start",
            correlation_id=corr, operation_id=op_id, items=len(items)
        )

        # Konvertiere zu Batch-Format
        rows: List[Dict[str, str]] = []
        for idx, txt in enumerate(items, start=1):
            rows.append({
                "id": f"REQ_{idx}",
                "requirementText": txt,
                "context": "{}"
            })

        # Domain-Event: batch.start
        total = len(rows)
        batch_size = settings.BATCH_SIZE
        total_chunks = (total + batch_size - 1) // batch_size
        json_log(
            lg, logging.INFO, "batch.start",
            correlation_id=corr, operation_id=op_id,
            kind="validate", total=total, batch_size=batch_size, total_chunks=total_chunks
        )

        # Nutze die optimierte Batch-Verarbeitung, mit robustem Fallback bei Fehlern
        try:
            with futures.ThreadPoolExecutor(max_workers=2) as executor:
                eval_future = executor.submit(process_evaluations, rows)
                rewrite_future = executor.submit(process_rewrites, rows)
                eval_results = eval_future.result()
                rewrite_results = rewrite_future.result()
        except Exception as e:
            # Fallback: sequentielle Verarbeitung ohne Pool
            json_log(
                lg, logging.ERROR, "batch.error",
                correlation_id=corr, operation_id=op_id,
                err_type=type(e).__name__, message=str(e)
            )
            # Kriterien bestimmen wie in Batch-Processing
            try:
                conn_fb = get_db()
                crits_fb = load_criteria(conn_fb)
                criteria_keys_fb = [c["key"] for c in crits_fb] or ["clarity", "testability", "measurability"]
            except Exception:
                criteria_keys_fb = ["clarity", "testability", "measurability"]

            eval_results_fallback: Dict[str, Any] = {}
            rewrite_results_fallback: Dict[str, Any] = {}

            for row in rows:
                rid = row["id"]
                requirement_text = row["requirementText"]
                # Kontext defensiv: in diesem Endpoint ist es "{}" -> leeres Dict
                context_obj: Dict[str, Any] = {}
                try:
                    eval_id, summ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys_fb)
                    eval_results_fallback[rid] = {"evaluationId": eval_id, **summ}
                except Exception as ee:
                    # Erzeuge minimale Defaults, damit Response nicht abbricht
                    eval_results_fallback[rid] = {
                        "evaluationId": None,
                        "score": 0.0,
                        "verdict": "fail",
                        "model": getattr(settings, "OPENAI_MODEL", "n/a"),
                        "latencyMs": 0,
                    }
                    json_log(
                        lg, logging.DEBUG, "eval.ensure.skip",
                        correlation_id=corr, operation_id=op_id,
                        error=str(ee), requirement_id=rid
                    )
                try:
                    rewritten = llm_rewrite(requirement_text, context_obj)
                    rewrite_results_fallback[rid] = {"redefinedRequirement": rewritten}
                except Exception as re:
                    rewrite_results_fallback[rid] = {"redefinedRequirement": requirement_text}
                    json_log(
                        lg, logging.DEBUG, "rewrite.skip",
                        correlation_id=corr, operation_id=op_id,
                        error=str(re), requirement_id=rid
                    )
            eval_results = eval_results_fallback
            rewrite_results = rewrite_results_fallback

        sugg_results: Dict[str, Any] = {}
        if include_flag:
            try:
                sugg_results = process_suggestions(rows)
            except Exception as se:
                # Robust: Suggestions optional, Fehler ignorieren
                sugg_results = {}

        # Kombiniere Ergebnisse
        results: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            req_id = row["id"]
            eval_data = eval_results.get(req_id, {})
            rewrite_data = rewrite_results.get(req_id, {})

            conn = get_db()
            eval_id = eval_data.get("evaluationId")
            eval_details: List[Dict[str, Any]] = []

            if eval_id:
                try:
                    detail_rows = conn.execute(
                        "SELECT criterion_key, score, passed, feedback FROM evaluation_detail WHERE evaluation_id = ?",
                        (eval_id,)
                    ).fetchall()
                    for detail in detail_rows:
                        eval_details.append({
                            "criterion": detail["criterion_key"],
                            "isValid": bool(detail["passed"]),
                            "reason": "" if detail["passed"] else detail["feedback"]
                        })
                except Exception as de:
                    json_log(
                        lg, logging.INFO, "eval.details.skip",
                        correlation_id=corr, operation_id=op_id,
                        evaluation_id=eval_id, error=str(de)
                    )

            status = "accepted" if eval_data.get("verdict") == "pass" else "rejected"

            result = {
                "id": idx,
                "originalText": row["requirementText"],
                "correctedText": rewrite_data.get("redefinedRequirement", row["requirementText"]),
                "status": status,
                "evaluation": eval_details,
                "score": eval_data.get("score", 0.0),
                "verdict": eval_data.get("verdict", "fail")
            }
            if include_flag:
                result["suggestions"] = sugg_results.get(req_id, {}).get("suggestions", [])
            results.append(result)

        # Domain-Event: batch.end
        json_log(
            lg, logging.INFO, "batch.end",
            correlation_id=corr, operation_id=op_id,
            processed_count=len(results)
        )
        # Domain-Event: requirements.process.end
        duration_ms = int((time.time() - start_ts) * 1000)
        json_log(
            lg, logging.INFO, "requirements.process.end",
            correlation_id=corr, operation_id=op_id,
            processed_count=len(results), duration_ms=duration_ms
        )

        return jsonify(results), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/validate/config")
def get_validation_config():
    """
    Liefert aktuelle Performance-Konfiguration
    """
    return jsonify({
        "batchSize": settings.BATCH_SIZE,
        "maxParallel": settings.MAX_PARALLEL,
        "model": settings.OPENAI_MODEL,
        "verdictThreshold": settings.VERDICT_THRESHOLD,
        "llmMaxTokens": getattr(settings, "LLM_MAX_TOKENS", 0),
        "llmTemperature": getattr(settings, "LLM_TEMPERATURE", 0.0)
    }), 200


@api_bp.post("/api/validate/config")
def update_validation_config():
    """
    Aktualisiert Performance-Konfiguration zur Laufzeit
    """
    try:
        data = request.get_json(silent=True) or {}

        if "batchSize" in data:
            settings.BATCH_SIZE = max(1, min(50, int(data["batchSize"])))
        if "maxParallel" in data:
            settings.MAX_PARALLEL = max(1, min(10, int(data["maxParallel"])))
        if "verdictThreshold" in data:
            settings.VERDICT_THRESHOLD = max(0.0, min(1.0, float(data["verdictThreshold"])))

        return jsonify({
            "message": "Konfiguration aktualisiert",
            "newConfig": {
                "batchSize": settings.BATCH_SIZE,
                "maxParallel": settings.MAX_PARALLEL,
                "verdictThreshold": settings.VERDICT_THRESHOLD
            }
        }), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
# --- NDJSON Streaming-Endpoints (additiv, bestehende bleiben unverändert) ---

@api_bp.post("/api/v1/validate/batch/stream")
def validate_batch_stream():
    """
    NDJSON-Stream: sendet pro Requirement ein Ergebnis (Evaluate+Rewrite, optional Suggestions) als einzelne JSON-Zeile.
    Keine UI-Änderungen nötig: fetch + ReadableStream + Zeilenweise JSON parsen.
    """
    from flask import Response, stream_with_context
    import json
    import time
    import concurrent.futures as futures

    lg = logging.getLogger("app")
    start_ts = time.time()
    payload = request.get_json(silent=True)
    corr = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or "n/a"
    op_id = f"{corr}:validate_batch_stream"

    # Request-Formate wie bei validate_batch_optimized
    include_flag = False
    if isinstance(payload, dict):
        include_flag = str(payload.get("includeSuggestions", "")).lower() in ("1", "true", "yes")
        items = payload.get("items")
    else:
        items = payload

    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        def bad():
            yield json.dumps({"event": "error", "message": "Erwarte ein Array von Strings"}, ensure_ascii=False) + "\n"
        return Response(stream_with_context(bad()), mimetype="application/x-ndjson")

    # Zu Rows konvertieren (id, requirementText)
    rows = [{"id": f"REQ_{i}", "requirementText": txt, "context": "{}"} for i, txt in enumerate(items, start=1)]

    json_log(
        lg, logging.INFO, "stream.start",
        correlation_id=corr, operation_id=op_id,
        batch_size=len(rows), includeSuggestions=include_flag,
        mode="ndjson", max_parallel=settings.MAX_PARALLEL,
        batch_size_effective=settings.BATCH_SIZE,
    )

    def gen():
        processed = 0

        # Worker je Requirement
        def worker(row):
            rid = row["id"]
            requirement_text = row["requirementText"]
            context_obj = {}
            t0 = time.time()
            try:
                # Evaluation persistieren/ermitteln
                criteria_keys = [c["key"] for c in load_criteria(get_db())] or ["clarity", "testability", "measurability"]
                eval_id, summ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys)

                # Evaluation-Details aus DB lesen
                eval_details = []
                try:
                    conn = get_db()
                    detail_rows = conn.execute(
                        "SELECT criterion_key, score, passed, feedback FROM evaluation_detail WHERE evaluation_id = ?",
                        (eval_id,),
                    ).fetchall()
                    for d in detail_rows:
                        eval_details.append({
                            "criterion": d["criterion_key"],
                            "isValid": bool(d["passed"]),
                            "reason": "" if d["passed"] else d["feedback"],
                        })
                except Exception:
                    pass

                # Rewrite (nicht zwingend persistent)
                rewritten = llm_rewrite(requirement_text, context_obj)

                # Optional Suggestions (Atoms)
                suggestions = []
                if include_flag:
                    try:
                        atoms = llm_suggest(requirement_text, context_obj)
                        suggestions = atoms or []
                        # Optional: Atoms persistieren (best effort)
                        try:
                            with get_db() as c2:
                                import json as _json
                                for atom in suggestions:
                                    c2.execute(
                                        "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                                        (eval_id, _json.dumps(atom, ensure_ascii=False), "atom"),
                                    )
                        except Exception:
                            pass
                    except Exception as se:
                        return {"event": "error", "reqId": rid, "message": str(se)}

                status = "accepted" if summ.get("verdict") == "pass" else "rejected"
                out = {
                    "reqId": rid,
                    "originalText": requirement_text,
                    "status": status,
                    "score": summ.get("score", 0.0),
                    "verdict": summ.get("verdict", "fail"),
                    "redefinedRequirement": rewritten if rewritten else requirement_text,
                    "evaluation": eval_details,
                    "latencyMs": int((time.time() - t0) * 1000),
                }
                if include_flag:
                    out["suggestions"] = suggestions
                return out
            except Exception as e:
                return {"event": "error", "reqId": rid, "message": str(e)}

        # Parallel verarbeiten und as_completed streamen (out-of-order für schnellste UX)
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            futs = [ex.submit(worker, r) for r in rows]
            for fut in futures.as_completed(futs):
                processed += 1
                try:
                    result = fut.result()
                except Exception as e:
                    result = {"event": "error", "message": str(e)}

                if isinstance(result, dict) and result.get("event") == "error":
                    json_log(lg, logging.INFO, "stream.item", correlation_id=corr, operation_id=op_id,
                             reqId=result.get("reqId"), status="error", error=result.get("message"))
                    yield json.dumps(result, ensure_ascii=False) + "\n"
                else:
                    json_log(lg, logging.INFO, "stream.item", correlation_id=corr, operation_id=op_id,
                             reqId=result.get("reqId"), duration_ms=result.get("latencyMs"), status="ok")
                    yield json.dumps(result, ensure_ascii=False) + "\n"

        duration_ms = int((time.time() - start_ts) * 1000)
        json_log(lg, logging.INFO, "stream.end", correlation_id=corr, operation_id=op_id,
                 processed_count=processed, duration_ms=duration_ms)
        yield json.dumps({"event": "end", "processed": processed, "durationMs": duration_ms}, ensure_ascii=False) + "\n"

    return Response(stream_with_context(gen()), mimetype="application/x-ndjson")


@api_bp.post("/api/v1/validate/suggest/stream")
def validate_suggest_stream():
    """
    NDJSON-Stream: sendet pro Requirement Suggestions (Atoms) als einzelne JSON-Zeile.
    """
    from flask import Response, stream_with_context
    import json
    import time
    import concurrent.futures as futures

    lg = logging.getLogger("app")
    start_ts = time.time()
    payload = request.get_json(silent=True)
    corr = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or "n/a"
    op_id = f"{corr}:validate_suggest_stream"

    # Optional: force (Bypass künftiger Cache-Shortcuts)
    if isinstance(payload, dict):
        items = payload.get("items")
        # force wird aktuell nicht ausgewertet (Platzhalter für Cache-Erweiterung)
        _force = str(payload.get("force", "")).lower() in ("1", "true", "yes")
    else:
        items = payload
        _force = False

    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        def bad():
            yield json.dumps({"event": "error", "message": "Erwarte ein Array von Strings"}, ensure_ascii=False) + "\n"
        return Response(stream_with_context(bad()), mimetype="application/x-ndjson")

    rows = [{"id": f"REQ_{i}", "requirementText": txt, "context": "{}"} for i, txt in enumerate(items, start=1)]
    json_log(
        lg, logging.INFO, "stream.start",
        correlation_id=corr, operation_id=op_id,
        batch_size=len(rows), mode="ndjson", max_parallel=settings.MAX_PARALLEL,
    )

    def gen():
        processed = 0

        def worker(row):
            rid = row["id"]
            requirement_text = row["requirementText"]
            context_obj = {}
            t0 = time.time()
            try:
                criteria_keys = [c["key"] for c in load_criteria(get_db())] or ["clarity", "testability", "measurability"]
                eval_id, _ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys)
                atoms = llm_suggest(requirement_text, context_obj) or []
                # Optional: Atoms persistieren (best effort)
                try:
                    with get_db() as c2:
                        import json as _json
                        for atom in atoms:
                            c2.execute(
                                "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                                (eval_id, _json.dumps(atom, ensure_ascii=False), "atom"),
                            )
                except Exception:
                    pass

                return {
                    "reqId": rid,
                    "originalText": requirement_text,
                    "evaluationId": eval_id,
                    "suggestions": atoms,
                    "latencyMs": int((time.time() - t0) * 1000),
                    "source": "llm",
                }
            except Exception as e:
                return {"event": "error", "reqId": rid, "message": str(e)}

        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            futs = [ex.submit(worker, r) for r in rows]
            for fut in futures.as_completed(futs):
                processed += 1
                try:
                    result = fut.result()
                except Exception as e:
                    result = {"event": "error", "message": str(e)}

                if isinstance(result, dict) and result.get("event") == "error":
                    json_log(lg, logging.INFO, "stream.item", correlation_id=corr, operation_id=op_id,
                             reqId=result.get("reqId"), status="error", error=result.get("message"))
                    yield json.dumps(result, ensure_ascii=False) + "\n"
                else:
                    json_log(lg, logging.INFO, "stream.item", correlation_id=corr, operation_id=op_id,
                             reqId=result.get("reqId"), duration_ms=result.get("latencyMs"), status="ok", source="llm")
                    yield json.dumps(result, ensure_ascii=False) + "\n"

        duration_ms = int((time.time() - start_ts) * 1000)
        json_log(lg, logging.INFO, "stream.end", correlation_id=corr, operation_id=op_id,
                 processed_count=processed, duration_ms=duration_ms)
        yield json.dumps({"event": "end", "processed": processed, "durationMs": duration_ms}, ensure_ascii=False) + "\n"

    return Response(stream_with_context(gen()), mimetype="application/x-ndjson")

# =========================
# RAG / VECTOR INGEST API
# =========================

@api_bp.post("/api/v1/files/ingest")
def files_ingest():
    """
    Multipart Upload von Requirements-Dateien. Unterstützte Typen: .md, .pdf, .docx, .txt, .json
    Optionale Formfelder:
      - chunkMin, chunkMax, chunkOverlap (Token-Parameter)
      - collection (Qdrant-Collection; Default settings.QDRANT_COLLECTION)
      - structured=1|true|yes|on → aktiviert LangExtract je Chunk (span-grounded Extraktionen)
    Ablauf: Extract -> Chunk -> optional: LangExtract -> Embeddings -> Upsert(Qdrant)
    Response: {
      countFiles, countBlocks, countChunks, upserted, collection, qdrantPort,
      lxEnabled?, lxChunks?, lxExtracted?, lxCoverageAvg?
    }
    Hinweise:
      - Erfordert OPENAI_API_KEY und OPENAI_MODEL in settings oder .env (für LangExtract).
      - Fehler in LangExtract führen nicht zum Abbruch; pro Chunk wird payload.lx.error gesetzt.
    """
    try:
        # Dateien einsammeln (akzeptiere 'files' und Legacy 'file')
        files = []
        try:
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f:
                    files = [f]
        except Exception:
            files = []

        if not files:
            return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben: form field 'files' oder 'file' fehlt"}), 400

        # Parameter
        def _to_int(name: str, default: int) -> int:
            v = request.form.get(name)
            try:
                return int(v)
            except Exception:
                return default

        chunk_min = _to_int("chunkMin", getattr(settings, "CHUNK_TOKENS_MIN", 200))
        chunk_max = _to_int("chunkMax", getattr(settings, "CHUNK_TOKENS_MAX", 400))
        chunk_overlap = _to_int("chunkOverlap", getattr(settings, "CHUNK_OVERLAP_TOKENS", 50))
        collection = request.form.get("collection") or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")

        # Extract
        raw_records = []
        for f in files:
            filename = f.filename or "unknown"
            data = f.read() or b""
            ctype = f.mimetype or ""
            parts = extract_texts(filename, data, ctype)
            raw_records.extend(parts)

        # Chunk
        payloads = chunk_payloads(raw_records, chunk_min, chunk_max, chunk_overlap)
        texts = [p["text"] for p in payloads]
        if not texts:
            return jsonify({"error": "empty", "message": "kein extrahierbarer Text gefunden"}), 200

        # Optional: LangExtract (aktiviert via multipart form field structured=1)
        structured_flag = str(request.form.get("structured", "")).lower() in ("1", "true", "yes", "on")
        lx_enabled = False
        total_extractions = 0
        coverage_sum = 0.0
        if structured_flag:
            try:
                import langextract as lx  # type: ignore
                lx_enabled = True

                def _normalize_lx_result(res, chunk_text: str):
                    # In generisches Dict bringen
                    try:
                        if hasattr(res, "to_dict"):
                            data = res.to_dict()
                        elif isinstance(res, dict):
                            data = res
                        else:
                            data = getattr(res, "__dict__", {}) or {}
                    except Exception:
                        data = {}

                    # Extractions sammeln (verschiedene Rückgabeformen unterstützen)
                    exts_raw = []
                    if isinstance(data, dict):
                        # 1) Top-Level extractions
                        if isinstance(data.get("extractions"), list):
                            exts_raw.extend(data.get("extractions") or [])
                        # 2) Dokument-Container
                        docs = data.get("documents") or data.get("items") or []
                        if isinstance(docs, list):
                            for d in docs:
                                if isinstance(d, dict) and isinstance(d.get("extractions"), list):
                                    exts_raw.extend(d.get("extractions") or [])
                    else:
                        # Objektstruktur: res.documents[*].extractions
                        docs = getattr(res, "documents", None) or getattr(res, "items", None)
                        if isinstance(docs, list):
                            for d in docs:
                                x = getattr(d, "extractions", None)
                                if isinstance(x, list):
                                    exts_raw.extend(x)

                    out = []
                    intervals = []
                    n = len(chunk_text or "")

                    def _coerce_int(v, default=0):
                        try:
                            return int(v)
                        except Exception:
                            return default

                    for e in exts_raw or []:
                        try:
                            # sowohl dict- als auch objektartige Zugriffe unterstützen
                            get = (lambda k: (e.get(k) if isinstance(e, dict) else getattr(e, k, None)))

                            # Klassen-/Textfelder mit Fallbacks
                            ec = get("extraction_class") or get("cls") or get("class") or get("label")
                            et = get("extraction_text") or get("text") or get("span_text")

                            # Char-Interval-Varianten
                            ci = get("char_interval") or get("char_span") or get("span") or get("interval")
                            s, epos = None, None
                            if isinstance(ci, dict):
                                # start_pos/end_pos | start/end
                                s = _coerce_int(ci.get("start_pos", ci.get("start")))
                                epos = _coerce_int(ci.get("end_pos", ci.get("end")))
                            elif ci is not None:
                                # Objekt mit Attributen
                                s = _coerce_int(getattr(ci, "start_pos", getattr(ci, "start", 0)))
                                epos = _coerce_int(getattr(ci, "end_pos", getattr(ci, "end", 0)))

                            # Falls kein Interval vorliegt: heuristisch über Textsuche bestimmen
                            if (s is None or epos is None or epos <= s) and isinstance(et, str) and et.strip():
                                try:
                                    idx = (chunk_text or "").find(et)
                                    if idx >= 0:
                                        s = idx
                                        epos = idx + len(et)
                                except Exception:
                                    pass

                            # Clamp und Validierung
                            s = 0 if s is None else max(0, min(s, n))
                            epos = 0 if epos is None else max(0, min(epos, n))
                            if epos < s:
                                s, epos = epos, s

                            al = get("alignment_status")
                            attrs = get("attributes")
                            if not isinstance(attrs, dict):
                                attrs = {}

                            if isinstance(ec, str) and isinstance(et, str) and et.strip() and epos > s:
                                out.append({
                                    "extraction_class": ec,
                                    "extraction_text": et,
                                    "char_interval": {"start_pos": s, "end_pos": epos},
                                    "alignment_status": al or "match_exact",
                                    "attributes": attrs,
                                })
                                intervals.append((s, epos))
                        except Exception:
                            # robust gegen einzelne fehlerhafte Items
                            continue

                    # Coverage berechnen (vereinigt)
                    try:
                        merged = []
                        for st, en in sorted(intervals):
                            if not merged:
                                merged.append((st, en))
                            else:
                                pst, pen = merged[-1]
                                if st <= pen:
                                    merged[-1] = (pst, max(pen, en))
                                else:
                                    merged.append((st, en))
                        covered = sum(en - st for st, en in merged)
                        ratio = float(covered) / float(n) if n > 0 else 0.0
                    except Exception:
                        covered, ratio = 0, 0.0

                    return out, covered, ratio

                # Prompt konservativ (DE), Klassen/Attribute auf eure Domäne anpassbar
                _PROMPT = (
                    "Extrahiere Anforderungen, Constraints, Akteure, Fähigkeiten, Akzeptanzkriterien "
                    "und Relationen in strukturierter Form. Nutze ausschließlich exakte Textspannen "
                    "aus der Quelle (keine Paraphrasen). Überschneide Extraktionen nicht. "
                    "Klassen: requirement, constraint, actor, capability, acceptance_criterion, relation. "
                    "Gib sinnvolle Attribute (z. B. priority/category/type/rationale) an."
                )
                # Minimale Default-Beispiele für LangExtract (stabilere, span-grounded Extraktionen).
                # Wichtig: LangExtract erwartet ExampleData/Extraction Objekte (nicht nur Dicts).
                EXAMPLES = [
                    lx.data.ExampleData(
                        text="Der Operator MUSS das Shuttle manuell stoppen koennen.",
                        extractions=[
                            lx.data.Extraction(
                                extraction_class="requirement",
                                extraction_text="Operator MUSS das Shuttle manuell stoppen",
                                attributes={"priority": "must"},
                            ),
                            lx.data.Extraction(
                                extraction_class="actor",
                                extraction_text="Operator",
                                attributes={},
                            ),
                            lx.data.Extraction(
                                extraction_class="capability",
                                extraction_text="manuell stoppen",
                                attributes={},
                            ),
                        ],
                    )
                ]

                for idx, p in enumerate(payloads):
                    txt = p.get("text") or ""
                    try:
                        res = lx.extract(
                            text_or_documents=txt,
                            prompt_description=_PROMPT,
                            examples=EXAMPLES,  # minimale Default-Beispiele für zuverlässigere Extraktion
                            model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                            api_key=getattr(settings, "OPENAI_API_KEY", None),
                        )
                        exts, covered, ratio = _normalize_lx_result(res, txt)
                        p["payload"].setdefault("lx", {})
                        p["payload"]["lx"].update({
                            "version": "le.v1",
                            "provider": "openai",
                            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                            "run_id": str(int(time.time())),
                            "extractions": exts,
                            "coverage": {
                                "chunk_len": len(txt),
                                "covered": covered,
                                "coverage_ratio": round(ratio, 4),
                            },
                            "evidence": {
                                "sourceFile": p["payload"].get("sourceFile"),
                                "chunkIndex": p["payload"].get("chunkIndex"),
                                "sha1": p["payload"].get("sha1"),
                                "pageNo": p["payload"].get("pageNo"),
                            },
                        })
                        total_extractions += len(exts)
                        coverage_sum += ratio
                    except Exception as le:
                        # Fehler am einzelnen Chunk nur annotieren, Ingest fortsetzen
                        p["payload"].setdefault("lx", {})
                        p["payload"]["lx"].update({
                            "version": "le.v1",
                            "error": str(le),
                        })
            except Exception:
                # Import/Globalfehler → ohne LangExtract fortfahren
                lx_enabled = False

        # Embeddings
        vectors = build_embeddings(texts, model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))
        dim = get_embeddings_dim()

        # Upsert vorbereiten
        items = []
        for i, p in enumerate(payloads):
            items.append({
                "vector": vectors[i],
                "payload": p["payload"] | {"text": p["text"]},
            })

        client, eff_port = get_qdrant_client()
        upserted = upsert_points(items, client=client, collection_name=collection, dim=dim)

        resp = {
            "countFiles": len(files),
            "countBlocks": len(raw_records),
            "countChunks": len(payloads),
            "upserted": upserted,
            "collection": collection,
            "qdrantPort": eff_port
        }
        # LangExtract KPIs (aktiv, wenn structured=1 angefordert wurde)
        if structured_flag:
            lx_chunks = len(payloads) if lx_enabled else 0
            lx_cov_avg = round((coverage_sum / lx_chunks), 4) if lx_chunks > 0 else 0.0

            # Flache Vorschau für das Frontend aus den pro-Chunk-Extrakten
            lx_preview = []
            if lx_enabled:
                try:
                    for p in payloads:
                        pl = p.get("payload") or {}
                        lx = pl.get("lx") or {}
                        exts = lx.get("extractions") or []
                        for e in exts:
                            try:
                                ec = e.get("extraction_class") if isinstance(e, dict) else getattr(e, "extraction_class", None)
                                et = e.get("extraction_text") if isinstance(e, dict) else getattr(e, "extraction_text", None)
                                ci = e.get("char_interval") if isinstance(e, dict) else getattr(e, "char_interval", None)
                                al = e.get("alignment_status") if isinstance(e, dict) else getattr(e, "alignment_status", None)
                                attrs = e.get("attributes") if isinstance(e, dict) else getattr(e, "attributes", None)
                                if not isinstance(attrs, dict):
                                    attrs = {}
                                lx_preview.append({
                                    "extraction_class": ec,
                                    "extraction_text": et,
                                    "char_interval": ci,
                                    "alignment_status": al,
                                    "attributes": attrs,
                                    "sourceFile": pl.get("sourceFile"),
                                    "chunkIndex": pl.get("chunkIndex"),
                                })
                            except Exception:
                                continue
                except Exception:
                    lx_preview = []

            resp.update({
                "lxEnabled": bool(lx_enabled),
                "lxChunks": lx_chunks,
                "lxExtracted": int(total_extractions),
                "lxCoverageAvg": lx_cov_avg,
                "lxPreview": lx_preview,
            })
        return jsonify(resp), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# Legacy-Alias für ältere Frontends: /api/mining/upload -> /api/v1/files/ingest
@api_bp.post("/api/mining/upload")
def legacy_mining_upload():
    """
    Legacy-Alias für /api/v1/files/ingest.
    Direktes Delegieren an files_ingest(), damit auch ältere Frontends ohne Redirect funktionieren.
    Unterstützt sowohl 'file' (singular) als auch 'files' (plural) Felder.
    """
    try:
        return files_ingest()
    except Exception as e:
        return jsonify({"error": "legacy_alias_failed", "message": str(e)}), 500

@api_bp.get("/api/v1/vector/collections")
def vector_collections():
    try:
        cols = vs_list_collections()
        return jsonify({"items": cols}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/vector/health")
def vector_health():
    try:
        h = vs_health()
        return jsonify(h), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 200


@api_bp.route("/api/v1/vector/reset", methods=["POST", "DELETE"], strict_slashes=False)
def vector_reset():
    """
    Droppt die Qdrant-Collection und legt sie neu an.
    Optionaler Body/Query: { "collection"?: str, "dim"?: int }
    """
    try:
        data = request.get_json(silent=True) or {}
        collection = (
            data.get("collection")
            or request.args.get("collection")
            or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        )
        dim_val = data.get("dim")
        if dim_val is None:
            # erlaube optionalen Query-Parameter ?dim=1536
            try:
                dim_val = request.args.get("dim", type=int)
            except Exception:
                dim_val = None
        try:
            dim_int = int(dim_val) if dim_val else None
        except Exception:
            dim_int = None
        if not isinstance(dim_int, int) or dim_int <= 0:
            # Default: aktuelle Embeddings-Dimension
            dim_int = get_embeddings_dim()

        res = vs_reset_collection(collection_name=collection, dim=dim_int)
        cols = vs_list_collections()
        payload = {"status": "ok", "reset": res, "collections": cols}
        resp = make_response(jsonify(payload), 200)
        try:
            resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        except Exception:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/vector/reset")
def vector_reset_get():
    """
    Fallback-Variante via GET um Preflight/METHOD-Probleme zu vermeiden.
    Erfordert confirm=1 im Querystring.
    Optional: collection, dim.
    Beispiel: GET /api/v1/vector/reset?confirm=1
    """
    try:
        confirm = str(request.args.get("confirm", "")).lower()
        if confirm not in ("1", "true", "yes"):
            return jsonify({"error": "confirm_required", "message": "Use confirm=1 to reset the vector collection."}), 400
        collection = request.args.get("collection") or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        dim_q = request.args.get("dim", type=int)
        dim_int = dim_q if isinstance(dim_q, int) and dim_q > 0 else get_embeddings_dim()
        res = vs_reset_collection(collection_name=collection, dim=dim_int)
        cols = vs_list_collections()
        payload = {"status": "ok", "reset": res, "collections": cols, "method": "GET"}
        resp = make_response(jsonify(payload), 200)
        try:
            resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        except Exception:
            resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/vector/source/full")
def vector_source_full():
    """
    Liefert alle Chunks eines sourceFile zusammen mit aggregiertem Text.
    GET /api/v1/vector/source/full?source=requirements.md
    Response: { sourceFile, chunks: [{chunkIndex,text}], text }
    """
    try:
        source = request.args.get("source", type=str)
        if not source or not source.strip():
            return jsonify({"error": "invalid_request", "message": "source fehlt"}), 400

        # iterativ Fenster lesen, bis keine neuen Chunks mehr gefunden werden
        # wir lesen in Fenstern von 256 Chunks
        window = 256
        start = 0
        out_chunks = []
        seen = set()
        while True:
            batch = fetch_window_by_source_and_index(source, start, start + window)
            if not batch:
                break
            added = 0
            for c in batch:
                p = c.get("payload") or {}
                ci = p.get("chunkIndex")
                try:
                    ci = int(ci)
                except Exception:
                    ci = None
                t = str(p.get("text") or "")
                if ci is None:
                    continue
                if ci in seen:
                    continue
                seen.add(ci)
                out_chunks.append({"chunkIndex": ci, "text": t})
                added += 1
            if added == 0:
                break
            start += window + 1
            # Sicherheit: Abbruch, wenn extrem groß
            if len(seen) > 5000:
                break

        # sortieren
        out_chunks.sort(key=lambda x: (x["chunkIndex"] if x["chunkIndex"] is not None else 0))
        full_text = "\n".join([c["text"] for c in out_chunks if c["text"]])
        return jsonify({"sourceFile": source, "chunks": out_chunks, "text": full_text}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/rag/search")
def rag_search():
    """
    Einfache Vektor-Suche:
      GET /api/v1/rag/search?query=...&top_k=5&collection=...
    """
    try:
        query = request.args.get("query", "", type=str)
        if not query.strip():
            return jsonify({"error": "invalid_request", "message": "query fehlt"}), 400
        top_k = request.args.get("top_k", default=5, type=int)
        collection = request.args.get("collection", default=getattr(settings, "QDRANT_COLLECTION", "requirements_v1"), type=str)

        qvec = build_embeddings([query], model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))[0]
        hits = vs_search(qvec, top_k=top_k, collection_name=collection)
        return jsonify({"query": query, "topK": top_k, "collection": collection, "hits": hits}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


# ================
# Agent / Memory RAG
# ================
def _ref_requirements_count() -> int:
    """
    Liefert Anzahl referenzierter Requirements (gleiches Verfahren wie demo_requirements()).
    """
    try:
        candidates = [
            getattr(settings, "REQUIREMENTS_MD_PATH", None),
            "/app/data/requirements.md",
            "/app/data/docs/requirements.md",
            "/app/docs/requirements.md",
        ]
        md_path = next((p for p in candidates if p and os.path.exists(p)), None)
        if not md_path:
            for p in candidates[1:]:
                if p and os.path.exists(p):
                    md_path = p
                    break
        if not md_path:
            md_path = "/app/data/requirements.md"
        items = parse_requirements_md(md_path)
        return len(items or [])
    except Exception:
        return 0


def _policy_match(query_lc: str, includes: list[str]) -> bool:
    try:
        toks = [t.strip().lower() for t in includes or [] if isinstance(t, str) and t.strip()]
        return all(t in query_lc for t in toks) if toks else False
    except Exception:
        return False


def _apply_policies(query: str) -> tuple[str, int, list[str], list[str], list[str]]:
    """
    Gibt (effective_query, top_k, prefer_sources, agent_notes, triggered_policy_ids) zurück.
    """
    q_lc = (query or "").lower()
    policies = _mem_store.load_policies()
    top_k = 5
    prefer_sources: list[str] = []
    notes: list[str] = []
    triggered: list[str] = []
    eff_query = query

    for rule in policies:
        rid = str(rule.get("id") or "")
        match = rule.get("match") or {}
        inc = match.get("includes") or []
        if _policy_match(q_lc, inc):
            action = rule.get("action") or {}
            a_type = action.get("type")
            triggered.append(rid)
            if a_type == "prefer_sources":
                pref = action.get("prefer") or []
                prefer_sources.extend([str(x) for x in pref if isinstance(x, str)])
                if isinstance(action.get("top_k"), int) and action["top_k"] > top_k:
                    top_k = int(action["top_k"])
                notes.append(f"policy:{rid} prefer={pref} top_k={top_k}")
            elif a_type == "rewrite_hint":
                add = str(action.get("rewrite_add") or "").strip()
                if add:
                    eff_query = f"{eff_query} {add}"
                pref = action.get("prefer") or []
                prefer_sources.extend([str(x) for x in pref if isinstance(x, str)])
                if isinstance(action.get("top_k"), int) and action["top_k"] > top_k:
                    top_k = int(action["top_k"])
                notes.append(f"policy:{rid} rewrite_add='{add}' prefer={pref} top_k={top_k}")
            elif a_type == "use_ref_count":
                # Spezialfall – wird im Endpoint behandelt
                notes.append(f"policy:{rid} use_ref_count")
            else:
                notes.append(f"policy:{rid} no-op")

    # Deduplicate sources while preserving order
    seen = set()
    prefer_sources = [x for x in prefer_sources if not (x in seen or seen.add(x))]
    return eff_query, top_k, prefer_sources, notes, triggered


def _re_rank_hits(hits: list[dict], prefer_sources: list[str]) -> list[dict]:
    """
    Boostet Treffer, deren payload.sourceFile in prefer_sources liegt.
    Sortiert danach absteigend nach (is_preferred, score).
    """
    if not hits or not prefer_sources:
        return hits
    pref_lc = [s.lower() for s in prefer_sources]
    def is_pref(h: dict) -> int:
        try:
            src = str((h.get("payload") or {}).get("sourceFile") or "").lower()
            return 1 if any(p in src for p in pref_lc) else 0
        except Exception:
            return 0
    def score_of(h: dict) -> float:
        try:
            s = h.get("score")
            return float(s) if isinstance(s, (int, float)) else 0.0
        except Exception:
            return 0.0
    return sorted(hits, key=lambda h: (is_pref(h), score_of(h)), reverse=True)


def _build_context_from_hit(hit: dict, window: int = 2) -> Dict[str, Any]:
    """
    Liefert ein erweitertes Kontextfenster um den getroffenen Chunk (±window) zurück.
    Nutzt Qdrant-Scroll via fetch_window_by_source_and_index().
    """
    try:
        p = hit.get("payload") or {}
        source = str(p.get("sourceFile") or "")
        idx = int(p.get("chunkIndex"))
    except Exception:
        return {"chunks": [], "text": "", "sourceFile": None, "chunkStart": None, "chunkEnd": None}

    start_idx = max(0, idx - int(window))
    end_idx = idx + int(window)
    chunks = fetch_window_by_source_and_index(source, start_idx, end_idx) or []
    txts = []
    cmin, cmax = None, None
    out_chunks = []
    for c in chunks:
        cp = c.get("payload") or {}
        t = str(cp.get("text") or "")
        ci = cp.get("chunkIndex")
        try:
            ci = int(ci)
        except Exception:
            ci = None
        if ci is not None:
            cmin = ci if cmin is None else min(cmin, ci)
            cmax = ci if cmax is None else max(cmax, ci)
        out_chunks.append({"chunkIndex": ci, "text": t})
        if t:
            txts.append(t)
    return {
        "sourceFile": source,
        "chunkStart": cmin if cmin is not None else start_idx,
        "chunkEnd": cmax if cmax is not None else end_idx,
        "chunks": out_chunks,
        "text": "\n".join(txts),
    }


def _multihop_rag(query: str, top_k: int = 5, window: int = 2) -> Dict[str, Any]:
    """
    Hop1: query → top1
    Hop2: query'= top1.payload.text → hits2
    Kontextfenster: ±window Chunks um top1(Hop2) im selben sourceFile
    """
    collection = getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    # Hop 1
    qvec1 = build_embeddings([query], model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))[0]
    hits1 = vs_search(qvec1, top_k=top_k, collection_name=collection)
    top1 = hits1[0] if hits1 else None
    if not top1:
        return {
            "query": query, "hop1": {"hits": []}, "hop2": {"hits": []}, "context": None
        }

    # Hop 2: exakter Text des Top1
    hop2_query = str((top1.get("payload") or {}).get("text") or "")
    qvec2 = build_embeddings([hop2_query], model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))[0]
    hits2 = vs_search(qvec2, top_k=max(8, top_k), collection_name=collection)

    # Kontextfenster bilden um den besten Hop2-Treffer (gleiches Dokument)
    top2 = hits2[0] if hits2 else None
    context = _build_context_from_hit(top2, window=window) if top2 else None

    return {
        "query": query,
        "hop1": {"hits": hits1, "top1": top1},
        "hop2": {"query": hop2_query, "hits": hits2, "top1": top2},
        "context": context
    }


def _extract_requirements_from_text(txt: str) -> List[Dict[str, Any]]:
    """
    Sehr einfache Extraktion aus Markdown-Tabellen-Zeilen:
      | R1 | requirementText | context |
    """
    out: List[Dict[str, Any]] = []
    if not txt:
        return out
    import re, json as _json
    row_re = re.compile(r'^\\|\\s*(R\\d+)\\s*\\|\\s*(.+?)\\s*\\|\\s*(.*?)\\s*\\|\\s*$', re.IGNORECASE)
    for line in txt.splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        rid, req, ctx = m.group(1), m.group(2), m.group(3)
        # Context-Spalte optional als JSON; sonst als plain text
        try:
            ctx_obj = _json.loads(ctx) if ctx else {}
            if not isinstance(ctx_obj, dict):
                ctx_obj = {"note": ctx}
        except Exception:
            ctx_obj = {"note": ctx}
        out.append({"id": rid, "requirementText": req, "context": ctx_obj})
    return out


@api_bp.post("/api/v1/agent/answer")
def agent_answer():
    """
    Agent-/Memory-unterstützter Wrapper um die RAG-Suche.
    Body: { query: string, sessionId?: string }
    Response: { query, effectiveQuery, topK, referenceCount, hits, agentNotes, triggeredPolicies }
    """
    try:
        body = request.get_json(silent=True) or {}
        query = str(body.get("query") or "").strip()
        session_id = str(body.get("sessionId") or "") or None
        if not query:
            return jsonify({"error": "invalid_request", "message": "query fehlt"}), 400

        # 1) Policies anwenden
        eff_query, top_k, prefer_sources, notes, triggered = _apply_policies(query)

        # 2) Spezialfall: Count-Policy greift?
        if any("use_ref_count" in n for n in notes):
            count = _ref_requirements_count()
            # Event loggen
            _mem_store.append_event({
                "type": "result",
                "sessionId": session_id,
                "query": query,
                "effectiveQuery": eff_query,
                "strategy": "ref_count",
                "top_k": 0,
                "quality": "ok" if count > 0 else "weak",
                "agentNotes": notes,
            })
            return jsonify({
                "query": query,
                "effectiveQuery": eff_query,
                "topK": 0,
                "referenceCount": count,
                "hits": [],
                "agentNotes": notes,
                "triggeredPolicies": triggered
            }), 200

        # 3) RAG mit evtl. Rewrite/Parametern
        collection = getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        qvec = build_embeddings([eff_query], model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))[0]
        hits = vs_search(qvec, top_k=top_k, collection_name=collection)
        hits = _re_rank_hits(hits, prefer_sources)

        # 4) Referenzgröße ermitteln (optional)
        ref_count = _ref_requirements_count()

        # 5) Event loggen (Top1-Proxy für Qualität)
        top1 = hits[0] if hits else None
        _mem_store.append_event({
            "type": "result",
            "sessionId": session_id,
            "query": query,
            "effectiveQuery": eff_query,
            "top_k": top_k,
            "top1": {
                "score": top1.get("score") if isinstance(top1, dict) else None,
                "source": (top1.get("payload") or {}).get("sourceFile") if isinstance(top1, dict) else None
            } if top1 else None,
            "agentNotes": notes,
        })

        return jsonify({
            "query": query,
            "effectiveQuery": eff_query,
            "topK": top_k,
            "collection": collection,
            "referenceCount": ref_count,
            "hits": hits,
            "agentNotes": notes,
            "triggeredPolicies": triggered
        }), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/validate/batch/structured")
def validate_batch_structured():
    """
    Wie /api/v1/validate/batch, aber serialisiert als StructuredRequirement-Liste:
      Request: Array[String] oder {items: [...], includeSuggestions: 0|1}
      Response: { items: [StructuredRequirement...] }
    """
    try:
        payload = request.get_json(silent=True)
        include_flag = False
        if isinstance(payload, dict):
            include_flag = str(payload.get("includeSuggestions", "")).lower() in ("1", "true", "yes")
            items = payload.get("items")
        else:
            items = payload

        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400

        # Rows bauen
        rows = [{"id": f"REQ_{i}", "requirementText": txt, "context": "{}"} for i, txt in enumerate(items, start=1)]

        out_items: List[Dict[str, Any]] = []
        for row in rows:
            rid = row["id"]
            requirement_text = row["requirementText"]
            context_obj: Dict[str, Any] = {}

            # Evaluation sicherstellen und Details laden
            try:
                criteria_keys = [c["key"] for c in load_criteria(get_db())] or ["clarity", "testability", "measurability"]
            except Exception:
                criteria_keys = ["clarity", "testability", "measurability"]

            eval_id, summ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys)

            eval_details: List[Dict[str, Any]] = []
            try:
                conn = get_db()
                detail_rows = conn.execute(
                    "SELECT criterion_key, score, passed, feedback FROM evaluation_detail WHERE evaluation_id = ?",
                    (eval_id,),
                ).fetchall()
                for d in detail_rows:
                    eval_details.append({
                        "criterion": d["criterion_key"],
                        "isValid": bool(d["passed"]),
                        "reason": "" if d["passed"] else d["feedback"],
                    })
            except Exception:
                pass

            # Rewrite
            try:
                rewritten = llm_rewrite(requirement_text, context_obj)
            except Exception:
                rewritten = requirement_text

            # Suggestions optional
            suggestions = []
            if include_flag:
                try:
                    atoms = llm_suggest(requirement_text, context_obj) or []
                    suggestions = atoms
                except Exception:
                    suggestions = []

            # Map auf StructuredRequirement
            sr_input = {
                "id": rid,
                "originalText": requirement_text,
                "redefinedRequirement": rewritten,
                "evaluation": eval_details,
                "score": summ.get("score"),
                "verdict": summ.get("verdict"),
                "suggestions": suggestions,
            }
            sr = StructuredRequirement.from_validate_item(sr_input)
            out_items.append(sr.to_dict())

        return jsonify({"items": out_items}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
@api_bp.post("/api/v1/agent/mine_requirements")
def agent_mine_requirements():
    """
    Extrahiert Requirements (Mining) via Multi-Hop-RAG und optionalen Policies.
    Body: { "query": string, "sessionId"?: string, "topK"?: int, "window"?: int }
    Response:
      {
        "query": str,
        "effectiveQuery": str,
        "topK": int,
        "window": int,
        "items": [ { "id": "R1", "requirementText": "...", "context": {...} }, ... ],
        "agentNotes": [ ... ],
        "triggeredPolicies": [ ... ]
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        query = str(body.get("query") or "").strip()
        session_id = str(body.get("sessionId") or "") or None
        if not query:
            return jsonify({"error": "invalid_request", "message": "query fehlt"}), 400

        # Defaults aus Policies ableiten; Fallbacks top_k=5, window=2
        eff_query, pol_top_k, _prefer_sources, notes, triggered = _apply_policies(query)
        req_top_k = int(body.get("topK") or body.get("top_k") or pol_top_k or 5)
        req_window = int(body.get("window") or 2)

        # Optional: an Agent-Worker delegieren (AutoGen), wenn verfügbar
        worker_url = os.environ.get("AGENT_WORKER_URL", "http://agent:8090").rstrip("/")
        try:
            if worker_url and not str(body.get("localOnly", "")).lower() in ("1", "true", "yes"):
                w_resp = requests.post(
                    f"{worker_url}/mine",
                    json={"query": query, "topK": req_top_k, "window": req_window},
                    timeout=25,
                )
                if w_resp.status_code == 200:
                    w_data = w_resp.json()
                    return jsonify(w_data), 200
                else:
                    json_log(logging.getLogger("app"), logging.INFO, "agent.mine.worker.error",
                             status=w_resp.status_code)
        except Exception as _we:
            json_log(logging.getLogger("app"), logging.DEBUG, "agent.mine.worker.unavailable", error=str(_we))

        lg = logging.getLogger("app")
        corr = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or "n/a"
        op_id = f"{corr}:agent.mine"

        json_log(
            lg, logging.INFO, "agent.mine.start",
            correlation_id=corr, operation_id=op_id,
            query=query, effective_query=eff_query, top_k=req_top_k, window=req_window
        )

        # Multi-Hop RAG
        rag = _multihop_rag(eff_query, top_k=req_top_k, window=req_window) or {}
        context = rag.get("context") or {}
        ctx_text = str(context.get("text") or "")
        items: List[Dict[str, Any]] = []

        # 1) Primär: Requirements aus Kontext (Markdown-Tabelle) extrahieren
        try:
            if ctx_text.strip():
                mined = _extract_requirements_from_text(ctx_text) or []
                items.extend(mined)
                json_log(
                    lg, logging.INFO, "agent.mine.context",
                    correlation_id=corr, operation_id=op_id,
                    mined=len(mined),
                    source=context.get("sourceFile")
                )
        except Exception as ce:
            json_log(
                lg, logging.DEBUG, "agent.mine.extract.error",
                correlation_id=corr, operation_id=op_id, error=str(ce)
            )

        # 2) Fallback: Hop2-Top1-Text versuchen
        try:
            if not items:
                hop2_top1 = (rag.get("hop2") or {}).get("top1") or {}
                hop2_p = hop2_top1.get("payload") or {}
                hop2_txt = str(hop2_p.get("text") or "")
                if hop2_txt.strip():
                    mined2 = _extract_requirements_from_text(hop2_txt) or []
                    items.extend(mined2)
                    json_log(
                        lg, logging.INFO, "agent.mine.hop2",
                        correlation_id=corr, operation_id=op_id,
                        mined=len(mined2),
                        source=hop2_p.get("sourceFile")
                    )
        except Exception as he2:
            json_log(
                lg, logging.DEBUG, "agent.mine.hop2.error",
                correlation_id=corr, operation_id=op_id, error=str(he2)
            )

        # 3) Fallback: Hop1-Top1-Text versuchen
        try:
            if not items:
                hop1_top1 = (rag.get("hop1") or {}).get("top1") or {}
                hop1_p = hop1_top1.get("payload") or {}
                hop1_txt = str(hop1_p.get("text") or "")
                if hop1_txt.strip():
                    mined3 = _extract_requirements_from_text(hop1_txt) or []
                    items.extend(mined3)
                    json_log(
                        lg, logging.INFO, "agent.mine.hop1",
                        correlation_id=corr, operation_id=op_id,
                        mined=len(mined3),
                        source=hop1_p.get("sourceFile")
                    )
        except Exception as he1:
            json_log(
                lg, logging.DEBUG, "agent.mine.hop1.error",
                correlation_id=corr, operation_id=op_id, error=str(he1)
            )

        # 4) Letzter Fallback: simple Items aus Hop2-Hits generieren (Snippet → requirementText)
        try:
            if not items:
                hop2_hits = (rag.get("hop2") or {}).get("hits") or []
                fallback_items = []
                for i, h in enumerate(hop2_hits[:max(1, req_top_k)], start=1):
                    p = h.get("payload") or {}
                    txt = str(p.get("text") or "").strip()
                    if not txt:
                        continue
                    fallback_items.append({
                        "id": f"R{i}",
                        "requirementText": txt[:4000],
                        "context": {"source": p.get("sourceFile"), "chunkIndex": p.get("chunkIndex")},
                    })
                if fallback_items:
                    items.extend(fallback_items)
                    json_log(
                        lg, logging.INFO, "agent.mine.fallback",
                        correlation_id=corr, operation_id=op_id,
                        fallback=len(fallback_items)
                    )
        except Exception as fe:
            json_log(
                lg, logging.DEBUG, "agent.mine.fallback.error",
                correlation_id=corr, operation_id=op_id, error=str(fe)
            )

        # Dedup nach requirementText
        norm_seen = set()
        deduped: List[Dict[str, Any]] = []
        for it in items:
            rt = str(it.get("requirementText") or "").strip()
            if not rt:
                continue
            key = rt.lower()
            if key in norm_seen:
                continue
            norm_seen.add(key)
            # ensure id/context
            rid = str(it.get("id") or f"R{len(deduped) + 1}")
            ctx = it.get("context") if isinstance(it.get("context"), dict) else {}
            deduped.append({"id": rid, "requirementText": rt, "context": ctx})

        # Event loggen
        _mem_store.append_event({
            "type": "mine",
            "sessionId": session_id,
            "query": query,
            "effectiveQuery": eff_query,
            "strategy": "multihop",
            "top_k": req_top_k,
            "window": req_window,
            "mined": len(deduped),
            "agentNotes": notes,
        })

        json_log(
            lg, logging.INFO, "agent.mine.end",
            correlation_id=corr, operation_id=op_id,
            mined=len(deduped)
        )

        return jsonify({
            "query": query,
            "effectiveQuery": eff_query,
            "topK": req_top_k,
            "window": req_window,
            "items": deduped,
            "agentNotes": notes,
            "triggeredPolicies": triggered
        }), 200

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
# =========================
# LangExtract Config + Extract + Mining endpoints
# =========================

def _lx_configs_dir() -> str:
    try:
        base = "/data"
        d = os.path.join(base, "lx_configs")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "./data/lx_configs"

def _lx_results_dir() -> str:
    try:
        base = "/data"
        d = os.path.join(base, "lx_results")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "./data/lx_results"

def _lx_default_config() -> dict:
    # Default-Prompt und -Beispiele an dev/run_extract.py angelehnt
    return {
        "prompt_description": (
            "Extrahiere Anforderungen, Constraints, Akteure, Fähigkeiten, Akzeptanzkriterien "
            "und Relationen in strukturierter Form. Nutze ausschließlich exakte Textspannen "
            "aus der Quelle (keine Paraphrasen). Überschneide Extraktionen nicht. "
            "Klassen: requirement, constraint, actor, capability, acceptance_criterion, relation. "
            "Gib sinnvolle Attribute (z. B. priority/category/type/rationale) an."
        ),
        "examples": [
            {
                "text": "Der Operator MUSS das Shuttle manuell stoppen koennen.",
                "extractions": [
                    {"extraction_class": "requirement", "extraction_text": "Operator MUSS das Shuttle manuell stoppen", "attributes": {"priority": "must"}},
                    {"extraction_class": "actor", "extraction_text": "Operator", "attributes": {}},
                    {"extraction_class": "capability", "extraction_text": "manuell stoppen", "attributes": {}},
                ],
            }
        ],
    }

def _lx_config_path(config_id: str) -> str:
    return os.path.join(_lx_configs_dir(), f"{config_id}.json")

def _lx_result_path(save_id: str) -> str:
    return os.path.join(_lx_results_dir(), f"{save_id}.json")

def _lx_list_configs() -> list[str]:
    try:
        d = _lx_configs_dir()
        out = []
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                out.append(os.path.splitext(fn)[0])
        return sorted(out)
    except Exception:
        return []

def _lx_load_config(config_id: str | None) -> dict:
    import json as _json
    try:
        if not config_id:
            # Fallback: default, ggf. Datei "default.json" verwenden
            p = _lx_config_path("default")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return _json.load(f)
            return _lx_default_config()
        p = _lx_config_path(config_id)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return _json.load(f)
        # Wenn angeforderte ID nicht existiert → default
        return _lx_default_config()
    except Exception:
        return _lx_default_config()

def _lx_save_config(config_id: str, data: dict) -> dict:
    import json as _json
    cid = config_id or f"cfg_{int(time.time())}"
    p = _lx_config_path(cid)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(data or {}, f, ensure_ascii=False, indent=2)
    return {"configId": cid, "path": p}

def _lx_examples_to_sdk(examples: list) -> list:
    # Konvertiert examples[] in LangExtract ExampleData/Extraction
    try:
        import langextract as lx  # type: ignore
        out = []
        if isinstance(examples, list):
            for ex in examples:
                if not isinstance(ex, dict):
                    continue
                txt = str(ex.get("text") or "")
                exts = []
                for it in (ex.get("extractions") or []):
                    if not isinstance(it, dict):
                        continue
                    exts.append(
                        lx.data.Extraction(
                            extraction_class=str(it.get("extraction_class") or it.get("cls") or it.get("class") or ""),
                            extraction_text=str(it.get("extraction_text") or it.get("text") or ""),
                            attributes=(it.get("attributes") if isinstance(it.get("attributes"), dict) else {}),
                        )
                    )
                out.append(lx.data.ExampleData(text=txt, extractions=exts))
        return out
    except Exception:
        return []

def _lx_preview_from_payloads(payloads: list[dict]) -> list[dict]:
    # Erzeugt flache Vorschau (wie im Ingest) aus payloads[*].payload.lx.extractions
    preview = []
    for p in payloads or []:
        try:
            pl = p.get("payload") or {}
            lx = pl.get("lx") or {}
            exts = lx.get("extractions") or []
            for e in exts:
                try:
                    if isinstance(e, dict):
                        ec = e.get("extraction_class")
                        et = e.get("extraction_text")
                        ci = e.get("char_interval")
                        al = e.get("alignment_status")
                        attrs = e.get("attributes") if isinstance(e.get("attributes"), dict) else {}
                    else:
                        ec = getattr(e, "extraction_class", None)
                        et = getattr(e, "extraction_text", None)
                        ci = getattr(e, "char_interval", None)
                        al = getattr(e, "alignment_status", None)
                        attrs = getattr(e, "attributes", {}) or {}
                        if not isinstance(attrs, dict):
                            attrs = {}
                    preview.append({
                        "extraction_class": ec,
                        "extraction_text": et,
                        "char_interval": ci,
                        "alignment_status": al,
                        "attributes": attrs,
                        "sourceFile": pl.get("sourceFile"),
                        "chunkIndex": pl.get("chunkIndex"),
                    })
                except Exception:
                    continue
        except Exception:
            continue
    return preview

@api_bp.get("/api/v1/lx/config/list")
def lx_config_list():
    try:
        return jsonify({"items": _lx_list_configs()}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.get("/api/v1/lx/config/get")
def lx_config_get():
    try:
        cid = request.args.get("id") or "default"
        cfg = _lx_load_config(cid)
        return jsonify({"configId": cid, "config": cfg}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/lx/config/save")
def lx_config_save():
    try:
        data = request.get_json(silent=True) or {}
        cid = str(data.get("configId") or "").strip() or f"cfg_{int(time.time())}"
        prompt = data.get("prompt_description") or data.get("prompt") or _lx_default_config()["prompt_description"]
        examples = data.get("examples") or _lx_default_config()["examples"]
        saved = _lx_save_config(cid, {"prompt_description": prompt, "examples": examples})
        return jsonify({"saved": saved}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/lx/extract")
def lx_extract_endpoint():
    """
    Führt LangExtract mit konfigurierbarem Prompt/Examples aus und persistiert das Ergebnis.
    Akzeptiert:
      - multipart/form-data mit 'files' (oder 'file'), optional: chunkMin, chunkMax, chunkOverlap, configId
      - application/json mit { text?: str, configId?: str, prompt_description?, examples? }
    Persistiert nach /data/lx_results/{save_id}.json.
    Response: { lxPreview: [...], savedAs: str, configId: str, chunks: int }
    """
    try:
        import json as _json
        import hashlib
        try:
            import langextract as lx  # type: ignore
        except Exception as _imp:
            return jsonify({"error": "lx_unavailable", "message": str(_imp)}), 500

        # Konfiguration bestimmen
        content_type = (request.content_type or "").lower()
        cfg_id = None
        prompt_desc = None
        examples_in = None

        # Eingabe sammeln
        texts: list[str] = []
        sources: list[dict] = []

        # Multipart (Dateien)
        if "multipart/form-data" in content_type:
            # Config-Parameter
            cfg_id = request.form.get("configId")
            prompt_desc = request.form.get("prompt_description") or request.form.get("prompt")
            try:
                ex_str = request.form.get("examples")
                if ex_str:
                    examples_in = _json.loads(ex_str)
            except Exception:
                examples_in = None

            # Chunking
            def _to_int(name: str, default: int) -> int:
                v = request.form.get(name)
                try:
                    return int(v)
                except Exception:
                    return default
            cmin = _to_int("chunkMin", getattr(settings, "CHUNK_TOKENS_MIN", 5000))
            cmax = _to_int("chunkMax", getattr(settings, "CHUNK_TOKENS_MAX", 10000))
            cover = _to_int("chunkOverlap", getattr(settings, "CHUNK_OVERLAP_TOKENS", 200))

            # Dateien lesen
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f:
                    files = [f]
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400

            raw_records = []
            for f in files:
                filename = f.filename or "unknown"
                data = f.read() or b""
                ctype = f.mimetype or ""
                parts = extract_texts(filename, data, ctype)
                raw_records.extend(parts)
            payloads = chunk_payloads(raw_records, cmin, cmax, cover)
            texts = [p["text"] for p in payloads]
            sources = [{"sourceFile": (p["payload"] or {}).get("sourceFile"), "chunkIndex": (p["payload"] or {}).get("chunkIndex")} for p in payloads]
        else:
            # JSON
            data = request.get_json(silent=True) or {}
            cfg_id = data.get("configId")
            prompt_desc = data.get("prompt_description") or data.get("prompt")
            examples_in = data.get("examples")
            txt = data.get("text")
            if isinstance(txt, str) and txt.strip():
                texts = [txt]
                sources = [{"sourceFile": "json:text", "chunkIndex": 0}]
            else:
                return jsonify({"error": "invalid_request", "message": "text fehlt oder multipart files fehlen"}), 400

            # Für JSON-Text ohne Chunking in ein Payload-Format bringen
            payloads = [{"text": t, "payload": {"sourceFile": "json:text", "chunkIndex": i}} for i, t in enumerate(texts)]

        # Config beschaffen
        cfg = _lx_load_config(cfg_id)
        if prompt_desc:
            cfg["prompt_description"] = prompt_desc
        if isinstance(examples_in, list):
            cfg["examples"] = examples_in
        prompt = cfg.get("prompt_description") or _lx_default_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk(cfg.get("examples") or _lx_default_config()["examples"])

        # Ausführen je Chunk
        total_extractions = 0
        coverage_sum = 0.0
        for p in payloads:
            txt = p.get("text") or ""
            try:
                res = lx.extract(
                    text_or_documents=txt,
                    prompt_description=prompt,
                    examples=examples_sdk,
                    model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=getattr(settings, "OPENAI_API_KEY", None),
                )
                # Normalisieren (reuse lokaler Logik aus Ingest)
                def _normalize_lx_result(res, chunk_text: str):
                    # stark vereinfachte Variante (nur dictionary)
                    data = res.to_dict() if hasattr(res, "to_dict") else (res if isinstance(res, dict) else getattr(res, "__dict__", {}) or {})
                    exts_raw = []
                    if isinstance(data, dict):
                        if isinstance(data.get("extractions"), list):
                            exts_raw.extend(data.get("extractions") or [])
                        docs = data.get("documents") or data.get("items") or []
                        if isinstance(docs, list):
                            for d in docs:
                                if isinstance(d, dict) and isinstance(d.get("extractions"), list):
                                    exts_raw.extend(d.get("extractions") or [])
                    out = []
                    intervals = []
                    n = len(chunk_text or "")
                    def _coerce_int(v, default=0):
                        try:
                            return int(v)
                        except Exception:
                            return default
                    for e in exts_raw or []:
                        try:
                            ec = e.get("extraction_class") or e.get("cls") or e.get("class") or e.get("label")
                            et = e.get("extraction_text") or e.get("text") or e.get("span_text")
                            ci = e.get("char_interval") or e.get("char_span") or e.get("span") or e.get("interval")
                            s, epos = None, None
                            if isinstance(ci, dict):
                                s = _coerce_int(ci.get("start_pos", ci.get("start")))
                                epos = _coerce_int(ci.get("end_pos", ci.get("end")))
                            if (s is None or epos is None or epos <= s) and isinstance(et, str) and et.strip():
                                idx = (chunk_text or "").find(et)
                                if idx >= 0:
                                    s, epos = idx, idx + len(et)
                            s = 0 if s is None else max(0, min(s, n))
                            epos = 0 if epos is None else max(0, min(epos, n))
                            if epos < s:
                                s, epos = epos, s
                            al = e.get("alignment_status")
                            attrs = e.get("attributes") if isinstance(e.get("attributes"), dict) else {}
                            if isinstance(ec, str) and isinstance(et, str) and et.strip() and epos > s:
                                out.append({
                                    "extraction_class": ec,
                                    "extraction_text": et,
                                    "char_interval": {"start_pos": s, "end_pos": epos},
                                    "alignment_status": al or "match_exact",
                                    "attributes": attrs,
                                })
                                intervals.append((s, epos))
                        except Exception:
                            continue
                    # coverage
                    try:
                        merged = []
                        for st, en in sorted(intervals):
                            if not merged:
                                merged.append((st, en))
                            else:
                                pst, pen = merged[-1]
                                if st <= pen:
                                    merged[-1] = (pst, max(pen, en))
                                else:
                                    merged.append((st, en))
                        covered = sum(en - st for st, en in merged)
                        ratio = float(covered) / float(n) if n > 0 else 0.0
                    except Exception:
                        covered, ratio = 0, 0.0
                    return out, covered, ratio

                exts, covered, ratio = _normalize_lx_result(res, txt)
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({
                    "version": "le.v1",
                    "provider": "openai",
                    "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    "run_id": str(int(time.time())),
                    "extractions": exts,
                    "coverage": {"chunk_len": len(txt), "covered": covered, "coverage_ratio": round(ratio, 4)},
                    "evidence": {"sourceFile": p["payload"].get("sourceFile"), "chunkIndex": p["payload"].get("chunkIndex")},
                })
                total_extractions += len(exts)
                coverage_sum += ratio
            except Exception as _le:
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({"version": "le.v1", "error": str(_le)})

        # Vorschau
        lx_preview = _lx_preview_from_payloads(payloads)

        # Persistieren
        # Save-ID aus SHA über Textinhalte bilden
        sha = hashlib.sha1(("||".join(texts)).encode("utf-8")).hexdigest() if texts else str(int(time.time()))
        save_id = f"lx_{sha[:10]}_{int(time.time())}"
        out = {
            "savedAt": int(time.time()),
            "configId": cfg_id or "default",
            "prompt_description": prompt,
            "examples": cfg.get("examples"),
            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            "sources": sources,
            "total_extractions": total_extractions,
            "coverage_avg": (coverage_sum / (len(payloads) or 1)) if payloads else 0.0,
            "payloads": payloads,
            "lxPreview": lx_preview,
        }
        pth = _lx_result_path(save_id)
        try:
            os.makedirs(os.path.dirname(pth), exist_ok=True)
            with open(pth, "w", encoding="utf-8") as f:
                _json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception as _se:
            # nicht kritisch
            pth = None

        return jsonify({"lxPreview": lx_preview, "savedAs": pth, "saveId": save_id, "configId": cfg_id or "default", "chunks": len(payloads)}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.get("/api/v1/lx/mine")
def lx_mine_from_results():
    """
    Baut Requirements-Items aus persistierten LangExtract-Ergebnissen.
    Optional: ?saveId=... (konkret) oder ?latest=1 (neueste Datei).
    Response: { items: [ {id, requirementText, context}, ... ] }
    """
    try:
        import json as _json
        d = _lx_results_dir()
        save_id = request.args.get("saveId")
        latest = str(request.args.get("latest", "")).lower() in ("1", "true", "yes")
        target = None
        if save_id:
            p = _lx_result_path(save_id)
            if os.path.exists(p):
                target = p
        if not target:
            # latest wählen
            files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith(".json")]
            if not files:
                return jsonify({"items": []}), 200
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            target = files[0]

        with open(target, "r", encoding="utf-8") as f:
            data = _json.load(f)

        preview = data.get("lxPreview") or []
        # Map: alle requirement-Extraktionen → UI-Items
        items = []
        for i, e in enumerate(preview, start=1):
            try:
                if str(e.get("extraction_class") or "").lower() != "requirement":
                    continue
                rt = str(e.get("extraction_text") or "").strip()
                if not rt:
                    continue
                items.append({
                    "id": f"R{i}",
                    "requirementText": rt,
                    "context": {"source": e.get("sourceFile"), "chunkIndex": e.get("chunkIndex")},
                })
            except Exception:
                continue
        return jsonify({"items": items}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500