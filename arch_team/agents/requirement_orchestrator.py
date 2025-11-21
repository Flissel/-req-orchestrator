# -*- coding: utf-8 -*-
"""
Requirement Orchestrator - Sequential Validation Workflow

This orchestrator processes each requirement through all 10 quality criteria sequentially:
1. Evaluate all criteria
2. For each failing criterion:
   - If atomic criterion fails: delegate to RequirementsAtomicityAgent for splitting
   - Else: use CriterionSpecialistAgent to suggest and apply fix
3. Re-evaluate after each fix
4. Track all changes in manifest
5. Maximum 3 iteration rounds to avoid infinite loops

Usage:
    orchestrator = RequirementOrchestrator(threshold=0.7, max_iterations=3)
    result = await orchestrator.process(
        requirement_id="REQ-001",
        requirement_text="The app must be fast",
        context={"project": "MyApp"},
        session_id="session-123"
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from arch_team.agents.criterion_specialists import (
    get_all_specialists,
    get_specialist_by_criterion,
    AtomicityAgent
)

# Import existing RequirementsAtomicityAgent for splitting
try:
    from backend.core.agents import RequirementsAtomicityAgent
    ATOMICITY_AGENT_AVAILABLE = True
except ImportError:
    RequirementsAtomicityAgent = None
    ATOMICITY_AGENT_AVAILABLE = False

logger = logging.getLogger(__name__)


class ValidationIteration:
    """Represents one iteration of validation with all criterion scores"""

    def __init__(self, iteration_number: int, phase: str = None):
        self.iteration_number = iteration_number
        self.phase = phase  # Which phase(s) this iteration processed (STRUCTURE, LANGUAGE_QUALITY, VERIFICATION)
        self.timestamp = datetime.utcnow().isoformat()
        self.requirement_text = ""
        self.criterion_scores: Dict[str, float] = {}
        self.overall_score: float = 0.0
        self.fixes_applied: List[Dict[str, Any]] = []
        self.split_occurred: bool = False
        self.split_children: List[str] = []


class RequirementValidationResult:
    """Result of the full validation process for one requirement"""

    def __init__(self, requirement_id: str, original_text: str):
        self.requirement_id = requirement_id
        self.original_text = original_text
        self.final_text = original_text
        self.iterations: List[ValidationIteration] = []
        self.passed: bool = False
        self.final_score: float = 0.0
        self.final_scores: Dict[str, float] = {}
        self.split_occurred: bool = False
        self.split_children: List[str] = []
        self.total_fixes: int = 0
        self.error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "requirement_id": self.requirement_id,
            "original_text": self.original_text,
            "final_text": self.final_text,
            "passed": self.passed,
            "final_score": self.final_score,
            "final_scores": self.final_scores,
            "split_occurred": self.split_occurred,
            "split_children": self.split_children,
            "total_fixes": self.total_fixes,
            "iterations": [
                {
                    "iteration": iter.iteration_number,
                    "phase": iter.phase,
                    "timestamp": iter.timestamp,
                    "requirement_text": iter.requirement_text,
                    "criterion_scores": iter.criterion_scores,
                    "overall_score": iter.overall_score,
                    "fixes_applied": iter.fixes_applied,
                    "split_occurred": iter.split_occurred,
                    "split_children": iter.split_children
                }
                for iter in self.iterations
            ],
            "error_message": self.error_message
        }


class RequirementOrchestrator:
    """
    Orchestrates the sequential validation and fixing workflow for a single requirement

    Enhanced with:
    - Pre-validation health check (word count, structure)
    - Tier-based scoring (gating → priority → polish)
    - Split-first logic for non-atomic requirements
    - Actionable feedback with specific fix guidance
    """

    # Phase-based criterion grouping to prevent conflicts and reduce iterations
    CRITERIA_PHASES = [
        {
            "phase": "STRUCTURE",
            "description": "Foundation: Establish clarity of statement",
            "sequence": ["atomic", "design_independent", "purpose_independent"]
        },
        {
            "phase": "LANGUAGE_QUALITY",
            "description": "Refinement: Make it understandable",
            "sequence": ["consistent_language", "clarity", "unambiguous", "concise"]
        },
        {
            "phase": "VERIFICATION",
            "description": "Validation: Define how to verify",
            "sequence": ["testability", "measurability"]
        }
    ]

    # Health check constants
    MAX_WORDS = 100  # Reject requirements longer than this
    IDEAL_MAX_WORDS = 50  # Target for core requirement
    MIN_WORDS = 3  # Too short to be meaningful

    # Modal verbs that indicate proper requirement structure
    MODAL_VERBS = ["must", "shall", "should", "may", "can", "will"]

    def __init__(
        self,
        threshold: float = 0.7,
        max_iterations: int = 3,
        stream_callback: Optional[callable] = None
    ):
        """
        Initialize the requirement orchestrator

        Args:
            threshold: Minimum acceptable score for each criterion (default: 0.7)
            max_iterations: Maximum number of fix iterations (default: 3)
            stream_callback: Optional async callback(event_type, data) for streaming updates
        """
        self.threshold = threshold
        self.max_iterations = max_iterations
        self.stream_callback = stream_callback
        self.specialists = {agent.criterion_name: agent for agent in get_all_specialists()}
        self.criteria_config = self._load_criteria_config()
        logger.info(f"RequirementOrchestrator initialized: threshold={threshold}, max_iterations={max_iterations}")
        logger.info(f"Loaded {len(self.specialists)} criterion specialists")
        logger.info(f"Loaded {len(self.criteria_config)} criteria with tier configuration")

    def _load_criteria_config(self) -> Dict[str, Dict[str, Any]]:
        """Load criteria configuration with tiers and weights from config/criteria.json"""
        config_path = Path(__file__).parent.parent.parent / "config" / "criteria.json"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                criteria_list = json.load(f)
            return {c["key"]: c for c in criteria_list if c.get("active", True)}
        except Exception as e:
            logger.warning(f"Failed to load criteria config: {e}, using defaults")
            # Return default config if file not found
            return {
                "atomic": {"weight": 0.20, "tier": "gating", "threshold": 0.80},
                "clarity": {"weight": 0.15, "tier": "gating", "threshold": 0.80},
                "testability": {"weight": 0.15, "tier": "gating", "threshold": 0.80},
                "design_independent": {"weight": 0.12, "tier": "priority", "threshold": 0.70},
                "unambiguous": {"weight": 0.12, "tier": "priority", "threshold": 0.70},
                "concise": {"weight": 0.08, "tier": "polish", "threshold": 0.60},
                "consistent_language": {"weight": 0.08, "tier": "polish", "threshold": 0.60},
                "measurability": {"weight": 0.05, "tier": "polish", "threshold": 0.60},
                "purpose_independent": {"weight": 0.05, "tier": "polish", "threshold": 0.60},
            }

    def _pre_check_health(self, requirement_text: str) -> Dict[str, Any]:
        """
        Pre-validation health check before processing.

        Checks:
        1. Word count (reject if >100, warn if >50)
        2. Has subject + modal verb structure
        3. Not just a heading/comment

        Returns:
            Dict with:
            - passed: bool - whether the requirement passes basic health
            - issues: List[Dict] - list of issues found
            - guidance: str - actionable guidance for fixing
        """
        issues = []
        words = requirement_text.split()
        word_count = len(words)

        # Check 1: Word count
        if word_count > self.MAX_WORDS:
            issues.append({
                "type": "word_count",
                "severity": "critical",
                "message": f"Requirement has {word_count} words (max: {self.MAX_WORDS})",
                "action": f"Reduce to <{self.IDEAL_MAX_WORDS} words; move details to acceptance criteria"
            })
        elif word_count > self.IDEAL_MAX_WORDS:
            issues.append({
                "type": "word_count",
                "severity": "warning",
                "message": f"Requirement has {word_count} words (ideal: <{self.IDEAL_MAX_WORDS})",
                "action": "Consider trimming or splitting into multiple requirements"
            })
        elif word_count < self.MIN_WORDS:
            issues.append({
                "type": "word_count",
                "severity": "critical",
                "message": f"Requirement too short ({word_count} words)",
                "action": "Add more detail about what the system must do"
            })

        # Check 2: Has modal verb structure (subject + must/shall/should/may)
        text_lower = requirement_text.lower()
        has_modal = any(f" {modal} " in f" {text_lower} " or text_lower.startswith(f"{modal} ")
                       for modal in self.MODAL_VERBS)

        if not has_modal:
            issues.append({
                "type": "structure",
                "severity": "warning",
                "message": "Missing modal verb (must/shall/should/may)",
                "action": "Start with 'The system must...' or 'The user shall...'"
            })

        # Check 3: Looks like a heading/comment (starts with #, contains only title case, etc.)
        if requirement_text.startswith("#") or requirement_text.startswith("//"):
            issues.append({
                "type": "format",
                "severity": "critical",
                "message": "Looks like a heading or comment, not a requirement",
                "action": "Convert to proper requirement statement"
            })

        # Check 4: Multiple sentences with different concerns (likely needs splitting)
        sentence_count = len(re.findall(r'[.!?]\s+[A-Z]', requirement_text)) + 1
        and_count = text_lower.count(" and ")
        or_count = text_lower.count(" or ")

        if sentence_count > 2 or and_count > 2:
            issues.append({
                "type": "atomicity_hint",
                "severity": "warning",
                "message": f"Contains {sentence_count} sentences and {and_count} 'and' conjunctions",
                "action": "Consider splitting into separate atomic requirements"
            })

        # Build guidance
        critical_issues = [i for i in issues if i["severity"] == "critical"]
        passed = len(critical_issues) == 0

        guidance_parts = []
        if not passed:
            guidance_parts.append("BLOCKED: Fix critical issues before validation:")
            for issue in critical_issues:
                guidance_parts.append(f"  - {issue['action']}")
        elif issues:
            guidance_parts.append("WARNINGS: Consider addressing before validation:")
            for issue in issues:
                guidance_parts.append(f"  - {issue['action']}")

        return {
            "passed": passed,
            "word_count": word_count,
            "issues": issues,
            "guidance": "\n".join(guidance_parts) if guidance_parts else "Health check passed"
        }

    def _calculate_tier_score(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculate tier-based weighted score and pass/fail status.

        Scoring logic:
        - Gating criteria (atomic, clarity, testability): Must all pass their tier threshold
        - Priority criteria: Should pass, weighted higher
        - Polish criteria: Nice to have, weighted lower

        Returns:
            Dict with:
            - overall_score: float - weighted average
            - tier_scores: Dict[str, float] - average per tier
            - passed: bool - whether all gating criteria pass
            - failing_criteria: List[str] - criteria below their threshold
            - feedback: List[Dict] - actionable feedback per failing criterion
        """
        tier_scores = {"gating": [], "priority": [], "polish": []}
        failing_criteria = []
        feedback = []
        weighted_sum = 0.0
        total_weight = 0.0

        for criterion, score in scores.items():
            config = self.criteria_config.get(criterion, {"weight": 0.10, "tier": "priority", "threshold": 0.70})
            tier = config.get("tier", "priority")
            weight = config.get("weight", 0.10)
            threshold = config.get("threshold", 0.70)
            action = config.get("action", "Improve this criterion")

            tier_scores[tier].append(score)
            weighted_sum += score * weight
            total_weight += weight

            if score < threshold:
                failing_criteria.append(criterion)
                feedback.append({
                    "criterion": criterion,
                    "score": score,
                    "threshold": threshold,
                    "tier": tier,
                    "action": action,
                    "priority": 1 if tier == "gating" else (2 if tier == "priority" else 3)
                })

        # Calculate tier averages
        tier_averages = {
            tier: sum(scores) / len(scores) if scores else 1.0
            for tier, scores in tier_scores.items()
        }

        # Overall score is weighted average
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Pass if all gating criteria meet their thresholds
        gating_failed = any(
            fb["tier"] == "gating" for fb in feedback
        )
        passed = not gating_failed and overall_score >= 0.70

        # Sort feedback by priority
        feedback.sort(key=lambda x: (x["priority"], -x["score"]))

        return {
            "overall_score": overall_score,
            "tier_scores": tier_averages,
            "passed": passed,
            "failing_criteria": failing_criteria,
            "feedback": feedback,
            "gating_passed": not gating_failed
        }

    def _get_ordered_criteria(self, failing_criteria: List[str]) -> List[str]:
        """
        Return failing criteria in phase order to prevent conflicts

        Args:
            failing_criteria: List of criterion names that are failing

        Returns:
            List of criterion names ordered by phase (STRUCTURE → LANGUAGE_QUALITY → VERIFICATION)
        """
        ordered = []
        for phase in self.CRITERIA_PHASES:
            for criterion in phase["sequence"]:
                if criterion in failing_criteria:
                    ordered.append(criterion)
        return ordered

    async def process(
        self,
        requirement_id: str,
        requirement_text: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> RequirementValidationResult:
        """
        Process a requirement through the validation workflow

        Args:
            requirement_id: Unique identifier for the requirement
            requirement_text: The requirement text to validate
            context: Optional context (project metadata, etc.)
            session_id: Optional session ID for streaming updates

        Returns:
            RequirementValidationResult with all validation details
        """
        result = RequirementValidationResult(requirement_id, requirement_text)
        context = context or {}

        logger.info(f"Starting orchestration for {requirement_id}: {requirement_text[:50]}...")

        try:
            # Step 0: Pre-validation health check
            health = self._pre_check_health(requirement_text)
            logger.info(f"Health check for {requirement_id}: passed={health['passed']}, word_count={health['word_count']}")

            if health["issues"]:
                for issue in health["issues"]:
                    logger.info(f"  Health issue [{issue['severity']}]: {issue['message']}")

            # Stream health check results
            await self._stream_event("health_check_completed", {
                "requirement_id": requirement_id,
                "passed": health["passed"],
                "word_count": health["word_count"],
                "issues": health["issues"],
                "guidance": health["guidance"]
            })

            # Don't block on health check failures - just log and continue with warnings
            # This allows the system to attempt improvement even on problematic requirements
            if not health["passed"]:
                logger.warning(f"Health check failed for {requirement_id}, proceeding with caution: {health['guidance']}")

            current_text = requirement_text

            for iteration_num in range(1, self.max_iterations + 1):
                logger.info(f"Iteration {iteration_num}/{self.max_iterations} for {requirement_id}")
                iteration = ValidationIteration(iteration_num)
                iteration.requirement_text = current_text

                # Step 1: Evaluate all criteria
                await self._stream_event("evaluation_started", {
                    "requirement_id": requirement_id,
                    "iteration": iteration_num,
                    "text": current_text
                })

                scores = await self._evaluate_all_criteria(current_text, context)
                iteration.criterion_scores = scores

                # Use tier-based scoring for weighted average and pass/fail logic
                tier_result = self._calculate_tier_score(scores)
                iteration.overall_score = tier_result["overall_score"]

                logger.info(f"Iteration {iteration_num} scores: {scores}")
                logger.info(f"Tier scores - Gating: {tier_result['tier_scores']['gating']:.2f}, Priority: {tier_result['tier_scores']['priority']:.2f}, Polish: {tier_result['tier_scores']['polish']:.2f}")
                logger.info(f"Overall weighted score: {iteration.overall_score:.2f}")

                await self._stream_event("evaluation_completed", {
                    "requirement_id": requirement_id,
                    "iteration": iteration_num,
                    "scores": scores,
                    "overall_score": iteration.overall_score,
                    "tier_scores": tier_result["tier_scores"],
                    "gating_passed": tier_result["gating_passed"],
                    "feedback": tier_result["feedback"]
                })

                # Step 2: Check pass/fail using tier-based logic
                # Pass if all gating criteria pass AND overall score >= 0.70
                failing_criteria = tier_result["failing_criteria"]

                if tier_result["passed"]:
                    logger.info(f"Tier-based validation passed for {requirement_id}!")
                    result.passed = True
                    result.final_text = current_text
                    result.final_score = iteration.overall_score
                    result.final_scores = scores
                    result.iterations.append(iteration)
                    break

                # Log feedback for failing criteria
                logger.info(f"Failing criteria ({len(failing_criteria)}): {failing_criteria}")
                for fb in tier_result["feedback"][:3]:  # Log top 3 issues
                    logger.info(f"  [{fb['tier']}] {fb['criterion']}: {fb['score']:.2f} < {fb['threshold']} - {fb['action']}")

                # Step 3: Handle atomic criterion specially (requires splitting)
                if "atomic" in failing_criteria:
                    logger.info(f"Atomic criterion failed (score: {scores['atomic']:.2f}), initiating split...")

                    split_result = await self._handle_atomic_split(
                        requirement_id,
                        current_text,
                        context
                    )

                    if split_result["split_occurred"]:
                        # Splitting occurred - mark result and exit orchestration
                        iteration.split_occurred = True
                        iteration.split_children = split_result["children"]
                        result.split_occurred = True
                        result.split_children = split_result["children"]
                        result.iterations.append(iteration)

                        await self._stream_event("requirement_split", {
                            "requirement_id": requirement_id,
                            "parent_text": current_text,
                            "children": split_result["children"]
                        })

                        logger.info(f"Requirement {requirement_id} split into {len(split_result['children'])} children")
                        break
                    else:
                        # Split failed or not needed - continue with other criteria
                        logger.warning(f"Atomic split failed or not triggered: {split_result.get('error')}")

                # Step 4: Fix failing criteria (except atomic, which is handled above)
                # Use phase-based ordering to prevent conflicts (STRUCTURE → LANGUAGE_QUALITY → VERIFICATION)
                other_failing_unordered = [c for c in failing_criteria if c != "atomic"]
                other_failing = self._get_ordered_criteria(other_failing_unordered)

                logger.info(f"Processing criteria in phase order: {other_failing}")

                for criterion in other_failing:
                    logger.info(f"Attempting to fix criterion: {criterion}")

                    fix_result = await self._fix_criterion(
                        requirement_id,
                        criterion,
                        current_text,
                        scores[criterion],
                        context,
                        iteration_num
                    )

                    if fix_result["fixed"]:
                        current_text = fix_result["new_text"]
                        iteration.fixes_applied.append({
                            "criterion": criterion,
                            "old_text": fix_result["old_text"],
                            "new_text": fix_result["new_text"],
                            "suggestion": fix_result["suggestion"],
                            "score_before": scores[criterion],
                            "score_after": fix_result.get("score_after")
                        })

                        await self._stream_event("requirement_updated", {
                            "requirement_id": requirement_id,
                            "criterion": criterion,
                            "old_text": fix_result["old_text"],
                            "new_text": fix_result["new_text"],
                            "score_before": scores[criterion],
                            "score_after": fix_result.get("score_after")
                        })

                        logger.info(f"Fixed {criterion}: {fix_result['old_text'][:30]}... → {fix_result['new_text'][:30]}...")

                # Immediate re-evaluation: Check if all criteria now pass after applying fixes
                if iteration.fixes_applied:
                    logger.info(f"Re-evaluating after {len(iteration.fixes_applied)} fixes to check if criteria pass...")

                    new_scores = await self._evaluate_all_criteria(current_text, context)
                    new_tier_result = self._calculate_tier_score(new_scores)

                    logger.info(f"Post-fix evaluation - Overall weighted score: {new_tier_result['overall_score']:.2f}")
                    logger.info(f"Post-fix evaluation - Gating passed: {new_tier_result['gating_passed']}")
                    logger.info(f"Post-fix evaluation - Still failing: {new_tier_result['failing_criteria']}")

                    if new_tier_result["passed"]:
                        # Tier-based validation passed - exit successfully!
                        iteration.criterion_scores = new_scores
                        iteration.overall_score = new_tier_result["overall_score"]

                        result.passed = True
                        result.final_text = current_text
                        result.final_score = iteration.overall_score
                        result.final_scores = new_scores
                        result.iterations.append(iteration)

                        logger.info(f"Tier-based validation passed after fixes! Final score: {result.final_score:.2f}")

                        await self._stream_event("validation_success", {
                            "requirement_id": requirement_id,
                            "final_score": result.final_score,
                            "iteration": iteration_num,
                            "tier_scores": new_tier_result["tier_scores"]
                        })
                        break

                result.iterations.append(iteration)
                result.total_fixes += len(iteration.fixes_applied)

                # If we've made fixes but still have failing criteria, continue to next iteration
                if iteration.fixes_applied or iteration.split_occurred:
                    logger.info(f"Fixes applied: {len(iteration.fixes_applied)}, continuing to next iteration for further refinement")
                    continue
                else:
                    # No fixes could be applied - stuck, exit loop
                    logger.warning(f"No fixes applied in iteration {iteration_num}, stopping")
                    break

            # Final result - use tier-based scoring for pass/fail determination
            if not result.split_occurred:
                result.final_text = current_text
                result.final_scores = result.iterations[-1].criterion_scores if result.iterations else {}
                if result.final_scores:
                    final_tier_result = self._calculate_tier_score(result.final_scores)
                    result.final_score = final_tier_result["overall_score"]
                    result.passed = final_tier_result["passed"]
                else:
                    result.final_score = 0.0
                    result.passed = False

            await self._stream_event("validation_complete", {
                "requirement_id": requirement_id,
                "passed": result.passed,
                "final_score": result.final_score,
                "split_occurred": result.split_occurred,
                "final_scores": result.final_scores
            })

            logger.info(f"Orchestration complete for {requirement_id}: passed={result.passed}, score={result.final_score:.2f}")

        except Exception as e:
            logger.error(f"Error in orchestration for {requirement_id}: {e}", exc_info=True)
            result.error_message = str(e)
            await self._stream_event("validation_error", {
                "requirement_id": requirement_id,
                "error": str(e)
            })

        return result

    async def _evaluate_all_criteria(
        self,
        requirement_text: str,
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Evaluate all 10 criteria in parallel

        Args:
            requirement_text: Text to evaluate
            context: Context dictionary

        Returns:
            Dict mapping criterion name to score
        """
        tasks = []
        criteria_names = []

        for criterion_name, specialist in self.specialists.items():
            tasks.append(specialist.evaluate(requirement_text, context))
            criteria_names.append(criterion_name)

        scores = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for i, criterion_name in enumerate(criteria_names):
            if isinstance(scores[i], Exception):
                logger.error(f"Error evaluating {criterion_name}: {scores[i]}")
                result[criterion_name] = 0.5  # Neutral score on error
            else:
                result[criterion_name] = scores[i]

        return result

    async def _handle_atomic_split(
        self,
        requirement_id: str,
        requirement_text: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle atomic criterion violation by delegating to RequirementsAtomicityAgent

        Args:
            requirement_id: Requirement ID
            requirement_text: Text to split
            context: Context dictionary

        Returns:
            Dict with split_occurred, children, and optional error
        """
        if not ATOMICITY_AGENT_AVAILABLE:
            logger.warning("RequirementsAtomicityAgent not available for splitting - continuing with other criteria")
            return {
                "split_occurred": False,
                "children": [],
                "error": "Atomicity agent not available (non-critical)"
            }

        try:
            # Use the existing split logic from backend.core.agents
            atomicity_agent = RequirementsAtomicityAgent()

            # Call the internal split method directly
            splits = await atomicity_agent._split_atomic_llm(
                requirement_text=requirement_text,
                context=context,
                max_splits=5
            )

            if splits and len(splits) >= 2:
                # Extract child requirement texts
                children = [split.get("text", "") for split in splits if split.get("text")]

                return {
                    "split_occurred": True,
                    "children": children,
                    "splits": splits
                }
            else:
                return {
                    "split_occurred": False,
                    "children": [],
                    "error": "Split produced fewer than 2 children"
                }

        except Exception as e:
            logger.error(f"Error during atomic split: {e}", exc_info=True)
            return {
                "split_occurred": False,
                "children": [],
                "error": str(e)
            }

    async def _fix_criterion(
        self,
        requirement_id: str,
        criterion: str,
        current_text: str,
        current_score: float,
        context: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        """
        Fix a failing criterion using its specialist agent

        Args:
            requirement_id: Requirement ID
            criterion: Criterion name
            current_text: Current requirement text
            current_score: Current criterion score
            context: Context dictionary
            iteration: Current iteration number

        Returns:
            Dict with fixed status, new_text, suggestion, etc.
        """
        specialist = self.specialists.get(criterion)
        if not specialist:
            logger.error(f"No specialist found for criterion: {criterion}")
            return {
                "fixed": False,
                "old_text": current_text,
                "new_text": current_text,
                "error": f"No specialist for {criterion}"
            }

        try:
            # Step 1: Get suggestion
            suggestion = await specialist.suggest_fix(current_text, current_score, context)

            # Step 2: Apply fix
            new_text = await specialist.apply_fix(current_text, suggestion, context)

            # Step 3: Re-evaluate criterion to verify improvement
            new_score = await specialist.evaluate(new_text, context)

            # Check if fix actually improved the score
            improved = new_score > current_score

            return {
                "fixed": improved,
                "old_text": current_text,
                "new_text": new_text,
                "suggestion": suggestion,
                "score_before": current_score,
                "score_after": new_score,
                "improved": improved
            }

        except Exception as e:
            logger.error(f"Error fixing criterion {criterion}: {e}", exc_info=True)
            return {
                "fixed": False,
                "old_text": current_text,
                "new_text": current_text,
                "error": str(e)
            }

    async def _stream_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Stream an event via the callback if configured

        Args:
            event_type: Type of event (evaluation_started, requirement_updated, etc.)
            data: Event data dictionary
        """
        if self.stream_callback:
            try:
                await self.stream_callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in stream callback: {e}")


# ============================================================================
# BATCH ORCHESTRATION - Process multiple requirements
# ============================================================================

class BatchOrchestrator:
    """Orchestrates validation for multiple requirements"""

    def __init__(
        self,
        threshold: float = 0.7,
        max_iterations: int = 3,
        stream_callback: Optional[callable] = None
    ):
        self.orchestrator = RequirementOrchestrator(
            threshold=threshold,
            max_iterations=max_iterations,
            stream_callback=stream_callback
        )

    async def process_batch(
        self,
        requirements: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> List[RequirementValidationResult]:
        """
        Process a batch of requirements

        Args:
            requirements: List of dicts with 'id' and 'text' keys
            context: Optional shared context
            session_id: Optional session ID for streaming

        Returns:
            List of RequirementValidationResult
        """
        context = context or {}
        results = []

        for req in requirements:
            req_id = req.get("id", f"REQ-{len(results)+1}")
            req_text = req.get("text", "")

            if not req_text:
                logger.warning(f"Skipping empty requirement: {req_id}")
                continue

            result = await self.orchestrator.process(
                requirement_id=req_id,
                requirement_text=req_text,
                context=context,
                session_id=session_id
            )
            results.append(result)

        return results
