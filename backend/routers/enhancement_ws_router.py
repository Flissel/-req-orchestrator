# -*- coding: utf-8 -*-
"""
WebSocket Router for Iterative SocietyOfMind Enhancement

This module provides WebSocket endpoints for real-time requirement enhancement
with human-in-the-loop clarification support.

The enhancement runs in iterative cycles:
1. Analyze requirement PURPOSE
2. Detect GAPS in information
3. Generate targeted QUESTION
4. Wait for user ANSWER
5. REWRITE requirement with answer
6. RE-EVALUATE until quality threshold met

Endpoints:
- WS /enhance/ws/{session_id} - WebSocket for enhancement with clarification
- POST /enhance/submit - Submit requirement for enhancement
- POST /enhance/answer/{session_id} - Submit answer to continue enhancement
- GET /enhance/status/{session_id} - Get enhancement status
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel, Field

# Import enhancement service
try:
    from arch_team.agents.society_of_mind_enhancement import (
        get_enhancement_service,
        EnhancementResult,
        EnhancementState,
        EnhancementStatus,
        ClarificationRequest
    )
    SOM_AVAILABLE = True
except ImportError as e:
    SOM_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"SocietyOfMind not available: {e}")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enhance", tags=["enhancement"])


# ============================================================================
# NEW: Batch Question Collection Endpoint
# ============================================================================

class BatchQuestionRequest(BaseModel):
    """Request to collect questions for multiple requirements."""
    requirements: List[Dict[str, Any]]  # [{"req_id": str, "text": str}, ...]
    quality_threshold: float = 0.7

class QuestionReportItem(BaseModel):
    """A single requirement with its collected questions."""
    req_id: str
    original_text: str
    current_score: float
    purpose: str
    gaps: List[str]
    questions: List[Dict[str, Any]]  # [{question, gap_addressed, examples}]
    needs_improvement: bool

class BatchQuestionReport(BaseModel):
    """Complete report of questions for all requirements."""
    total_requirements: int
    requirements_needing_input: int
    total_questions: int
    items: List[Dict[str, Any]]
    session_id: str
    success: bool
    error: Optional[str] = None

@router.post("/batch-questions", response_model=BatchQuestionReport)
async def collect_batch_questions(request: BatchQuestionRequest):
    """
    Collect clarifying questions for all requirements that don't meet the quality threshold.
    
    This does NOT enhance - it only analyzes and generates questions.
    Returns a report that can be displayed to the user for answering.
    """
    try:
        from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
        
        logger.info(f"[batch-questions] Starting question collection for {len(request.requirements)} requirements")
        logger.info(f"[batch-questions] Quality threshold: {request.quality_threshold}")
        
        enhancement_service = get_enhancement_service()
        
        if not enhancement_service._initialized:
            logger.error("[batch-questions] Enhancement service not initialized!")
            raise HTTPException(status_code=503, detail="Enhancement service not initialized")
        
        logger.info(f"[batch-questions] Enhancement service initialized with model: {enhancement_service.model_client}")
        
        session_id = f"batch-q-{uuid.uuid4().hex[:8]}"
        report_items = []
        total_questions = 0
        
        for idx, req in enumerate(request.requirements):
            req_id = req.get("req_id", "UNKNOWN")
            req_text = req.get("text", req.get("title", ""))
            
            logger.info(f"[batch-questions] [{idx+1}/{len(request.requirements)}] Processing {req_id}")
            
            if not req_text:
                logger.warning(f"[batch-questions] Skipping {req_id} - no text")
                continue            
            
            try:
                # Step 1: Analyze purpose
                logger.debug(f"[batch-questions] {req_id}: Analyzing purpose...")
                purpose_response = await enhancement_service._call_agent(
                    enhancement_service.PURPOSE_ANALYZER_PROMPT,
                    f"Analyze this requirement:\n\n{req_text}"
                )
                
                purpose = ""
                if "PURPOSE:" in purpose_response:
                    purpose = purpose_response.split("PURPOSE:")[-1].split("\n")[0].strip()
                logger.debug(f"[batch-questions] {req_id}: Purpose identified: {purpose[:50]}...")
                
                # Step 2: Detect gaps
                logger.debug(f"[batch-questions] {req_id}: Detecting gaps...")
                gap_input = f"""Requirement: {req_text}
