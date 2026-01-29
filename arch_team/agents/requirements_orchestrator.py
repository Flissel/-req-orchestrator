# -*- coding: utf-8 -*-

"""
Requirements Orchestrator for Complete Iterative Workflow.

Coordinates the full requirements quality improvement cycle:

1. Validate all requirements against IEEE 29148 criteria
2. DECISION: DecisionMaker decides action for each failing requirement
3. Auto-rewrite fixable requirements using RewriteAgent
4. Split complex requirements into atomic ones
5. Auto-clarify missing information (AUTO mode) or wait for user
6. Loop until all requirements pass threshold

Supports two modes:

- AUTO (default): DecisionMaker makes all decisions autonomously
- MANUAL: User is asked to make decisions

Part of the Requirements-Management-System.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from .decision_maker_agent import (
    DecisionMakerAgent,
    DecisionAction,
    WorkflowMode,
    Decision,
    DecisionBatchResult
)

logger = logging.getLogger("arch_team.requirements_orchestrator")


@dataclass
class OrchestratorConfig:
    """Configuration for RequirementsOrchestrator."""
    quality_threshold: float = 0.7      # Min score to pass validation
    max_iterations: int = 5             # Max workflow iterations
    max_rewrite_attempts: int = 3       # Max rewrite attempts per requirement
    validation_concurrent: int = 10     # Concurrent validation workers (increased from 5)
    rewrite_concurrent: int = 10        # Concurrent rewrite workers (increased from 3)
    clarification_concurrent: int = 10  # Concurrent clarification workers (increased from 5)
    decision_concurrent: int = 10       # Concurrent decision workers (increased from 5)
    auto_fix_threshold: float = 0.5     # Below this, need user input
    accept_threshold: float = 0.65      # Above this, may accept as-is
    wait_for_answers_timeout: int = 300 # Timeout waiting for user answers (seconds)
    mode: WorkflowMode = WorkflowMode.AUTO  # AUTO or MANUAL mode

    @classmethod
    def from_env(cls) -> "OrchestratorConfig":
        """Load configuration from environment variables."""
        mode_str = os.environ.get("WORKFLOW_MODE", "auto").lower()
        mode = WorkflowMode.AUTO if mode_str == "auto" else WorkflowMode.MANUAL
        
        return cls(
            quality_threshold=float(os.environ.get("QUALITY_THRESHOLD", "0.7")),
            max_iterations=int(os.environ.get("MAX_ITERATIONS", "5")),
            max_rewrite_attempts=int(os.environ.get("REWRITE_MAX_ATTEMPTS", "3")),
            validation_concurrent=int(os.environ.get("VALIDATION_MAX_CONCURRENT", "5")),
            rewrite_concurrent=int(os.environ.get("REWRITE_MAX_CONCURRENT", "3")),
            clarification_concurrent=int(os.environ.get("CLARIFICATION_MAX_CONCURRENT", "5")),
            decision_concurrent=int(os.environ.get("DECISION_MAX_CONCURRENT", "5")),
            auto_fix_threshold=float(os.environ.get("AUTO_FIX_THRESHOLD", "0.5")),
            accept_threshold=float(os.environ.get("ACCEPT_THRESHOLD", "0.65")),
            wait_for_answers_timeout=int(os.environ.get("CLARIFICATION_TIMEOUT", "300")),
            mode=mode
        )

@dataclass
class IterationResult:
    """Result from a single orchestrator iteration."""
    iteration: int
    total_requirements: int
    passed_count: int
    failed_count: int
    rewritten_count: int
    split_count: int = 0
    clarification_count: int = 0
    answered_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    validation_time_ms: int = 0
    decision_time_ms: int = 0
    rewrite_time_ms: int = 0
    clarification_time_ms: int = 0
    
    @property
    def pass_rate(self) -> float:
        if self.total_requirements == 0:
            return 0.0
        return self.passed_count / self.total_requirements

@dataclass
class OrchestratorResult:
    """Final result from running the orchestrator."""
    success: bool
    total_iterations: int
    final_pass_rate: float
    initial_pass_rate: float
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    iterations: List[IterationResult] = field(default_factory=list)
    pending_questions: List[Dict[str, Any]] = field(default_factory=list)
    split_requirements: List[Dict[str, Any]] = field(default_factory=list)
    accepted_requirements: List[Dict[str, Any]] = field(default_factory=list)
    rejected_requirements: List[Dict[str, Any]] = field(default_factory=list)
    total_time_ms: int = 0
    error: Optional[str] = None
    workflow_id: str = ""
    mode: str = "auto"
    
    @property
    def improved(self) -> bool:
        return self.final_pass_rate > self.initial_pass_rate

class RequirementsOrchestrator:
    """
    Orchestrator for complete requirements quality improvement workflow.
    
    In AUTO mode (default), the DecisionMaker LLM decides:
    - SPLIT: Break complex requirements into atomic ones
    - REWRITE: Auto-improve using RewriteAgent
    - ACCEPT: Accept as-is (good enough)
    - CLARIFY: Auto-answer clarification questions
    - REJECT: Cannot be improved, reject
    
    In MANUAL mode, the user makes decisions.
    
    Usage:
        orchestrator = RequirementsOrchestrator()
        result = await orchestrator.run(requirements, correlation_id)
    """
    
    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None
    ):
        """
        Initialize requirements orchestrator.
        
        Args:
            config: Orchestrator configuration (defaults to env vars)
            progress_callback: Optional callback(stage, completed, total, message)
        """
        self.config = config or OrchestratorConfig.from_env()
        self.progress_callback = progress_callback
        self.workflow_id = ""
        
        # Initialize DecisionMaker
        self.decision_maker = DecisionMakerAgent(
            mode=self.config.mode,
            accept_threshold=self.config.accept_threshold
        )
    
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
            
            queue = workflow_streams.get(correlation_id)
            if queue:
                message = {
                    "type": message_type,
                    "timestamp": datetime.now().isoformat(),
                    "workflow_id": self.workflow_id,
                    "mode": self.config.mode.value,
                    **kwargs
                }
                queue.put(message)
                logger.debug(f"[Stream] Sent {message_type}")
        except Exception as e:
            logger.error(f"Error sending to workflow stream: {e}")
    
    async def run(
        self,
        requirements: List[Dict[str, Any]],
        correlation_id: Optional[str] = None,
        wait_for_answers: bool = True,
        mode: Optional[WorkflowMode] = None
    ) -> OrchestratorResult:
        """
        Run the complete requirements orchestration workflow.
        
        Args:
            requirements: List of requirement dicts
            correlation_id: SSE session ID for streaming
            wait_for_answers: Whether to wait for user answers (MANUAL mode)
            mode: Override config mode for this run
        
        Returns:
            OrchestratorResult with final state and statistics
        """
        start_time = time.time()
        self.workflow_id = str(uuid.uuid4())[:8]
        
        # Override mode if specified
        if mode:
            self.config.mode = mode
            self.decision_maker.mode = mode
        
        is_auto = self.config.mode == WorkflowMode.AUTO
        
        logger.info(f"[{self.workflow_id}] Starting orchestrator with {len(requirements)} requirements "
                   f"in {self.config.mode.value.upper()} mode")
        
        self._send_to_workflow_stream(
            correlation_id,
            "orchestrator_started",
            total_requirements=len(requirements),
            mode=self.config.mode.value,
            config={
                "threshold": self.config.quality_threshold,
                "max_iterations": self.config.max_iterations,
                "auto_mode": is_auto
            }
        )
        
        # Track state
        current_requirements = requirements.copy()
        iterations: List[IterationResult] = []
        initial_pass_rate = 0.0
        all_split_requirements: List[Dict[str, Any]] = []
        all_accepted: List[Dict[str, Any]] = []
        all_rejected: List[Dict[str, Any]] = []
        
        try:
            for iteration in range(1, self.config.max_iterations + 1):
                logger.info(f"[{self.workflow_id}] === Iteration {iteration}/{self.config.max_iterations} ===")
                
                self._send_to_workflow_stream(
                    correlation_id,
                    "iteration_started",
                    iteration=iteration,
                    max_iterations=self.config.max_iterations,
                    mode=self.config.mode.value
                )
                
                # === PHASE 1: VALIDATE ===
                validation_result = await self._run_validation(
                    current_requirements,
                    correlation_id
                )
                
                passed_count = validation_result["passed_count"]
                failed_count = validation_result["failed_count"]
                validation_ms = validation_result["time_ms"]
                
                # Calculate pass rate
                pass_rate = passed_count / len(current_requirements) if current_requirements else 0.0
                
                # Store initial pass rate
                if iteration == 1:
                    initial_pass_rate = pass_rate
                
                logger.info(f"[{self.workflow_id}] Validation: {passed_count} passed, {failed_count} failed ({pass_rate:.1%})")
                
                # === CHECK: All passed? ===
                if failed_count == 0:
                    logger.info(f"[{self.workflow_id}] All requirements passed! Workflow complete.")
                    
                    iterations.append(IterationResult(
                        iteration=iteration,
                        total_requirements=len(current_requirements),
                        passed_count=passed_count,
                        failed_count=0,
                        rewritten_count=0,
                        validation_time_ms=validation_ms
                    ))
                    
                    return OrchestratorResult(
                        success=True,
                        total_iterations=iteration,
                        final_pass_rate=1.0,
                        initial_pass_rate=initial_pass_rate,
                        requirements=current_requirements,
                        iterations=iterations,
                        pending_questions=[],
                        split_requirements=all_split_requirements,
                        accepted_requirements=all_accepted,
                        rejected_requirements=all_rejected,
                        total_time_ms=int((time.time() - start_time) * 1000),
                        workflow_id=self.workflow_id,
                        mode=self.config.mode.value
                    )
                
                # === PHASE 2: DECISION (NEW!) ===
                decision_result = await self._run_decisions(
                    validation_result["failed_results"],
                    correlation_id
                )
                
                decision_ms = decision_result["time_ms"]
                decisions = decision_result["decisions"]
                
                logger.info(f"[{self.workflow_id}] Decisions: "
                           f"SPLIT={decision_result['split_count']}, "
                           f"REWRITE={decision_result['rewrite_count']}, "
                           f"ACCEPT={decision_result['accept_count']}, "
                           f"CLARIFY={decision_result['clarify_count']}, "
                           f"REJECT={decision_result['reject_count']}")

                
                # === PHASE 3: APPLY DECISIONS ===
                
                # 3a. Handle SPLIT decisions
                split_reqs = []
                for decision in decisions:
                    if decision.action == DecisionAction.SPLIT:
                        original_req = next(
                            (r for r in current_requirements if r.get("req_id") == decision.req_id),
                            None
                        )
                        if original_req and decision.split_suggestions:
                            new_reqs = await self.decision_maker.apply_split(
                                original_req,
                                decision.split_suggestions
                            )
                            split_reqs.extend(new_reqs)
                            all_split_requirements.extend(new_reqs)
                            # Remove original from current
                            current_requirements = [
                                r for r in current_requirements
                                if r.get("req_id") != decision.req_id
                            ]
                
                # Add split requirements to current
                current_requirements.extend(split_reqs)
                
                # 3b. Handle ACCEPT decisions
                for decision in decisions:
                    if decision.action == DecisionAction.ACCEPT:
                        accepted_req = next(
                            (r for r in current_requirements if r.get("req_id") == decision.req_id),
                            None
                        )
                        if accepted_req:
                            accepted_req["_accepted"] = True
                            accepted_req["_accept_reason"] = decision.reason
                            all_accepted.append(accepted_req)
                
                # 3c. Handle REJECT decisions
                for decision in decisions:
                    if decision.action == DecisionAction.REJECT:
                        rejected_req = next(
                            (r for r in current_requirements if r.get("req_id") == decision.req_id),
                            None
                        )
                        if rejected_req:
                            rejected_req["_rejected"] = True
                            rejected_req["_reject_reason"] = decision.reason
                            all_rejected.append(rejected_req)
                            # Remove from current
                            current_requirements = [
                                r for r in current_requirements
                                if r.get("req_id") != decision.req_id
                            ]
                
                # 3d. Handle REWRITE decisions
                rewrite_decisions = [d for d in decisions if d.action == DecisionAction.REWRITE]
                rewrite_reqs = [
                    r for r in validation_result["failed_results"]
                    if r.get("req_id") in [d.req_id for d in rewrite_decisions]
                ]
                
                rewrite_result = await self._run_rewrite(
                    rewrite_reqs,
                    correlation_id,
                    rewrite_decisions
                )
                
                rewritten_count = rewrite_result["rewritten_count"]
                rewrite_ms = rewrite_result["time_ms"]
                
                # Update requirements with rewritten text
                current_requirements = self._apply_rewrites(
                    current_requirements,
                    rewrite_result["rewrites"]
                )
                
                # 3e. Handle CLARIFY decisions
                clarify_decisions = [d for d in decisions if d.action == DecisionAction.CLARIFY]
                clarification_count = 0
                answered_count = 0
                clarification_ms = 0
                
                if clarify_decisions:
                    if is_auto:
                        # AUTO mode: Apply auto-generated clarification answers
                        clarify_start = time.time()
                        for decision in clarify_decisions:
                            if decision.clarification_answers:
                                original_req = next(
                                    (r for r in current_requirements if r.get("req_id") == decision.req_id),
                                    None
                                )
                                if original_req:
                                    improved_req = await self.decision_maker.apply_clarification_answers(
                                        original_req,
                                        decision.clarification_answers
                                    )
                                    # Update in list
                                    for i, r in enumerate(current_requirements):
                                        if r.get("req_id") == decision.req_id:
                                            current_requirements[i] = improved_req
                                            break
                                    answered_count += 1
                        
                        clarification_count = len(clarify_decisions)
                        clarification_ms = int((time.time() - clarify_start) * 1000)
                        
                        logger.info(f"[{self.workflow_id}] Auto-clarified {answered_count} requirements")
                    else:
                        # MANUAL mode: Generate questions and wait for user
                        clarify_reqs = [
                            r for r in validation_result["failed_results"]
                            if r.get("req_id") in [d.req_id for d in clarify_decisions]
                        ]
                        
                        clarification_result = await self._run_clarification(
                            clarify_reqs,
                            validation_result["validation_results"],
                            correlation_id
                        )
                        
                        clarification_count = clarification_result["question_count"]
                        clarification_ms = clarification_result["time_ms"]
                        
                        if wait_for_answers and clarification_count > 0:
                            answers_result = await self._wait_for_answers(
                                clarification_result["questions"],
                                correlation_id
                            )
                            
                            answered_count = answers_result["answered_count"]
                            current_requirements = self._apply_answers(
                                current_requirements,
                                answers_result["answers"]
                            )
                
                # Record iteration result
                iterations.append(IterationResult(
                    iteration=iteration,
                    total_requirements=len(current_requirements),
                    passed_count=passed_count,
                    failed_count=failed_count,
                    rewritten_count=rewritten_count,
                    split_count=len(split_reqs),
                    clarification_count=clarification_count,
                    answered_count=answered_count,
                    accepted_count=decision_result["accept_count"],
                    rejected_count=decision_result["reject_count"],
                    validation_time_ms=validation_ms,
                    decision_time_ms=decision_ms,
                    rewrite_time_ms=rewrite_ms,
                    clarification_time_ms=clarification_ms
                ))
                
                self._send_to_workflow_stream(
                    correlation_id,
                    "iteration_completed",
                    iteration=iteration,
                    passed=passed_count,
                    failed=failed_count,
                    split=len(split_reqs),
                    rewritten=rewritten_count,
                    accepted=decision_result["accept_count"],
                    rejected=decision_result["reject_count"],
                    clarified=answered_count
                )
                
                # If no progress was made, stop looping
                total_actions = (rewritten_count + len(split_reqs) + answered_count + 
                               decision_result["accept_count"] + decision_result["reject_count"])
                if total_actions == 0:
                    logger.warning(f"[{self.workflow_id}] No progress made in iteration {iteration}, stopping")
                    break
            
            # === FINAL VALIDATION ===
            final_validation = await self._run_validation(
                current_requirements,
                correlation_id
            )
            
            final_pass_rate = final_validation["passed_count"] / len(current_requirements) if current_requirements else 0.0
            
            # Get pending questions (MANUAL mode only)
            pending_questions = []
            if not is_auto:
                pending_questions = await self._get_pending_questions(correlation_id)
            
            total_time_ms = int((time.time() - start_time) * 1000)
            
            success = final_pass_rate >= self.config.quality_threshold or len(current_requirements) == 0
            
            self._send_to_workflow_stream(
                correlation_id,
                "orchestrator_completed",
                success=success,
                final_pass_rate=final_pass_rate,
                initial_pass_rate=initial_pass_rate,
                iterations=len(iterations),
                total_time_ms=total_time_ms,
                split_count=len(all_split_requirements),
                accepted_count=len(all_accepted),
                rejected_count=len(all_rejected),
                mode=self.config.mode.value
            )
            
            return OrchestratorResult(
                success=success,
                total_iterations=len(iterations),
                final_pass_rate=final_pass_rate,
                initial_pass_rate=initial_pass_rate,
                requirements=current_requirements,
                iterations=iterations,
                pending_questions=pending_questions,
                split_requirements=all_split_requirements,
                accepted_requirements=all_accepted,
                rejected_requirements=all_rejected,
                total_time_ms=total_time_ms,
                workflow_id=self.workflow_id,
                mode=self.config.mode.value
            )
            
        except Exception as e:
            logger.error(f"[{self.workflow_id}] Orchestrator failed: {e}", exc_info=True)
            
            self._send_to_workflow_stream(
                correlation_id,
                "orchestrator_failed",
                error=str(e)
            )
            
            return OrchestratorResult(
                success=False,
                total_iterations=len(iterations),
                final_pass_rate=0.0,
                initial_pass_rate=initial_pass_rate,
                requirements=current_requirements,
                iterations=iterations,
                error=str(e),
                total_time_ms=int((time.time() - start_time) * 1000),
                workflow_id=self.workflow_id,
                mode=self.config.mode.value
            )
    
    async def _run_decisions(
        self,
        failed_results: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run DecisionMaker to decide action for each failing requirement."""
        if not failed_results:
            return {
                "decisions": [],
                "split_count": 0,
                "rewrite_count": 0,
                "accept_count": 0,
                "clarify_count": 0,
                "reject_count": 0,
                "time_ms": 0
            }
        
        start = time.time()
        
        self._send_to_workflow_stream(
            correlation_id,
            "agent_message",
            agent="DecisionMaker",
            message=f"🧠 Analyzing {len(failed_results)} requirements to decide best action..."
        )
        
        # Prepare requirements for decision
        decision_reqs = [
            {
                "req_id": r.get("req_id"),
                "title": r.get("title"),
                "text": r.get("title"),
                "score": r.get("score", 0.0),
                "evaluation": r.get("evaluation", []),
                "tag": r.get("tag")
            }
            for r in failed_results
        ]
        
        batch_result = await self.decision_maker.decide_batch(decision_reqs)
        
        self._send_to_workflow_stream(
            correlation_id,
            "decision_completed",
            split=batch_result.split_count,
            rewrite=batch_result.rewrite_count,
            accept=batch_result.accept_count,
            clarify=batch_result.clarify_count,
            reject=batch_result.reject_count,
            time_ms=batch_result.total_time_ms
        )
        
        return {
            "decisions": batch_result.decisions,
            "split_count": batch_result.split_count,
            "rewrite_count": batch_result.rewrite_count,
            "accept_count": batch_result.accept_count,
            "clarify_count": batch_result.clarify_count,
            "reject_count": batch_result.reject_count,
            "time_ms": int((time.time() - start) * 1000)
        }
    
    async def _run_validation(
        self,
        requirements: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run validation phase."""
        from .validation_delegator import ValidationDelegatorAgent
        
        start = time.time()
        
        delegator = ValidationDelegatorAgent(
            max_concurrent=self.config.validation_concurrent
        )
        
        batch_result = await delegator.validate_batch(
            requirements=requirements,
            correlation_id=correlation_id
        )
        
        # Convert results
        validation_results = delegator.to_dict_results(batch_result)
        
        # Separate passed and failed
        passed_results = [r for r in validation_results if r["verdict"] == "pass"]
        failed_results = [r for r in validation_results if r["verdict"] == "fail"]
        
        return {
            "validation_results": validation_results,
            "passed_results": passed_results,
            "failed_results": failed_results,
            "passed_count": len(passed_results),
            "failed_count": len(failed_results),
            "time_ms": int((time.time() - start) * 1000)
        }
    
    async def _run_rewrite(
        self,
        failed_results: List[Dict[str, Any]],
        correlation_id: Optional[str],
        decisions: Optional[List[Decision]] = None
    ) -> Dict[str, Any]:
        """Run rewrite phase for failed requirements."""
        from .rewrite_delegator import RewriteDelegatorAgent
        
        if not failed_results:
            return {
                "rewrites": [],
                "rewritten_count": 0,
                "improved_count": 0,
                "time_ms": 0
            }
        
        start = time.time()
        
        delegator = RewriteDelegatorAgent(
            max_concurrent=self.config.rewrite_concurrent,
            max_attempts=self.config.max_rewrite_attempts,
            target_score=self.config.quality_threshold,
            enable_revalidation=True
        )
        
        # Prepare failed requirements for rewriting, including hints from decisions
        decision_lookup = {d.req_id: d for d in (decisions or [])}
        
        failed_for_rewrite = []
        for r in failed_results:
            req_data = {
                "req_id": r.get("req_id"),
                "text": r.get("title"),
                "score": r.get("score", 0.0),
                "evaluation": r.get("evaluation", []),
                "tag": r.get("tag")
            }
            
            # Add rewrite hints from decision if available
            decision = decision_lookup.get(r.get("req_id"))
            if decision and decision.rewrite_hints:
                req_data["rewrite_hints"] = decision.rewrite_hints
            
            failed_for_rewrite.append(req_data)
        
        batch_result = await delegator.rewrite_batch(
            failed_requirements=failed_for_rewrite,
            correlation_id=correlation_id
        )
        
        # Convert to list format
        rewrites = delegator.to_dict_results(batch_result)
        
        return {
            "rewrites": rewrites,
            "rewritten_count": batch_result.rewritten_count,
            "improved_count": batch_result.improved_count,
            "time_ms": int((time.time() - start) * 1000)
        }
    
    async def _run_clarification(
        self,
        still_failed: List[Dict[str, Any]],
        validation_results: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Run clarification phase for requirements that need user input."""
        from .clarification_delegator import ClarificationDelegator
        
        if not still_failed:
            return {
                "questions": [],
                "question_count": 0,
                "time_ms": 0
            }
        
        start = time.time()
        
        # Find validation results for still-failed requirements
        still_failed_ids = {r.get("req_id") for r in still_failed}
        relevant_validation = [
            v for v in validation_results
            if v.get("req_id") in still_failed_ids
        ]
        
        delegator = ClarificationDelegator(
            max_concurrent=self.config.clarification_concurrent,
            auto_fix_threshold=self.config.auto_fix_threshold,
            persist_to_db=True
        )
        
        batch_result = await delegator.process_batch(
            validation_results=relevant_validation,
            correlation_id=correlation_id,
            validation_id=self.workflow_id
        )
        
        questions = [q.to_dict() for q in batch_result.questions]
        
        return {
            "questions": questions,
            "question_count": len(questions),
            "time_ms": int((time.time() - start) * 1000)
        }
    
    async def _wait_for_answers(
        self,
        questions: List[Dict[str, Any]],
        correlation_id: Optional[str]
    ) -> Dict[str, Any]:
        """Wait for user to answer clarification questions."""
        if not questions:
            return {
                "answers": [],
                "answered_count": 0
            }
        
        # Send questions to frontend
        self._send_to_workflow_stream(
            correlation_id,
            "clarification_questions",
            questions=questions,
            total=len(questions)
        )
        
        # Wait for answers with timeout
        start = time.time()
        timeout = self.config.wait_for_answers_timeout
        poll_interval = 2
        
        answered = []
        
        try:
            from backend.core import db as _db
            from backend.services.clarification_service import ClarificationService
            
            service = ClarificationService()
            
            while (time.time() - start) < timeout:
                conn = _db.get_db()
                try:
                    summary = service.get_questions_summary(
                        conn,
                        validation_id=self.workflow_id
                    )
                    
                    pending = summary.get("pending", 0)
                    answered_count = summary.get("answered", 0)
                    
                    if pending == 0 or answered_count >= len(questions):
                        all_questions = conn.execute(
                            """
                            SELECT id, requirement_id, criterion, answer_text, applied_text
                            FROM clarification_question
                            WHERE validation_id = ? AND status = 'answered'
                            """,
                            (self.workflow_id,)
                        ).fetchall()
                        
                        answered = [dict(q) for q in all_questions]
                        break
                    
                finally:
                    conn.close()
                
                await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error waiting for answers: {e}")
        
        return {
            "answers": answered,
            "answered_count": len(answered)
        }
    
    async def _get_pending_questions(
        self,
        correlation_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get any pending (unanswered) questions from this workflow."""
        try:
            from backend.core import db as _db
            from backend.services.clarification_service import ClarificationService
            
            service = ClarificationService()
            conn = _db.get_db()
            
            try:
                pending = service.get_pending_questions(
                    conn,
                    validation_id=self.workflow_id
                )
                return pending
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Error getting pending questions: {e}")
            return []

    
    def _apply_rewrites(
        self,
        requirements: List[Dict[str, Any]],
        rewrites: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply rewritten text back to requirements."""
        rewrite_lookup = {r["req_id"]: r for r in rewrites}
        
        updated = []
        for req in requirements:
            req_id = req.get("req_id")
            if req_id in rewrite_lookup:
                rewrite = rewrite_lookup[req_id]
                req = req.copy()
                req["title"] = rewrite.get("rewritten_text", req.get("title"))
                req["_rewritten"] = True
            updated.append(req)
        
        return updated

    def _apply_answers(
        self,
        requirements: List[Dict[str, Any]],
        answers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply user answers back to requirements."""
        answer_lookup = {a["requirement_id"]: a for a in answers if a.get("applied_text")}
        
        updated = []
        for req in requirements:
            req_id = req.get("req_id")
            if req_id in answer_lookup:
                answer = answer_lookup[req_id]
                req = req.copy()
                req["title"] = answer.get("applied_text", req.get("title"))
                req["_answered"] = True
            updated.append(req)
        
        return updated
