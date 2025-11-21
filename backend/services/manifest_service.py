# -*- coding: utf-8 -*-
"""
ManifestService (framework-free, DI-ready)

Purpose:
- Encapsulates all manifest lifecycle tracking logic
- Provides high-level operations for creating, updating, and querying requirement manifests
- Integrates with database helper functions from backend.core.db

Design Patterns:
- Port/Adapter pattern for database access
- Stable requirement IDs: REQ-{sha1[:6]}-{chunk:03d}
- Full provenance tracking (source → mining → processing → final)
- Conditional processing (check before adding stages)

Operations:
- create_manifest_with_evidence() - Create manifest + evidence refs
- update_stage() - Add/complete processing stages
- record_split() - Track AtomicityAgent splits
- get_full_manifest() - Retrieve complete manifest with relationships
- get_timeline() - Get processing history
- get_children() - Get split children
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from backend.core import db as _db
from backend.schemas import (
    RequirementManifest,
    ProcessingStage,
    EvidenceReference,
    SplitRelationship,
    ManifestTimelineResponse,
    ManifestChildrenResponse,
)
from .ports import RequestContext, ServiceError


def sha256_text(text: str) -> str:
    """Generate SHA256 checksum for requirement text"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ManifestService:
    """
    ManifestService - Requirement Lifecycle Tracking

    Provides high-level operations for manifest creation, updates, and queries.
    Integrates with SQLite database via backend.core.db helper functions.

    Dependencies:
    - SQLite connection (passed to methods, not stored)
    - backend.core.db helper functions for CRUD operations

    Usage:
        service = ManifestService()

        # Create manifest from ChunkMiner
        manifest_id = service.create_manifest_with_evidence(
            conn,
            requirement_id="REQ-a3f2b1-001",
            requirement_text="System must be fast",
            source_type="chunk_miner",
            source_file="requirements.md",
            source_file_sha1="abc123...",
            chunk_index=0,
            evidence_refs=[{
                "sourceFile": "requirements.md",
                "sha1": "abc123...",
                "chunkIndex": 0
            }]
        )

        # Add processing stage
        stage_id = service.start_stage(
            conn,
            requirement_id="REQ-a3f2b1-001",
            stage_name="evaluation"
        )

        # Complete stage
        service.complete_stage(
            conn,
            stage_id=stage_id,
            status="completed",
            score=0.85,
            verdict="pass"
        )
    """

    def __init__(self) -> None:
        """Initialize ManifestService (no stored state)"""
        pass

    # -----------------------
    # Manifest Creation
    # -----------------------

    def create_manifest_with_evidence(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        requirement_text: str,
        source_type: str,
        *,
        source_file: Optional[str] = None,
        source_file_sha1: Optional[str] = None,
        chunk_index: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        evidence_refs: Optional[Sequence[Dict[str, Any]]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> str:
        """
        Create a new requirement manifest with evidence references.

        Args:
            conn: SQLite connection
            requirement_id: Stable ID (REQ-{sha1[:6]}-{chunk:03d})
            requirement_text: Initial requirement text
            source_type: upload|manual|chunk_miner|api
            source_file: Original filename (optional)
            source_file_sha1: Document SHA1 hash (optional)
            chunk_index: Position in chunked document (optional)
            metadata: Additional metadata (optional)
            evidence_refs: List of evidence references [{sourceFile, sha1, chunkIndex, isNeighbor?}]
            ctx: Request context (optional)

        Returns:
            requirement_id

        Raises:
            ServiceError if creation fails
        """
        try:
            # Generate checksum
            checksum = sha256_text(requirement_text)

            # Create manifest
            _db.create_manifest(
                conn,
                requirement_id=requirement_id,
                requirement_text=requirement_text,
                checksum=checksum,
                source_type=source_type,
                source_file=source_file,
                source_file_sha1=source_file_sha1,
                chunk_index=chunk_index,
                metadata=metadata,
            )

            # Add evidence references
            if evidence_refs:
                for evidence in evidence_refs:
                    _db.add_evidence_reference(
                        conn,
                        requirement_id=requirement_id,
                        source_file=evidence.get("sourceFile"),
                        sha1=evidence.get("sha1"),
                        chunk_index=evidence.get("chunkIndex"),
                        is_neighbor=evidence.get("isNeighbor", False),
                        evidence_metadata=evidence.get("metadata"),
                    )

            # Add initial "input" stage
            _db.add_processing_stage(
                conn,
                requirement_id=requirement_id,
                stage_name="input",
                status="completed",
                stage_metadata={"created_by": "ManifestService"},
            )
            _db.complete_processing_stage(
                conn,
                stage_id=conn.execute(
                    "SELECT id FROM processing_stage WHERE requirement_id = ? ORDER BY id DESC LIMIT 1",
                    (requirement_id,)
                ).fetchone()[0],
                status="completed",
            )

            # Update manifest current_stage
            _db.update_manifest_stage(conn, requirement_id, "input")

            conn.commit()
            return requirement_id

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "manifest_creation_failed",
                f"Failed to create manifest: {str(e)}",
                details={"requirement_id": requirement_id, "request_id": getattr(ctx, "request_id", None)}
            ) from e

    # -----------------------
    # Stage Management
    # -----------------------

    def start_stage(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        stage_name: str,
        *,
        evaluation_id: Optional[str] = None,
        model_used: Optional[str] = None,
        stage_metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> int:
        """
        Start a new processing stage (sets status=in_progress).

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            stage_name: input|mining|evaluation|atomicity|suggestion|rewrite|validation|completed|failed
            evaluation_id: Link to evaluation table (optional)
            model_used: LLM model (optional)
            stage_metadata: Additional metadata (optional)
            ctx: Request context (optional)

        Returns:
            stage_id (auto-incremented ID from processing_stage table)

        Raises:
            ServiceError if stage creation fails
        """
        try:
            # Add processing stage
            _db.add_processing_stage(
                conn,
                requirement_id=requirement_id,
                stage_name=stage_name,
                status="in_progress",
                evaluation_id=evaluation_id,
                model_used=model_used,
                stage_metadata=stage_metadata,
            )

            # Get stage ID
            stage_id = conn.execute(
                "SELECT id FROM processing_stage WHERE requirement_id = ? ORDER BY id DESC LIMIT 1",
                (requirement_id,)
            ).fetchone()[0]

            # Update manifest current_stage
            _db.update_manifest_stage(conn, requirement_id, stage_name)

            conn.commit()
            return stage_id

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "stage_start_failed",
                f"Failed to start stage: {str(e)}",
                details={"requirement_id": requirement_id, "stage_name": stage_name, "request_id": getattr(ctx, "request_id", None)}
            ) from e

    def complete_stage(
        self,
        conn: sqlite3.Connection,
        stage_id: int,
        status: str,
        *,
        score: Optional[float] = None,
        verdict: Optional[str] = None,
        atomic_score: Optional[float] = None,
        was_split: bool = False,
        latency_ms: Optional[int] = None,
        token_usage: Optional[Dict[str, int]] = None,
        error_message: Optional[str] = None,
        stage_metadata: Optional[Dict[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> None:
        """
        Complete a processing stage (sets status=completed|failed and completed_at timestamp).

        Args:
            conn: SQLite connection
            stage_id: Processing stage ID
            status: completed|failed
            score: Overall score (optional)
            verdict: pass|fail (optional)
            atomic_score: Atomic criterion score (optional, for atomicity stage)
            was_split: Flag indicating requirement was split (optional)
            latency_ms: Processing time in milliseconds (optional)
            token_usage: {prompt_tokens, completion_tokens, total_tokens} (optional)
            error_message: Error details if status=failed (optional)
            stage_metadata: Additional metadata to merge (optional)
            ctx: Request context (optional)

        Raises:
            ServiceError if completion fails
        """
        try:
            # Get existing stage_metadata
            existing_metadata = {}
            row = conn.execute(
                "SELECT stage_metadata FROM processing_stage WHERE id = ?",
                (stage_id,)
            ).fetchone()
            if row and row[0]:
                import json
                existing_metadata = json.loads(row[0])

            # Merge metadata
            merged_metadata = {**existing_metadata, **(stage_metadata or {})}

            # Complete stage
            _db.complete_processing_stage(
                conn,
                stage_id=stage_id,
                status=status,
                score=score,
                verdict=verdict,
                atomic_score=atomic_score,
                was_split=1 if was_split else 0,
                latency_ms=latency_ms,
                token_usage=token_usage,
                error_message=error_message,
                stage_metadata=merged_metadata,
            )

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "stage_completion_failed",
                f"Failed to complete stage: {str(e)}",
                details={"stage_id": stage_id, "status": status, "request_id": getattr(ctx, "request_id", None)}
            ) from e

    def check_stage_exists(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        stage_name: str,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> bool:
        """
        Check if a processing stage already exists for a requirement.

        This is critical for conditional processing (e.g., AtomicityAgent should only run
        if "atomicity" stage doesn't exist).

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            stage_name: Stage name to check
            ctx: Request context (optional)

        Returns:
            True if stage exists, False otherwise
        """
        stages = _db.get_processing_stages(conn, requirement_id)
        return any(s["stage_name"] == stage_name for s in stages)

    # -----------------------
    # Split Management
    # -----------------------

    def record_split(
        self,
        conn: sqlite3.Connection,
        parent_id: str,
        child_id: str,
        child_text: str,
        split_rationale: str,
        *,
        split_model: Optional[str] = None,
        ctx: Optional[RequestContext] = None,
    ) -> str:
        """
        Record a requirement split (parent → child) and create child manifest.

        Args:
            conn: SQLite connection
            parent_id: Parent requirement ID
            child_id: Child requirement ID
            child_text: Child requirement text
            split_rationale: Explanation for split
            split_model: Model used for splitting (optional)
            ctx: Request context (optional)

        Returns:
            child_id

        Raises:
            ServiceError if split recording fails
        """
        try:
            # Create child manifest
            checksum = sha256_text(child_text)
            _db.create_manifest(
                conn,
                requirement_id=child_id,
                requirement_text=child_text,
                checksum=checksum,
                source_type="atomic_split",
                metadata={"parent_id": parent_id, "split_rationale": split_rationale},
            )

            # Record split relationship
            _db.record_requirement_split(
                conn,
                parent_id=parent_id,
                child_id=child_id,
                split_rationale=split_rationale,
                split_model=split_model,
            )

            # Add "input" stage to child
            _db.add_processing_stage(
                conn,
                requirement_id=child_id,
                stage_name="input",
                status="completed",
                stage_metadata={"created_by": "AtomicityAgent", "parent_id": parent_id},
            )
            child_stage_id = conn.execute(
                "SELECT id FROM processing_stage WHERE requirement_id = ? ORDER BY id DESC LIMIT 1",
                (child_id,)
            ).fetchone()[0]
            _db.complete_processing_stage(conn, child_stage_id, "completed")

            # Update child manifest current_stage
            _db.update_manifest_stage(conn, child_id, "input")

            conn.commit()
            return child_id

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "split_recording_failed",
                f"Failed to record split: {str(e)}",
                details={"parent_id": parent_id, "child_id": child_id, "request_id": getattr(ctx, "request_id", None)}
            ) from e

    # -----------------------
    # Queries
    # -----------------------

    def get_full_manifest(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> Optional[RequirementManifest]:
        """
        Retrieve complete manifest with all relationships (stages, evidence, children).

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            ctx: Request context (optional)

        Returns:
            RequirementManifest with populated relationships, or None if not found
        """
        # Get manifest
        manifest_row = _db.get_manifest_by_id(conn, requirement_id)
        if not manifest_row:
            return None

        # Get processing stages
        stages = _db.get_processing_stages(conn, requirement_id)
        processing_stages = [
            ProcessingStage(
                id=s["id"],
                requirement_id=s["requirement_id"],
                stage_name=s["stage_name"],
                status=s["status"],
                started_at=s["started_at"],
                completed_at=s["completed_at"],
                evaluation_id=s["evaluation_id"],
                score=s["score"],
                verdict=s["verdict"],
                atomic_score=s["atomic_score"],
                was_split=bool(s["was_split"]),
                model_used=s["model_used"],
                latency_ms=s["latency_ms"],
                token_usage=json.loads(s["token_usage"]) if s["token_usage"] else {},
                error_message=s["error_message"],
                stage_metadata=json.loads(s["stage_metadata"]) if s["stage_metadata"] else {},
            )
            for s in stages
        ]

        # Get evidence references
        evidence = _db.get_evidence_refs(conn, requirement_id)
        evidence_refs = [
            EvidenceReference(
                source_file=e["source_file"],
                sha1=e["sha1"],
                chunk_index=e["chunk_index"],
                is_neighbor=bool(e["is_neighbor"]),
                evidence_metadata=json.loads(e["evidence_metadata"]) if e["evidence_metadata"] else {},
            )
            for e in evidence
        ]

        # Get split children
        children_rows = _db.get_split_children(conn, requirement_id)
        split_children = [c["child_id"] for c in children_rows]

        # Build manifest
        return RequirementManifest(
            requirement_id=manifest_row["requirement_id"],
            requirement_checksum=manifest_row["requirement_checksum"],
            source_type=manifest_row["source_type"],
            source_file=manifest_row["source_file"],
            source_file_sha1=manifest_row["source_file_sha1"],
            chunk_index=manifest_row["chunk_index"],
            original_text=manifest_row["original_text"],
            current_text=manifest_row["current_text"],
            current_stage=manifest_row["current_stage"],
            parent_id=manifest_row["parent_id"],
            created_at=manifest_row["created_at"],
            updated_at=manifest_row["updated_at"],
            metadata=json.loads(manifest_row["metadata"]) if manifest_row["metadata"] else {},
            processing_stages=processing_stages,
            evidence_refs=evidence_refs,
            split_children=split_children,
        )

    def get_timeline(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> ManifestTimelineResponse:
        """
        Get processing timeline for a requirement.

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            ctx: Request context (optional)

        Returns:
            ManifestTimelineResponse with chronological stages
        """
        stages = _db.get_processing_stages(conn, requirement_id)
        processing_stages = [
            ProcessingStage(
                id=s["id"],
                requirement_id=s["requirement_id"],
                stage_name=s["stage_name"],
                status=s["status"],
                started_at=s["started_at"],
                completed_at=s["completed_at"],
                evaluation_id=s["evaluation_id"],
                score=s["score"],
                verdict=s["verdict"],
                atomic_score=s["atomic_score"],
                was_split=bool(s["was_split"]),
                model_used=s["model_used"],
                latency_ms=s["latency_ms"],
                token_usage=json.loads(s["token_usage"]) if s["token_usage"] else {},
                error_message=s["error_message"],
                stage_metadata=json.loads(s["stage_metadata"]) if s["stage_metadata"] else {},
            )
            for s in stages
        ]

        return ManifestTimelineResponse(
            requirement_id=requirement_id,
            timeline=processing_stages,
        )

    def get_children(
        self,
        conn: sqlite3.Connection,
        parent_id: str,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> ManifestChildrenResponse:
        """
        Get split children for a parent requirement.

        Args:
            conn: SQLite connection
            parent_id: Parent requirement ID
            ctx: Request context (optional)

        Returns:
            ManifestChildrenResponse with child manifests and relationships
        """
        # Get split children
        children_rows = _db.get_split_children(conn, parent_id)

        # Get child manifests
        children_manifests = []
        for child_row in children_rows:
            child_manifest = self.get_full_manifest(conn, child_row["child_id"], ctx=ctx)
            if child_manifest:
                children_manifests.append(child_manifest)

        # Get split relationships
        split_relationships = [
            SplitRelationship(
                parent_id=c["parent_id"],
                child_id=c["child_id"],
                split_rationale=c["split_rationale"],
                split_timestamp=c["split_timestamp"],
                split_model=c["split_model"],
            )
            for c in children_rows
        ]

        return ManifestChildrenResponse(
            parent_id=parent_id,
            children=children_manifests,
            split_relationships=split_relationships,
        )

    def update_text(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        new_text: str,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> None:
        """
        Update requirement text after rewrite (updates current_text and checksum).

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            new_text: New requirement text
            ctx: Request context (optional)

        Raises:
            ServiceError if update fails
        """
        try:
            checksum = sha256_text(new_text)
            _db.update_manifest_text(conn, requirement_id, new_text, checksum)
            conn.commit()

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "text_update_failed",
                f"Failed to update text: {str(e)}",
                details={"requirement_id": requirement_id, "request_id": getattr(ctx, "request_id", None)}
            ) from e

    def update_requirement_with_fix(
        self,
        conn: sqlite3.Connection,
        requirement_id: str,
        new_text: str,
        criterion: str,
        old_score: float,
        new_score: float,
        suggestion: str,
        iteration: int,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> int:
        """
        Update requirement text after a criterion fix and track the change in processing stages.

        This method is used by the RequirementOrchestrator to track each individual fix
        applied during validation. It creates a processing stage entry for the fix and
        updates the requirement text.

        Args:
            conn: SQLite connection
            requirement_id: Requirement ID
            new_text: New requirement text after fix
            criterion: Name of the criterion that was fixed (e.g., "clarity", "testability")
            old_score: Score before fix
            new_score: Score after fix
            suggestion: The suggestion that was applied
            iteration: Current iteration number in orchestration
            ctx: Request context (optional)

        Returns:
            stage_id of the created processing stage

        Raises:
            ServiceError if update fails
        """
        try:
            # Update requirement text
            checksum = sha256_text(new_text)
            _db.update_manifest_text(conn, requirement_id, new_text, checksum)

            # Create a processing stage for this fix
            stage_name = f"fix_{criterion}"
            stage_metadata = {
                "criterion": criterion,
                "old_score": old_score,
                "new_score": new_score,
                "improvement": new_score - old_score,
                "suggestion": suggestion,
                "iteration": iteration,
                "fixed_at": datetime.utcnow().isoformat()
            }

            _db.add_processing_stage(
                conn,
                requirement_id=requirement_id,
                stage_name=stage_name,
                status="completed",
                score=new_score,
                stage_metadata=stage_metadata,
            )

            # Get the created stage_id
            stage_id = conn.execute(
                "SELECT id FROM processing_stage WHERE requirement_id = ? ORDER BY id DESC LIMIT 1",
                (requirement_id,)
            ).fetchone()[0]

            # Mark stage as completed immediately
            _db.complete_processing_stage(
                conn,
                stage_id=stage_id,
                status="completed",
                score=new_score
            )

            # Update manifest current_stage
            _db.update_manifest_stage(conn, requirement_id, stage_name)

            conn.commit()
            return stage_id

        except Exception as e:
            conn.rollback()
            raise ServiceError(
                "requirement_fix_update_failed",
                f"Failed to update requirement with fix: {str(e)}",
                details={
                    "requirement_id": requirement_id,
                    "criterion": criterion,
                    "request_id": getattr(ctx, "request_id", None)
                }
            ) from e