Purpose: {purpose}"""
                
                gap_response = await enhancement_service._call_agent(
                    enhancement_service.GAP_DETECTOR_PROMPT, 
                    gap_input
                )
                
                # Parse gaps
                gaps = []
                if "GAPS:" in gap_response and "GAPS_NONE" not in gap_response:
                    gaps_section = gap_response.split("GAPS:")[-1]
                    for line in gaps_section.split("\n"):
                        line = line.strip()
                        if line and (line[0].isdigit() or line.startswith("-")):
                            gap = line.lstrip("0123456789.-) ").strip()
                            if gap and "CRITICAL_GAP" not in gap:
                                gaps.append(gap)
                
                logger.debug(f"[batch-questions] {req_id}: Found {len(gaps)} gaps")
                
                critical_gap = ""
                if "CRITICAL_GAP:" in gap_response:
                    critical_gap = gap_response.split("CRITICAL_GAP:")[-1].split("\n")[0].strip()
                
                # Step 3: Evaluate current quality
                logger.debug(f"[batch-questions] {req_id}: Evaluating quality...")
                eval_response = await enhancement_service._call_agent(
                    enhancement_service.EVALUATOR_PROMPT,
                    f"Evaluate this requirement:\n\n{req_text}"
                )
                
                current_score = 0.5
                if "TOTAL:" in eval_response:
                    try:
                        current_score = float(eval_response.split("TOTAL:")[-1].split("\n")[0].strip())
                    except ValueError:
                        pass
                
                logger.info(f"[batch-questions] {req_id}: Score = {current_score:.2f}")
                
                needs_improvement = current_score < request.quality_threshold
                
                # Step 4: Generate questions if gaps exist
                questions = []
                if gaps and needs_improvement:
                    logger.debug(f"[batch-questions] {req_id}: Generating questions for {len(gaps[:3])} gaps...")
                    # Generate question for each gap (max 3)
                    for gap_idx, gap in enumerate(gaps[:3]):
                        question_input = f"""Requirement: {req_text}
