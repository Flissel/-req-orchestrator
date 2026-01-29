# -*- coding: utf-8 -*-
"""
DecisionMaker Agent for Autonomous Requirements Improvement.

Makes intelligent decisions about how to handle failing requirements:
- SPLIT: Break down complex requirements into atomic ones
- REWRITE: Auto-improve requirement using RewriteAgent
- ACCEPT: Accept as-is (good enough or cannot be improved)
- CLARIFY: Generate and auto-answer clarification questions

Operates in two modes:
- AUTO (default): LLM makes all decisions autonomously
- MANUAL: User is asked to make decisions

Part of the Requirements-Management-System.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("arch_team.decision_maker_agent")


class DecisionAction(Enum):
    """Possible actions the DecisionMaker can take."""
    SPLIT = "split"           # Split into multiple requirements
    REWRITE = "rewrite"       # Auto-rewrite using RewriteAgent
    ACCEPT = "accept"         # Accept as-is (good enough)
    CLARIFY = "clarify"       # Generate clarification (auto-answer in AUTO mode)
    REJECT = "reject"         # Cannot be improved, reject


class WorkflowMode(Enum):
    """Workflow operation modes."""
    AUTO = "auto"             # DecisionMaker decides everything
    MANUAL = "manual"         # User makes decisions
    HYBRID = "hybrid"         # Auto for simple, manual for complex


@dataclass
class Decision:
    """A decision made by the DecisionMaker."""
    req_id: str
    action: DecisionAction
    reason: str
    confidence: float = 0.0
    split_suggestions: List[str] = field(default_factory=list)  # For SPLIT action
    clarification_answers: Dict[str, str] = field(default_factory=dict)  # For CLARIFY action
    rewrite_hints: List[str] = field(default_factory=list)  # For REWRITE action
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id,
            "action": self.action.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "split_suggestions": self.split_suggestions,
            "clarification_answers": self.clarification_answers,
            "rewrite_hints": self.rewrite_hints
        }


@dataclass
class DecisionBatchResult:
    """Result from processing a batch of requirements."""
    total_count: int
    decisions: List[Decision] = field(default_factory=list)
    split_count: int = 0
    rewrite_count: int = 0
    accept_count: int = 0
    clarify_count: int = 0
    reject_count: int = 0
    total_time_ms: int = 0
    errors: List[str] = field(default_factory=list)


class DecisionMakerAgent:
    """
    LLM-based agent that makes intelligent decisions about requirement processing.
    
    In AUTO mode (default), the agent:
    1. Analyzes validation feedback for each failing requirement
    2. Decides the best action (SPLIT/REWRITE/ACCEPT/CLARIFY/REJECT)
    3. Auto-generates clarification answers using domain knowledge
    4. Routes to appropriate processing pipeline
    
    Usage:
        agent = DecisionMakerAgent(mode=WorkflowMode.AUTO)
        decisions = await agent.decide_batch(failed_requirements)
    """
    
    # Decision prompt template
    DECISION_PROMPT = """Du bist ein Requirements Engineering Experte.
Analysiere das folgende Requirement und seine Validierungsergebnisse.
Entscheide, welche Aktion am besten geeignet ist.

REQUIREMENT:
ID: {req_id}
Text: {requirement_text}
Score: {score}
Tag: {tag}

VALIDIERUNGSERGEBNISSE:
{evaluation_details}

MÖGLICHE AKTIONEN:
1. SPLIT - Wenn das Requirement zu komplex ist und mehrere Aspekte behandelt
2. REWRITE - Wenn das Requirement durch Umformulierung verbessert werden kann
3. ACCEPT - Wenn das Requirement gut genug ist (nahe am Threshold) oder nicht verbessert werden kann
4. CLARIFY - Wenn spezifische Informationen fehlen (Metriken, Akzeptanzkriterien)
5. REJECT - Wenn das Requirement grundlegend fehlerhaft ist und verworfen werden sollte

ENTSCHEIDUNGSKRITERIEN:
- SPLIT: Wenn "atomic" fehlschlägt oder mehrere unabhängige Aspekte vorhanden
- REWRITE: Wenn Formulierung das Problem ist (clarity, consistency, concise)
- ACCEPT: Wenn Score > 0.65 oder keine weitere Verbesserung möglich
- CLARIFY: Wenn messbare Werte oder Testkriterien fehlen (measurability, testability)
- REJECT: Wenn kein sinnvolles Requirement ableitbar

