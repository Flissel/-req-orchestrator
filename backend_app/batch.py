# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import json
import logging
from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, g
from .logging_ext import _json_log as json_log

from . import settings
from .db import (
    get_db,
    load_criteria,
    get_latest_evaluation_by_checksum,
    get_suggestions_for_eval,
    get_latest_rewrite_for_eval,
)
from .llm import llm_evaluate, llm_suggest, llm_rewrite
from .utils import parse_context_cell, parse_requirements_md, sha256_text, weighted_score, compute_verdict, chunked

import concurrent.futures as futures

batch_bp = Blueprint("batch", __name__)


def ensure_evaluation_exists(requirement_text: str, context: Dict[str, Any], criteria_keys: List[str]) -> Tuple[str, Dict[str, Any]]:
    """
    Liefert (evaluation_id, summary). Falls noch keine Evaluation existiert, wird sie erzeugt.
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

    return eval_id, {"score": agg_score, "verdict": verdict, "model": settings.OPENAI_MODEL, "latencyMs": latency_ms}


def merged_markdown(rows: List[Dict[str, str]]) -> str:
    """
    Baut die zusammengeführte Markdown-Tabelle mit zusätzlichen Spalten:
    [evaluationScore, verdict, suggestions, redefinedRequirement]
    """
    conn = get_db()
    out = []
    header = "| id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement |"
    sep =    "|----|------------------|---------|-----------------|--------|-------------|----------------------|"
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
    lg = logging.getLogger("app")
    corr = getattr(g, "correlation_id", None)
    op = getattr(g, "operation_id", None) or "process_evaluations"
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
            correlation_id=corr, operation_id=op,
            kind="evaluate", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch)
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                correlation_id=corr, operation_id=op,
                kind="evaluate", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch)
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                rid, data = fut.result()
                results[rid] = data
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                correlation_id=corr, operation_id=op,
                kind="evaluate", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000)
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            correlation_id=corr, operation_id=op,
            kind="evaluate", chunk_index=idx_batch, processed_count=processed
        )
    return results


def process_suggestions(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    lg = logging.getLogger("app")
    corr = getattr(g, "correlation_id", None)
    op = getattr(g, "operation_id", None) or "process_suggestions"
    total = len(rows)
    batch_size = settings.BATCH_SIZE
    total_chunks = (total + batch_size - 1) // batch_size
    conn = get_db()
    crits = load_criteria(conn)
    criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

    # Worker macht nur LLM-Aufruf, Speichern erfolgt sequenziell
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
            correlation_id=corr, operation_id=op,
            kind="suggest", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch)
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                correlation_id=corr, operation_id=op,
                kind="suggest", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch)
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                collected.append(fut.result())
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                correlation_id=corr, operation_id=op,
                kind="suggest", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000)
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            correlation_id=corr, operation_id=op,
            kind="suggest", chunk_index=idx_batch, processed_count=processed
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
    conn = get_db()
    crits = load_criteria(conn)
    criteria_keys = [c["key"] for c in crits] or ["clarity", "testability", "measurability"]

    # Worker macht nur LLM-Aufruf, Speichern erfolgt sequenziell
    def worker(row: Dict[str, str]) -> Tuple[str, str, str]:
        rid = row["id"]
        requirement_text = row["requirementText"]
        context = parse_context_cell(row.get("context", ""))
        eval_id, _ = ensure_evaluation_exists(requirement_text, context, criteria_keys)
        rewritten = llm_rewrite(requirement_text, context)
        return rid, eval_id, rewritten

    collected: List[Tuple[str, str, str]] = []
    lg = logging.getLogger("app")
    corr = getattr(g, "correlation_id", None)
    op = getattr(g, "operation_id", None) or "process_rewrites"
    total = len(rows)
    batch_size = settings.BATCH_SIZE
    total_chunks = (total + batch_size - 1) // batch_size

    for idx_batch, batch in enumerate(chunked(rows, settings.BATCH_SIZE), start=1):
        json_log(
            lg, logging.DEBUG, "batch.chunk.start",
            correlation_id=corr, operation_id=op,
            kind="rewrite", chunk_index=idx_batch, total_chunks=total_chunks, chunk_size=len(batch)
        )
        ts_pool = time.time()
        with futures.ThreadPoolExecutor(max_workers=settings.MAX_PARALLEL) as ex:
            json_log(
                lg, logging.DEBUG, "parallel.pool.start",
                correlation_id=corr, operation_id=op,
                kind="rewrite", pool_size=settings.MAX_PARALLEL, queue_depth=len(batch)
            )
            futs = [ex.submit(worker, r) for r in batch]
            processed = 0
            for fut in futures.as_completed(futs):
                collected.append(fut.result())
                processed += 1
            json_log(
                lg, logging.DEBUG, "parallel.pool.end",
                correlation_id=corr, operation_id=op,
                kind="rewrite", processed_count=processed,
                duration_ms=int((time.time() - ts_pool) * 1000)
            )
        json_log(
            lg, logging.DEBUG, "batch.chunk.end",
            correlation_id=corr, operation_id=op,
            kind="rewrite", chunk_index=idx_batch, processed_count=processed
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


@batch_bp.post("/api/v1/batch/evaluate")
def batch_evaluate():
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        eval_map = process_evaluations(rows)
        merged = merged_markdown(rows)
        # Optional: Ergebnis serverseitig schreiben, wenn OUTPUT_MD_PATH gesetzt ist
        try:
            out_path = getattr(settings, "OUTPUT_MD_PATH", "")
            if isinstance(out_path, str) and out_path.strip():
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(merged)
        except Exception:
            pass
        return jsonify({"items": eval_map, "mergedMarkdown": merged}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@batch_bp.post("/api/v1/batch/suggest")
def batch_suggest():
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        sug_map = process_suggestions(rows)
        merged = merged_markdown(rows)
        try:
            out_path = getattr(settings, "OUTPUT_MD_PATH", "")
            if isinstance(out_path, str) and out_path.strip():
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(merged)
        except Exception:
            pass
        return jsonify({"items": sug_map, "mergedMarkdown": merged}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@batch_bp.post("/api/v1/batch/rewrite")
def batch_rewrite():
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        rw_map = process_rewrites(rows)
        merged = merged_markdown(rows)
        try:
            out_path = getattr(settings, "OUTPUT_MD_PATH", "")
            if isinstance(out_path, str) and out_path.strip():
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(merged)
        except Exception:
            pass
        return jsonify({"items": rw_map, "mergedMarkdown": merged}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500