Purpose: {purpose}
Critical gap to address: {gap}"""
                        
                        question_response = await enhancement_service._call_agent(
                            enhancement_service.QUESTION_GENERATOR_PROMPT, 
                            question_input
                        )
                        
                        question_text = ""
                        if "QUESTION:" in question_response:
                            question_text = question_response.split("QUESTION:")[-1].split("\n")[0].strip()
                        
                        examples = []
                        if "EXAMPLE_ANSWERS:" in question_response:
                            examples_text = question_response.split("EXAMPLE_ANSWERS:")[-1].split("\n")[0]
                            examples = [e.strip() for e in examples_text.split(",") if e.strip()]
                        
                        expected_type = "text"
                        if "EXPECTED_ANSWER_TYPE:" in question_response:
                            expected_type = question_response.split("EXPECTED_ANSWER_TYPE:")[-1].split("\n")[0].strip()
                        
                        if question_text:
                            questions.append({
                                "question_id": f"{req_id}-Q{len(questions)+1}",
                                "question": question_text,
                                "gap_addressed": gap,
                                "expected_type": expected_type,
                                "examples": examples,
                                "answer": None
                            })
                            total_questions += 1
                            logger.debug(f"[batch-questions] {req_id}: Q{gap_idx+1}: {question_text[:50]}...")
                
                logger.info(f"[batch-questions] {req_id}: Generated {len(questions)} questions, needs_improvement={needs_improvement}")
                
                report_items.append({
                    "req_id": req_id,
                    "original_text": req_text,
                    "current_score": current_score,
                    "purpose": purpose,
                    "gaps": gaps,
                    "questions": questions,
                    "needs_improvement": needs_improvement
                })
                
            except Exception as e:
                logger.error(f"[batch-questions] Error analyzing {req_id}: {e}", exc_info=True)
                report_items.append({
                    "req_id": req_id,
                    "original_text": req_text,
                    "current_score": 0.0,
                    "purpose": "",
                    "gaps": [],
                    "questions": [],
                    "needs_improvement": True,
                    "error": str(e)
                })
        
        needs_input_count = sum(1 for item in report_items if len(item.get("questions", [])) > 0)
        
        logger.info(f"[batch-questions] COMPLETE: {len(report_items)} requirements analyzed, {needs_input_count} need input, {total_questions} total questions")
        
        return BatchQuestionReport(
            total_requirements=len(request.requirements),
            requirements_needing_input=needs_input_count,
            total_questions=total_questions,
            items=report_items,
            session_id=session_id,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[batch-questions] FAILED: {e}", exc_info=True)
        return BatchQuestionReport(
            total_requirements=len(request.requirements),
            requirements_needing_input=0,
            total_questions=0,
            items=[],
            session_id="",
            success=False,
            error=str(e)
        )


# ============================================================================
# NEW: Apply Answers and Enhance Batch
# ============================================================================

class ApplyAnswersRequest(BaseModel):
    """Request to apply user answers and enhance requirements."""
    session_id: str
    items: List[Dict[str, Any]]  # Report items with filled answers

class EnhancedRequirement(BaseModel):
    """Result of applying answers to a requirement."""
    req_id: str
    original_text: str
    enhanced_text: str
    final_score: float
    passed: bool
    changes_made: List[str]

class ApplyAnswersResponse(BaseModel):
    """Response after applying answers."""
    total_enhanced: int
    passed_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None

@router.post("/apply-answers", response_model=ApplyAnswersResponse)
async def apply_answers_and_enhance(request: ApplyAnswersRequest):
    """
    Apply user answers from the question report and enhance requirements.
    
    Takes the report items with filled-in answers and rewrites each requirement.
    """
    try:
        from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
        
        enhancement_service = get_enhancement_service()
        
        if not enhancement_service._initialized:
            raise HTTPException(status_code=503, detail="Enhancement service not initialized")
        
        results = []
        passed_count = 0
        
        for item in request.items:
            req_id = item.get("req_id")
            original_text = item.get("original_text", "")
            purpose = item.get("purpose", "")
            questions = item.get("questions", [])
            
            # Collect answered questions
            answered = [q for q in questions if q.get("answer")]
            
            if not answered:
                # No answers provided - skip enhancement
                results.append({
                    "req_id": req_id,
                    "original_text": original_text,
                    "enhanced_text": original_text,
                    "final_score": item.get("current_score", 0.5),
                    "passed": False,
                    "changes_made": [],
                    "skipped": True
                })
                continue
            
            try:
                # Build context from all answers
                answers_context = "\n".join([
                    f"Q: {q['question']}\nA: {q['answer']}"
                    for q in answered
                ])
                
                # Rewrite requirement with all answers
                rewrite_input = f"""Original requirement: {original_text}
Purpose: {purpose}

User provided the following answers to clarification questions:
{answers_context}

