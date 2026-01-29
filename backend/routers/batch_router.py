# -*- coding: utf-8 -*-
"""
Batch Processing API Router

Endpoints for submitting, monitoring, and retrieving batch processing jobs
for mass requirements validation using OpenAI Batch API.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from backend.core.batch_processor import get_batch_processor, BatchJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


# Request/Response Models

class RequirementInput(BaseModel):
    """Single requirement for batch processing"""
    id: str = Field(..., description="Unique requirement ID")
    text: str = Field(..., description="Requirement text to evaluate")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context")


class BatchSubmitRequest(BaseModel):
    """Request to submit a batch of requirements"""
    requirements: List[RequirementInput] = Field(..., min_length=1, max_length=1000)
    metadata: Optional[Dict[str, str]] = Field(default=None)
    wait: bool = Field(default=False, description="If true, wait for completion (sync mode)")


class BatchSubmitResponse(BaseModel):
    """Response after submitting a batch"""
    batch_id: str
    status: str
    request_count: int
    message: str


class BatchStatusResponse(BaseModel):
    """Response for batch status check"""
    batch_id: str
    status: str
    request_count: int
    completed_count: int
    failed_count: int
    progress_percent: float
    output_file_id: Optional[str] = None


class BatchResultItem(BaseModel):
    """Single result item from batch"""
    id: str
    scores: Dict[str, float]
    summary: str
    success: bool
    error: Optional[str] = None


class BatchResultsResponse(BaseModel):
    """Response with batch results"""
    batch_id: str
    results: List[BatchResultItem]
    total_count: int
    success_count: int
    failed_count: int


# Endpoints

@router.post("/submit", response_model=BatchSubmitResponse)
async def submit_batch(request: BatchSubmitRequest):
    """
    Submit requirements for batch processing.
    
    The Batch API processes requirements asynchronously with 50% cost savings.
    Use GET /batch/status/{batch_id} to check progress.
    """
    processor = get_batch_processor()
    
    if not processor.client:
        raise HTTPException(
            status_code=503,
            detail="Batch API not available. Requires direct OpenAI API key (not OpenRouter)."
        )
    
    try:
        requirements = [
            {
                "id": req.id,
                "text": req.text,
                "context": req.context or {}
            }
            for req in request.requirements
        ]
        
        batch_id = await processor.submit_batch(
            requirements=requirements,
            metadata=request.metadata
        )
        
        job = await processor.get_batch_status(batch_id)
        
        return BatchSubmitResponse(
            batch_id=batch_id,
            status=job.status,
            request_count=job.request_count,
            message=f"Batch submitted successfully. Use GET /batch/status/{batch_id} to check progress."
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(batch_id: str):
    """
    Check the status of a batch processing job.
    
    Status values:
    - validating: Batch is being validated
    - in_progress: Processing requirements
    - completed: All done, results available via /batch/results/{batch_id}
    - failed: Batch failed
    - expired: Batch expired (24h limit)
    - cancelled: Batch was cancelled
    """
    processor = get_batch_processor()
    
    if not processor.client:
        raise HTTPException(
            status_code=503,
            detail="Batch API not available"
        )
    
    try:
        job = await processor.get_batch_status(batch_id)
        
        progress = (job.completed_count / job.request_count * 100) if job.request_count > 0 else 0
        
        return BatchStatusResponse(
            batch_id=job.batch_id,
            status=job.status,
            request_count=job.request_count,
            completed_count=job.completed_count,
            failed_count=job.failed_count,
            progress_percent=round(progress, 1),
            output_file_id=job.output_file_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{batch_id}", response_model=BatchResultsResponse)
async def get_batch_results(batch_id: str):
    """
    Get results from a completed batch.
    
    Only available when status is 'completed'.
    """
    processor = get_batch_processor()
    
    if not processor.client:
        raise HTTPException(
            status_code=503,
            detail="Batch API not available"
        )
    
    try:
        # Check status first
        job = await processor.get_batch_status(batch_id)
        
        if job.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Batch not complete. Current status: {job.status}"
            )
        
        results = await processor.get_batch_results(batch_id)
        
        success_count = sum(1 for r in results if r.get("success", False))
        
        return BatchResultsResponse(
            batch_id=batch_id,
            results=[
                BatchResultItem(
                    id=r.get("id", ""),
                    scores=r.get("scores", {}),
                    summary=r.get("summary", ""),
                    success=r.get("success", False),
                    error=r.get("error")
                )
                for r in results
            ],
            total_count=len(results),
            success_count=success_count,
            failed_count=len(results) - success_count
        )
        
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{batch_id}")
async def cancel_batch(batch_id: str):
    """
    Cancel a running batch job.
    """
    processor = get_batch_processor()
    
    if not processor.client:
        raise HTTPException(
            status_code=503,
            detail="Batch API not available"
        )
    
    success = await processor.cancel_batch(batch_id)
    
    if success:
        return {"message": f"Batch {batch_id} cancelled successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to cancel batch")


@router.get("/active")
async def list_active_batches():
    """
    List all active/tracked batch jobs.
    """
    processor = get_batch_processor()
    
    batches = processor.get_active_batches()
    
    return {
        "active_batches": [
            {
                "batch_id": job.batch_id,
                "status": job.status,
                "request_count": job.request_count,
                "completed_count": job.completed_count,
                "failed_count": job.failed_count,
                "created_at": job.created_at.isoformat() if job.created_at else None
            }
            for job in batches
        ],
        "total_count": len(batches)
    }