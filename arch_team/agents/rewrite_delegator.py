# -*- coding: utf-8 -*-
"""
Rewrite Delegator Agent for Parallel Requirement Improvement.

Coordinates parallel rewriting using:
- AsyncSemaphore for rate-limiting
- asyncio.gather for parallel execution
- Optional re-validation loop
- SSE streaming for real-time progress updates

Part of the AutoGen Event-based parallel system.
See: arch_team/REQUIREMENTS_VALIDATION_DESIGN.md
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from .rewrite_worker import RewriteTask, RewriteResult, RewriteWorkerAgent
from .validation_worker import ValidationTask, ValidationResult, ValidationWorkerAgent

logger = logging.getLogger("arch_team.rewrite_delegator")


@dataclass
class BatchRewriteResult:
    """Aggregated results from parallel rewriting."""
    total_count: int
    rewritten_count: int
    improved_count: int  # Successfully improved after re-validation
    unchanged_count: int
    error_count: int
    results: List[RewriteResult] = field(default_factory=list)
    total_time_ms: int = 0
    avg_time_per_item_ms: int = 0


class RewriteDelegatorAgent:
    """
    Coordinates parallel requirement rewriting with configurable worker pool.
    
    Features:
    - Configurable max_concurrent via environment variable
    - AsyncSemaphore-based rate limiting
    - Optional re-validation loop with max attempts
    - SSE streaming for real-time progress updates
    - Graceful error handling per requirement
    
    Usage:
        delegator = RewriteDelegatorAgent(max_concurrent=3)
        result = await delegator.rewrite_batch(
            failed_requirements=failed_reqs,
            correlation_id="session-123"
        )
    """
    
    def __init__(
        self,
        max_concurrent: Optional[int] = None,
        max_attempts: int = 3,
        target_score: float = 0.7,
        enable_revalidation: bool = True,
        sse_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        Initialize the rewrite delegator.
        
        Args:
            max_concurrent: Maximum parallel rewrites (default from env)
            max_attempts: Maximum rewrite attempts per requirement
            target_score: Target validation score for re-validation
            enable_revalidation: Whether to re-validate after rewriting
            sse_callback: Optional callback(correlation_id, message_type, message) for SSE
        """
        self.max_concurrent = max_concurrent or int(
            os.environ.get("REWRITE_MAX_CONCURRENT", "3")
        )
        self.max_attempts = max_attempts
        self.target_score = target_score
        self.enable_revalidation = enable_revalidation
        self.sse_callback = sse_callback
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._validation_semaphore: Optional[asyncio.Semaphore] = None
        
        logger.info(f"RewriteDelegator initialized with max_concurrent={self.max_concurrent}, "
                   f"max_attempts={self.max_attempts}, target_score={self.target_score}")
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create the rewrite semaphore (must be created in async context)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
    def _get_validation_semaphore(self) -> asyncio.Semaphore:
        """Get or create the validation semaphore for re-validation."""
        if self._validation_semaphore is None:
            # Use more concurrent slots for validation (it's faster)
            self._validation_semaphore = asyncio.Semaphore(
                int(os.environ.get("VALIDATION_MAX_CONCURRENT", "5"))
            )
        return self._validation_semaphore
    
    def _send_sse(self, correlation_id: Optional[str], agent: str, message: str) -> None:
        """Send SSE message to frontend if callback is configured."""
        if self.sse_callback and correlation_id:
            try:
                self.sse_callback(correlation_id, agent, message)
            except Exception as e:
                logger.warning(f"SSE callback failed: {e}")
        else:
            # Fallback: Try to use workflow_streams directly
            if correlation_id:
                try:
                    from arch_team.service import workflow_streams
                    from datetime import datetime
                    
                    queue = workflow_streams.get(correlation_id)
                    if queue:
                        queue.put({
                            "type": "agent_message",
                            "agent": agent,
                            "message": message,
                            "timestamp": datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.debug(f"Direct SSE send failed: {e}")
    
    async def rewrite_batch(
        self,
        failed_requirements: List[Dict[str, Any]],
        *,
        correlation_id: Optional[str] = None
    ) -> BatchRewriteResult:
        """
        Rewrite a batch of failed requirements in parallel.
        
        Args:
            failed_requirements: List of requirement dicts with:
                - req_id: Requirement ID
                - title/text: Original requirement text
                - score: Validation score (should be < target_score)
                - evaluation: List of criterion evaluations
                - tag: Optional category
            correlation_id: Session ID for SSE streaming
        
        Returns:
            BatchRewriteResult with aggregated statistics and individual results
        """
        start_time = time.time()
        
        if not failed_requirements:
            return BatchRewriteResult(
                total_count=0,
                rewritten_count=0,
                improved_count=0,
                unchanged_count=0,
                error_count=0,
                results=[]
            )
        
        logger.info(f"Starting parallel rewrite of {len(failed_requirements)} requirements "
                   f"(max_concurrent={self.max_concurrent}, max_attempts={self.max_attempts})")
        
        self._send_sse(
            correlation_id,
            "RewriteDelegator",
            f"✍️ Starting parallel rewrite of {len(failed_requirements)} requirements "
            f"with {self.max_concurrent} workers..."
        )
        
        # Create rewrite tasks
        tasks = [
            RewriteTask(
                req_id=req.get("req_id", f"req-{idx}"),
                original_text=req.get("title", req.get("text", "")),
                score=req.get("score", 0.0),
                evaluation=req.get("evaluation", []),
                tag=req.get("tag"),
                index=idx,
                attempt=1
            )
            for idx, req in enumerate(failed_requirements)
        ]
        
        # Get semaphore (creates if needed)
        semaphore = self._get_semaphore()
        
        # Track progress
        completed = 0
        total = len(tasks)
        
        def progress_callback(worker_id: str, task_completed: int, task_total: int, message: str):
            nonlocal completed
            completed += 1
            if completed % 3 == 0 or completed == total:
                self._send_sse(
                    correlation_id,
                    "RewriteDelegator",
                    f"✍️ Progress: {completed}/{total} rewritten..."
                )
        
        # Rewrite all requirements in parallel
        async def rewrite_with_worker(task: RewriteTask) -> RewriteResult:
            worker = RewriteWorkerAgent(
                worker_id=f"rewrite-worker-{task.index % self.max_concurrent}",
                semaphore=semaphore,
                progress_callback=progress_callback
            )
            result = await worker.rewrite(task, total)
            
            # Optional: Re-validate and retry if needed
            if self.enable_revalidation and not result.error:
                result = await self._revalidate_and_retry(
                    task, result, worker, correlation_id
                )
            
            return result
        
        # Execute all rewrites in parallel (semaphore limits concurrency)
        results = await asyncio.gather(
            *[rewrite_with_worker(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results
        rewrite_results: List[RewriteResult] = []
        rewritten_count = 0
        improved_count = 0
        unchanged_count = 0
        error_count = 0
        
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle unexpected exceptions
                rewrite_results.append(RewriteResult(
                    req_id=tasks[idx].req_id,
                    original_text=tasks[idx].original_text,
                    rewritten_text=tasks[idx].original_text,
                    improvement_summary=f"Error: {str(result)}",
                    addressed_criteria=[],
                    attempt=tasks[idx].attempt,
                    tag=tasks[idx].tag,
                    error=str(result)
                ))
                error_count += 1
            else:
                rewrite_results.append(result)
                if result.error:
                    error_count += 1
                elif result.rewritten_text != result.original_text:
                    rewritten_count += 1
                    if hasattr(result, 'new_score') and result.new_score >= self.target_score:
                        improved_count += 1
                else:
                    unchanged_count += 1
        
        total_time_ms = int((time.time() - start_time) * 1000)
        avg_time_ms = total_time_ms // len(failed_requirements) if failed_requirements else 0
        
        logger.info(f"Parallel rewrite completed in {total_time_ms}ms: "
                   f"{rewritten_count} rewritten, {improved_count} improved, "
                   f"{unchanged_count} unchanged, {error_count} errors")
        
        self._send_sse(
            correlation_id,
            "RewriteDelegator",
            f"✅ Parallel rewrite complete in {total_time_ms/1000:.1f}s: "
            f"{rewritten_count} rewritten, {improved_count} improved to score >= {self.target_score}"
        )
        
        return BatchRewriteResult(
            total_count=len(failed_requirements),
            rewritten_count=rewritten_count,
            improved_count=improved_count,
            unchanged_count=unchanged_count,
            error_count=error_count,
            results=rewrite_results,
            total_time_ms=total_time_ms,
            avg_time_per_item_ms=avg_time_ms
        )
    
    async def _revalidate_and_retry(
        self,
        original_task: RewriteTask,
        rewrite_result: RewriteResult,
        worker: RewriteWorkerAgent,
        correlation_id: Optional[str]
    ) -> RewriteResult:
        """
        Re-validate the rewritten requirement and retry if needed.
        
        Args:
            original_task: Original rewrite task
            rewrite_result: Result from first rewrite attempt
            worker: The worker to use for retries
            correlation_id: Session ID for SSE
        
        Returns:
            Final RewriteResult, possibly with multiple attempts
        """
        validation_semaphore = self._get_validation_semaphore()
        current_result = rewrite_result
        current_text = rewrite_result.rewritten_text
        
        for attempt in range(1, self.max_attempts + 1):
            # Skip validation if text is unchanged or empty
            if not current_text or current_text == original_task.original_text:
                break
            
            # Re-validate the rewritten requirement
            validation_worker = ValidationWorkerAgent(
                worker_id=f"val-worker-{original_task.index}",
                semaphore=validation_semaphore
            )
            
            val_task = ValidationTask(
                req_id=original_task.req_id,
                text=current_text,
                threshold=self.target_score,
                tag=original_task.tag,
                index=original_task.index
            )
            
            val_result = await validation_worker.validate(val_task)
            
            # Check if we've reached the target score
            if val_result.score >= self.target_score:
                logger.info(f"[{original_task.req_id}] Reached target score {val_result.score:.2f} "
                           f"on attempt {attempt}")
                
                # Update result with new score
                current_result.improvement_summary = (
                    f"Improved from {original_task.score:.2f} to {val_result.score:.2f} "
                    f"after {attempt} attempt(s)"
                )
                # Store new score as attribute
                setattr(current_result, 'new_score', val_result.score)
                setattr(current_result, 'new_evaluation', val_result.evaluation)
                break
            
            # If not good enough and more attempts remain, retry
            if attempt < self.max_attempts:
                logger.info(f"[{original_task.req_id}] Score {val_result.score:.2f} < {self.target_score}, "
                           f"retrying (attempt {attempt + 1}/{self.max_attempts})")
                
                self._send_sse(
                    correlation_id,
                    "RewriteDelegator",
                    f"🔄 {original_task.req_id}: Score {val_result.score:.2f}, retrying..."
                )
                
                # Create new task with updated evaluation feedback
                retry_task = RewriteTask(
                    req_id=original_task.req_id,
                    original_text=current_text,  # Use the rewritten text as input
                    score=val_result.score,
                    evaluation=val_result.evaluation,
                    tag=original_task.tag,
                    index=original_task.index,
                    attempt=attempt + 1
                )
                
                # Rewrite again
                current_result = await worker.rewrite(retry_task, 1)
                current_text = current_result.rewritten_text
            else:
                # Max attempts reached, keep best version
                logger.info(f"[{original_task.req_id}] Max attempts reached. "
                           f"Final score: {val_result.score:.2f}")
                current_result.improvement_summary = (
                    f"Max attempts reached. Score improved from {original_task.score:.2f} "
                    f"to {val_result.score:.2f}"
                )
                setattr(current_result, 'new_score', val_result.score)
                setattr(current_result, 'new_evaluation', val_result.evaluation)
        
        return current_result
    
    def to_dict_results(self, batch_result: BatchRewriteResult) -> List[Dict[str, Any]]:
        """
        Convert BatchRewriteResult to list of dicts for JSON serialization.
        
        Args:
            batch_result: The batch rewrite result
        
        Returns:
            List of result dicts compatible with existing code
        """
        return [
            {
                "req_id": r.req_id,
                "original_text": r.original_text,
                "rewritten_text": r.rewritten_text,
                "improvement_summary": r.improvement_summary,
                "addressed_criteria": r.addressed_criteria,
                "attempt": r.attempt,
                "tag": r.tag,
                "error": r.error,
                "worker_id": r.worker_id,
                "processing_time_ms": r.processing_time_ms,
                "new_score": getattr(r, 'new_score', None),
                "new_evaluation": getattr(r, 'new_evaluation', None)
            }
            for r in batch_result.results
        ]


# Convenience function for direct use
async def rewrite_requirements_parallel(
    failed_requirements: List[Dict[str, Any]],
    max_concurrent: int = 3,
    max_attempts: int = 3,
    target_score: float = 0.7,
    enable_revalidation: bool = True,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for parallel requirement rewriting.
    
    Args:
        failed_requirements: List of failed requirement dicts
        max_concurrent: Max parallel workers
        max_attempts: Max rewrite attempts per requirement
        target_score: Target validation score
        enable_revalidation: Whether to re-validate after rewriting
        correlation_id: Session ID for SSE
    
    Returns:
        Dict with rewritten_count, improved, unchanged, errors, details
    """
    delegator = RewriteDelegatorAgent(
        max_concurrent=max_concurrent,
        max_attempts=max_attempts,
        target_score=target_score,
        enable_revalidation=enable_revalidation
    )
    result = await delegator.rewrite_batch(
        failed_requirements=failed_requirements,
        correlation_id=correlation_id
    )
    
    return {
        "total_count": result.total_count,
        "rewritten_count": result.rewritten_count,
        "improved_count": result.improved_count,
        "unchanged_count": result.unchanged_count,
        "error_count": result.error_count,
        "total_time_ms": result.total_time_ms,
        "details": delegator.to_dict_results(result)
    }


__all__ = [
    "RewriteDelegatorAgent",
    "BatchRewriteResult",
    "rewrite_requirements_parallel"
]