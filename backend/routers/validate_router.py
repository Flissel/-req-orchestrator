import asyncio
import concurrent.futures as futures
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
import logging
import json
import time

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
from backend.schemas import (
    ValidateItemResult, ValidateSuggestResponse, EvaluateSingleRequest,
    EvaluateSingleResponse, EvaluateBatchRequestV2, EvaluateBatchItem, ErrorResponse,
    AllInOneValidationRequest, AllInOneValidationResult
)
from backend.services import EvaluationService, RequestContext, ServiceError
from backend.services.validation_persistence_service import ValidationPersistenceService

router = APIRouter(tags=["validate"])


def _generate_criterion_question(criterion: str, req_text: str, feedback: str) -> str:
    """Generate a clarification question based on the failing criterion"""
    questions = {
        "measurability": "What specific metrics or values should be used? (e.g., response time in seconds, throughput)",
        "testability": "How can we verify this requirement is met? What test scenarios should be used?",
        "clarity": "Could you clarify what exactly is meant? Which terms need more precise definition?",
        "atomic": "This requirement covers multiple aspects. Which part is most important, or should it be split?",
        "unambiguous": "Some terms could be interpreted differently. What specific meaning is intended?",
        "concise": "Can this requirement be expressed more concisely while keeping its meaning?",
        "consistent_language": "Should different terminology be used to match the rest of the document?",
        "design_independent": "This mentions implementation details. What is the actual user/business need?",
        "purpose_independent": "What is the underlying goal this requirement should achieve?"
    }
    return questions.get(criterion.lower(), f"Please clarify: {feedback}")

# All 9 quality criteria (fallback when load_criteria() fails)
DEFAULT_CRITERIA_KEYS = [
    "clarity",
    "testability",
    "measurability",
    "atomic",
    "concise",
    "unambiguous",
    "consistent_language",
    "design_independent",
    "purpose_independent"
]


