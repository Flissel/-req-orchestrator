# -*- coding: utf-8 -*-
"""
Batch processing functions for requirements evaluation, suggestions, and rewrites.

Migrated from backend.legacy.batch — Flask-free, pure business logic.
"""
from __future__ import annotations

import time
import json
import logging
import concurrent.futures as futures
from typing import Any, Dict, List, Tuple

from backend.core.logging_ext import _json_log as json_log
from backend.core import settings
from backend.core.db import (
    get_db,
    load_criteria,
    get_latest_evaluation_by_checksum,
    get_suggestions_for_eval,
    get_latest_rewrite_for_eval,
)
from backend.core.llm import llm_evaluate, llm_suggest, llm_rewrite
from backend.core.utils import parse_context_cell, parse_requirements_md, sha256_text, weighted_score, compute_verdict, chunked

from backend.services.manifest_integration import (
    start_evaluation_stage,
    complete_evaluation_stage,
    start_atomicity_stage,
    complete_atomicity_stage,
    record_atomicity_split,
)


def ensure_evaluation_exists(
    requirement_text: str, context: Dict[str, Any], criteria_keys: List[str]
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (evaluation_id, summary). Creates a new evaluation if none exists.
    summary = {"score": float, "verdict": str, "model": str, "latencyMs": int}
    """
    conn = get_db()
    checksum = sha256_text(requirement_text)
    row = get_latest_evaluation_by_checksum(conn, checksum)
    if row:
        return row["id"], {
            "score": row["score"],
            "verdict": row["verdict"],
            "model": row["model"],
            "latencyMs": row["latency_ms"],
        }

    requirement_id = f"REQ-{checksum[:6]}-api"

    stage_id = None
    try:
        stage_id = start_evaluation_stage(
            conn=conn,
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            evaluation_id=None,
            model_used=settings.OPENAI_MODEL,
            ctx=None,
        )
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to start evaluation stage: {e}")

    ts = time.time()
    details = llm_evaluate(requirement_text, criteria_keys, context)
    crits = load_criteria(conn, criteria_keys)
    agg_score = weighted_score(details, crits)
    verdict = compute_verdict(agg_score, settings.VERDICT_THRESHOLD)
    latency_ms = int((time.time() - ts) * 1000)
    eval_id = f"ev_{int(time.time())}_{checksum[:8]}"

    with conn:
        conn.execute(
            "INSERT INTO evaluation(id, requirement_checksum, model, latency_ms, score, verdict) VALUES (?, ?, ?, ?, ?, ?)",
            (eval_id, checksum, settings.OPENAI_MODEL, latency_ms, agg_score, verdict),
        )
        for d in details:
            conn.execute(
                "INSERT INTO evaluation_detail(evaluation_id, criterion_key, score, passed, feedback) VALUES (?, ?, ?, ?, ?)",
                (eval_id, d["criterion"], float(d["score"]), 1 if d["passed"] else 0, d.get("feedback", "")),
            )

    if stage_id is not None:
        try:
            complete_evaluation_stage(
                conn=conn,
                stage_id=stage_id,
                score=agg_score,
                verdict=verdict,
                latency_ms=latency_ms,
                token_usage=None,
                ctx=None,
            )
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to complete evaluation stage: {e}")

    # Conditional atomicity check
    atomic_detail = next((d for d in details if d["criterion"] == "atomic"), None)
    if atomic_detail:
        atomic_score = atomic_detail.get("score", 1.0)
        if atomic_score < 0.7:
            try:
                atomicity_stage_id = start_atomicity_stage(
                    conn,
                    requirement_id=requirement_id,
                    model_used=settings.OPENAI_MODEL,
                    ctx=None,
                )
                if atomicity_stage_id is not None:
                    try:
                        from backend.core.agents import RequirementsAtomicityAgent
                        import asyncio

                        agent = RequirementsAtomicityAgent()
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            splits = loop.run_until_complete(
                                agent._split_with_retry(requirement_text, context, max_splits=5)
                            )
                        finally:
                            loop.close()

                        complete_atomicity_stage(
                            conn,
                            stage_id=atomicity_stage_id,
                            atomic_score=atomic_score,
                            is_atomic=False,
                            was_split=bool(splits),
                            ctx=None,
                        )
                        if splits:
                            child_ids = record_atomicity_split(
                                conn,
                                parent_id=requirement_id,
                                splits=splits,
                                split_model=settings.OPENAI_MODEL,
                                ctx=None,
                            )
                            logging.getLogger(__name__).info(
                                f"Atomicity: Split {requirement_id} into {len(child_ids)} children"
                            )
                    except Exception as split_error:
                        conn.execute(
                            "UPDATE processing_stage SET status = 'failed', error_message = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (str(split_error), atomicity_stage_id),
                        )
                        logging.getLogger(__name__).warning(f"Atomicity split failed: {split_error}")
                else:
                    logging.getLogger(__name__).info(
                        f"Atomicity stage already exists for {requirement_id}, skipping"
                    )
            except Exception as e:
                logging.getLogger(__name__).warning(f"Atomicity check failed: {e}")

    return eval_id, {"score": agg_score, "verdict": verdict, "model": settings.OPENAI_MODEL, "latencyMs": latency_ms}


def merged_markdown(rows: List[Dict[str, str]]) -> str:
    """Build merged markdown table with evaluation columns."""
    conn = get_db()
    out = []
    header = "| id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement |"
    sep = "|----|------------------|---------|-----------------|--------|-------------|----------------------|"
    out.append(header)
    out.append(sep)
    for r in rows:
        rid = r["id"]
        req = r["requirementText"]
        ctx_raw = r.get("context", "")
        checksum = sha256_text(req)
        ev = get_latest_evaluation_by_checksum(conn, checksum)
        score = f"{(ev['score'] if ev and ev['score'] is not None else '')}"
        verdict = f"{(ev['verdict'] if ev else '')}"
        sugg_cell = ""
        rewrite_cell = ""
        if ev:
            sugg = get_suggestions_for_eval(conn, ev["id"])
            if sugg:
                sugg_cell = "; ".join([f"{s['text']} ({s['priority']})" for s in sugg])
            rw = get_latest_rewrite_for_eval(conn, ev["id"])
            if rw:
                rewrite_cell = rw.replace("\n", "<br>")

        def safe(s: str) -> str:
            return (s or "").replace("|", "\\|")

        out.append(f"| {safe(rid)} | {safe(req)} | {safe(ctx_raw)} | {safe(score)} | {safe(verdict)} | {safe(sugg_cell)} | {safe(rewrite_cell)} |")
    return "\n".join(out)


def process_evaluations(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Evaluate a batch of requirements in parallel."""
    lg = logging.getLogger("app")
    total = len(rows)
    batch_size = settings.BATCH_SIZE
    total_chunks = (total + batch_size - 1) // batch_size
    conn = get_db()
    crits = load_criteria(conn)
    criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

    def worker(row: Dict[str, str]) -> Tuple[str, Dict[str, Any]]:
        rid = row["id"]
        requirement_text = row["requirementText"]
        context = parse_context_cell(row.get("context", ""))
        eval_id, summ = ensure_evaluation_exists(requirement_text, context, criteria_keys)
        return rid, {"evaluationId": eval_id, **summ}

    results: Dict[str, Any] = {}
    for idx_batch, batch in enumerate(chunked(rows, settings.BATCH_SIZE), start=1):
        json_log(
            lg, logging.DEBUG, "batch.chunk.start",
            kind="evaluate", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch),
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                kind="evaluate", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch),
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                rid, data = fut.result()
                results[rid] = data
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                kind="evaluate", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000),
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            kind="evaluate", chunk_index=idx_batch, processed_count=processed,
        )
    return results


