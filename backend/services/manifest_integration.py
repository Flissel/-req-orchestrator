# -*- coding: utf-8 -*-
"""
Manifest Integration Helpers

Purpose:
- Bridge ChunkMiner output → Manifest creation
- Bridge validation pipeline → Manifest stage tracking
- Bridge AtomicityAgent → Manifest split recording

Design:
- Standalone functions (no dependencies on specific services)
- Can be called from ChunkMiner, validation pipeline, or agents
- Uses ManifestService for all database operations
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from backend.core import db as _db
from .manifest_service import ManifestService
from .ports import RequestContext


def create_manifests_from_chunkminer(
    conn: sqlite3.Connection,
    mined_items: List[Dict[str, Any]],
    *,
    ctx: Optional[RequestContext] = None,
) -> List[str]:
    """
    Create manifests from ChunkMiner output.

    Args:
        conn: SQLite connection
        mined_items: List of ChunkMiner DTOs with format:
            {
              "req_id": "REQ-<sha1[:6]>-<chunkIndex:03d>",
              "title": "Requirement text",
              "tag": "functional|security|performance|ux|ops",
              "evidence_refs": [{"sourceFile": "...", "sha1": "...", "chunkIndex": 0}]
            }
        ctx: Request context (optional)

    Returns:
        List of created requirement_ids

    Example:
        from arch_team.agents.chunk_miner import ChunkMinerAgent
        agent = ChunkMinerAgent()
        items = agent.mine_files_or_texts_collect(files)

        manifest_ids = create_manifests_from_chunkminer(conn, items)
    """
    service = ManifestService()
    created_ids: List[str] = []

    for item in mined_items:
        try:
            # Extract fields from ChunkMiner DTO
            requirement_id = item.get("req_id") or item.get("reqId") or ""
            requirement_text = item.get("title") or ""
            tag = item.get("tag") or "functional"
            evidence_refs = item.get("evidence_refs") or []

            if not requirement_id or not requirement_text:
                continue

            # Check if manifest already exists
            existing = _db.get_manifest_by_id(conn, requirement_id)
            if existing:
                # Skip if already exists (deduplication)
                continue

            # Extract source metadata from first evidence ref
            source_file = None
            source_file_sha1 = None
            chunk_index = None

            if evidence_refs and isinstance(evidence_refs, list) and len(evidence_refs) > 0:
                first_ev = evidence_refs[0]
                source_file = first_ev.get("sourceFile")
                source_file_sha1 = first_ev.get("sha1")
                chunk_index = first_ev.get("chunkIndex")

            # Create manifest
            manifest_id = service.create_manifest_with_evidence(
                conn,
                requirement_id=requirement_id,
                requirement_text=requirement_text,
                source_type="chunk_miner",
                source_file=source_file,
                source_file_sha1=source_file_sha1,
                chunk_index=chunk_index,
                metadata={"tag": tag},
                evidence_refs=evidence_refs,
                ctx=ctx,
            )

            # Add "mining" stage (completed)
            stage_id = service.start_stage(
                conn,
                requirement_id=manifest_id,
                stage_name="mining",
                model_used="gpt-4o-mini",  # ChunkMiner default model
                stage_metadata={"tag": tag, "from_chunkminer": True},
                ctx=ctx,
            )
            service.complete_stage(
                conn,
                stage_id=stage_id,
                status="completed",
                ctx=ctx,
            )

            created_ids.append(manifest_id)

        except Exception as e:
            # Log error but continue with next item
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create manifest for {item.get('req_id')}: {str(e)}")
            continue

    return created_ids


def start_evaluation_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    requirement_text: str,
    *,
    evaluation_id: Optional[str] = None,
    model_used: Optional[str] = None,
    ctx: Optional[RequestContext] = None,
) -> int:
    """
    Start evaluation stage for a requirement.

    This is called from the validation pipeline (backend/legacy/batch.py)
    before running llm_evaluate().

    Args:
        conn: SQLite connection
        requirement_id: Requirement ID (manifest must exist)
        requirement_text: Requirement text (for manifest creation if needed)
        evaluation_id: Link to evaluation table (optional)
        model_used: LLM model (optional)
        ctx: Request context (optional)

    Returns:
        stage_id
    """
    service = ManifestService()

    # Check if manifest exists, create if not
    manifest = _db.get_manifest_by_id(conn, requirement_id)
    if not manifest:
        # Create manifest from API source
        import hashlib
        checksum = hashlib.sha256(requirement_text.encode('utf-8')).hexdigest()
        requirement_id = f"REQ-{checksum[:6]}-api"

        service.create_manifest_with_evidence(
            conn,
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            source_type="api",
            ctx=ctx,
        )

    # Check if evaluation stage already exists
    if service.check_stage_exists(conn, requirement_id, "evaluation", ctx=ctx):
        # Get existing stage ID
        stages = _db.get_processing_stages(conn, requirement_id)
        for stage in stages:
            if stage["stage_name"] == "evaluation" and stage["status"] == "in_progress":
                return stage["id"]

    # Start evaluation stage
    stage_id = service.start_stage(
        conn,
        requirement_id=requirement_id,
        stage_name="evaluation",
        evaluation_id=evaluation_id,
        model_used=model_used,
        ctx=ctx,
    )

    return stage_id


def complete_evaluation_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    score: float,
    verdict: str,
    *,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    ctx: Optional[RequestContext] = None,
) -> None:
    """
    Complete evaluation stage with results.

    This is called from the validation pipeline after llm_evaluate() completes.

    Args:
        conn: SQLite connection
        stage_id: Processing stage ID
        score: Overall evaluation score
        verdict: pass|fail
        latency_ms: Processing time (optional)
        token_usage: Token usage stats (optional)
        ctx: Request context (optional)
    """
    service = ManifestService()

    service.complete_stage(
        conn,
        stage_id=stage_id,
        status="completed",
        score=score,
        verdict=verdict,
        latency_ms=latency_ms,
        token_usage=token_usage,
        ctx=ctx,
    )


def start_atomicity_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    *,
    model_used: Optional[str] = None,
    ctx: Optional[RequestContext] = None,
) -> Optional[int]:
    """
    Start atomicity stage for a requirement (conditional).

    Returns None if atomicity stage already exists (prevents redundant LLM calls).
    Returns stage_id if started.

    Args:
        conn: SQLite connection
        requirement_id: Requirement ID
        model_used: LLM model (optional)
        ctx: Request context (optional)

    Returns:
        stage_id or None
    """
    service = ManifestService()

    # **CRITICAL**: Check if atomicity stage already exists
    if service.check_stage_exists(conn, requirement_id, "atomicity", ctx=ctx):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Atomicity stage already exists for {requirement_id}, skipping")
        return None

    # Start atomicity stage
    stage_id = service.start_stage(
        conn,
        requirement_id=requirement_id,
        stage_name="atomicity",
        model_used=model_used,
        ctx=ctx,
    )

    return stage_id


def complete_atomicity_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    atomic_score: float,
    is_atomic: bool,
    *,
    was_split: bool = False,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    ctx: Optional[RequestContext] = None,
) -> None:
    """
    Complete atomicity stage with results.

    Args:
        conn: SQLite connection
        stage_id: Processing stage ID
        atomic_score: Atomic criterion score (0.0-1.0)
        is_atomic: True if atomic_score >= 0.7
        was_split: True if requirement was split
        latency_ms: Processing time (optional)
        token_usage: Token usage stats (optional)
        ctx: Request context (optional)
    """
    service = ManifestService()

    service.complete_stage(
        conn,
        stage_id=stage_id,
        status="completed",
        atomic_score=atomic_score,
        verdict="pass" if is_atomic else "fail",
        was_split=was_split,
        latency_ms=latency_ms,
        token_usage=token_usage,
        stage_metadata={"is_atomic": is_atomic},
        ctx=ctx,
    )


def record_atomicity_split(
    conn: sqlite3.Connection,
    parent_id: str,
    splits: List[Dict[str, str]],
    *,
    split_model: Optional[str] = None,
    ctx: Optional[RequestContext] = None,
) -> List[str]:
    """
    Record requirement split from AtomicityAgent.

    Args:
        conn: SQLite connection
        parent_id: Parent requirement ID
        splits: List of {text: "...", rationale: "..."}
        split_model: Model used for splitting (optional)
        ctx: Request context (optional)

    Returns:
        List of child requirement IDs
    """
    service = ManifestService()
    child_ids: List[str] = []

    for i, split in enumerate(splits):
        try:
            child_id = f"{parent_id}-split-{i:02d}"
            child_text = split.get("text") or ""
            split_rationale = split.get("rationale") or "Atomicity split"

            if not child_text:
                continue

            # Record split (creates child manifest)
            service.record_split(
                conn,
                parent_id=parent_id,
                child_id=child_id,
                child_text=child_text,
                split_rationale=split_rationale,
                split_model=split_model,
                ctx=ctx,
            )

            child_ids.append(child_id)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to record split {i} for {parent_id}: {str(e)}")
            continue

    return child_ids


def start_suggestion_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    *,
    model_used: Optional[str] = None,
    ctx: Optional[RequestContext] = None,
) -> int:
    """
    Start suggestion stage for a requirement.

    Args:
        conn: SQLite connection
        requirement_id: Requirement ID
        model_used: LLM model (optional)
        ctx: Request context (optional)

    Returns:
        stage_id
    """
    service = ManifestService()

    stage_id = service.start_stage(
        conn,
        requirement_id=requirement_id,
        stage_name="suggestion",
        model_used=model_used,
        ctx=ctx,
    )

    return stage_id


def complete_suggestion_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    suggestion_count: int,
    *,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    ctx: Optional[RequestContext] = None,
) -> None:
    """
    Complete suggestion stage with results.

    Args:
        conn: SQLite connection
        stage_id: Processing stage ID
        suggestion_count: Number of suggestions generated
        latency_ms: Processing time (optional)
        token_usage: Token usage stats (optional)
        ctx: Request context (optional)
    """
    service = ManifestService()

    service.complete_stage(
        conn,
        stage_id=stage_id,
        status="completed",
        latency_ms=latency_ms,
        token_usage=token_usage,
        stage_metadata={"suggestion_count": suggestion_count},
        ctx=ctx,
    )


def start_rewrite_stage(
    conn: sqlite3.Connection,
    requirement_id: str,
    *,
    model_used: Optional[str] = None,
    ctx: Optional[RequestContext] = None,
) -> int:
    """
    Start rewrite stage for a requirement.

    Args:
        conn: SQLite connection
        requirement_id: Requirement ID
        model_used: LLM model (optional)
        ctx: Request context (optional)

    Returns:
        stage_id
    """
    service = ManifestService()

    stage_id = service.start_stage(
        conn,
        requirement_id=requirement_id,
        stage_name="rewrite",
        model_used=model_used,
        ctx=ctx,
    )

    return stage_id


def complete_rewrite_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    rewritten_text: str,
    *,
    latency_ms: Optional[int] = None,
    token_usage: Optional[Dict[str, int]] = None,
    ctx: Optional[RequestContext] = None,
) -> None:
    """
    Complete rewrite stage and update manifest text.

    Args:
        conn: SQLite connection
        stage_id: Processing stage ID
        rewritten_text: New requirement text
        latency_ms: Processing time (optional)
        token_usage: Token usage stats (optional)
        ctx: Request context (optional)
    """
    service = ManifestService()

    # Complete stage
    service.complete_stage(
        conn,
        stage_id=stage_id,
        status="completed",
        latency_ms=latency_ms,
        token_usage=token_usage,
        ctx=ctx,
    )

    # Update manifest text
    # Get requirement_id from stage
    stage_row = conn.execute(
        "SELECT requirement_id FROM processing_stage WHERE id = ?",
        (stage_id,)
    ).fetchone()

    if stage_row:
        requirement_id = stage_row["requirement_id"]
        service.update_text(conn, requirement_id, rewritten_text, ctx=ctx)
