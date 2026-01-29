# -*- coding: utf-8 -*-
"""
EvaluationService (framework-frei, DI-ready)

Zweck
- Kapselt Evaluations-Logik (einzeln/Batch) ohne direkte Web-/Framework-Kopplung.
- Nutzt Ports/Adapter (Persistence/Embeddings), LLM-Aufrufe werden in einer
  nachgelagerten Iteration über einen dedizierten LLM-Port abstrahiert.

Aktueller Stand
- evaluate_single: Einzel-Evaluation
- evaluate_batch: Sequenzielle Batch-Evaluation (Fallback)
- evaluate_batch_optimized: ECHTES LLM-Batching mit paralleler Batch-Verarbeitung
"""

from __future__ import annotations

import os
import concurrent.futures
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .ports import EmbeddingsPort, PersistencePort, RequestContext, ServiceError, LLMPort, safe_request_id
from .adapters import EmbeddingsAdapter, PersistenceAdapter
from .adapters import LLMAdapter
from backend.core import utils as _utils
from backend.core import settings as _settings

# All 9 quality criteria (fallback when no criteria specified)
DEFAULT_CRITERIA_KEYS = [
    "clarity", "testability", "measurability",
    "atomic", "concise", "unambiguous",
    "consistent_language",
    "design_independent", "purpose_independent"
]

# Default batch size (can be overridden via VALIDATION_BATCH_SIZE env var)
DEFAULT_BATCH_SIZE = int(os.environ.get("VALIDATION_BATCH_SIZE", "5"))


