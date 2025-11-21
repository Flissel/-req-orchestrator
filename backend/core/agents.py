# -*- coding: utf-8 -*-
"""
AutoGen Agents für Requirements Engineering
Distributed Processing von Requirements über gRPC Worker Runtime
"""

import asyncio
import logging
import inspect
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime

from autogen_core import (
    AgentId,
    DefaultSubscription,
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    message_handler,
    try_get_known_serializers_for_type
)

# Import bestehender Backend-Module
from .llm import llm_evaluate, llm_suggest, llm_rewrite
from .utils import compute_verdict, sha256_text, weighted_score
from .db import get_db

logger = logging.getLogger(__name__)

# Utility: Unterstützt sync/async Callables transparent
async def _maybe_await(func, *args, **kwargs):
    """
    Ruft func wahlweise synchron oder asynchron auf.
    - Unterstützt reine kwargs-Aufrufe (unsere Call-Sites nutzen Keyword-Args).
    - Wenn das Ergebnis awaitable ist, wird es awaited, sonst direkt zurückgegeben.
    """
    try:
        result = func(*args, **kwargs)
    except TypeError:
        # Falls die Signatur nur kwargs erwartet oder args leer sein sollen
        result = func(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result

# =============================================================================
# Message Types für Agent-Kommunikation
# =============================================================================

@dataclass
class RequirementProcessingRequest:
    """Request für Requirements Processing"""
    requirement_id: str
    requirement_text: str
    context: Dict[str, Any]
    criteria_keys: Optional[List[str]] = None
    request_id: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass 
class EvaluationResult:
    """Ergebnis der Requirements-Evaluation"""
    requirement_id: str
    request_id: str
    evaluation_id: str
    score: float
    verdict: str
    details: Dict[str, float]
    latency_ms: int
    model_used: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class SuggestionResult:
    """Ergebnis der Suggestion-Generierung"""
    requirement_id: str
    request_id: str
    suggestions: List[str]
    latency_ms: int
    model_used: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class RewriteResult:
    """Ergebnis des Requirements-Rewrite"""
    requirement_id: str
    request_id: str
    rewritten_text: str
    latency_ms: int
    model_used: str
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class ProcessingStatusUpdate:
    """Status-Update für Processing Pipeline"""
    requirement_id: str
    request_id: str
    stage: str  # "evaluation", "suggestion", "rewrite", "completed"
    status: str  # "started", "completed", "failed"
    message: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class BatchProcessingRequest:
    """Request für Batch-Processing von Requirements"""
    batch_id: str
    requirements: List[RequirementProcessingRequest]
    processing_types: List[str]  # ["evaluation", "suggestion", "rewrite"]
    parallel_limit: int = 3
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class AtomicSplitRequest:
    """Request für Atomicity Check und Splitting"""
    requirement_id: str
    requirement_text: str
    context: Dict[str, Any]
    max_splits: int = 5
    retry_attempt: int = 0
    request_id: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"split_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class AtomicSplitResult:
    """Ergebnis des Atomicity Checks und Splittings"""
    requirement_id: str
    request_id: str
    is_atomic: bool
    atomic_score: float
    splits: List[Dict[str, str]]  # List of {text: "...", rationale: "..."}
    error_message: Optional[str] = None
    retry_count: int = 0
    latency_ms: int = 0
    model_used: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

# =============================================================================
# Requirements Processing Agents
# =============================================================================

class RequirementsEvaluatorAgent(RoutedAgent):
    """Agent für Requirements-Evaluation mit LLM"""
    
    def __init__(self, agent_name: str = "RequirementsEvaluator") -> None:
        # Stelle _id bereits vor Basisklassen-Init bereit
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Evaluiert Requirements mit LLM")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.processed_count = 0
        logger.info(f"RequirementsEvaluatorAgent initialisiert: {self.id}")
    
    @message_handler
    async def evaluate_requirement(self, message: RequirementProcessingRequest, ctx: MessageContext) -> None:
        """Evaluiert ein einzelnes Requirement"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starte Evaluation für Requirement: {message.requirement_id}")
            
            # Status-Update senden
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="evaluation",
                    status="started",
                    message=f"Evaluation gestartet von Agent {self.id.key}"
                ),
                topic_id=DefaultTopicId()
            )
            
            # LLM Evaluation ausführen
            evaluation_result = await _maybe_await(
                llm_evaluate,
                requirement_text=message.requirement_text,
                context=message.context,
                criteria_keys=message.criteria_keys,
            )
            
            end_time = asyncio.get_event_loop().time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Evaluation-Ergebnis erstellen
            result = EvaluationResult(
                requirement_id=message.requirement_id,
                request_id=message.request_id,
                evaluation_id=f"eval_{message.requirement_id}_{int(asyncio.get_event_loop().time())}",
                score=evaluation_result.get("score", 0.0),
                verdict=evaluation_result.get("verdict", "unknown"),
                details=evaluation_result.get("details", {}),
                latency_ms=latency_ms,
                model_used=evaluation_result.get("model", "unknown")
            )
            
            # Ergebnis publizieren
            await self.publish_message(result, topic_id=DefaultTopicId())
            
            # Status-Update: Completed
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="evaluation",
                    status="completed",
                    message=f"Evaluation abgeschlossen. Score: {result.score:.2f}, Verdict: {result.verdict}"
                ),
                topic_id=DefaultTopicId()
            )
            
            self.processed_count += 1
            logger.info(f"Evaluation erfolgreich für {message.requirement_id}. Total verarbeitet: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"Fehler bei Evaluation von {message.requirement_id}: {str(e)}")
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="evaluation",
                    status="failed",
                    message=f"Evaluation fehlgeschlagen: {str(e)}"
                ),
                topic_id=DefaultTopicId()
            )

class RequirementsSuggestionAgent(RoutedAgent):
    """Agent für Requirements-Suggestion-Generierung"""
    
    def __init__(self, agent_name: str = "RequirementsSuggester") -> None:
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Generiert Verbesserungsvorschläge")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.processed_count = 0
        logger.info(f"RequirementsSuggestionAgent initialisiert: {self.id}")
    
    @message_handler
    async def generate_suggestions(self, message: RequirementProcessingRequest, ctx: MessageContext) -> None:
        """Generiert Suggestions für ein Requirement"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starte Suggestion-Generierung für: {message.requirement_id}")
            
            # Status-Update
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="suggestion",
                    status="started",
                    message=f"Suggestion-Generierung gestartet von Agent {self.id.key}"
                ),
                topic_id=DefaultTopicId()
            )
            
            # LLM Suggestions generieren
            suggestions_result = await _maybe_await(
                llm_suggest,
                requirement_text=message.requirement_text,
                context=message.context,
            )
            
            end_time = asyncio.get_event_loop().time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Suggestion-Ergebnis erstellen
            result = SuggestionResult(
                requirement_id=message.requirement_id,
                request_id=message.request_id,
                suggestions=suggestions_result.get("suggestions", []),
                latency_ms=latency_ms,
                model_used=suggestions_result.get("model", "unknown")
            )
            
            # Ergebnis publizieren
            await self.publish_message(result, topic_id=DefaultTopicId())
            
            # Status-Update: Completed
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="suggestion",
                    status="completed",
                    message=f"Suggestions generiert: {len(result.suggestions)} Vorschläge"
                ),
                topic_id=DefaultTopicId()
            )
            
            self.processed_count += 1
            logger.info(f"Suggestions generiert für {message.requirement_id}. Total: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"Fehler bei Suggestion-Generierung für {message.requirement_id}: {str(e)}")
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="suggestion", 
                    status="failed",
                    message=f"Suggestion fehlgeschlagen: {str(e)}"
                ),
                topic_id=DefaultTopicId()
            )

