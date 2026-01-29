# -*- coding: utf-8 -*-
"""
Clarification Delegator for Parallel Question Generation and Prioritization.

Coordinates multiple ClarificationAgents, aggregates questions,
prioritizes them, and persists to database.

Part of the Requirements-Management-System.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from .clarification_agent import (
    ClarificationAgent,
    ClarificationTask,
    ClarificationResult,
    ClarificationQuestion,
    ClarificationPriority
)

logger = logging.getLogger("arch_team.clarification_delegator")


@dataclass
class BatchClarificationResult:
    """Result from processing a batch of requirements for clarification."""
    total_count: int
    needs_clarification_count: int
    auto_fixable_count: int
    questions: List[ClarificationQuestion] = field(default_factory=list)
    results_by_req_id: Dict[str, ClarificationResult] = field(default_factory=dict)
    total_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def questions_by_priority(self) -> Dict[str, List[ClarificationQuestion]]:
        """Group questions by priority level."""
        by_priority = {p.name: [] for p in ClarificationPriority}
        for q in self.questions:
            by_priority[q.priority.name].append(q)
        return by_priority
    
    @property
    def critical_questions(self) -> List[ClarificationQuestion]:
        """Get only CRITICAL priority questions."""
        return [q for q in self.questions if q.priority == ClarificationPriority.CRITICAL]
    
    @property
    def high_questions(self) -> List[ClarificationQuestion]:
        """Get only HIGH priority questions."""
        return [q for q in self.questions if q.priority == ClarificationPriority.HIGH]


class ClarificationDelegator:
    """
    Delegator for parallel clarification question generation.
    
    This delegator:
    1. Creates ClarificationAgents for parallel processing
    2. Aggregates all questions from multiple requirements
    3. Prioritizes questions globally (CRITICAL > HIGH > MEDIUM > LOW)
    4. Persists questions to clarification_question table
    5. Streams progress via SSE to frontend
    
    Usage:
        delegator = ClarificationDelegator(max_concurrent=5)
        result = await delegator.process_batch(validation_results, correlation_id)
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        auto_fix_threshold: float = 0.5,
        persist_to_db: bool = True
    ):
        """
        Initialize clarification delegator.
        
        Args:
            max_concurrent: Maximum concurrent clarification analyses
            auto_fix_threshold: Criteria scores below this may need user input
            persist_to_db: Whether to persist questions to database
        """
        self.max_concurrent = max_concurrent
        self.auto_fix_threshold = auto_fix_threshold
        self.persist_to_db = persist_to_db
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    def _send_to_workflow_stream(
        self,
        correlation_id: Optional[str],
        message_type: str,
        **kwargs
    ):
        """Send message to workflow stream for frontend display."""
        if not correlation_id:
            return
        
        try:
            from arch_team.service import workflow_streams
            from datetime import datetime
            
            queue = workflow_streams.get(correlation_id)
            if queue:
                message = {
                    "type": message_type,
                    "timestamp": datetime.now().isoformat(),
                    **kwargs
                }
                queue.put(message)
                logger.debug(f"[Stream] Sent {message_type}: {kwargs}")
        except Exception as e:
            logger.error(f"Error sending to workflow stream: {e}")
    
    async def process_batch(
        self,
        validation_results: List[Dict[str, Any]],
        correlation_id: Optional[str] = None,
        validation_id: Optional[str] = None
    ) -> BatchClarificationResult:
        """
        Process a batch of validation results and generate clarification questions.
        
        Args:
            validation_results: List of validation results with format:
                {
                    "req_id": "REQ-xxx",
                    "title": "Requirement text",
                    "score": 0.5,
                    "verdict": "fail",
                    "evaluation": [{"criterion": "...", "score": 0.3, "passed": False, "feedback": "..."}]
                }
            correlation_id: SSE session ID for streaming
            validation_id: Link to validation_history table
        
        Returns:
            BatchClarificationResult with all questions and statistics
        """
        start_time = time.time()
        
        # Filter to only failed requirements
        failed_results = [r for r in validation_results if r.get("verdict") == "fail"]
        
        if not failed_results:
            logger.info("No failed requirements to analyze for clarification")
            return BatchClarificationResult(
                total_count=len(validation_results),
                needs_clarification_count=0,
                auto_fixable_count=0,
                total_time_ms=0
            )
        
        logger.info(f"Analyzing {len(failed_results)} failed requirements for clarification needs")
        
        self._send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="ClarificationAgent",
            message=f"🔍 Analyzing {len(failed_results)} failed requirements for clarification needs..."
        )
        
        # Create progress callback for SSE
        def progress_callback(worker_id: str, completed: int, total: int, message: str):
            self._send_to_workflow_stream(
                correlation_id,
                "clarification_progress",
                worker_id=worker_id,
                completed=completed,
                total=total,
                message=message
            )
        
        # Create ClarificationAgent
        agent = ClarificationAgent(
            semaphore=self._semaphore,
            progress_callback=progress_callback,
            auto_fix_threshold=self.auto_fix_threshold
        )
        
        # Create tasks from validation results
        tasks = []
        for i, vr in enumerate(failed_results):
            task = ClarificationTask(
                req_id=vr.get("req_id", f"unknown-{i}"),
                requirement_text=vr.get("title", ""),
                validation_results=vr.get("evaluation", []),
                overall_score=vr.get("score", 0.0),
                tag=vr.get("tag"),
                index=i
            )
            tasks.append(task)
        
        # Process in parallel
        results = await agent.analyze_batch(tasks)
        
        # Aggregate results
        all_questions = []
        results_by_req_id = {}
        needs_clarification_count = 0
        auto_fixable_count = 0
        errors = []
        
        for result in results:
            results_by_req_id[result.req_id] = result
            
            if result.error:
                errors.append(f"{result.req_id}: {result.error}")
                continue
            
            if result.needs_clarification:
                needs_clarification_count += 1
                all_questions.extend(result.questions)
            
            if result.auto_fixable_criteria:
                auto_fixable_count += 1
        
        # Sort all questions by priority
        all_questions.sort(key=lambda q: (q.priority.value, q.score))
        
        total_time_ms = int((time.time() - start_time) * 1000)
        
        # Create result
        batch_result = BatchClarificationResult(
            total_count=len(validation_results),
            needs_clarification_count=needs_clarification_count,
            auto_fixable_count=auto_fixable_count,
            questions=all_questions,
            results_by_req_id=results_by_req_id,
            total_time_ms=total_time_ms,
            errors=errors
        )
        
        # Persist to database if enabled
        if self.persist_to_db and all_questions:
            await self._persist_questions(
                all_questions,
                validation_id=validation_id
            )
        
        # Send completion message
        critical_count = len(batch_result.critical_questions)
        high_count = len(batch_result.high_questions)
        
        self._send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="ClarificationAgent",
            message=f"✅ Analysis complete ({total_time_ms/1000:.1f}s): "
                   f"{len(all_questions)} questions generated "
                   f"({critical_count} critical, {high_count} high priority)"
        )
        
        logger.info(f"Clarification analysis complete: {len(all_questions)} questions, "
                   f"{needs_clarification_count} requirements need input, "
                   f"{auto_fixable_count} can be auto-fixed")
        
        return batch_result
    
    async def _persist_questions(
        self,
        questions: List[ClarificationQuestion],
        validation_id: Optional[str] = None
    ) -> List[int]:
        """
        Persist clarification questions to database.
        
        Args:
            questions: List of ClarificationQuestions to persist
            validation_id: Optional link to validation_history
        
        Returns:
            List of inserted question IDs
        """
        try:
            from backend.core import db as _db
            import json
            
            conn = _db.get_db()
            inserted_ids = []
            
            try:
                for q in questions:
                    cursor = conn.execute(
                        """
                        INSERT INTO clarification_question
                        (validation_id, requirement_id, criterion, question_text,
                         suggested_answers, context_hint, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending')
                        """,
                        (
                            validation_id,
                            q.requirement_id,
                            q.criterion,
                            q.question_text,
                            json.dumps(q.suggested_answers, ensure_ascii=False),
                            q.context_hint
                        )
                    )
                    inserted_ids.append(cursor.lastrowid)
                
                logger.info(f"Persisted {len(inserted_ids)} clarification questions to database")
                
            finally:
                conn.close()
            
            return inserted_ids
            
        except Exception as e:
            logger.error(f"Failed to persist clarification questions: {e}")
            return []
    
    def to_dict_results(
        self,
        batch_result: BatchClarificationResult
    ) -> Dict[str, Any]:
        """
        Convert BatchClarificationResult to dictionary format.
        
        Args:
            batch_result: BatchClarificationResult to convert
        
        Returns:
            Dictionary with all results
        """
        return {
            "total_count": batch_result.total_count,
            "needs_clarification_count": batch_result.needs_clarification_count,
            "auto_fixable_count": batch_result.auto_fixable_count,
            "total_questions": len(batch_result.questions),
            "critical_questions": len(batch_result.critical_questions),
            "high_questions": len(batch_result.high_questions),
            "total_time_ms": batch_result.total_time_ms,
            "questions": [q.to_dict() for q in batch_result.questions],
            "questions_by_priority": {
                priority: [q.to_dict() for q in qs]
                for priority, qs in batch_result.questions_by_priority.items()
            },
            "errors": batch_result.errors
        }


__all__ = ["BatchClarificationResult", "ClarificationDelegator"]