class EvaluationService:
    """
    EvaluationService

    Abhängigkeiten:
    - persistence: PersistencePort (DB-Zugriffe wie load_criteria, latest eval/rewrite)
    - embeddings: EmbeddingsPort (optional für Einbettungs-basierte Metriken in späteren Erweiterungen)

    Hinweise:
    - LLM-Aufrufe werden über LLMAdapter abstrahiert
    - evaluate_batch_optimized nutzt echtes LLM-Batching für ~3x Speedup
    """

    def __init__(
        self,
        persistence: Optional[PersistencePort] = None,
        embeddings: Optional[EmbeddingsPort] = None,
        llm: Optional[LLMPort] = None,
    ) -> None:
        self._persistence = persistence or PersistenceAdapter()
        self._embeddings = embeddings or EmbeddingsAdapter()
        self._llm = llm or LLMAdapter()

    # -----------------------
    # Einzel-Evaluation
    # -----------------------

    def evaluate_single(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        criteria_keys: Optional[Sequence[str]] = None,
        threshold: Optional[float] = None,
        ctx: Optional[RequestContext] = None,
    ) -> Dict[str, Any]:
        """
        Implementierung über LLMPort (evaluate) + Aggregation/Decision gemäß CONFIG/Threshold.
        Rückgabe:
        {
          "requirementText": "...",
          "evaluation": [ { "criterion": str, "score": float, "passed": bool, "feedback": str } ],
          "score": float,
          "verdict": "pass" | "fail",
        }
        """
        if not isinstance(requirement_text, str) or not requirement_text.strip():
            raise ServiceError("invalid_request", "requirementText fehlt oder leer", details={"request_id": getattr(ctx, "request_id", None)})
        try:
            # Kriterien laden/auswählen
            all_criteria = self._persistence.load_criteria(ctx=ctx)  # List[Mapping]
            if criteria_keys:
                crit_keys = list(criteria_keys)
                crits = [
                    c for c in all_criteria if str(c.get("key")) in crit_keys
                ]
                # Fallback: falls Filter leer (z. B. ungültige Keys), nutze alle
                if not crits:
                    crits = list(all_criteria)
                    crit_keys = [str(c.get("key")) for c in crits]
            else:
                crits = list(all_criteria)
                crit_keys = [str(c.get("key")) for c in crits]
                if not crit_keys:
                    crit_keys = DEFAULT_CRITERIA_KEYS
            # LLM Evaluate
            details = self._llm.evaluate(
                requirement_text,
                crit_keys,
                context=dict(context or {}),
                ctx=ctx,
            )
            # Score + Verdict
            score = float(_utils.weighted_score(details, list(crits)))
            thr = float(
                threshold
                if isinstance(threshold, (int, float))
                else getattr(_settings, "VERDICT_THRESHOLD", 0.7)
            )
            verdict = _utils.compute_verdict(score, thr)
            return {
                "requirementText": requirement_text,
                "evaluation": details,
                "score": score,
                "verdict": verdict,
            }
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("evaluation_failed", "evaluate_single failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    # -----------------------
    # Batch-Evaluation (Legacy - sequenziell)
    # -----------------------

    def evaluate_batch(
        self,
        items: Sequence[str],
        *,
        context: Optional[Mapping[str, Any]] = None,
        criteria_keys: Optional[Sequence[str]] = None,
        threshold: Optional[float] = None,
        max_parallel: Optional[int] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Sequenzielle Batch-Evaluation (Legacy-Modus).
        Für optimierte Performance nutze evaluate_batch_optimized().
        """
        if not items:
            return []
        results: List[Dict[str, Any]] = []
        try:
            for idx, text in enumerate(items, start=1):
                single = self.evaluate_single(
                    str(text or ""),
                    context=context,
                    criteria_keys=criteria_keys,
                    threshold=threshold,
                    ctx=ctx,
                )
                results.append(
                    {
                        "id": f"item-{idx}",
                        "originalText": str(text or ""),
                        "evaluation": list(single.get("evaluation", [])),
                        "score": float(single.get("score", 0.0)),
                        "verdict": str(single.get("verdict", "")),
                    }
                )
            return results
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("evaluation_batch_failed", "evaluate_batch failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    # -----------------------
    # Batch-Evaluation OPTIMIERT (echtes LLM-Batching)
    # -----------------------

    def evaluate_batch_optimized(
        self,
        items: Sequence[Dict[str, Any]],
        *,
        context: Optional[Mapping[str, Any]] = None,
        criteria_keys: Optional[Sequence[str]] = None,
        threshold: Optional[float] = None,
        batch_size: Optional[int] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        OPTIMIERTE Batch-Evaluation mit echtem LLM-Batching + paralleler Verarbeitung.
        
        Sendet mehrere Requirements in parallelen LLM-Calls für maximalen Speedup.
        
        Args:
            items: Liste von Dicts mit {id, text}
            context: Zusätzlicher Kontext
            criteria_keys: Zu prüfende Kriterien
            threshold: Verdikt-Schwelle
            batch_size: Anzahl Requirements pro LLM-Call (default: 5)
            ctx: Request-Kontext
        
        Returns:
            Liste von {id, originalText, evaluation, score, verdict}
        """
        if not items:
            return []
        
        # Konfiguration
        bs = batch_size or DEFAULT_BATCH_SIZE
        thr = float(
            threshold
            if isinstance(threshold, (int, float))
            else getattr(_settings, "VERDICT_THRESHOLD", 0.7)
        )
        
        try:
            # Kriterien laden
            all_criteria = self._persistence.load_criteria(ctx=ctx)
            if criteria_keys:
                crit_keys = list(criteria_keys)
                crits = [c for c in all_criteria if str(c.get("key")) in crit_keys]
                if not crits:
                    crits = list(all_criteria)
                    crit_keys = [str(c.get("key")) for c in crits]
            else:
                crits = list(all_criteria)
                crit_keys = [str(c.get("key")) for c in crits]
                if not crit_keys:
                    crit_keys = DEFAULT_CRITERIA_KEYS
            
            # In Batches aufteilen
            batches: List[List[Dict[str, Any]]] = []
            for batch_start in range(0, len(items), bs):
                batch_items = list(items[batch_start:batch_start + bs])
                batches.append([
                    {"id": str(item.get("id", f"item-{batch_start + i}")), "text": str(item.get("text", ""))}
                    for i, item in enumerate(batch_items)
                ])
            
            # Parallele Batch-Verarbeitung mit ThreadPoolExecutor
            all_batch_results: List[List[Dict[str, Any]]] = []
            max_workers = min(len(batches), int(os.environ.get("MAX_PARALLEL", "5")))
            
            def process_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                return self._llm.evaluate_batch(
                    batch,
                    crit_keys,
                    context=dict(context or {}),
                    ctx=ctx,
                )
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_batch, batch) for batch in batches]
                for future in concurrent.futures.as_completed(futures):
                    all_batch_results.append(future.result())
            
            # Flatten und Ergebnisse normalisieren
            all_results: List[Dict[str, Any]] = []
            
            # Alle Batch-Ergebnisse zusammenführen
            flat_results: Dict[str, Dict[str, Any]] = {}
            for batch_results in all_batch_results:
                for result in batch_results:
                    flat_results[result.get("id", "")] = result
            
            # In Original-Reihenfolge zurückgeben
            for i, item in enumerate(items):
                item_id = str(item.get("id", f"item-{i}"))
                item_text = str(item.get("text", ""))
                
                # Finde passendes Ergebnis
                result = flat_results.get(item_id, {"id": item_id, "details": []})
                details = result.get("details", [])
                
                # Score berechnen
                score = float(_utils.weighted_score(details, list(crits)))
                verdict = _utils.compute_verdict(score, thr)
                
                all_results.append({
                    "id": item_id,
                    "originalText": item_text,
                    "evaluation": details,
                    "score": score,
                    "verdict": verdict,
                })
            
            return all_results
            
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                "evaluation_batch_optimized_failed",
                "evaluate_batch_optimized failed",
                details={"request_id": safe_request_id(ctx), "error": str(e)}
            )