class RequirementsRewriteAgent(RoutedAgent):
    """Agent für Requirements-Rewriting"""
    
    def __init__(self, agent_name: str = "RequirementsRewriter") -> None:
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Schreibt Requirements um")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.processed_count = 0
        logger.info(f"RequirementsRewriteAgent initialisiert: {self.id}")
    
    @message_handler
    async def rewrite_requirement(self, message: RequirementProcessingRequest, ctx: MessageContext) -> None:
        """Schreibt ein Requirement um"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starte Rewrite für: {message.requirement_id}")
            
            # Status-Update
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="rewrite",
                    status="started",
                    message=f"Rewrite gestartet von Agent {self.id.key}"
                ),
                topic_id=DefaultTopicId()
            )
            
            # LLM Rewrite ausführen
            rewrite_result = await _maybe_await(
                llm_rewrite,
                requirement_text=message.requirement_text,
                context=message.context,
            )
            
            end_time = asyncio.get_event_loop().time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Rewrite-Ergebnis erstellen
            result = RewriteResult(
                requirement_id=message.requirement_id,
                request_id=message.request_id,
                rewritten_text=rewrite_result.get("rewritten_requirement", ""),
                latency_ms=latency_ms,
                model_used=rewrite_result.get("model", "unknown")
            )
            
            # Ergebnis publizieren
            await self.publish_message(result, topic_id=DefaultTopicId())
            
            # Status-Update: Completed
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="rewrite",
                    status="completed",
                    message=f"Rewrite abgeschlossen. Länge: {len(result.rewritten_text)} Zeichen"
                ),
                topic_id=DefaultTopicId()
            )
            
            self.processed_count += 1
            logger.info(f"Rewrite abgeschlossen für {message.requirement_id}. Total: {self.processed_count}")
            
        except Exception as e:
            logger.error(f"Fehler bei Rewrite von {message.requirement_id}: {str(e)}")
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="rewrite",
                    status="failed",
                    message=f"Rewrite fehlgeschlagen: {str(e)}"
                ),
                topic_id=DefaultTopicId()
            )

class RequirementsOrchestratorAgent(RoutedAgent):
    """Master Agent für Requirements Processing Orchestration"""
    
    def __init__(self, agent_name: str = "RequirementsOrchestrator") -> None:
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Orchestriert Requirements Processing")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.active_requests: Dict[str, Dict] = {}
        self.results_cache: Dict[str, Dict] = {}
        logger.info(f"RequirementsOrchestratorAgent initialisiert: {self.id}")
    
    @message_handler
    async def process_batch_request(self, message: BatchProcessingRequest, ctx: MessageContext) -> None:
        """Verarbeitet Batch von Requirements"""
        logger.info(f"Starte Batch-Processing: {message.batch_id} mit {len(message.requirements)} Requirements")
        
        try:
            # Jedes Requirement an entsprechende Worker senden
            for req in message.requirements:
                self.active_requests[req.request_id] = {
                    "requirement_id": req.requirement_id,
                    "processing_types": message.processing_types,
                    "completed_stages": [],
                    "results": {},
                    "start_time": asyncio.get_event_loop().time()
                }
                
                # Je nach Processing-Type entsprechende Messages senden
                for processing_type in message.processing_types:
                    if processing_type == "evaluation":
                        await self.publish_message(req, topic_id=DefaultTopicId())
                    elif processing_type == "suggestion":
                        await self.publish_message(req, topic_id=DefaultTopicId())
                    elif processing_type == "rewrite":
                        await self.publish_message(req, topic_id=DefaultTopicId())
                        
        except Exception as e:
            logger.error(f"Fehler beim Batch-Processing {message.batch_id}: {str(e)}")
    
    @message_handler
    async def handle_evaluation_result(self, message: EvaluationResult, ctx: MessageContext) -> None:
        """Verarbeitet Evaluation-Ergebnisse"""
        if message.request_id in self.active_requests:
            self.active_requests[message.request_id]["results"]["evaluation"] = message
            self.active_requests[message.request_id]["completed_stages"].append("evaluation")
            logger.info(f"Evaluation-Ergebnis erhalten für {message.requirement_id}")
    
    @message_handler
    async def handle_suggestion_result(self, message: SuggestionResult, ctx: MessageContext) -> None:
        """Verarbeitet Suggestion-Ergebnisse"""
        if message.request_id in self.active_requests:
            self.active_requests[message.request_id]["results"]["suggestion"] = message
            self.active_requests[message.request_id]["completed_stages"].append("suggestion")
            logger.info(f"Suggestion-Ergebnis erhalten für {message.requirement_id}")
    
    @message_handler
    async def handle_rewrite_result(self, message: RewriteResult, ctx: MessageContext) -> None:
        """Verarbeitet Rewrite-Ergebnisse"""
        if message.request_id in self.active_requests:
            self.active_requests[message.request_id]["results"]["rewrite"] = message
            self.active_requests[message.request_id]["completed_stages"].append("rewrite")
            logger.info(f"Rewrite-Ergebnis erhalten für {message.requirement_id}")
    
    @message_handler
    async def handle_status_update(self, message: ProcessingStatusUpdate, ctx: MessageContext) -> None:
        """Verarbeitet Status-Updates"""
        logger.debug(f"Status-Update: {message.requirement_id} - {message.stage} - {message.status}")

# =============================================================================
# Observer Agent für Monitoring und Logging
# =============================================================================

class RequirementsAtomicityAgent(RoutedAgent):
    """Agent für Atomicity Check und Splitting von Requirements"""

    def __init__(self, agent_name: str = "RequirementsAtomicity") -> None:
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Prüft Atomicity und splittet komplexe Requirements")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.processed_count = 0
        self.split_count = 0
        logger.info(f"RequirementsAtomicityAgent initialisiert: {self.id}")

    @message_handler
    async def check_and_split_atomic(self, message: AtomicSplitRequest, ctx: MessageContext) -> None:
        """Prüft Atomicity und splittet bei Bedarf"""
        start_time = asyncio.get_event_loop().time()

        try:
            logger.info(f"Starte Atomicity-Check für: {message.requirement_id}")

            # Status-Update
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="atomicity",
                    status="started",
                    message=f"Atomicity-Check gestartet von Agent {self.id.key}"
                ),
                topic_id=DefaultTopicId()
            )

            # Atomicity evaluieren (nur "atomic" Kriterium)
            eval_result = await self._evaluate_atomic(
                message.requirement_text,
                message.context
            )

            atomic_score = eval_result.get("details", {}).get("atomic", 0.0)
            is_atomic = atomic_score >= 0.7  # Threshold für Atomicity

            splits = []
            error_message = None

            # Wenn nicht atomic: Splitting mit Retry
            if not is_atomic:
                logger.info(f"Requirement {message.requirement_id} ist nicht atomic (Score: {atomic_score:.2f}). Starte Splitting...")
                try:
                    splits = await self._split_with_retry(
                        message.requirement_text,
                        message.context,
                        message.max_splits,
                        message.retry_attempt
                    )
                    self.split_count += 1
                except Exception as split_error:
                    error_message = f"Splitting fehlgeschlagen: {str(split_error)}"
                    logger.error(f"Splitting-Fehler für {message.requirement_id}: {error_message}")

            end_time = asyncio.get_event_loop().time()
            latency_ms = int((end_time - start_time) * 1000)

            # Ergebnis erstellen
            result = AtomicSplitResult(
                requirement_id=message.requirement_id,
                request_id=message.request_id,
                is_atomic=is_atomic,
                atomic_score=atomic_score,
                splits=splits,
                error_message=error_message,
                retry_count=message.retry_attempt,
                latency_ms=latency_ms,
                model_used=eval_result.get("model", "unknown")
            )

            # Ergebnis publizieren
            await self.publish_message(result, topic_id=DefaultTopicId())

            # Status-Update: Completed
            status_msg = f"Atomicity-Check abgeschlossen. Score: {atomic_score:.2f}"
            if not is_atomic:
                status_msg += f", {len(splits)} Splits generiert"

            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="atomicity",
                    status="completed",
                    message=status_msg
                ),
                topic_id=DefaultTopicId()
            )

            self.processed_count += 1
            logger.info(f"Atomicity-Check abgeschlossen für {message.requirement_id}. Total: {self.processed_count}")

        except Exception as e:
            logger.error(f"Fehler bei Atomicity-Check von {message.requirement_id}: {str(e)}")
            await self.publish_message(
                ProcessingStatusUpdate(
                    requirement_id=message.requirement_id,
                    request_id=message.request_id,
                    stage="atomicity",
                    status="failed",
                    message=f"Atomicity-Check fehlgeschlagen: {str(e)}"
                ),
                topic_id=DefaultTopicId()
            )

    async def _evaluate_atomic(self, requirement_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluiert nur das 'atomic' Kriterium"""
        # llm_evaluate returns List[Dict] with criterion details
        details_list = await _maybe_await(
            llm_evaluate,
            requirement_text=requirement_text,
            context=context,
            criteria_keys=["atomic"]
        )

        # Convert list to dict format expected by check_and_split_atomic
        details_dict = {}
        for criterion_detail in details_list:
            criterion_key = criterion_detail.get("criterion")
            if criterion_key:
                details_dict[criterion_key] = criterion_detail.get("score", 0.0)

        return {
            "details": details_dict,
            "model": "gpt-4o-mini"  # Default model
        }

    async def _split_with_retry(
        self,
        requirement_text: str,
        context: Dict[str, Any],
        max_splits: int,
        current_attempt: int = 0
    ) -> List[Dict[str, str]]:
        """Splittet Requirement mit Retry-Logik (max 3 Versuche)"""
        max_retries = 3

        for attempt in range(current_attempt, max_retries):
            try:
                logger.debug(f"Splitting-Versuch {attempt + 1}/{max_retries}")
                splits = await self._split_atomic_llm(requirement_text, context, max_splits)

                # Validierung: Mindestens 2 Splits, maximal max_splits
                if not splits or len(splits) < 2:
                    raise ValueError(f"Zu wenige Splits generiert: {len(splits)}")
                if len(splits) > max_splits:
                    splits = splits[:max_splits]
                    logger.warning(f"Mehr als {max_splits} Splits generiert, gekürzt auf {max_splits}")

                # Validierung: Jeder Split muss 'text' und 'rationale' haben
                for i, split in enumerate(splits):
                    if "text" not in split or not split["text"].strip():
                        raise ValueError(f"Split {i} hat kein 'text' Feld")
                    if "rationale" not in split:
                        split["rationale"] = ""  # Optional, füge leeren String hinzu

                logger.info(f"Splitting erfolgreich: {len(splits)} atomare Requirements generiert")
                return splits

            except Exception as e:
                logger.warning(f"Splitting-Versuch {attempt + 1} fehlgeschlagen: {str(e)}")
                if attempt == max_retries - 1:
                    # Letzter Versuch fehlgeschlagen
                    raise Exception(f"Splitting nach {max_retries} Versuchen fehlgeschlagen: {str(e)}")
                # Kurze Pause vor erneutem Versuch
                await asyncio.sleep(0.5)

        return []

    async def _split_atomic_llm(
        self,
        requirement_text: str,
        context: Dict[str, Any],
        max_splits: int
    ) -> List[Dict[str, str]]:
        """LLM-basiertes Splitting in atomare Requirements"""
        import json
        import os
        from openai import OpenAI

        prompt = f"""Du bist ein Experte für Requirements Engineering.
Analysiere folgendes Requirement und teile es in atomare, eigenständige Sub-Requirements auf.

**Requirement:** {requirement_text}

**Regeln:**
1. Jedes Sub-Requirement muss GENAU EINE Aussage enthalten (atomic principle)
2. Jedes Sub-Requirement muss eigenständig verständlich sein
3. Erstelle mindestens 2, maximal {max_splits} Sub-Requirements
4. Vermeide Redundanz zwischen den Sub-Requirements
5. Behalte die ursprüngliche Intention bei

**Antwortformat (JSON):**
{{
  "splits": [
    {{
      "text": "Das erste atomare Sub-Requirement",
      "rationale": "Erklärung, warum dies ein eigenständiges Requirement ist"
    }},
    {{
      "text": "Das zweite atomare Sub-Requirement",
      "rationale": "Erklärung, warum dies ein eigenständiges Requirement ist"
    }}
  ]
}}

Antworte NUR mit dem JSON-Objekt, ohne zusätzlichen Text."""

        try:
            # OpenAI Client erstellen
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY nicht gesetzt")

            client = OpenAI(api_key=api_key)

            # OpenAI API call mit JSON response format
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Günstiges, schnelles Modell für Splitting
                messages=[
                    {"role": "system", "content": "Du bist ein Requirements Engineering Experte."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Niedrige Temperatur für konsistente Splits
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            parsed = json.loads(content)

            if "splits" not in parsed:
                raise ValueError("Response enthält kein 'splits' Feld")

            return parsed["splits"]

        except json.JSONDecodeError as e:
            raise ValueError(f"LLM Response ist kein valides JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"LLM Splitting fehlgeschlagen: {str(e)}")

class RequirementsMonitorAgent(RoutedAgent):
    """Agent für Monitoring und Logging des gesamten Systems"""

    def __init__(self, agent_name: str = "RequirementsMonitor") -> None:
        try:
            self._id = getattr(self, "_id", AgentId(type=str(agent_name), key=str(agent_name)))
        except Exception:
            self._id = AgentId(type=str(agent_name), key=str(agent_name))
        super().__init__(f"{agent_name} - Monitort System Performance")
        # Öffentliche id sicherstellen (für Tests/Logs)
        try:
            if not hasattr(self, "id") or self.id is None:
                self.id = self._id
        except Exception:
            self.id = self._id
        self.processing_stats = {
            "total_requests": 0,
            "completed_evaluations": 0,
            "completed_suggestions": 0,
            "completed_rewrites": 0,
            "failed_requests": 0,
            "average_latency": 0.0
        }
        logger.info(f"RequirementsMonitorAgent initialisiert: {self.id}")
    
    @message_handler
    async def monitor_status_update(self, message: ProcessingStatusUpdate, ctx: MessageContext) -> None:
        """Monitort alle Status-Updates"""
        if message.status == "started":
            self.processing_stats["total_requests"] += 1
        elif message.status == "completed":
            if message.stage == "evaluation":
                self.processing_stats["completed_evaluations"] += 1
            elif message.stage == "suggestion":
                self.processing_stats["completed_suggestions"] += 1
            elif message.stage == "rewrite":
                self.processing_stats["completed_rewrites"] += 1
        elif message.status == "failed":
            self.processing_stats["failed_requests"] += 1
            
        # Statistiken loggen (alle 10 Requests)
        if self.processing_stats["total_requests"] % 10 == 0:
            logger.info(f"Processing Stats: {self.processing_stats}")

# =============================================================================
# Message Serializer Registration Helper
# =============================================================================

def register_all_message_serializers(runtime):
    """Registriert alle Message-Types für Serialization"""
    message_types = [
        RequirementProcessingRequest,
        EvaluationResult,
        SuggestionResult,
        RewriteResult,
        ProcessingStatusUpdate,
        BatchProcessingRequest,
        AtomicSplitRequest,
        AtomicSplitResult
    ]

    for msg_type in message_types:
        try:
            serializers = try_get_known_serializers_for_type(msg_type)
            runtime.add_message_serializer(serializers)
            logger.debug(f"Serializer registriert für: {msg_type.__name__}")
        except Exception as e:
            logger.warning(f"Konnte Serializer für {msg_type.__name__} nicht registrieren: {e}")

    logger.info("Alle Message-Serializer erfolgreich registriert")
