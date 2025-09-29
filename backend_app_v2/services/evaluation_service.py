# -*- coding: utf-8 -*-
"""
EvaluationService (framework-frei, DI-ready)

Zweck
- Kapselt Evaluations-Logik (einzeln/Batch) ohne direkte Web-/Framework-Kopplung.
- Nutzt Ports/Adapter (Persistence/Embeddings), LLM-Aufrufe werden in einer
  nachgelagerten Iteration über einen dedizierten LLM-Port abstrahiert.

Aktueller Stand (Skeleton)
- Schnittstellen und Konstruktor stehen fest.
- Methoden sind mit TODOs versehen und verweisen auf bestehende Implementierungen
  (backend_app.llm / backend_app.batch) gemäß MIGRATION_DEP_MAP.md.

Nächste Schritte
- LLMPort in [ports.py](backend_app_v2/services/ports.py:1) ergänzen (evaluate/suggest/rewrite/apply).
- Konkrete Implementierung der Methoden unten auf LLMPort/PersistencePort aufsetzen.
- Unit-Tests (Happy/Error/Edge) gemäß DoD (Coverage ≥ 80%).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .ports import EmbeddingsPort, PersistencePort, RequestContext, ServiceError, LLMPort, safe_request_id
from .adapters import EmbeddingsAdapter, PersistenceAdapter
from .adapters import LLMAdapter
from backend_app import utils as _utils
from backend_app import settings as _settings


class EvaluationService:
    """
    EvaluationService

    Abhängigkeiten:
    - persistence: PersistencePort (DB-Zugriffe wie load_criteria, latest eval/rewrite)
    - embeddings: EmbeddingsPort (optional für Einbettungs-basierte Metriken in späteren Erweiterungen)

    Hinweise:
    - LLM-Aufrufe werden in einer nachgelagerten Iteration über einen LLMPort abstrahiert.
      Bis dahin referenzieren TODOs die bestehenden Module:
        - Einzel-Evaluation: backend_app.llm.llm_evaluate
        - Batch: backend_app.batch.process_evaluations
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
                    crit_keys = ["clarity", "testability", "measurability"]
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
    # Batch-Evaluation
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
        Implementierung via LLMPort pro Item (sequenziell; Parallelisierung kann später ergänzt werden).
        Rückgabe:
        [
          { "id": "item-1", "originalText": "...", "evaluation": [...], "score": float, "verdict": "pass|fail" },
          ...
        ]
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