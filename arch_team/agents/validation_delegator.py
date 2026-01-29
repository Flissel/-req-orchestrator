# -*- coding: utf-8 -*-
"""
Validation Delegator Agent for Parallel Requirements Validation.

Coordinates parallel validation using:
- AsyncSemaphore for rate-limiting
- asyncio.gather for parallel execution
- SSE streaming for real-time progress updates

Part of the AutoGen Event-based parallel validation system.
See: arch_team/PARALLEL_VALIDATION_DESIGN.md
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from .validation_worker import ValidationTask, ValidationResult, ValidationWorkerAgent

logger = logging.getLogger("arch_team.validation_delegator")


@dataclass
class BatchValidationResult:
    """Aggregated results from parallel validation."""
    total_count: int
    passed_count: int
    failed_count: int
    error_count: int
    results: List[ValidationResult] = field(default_factory=list)
    total_time_ms: int = 0
    avg_time_per_item_ms: int = 0


class ValidationDelegatorAgent:
    """
    Coordinates parallel requirement validation with configurable worker pool.
    
    Features:
    - Configurable max_concurrent via environment variable
    - AsyncSemaphore-based rate limiting
    - SSE streaming for real-time progress updates
    - Graceful error handling per requirement
    
    Usage:
        delegator = ValidationDelegatorAgent(max_concurrent=5)
        result = await delegator.validate_batch(
            requirements=requirements,
            correlation_id="session-123"
        )
    """
    
    def __init__(
        self,
        max_concurrent: Optional[int] = None,
        sse_callback: Optional[Callable[[str, str, str], None]] = None
    ):
        """
        Initialize the validation delegator.
        
        Args:
            max_concurrent: Maximum parallel validations (default from env)
            sse_callback: Optional callback(correlation_id, message_type, message) for SSE
        """
        self.max_concurrent = max_concurrent or int(
            os.environ.get("VALIDATION_MAX_CONCURRENT", "5")
        )
        self.sse_callback = sse_callback
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        logger.info(f"ValidationDelegator initialized with max_concurrent={self.max_concurrent}")
    
    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create the semaphore (must be created in async context)."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)
        return self._semaphore
    
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
    
    async def validate_batch(
        self,
        requirements: List[Dict[str, Any]],
        *,
        correlation_id: Optional[str] = None,
        criteria_keys: Optional[List[str]] = None,
        threshold: float = 0.7
    ) -> BatchValidationResult:
        """
        Validate a batch of requirements in parallel.
        
        Args:
            requirements: List of requirement dicts with req_id, title, tag
            correlation_id: Session ID for SSE streaming
            criteria_keys: Optional quality criteria to check
            threshold: Quality threshold (default 0.7)
        
        Returns:
            BatchValidationResult with aggregated statistics and individual results
        """
        start_time = time.time()
        
        if not requirements:
            return BatchValidationResult(
                total_count=0,
                passed_count=0,
                failed_count=0,
                error_count=0,
                results=[]
            )
        
        logger.info(f"Starting parallel validation of {len(requirements)} requirements "
                   f"(max_concurrent={self.max_concurrent})")
        
        self._send_sse(
            correlation_id,
            "ValidationDelegator",
            f"🚀 Starting parallel validation of {len(requirements)} requirements "
            f"with {self.max_concurrent} workers..."
        )
        
        # Create validation tasks
        tasks = [
            ValidationTask(
                req_id=req.get("req_id", f"req-{idx}"),
                text=req.get("title", req.get("text", "")),
                criteria_keys=criteria_keys,
                threshold=threshold,
                tag=req.get("tag"),
                index=idx
            )
            for idx, req in enumerate(requirements)
        ]
        
        # Get semaphore (creates if needed)
        semaphore = self._get_semaphore()
        
        # Track progress
        completed = 0
        total = len(tasks)
        
        def progress_callback(worker_id: str, task_completed: int, task_total: int, message: str):
            nonlocal completed
            completed += 1
            if completed % 5 == 0 or completed == total:
                self._send_sse(
                    correlation_id,
                    "ValidationDelegator",
                    f"⏳ Progress: {completed}/{total} validated..."
                )
        
        # Create workers and validate in parallel
        async def validate_with_worker(task: ValidationTask) -> ValidationResult:
            worker = ValidationWorkerAgent(
                worker_id=f"worker-{task.index % self.max_concurrent}",
                semaphore=semaphore,
                progress_callback=progress_callback
            )
            return await worker.validate(task, total)
        
        # Execute all validations in parallel (semaphore limits concurrency)
        results = await asyncio.gather(
            *[validate_with_worker(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results
        validation_results: List[ValidationResult] = []
        passed_count = 0
        failed_count = 0
        error_count = 0
        
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle unexpected exceptions
                validation_results.append(ValidationResult(
                    req_id=tasks[idx].req_id,
                    title=tasks[idx].text,
                    score=0.0,
                    verdict="error",
                    tag=tasks[idx].tag,
                    error=str(result)
                ))
                error_count += 1
            else:
                validation_results.append(result)
                if result.verdict == "pass":
                    passed_count += 1
                elif result.verdict == "error":
                    error_count += 1
                else:
                    failed_count += 1
        
        total_time_ms = int((time.time() - start_time) * 1000)
        avg_time_ms = total_time_ms // len(requirements) if requirements else 0
        
        logger.info(f"Parallel validation completed in {total_time_ms}ms: "
                   f"{passed_count} passed, {failed_count} failed, {error_count} errors")
        
        self._send_sse(
            correlation_id,
            "ValidationDelegator",
            f"✅ Parallel validation complete in {total_time_ms/1000:.1f}s: "
            f"{passed_count} passed, {failed_count} failed, {error_count} errors"
        )
        
        return BatchValidationResult(
            total_count=len(requirements),
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            results=validation_results,
            total_time_ms=total_time_ms,
            avg_time_per_item_ms=avg_time_ms
        )
    
    def to_dict_results(self, batch_result: BatchValidationResult) -> List[Dict[str, Any]]:
        """
        Convert BatchValidationResult to list of dicts for JSON serialization.
        
        Args:
            batch_result: The batch validation result
        
        Returns:
            List of result dicts compatible with existing code
        """
        return [
            {
                "req_id": r.req_id,
                "title": r.title,
                "score": round(r.score, 2),
                "verdict": r.verdict,
                "evaluation": r.evaluation,
                "tag": r.tag,
                "error": r.error,
                "worker_id": r.worker_id,
                "processing_time_ms": r.processing_time_ms
            }
            for r in batch_result.results
        ]


# Convenience function for direct use
async def validate_requirements_parallel(
    requirements: List[Dict[str, Any]],
    max_concurrent: int = 5,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function for parallel requirement validation.
    
    Args:
        requirements: List of requirement dicts
        max_concurrent: Max parallel workers
        correlation_id: Session ID for SSE
    
    Returns:
        Dict with validated_count, passed, failed, details
    """
    delegator = ValidationDelegatorAgent(max_concurrent=max_concurrent)
    result = await delegator.validate_batch(
        requirements=requirements,
        correlation_id=correlation_id
    )
    
    return {
        "validated_count": result.total_count,
        "passed": result.passed_count,
        "failed": result.failed_count,
        "errors": result.error_count,
        "total_time_ms": result.total_time_ms,
        "details": delegator.to_dict_results(result)
    }


__all__ = [
    "ValidationDelegatorAgent",
    "BatchValidationResult",
    "validate_requirements_parallel"
]