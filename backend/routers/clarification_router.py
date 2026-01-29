# -*- coding: utf-8 -*-
"""
Clarification API Router.

REST endpoints for managing clarification questions:
- GET /api/v1/clarifications/pending - Get pending questions
- GET /api/v1/clarifications/{id} - Get single question
- POST /api/v1/clarifications/{id}/answer - Answer a question
- POST /api/v1/clarifications/{id}/skip - Skip a question
- GET /api/v1/clarifications/summary - Get statistics

Part of the Requirements-Management-System.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core import db as _db
from backend.services.clarification_service import ClarificationService

logger = logging.getLogger("backend.routers.clarification_router")

router = APIRouter(prefix="/api/v1/clarifications", tags=["clarifications"])


# === Request/Response Models ===

class AnswerRequest(BaseModel):
    """Request to answer a clarification question."""
    answer_text: str
    apply_to_requirement: bool = True


class SkipRequest(BaseModel):
    """Request to skip a clarification question."""
    reason: Optional[str] = None


class QuestionResponse(BaseModel):
    """Response for a single clarification question."""
    id: int
    validation_id: Optional[str] = None
    requirement_id: str
    criterion: str
    question_text: str
    suggested_answers: List[str]
    context_hint: Optional[str] = None
    status: str
    answer_text: Optional[str] = None
    created_at: str
    answered_at: Optional[str] = None
    applied_text: Optional[str] = None


class SummaryResponse(BaseModel):
    """Response for clarification summary statistics."""
    total: int
    pending: int
    answered: int
    skipped: int
    expired: int
    by_status: Dict[str, int]
    by_criterion: Dict[str, int]


# === Endpoints ===

@router.get("/pending", response_model=List[QuestionResponse])
async def get_pending_questions(
    requirement_id: Optional[str] = Query(None, description="Filter by requirement ID"),
    validation_id: Optional[str] = Query(None, description="Filter by validation session ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results")
) -> List[Dict[str, Any]]:
    """
    Get all pending (unanswered) clarification questions.
    
    Returns questions sorted by creation time (oldest first).
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        questions = service.get_pending_questions(
            conn,
            requirement_id=requirement_id,
            validation_id=validation_id,
            limit=limit
        )
        return questions
    finally:
        conn.close()


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    validation_id: Optional[str] = Query(None, description="Filter by validation session ID")
) -> Dict[str, Any]:
    """
    Get summary statistics for clarification questions.
    
    Returns counts by status and criterion.
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        summary = service.get_questions_summary(conn, validation_id=validation_id)
        return summary
    finally:
        conn.close()


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(question_id: int) -> Dict[str, Any]:
    """
    Get a single clarification question by ID.
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        question = service.get_question_by_id(conn, question_id)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        return question
    finally:
        conn.close()


@router.get("/requirement/{requirement_id}", response_model=List[QuestionResponse])
async def get_questions_for_requirement(
    requirement_id: str,
    status: Optional[str] = Query(None, description="Filter by status (pending/answered/skipped/expired)")
) -> List[Dict[str, Any]]:
    """
    Get all clarification questions for a specific requirement.
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        questions = service.get_questions_for_requirement(
            conn,
            requirement_id=requirement_id,
            status=status
        )
        return questions
    finally:
        conn.close()


@router.post("/{question_id}/answer", response_model=QuestionResponse)
async def answer_question(
    question_id: int,
    request: AnswerRequest
) -> Dict[str, Any]:
    """
    Answer a clarification question.
    
    Optionally applies the answer to update the requirement text.
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        # Check if question exists and is pending
        question = service.get_question_by_id(conn, question_id)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        if question["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Question {question_id} is not pending (status: {question['status']})"
            )
        
        # Answer the question
        updated = service.answer_question(
            conn,
            question_id=question_id,
            answer_text=request.answer_text,
            apply_to_requirement=request.apply_to_requirement
        )
        
        logger.info(f"Question {question_id} answered: {request.answer_text[:50]}...")
        
        return updated
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.post("/{question_id}/skip", response_model=QuestionResponse)
async def skip_question(
    question_id: int,
    request: SkipRequest
) -> Dict[str, Any]:
    """
    Skip a clarification question (user chose not to answer).
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        # Check if question exists
        question = service.get_question_by_id(conn, question_id)
        if not question:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        
        if question["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Question {question_id} is not pending (status: {question['status']})"
            )
        
        # Skip the question
        updated = service.skip_question(
            conn,
            question_id=question_id,
            reason=request.reason
        )
        
        logger.info(f"Question {question_id} skipped: {request.reason}")
        
        return updated
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.post("/batch/answer")
async def batch_answer_questions(
    answers: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Answer multiple clarification questions at once.
    
    Request body: [
        {"question_id": 1, "answer_text": "...", "apply_to_requirement": true},
        {"question_id": 2, "answer_text": "...", "apply_to_requirement": true},
        ...
    ]
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    results = {
        "successful": [],
        "failed": []
    }
    
    try:
        for item in answers:
            question_id = item.get("question_id")
            answer_text = item.get("answer_text")
            apply = item.get("apply_to_requirement", True)
            
            if not question_id or not answer_text:
                results["failed"].append({
                    "question_id": question_id,
                    "error": "Missing question_id or answer_text"
                })
                continue
            
            try:
                updated = service.answer_question(
                    conn,
                    question_id=question_id,
                    answer_text=answer_text,
                    apply_to_requirement=apply
                )
                results["successful"].append({
                    "question_id": question_id,
                    "status": "answered"
                })
            except Exception as e:
                results["failed"].append({
                    "question_id": question_id,
                    "error": str(e)
                })
        
        return {
            "total": len(answers),
            "successful_count": len(results["successful"]),
            "failed_count": len(results["failed"]),
            **results
        }
        
    finally:
        conn.close()


@router.delete("/expired")
async def cleanup_expired_questions(
    max_age_hours: int = Query(24, ge=1, le=168, description="Max age in hours")
) -> Dict[str, Any]:
    """
    Clean up expired clarification questions.
    
    Marks pending questions older than max_age_hours as expired.
    """
    service = ClarificationService()
    conn = _db.get_db()
    
    try:
        count = service.expire_old_questions(conn, max_age_hours=max_age_hours)
        return {
            "expired_count": count,
            "max_age_hours": max_age_hours
        }
    finally:
        conn.close()