Please rewrite the requirement incorporating ALL these answers to make it:
1. Specific and measurable
2. Testable
3. Atomic (single concern)
4. Clear and unambiguous"""
                
                rewrite_response = await enhancement_service._call_agent(
                    enhancement_service.REWRITE_PROMPT,
                    rewrite_input
                )
                
                # Extract rewritten text
                enhanced_text = original_text
                changes = []
                
                if "REWRITTEN:" in rewrite_response:
                    enhanced_text = rewrite_response.split("REWRITTEN:")[-1].split("\n")[0].strip()
                elif "COMPLETE:" in rewrite_response:
                    enhanced_text = rewrite_response.split("COMPLETE:")[-1].split("\n")[0].strip()
                
                if "CHANGES:" in rewrite_response:
                    changes_section = rewrite_response.split("CHANGES:")[-1].split("INCORPORATED:")[0]
                    changes = [c.strip() for c in changes_section.split("\n") if c.strip() and c.strip() != "-"]
                
                # Evaluate final quality
                eval_response = await enhancement_service._call_agent(
                    enhancement_service.EVALUATOR_PROMPT,
                    f"Evaluate this requirement:\n\n{enhanced_text}"
                )
                
                final_score = 0.5
                if "TOTAL:" in eval_response:
                    try:
                        final_score = float(eval_response.split("TOTAL:")[-1].split("\n")[0].strip())
                    except ValueError:
                        pass
                
                passed = final_score >= 0.7
                if passed:
                    passed_count += 1
                
                results.append({
                    "req_id": req_id,
                    "original_text": original_text,
                    "enhanced_text": enhanced_text,
                    "final_score": final_score,
                    "passed": passed,
                    "changes_made": changes,
                    "answers_applied": len(answered)
                })
                
            except Exception as e:
                logger.error(f"Error enhancing {req_id}: {e}")
                results.append({
                    "req_id": req_id,
                    "original_text": original_text,
                    "enhanced_text": original_text,
                    "final_score": 0.0,
                    "passed": False,
                    "changes_made": [],
                    "error": str(e)
                })
        
        return ApplyAnswersResponse(
            total_enhanced=len(results),
            passed_count=passed_count,
            failed_count=len(results) - passed_count,
            results=results,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply answers failed: {e}", exc_info=True)
        return ApplyAnswersResponse(
            total_enhanced=0,
            passed_count=0,
            failed_count=0,
            results=[],
            success=False,
            error=str(e)
        )


# ============================================================================
# NEW: Auto-Enhance Batch (No User Input Required)
# ============================================================================

class AutoEnhanceBatchRequest(BaseModel):
    """Request for automatic batch enhancement without user input."""
    requirements: List[Dict[str, Any]]  # [{"req_id": str, "text": str}, ...]
    quality_threshold: float = 0.7
    max_iterations: int = 3

class AutoEnhanceResult(BaseModel):
    """Result of auto-enhancement for a single requirement."""
    req_id: str
    original_text: str
    enhanced_text: str
    score: float
    verdict: str
    iterations: int
    purpose: str
    gaps_filled: List[str]
    gaps_remaining: List[str]
    changes: List[str]
    success: bool

class AutoEnhanceBatchResponse(BaseModel):
    """Response from auto-batch enhancement."""
    total_processed: int
    passed_count: int
    failed_count: int
    improved_count: int
    average_score: float
    total_time_ms: int
    results: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None

@router.post("/auto-batch", response_model=AutoEnhanceBatchResponse)
async def auto_enhance_batch(request: AutoEnhanceBatchRequest):
    """
    Automatically enhance all requirements without user input.
    
    This mode:
    1. Analyzes each requirement for PURPOSE and GAPS
    2. Auto-generates reasonable values for missing metrics
    3. Rewrites requirements to be measurable and testable
    4. Returns gaps that cannot be auto-filled as suggestions
    
    Best for: Getting quick improvements without manual intervention.
    """
    try:
        from arch_team.agents.society_of_mind_enhancement import get_enhancement_service
        
        logger.info(f"[auto-batch] Starting auto-enhancement for {len(request.requirements)} requirements")
        logger.info(f"[auto-batch] Quality threshold: {request.quality_threshold}, max_iterations: {request.max_iterations}")
        
        enhancement_service = get_enhancement_service()
        
        if not enhancement_service._initialized:
            logger.error("[auto-batch] Enhancement service not initialized!")
            raise HTTPException(status_code=503, detail="Enhancement service not initialized")
        
        # Convert to format expected by run_auto_batch
        reqs_for_batch = [
            {"id": r.get("req_id", f"REQ-{i}"), "text": r.get("text", r.get("title", ""))}
            for i, r in enumerate(request.requirements)
        ]
        
        def progress_callback(stage: str, completed: int, total: int, message: str):
            logger.info(f"[auto-batch] [{stage}] {completed}/{total}: {message}")
        
        # Run automatic batch enhancement
        result = await enhancement_service.run_auto_batch(
            requirements=reqs_for_batch,
            quality_threshold=request.quality_threshold,
            max_iterations=request.max_iterations,
            progress_callback=progress_callback
        )
        
        logger.info(f"[auto-batch] COMPLETE: {result.passed_count}/{result.total_processed} passed, avg score: {result.average_score:.2f}")
        
        return AutoEnhanceBatchResponse(
            total_processed=result.total_processed,
            passed_count=result.passed_count,
            failed_count=result.failed_count,
            improved_count=result.improved_count,
            average_score=result.average_score,
            total_time_ms=result.total_time_ms,
            results=result.requirements,
            success=result.success,
            error=result.error
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[auto-batch] FAILED: {e}", exc_info=True)
        return AutoEnhanceBatchResponse(
            total_processed=0,
            passed_count=0,
            failed_count=0,
            improved_count=0,
            average_score=0.0,
            total_time_ms=0,
            results=[],
            success=False,
            error=str(e)
        )


# Request/Response Models

class EnhancementRequest(BaseModel):
    """Request to enhance a requirement"""
    requirement_text: str = Field(..., min_length=10)
    context: Optional[Dict[str, Any]] = None


class EnhancementResponse(BaseModel):
    """Response from enhancement request"""
    session_id: str
    status: str
    message: str
    current_text: Optional[str] = None
    score: Optional[float] = None
    pending_question: Optional[Dict[str, Any]] = None


class AnswerRequest(BaseModel):
    """User's answer to a clarification question"""
    answer: str = Field(..., min_length=1)


