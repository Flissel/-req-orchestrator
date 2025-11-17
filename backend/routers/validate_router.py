from __future__ import annotations

from typing import Any, Dict, List
import logging
import json
import time
import concurrent.futures as futures

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.core.batch import (
    process_evaluations,
    process_rewrites,
    process_suggestions,
    ensure_evaluation_exists,
)
from backend.core.db import get_db, load_criteria
from backend.core.llm import llm_rewrite, llm_suggest
from backend.core import settings
from backend import schemas
from backend.schemas import ValidateItemResult, ValidateSuggestResponse, EvaluateSingleRequest, EvaluateSingleResponse, EvaluateBatchRequestV2, EvaluateBatchItem, ErrorResponse
from backend.services import EvaluationService, RequestContext, ServiceError

router = APIRouter(tags=["validate"])

# Robust: toleranter JSON-Reader (UTF-8-SIG/BOM, Whitespace, Raw-Fallback)
async def _read_json_tolerant(request: Request) -> Any:
    try:
        return await request.json()
    except Exception as e1:
        try:
            raw = await request.body()
            s = (raw.decode("utf-8-sig", errors="ignore")).strip()
            return json.loads(s) if s else None
        except Exception as e2:
            lg = logging.getLogger("app")
            try:
                lg.error(json.dumps({"event": "request.json.error", "primary": str(e1), "secondary": str(e2)}))
            except Exception:
                pass
            raise e2