async def _read_json_tolerant(request: Request) -> Any:
    """Robust JSON reader with UTF-8-SIG/BOM, whitespace trimming, and raw fallback."""
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

        rows: List[Dict[str, str]] = []
        for idx, txt in enumerate(items, start=1):
            rows.append({"id": f"REQ_{idx}", "requirementText": txt, "context": "{}"})

        eval_results = process_evaluations(rows)
        rewrite_results = process_rewrites(rows)

        sug_map: Dict[str, Any] = {}
        if include_flag:
            try:
                sug_map = process_suggestions(rows)
            except Exception:
                sug_map = {}

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
    """NDJSON-Stream: sendet pro Requirement Suggestions (Atoms) als einzelne JSON-Zeile."""
    lg = logging.getLogger("app")
    payload = await _read_json_tolerant(request)
    if isinstance(payload, dict):
        items = payload.get("items")
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
    """NDJSON-Stream: sendet pro Requirement ein Ergebnis als einzelne JSON-Zeile."""
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
                try:
                    criteria_keys = [c["key"] for c in load_criteria(get_db())] or DEFAULT_CRITERIA_KEYS
                except Exception:
                    criteria_keys = DEFAULT_CRITERIA_KEYS
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

                rewritten = llm_rewrite(requirement_text, context_obj)

                suggestions = []
                if include_flag:
                    try:
                        suggestions = llm_suggest(requirement_text, context_obj) or []
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
    Service-Layer: Einzel-Evaluation ueber EvaluationService.
    Uses asyncio.to_thread() for parallel LLM calls without blocking the event loop.
    """
    try:
        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()
        
        # Run synchronous LLM call in thread pool to enable parallel processing
        res = await asyncio.to_thread(
            svc.evaluate_single,
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
    """Service-Layer: Batch-Evaluation ueber EvaluationService."""
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


@router.post("/api/v2/evaluate/batch/optimized", responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def evaluate_batch_optimized(request: Request):
    """
    OPTIMIERTE Batch-Evaluation mit echtem LLM-Batching.
    
    Sendet mehrere Requirements in einem einzigen LLM-Call für ~3x Speedup.
    
    Request Body:
    {
        "items": [
            {"id": "REQ-001", "text": "Das System soll..."},
            {"id": "REQ-002", "text": "Als User..."}
        ],
        "context": {},
        "criteria_keys": ["clarity", "testability", ...],
        "threshold": 0.7,
        "batch_size": 5
    }
    
    Response:
    [
        {"id": "REQ-001", "originalText": "...", "evaluation": [...], "score": 0.8, "verdict": "pass"},
        ...
    ]
    """
    try:
        payload = await _read_json_tolerant(request)
        
        items = payload.get("items", [])
        if not isinstance(items, list):
            return JSONResponse(
                content={"error": "invalid_request", "message": "items must be a list of {id, text} objects"},
                status_code=400,
            )
        
        # Normalize items (accept both dict and string formats)
        normalized_items = []
        for i, item in enumerate(items):
            if isinstance(item, str):
                normalized_items.append({"id": f"REQ-{i+1}", "text": item})
            elif isinstance(item, dict):
                normalized_items.append({
                    "id": str(item.get("id", f"REQ-{i+1}")),
                    "text": str(item.get("text", item.get("title", "")))
                })
            else:
                normalized_items.append({"id": f"REQ-{i+1}", "text": str(item)})
        
        context = payload.get("context", {})
        criteria_keys = payload.get("criteria_keys")
        threshold = payload.get("threshold")
        batch_size = payload.get("batch_size", 5)
        
        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()
        
        # Run batch evaluation in thread pool for parallel processing
        results = await asyncio.to_thread(
            svc.evaluate_batch_optimized,
            normalized_items,
            context=context,
            criteria_keys=criteria_keys,
            threshold=threshold,
            batch_size=batch_size,
            ctx=ctx,
        )
        
        return results
        
    except ServiceError as se:
        return JSONResponse(content={"error": se.code, "message": se.message, "details": se.details}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


# =======================================================================
# SSE (Server-Sent Events) Streaming Endpoint for Real-Time Validation
# =======================================================================

@router.get("/api/v1/validation/stream/{session_id}")
async def stream_validation_events(session_id: str):
    """SSE endpoint for streaming real-time validation updates."""
    from backend.services.validation_stream_service import (
        validation_stream_service,
        create_sse_response
    )

    validation_stream_service.start_cleanup_task()

    return StreamingResponse(
        validation_stream_service.stream_events(session_id),
        **create_sse_response()
    )


# =======================================================================
# Validation Analytics Endpoint
# =======================================================================

@router.get("/api/v1/validation/analytics")
async def get_validation_analytics(days: int = 30):
    """
    Get validation analytics for the last N days.
    Returns statistics about validation runs.
    """
    try:
        persistence = ValidationPersistenceService()
        
        # Get summary statistics
        total_validations = persistence.count_validations(days=days)
        passed = persistence.count_validations(days=days, verdict="pass")
        failed = persistence.count_validations(days=days, verdict="fail")
        
        # Calculate percentages
        pass_rate = (passed / total_validations * 100) if total_validations > 0 else 0
        
        return {
            "period_days": days,
            "total_validations": total_validations,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(pass_rate, 2),
            "avg_score": persistence.get_average_score(days=days),
            "criteria_stats": persistence.get_criteria_stats(days=days)
        }
    except AttributeError:
        # If ValidationPersistenceService doesn't have these methods, return mock data
        return {
            "period_days": days,
            "total_validations": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "avg_score": 0.0,
            "criteria_stats": {}
        }
    except Exception as e:
        return JSONResponse(
            content={"error": "analytics_error", "message": str(e)},
            status_code=500
        )


# =======================================================================
# Automatic Batch Requirement Validation
# =======================================================================

@router.post("/api/v1/validate/auto/batch")
async def validate_auto_batch(request: Request):
    """
    Automatic batch requirement validation using the RequirementsOrchestrator.
    Processes multiple requirements with automatic fix of failing criteria.
    
    Request Body:
    {
        "requirements": [
            {"id": "REQ-001", "text": "Das System soll..."},
            {"id": "REQ-002", "text": "Als User..."}
        ],
        "session_id": "session-xxx",
        "threshold": 0.7,
        "max_iterations": 3
    }
    """
    try:
        payload = await _read_json_tolerant(request)

        requirements = payload.get("requirements", [])
        session_id = payload.get("session_id")
        context = payload.get("context", {})
        threshold = payload.get("threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)

        if not requirements:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "requirements array is required",
                },
                status_code=400
            )

        try:
            from arch_team.agents.requirements_orchestrator import (
                RequirementsOrchestrator,
                OrchestratorConfig
            )
            from backend.services.validation_stream_service import validation_stream_service
        except ImportError as e:
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import orchestrator: {str(e)}",
                },
                status_code=500
            )

        # Create configuration with request parameters
        config = OrchestratorConfig(
            quality_threshold=threshold,
            max_iterations=max_iterations
        )
        
        # Create stream callback for SSE updates
        def progress_callback(stage: str, completed: int, total: int, message: str):
            if session_id:
                validation_stream_service.send_event(
                    session_id,
                    "progress",
                    {
                        "stage": stage,
                        "completed": completed,
                        "total": total,
                        "message": message
                    }
                )

        orchestrator = RequirementsOrchestrator(
            config=config,
            progress_callback=progress_callback
        )

        # Format requirements for orchestrator (expects req_id and title)
        formatted_reqs = []
        for i, req in enumerate(requirements):
            formatted_reqs.append({
                "req_id": req.get("id", f"REQ-{i+1}"),
                "title": req.get("text", req.get("title", "")),
                "tag": req.get("tag", "requirements")
            })

        # Run orchestrator
        result = await orchestrator.run(
            requirements=formatted_reqs,
            correlation_id=session_id
        )

        return {
            "success": result.success,
            "session_id": session_id,
            "total_iterations": result.total_iterations,
            "initial_pass_rate": result.initial_pass_rate,
            "final_pass_rate": result.final_pass_rate,
            "requirements": result.requirements,
            "split_requirements": result.split_requirements,
            "accepted_requirements": result.accepted_requirements,
            "rejected_requirements": result.rejected_requirements,
            "total_time_ms": result.total_time_ms,
            "workflow_id": result.workflow_id,
            "mode": result.mode,
            "error": result.error
        }

    except Exception as e:
        logging.getLogger("app").error(f"validate_auto_batch error: {e}")
        return JSONResponse(
            content={
                "error": "internal_error",
                "message": str(e),
            },
            status_code=500
        )


# =======================================================================
# Automatic Requirement Validation with Orchestrator
# =======================================================================

@router.post("/api/v1/validate/auto")
async def validate_auto(request: Request):
    """
    Automatic requirement validation using the RequirementOrchestrator.
    Automatically fixes failing criteria using specialist agents.
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
                    "message": "requirement_id and requirement_text are required",
                },
                status_code=400
            )

        try:
            from arch_team.agents.requirement_orchestrator import RequirementOrchestrator
            from backend.services.validation_stream_service import create_stream_callback
        except ImportError as e:
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import orchestrator: {str(e)}",
                },
                status_code=500
            )

        stream_callback = None
        if session_id:
            stream_callback = create_stream_callback(session_id)

        orchestrator = RequirementOrchestrator(
            threshold=threshold,
            max_iterations=max_iterations,
            stream_callback=stream_callback
        )

        result = await orchestrator.process(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            context=context,
            session_id=session_id
        )

        return result

    except Exception as e:
        logging.getLogger("app").error(f"validate_auto error: {e}")
        return JSONResponse(
            content={
                "error": "internal_error",
                "message": str(e),
            },
            status_code=500
        )