class SessionStatusResponse(BaseModel):
    """Status of an enhancement session"""
    session_id: str
    status: str
    original_text: str
    current_text: str
    score: float
    iteration: int
    questions_answered: int
    pending_question: Optional[Dict[str, Any]] = None
    identified_purpose: str = ""
    identified_gaps: List[str] = []


# WebSocket Message Types
class WSMessageType:
    ENHANCEMENT_START = "enhancement_start"
    ENHANCEMENT_PROGRESS = "progress"
    PURPOSE = "purpose"
    EVALUATION = "evaluation"
    REWRITTEN = "rewritten"
    CLARIFICATION_REQUEST = "clarification_request"
    CLARIFICATION_RESPONSE = "clarification_response"
    COMPLETE = "complete"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


# REST Endpoints

@router.post("/submit", response_model=EnhancementResponse)
async def submit_enhancement(request: EnhancementRequest):
    """
    Start a new enhancement session.
    
    Returns session_id and first question (if any).
    """
    if not SOM_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="SocietyOfMind enhancement not available"
        )
    
    try:
        service = get_enhancement_service()
        state = await service.start_enhancement(request.requirement_text)
        
        return EnhancementResponse(
            session_id=state.session_id,
            status=state.status.value,
            message="Enhancement started" if state.status == EnhancementStatus.AWAITING_ANSWER else "Enhancement complete",
            current_text=state.current_text,
            score=state.current_score,
            pending_question=state.pending_question
        )
        
    except Exception as e:
        logger.error(f"Enhancement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/answer/{session_id}", response_model=EnhancementResponse)
async def submit_answer(session_id: str, request: AnswerRequest):
    """
    Submit answer to continue enhancement.
    
    The system will:
    1. Incorporate the answer into the requirement
    2. Re-evaluate quality
    3. Generate next question if needed
    """
    if not SOM_AVAILABLE:
        raise HTTPException(status_code=503, detail="SocietyOfMind not available")
    
    try:
        service = get_enhancement_service()
        state = await service.continue_enhancement(session_id, request.answer)
        
        return EnhancementResponse(
            session_id=state.session_id,
            status=state.status.value,
            message="Answer processed",
            current_text=state.current_text,
            score=state.current_score,
            pending_question=state.pending_question
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Answer processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """Get the current status of an enhancement session."""
    if not SOM_AVAILABLE:
        raise HTTPException(status_code=503, detail="SocietyOfMind not available")
    
    service = get_enhancement_service()
    state = service.get_state(session_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionStatusResponse(
        session_id=state.session_id,
        status=state.status.value,
        original_text=state.original_text,
        current_text=state.current_text,
        score=state.current_score,
        iteration=state.iteration,
        questions_answered=len(state.questions_answered),
        pending_question=state.pending_question,
        identified_purpose=state.purpose,
        identified_gaps=state.gaps
    )