@router.post("/api/v1/validate/suggest", response_model=ValidateSuggestResponse, responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def validate_suggest_v2(request: Request):
    """
    FastAPI-Port von validate_suggest:
    - Erwartet Array[string] oder { items: string[] }
    - Antwort: { items: { REQ_n: { suggestions: Atom[] } } }
    """
    try:
        payload = await _read_json_tolerant(request)
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            items = payload.get("items")
        else:
            items = payload
        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            return JSONResponse(
                content={"error": "invalid_request", "message": "Erwarte ein Array von Strings oder {items: string[])"},
                status_code=400,
            )

        rows: List[Dict[str, str]] = []
        for idx, txt in enumerate(items, start=1):
            rows.append({"id": f"REQ_{idx}", "requirementText": txt, "context": "{}"})

        sug_map = process_suggestions(rows)
        return {"items": sug_map}
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/validate/batch", response_model=List[ValidateItemResult], responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def validate_batch_v2(request: Request):
    """
    FastAPI-Port von validate_batch_optimized:
    - Erwartet Array[string] ODER { items: string[], includeSuggestions?: bool }
    - Antwort: Array von Ergebnissen mit Feldern:
      { id, originalText, correctedText, status, evaluation, score, verdict, suggestions? }
    """
    try:
        payload = await _read_json_tolerant(request)
        include_flag = False
        if isinstance(payload, dict):
            include_flag = str(payload.get("includeSuggestions", "")).lower() in ("1", "true", "yes")
            items = payload.get("items")
        else:
            items = payload

        if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
            return JSONResponse(
                content={"error": "invalid_request", "message": "Erwarte ein Array von Strings oder {items: string[])"},
                status_code=400,
            )

        # Rows für Batch-Helper bauen
        rows: List[Dict[str, str]] = []
        for idx, txt in enumerate(items, start=1):
            rows.append({"id": f"REQ_{idx}", "requirementText": txt, "context": "{}"})

        # Auswertung + Rewrite (nutzt intern ThreadPool/Chunking)
        eval_results = process_evaluations(rows)  # { REQ_n: { evaluationId, score, verdict, ... } }
        rewrite_results = process_rewrites(rows)  # { REQ_n: { redefinedRequirement } }

        # Optional Suggestions
        sug_map: Dict[str, Any] = {}
        if include_flag:
            try:
                sug_map = process_suggestions(rows)  # { REQ_n: { suggestions: Atom[] } }
            except Exception:
                sug_map = {}

        # Details aus DB laden und Ergebnisliste formen
        conn = get_db()
        results: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            req_id = row["id"]
            eval_data = eval_results.get(req_id, {}) or {}
            rw_data = rewrite_results.get(req_id, {}) or {}

            evaluation_details: List[Dict[str, Any]] = []
            ev_id = eval_data.get("evaluationId")
            if ev_id:
                try:
                    detail_rows = conn.execute(
                        "SELECT criterion_key, score, passed, feedback FROM evaluation_detail WHERE evaluation_id = ?",
                        (ev_id,),
                    ).fetchall()
                    for d in detail_rows:
                        evaluation_details.append(
                            {
                                "criterion": d["criterion_key"],
                                "isValid": bool(d["passed"]),
                                "reason": "" if d["passed"] else d["feedback"],
                            }
                        )
                except Exception:
                    pass

            status = "accepted" if (eval_data.get("verdict") == "pass") else "rejected"
            out: Dict[str, Any] = {
                "id": idx,
                "originalText": row["requirementText"],
                "correctedText": rw_data.get("redefinedRequirement", row["requirementText"]),
                "status": status,
                "evaluation": evaluation_details,
                "score": eval_data.get("score", 0.0),
                "verdict": eval_data.get("verdict", "fail"),
            }
            if include_flag:
                out["suggestions"] = (sug_map.get(req_id, {}) or {}).get("suggestions", [])
            results.append(out)

        return results
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/validate/suggest/stream")
async def validate_suggest_stream_v2(request: Request) -> StreamingResponse:
    """
    NDJSON-Stream: sendet pro Requirement Suggestions (Atoms) als einzelne JSON-Zeile.
    Erwartet Array[string] oder { items: string[], force?: bool }
    """
    lg = logging.getLogger("app")
    payload = await _read_json_tolerant(request)
    if isinstance(payload, dict):
        items = payload.get("items")
        # force ist derzeit ohne Funktion (Kompatibilitäts-Flag)
        _ = str(payload.get("force", "")).lower() in ("1", "true", "yes")
    else:
        items = payload

    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        async def bad():
            yield json.dumps({"event": "error", "message": "Erwarte ein Array von Strings"}, ensure_ascii=False) + "\n"
        return StreamingResponse(bad(), media_type="application/x-ndjson")

    rows = [{"id": f"REQ_{i}", "requirementText": txt, "context": "{}"} for i, txt in enumerate(items, start=1)]

    def gen():
        processed = 0

        def worker(row: Dict[str, str]) -> Dict[str, Any]:
            rid = row["id"]
            requirement_text = row["requirementText"]
            context_obj: Dict[str, Any] = {}
            t0 = time.time()
            try:
                try:
                    criteria_keys = [c["key"] for c in load_criteria(get_db())] or ["clarity", "testability", "measurability"]
                except Exception:
                    criteria_keys = ["clarity", "testability", "measurability"]
                eval_id, _ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys)
                atoms = llm_suggest(requirement_text, context_obj) or []
                # optional: Persist der Atoms (best effort)
                try:
                    with get_db() as c2:
                        for atom in atoms:
                            c2.execute(
                                "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                                (eval_id, json.dumps(atom, ensure_ascii=False), "atom"),
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
                yield json.dumps(result, ensure_ascii=False) + "\n"

        yield json.dumps({"event": "end", "processed": processed}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/api/v1/validate/batch/stream")
async def validate_batch_stream_v2(request: Request) -> StreamingResponse:
    """
    NDJSON-Stream: sendet pro Requirement ein Ergebnis (Evaluate+Rewrite, optional Suggestions) als einzelne JSON-Zeile.
    Erwartet Array[string] oder { items: string[], includeSuggestions?: bool }
    """
    lg = logging.getLogger("app")
    payload = await _read_json_tolerant(request)
    include_flag = False
    if isinstance(payload, dict):
        include_flag = str(payload.get("includeSuggestions", "")).lower() in ("1", "true", "yes")
        items = payload.get("items")
    else:
        items = payload

    if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
        async def bad():
            yield json.dumps({"event": "error", "message": "Erwarte ein Array von Strings"}, ensure_ascii=False) + "\n"
        return StreamingResponse(bad(), media_type="application/x-ndjson")

    rows = [{"id": f"REQ_{i}", "requirementText": txt, "context": "{}"} for i, txt in enumerate(items, start=1)]

    def gen():
        processed = 0

        def worker(row: Dict[str, str]) -> Dict[str, Any]:
            rid = row["id"]
            requirement_text = row["requirementText"]
            context_obj: Dict[str, Any] = {}
            t0 = time.time()
            try:
                # Evaluation sichern/ermitteln
                try:
                    criteria_keys = [c["key"] for c in load_criteria(get_db())] or ["clarity", "testability", "measurability"]
                except Exception:
                    criteria_keys = ["clarity", "testability", "measurability"]
                eval_id, summ = ensure_evaluation_exists(requirement_text, context_obj, criteria_keys)

                # Evaluation-Details aus DB
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
                rewritten = llm_rewrite(requirement_text, context_obj)

                # Optional Suggestions
                suggestions = []
                if include_flag:
                    try:
                        suggestions = llm_suggest(requirement_text, context_obj) or []
                        # optional persist
                        try:
                            with get_db() as c2:
                                for atom in suggestions:
                                    c2.execute(
                                        "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                                        (eval_id, json.dumps(atom, ensure_ascii=False), "atom"),
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

        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            futs = [ex.submit(worker, r) for r in rows]
            for fut in futures.as_completed(futs):
                processed += 1
                try:
                    result = fut.result()
                except Exception as e:
                    result = {"event": "error", "message": str(e)}
                yield json.dumps(result, ensure_ascii=False) + "\n"

        yield json.dumps({"event": "end", "processed": processed}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# -----------------------
# v2 Service-Layer Endpunkte (EvaluationService)
# -----------------------

@router.post("/api/v2/evaluate/single", response_model=EvaluateSingleResponse, responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def evaluate_single_v2(body: EvaluateSingleRequest, request: Request):
    """
    Service-Layer: Einzel-Evaluation über EvaluationService.
    """
    try:
        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()
        res = svc.evaluate_single(
            body.text,
            context=(body.context or {}),
            criteria_keys=body.criteria_keys,
            threshold=body.threshold,
            ctx=ctx,
        )
        return res
    except ServiceError as se:
        return JSONResponse(content={"error": se.code, "message": se.message, "details": se.details}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v2/evaluate/batch", response_model=List[EvaluateBatchItem], responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def evaluate_batch_v2_service(body: EvaluateBatchRequestV2, request: Request):
    """
    Service-Layer: Batch-Evaluation über EvaluationService.
    """
    try:
        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()
        res = svc.evaluate_batch(
            body.items,
            context=(body.context or {}),
            criteria_keys=body.criteria_keys,
            threshold=body.threshold,
            ctx=ctx,
        )
        return res
    except ServiceError as se:
        return JSONResponse(content={"error": se.code, "message": se.message, "details": se.details}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)