# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.db import (
    get_db,
    load_criteria,
    get_latest_rewrite_row_for_eval,
    get_latest_evaluation_by_checksum,
)
from backend.core.llm import llm_apply_with_suggestions
from backend.core.utils import sha256_text
from backend.core.batch import ensure_evaluation_exists

router = APIRouter(tags=["corrections"])


@router.post("/api/v1/corrections/decision")
async def set_correction_decision_v2(request: Request) -> JSONResponse:
    """
    Setzt die Entscheidung accepted|rejected für die jüngste Korrektur einer Evaluation.
    Body: { "evaluationId": "...", "decision": "accepted"|"rejected", "decidedBy"?: "..." }
    """
    try:
        data = await request.json()
        evaluation_id = data.get("evaluationId")
        decision = str(data.get("decision", "")).lower()
        decided_by = data.get("decidedBy")

        if not isinstance(evaluation_id, str) or not evaluation_id.strip():
            return JSONResponse(content={"error": "invalid_request", "message": "evaluationId fehlt oder ist leer"}, status_code=400)
        if decision not in ("accepted", "rejected"):
            return JSONResponse(content={"error": "invalid_request", "message": "decision muss accepted oder rejected sein"}, status_code=400)

        conn = get_db()
        rw = get_latest_rewrite_row_for_eval(conn, evaluation_id)
        if not rw:
            return JSONResponse(content={"error": "not_found", "message": "keine Correction vorhanden"}, status_code=404)

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
        return JSONResponse(content={"evaluationId": evaluation_id, "decision": decision}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/corrections/text")
async def save_correction_text_v2(request: Request) -> JSONResponse:
    """
    Speichert eine manuell eingegebene Korrektur (Correction) zu einer bestehenden Evaluation.
    Body: { "originalText": string, "text": string }
    """
    try:
        data = await request.json()
        original_text = data.get("originalText")
        text = data.get("text")

        if not isinstance(original_text, str) or not original_text.strip():
            return JSONResponse(content={"error": "invalid_request", "message": "originalText fehlt oder ist leer"}, status_code=400)
        if not isinstance(text, str) or not text.strip():
            return JSONResponse(content={"error": "invalid_request", "message": "text fehlt oder ist leer"}, status_code=400)

        conn = get_db()
        checksum = sha256_text(original_text)
        row = get_latest_evaluation_by_checksum(conn, checksum)
        if not row:
            return JSONResponse(content={"error": "not_found", "message": "keine Evaluation für diesen originalText gefunden"}, status_code=404)

        eval_id = row["id"]
        with conn:
            conn.execute(
                "INSERT INTO rewritten_requirement(evaluation_id, text) VALUES (?, ?)",
                (eval_id, text),
            )

        return JSONResponse(content={"evaluationId": eval_id, "status": "saved"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


from backend.core.llm import llm_rewrite
@router.post("/api/v1/corrections/apply")
async def apply_corrections_v2(request: Request) -> JSONResponse:
    """
    Wendet ausgewählte Suggestions (Atoms) auf eine Anforderung an und erzeugt 1..N neue Umschreibungen.
    Body:
      {
        originalText?: string,
        evaluationId?: string,
        selectedSuggestions?: Atom[],
        mode?: "merge"|"split",
        context?: {}
      }
    """
    try:
        data = await request.json()
        original_text = data.get("originalText")
        evaluation_id = data.get("evaluationId")
        selected = data.get("selectedSuggestions") or data.get("selectedAtoms") or []
        mode = str(data.get("mode", "merge")).lower()
        context = data.get("context") or {}

        if not isinstance(selected, list):
            selected = []

        if not evaluation_id and not (isinstance(original_text, str) and original_text.strip()):
            return JSONResponse(content={"error": "invalid_request", "message": "originalText oder evaluationId erforderlich"}, status_code=400)

        conn = get_db()
        crits = load_criteria(conn)
        criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

        if not evaluation_id:
            evaluation_id, _ = ensure_evaluation_exists(original_text, context, criteria_keys)

        if not (isinstance(original_text, str) and original_text.strip()):
            return JSONResponse(content={"error": "invalid_request", "message": "originalText fehlt"}, status_code=400)

        if selected:
            items = llm_apply_with_suggestions(original_text, context, selected, mode)
        else:
            try:
                rewritten = str(llm_rewrite(original_text, context) or "").strip()
            except Exception:
                rewritten = ""
            items = [{"redefinedRequirement": rewritten}] if rewritten else []

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

        return JSONResponse(content={"evaluationId": evaluation_id, "items": results}, status_code=200)

    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/corrections/decision/batch")
async def set_correction_decision_batch_v2(request: Request) -> JSONResponse:
    """
    Setzt Entscheidungen im Batch.
    Body: { "items": [ { "evaluationId": "...", "decision": "accepted"|"rejected", "decidedBy"?: "..." }, ... ] }
    """
    try:
        data = await request.json()
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return JSONResponse(content={"error": "invalid_request", "message": "items ist erforderlich und muss eine Liste sein"}, status_code=400)

        conn = get_db()
        updated = 0
        errors: List[Dict[str, Any]] = []

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

        return JSONResponse(content={"updated": updated, "errors": errors}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)