# =======================================================================
# NEW: Enhanced Auto Validation with SocietyOfMind (Faster)
# =======================================================================

@router.post("/api/v1/validate/auto/enhanced")
async def validate_auto_enhanced(request: Request):
    """
    Enhanced automatic requirement validation using SocietyOfMindEnhancement.
    
    This is FASTER than /api/v1/validate/auto because it uses:
    - PURPOSE-focused coordinated prompts (4-5 LLM calls per iteration)
    - Auto-generated answers for missing metrics
    - Returns gaps that cannot be auto-filled as suggestions
    
    vs. the old process:
    - 9 separate criterion agents (9 LLM calls per iteration)
    - Sequential evaluation and rewrite cycles
    
    Request Body:
    {
        "requirements": [
            {"id": "REQ-001", "text": "Das System soll..."},
            {"id": "REQ-002", "text": "Als User..."}
        ],
        "session_id": "session-xxx",
        "threshold": 0.7,
        "max_iterations": 3
    }
    
    Response:
    {
        "success": true,
        "total_processed": 5,
        "passed_count": 3,
        "failed_count": 2,
        "improved_count": 4,
        "average_score": 0.75,
        "total_time_ms": 5000,
        "requirements": [
            {
                "id": "REQ-001",
                "original_text": "...",
                "enhanced_text": "...",
                "score": 0.8,
                "verdict": "pass",
                "purpose": "...",
                "gaps_filled": [...],
                "gaps_remaining": [...]
            }
        ]
    }
    """
    lg = logging.getLogger("app")
    
    try:
        payload = await _read_json_tolerant(request)
        
        requirements = payload.get("requirements", [])
        session_id = payload.get("session_id")
        threshold = payload.get("threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)
        
        if not requirements:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "requirements array is required",
                },
                status_code=400
            )
        
        # Normalize requirements format
        normalized_reqs = []
        for i, req in enumerate(requirements):
            if isinstance(req, str):
                normalized_reqs.append({"id": f"REQ-{i+1}", "text": req})
            elif isinstance(req, dict):
                normalized_reqs.append({
                    "id": req.get("id", req.get("requirement_id", f"REQ-{i+1}")),
                    "text": req.get("text", req.get("requirement_text", req.get("title", "")))
                })
        
        try:
            from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
            from backend.services.validation_stream_service import validation_stream_service
        except ImportError as e:
            lg.error(f"Import error: {e}")
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import enhancement service: {str(e)}",
                },
                status_code=500
            )
        
        # Create progress callback for SSE updates
        def progress_callback(stage: str, completed: int, total: int, message: str):
            if session_id:
                validation_stream_service.send_event(
                    session_id,
                    "progress",
                    {
                        "stage": stage,
                        "completed": completed,
                        "total": total,
                        "message": message,
                        "process": "society_of_mind"
                    }
                )
        
        # Get enhancement service
        enhancement_service = get_enhancement_service()
        
        # Run auto batch enhancement
        result = await enhancement_service.run_auto_batch(
            requirements=normalized_reqs,
            quality_threshold=threshold,
            max_iterations=max_iterations,
            progress_callback=progress_callback
        )
        
        # Send completion event
        if session_id:
            validation_stream_service.send_event(
                session_id,
                "complete",
                {
                    "success": result.success,
                    "passed": result.passed_count,
                    "failed": result.failed_count,
                    "process": "society_of_mind"
                }
            )
        
        return {
            "success": result.success,
            "session_id": session_id,
            "total_processed": result.total_processed,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "improved_count": result.improved_count,
            "average_score": result.average_score,
            "total_time_ms": result.total_time_ms,
            "requirements": result.requirements,
            "error": result.error
        }
        
    except Exception as e:
        lg.error(f"validate_auto_enhanced error: {e}", exc_info=True)
        return JSONResponse(
            content={
                "error": "internal_error",
                "message": str(e),
            },
            status_code=500
        )