Antworte NUR mit validem JSON:
{{
    "action": "SPLIT|REWRITE|ACCEPT|CLARIFY|REJECT",
    "reason": "Begründung der Entscheidung",
    "confidence": 0.0-1.0,
    "split_suggestions": ["Req 1...", "Req 2..."],  // nur bei SPLIT
    "clarification_answers": {{"criterion": "answer"}},  // nur bei CLARIFY
    "rewrite_hints": ["Hinweis 1", "Hinweis 2"]  // nur bei REWRITE
}}"""

    # Auto-clarification prompt
    CLARIFY_PROMPT = """Du bist ein Requirements Engineering Experte.
Beantworte die Klärungsfrage für das folgende Requirement.
Nutze dein Fachwissen, um sinnvolle Werte/Antworten zu generieren.

REQUIREMENT:
{requirement_text}

KRITERIUM: {criterion}
SCORE: {score}
FEEDBACK: {feedback}

FRAGE: {question}

VORGESCHLAGENE ANTWORTEN:
{suggested_answers}

Wähle die beste Antwort oder formuliere eine eigene.
Antworte NUR mit der Antwort (kein JSON, keine Erklärung)."""

    def __init__(
        self,
        mode: WorkflowMode = WorkflowMode.AUTO,
        semaphore: Optional[asyncio.Semaphore] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        accept_threshold: float = 0.65,  # If score above this, consider accepting
        confidence_threshold: float = 0.7  # Minimum confidence for auto-decisions
    ):
        """
        Initialize DecisionMaker agent.
        
        Args:
            mode: Operating mode (AUTO/MANUAL/HYBRID)
            semaphore: Rate limiting semaphore
            progress_callback: Progress reporting callback
            accept_threshold: Score above which requirement may be accepted
            confidence_threshold: Minimum confidence for autonomous decisions
        """
        self.mode = mode
        self.semaphore = semaphore or asyncio.Semaphore(5)
        self.progress_callback = progress_callback
        self.accept_threshold = accept_threshold
        self.confidence_threshold = confidence_threshold
        self._timeout = int(os.environ.get("DECISION_TIMEOUT", "30"))
        
    async def decide(
        self,
        req_id: str,
        requirement_text: str,
        score: float,
        evaluation: List[Dict[str, Any]],
        tag: Optional[str] = None,
        questions: Optional[List[Dict[str, Any]]] = None
    ) -> Decision:
        """
        Make a decision about how to handle a failing requirement.
        
        Args:
            req_id: Requirement ID
            requirement_text: The requirement text
            score: Overall validation score
            evaluation: List of criterion evaluation results
            tag: Optional requirement tag/category
            questions: Optional pre-generated clarification questions
        
        Returns:
            Decision with action and supporting data
        """
        async with self.semaphore:
            start_time = time.time()
            
            try:
                # Quick accept for near-threshold requirements
                if score >= self.accept_threshold:
                    return Decision(
                        req_id=req_id,
                        action=DecisionAction.ACCEPT,
                        reason=f"Score {score:.2f} ist nahe am Threshold, Verbesserungspotential gering",
                        confidence=0.9
                    )
                
                # Use LLM to make decision
                decision = await self._llm_decide(
                    req_id=req_id,
                    requirement_text=requirement_text,
                    score=score,
                    evaluation=evaluation,
                    tag=tag
                )
                
                # If CLARIFY in AUTO mode, auto-answer the questions
                if decision.action == DecisionAction.CLARIFY and self.mode == WorkflowMode.AUTO:
                    clarification_answers = await self._auto_clarify(
                        requirement_text=requirement_text,
                        evaluation=evaluation,
                        questions=questions
                    )
                    decision.clarification_answers = clarification_answers
                
                processing_time = int((time.time() - start_time) * 1000)
                logger.debug(f"Decision for {req_id}: {decision.action.value} ({processing_time}ms)")
                
                return decision
                
            except Exception as e:
                logger.error(f"Decision failed for {req_id}: {e}")
                # Default to REWRITE on error
                return Decision(
                    req_id=req_id,
                    action=DecisionAction.REWRITE,
                    reason=f"Entscheidungsfehler: {str(e)}, versuche Rewrite",
                    confidence=0.3
                )
    
    async def _llm_decide(
        self,
        req_id: str,
        requirement_text: str,
        score: float,
        evaluation: List[Dict[str, Any]],
        tag: Optional[str]
    ) -> Decision:
        """Use LLM to make intelligent decision."""
        from backend.core import llm as _llm
        from backend.core import settings as _settings
        
        # Format evaluation details
        eval_details = "\n".join([
            f"- {e.get('criterion', 'unknown')}: Score={e.get('score', 0):.2f}, "
            f"Passed={e.get('passed', False)}, Feedback: {e.get('feedback', 'N/A')}"
            for e in evaluation
        ])
        
        prompt = self.DECISION_PROMPT.format(
            req_id=req_id,
            requirement_text=requirement_text,
            score=score,
            tag=tag or "general",
            evaluation_details=eval_details
        )
        
        # Call LLM
        llm_config = _settings.get_llm_config()
        response = await asyncio.to_thread(
            _llm._llm_call_sync,
            system_prompt="Du bist ein Requirements Engineering Decision Maker.",
            user_prompt=prompt,
            temperature=0.1  # Low temperature for consistent decisions
        )
        
        # Parse response
        try:
            # Clean response (remove markdown code blocks if present)
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            clean_response = clean_response.strip()
            
            data = json.loads(clean_response)
            
            action_str = data.get("action", "REWRITE").upper()
            action = DecisionAction[action_str]
            
            return Decision(
                req_id=req_id,
                action=action,
                reason=data.get("reason", ""),
                confidence=float(data.get("confidence", 0.5)),
                split_suggestions=data.get("split_suggestions", []),
                clarification_answers=data.get("clarification_answers", {}),
                rewrite_hints=data.get("rewrite_hints", [])
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM decision: {e}, response: {response[:200]}")
            # Default to REWRITE
            return Decision(
                req_id=req_id,
                action=DecisionAction.REWRITE,
                reason="Konnte LLM-Antwort nicht parsen, versuche Rewrite",
                confidence=0.4
            )
    
    async def _auto_clarify(
        self,
        requirement_text: str,
        evaluation: List[Dict[str, Any]],
        questions: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, str]:
        """Auto-answer clarification questions using LLM."""
        from backend.core import llm as _llm
        
        answers = {}
        
        # Get questions from evaluation if not provided
        if not questions:
            # Generate questions based on failed criteria
            questions = []
            for e in evaluation:
                if not e.get("passed", True):
                    questions.append({
                        "criterion": e.get("criterion"),
                        "score": e.get("score", 0.0),
                        "feedback": e.get("feedback", ""),
                        "question": f"Welche konkreten Werte/Kriterien fehlen für {e.get('criterion')}?",
                        "suggested_answers": ["Spezifischen Wert angeben", "Standard-Branchenwert verwenden"]
                    })
        
        for q in questions:
            criterion = q.get("criterion", "unknown")
            
            prompt = self.CLARIFY_PROMPT.format(
                requirement_text=requirement_text,
                criterion=criterion,
                score=q.get("score", 0.0),
                feedback=q.get("feedback", ""),
                question=q.get("question_text", q.get("question", "")),
                suggested_answers="\n".join([f"- {a}" for a in q.get("suggested_answers", [])])
            )
            
            try:
                response = await asyncio.to_thread(
                    _llm._llm_call_sync,
                    system_prompt="Du bist ein Requirements Engineering Experte. Gib präzise Antworten.",
                    user_prompt=prompt,
                    temperature=0.3
                )
                
                answers[criterion] = response.strip()
                logger.debug(f"Auto-clarified {criterion}: {response[:50]}...")
                
            except Exception as e:
                logger.warning(f"Auto-clarify failed for {criterion}: {e}")
                # Use first suggested answer as fallback
                if q.get("suggested_answers"):
                    answers[criterion] = q["suggested_answers"][0]
        
        return answers
    
    async def decide_batch(
        self,
        failed_requirements: List[Dict[str, Any]]
    ) -> DecisionBatchResult:
        """
        Make decisions for a batch of failing requirements.
        
        Args:
            failed_requirements: List of requirement dicts with:
                - req_id
                - title/text
                - score
                - evaluation
                - tag (optional)
        
        Returns:
            DecisionBatchResult with all decisions and statistics
        """
        start_time = time.time()
        
        if not failed_requirements:
            return DecisionBatchResult(total_count=0)
        
        logger.info(f"[DecisionMaker] Processing {len(failed_requirements)} requirements in {self.mode.value} mode")
        
        # Create decision coroutines
        coroutines = []
        for i, req in enumerate(failed_requirements):
            coro = self.decide(
                req_id=req.get("req_id", f"REQ-{i}"),
                requirement_text=req.get("title", req.get("text", "")),
                score=req.get("score", 0.0),
                evaluation=req.get("evaluation", []),
                tag=req.get("tag"),
                questions=req.get("questions")
            )
            coroutines.append(coro)
            
            if self.progress_callback:
                self.progress_callback("decision_maker", i, len(failed_requirements), f"Analyzing {req.get('req_id')}")
        
        # Execute in parallel
        decisions = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Process results
        final_decisions = []
        errors = []
        counts = {action: 0 for action in DecisionAction}
        
        for i, result in enumerate(decisions):
            if isinstance(result, Exception):
                errors.append(f"REQ-{i}: {str(result)}")
                # Default decision
                final_decisions.append(Decision(
                    req_id=failed_requirements[i].get("req_id", f"REQ-{i}"),
                    action=DecisionAction.REWRITE,
                    reason=f"Error: {str(result)}",
                    confidence=0.0
                ))
                counts[DecisionAction.REWRITE] += 1
            else:
                final_decisions.append(result)
                counts[result.action] += 1
        
        total_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"[DecisionMaker] Completed in {total_time_ms}ms: "
                   f"SPLIT={counts[DecisionAction.SPLIT]}, "
                   f"REWRITE={counts[DecisionAction.REWRITE]}, "
                   f"ACCEPT={counts[DecisionAction.ACCEPT]}, "
                   f"CLARIFY={counts[DecisionAction.CLARIFY]}, "
                   f"REJECT={counts[DecisionAction.REJECT]}")
        
        return DecisionBatchResult(
            total_count=len(failed_requirements),
            decisions=final_decisions,
            split_count=counts[DecisionAction.SPLIT],
            rewrite_count=counts[DecisionAction.REWRITE],
            accept_count=counts[DecisionAction.ACCEPT],
            clarify_count=counts[DecisionAction.CLARIFY],
            reject_count=counts[DecisionAction.REJECT],
            total_time_ms=total_time_ms,
            errors=errors
        )
    
    async def apply_split(
        self,
        original_req: Dict[str, Any],
        split_suggestions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Apply a SPLIT decision by creating new requirements.
        
        Args:
            original_req: Original requirement dict
            split_suggestions: List of new requirement texts
        
        Returns:
            List of new requirement dicts
        """
        new_requirements = []
        base_id = original_req.get("req_id", "REQ")
        
        for i, text in enumerate(split_suggestions, start=1):
            new_req = original_req.copy()
            new_req["req_id"] = f"{base_id}-{chr(96+i)}"  # REQ-001-a, REQ-001-b, etc.
            new_req["title"] = text
            new_req["_split_from"] = original_req.get("req_id")
            new_req["_needs_validation"] = True
            new_requirements.append(new_req)
        
        logger.info(f"Split {original_req.get('req_id')} into {len(new_requirements)} requirements")
        return new_requirements
    
    async def apply_clarification_answers(
        self,
        original_req: Dict[str, Any],
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Apply clarification answers to improve the requirement.
        
        Uses LLM to integrate answers into the requirement text.
        """
        from backend.core import llm as _llm
        
        if not answers:
            return original_req
        
        requirement_text = original_req.get("title", original_req.get("text", ""))
        
        # Format answers
        answers_text = "\n".join([f"- {k}: {v}" for k, v in answers.items()])
        
        prompt = f"""Verbessere das folgende Requirement, indem du die Klärungsantworten einarbeitest.

ORIGINAL REQUIREMENT:
{requirement_text}

KLÄRUNGSANTWORTEN:
{answers_text}

Gib NUR das verbesserte Requirement zurück (kein JSON, keine Erklärung).
Behalte das User-Story Format bei, falls vorhanden."""

        try:
            response = await asyncio.to_thread(
                _llm._llm_call_sync,
                system_prompt="Du bist ein Requirements Engineer. Verbessere Requirements präzise.",
                user_prompt=prompt,
                temperature=0.2
            )
            
            improved_req = original_req.copy()
            improved_req["title"] = response.strip()
            improved_req["_clarified"] = True
            improved_req["_clarification_answers"] = answers
            improved_req["_needs_validation"] = True
            
            return improved_req
            
        except Exception as e:
            logger.error(f"Failed to apply clarification answers: {e}")
            return original_req


__all__ = [
    "DecisionAction",
    "WorkflowMode",
    "Decision",
    "DecisionBatchResult",
    "DecisionMakerAgent"
]