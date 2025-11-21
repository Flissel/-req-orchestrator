from __future__ import annotations

from typing import Any, Dict, List
import logging
import json
import time
import concurrent.futures as futures

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response

from backend.legacy.batch import (
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

# All 9 quality criteria (fallback when load_criteria() fails)
DEFAULT_CRITERIA_KEYS = [
    "clarity", "testability", "measurability",
    "atomic", "concise", "unambiguous",
    "consistent_language",
    "design_independent", "purpose_independent"
]

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
                    criteria_keys = [c["key"] for c in load_criteria(get_db())] or DEFAULT_CRITERIA_KEYS
                except Exception:
                    criteria_keys = DEFAULT_CRITERIA_KEYS
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
                    criteria_keys = [c["key"] for c in load_criteria(get_db())] or DEFAULT_CRITERIA_KEYS
                except Exception:
                    criteria_keys = DEFAULT_CRITERIA_KEYS
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


# ============================================================================
# SSE (Server-Sent Events) Streaming Endpoint for Real-Time Validation
# ============================================================================

@router.get("/api/v1/validation/stream/{session_id}")
async def stream_validation_events(session_id: str):
    """
    SSE (Server-Sent Events) endpoint for streaming real-time validation updates.

    This endpoint provides a persistent connection for clients to receive live updates
    as the RequirementOrchestrator processes requirements through validation.

    Event Types:
    - connected: Initial connection confirmation
    - evaluation_started: Validation begins for a requirement
    - evaluation_completed: All criteria evaluated, scores available
    - requirement_updated: Requirement text changed after criterion fix
    - requirement_split: Requirement split into atomic sub-requirements
    - validation_complete: Validation finished (passed or failed)
    - validation_error: Error occurred during validation
    - stream_error: Error in the SSE stream itself

    Args:
        session_id: Unique session identifier (UUID recommended)

    Returns:
        StreamingResponse with text/event-stream media type

    Usage (JavaScript EventSource):
        const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`);

        eventSource.addEventListener('requirement_updated', (event) => {
            const data = JSON.parse(event.data);
            console.log('Requirement updated:', data.old_text, '→', data.new_text);
        });

        eventSource.addEventListener('validation_complete', (event) => {
            const data = JSON.parse(event.data);
            console.log('Validation complete:', data.passed, data.final_score);
            eventSource.close();
        });

    Notes:
    - Connection includes automatic keepalive pings every 30 seconds
    - Stream closes automatically after validation_complete or validation_error events
    - Sessions are automatically cleaned up after 60 minutes of inactivity
    """
    from backend.services.validation_stream_service import (
        validation_stream_service,
        create_sse_response
    )

    # Start cleanup task if not already running
    validation_stream_service.start_cleanup_task()

    # Stream events for this session
    return StreamingResponse(
        validation_stream_service.stream_events(session_id),
        **create_sse_response()
    )


# ============================================================================
# Automatic Requirement Validation with Orchestrator
# ============================================================================

@router.post("/api/v1/validate/auto")
async def validate_auto(request: Request):
    """
    Automatic requirement validation using the RequirementOrchestrator.

    This endpoint replaces the manual UserClarificationAgent workflow with an automatic
    "Society of Mind" approach where specialist agents fix each quality criterion.

    Request Body:
        {
            "requirement_id": "REQ-001",
            "requirement_text": "Die App muss schnell sein",
            "context": {},  // optional
            "session_id": "uuid",  // optional for SSE streaming
            "threshold": 0.7,  // optional
            "max_iterations": 3  // optional
        }

    Response:
        {
            "requirement_id": "REQ-001",
            "original_text": "Die App muss schnell sein",
            "final_text": "As a user, I want the app to respond within 200ms...",
            "passed": true,
            "final_score": 0.85,
            "final_scores": {
                "clarity": 0.9,
                "testability": 0.8,
                ...
            },
            "split_occurred": false,
            "split_children": [],
            "total_fixes": 5,
            "iterations": [
                {
                    "iteration": 1,
                    "timestamp": "2025-11-11T10:00:00Z",
                    "requirement_text": "...",
                    "criterion_scores": {...},
                    "overall_score": 0.6,
                    "fixes_applied": [
                        {
                            "criterion": "clarity",
                            "old_text": "...",
                            "new_text": "...",
                            "suggestion": "Add user story format",
                            "score_before": 0.5,
                            "score_after": 0.9
                        }
                    ],
                    "split_occurred": false,
                    "split_children": []
                }
            ],
            "error_message": null
        }

    Notes:
    - Automatically fixes failing criteria using specialist agents
    - Handles atomic violations by splitting requirements
    - Streams real-time updates if session_id is provided
    - Maximum 3 iteration rounds to avoid infinite loops
    - Tracks all changes in manifest processing stages
    """
    try:
        payload = await _read_json_tolerant(request)

        requirement_id = payload.get("requirement_id")
        requirement_text = payload.get("requirement_text")
        context = payload.get("context", {})
        session_id = payload.get("session_id")
        threshold = payload.get("threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)

        if not requirement_id or not requirement_text:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "requirement_id and requirement_text are required"
                },
                status_code=400
            )

        # Import orchestrator components
        try:
            from arch_team.agents.requirement_orchestrator import RequirementOrchestrator
            from backend.services.validation_stream_service import create_stream_callback
        except ImportError as e:
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import orchestrator: {str(e)}"
                },
                status_code=500
            )

        # Create stream callback if session_id provided
        stream_callback = None
        if session_id:
            stream_callback = create_stream_callback(session_id)

        # Create orchestrator
        orchestrator = RequirementOrchestrator(
            threshold=threshold,
            max_iterations=max_iterations,
            stream_callback=stream_callback
        )

        # Process requirement
        result = await orchestrator.process(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            context=context,
            session_id=session_id
        )

        # Return result with success field for frontend compatibility
        result_dict = result.to_dict()
        result_dict["success"] = True
        return JSONResponse(content=result_dict)

    except Exception as e:
        logging.getLogger("app").error(f"Error in validate_auto: {e}", exc_info=True)
        return JSONResponse(
            content={"success": False, "error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.post("/api/v1/validate/auto/batch")
async def validate_auto_batch(request: Request):
    """
    Batch automatic requirement validation using the RequirementOrchestrator.

    Request Body:
        {
            "requirements": [
                {"id": "REQ-001", "text": "Die App muss schnell sein"},
                {"id": "REQ-002", "text": "System soll skalierbar sein"}
            ],
            "context": {},  // optional
            "session_id": "uuid",  // optional for SSE streaming
            "threshold": 0.7,  // optional
            "max_iterations": 3  // optional
        }

    Response:
        {
            "results": [
                {
                    "requirement_id": "REQ-001",
                    "original_text": "...",
                    "final_text": "...",
                    "passed": true,
                    ...
                }
            ],
            "summary": {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "split": 0,
                "total_fixes": 10
            }
        }
    """
    try:
        payload = await _read_json_tolerant(request)

        requirements = payload.get("requirements", [])
        context = payload.get("context", {})
        session_id = payload.get("session_id")
        threshold = payload.get("threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)

        if not requirements or not isinstance(requirements, list):
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "requirements array is required"
                },
                status_code=400
            )

        # Import orchestrator components
        try:
            from arch_team.agents.requirement_orchestrator import BatchOrchestrator
            from backend.services.validation_stream_service import create_stream_callback
        except ImportError as e:
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import orchestrator: {str(e)}"
                },
                status_code=500
            )

        # Create stream callback if session_id provided
        stream_callback = None
        if session_id:
            stream_callback = create_stream_callback(session_id)

        # Create batch orchestrator
        batch_orchestrator = BatchOrchestrator(
            threshold=threshold,
            max_iterations=max_iterations,
            stream_callback=stream_callback
        )

        # Process batch
        results = await batch_orchestrator.process_batch(
            requirements=requirements,
            context=context,
            session_id=session_id
        )

        # Calculate summary
        summary = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed and not r.split_occurred),
            "split": sum(1 for r in results if r.split_occurred),
            "total_fixes": sum(r.total_fixes for r in results)
        }

        return JSONResponse(content={
            "results": [r.to_dict() for r in results],
            "summary": summary
        })

    except Exception as e:
        logging.getLogger("app").error(f"Error in validate_auto_batch: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.get("/api/v1/validation/history/{requirement_id}")
async def get_validation_history(requirement_id: str, limit: int = 10):
    """Get validation history for a requirement"""
    try:
        from backend.core import db as _db
        from backend.services.validation_persistence_service import validation_persistence_service

        with _db.get_db() as conn:
            history = validation_persistence_service.get_validation_history(conn, requirement_id, limit)

        return JSONResponse(content={
            "success": True,
            "requirement_id": requirement_id,
            "history": history,
            "count": len(history)
        })

    except Exception as e:
        logging.getLogger("app").error(f"Error getting validation history: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.get("/api/v1/validation/details/{validation_id}")
async def get_validation_details(validation_id: str):
    """Get complete validation details including iterations and fixes"""
    try:
        from backend.core import db as _db
        from backend.services.validation_persistence_service import validation_persistence_service

        with _db.get_db() as conn:
            details = validation_persistence_service.get_validation_details(conn, validation_id)

        if not details:
            return JSONResponse(
                content={"error": "not_found", "message": f"Validation {validation_id} not found"},
                status_code=404
            )

        return JSONResponse(content={
            "success": True,
            "validation": details
        })

    except Exception as e:
        logging.getLogger("app").error(f"Error getting validation details: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.get("/api/v1/validation/analytics")
async def get_validation_analytics(days: int = 30):
    """Get validation analytics for the last N days"""
    try:
        from backend.core import db as _db
        from backend.services.validation_persistence_service import validation_persistence_service

        with _db.get_db() as conn:
            analytics = validation_persistence_service.get_validation_analytics(conn, days)

        return JSONResponse(content={
            "success": True,
            "analytics": analytics,
            "days": days
        })

    except Exception as e:
        logging.getLogger("app").error(f"Error getting validation analytics: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.get("/api/v1/validation/export/{validation_id}")
async def export_validation_report(validation_id: str, format: str = "markdown"):
    """Export validation report in various formats (markdown, json)"""
    try:
        from backend.core import db as _db
        from backend.services.validation_persistence_service import validation_persistence_service

        with _db.get_db() as conn:
            details = validation_persistence_service.get_validation_details(conn, validation_id)

        if not details:
            return JSONResponse(
                content={"error": "not_found", "message": f"Validation {validation_id} not found"},
                status_code=404
            )

        if format == "markdown":
            markdown = _generate_markdown_report(details)
            return Response(
                content=markdown,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=validation_{validation_id}.md"
                }
            )
        elif format == "json":
            return JSONResponse(content=details)
        else:
            return JSONResponse(
                content={"error": "invalid_format", "message": f"Format '{format}' not supported"},
                status_code=400
            )

    except Exception as e:
        logging.getLogger("app").error(f"Error exporting validation report: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


def _generate_markdown_report(details: dict) -> str:
    """Generate a markdown report from validation details"""
    from datetime import datetime

    lines = []
    lines.append(f"# Validation Report: {details['id']}")
    lines.append("")
    lines.append(f"**Requirement ID:** {details['requirement_id']}")
    lines.append(f"**Started:** {details['started_at']}")
    lines.append(f"**Completed:** {details.get('completed_at', 'N/A')}")
    lines.append(f"**Status:** {'✅ PASSED' if details.get('passed') else '❌ FAILED'}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Initial Text:** {details['initial_text']}")
    lines.append(f"- **Final Text:** {details.get('final_text', 'N/A')}")
    lines.append(f"- **Initial Score:** {details.get('initial_score', 'N/A')}")
    lines.append(f"- **Final Score:** {details.get('final_score', 'N/A')}")
    lines.append(f"- **Threshold:** {details['threshold']}")
    lines.append(f"- **Total Iterations:** {details.get('total_iterations', 0)}")
    lines.append(f"- **Total Fixes:** {details.get('total_fixes', 0)}")
    lines.append(f"- **Split Occurred:** {'Yes' if details.get('split_occurred') else 'No'}")
    lines.append("")

    # Iterations
    if details.get('iterations'):
        lines.append("## Iteration History")
        lines.append("")

        for iteration in details['iterations']:
            lines.append(f"### Iteration {iteration['iteration_number']}")
            lines.append("")
            lines.append(f"- **Overall Score:** {iteration.get('overall_score', 'N/A')}")
            lines.append(f"- **Requirement Text:** {iteration['requirement_text']}")
            lines.append(f"- **Fixes Applied:** {iteration.get('fixes_applied', 0)}")
            lines.append("")

            # Criterion scores
            if iteration.get('criterion_scores'):
                lines.append("#### Criterion Scores")
                lines.append("")
                lines.append("| Criterion | Score | Passed |")
                lines.append("|-----------|-------|--------|")
                for score in iteration['criterion_scores']:
                    passed_mark = "✓" if score['passed'] else "✗"
                    lines.append(f"| {score['criterion']} | {score['score']:.2f} | {passed_mark} |")
                lines.append("")

            # Fixes
            if iteration.get('fixes'):
                lines.append("#### Applied Fixes")
                lines.append("")
                for fix in iteration['fixes']:
                    lines.append(f"**{fix['criterion']}**")
                    lines.append(f"- Score: {fix['score_before']:.2f} → {fix['score_after']:.2f} (+{fix['improvement']:.2f})")
                    if fix.get('suggestion'):
                        lines.append(f"- Suggestion: {fix['suggestion']}")
                    lines.append(f"- Old: {fix['old_text']}")
                    lines.append(f"- New: {fix['new_text']}")
                    lines.append("")

            if iteration.get('split_occurred'):
                lines.append(f"**Split into {iteration.get('split_children_count', 0)} children**")
                lines.append("")

    # Metadata
    if details.get('metadata'):
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"```json\n{details['metadata']}\n```")
        lines.append("")

    lines.append("---")
    lines.append(f"*Report generated on {datetime.utcnow().isoformat()}*")

    return "\n".join(lines)