@router.post("/api/v1/validate/single/enhanced")
async def validate_single_enhanced(request: Request):
    """
    Enhanced single requirement validation using SocietyOfMindEnhancement.
    
    Faster alternative to /api/v1/validate/auto for single requirements.
    
    Request Body:
    {
        "requirement_id": "REQ-001",
        "requirement_text": "Das System soll...",
        "threshold": 0.7,
        "max_iterations": 3
    }
    """
    lg = logging.getLogger("app")
    
    try:
        payload = await _read_json_tolerant(request)
        
        requirement_id = payload.get("requirement_id", "REQ-1")
        requirement_text = payload.get("requirement_text")
        threshold = payload.get("threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)
        
        if not requirement_text:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "requirement_text is required",
                },
                status_code=400
            )
        
        try:
            from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
        except ImportError as e:
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import enhancement service: {str(e)}",
                },
                status_code=500
            )
        
        enhancement_service = get_enhancement_service()
        
        # Run auto batch with single requirement
        result = await enhancement_service.run_auto_batch(
            requirements=[{"id": requirement_id, "text": requirement_text}],
            quality_threshold=threshold,
            max_iterations=max_iterations
        )
        
        if result.requirements:
            req_result = result.requirements[0]
            return {
                "id": req_result.get("id"),
                "original_text": req_result.get("original_text"),
                "enhanced_text": req_result.get("enhanced_text"),
                "score": req_result.get("score"),
                "verdict": req_result.get("verdict"),
                "iterations": req_result.get("iterations"),
                "purpose": req_result.get("purpose"),
                "gaps_filled": req_result.get("gaps_filled", []),
                "gaps_remaining": req_result.get("gaps_remaining", []),
                "changes": req_result.get("changes", []),
                "success": req_result.get("success", True),
                "time_ms": result.total_time_ms
            }
        
        return JSONResponse(
            content={"error": "no_result", "message": "Enhancement produced no result"},
            status_code=500
        )
        
    except Exception as e:
        lg.error(f"validate_single_enhanced error: {e}")
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )

# =======================================================================
# Mining + Validation Pipeline Endpoint
# =======================================================================

