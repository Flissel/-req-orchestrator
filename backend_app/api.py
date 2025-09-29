# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import logging
import concurrent.futures as futures
from typing import Any, Dict, List, Tuple
import requests  # HTTP delegation to agent worker
import json  # NDJSON streaming

from flask import Blueprint, jsonify, request, g, make_response, Response
from .logging_ext import _json_log as json_log
from flask import stream_with_context  # Streaming-Helfer aus Flask

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

from backend_app_v2.services import EvaluationService, RequestContext, ServiceError  # type: ignore
from backend_app_v2.services.adapters import LLMAdapter  # type: ignore

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

# Deprecation/Sunset Header für alle v1-Endpunkte
@api_bp.after_request
def _attach_deprecation_headers(resp):
    try:
        path = str(getattr(request, "path", "") or "")
        # Nur für v1 JSON-Endpunkte; Preflight/OPTIONS ausnehmen
        if request.method != "OPTIONS" and path.startswith("/api/v1/"):
            # RFC 8594 (Sunset) / Deprecation-Hinweis
            resp.headers["Deprecation"] = "true"
            # Sunset-Datum (RFC 7231/RFC 1123 Format) – anpassbar in Zukunft
            resp.headers["Sunset"] = "Tue, 31 Mar 2026 00:00:00 GMT"
            # Link zu Migrationshinweisen (OpenAPI / Docs)
            # rel="deprecation": Hinweise zur Abschaltung
            # rel="alternate": neue v2-Route (Dokumentation)
            links = []
            links.append('</docs>; rel="deprecation"; type="text/html"')
            links.append('</openapi.json>; rel="describedby"; type="application/json"')
            resp.headers["Link"] = ", ".join(links)
    except Exception:
        # Header nicht kritisch – Fehler hier nicht propagieren
        pass
    return resp

# --- Added validate endpoint for array-based evaluation ---
@api_bp.get("/api/v1/demo/requirements")
def demo_requirements():
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

# -----------------------
# v1 Validate – dünne Wrapper auf Service-Layer (Parität)
# -----------------------
from backend_app_v2.services import EvaluationService, RequestContext, ServiceError  # type: ignore
from backend_app_v2.services.adapters import LLMAdapter  # type: ignore
from flask import stream_with_context  # Streaming-Helfer aus Flask

def _request_ctx() -> RequestContext:
    """Erzeuge RequestContext aus eingehenden Headern (z. B. X-Request-Id)."""
    try:
        rid = request.headers.get("X-Request-Id")
        return RequestContext(request_id=rid)
    except Exception:
        return RequestContext()

