# -*- coding: utf-8 -*-
"""
Rewrite Worker Agent for Feedback-based Requirement Improvement.

Uses validation feedback to intelligently rewrite failed requirements
following IEEE 29148 standards.

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

logger = logging.getLogger("arch_team.rewrite_worker")


@dataclass
class RewriteTask:
    """A single requirement rewrite task with validation feedback."""
    req_id: str
    original_text: str
    score: float
    evaluation: List[Dict[str, Any]]  # Failed criteria with feedback
    tag: Optional[str] = None
    index: int = 0  # Position in batch for progress tracking
    attempt: int = 1  # Current rewrite attempt number


@dataclass
class RewriteResult:
    """Result from rewriting a single requirement."""
    req_id: str
    original_text: str
    rewritten_text: str
    improvement_summary: str
    addressed_criteria: List[str]  # Which criteria were targeted
    attempt: int = 1
    tag: Optional[str] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    processing_time_ms: int = 0


class RewriteWorkerAgent:
    """
    Single worker for parallel requirement rewriting.
    
    Uses AsyncSemaphore for rate-limiting across multiple workers.
    Takes validation feedback to generate targeted improvements.
    
    Usage:
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent
        worker = RewriteWorkerAgent("rewrite-worker-1", semaphore)
        result = await worker.rewrite(task)
    """
    
    # IEEE 29148 Template for requirements
    IEEE_29148_TEMPLATE = """
The system shall [ACTION] [OBJECT] [CONSTRAINT].

Acceptance Criteria:
- GIVEN [precondition]
- WHEN [trigger]
- THEN [expected outcome]
- AND [additional verification]
"""

    # Mapping from criteria to specific improvement instructions
    CRITERIA_IMPROVEMENTS = {
        "clarity": "Use precise, unambiguous language. Define all technical terms.",
        "testability": "Add specific acceptance criteria with GIVEN-WHEN-THEN format.",
        "measurability": "Include quantifiable metrics (numbers, percentages, time limits).",
        "atomic": "Focus on a single, indivisible requirement. Split compound requirements.",
        "design_independent": "Describe WHAT, not HOW. Avoid implementation details.",
        "unambiguous": "Remove vague terms like 'should', 'may', 'approximately'. Be explicit.",
        "concise": "Remove unnecessary words while keeping all essential information.",
        "consistent_language": "Use standard terminology consistently throughout.",
        "purpose_independent": "Focus on the requirement itself, not the business rationale.",
        "follows_template": "Use structured format: Actor + Action + Object + Constraint + Acceptance."
    }
    
    def __init__(
        self,
        worker_id: str,
        semaphore: asyncio.Semaphore,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ):
        """
        Initialize rewrite worker.
        
        Args:
            worker_id: Unique identifier for this worker
            semaphore: Shared AsyncSemaphore for rate limiting
            progress_callback: Optional callback(worker_id, completed, total, message)
        """
        self.worker_id = worker_id
        self.semaphore = semaphore
        self.progress_callback = progress_callback
        self._timeout = int(os.environ.get("REWRITE_TIMEOUT", "60"))
    
    def _build_rewrite_prompt(self, task: RewriteTask) -> str:
        """
        Build the LLM prompt for rewriting based on validation feedback.
        
        Args:
            task: RewriteTask with original text and evaluation feedback
        
        Returns:
            Formatted prompt string for the LLM
        """
        # Extract failed criteria
        failed_criteria = []
        for eval_item in task.evaluation:
            if not eval_item.get("passed", True):
                criterion = eval_item.get("criterion", "unknown")
                feedback = eval_item.get("feedback", "No feedback")
                score = eval_item.get("score", 0.0)
                failed_criteria.append({
                    "criterion": criterion,
                    "feedback": feedback,
                    "score": score,
                    "improvement": self.CRITERIA_IMPROVEMENTS.get(criterion, "Improve this aspect.")
                })
        
        # Build the prompt
        prompt = f"""You are a Requirements Engineering expert following IEEE 29148 standards.

TASK: Rewrite the following requirement to address ALL failed quality criteria.

ORIGINAL REQUIREMENT:
"{task.original_text}"

FAILED QUALITY CRITERIA ({len(failed_criteria)} issues):
"""
        
        for i, fc in enumerate(failed_criteria, 1):
            prompt += f"""
{i}. {fc['criterion'].upper()} (Score: {fc['score']:.2f})
   Problem: {fc['feedback']}
   Solution: {fc['improvement']}