@router.post("/api/v1/mining/validate")
async def mining_validate(request: Request):
    """
    End-to-end pipeline: Document Mining + Requirement Validation.
    
    1. ChunkMinerAgent extracts requirements from uploaded documents
    2. RequirementsOrchestrator validates against 10 IEEE 29148 criteria
    3. DecisionMaker decides: SPLIT / REWRITE / ACCEPT / CLARIFY / REJECT
    4. Auto-improvement loop until quality threshold met
    
    Request Body:
    {
        "files": [
            {"filename": "reqs.md", "content": "# Requirements\n- Das System soll..."},
            {"text": "Als Benutzer möchte ich..."}
        ],
        "session_id": "session-xxx",
        "quality_threshold": 0.7,
        "max_iterations": 3,
        "auto_mode": true,
        "persist_to_db": true
    }
    
    Response:
    {
        "success": true,
        "pipeline_id": "abc12345",
        "mining": {
            "mined_count": 12,
            "time_ms": 1500,
            "source_files": ["reqs.md"]
        },
        "validation": {
            "initial_pass_rate": 0.42,
            "final_pass_rate": 0.83,
            "iterations": 2,
            "time_ms": 8500
        },
        "final_requirements": [...],
        "statistics": {
            "passed": 10,
            "failed": 2,
            "improved": 5,
            "total_time_ms": 10000
        }
    }
    """
    lg = logging.getLogger("app")
    
    try:
        payload = await _read_json_tolerant(request)
        
        files = payload.get("files", [])
        session_id = payload.get("session_id")
        quality_threshold = payload.get("quality_threshold", 0.7)
        max_iterations = payload.get("max_iterations", 3)
        auto_mode = payload.get("auto_mode", True)
        persist_to_db = payload.get("persist_to_db", True)
        mining_model = payload.get("mining_model")  # Optional override
        
        if not files:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "files array is required (list of {filename, content} or {text})"
                },
                status_code=400
            )
        
        # Convert request format to pipeline input format
        files_or_texts = []
        for item in files:
            if isinstance(item, str):
                # Plain text
                files_or_texts.append({"text": item})
            elif isinstance(item, dict):
                if "content" in item:
                    # {filename, content} format
                    files_or_texts.append({
                        "filename": item.get("filename", "unknown.txt"),
                        "data": item["content"].encode("utf-8") if isinstance(item["content"], str) else item["content"]
                    })
                elif "text" in item:
                    # {text} format - raw text
                    files_or_texts.append(item["text"])
                elif "data" in item:
                    # {filename, data} format - bytes
                    files_or_texts.append(item)
        
        if not files_or_texts:
            return JSONResponse(
                content={
                    "error": "invalid_request",
                    "message": "No valid file/text content found"
                },
                status_code=400
            )
        
        # Import pipeline
        try:
            from arch_team.agents.mining_validation_pipeline import MiningValidationPipeline
            from backend.services.validation_stream_service import validation_stream_service
        except ImportError as e:
            lg.error(f"Import error: {e}")
            return JSONResponse(
                content={
                    "error": "import_error",
                    "message": f"Failed to import pipeline: {str(e)}"
                },
                status_code=500
            )
        
        # Create progress callback for SSE updates
        def progress_callback(stage: str, completed: int, total: int, message: str):
            if session_id:
                validation_stream_service.send_event(
                    session_id,
                    "progress",
                    {
                        "stage": stage,
                        "completed": completed,
                        "total": total,
                        "message": message,
                        "pipeline": "mining_validation"
                    }
                )
        
        # Create and run pipeline
        pipeline = MiningValidationPipeline(
            quality_threshold=quality_threshold,
            max_iterations=max_iterations,
            auto_mode=auto_mode,
            persist_to_db=persist_to_db,
            progress_callback=progress_callback
        )
        
        result = await pipeline.process_files(
            files_or_texts,
            mining_model=mining_model,
            correlation_id=session_id
        )
        
        # Send completion event
        if session_id:
            validation_stream_service.send_event(
                session_id,
                "complete",
                {
                    "pipeline_id": result.pipeline_id,
                    "success": result.success,
                    "passed": result.passed_count,
                    "failed": result.failed_count
                }
            )
        
        return result.to_dict()
        
    except Exception as e:
        lg.error(f"mining_validate error: {e}", exc_info=True)
        return JSONResponse(
            content={
                "error": "internal_error",
                "message": str(e)
            },
            status_code=500
        )