@api_bp.post("/api/v1/validate/batch")
def validate_batch_v1():
    """
    Parität gewahrt:
    - akzeptiert {items: string[]} ODER direkt string[]
    - optional includeSuggestions: bool → suggestions pro Item anhängen
    - liefert Array[{ id, originalText, correctedText:'', status, evaluation[], score, verdict, suggestions? }]
    """
    try:
        payload = request.get_json(silent=True)
        items = []
        include_suggestions = False
        if isinstance(payload, dict):
            items = payload.get("items")
            include_suggestions = bool(payload.get("includeSuggestions") or False)
        else:
            items = payload

        if not isinstance(items, list) or not all(isinstance(x, (str, type(None))) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings (items) oder JSON-Objekt mit Feld 'items'."}), 400

        # Service-Layer Aufruf
        ctx = _request_ctx()
        svc = EvaluationService()
        results = svc.evaluate_batch([str(t or "") for t in items], ctx=ctx)

        # Parität: Felder ergänzen (correctedText, status) und optional suggestions
        llm = LLMAdapter() if include_suggestions else None
        for r in results:
            r.setdefault("correctedText", "")
            r["status"] = "accepted" if str(r.get("verdict", "")).lower() == "pass" else "rejected"
            if include_suggestions and llm:
                try:
                    atoms = llm.suggest(str(r.get("originalText", "")), ctx=ctx)
                except ServiceError as se:
                    atoms = []
                r["suggestions"] = atoms

        return jsonify(results), 200
    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/validate/suggest")
def validate_suggest_v1():
    """
    Erzeugt Vorschlags-„Atoms“ für Eingabetexte.
    Akzeptiert {items: string[]} ODER direkt string[].
    Antwort: { items: { "<index>": { suggestions: Atom[] } } }
    """
    try:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            items = payload.get("items")
        else:
            items = payload

        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list) or not all(isinstance(x, (str, type(None))) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings (items) oder JSON-Objekt mit Feld 'items'."}), 400

        ctx = _request_ctx()
        llm = LLMAdapter()
        out_map: Dict[str, Any] = {}
        for i, t in enumerate(items, start=1):
            atoms = llm.suggest(str(t or ""), ctx=ctx)
            out_map[str(i)] = {"suggestions": atoms}

        return jsonify({"items": out_map}), 200
    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/validate/batch/stream")
def validate_batch_stream_v1():
    """
    NDJSON-Stream der Batch-Validate-Ergebnisse.
    Request:
      - { items: string[], includeSuggestions?: boolean } oder direkt string[]
    Response:
      - application/x-ndjson; pro Zeile ein JSON-Objekt:
        { id, originalText, correctedText:'', status, evaluation[], score, verdict, suggestions? }
    """
    try:
        payload = request.get_json(silent=True)
        include_suggestions = False
        if isinstance(payload, dict):
            items = payload.get("items")
            include_suggestions = bool(payload.get("includeSuggestions") or False)
        else:
            items = payload

        if not isinstance(items, list) or not all(isinstance(x, (str, type(None))) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings (items) oder JSON-Objekt mit Feld 'items'."}), 400

        ctx = _request_ctx()
        svc = EvaluationService()
        llm = LLMAdapter() if include_suggestions else None

        @stream_with_context
        def generate():
            for idx, t in enumerate(items, start=1):
                try:
                    single = svc.evaluate_single(str(t or ""), ctx=ctx)
                    rec: Dict[str, Any] = {
                        "id": f"item-{idx}",
                        "originalText": str(t or ""),
                        "correctedText": "",
                        "evaluation": list(single.get("evaluation", [])),
                        "score": float(single.get("score", 0.0)),
                        "verdict": str(single.get("verdict", "")),
                    }
                    rec["status"] = "accepted" if rec["verdict"].lower() == "pass" else "rejected"
                    if include_suggestions and llm:
                        try:
                            rec["suggestions"] = llm.suggest(rec["originalText"], ctx=ctx)
                        except ServiceError:
                            rec["suggestions"] = []
                except ServiceError as se:
                    rec = {"error": se.code, "message": se.message, "details": se.details, "id": f"item-{idx}"}
                except Exception as e:
                    rec = {"error": "internal_error", "message": str(e), "id": f"item-{idx}"}
                yield json.dumps(rec, ensure_ascii=False) + "\n"

        return Response(generate(), mimetype="application/x-ndjson")
    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/validate/suggest/stream")
def validate_suggest_stream_v1():
    """
    NDJSON-Stream der Vorschläge je Eingabetext.
    Request:
      - { items: string[] } oder direkt string[]
    Response:
      - application/x-ndjson; pro Zeile:
        { id, originalText, suggestions: Atom[] }
    """
    try:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            items = payload.get("items")
        else:
            items = payload

        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list) or not all(isinstance(x, (str, type(None))) for x in items):
            return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings (items) oder JSON-Objekt mit Feld 'items'."}), 400

        ctx = _request_ctx()
        llm = LLMAdapter()

        @stream_with_context
        def generate():
            for idx, t in enumerate(items, start=1):
                try:
                    atoms = llm.suggest(str(t or ""), ctx=ctx)
                    rec = {
                        "id": f"item-{idx}",
                        "originalText": str(t or ""),
                        "suggestions": list(atoms or []),
                    }
                except ServiceError as se:
                    rec = {"error": se.code, "message": se.message, "details": se.details, "id": f"item-{idx}"}
                except Exception as e:
                    rec = {"error": "internal_error", "message": str(e), "id": f"item-{idx}"}
                yield json.dumps(rec, ensure_ascii=False) + "\n"

        return Response(generate(), mimetype="application/x-ndjson")
    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500

@api_bp.post("/api/v1/evaluations")
def create_evaluation_v1():
    """
    Einzel-Evaluation (v1-Form) – Wrapper auf EvaluationService.evaluate_single

    Request:
      { "requirementText": string, "context"?: object, "criteriaKeys"?: string[] }

    Response (v1-kompatibel, minimal):
      {
        "evaluationId": "ev_<ts>_<pid>",
        "verdict": "pass|fail",
        "score": float,
        "latencyMs": int,
        "model": settings.OPENAI_MODEL,
        "details": [ {criterion, score, passed, feedback} ],
        "suggestions": []
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_request", "message": "Erwarte JSON-Objekt mit Feld 'requirementText'."}), 400

        req_text = body.get("requirementText")
        if not isinstance(req_text, str) or not req_text.strip():
            return jsonify({"error": "invalid_request", "message": "requirementText fehlt oder leer"}), 400

        criteria_keys = body.get("criteriaKeys") if isinstance(body.get("criteriaKeys"), list) else None
        ctx_obj = body.get("context") if isinstance(body.get("context"), dict) else None

        ctx = _request_ctx()
        t0 = time.time()
        svc = EvaluationService()
        res = svc.evaluate_single(
            str(req_text),
            context=ctx_obj,
            criteria_keys=criteria_keys,
            ctx=ctx,
        )
        latency_ms = int((time.time() - t0) * 1000)

        out = {
            "evaluationId": f"ev_{int(time.time())}_{os.getpid()}",
            "verdict": str(res.get("verdict", "")),
            "score": float(res.get("score", 0.0)),
            "latencyMs": latency_ms,
            "model": getattr(settings, "OPENAI_MODEL", ""),
            "details": list(res.get("evaluation", [])),
            "suggestions": [],
        }
        return jsonify(out), 200
    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500
