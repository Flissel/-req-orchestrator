# -*- coding: utf-8 -*-
"""
Clarification Agent for Intelligent Question Generation.

Analyzes validation feedback and generates prioritized clarification questions
when requirements cannot be automatically improved.

Part of the Requirements-Management-System.
See: backend/core/db.py for clarification_question table schema.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

logger = logging.getLogger("arch_team.clarification_agent")


class ClarificationPriority(Enum):
    """Priority levels for clarification questions."""
    CRITICAL = 1    # Blocks all progress, must be answered first
    HIGH = 2        # Significantly impacts requirement quality
    MEDIUM = 3      # Improves quality but not blocking
    LOW = 4         # Nice to have, optional


@dataclass
class ClarificationQuestion:
    """A single clarification question derived from validation feedback."""
    requirement_id: str
    requirement_text: str
    criterion: str
    question_text: str
    suggested_answers: List[str] = field(default_factory=list)
    context_hint: str = ""
    priority: ClarificationPriority = ClarificationPriority.MEDIUM
    score: float = 0.0
    feedback: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "requirement_text": self.requirement_text,
            "criterion": self.criterion,
            "question_text": self.question_text,
            "suggested_answers": self.suggested_answers,
            "context_hint": self.context_hint,
            "priority": self.priority.name,
            "priority_value": self.priority.value,
            "score": self.score,
            "feedback": self.feedback
        }


@dataclass
class ClarificationTask:
    """A task for generating clarification questions from validation results."""
    req_id: str
    requirement_text: str
    validation_results: List[Dict[str, Any]]  # Failed criteria with feedback
    overall_score: float
    tag: Optional[str] = None
    index: int = 0


@dataclass
class ClarificationResult:
    """Result from analyzing a requirement for clarification needs."""
    req_id: str
    needs_clarification: bool
    questions: List[ClarificationQuestion] = field(default_factory=list)
    auto_fixable_criteria: List[str] = field(default_factory=list)
    unfixable_criteria: List[str] = field(default_factory=list)
    worker_id: Optional[str] = None
    processing_time_ms: int = 0
    error: Optional[str] = None


class ClarificationAgent:
    """
    Agent for generating intelligent clarification questions from validation feedback.
    
    This agent:
    1. Analyzes which criteria can be auto-fixed vs need user input
    2. Generates contextual questions based on the specific failure
    3. Prioritizes questions by criticality
    4. Provides suggested answers when possible
    
    Usage:
        agent = ClarificationAgent()
        result = await agent.analyze(task)
    """
    
    # Criteria that can usually be auto-fixed by RewriteAgent
    AUTO_FIXABLE_CRITERIA = {
        "concise",              # Can remove unnecessary words
        "consistent_language",  # Can standardize terminology
        "follows_template",     # Can restructure to template
        "design_independent",   # Can remove implementation details
        "purpose_independent",  # Can remove business rationale
    }
    
    # Criteria that typically need user input
    NEEDS_USER_INPUT_CRITERIA = {
        "measurability",        # Need specific numbers from user
        "testability",          # Need acceptance criteria from user
        "clarity",              # May need domain knowledge
        "atomic",               # User decides which sub-requirements to keep
        "unambiguous",          # User clarifies intended meaning
    }
    
    # Question templates for each criterion
    QUESTION_TEMPLATES = {
        "measurability": {
            "pattern": "Welche konkreten Messwerte sollen für '{subject}' gelten?",
            "context": "Diese Anforderung enthält keine quantifizierbaren Metriken.",
            "suggestions": [
                "Maximal {n} Sekunden Antwortzeit",
                "Mindestens {n}% Verfügbarkeit",
                "Maximal {n} gleichzeitige Nutzer",
                "Bitte spezifischen Wert angeben"
            ]
        },
        "testability": {
            "pattern": "Wie kann überprüft werden, dass '{subject}' korrekt funktioniert?",
            "context": "Es fehlen konkrete Akzeptanzkriterien für die Verifikation.",
            "suggestions": [
                "GIVEN-WHEN-THEN Testfall beschreiben",
                "Manuelle Testanweisung angeben",
                "Automatisierter Testansatz vorschlagen",
                "Keine Akzeptanzkriterien notwendig"
            ]
        },
        "clarity": {
            "pattern": "Was genau ist mit '{ambiguous_term}' gemeint?",
            "context": "Der Begriff ist mehrdeutig oder unklar im Kontext.",
            "suggestions": [
                "Definition des Begriffs angeben",
                "Synonyme oder Beispiele nennen",
                "Den Begriff aus der Anforderung entfernen",
                "Der Begriff ist branchenüblich, beibehalten"
            ]
        },
        "atomic": {
            "pattern": "Diese Anforderung enthält mehrere Aspekte. Welcher soll priorisiert werden?",
            "context": "Atomare Anforderungen behandeln nur eine Sache.",
            "suggestions": [
                "In separate Anforderungen aufteilen",
                "Nur den Hauptaspekt behalten",
                "Beide Aspekte sind untrennbar verbunden",
                "Sekundären Aspekt entfernen"
            ]
        },
        "unambiguous": {
            "pattern": "Der Begriff '{vague_term}' ist vage. Was ist die genaue Bedeutung?",
            "context": "Begriffe wie 'schnell', 'einfach', 'ungefähr' sind nicht präzise.",
            "suggestions": [
                "Konkreten Wert angeben",
                "Vergleichsreferenz nennen",
                "Den Begriff präzisieren",
                "Begriff entfernen, wenn nicht kritisch"
            ]
        }
    }
    
    # Priority mapping based on criteria importance
    CRITERIA_PRIORITY = {
        "measurability": ClarificationPriority.CRITICAL,
        "testability": ClarificationPriority.CRITICAL,
        "clarity": ClarificationPriority.HIGH,
        "atomic": ClarificationPriority.HIGH,
        "unambiguous": ClarificationPriority.MEDIUM,
        "concise": ClarificationPriority.LOW,
        "consistent_language": ClarificationPriority.LOW,
        "follows_template": ClarificationPriority.LOW,
        "design_independent": ClarificationPriority.MEDIUM,
        "purpose_independent": ClarificationPriority.LOW,
    }
    
    def __init__(
        self,
        semaphore: Optional[asyncio.Semaphore] = None,
        progress_callback: Optional[Callable[[str, int, int, str], None]] = None,
        auto_fix_threshold: float = 0.5
    ):
        """
        Initialize clarification agent.
        
        Args:
            semaphore: Optional AsyncSemaphore for rate limiting
            progress_callback: Optional callback(worker_id, completed, total, message)
            auto_fix_threshold: Criteria scores below this may need user input (default: 0.5)
        """
        self.semaphore = semaphore or asyncio.Semaphore(5)
        self.progress_callback = progress_callback
        self.auto_fix_threshold = auto_fix_threshold
        self.worker_id = "clarification-agent"
        self._timeout = int(os.environ.get("CLARIFICATION_TIMEOUT", "30"))
    
    async def analyze(
        self,
        task: ClarificationTask,
        total_tasks: int = 1
    ) -> ClarificationResult:
        """
        Analyze a requirement's validation results and generate clarification questions.
        
        Args:
            task: ClarificationTask with requirement and validation feedback
            total_tasks: Total number of tasks in batch (for progress)
        
        Returns:
            ClarificationResult with questions and categorized criteria
        """
        start_time = time.time()
        
        async with self.semaphore:
            logger.debug(f"[{self.worker_id}] Analyzing {task.req_id}")
            
            if self.progress_callback:
                self.progress_callback(
                    self.worker_id,
                    task.index + 1,
                    total_tasks,
                    f"Analyzing {task.req_id} for clarification needs..."
                )
            
            try:
                # Categorize failed criteria
                auto_fixable = []
                needs_input = []
                questions = []
                
                for eval_item in task.validation_results:
                    if eval_item.get("passed", True):
                        continue
                    
                    criterion = eval_item.get("criterion", "unknown")
                    score = eval_item.get("score", 0.0)
                    feedback = eval_item.get("feedback", "")
                    
                    # Determine if auto-fixable or needs user input
                    if criterion in self.AUTO_FIXABLE_CRITERIA:
                        auto_fixable.append(criterion)
                    elif criterion in self.NEEDS_USER_INPUT_CRITERIA:
                        # Only require input if score is very low
                        if score < self.auto_fix_threshold:
                            needs_input.append(criterion)
                            
                            # Generate question for this criterion
                            question = self._generate_question(
                                task.req_id,
                                task.requirement_text,
                                criterion,
                                score,
                                feedback
                            )
                            if question:
                                questions.append(question)
                        else:
                            # Score is okay, try auto-fix first
                            auto_fixable.append(criterion)
                    else:
                        # Unknown criterion, try auto-fix
                        auto_fixable.append(criterion)
                
                # Sort questions by priority
                questions.sort(key=lambda q: q.priority.value)
                
                processing_time = int((time.time() - start_time) * 1000)
                
                return ClarificationResult(
                    req_id=task.req_id,
                    needs_clarification=len(questions) > 0,
                    questions=questions,
                    auto_fixable_criteria=auto_fixable,
                    unfixable_criteria=needs_input,
                    worker_id=self.worker_id,
                    processing_time_ms=processing_time
                )
                
            except Exception as e:
                logger.error(f"[{self.worker_id}] Error analyzing {task.req_id}: {e}")
                return ClarificationResult(
                    req_id=task.req_id,
                    needs_clarification=False,
                    error=str(e),
                    worker_id=self.worker_id,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
    
    def _generate_question(
        self,
        req_id: str,
        requirement_text: str,
        criterion: str,
        score: float,
        feedback: str
    ) -> Optional[ClarificationQuestion]:
        """
        Generate a clarification question for a specific criterion.
        
        Args:
            req_id: Requirement ID
            requirement_text: The requirement text
            criterion: Failed criterion name
            score: Criterion score
            feedback: Validation feedback
        
        Returns:
            ClarificationQuestion or None if no question can be generated
        """
        template = self.QUESTION_TEMPLATES.get(criterion)
        if not template:
            # Generate generic question for unknown criteria
            return ClarificationQuestion(
                requirement_id=req_id,
                requirement_text=requirement_text,
                criterion=criterion,
                question_text=f"Wie kann das Kriterium '{criterion}' für diese Anforderung erfüllt werden?",
                suggested_answers=[
                    "Konkreten Vorschlag machen",
                    "Anforderung ist korrekt, Kriterium ignorieren",
                    "Anforderung entfernen"
                ],
                context_hint=feedback or f"Kriterium '{criterion}' wurde nicht erfüllt.",
                priority=self.CRITERIA_PRIORITY.get(criterion, ClarificationPriority.MEDIUM),
                score=score,
                feedback=feedback
            )
        
        # Extract subject/term from requirement for question personalization
        subject = self._extract_subject(requirement_text, criterion)
        
        # Build question text
        question_text = template["pattern"].format(
            subject=subject,
            ambiguous_term=subject,
            vague_term=subject
        )
        
        # Get suggested answers
        suggested = [s.format(n="[Zahl]") for s in template.get("suggestions", [])]
        
        return ClarificationQuestion(
            requirement_id=req_id,
            requirement_text=requirement_text,
            criterion=criterion,
            question_text=question_text,
            suggested_answers=suggested,
            context_hint=template.get("context", "") + f"\n\nValidierungs-Feedback: {feedback}",
            priority=self.CRITERIA_PRIORITY.get(criterion, ClarificationPriority.MEDIUM),
            score=score,
            feedback=feedback
        )
    
    def _extract_subject(self, requirement_text: str, criterion: str) -> str:
        """
        Extract the main subject/term from requirement text for personalized questions.
        
        Simple heuristic: Use first noun phrase or the whole requirement if short.
        """
        # For now, use a simple truncation approach
        if len(requirement_text) <= 50:
            return requirement_text
        
        # Try to find the main action/object
        words = requirement_text.split()
        if len(words) <= 5:
            return requirement_text
        
        # Return first ~50 chars with word boundary
        truncated = requirement_text[:50]
        last_space = truncated.rfind(' ')
        if last_space > 30:
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    async def analyze_batch(
        self,
        tasks: List[ClarificationTask]
    ) -> List[ClarificationResult]:
        """
        Analyze multiple requirements for clarification needs in parallel.
        
        Args:
            tasks: List of ClarificationTasks
        
        Returns:
            List of ClarificationResults
        """
        logger.info(f"[{self.worker_id}] Analyzing {len(tasks)} requirements for clarification needs")
        
        # Create coroutines for parallel execution
        coroutines = [
            self.analyze(task, len(tasks))
            for task in tasks
        ]
        
        # Execute in parallel with semaphore limiting
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {tasks[i].req_id} failed: {result}")
                final_results.append(ClarificationResult(
                    req_id=tasks[i].req_id,
                    needs_clarification=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results


__all__ = [
    "ClarificationPriority",
    "ClarificationQuestion",
    "ClarificationTask",
    "ClarificationResult",
    "ClarificationAgent"
]