@router.post("/api/v1/mining/validate/stream")
async def mining_validate_stream(request: Request) -> StreamingResponse:
    """
    Streaming version of mining + validation pipeline.
    Returns NDJSON stream with progress updates.
    """
    lg = logging.getLogger("app")
    payload = await _read_json_tolerant(request)
    
    files = payload.get("files", [])
    quality_threshold = payload.get("quality_threshold", 0.7)
    max_iterations = payload.get("max_iterations", 3)
    auto_mode = payload.get("auto_mode", True)
    persist_to_db = payload.get("persist_to_db", True)
    
    if not files:
        async def error_gen():
            yield json.dumps({"event": "error", "message": "files array required"}) + "\n"
        return StreamingResponse(error_gen(), media_type="application/x-ndjson")
    
    # Convert to pipeline format
    files_or_texts = []
    for item in files:
        if isinstance(item, str):
            files_or_texts.append({"text": item})
        elif isinstance(item, dict):
            if "content" in item:
                files_or_texts.append({
                    "filename": item.get("filename", "unknown.txt"),
                    "data": item["content"].encode("utf-8") if isinstance(item["content"], str) else item["content"]
                })
            elif "text" in item:
                files_or_texts.append(item["text"])
            elif "data" in item:
                files_or_texts.append(item)
    
    async def stream_gen():
        import asyncio
        from queue import Queue
        from threading import Thread
        
        progress_queue: Queue = Queue()
        
        def progress_callback(stage: str, completed: int, total: int, message: str):
            progress_queue.put({
                "event": "progress",
                "stage": stage,
                "completed": completed,
                "total": total,
                "message": message
            })
        
        try:
            from arch_team.agents.mining_validation_pipeline import MiningValidationPipeline
            
            pipeline = MiningValidationPipeline(
                quality_threshold=quality_threshold,
                max_iterations=max_iterations,
                auto_mode=auto_mode,
                persist_to_db=persist_to_db,
                progress_callback=progress_callback
            )
            
            # Start pipeline in background
            result_holder = [None]
            error_holder = [None]
            
            async def run_pipeline():
                try:
                    result_holder[0] = await pipeline.process_files(files_or_texts)
                except Exception as e:
                    error_holder[0] = e
            
            task = asyncio.create_task(run_pipeline())
            
            # Stream progress updates while pipeline runs
            while not task.done():
                while not progress_queue.empty():
                    update = progress_queue.get_nowait()
                    yield json.dumps(update, ensure_ascii=False) + "\n"
                await asyncio.sleep(0.1)
            
            # Flush remaining progress
            while not progress_queue.empty():
                update = progress_queue.get_nowait()
                yield json.dumps(update, ensure_ascii=False) + "\n"
            
            # Check for errors
            if error_holder[0]:
                yield json.dumps({
                    "event": "error",
                    "message": str(error_holder[0])
                }, ensure_ascii=False) + "\n"
            elif result_holder[0]:
                result = result_holder[0]
                yield json.dumps({
                    "event": "complete",
                    **result.to_dict()
                }, ensure_ascii=False) + "\n"
                
        except Exception as e:
            lg.error(f"Stream error: {e}")
            yield json.dumps({"event": "error", "message": str(e)}, ensure_ascii=False) + "\n"
    
    return StreamingResponse(stream_gen(), media_type="application/x-ndjson")


# =======================================================================
# ALL-IN-ONE VALIDATION (Unified Two-Mode Pipeline)
# =======================================================================

