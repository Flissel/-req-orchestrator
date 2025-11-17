# -*- coding: utf-8 -*-
"""
CorrectionsService (framework-frei)

Zweck
- Kapselt Korrektur-bezogene Operationen (Apply mit Suggestions, Entscheidungen).
- Nutzt bestehende Implementierungen in backend_app.llm bzw. backend_app.batch/DB,
  bleibt aber unabhängig von FastAPI/Flask und bietet eine klare Service-API (DI-fähig).

Hinweis
- apply_with_suggestions nutzt backend_app.llm.llm_apply_with_suggestions
- Weitere Funktionen (z. B. set_decision) können schrittweise ergänzt werden.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .ports import RequestContext, ServiceError, safe_request_id

# Legacy/Shared LLM-Implementierung
from backend.core.llm import llm_apply_with_suggestions as _llm_apply_with_suggestions


class CorrectionsService:
    """
    CorrectionsService – API
    - apply_with_suggestions(original_text, selected_suggestions, ...)
    - (optional) set_decision(...), set_decision_batch(...)
    """

    def apply_with_suggestions(
        self,
        original_text: str,
        selected_suggestions: Sequence[Mapping[str, Any]],
        *,
        ctx: Optional[RequestContext] = None,
    ) -> Dict[str, Any]:
        """
        Führt einen Korrektur-Applikationslauf aus.
        Erwartet:
        - original_text: Ursprünglicher Requirement-Text
        - selected_suggestions: Liste von Suggestion-Objekten (mindestens 'correction' o. ä.)

        Rückgabe (Beispiel):
        {
          "evaluationId": "...",
          "items": [
            { "rewrittenId": 1, "redefinedRequirement": "..." }
          ]
        }
        """
        if not isinstance(original_text, str) or not original_text.strip():
            raise ServiceError("invalid_request", "originalText fehlt oder leer", details={"request_id": safe_request_id(ctx)})

        try:
            # backend_app.llm.llm_apply_with_suggestions erwartet (original_text, suggestions=list)
            res = _llm_apply_with_suggestions(original_text, list(selected_suggestions or []))
            if not isinstance(res, dict):
                raise ServiceError(
                    "corrections_apply_failed",
                    "Unexpected response type from llm_apply_with_suggestions",
                    details={"request_id": safe_request_id(ctx), "type": str(type(res))},
                )
            return res
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                "corrections_apply_failed",
                "Failed to apply corrections with suggestions",
                details={"request_id": safe_request_id(ctx), "error": str(e)},
            )