def process_suggestions(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Generate suggestions for a batch of requirements in parallel."""
    lg = logging.getLogger("app")
    total = len(rows)
    batch_size = settings.BATCH_SIZE
    total_chunks = (total + batch_size - 1) // batch_size
    conn = get_db()
    crits = load_criteria(conn)
    criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

    def worker(row: Dict[str, str]) -> Tuple[str, str, List[Dict[str, Any]]]:
        rid = row["id"]
        requirement_text = row["requirementText"]
        context = parse_context_cell(row.get("context", ""))
        eval_id, _ = ensure_evaluation_exists(requirement_text, context, criteria_keys)
        atoms = llm_suggest(requirement_text, context)
        return rid, eval_id, atoms

    collected: List[Tuple[str, str, List[Dict[str, Any]]]] = []
    for idx_batch, batch in enumerate(chunked(rows, settings.BATCH_SIZE), start=1):
        json_log(
            lg, logging.DEBUG, "batch.chunk.start",
            kind="suggest", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch),
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                kind="suggest", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch),
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                collected.append(fut.result())
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                kind="suggest", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000),
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            kind="suggest", chunk_index=idx_batch, processed_count=processed,
        )

    with get_db() as c2:
        for rid, eval_id, atoms in collected:
            for atom in atoms:
                c2.execute(
                    "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                    (eval_id, json.dumps(atom, ensure_ascii=False), "atom"),
                )

    results: Dict[str, Any] = {}
    for rid, _, atoms in collected:
        results[rid] = {"suggestions": atoms}
    return results


def process_rewrites(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Rewrite a batch of requirements in parallel."""
    conn = get_db()
    crits = load_criteria(conn)
    criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

    def worker(row: Dict[str, str]) -> Tuple[str, str, str]:
        rid = row["id"]
        requirement_text = row["requirementText"]
        context = parse_context_cell(row.get("context", ""))
        eval_id, _ = ensure_evaluation_exists(requirement_text, context, criteria_keys)
        rewritten = llm_rewrite(requirement_text, context)
        return rid, eval_id, rewritten

    collected: List[Tuple[str, str, str]] = []
    lg = logging.getLogger("app")
    total = len(rows)
    batch_size = settings.BATCH_SIZE
    total_chunks = (total + batch_size - 1) // batch_size

    for idx_batch, batch in enumerate(chunked(rows, settings.BATCH_SIZE), start=1):
        json_log(
            lg, logging.DEBUG, "batch.chunk.start",
            kind="rewrite", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch),
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                kind="rewrite", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch),
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                collected.append(fut.result())
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                kind="rewrite", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000),
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            kind="rewrite", chunk_index=idx_batch, processed_count=processed,
        )

    with get_db() as c2:
        for rid, eval_id, rewritten in collected:
            c2.execute(
                "INSERT INTO rewritten_requirement(evaluation_id, text) VALUES (?, ?)",
                (eval_id, rewritten),
            )

    results: Dict[str, Any] = {}
    for rid, eval_id, rewritten in collected:
        results[rid] = {"redefinedRequirement": rewritten}
    return results