@router.post("/api/v1/validate/all-in-one", response_model=AllInOneValidationResult, responses={
    400: {"model": ErrorResponse, "description": "Bad Request"},
    500: {"model": ErrorResponse, "description": "Internal Error"},
})
async def validate_all_in_one(body: AllInOneValidationRequest, request: Request):
    """
    Unified all-in-one validation workflow with two modes:

    **Quick Mode** (mode="quick"):
    - Validates + auto-enhances requirements without user questions
    - Uses SocietyOfMindEnhancement for fast processing
    - Auto-generates reasonable values for missing metrics
    - Returns enhanced requirements with final scores

    **Guided Mode** (mode="guided"):
    - Validates requirements and collects clarification questions
    - Returns questions for user to answer
    - User submits answers via /api/v1/validate/all-in-one/apply-answers
    - Applies answers and re-validates

    Both modes use fixed configuration:
    - Quality threshold: 0.7 (70%)
    - Max iterations: 3
    - Parallel workers: 5

    SSE Events (via /api/v1/validation/stream/{session_id}):
    - pipeline_start: {mode, total_count, session_id}
    - stage_change: {stage: "validating|enhancing|collecting_questions|complete"}
    - requirement_scored: {req_id, score, verdict}
    - question_generated: {req_id, questions} (guided mode only)
    - enhancement_applied: {req_id, old_score, new_score}
    - pipeline_complete: {summary}
    """
    lg = logging.getLogger("app")

    try:
        requirements = body.requirements
        mode = body.mode.lower()
        session_id = body.session_id
        # Fixed configuration
        threshold = 0.7
        max_iterations = 3

        if not requirements:
            return JSONResponse(
                content={"error": "invalid_request", "message": "requirements array is required"},
                status_code=400
            )

        if mode not in ("quick", "guided"):
            return JSONResponse(
                content={"error": "invalid_request", "message": "mode must be 'quick' or 'guided'"},
                status_code=400
            )

        # Normalize requirements format
        normalized_reqs = []
        for i, req in enumerate(requirements):
            if isinstance(req, str):
                normalized_reqs.append({"id": f"REQ-{i+1}", "text": req})
            elif isinstance(req, dict):
                normalized_reqs.append({
                    "id": req.get("id", req.get("requirement_id", req.get("req_id", f"REQ-{i+1}"))),
                    "text": req.get("text", req.get("requirement_text", req.get("title", "")))
                })

        # Import services
        try:
            from backend.services.validation_stream_service import validation_stream_service
        except ImportError as e:
            lg.error(f"Import error: {e}")
            return JSONResponse(
                content={"error": "import_error", "message": f"Failed to import services: {str(e)}"},
                status_code=500
            )

        # Send pipeline start event
        if session_id:
            validation_stream_service.send_event(
                session_id,
                "pipeline_start",
                {
                    "mode": mode,
                    "total_count": len(normalized_reqs),
                    "session_id": session_id,
                    "threshold": threshold,
                    "max_iterations": max_iterations
                }
            )

        # =====================
        # QUICK MODE: Auto-enhance without questions
        # =====================
        if mode == "quick":
            try:
                from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
            except ImportError as e:
                lg.error(f"Import error: {e}")
                return JSONResponse(
                    content={"error": "import_error", "message": f"Failed to import enhancement service: {str(e)}"},
                    status_code=500
                )

            # Progress callback for SSE
            def progress_callback(stage: str, completed: int, total: int, message: str):
                if session_id:
                    validation_stream_service.send_event(
                        session_id,
                        "stage_change" if "stage" in stage.lower() else "progress",
                        {
                            "stage": stage,
                            "completed": completed,
                            "total": total,
                            "message": message,
                            "mode": "quick"
                        }
                    )

            # Send stage change
            if session_id:
                validation_stream_service.send_event(session_id, "stage_change", {"stage": "enhancing"})

            enhancement_service = get_enhancement_service()
            result = await enhancement_service.run_auto_batch(
                requirements=normalized_reqs,
                quality_threshold=threshold,
                max_iterations=max_iterations,
                progress_callback=progress_callback
            )

            # Send individual requirement events
            for req_result in (result.requirements or []):
                if session_id:
                    validation_stream_service.send_event(
                        session_id,
                        "requirement_scored",
                        {
                            "req_id": req_result.get("id"),
                            "score": req_result.get("score", 0),
                            "verdict": req_result.get("verdict", "fail"),
                            "enhanced": req_result.get("original_text") != req_result.get("enhanced_text")
                        }
                    )

            # Send completion event
            if session_id:
                validation_stream_service.send_event(
                    session_id,
                    "pipeline_complete",
                    {
                        "mode": "quick",
                        "passed": result.passed_count,
                        "failed": result.failed_count,
                        "improved": result.improved_count,
                        "average_score": result.average_score
                    }
                )

            return AllInOneValidationResult(
                success=result.success,
                mode="quick",
                session_id=session_id,
                stage="complete",
                total_processed=result.total_processed,
                passed_count=result.passed_count,
                failed_count=result.failed_count,
                improved_count=result.improved_count,
                average_score=result.average_score,
                total_time_ms=result.total_time_ms,
                requirements=result.requirements or [],
                pending_questions=None,
                error=result.error
            )

        # =====================
        # GUIDED MODE: Validate first, then generate questions for failing criteria
        # =====================
        else:  # mode == "guided"
            import time
            start_time = time.time()

            if session_id:
                validation_stream_service.send_event(session_id, "stage_change", {"stage": "validating"})

            # Validate all requirements and generate questions for failing ones
            processed_reqs = []
            all_questions = []
            eval_service = EvaluationService()

            for req in normalized_reqs:
                req_id = req.get("id")
                req_text = req.get("text", "")

                try:
                    eval_result = eval_service.evaluate_single(
                        requirement_text=req_text
                    )

                    score = eval_result.get("overall_score", 0)
                    verdict = "pass" if score >= threshold else "fail"
                    evaluation = eval_result.get("evaluation", [])

                    # For failing requirements, generate clarification questions
                    questions = []
                    gaps = []

                    if verdict == "fail":
                        for crit in evaluation:
                            if not crit.get("passed", True):
                                criterion_name = crit.get("criterion", "unknown")
                                feedback = crit.get("feedback", "")
                                gaps.append(f"{criterion_name}: {feedback}")

                                question = _generate_criterion_question(criterion_name, req_text, feedback)
                                if question:
                                    questions.append({
                                        "criterion": criterion_name,
                                        "question": question,
                                        "context": feedback,
                                        "suggested_answers": []
                                    })

                    processed_reqs.append({
                        "id": req_id,
                        "original_text": req_text,
                        "score": score,
                        "verdict": verdict,
                        "evaluation": evaluation,
                        "gaps": gaps,
                        "questions": questions
                    })

                    if session_id:
                        validation_stream_service.send_event(
                            session_id, "requirement_scored",
                            {"req_id": req_id, "score": score, "verdict": verdict}
                        )

                    if questions:
                        all_questions.append({
                            "req_id": req_id,
                            "questions": questions,
                            "current_text": req_text,
                            "gaps": gaps
                        })
                        if session_id:
                            validation_stream_service.send_event(
                                session_id, "question_generated",
                                {"req_id": req_id, "questions": questions, "gaps": gaps, "current_score": score}
                            )

                except Exception as e:
                    lg.error(f"Error evaluating {req_id}: {e}")
                    processed_reqs.append({
                        "id": req_id, "original_text": req_text, "score": 0,
                        "verdict": "error", "error": str(e), "gaps": [], "questions": []
                    })

            # Calculate stats
            passed = sum(1 for r in processed_reqs if r.get("verdict") == "pass")
            failed = len(processed_reqs) - passed
            avg_score = sum(r.get("score", 0) for r in processed_reqs) / len(processed_reqs) if processed_reqs else 0
            total_time = int((time.time() - start_time) * 1000)

            if session_id:
                validation_stream_service.send_event(
                    session_id, "pipeline_complete",
                    {
                        "mode": "guided",
                        "stage": "awaiting_answers" if all_questions else "complete",
                        "passed": passed, "failed": failed,
                        "questions_count": len(all_questions),
                        "total_questions": sum(len(q.get("questions", [])) for q in all_questions)
                    }
                )

            return AllInOneValidationResult(
                success=True,
                mode="guided",
                session_id=session_id,
                stage="awaiting_answers" if all_questions else "complete",
                total_processed=len(processed_reqs),
                passed_count=passed,
                failed_count=failed,
                improved_count=0,
                average_score=round(avg_score, 3),
                total_time_ms=total_time,
                requirements=processed_reqs,
                pending_questions=all_questions if all_questions else None,
                error=None
            )


    except Exception as e:
        lg.error(f"validate_all_in_one error: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )


@router.post("/api/v1/validate/all-in-one/apply-answers")
async def apply_answers_all_in_one(request: Request):
    """
    Apply user answers from guided mode and re-validate requirements.

    Request Body:
    {
        "session_id": "session-xxx",
        "answers": [
            {
                "req_id": "REQ-001",
                "original_text": "Das System soll schnell sein",
                "answered_questions": [
                    {"question": "...", "answer": "5 Sekunden"}
                ]
            }
        ]
    }

    Response:
    Same as AllInOneValidationResult with updated scores after applying answers
    """
    lg = logging.getLogger("app")

    try:
        payload = await _read_json_tolerant(request)

        session_id = payload.get("session_id")
        answers = payload.get("answers", [])

        if not answers:
            return JSONResponse(
                content={"error": "invalid_request", "message": "answers array is required"},
                status_code=400
            )

        try:
            from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
            from backend.services.validation_stream_service import validation_stream_service
        except ImportError as e:
            lg.error(f"Import error: {e}")
            return JSONResponse(
                content={"error": "import_error", "message": f"Failed to import services: {str(e)}"},
                status_code=500
            )

        if session_id:
            validation_stream_service.send_event(session_id, "stage_change", {"stage": "applying_answers"})

        enhancement_service = get_enhancement_service()

        # Apply answers and enhance
        result = await enhancement_service.apply_answers_and_enhance(
            answers=answers,
            quality_threshold=0.7
        )

        # Send enhancement events
        for req_result in (result.requirements or []):
            if session_id:
                validation_stream_service.send_event(
                    session_id,
                    "enhancement_applied",
                    {
                        "req_id": req_result.get("id"),
                        "old_score": req_result.get("original_score", 0),
                        "new_score": req_result.get("score", 0),
                        "enhanced_text": req_result.get("enhanced_text")
                    }
                )

        if session_id:
            validation_stream_service.send_event(
                session_id,
                "pipeline_complete",
                {
                    "mode": "guided",
                    "stage": "complete",
                    "passed": result.passed_count,
                    "failed": result.failed_count,
                    "improved": result.improved_count
                }
            )

        return {
            "success": result.success,
            "mode": "guided",
            "session_id": session_id,
            "stage": "complete",
            "total_processed": result.total_processed,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "improved_count": result.improved_count,
            "average_score": result.average_score,
            "total_time_ms": result.total_time_ms,
            "requirements": result.requirements or [],
            "error": result.error
        }

    except Exception as e:
        lg.error(f"apply_answers_all_in_one error: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "internal_error", "message": str(e)},
            status_code=500
        )