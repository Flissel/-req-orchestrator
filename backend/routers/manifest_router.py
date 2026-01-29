# -*- coding: utf-8 -*-
"""
Manifest API Router
Provides endpoints for requirement lifecycle tracking and provenance.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging

from backend.core import db as _db
from backend.services import ManifestService
from backend.services.ports import RequestContext
from backend.schemas import (
    RequirementManifest,
    ManifestTimelineResponse,
    ManifestChildrenResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api/v1/manifest", tags=["manifest"])
logger = logging.getLogger(__name__)


@router.get("/sources")
async def get_manifest_sources():
    """
    Get list of unique source files (projects) with requirement counts.
    
    Returns:
    - List of source files with statistics
    - Useful for selecting which project/file to load
    
    Example: GET /api/v1/manifest/sources
    """
    try:
        conn = _db.get_db()
        try:
            query = """
                SELECT 
                    source_file,
                    source_type,
                    COUNT(*) as requirement_count,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM requirement_manifest
                WHERE source_file IS NOT NULL AND source_file != ''
                GROUP BY source_file, source_type
                ORDER BY last_created DESC
            """
            rows = conn.execute(query).fetchall()
            
            sources = []
            for row in rows:
                sources.append({
                    "source_file": row["source_file"],
                    "source_type": row["source_type"],
                    "requirement_count": row["requirement_count"],
                    "first_created": row["first_created"],
                    "last_created": row["last_created"]
                })
            
            return {
                "sources": sources,
                "total_sources": len(sources)
            }
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Failed to get manifest sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{requirement_id}", response_model=RequirementManifest)
async def get_manifest(requirement_id: str):
    """
    Get complete requirement manifest with full lifecycle tracking.

    Returns:
    - Requirement metadata (ID, source, checksums, timestamps)
    - Full processing timeline (all stages with scores/verdicts)
    - Evidence chain (source documents, chunks, neighbor context)
    - Split children (if requirement was split)

    Example: GET /api/v1/manifest/REQ-535535-api
    """
    try:
        conn = _db.get_db()
        try:
            service = ManifestService()
            ctx = RequestContext(request_id=f"manifest-get-{requirement_id}")

            manifest = service.get_full_manifest(conn, requirement_id, ctx=ctx)

            if not manifest:
                raise HTTPException(
                    status_code=404,
                    detail=f"Manifest not found for requirement_id: {requirement_id}"
                )

            return manifest

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get manifest {requirement_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{requirement_id}/timeline", response_model=ManifestTimelineResponse)
async def get_manifest_timeline(requirement_id: str):
    """
    Get chronological timeline of all processing stages for a requirement.

    Returns:
    - All processing stages ordered by started_at timestamp
    - Stage details: name, status, scores, verdicts, latency, token usage
    - Useful for visualizing the requirement's journey through the pipeline

    Example: GET /api/v1/manifest/REQ-535535-api/timeline
    """
    try:
        conn = _db.get_db()
        try:
            service = ManifestService()
            ctx = RequestContext(request_id=f"timeline-{requirement_id}")

            timeline = service.get_timeline(conn, requirement_id, ctx=ctx)

            if not timeline:
                raise HTTPException(
                    status_code=404,
                    detail=f"No timeline found for requirement_id: {requirement_id}"
                )

            return timeline

        finally:
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeline for {requirement_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{requirement_id}/children", response_model=ManifestChildrenResponse)
async def get_manifest_children(requirement_id: str):
    """
    Get all child requirements created when AtomicityAgent split this requirement.

    Returns:
    - List of child manifests (if requirement was split)
    - Split relationships with rationale and metadata
    - Empty list if requirement was not split or is atomic

    Example: GET /api/v1/manifest/REQ-535535-api/children
    """
    try:
        conn = _db.get_db()
        try:
            service = ManifestService()
            ctx = RequestContext(request_id=f"children-{requirement_id}")

            children = service.get_children(conn, requirement_id, ctx=ctx)

            return children

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to get children for {requirement_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[RequirementManifest])
async def query_manifests(
    source_type: Optional[str] = Query(None, description="Filter by source type: upload|manual|chunk_miner|api"),
    source_file: Optional[str] = Query(None, description="Filter by source filename"),
    current_stage: Optional[str] = Query(None, description="Filter by current processing stage"),
    parent_id: Optional[str] = Query(None, description="Filter by parent requirement ID (for splits)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip (for pagination)"),
):
    """
    Query requirements manifests with filters and pagination.

    Query Parameters:
    - source_type: Filter by source (upload|manual|chunk_miner|api)
    - source_file: Filter by original filename
    - current_stage: Filter by processing stage (input|mining|evaluation|atomicity|etc.)
    - parent_id: Filter by parent ID (to find all splits from a parent)
    - limit: Max results (default: 100, max: 1000)
    - offset: Skip N results for pagination (default: 0)

    Example: GET /api/v1/manifest?source_type=chunk_miner&current_stage=evaluation&limit=50
    """
    try:
        conn = _db.get_db()
        try:
            # Build dynamic query
            where_clauses = []
            params = []

            if source_type:
                where_clauses.append("source_type = ?")
                params.append(source_type)

            if source_file:
                where_clauses.append("source_file = ?")
                params.append(source_file)

            if current_stage:
                where_clauses.append("current_stage = ?")
                params.append(current_stage)

            if parent_id:
                where_clauses.append("parent_id = ?")
                params.append(parent_id)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Query manifests
            query = f"""
                SELECT requirement_id, requirement_checksum, source_type, source_file,
                       source_file_sha1, chunk_index, original_text, current_text,
                       current_stage, parent_id, validation_score, validation_verdict,
                       created_at, updated_at, metadata
                FROM requirement_manifest
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            # Convert to Pydantic models
            service = ManifestService()
            manifests = []

            for row in rows:
                ctx = RequestContext(request_id=f"query-{row['requirement_id']}")
                manifest = service.get_full_manifest(conn, row["requirement_id"], ctx=ctx)
                if manifest:
                    manifests.append(manifest)

            return manifests

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to query manifests: {e}")
        raise HTTPException(status_code=500, detail=str(e))