"""
        
        prompt += f"""

REQUIRED OUTPUT FORMAT (IEEE 29148):
{self.IEEE_29148_TEMPLATE}

RULES:
1. Address EVERY failed criterion listed above
2. Use precise, measurable language (specific numbers, not "fast" or "small")
3. Include acceptance criteria in GIVEN-WHEN-THEN format
4. Keep the original intent and functionality
5. Write in English
6. Output ONLY the rewritten requirement, nothing else

REWRITTEN REQUIREMENT:
"""
        return prompt
    
    async def rewrite(self, task: RewriteTask, total_tasks: int = 1) -> RewriteResult:
        """
        Rewrite a single requirement with rate limiting.
        
        Args:
            task: RewriteTask with requirement details and feedback
            total_tasks: Total number of tasks in batch (for progress)
        
        Returns:
            RewriteResult with rewritten text and improvement summary
        """
        start_time = time.time()
        
        # Acquire semaphore slot (blocks if max_concurrent reached)
        async with self.semaphore:
            logger.debug(f"[{self.worker_id}] Starting rewrite for {task.req_id} (attempt {task.attempt})")
            
            if self.progress_callback:
                self.progress_callback(
                    self.worker_id,
                    task.index + 1,
                    total_tasks,
                    f"Rewriting {task.req_id} (attempt {task.attempt})..."
                )
            
            try:
                # Build the prompt
                prompt = self._build_rewrite_prompt(task)
                
                # Call LLM (wrapped in asyncio.to_thread for blocking HTTP call)
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_rewrite_llm,
                        prompt
                    ),
                    timeout=self._timeout
                )
                
                processing_time = int((time.time() - start_time) * 1000)
                
                # Extract addressed criteria
                addressed = [
                    eval_item.get("criterion", "unknown")
                    for eval_item in task.evaluation
                    if not eval_item.get("passed", True)
                ]
                
                return RewriteResult(
                    req_id=task.req_id,
                    original_text=task.original_text,
                    rewritten_text=result.get("rewritten_text", task.original_text),
                    improvement_summary=result.get("summary", f"Addressed {len(addressed)} criteria"),
                    addressed_criteria=addressed,
                    attempt=task.attempt,
                    tag=task.tag,
                    error=result.get("error"),
                    worker_id=self.worker_id,
                    processing_time_ms=processing_time
                )
                
            except asyncio.TimeoutError:
                logger.warning(f"[{self.worker_id}] Timeout for {task.req_id}")
                return RewriteResult(
                    req_id=task.req_id,
                    original_text=task.original_text,
                    rewritten_text=task.original_text,
                    improvement_summary="Timeout - no changes applied",
                    addressed_criteria=[],
                    attempt=task.attempt,
                    tag=task.tag,
                    error=f"Timeout after {self._timeout}s",
                    worker_id=self.worker_id,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
            except Exception as e:
                logger.error(f"[{self.worker_id}] Error for {task.req_id}: {e}")
                return RewriteResult(
                    req_id=task.req_id,
                    original_text=task.original_text,
                    rewritten_text=task.original_text,
                    improvement_summary=f"Error: {str(e)}",
                    addressed_criteria=[],
                    attempt=task.attempt,
                    tag=task.tag,
                    error=str(e),
                    worker_id=self.worker_id,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
    
    def _call_rewrite_llm(self, prompt: str) -> Dict[str, Any]:
        """
        Call the LLM API to rewrite the requirement.
        
        This is run in a thread pool to avoid blocking the event loop.
        """
        try:
            from ..model.openai_adapter import OpenAIAdapter
            
            adapter = OpenAIAdapter()
            
            # Use create method (OpenAIAdapter's main method)
            messages = [
                {
                    "role": "system",
                    "content": "You are a Requirements Engineering expert. Output ONLY the rewritten requirement, no explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = adapter.create(
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent output
            )
            
            # Response is already a string content
            rewritten_text = response.strip() if isinstance(response, str) else str(response).strip()
            
            # Clean up any markdown formatting
            if rewritten_text.startswith("```"):
                lines = rewritten_text.split("\n")
                rewritten_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            return {
                "rewritten_text": rewritten_text,
                "summary": "Successfully rewritten using IEEE 29148 template"
            }
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "rewritten_text": "",
                "error": str(e),
                "summary": f"LLM call failed: {e}"
            }


__all__ = ["RewriteTask", "RewriteResult", "RewriteWorkerAgent"]