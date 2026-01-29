# -*- coding: utf-8 -*-
"""
Validation Worker Agent for Parallel Requirements Validation.

Uses AsyncSemaphore for rate-limiting and provides real-time progress updates
via SSE streaming to the frontend.

Part of the AutoGen Event-based parallel validation system.
See: arch_team/PARALLEL_VALIDATION_DESIGN.md
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("arch_team.validation_worker")


@dataclass
class ValidationTask:
    """A single requirement validation task."""
    req_id: str
    text: str
    criteria_keys: Optional[List[str]] = None
    threshold: float = 0.7
    tag: Optional[str] = None
    index: int = 0  # Position in batch for progress tracking


@dataclass
class ValidationResult:
    """Result from validating a single requirement."""
    req_id: str
    title: str
    score: float
    verdict: str  # pass | fail | error
    evaluation: List[Dict[str, Any]] = field(default_factory=list)
    tag: Optional[str] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    processing_time_ms: int = 0


class ValidationWorkerAgent:
    """
    Single worker for parallel requirement validation.
    
    Uses AsyncSemaphore for rate-limiting across multiple workers.
    Reports progress via callback for SSE streaming.
    
    Usage:
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent
        worker = ValidationWorkerAgent("worker-1", semaphore)
        result = await worker.validate(task)
    """
    
    def __init__(
        self,
        worker_id: str,
        semaphore: asyncio.Semaphore,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ):
        """
        Initialize validation worker.
        
        Args:
            worker_id: Unique identifier for this worker
            semaphore: Shared AsyncSemaphore for rate limiting
            progress_callback: Optional callback(worker_id, completed, total, message)
        """
        self.worker_id = worker_id
        self.semaphore = semaphore
        self.progress_callback = progress_callback
        self._timeout = int(os.environ.get("VALIDATION_TIMEOUT", "120"))
    
    async def validate(self, task: ValidationTask, total_tasks: int = 1) -> ValidationResult:
        """
        Validate a single requirement with rate limiting.
        
        Args:
            task: ValidationTask with requirement details
            total_tasks: Total number of tasks in batch (for progress)
        
        Returns:
            ValidationResult with score, verdict, and evaluation details
        """
        start_time = time.time()
        
        # Acquire semaphore slot (blocks if max_concurrent reached)
        async with self.semaphore:
            logger.debug(f"[{self.worker_id}] Starting task {task.req_id}")
            
            if self.progress_callback:
                self.progress_callback(
                    self.worker_id,
                    task.index + 1,
                    total_tasks,
                    f"Validating {task.req_id}..."
                )
            
            try:
                # Call validation API (wrapped in asyncio.to_thread for blocking HTTP call)
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_validation_api,
                        task
                    ),
                    timeout=self._timeout
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                return ValidationResult(
                    req_id=task.req_id,
                    title=task.text,
                    score=result.get("score", 0.0),
                    verdict=result.get("verdict", "fail"),
                    evaluation=result.get("evaluation", []),
                    tag=task.tag,
                    error=result.get("error"),
                    worker_id=self.worker_id,
                    processing_time_ms=processing_time
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"[{self.worker_id}] Timeout for {task.req_id}")
                return ValidationResult(
                    req_id=task.req_id,
                    title=task.text,
                    score=0.0,
                    verdict="error",
                    tag=task.tag,
                    error=f"Timeout after {self._timeout}s",
                    worker_id=self.worker_id,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
            except Exception as e:
                logger.error(f"[{self.worker_id}] Error for {task.req_id}: {e}")
                return ValidationResult(
                    req_id=task.req_id,
                    title=task.text,
                    score=0.0,
                    verdict="error",
                    tag=task.tag,
                    error=str(e),
                    worker_id=self.worker_id,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )

    def _call_validation_api(self, task: ValidationTask) -> Dict[str, Any]:
        """
        Call the validation API synchronously.
        
        This is run in a thread pool to avoid blocking the event loop.
        """
        from ..tools.validation_tools import evaluate_requirement
        
        return evaluate_requirement(
            requirement_text=task.text,
            criteria_keys=task.criteria_keys
        )


__all__ = ["ValidationTask", "ValidationResult", "ValidationWorkerAgent"]