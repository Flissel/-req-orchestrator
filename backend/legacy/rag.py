# -*- coding: utf-8 -*-
"""
Pydantic-Schema: StructuredRequirement

Zweck:
- Einheitliches Datenmodell für evaluierte/umgeschriebene Anforderungen
- Kompatibel zu bestehenden API-Responses:
  * validate_batch / validate_batch_stream:
      - "correctedText" (alias) wird in rewrittenText abgebildet
      - "redefinedRequirement" (alias) wird in rewrittenText abgebildet
  * evaluation[]-Einträge: {"criterion", "isValid", "reason"}
  * suggestions[]: unterstützt sowohl einfache Vorschläge {"text","priority"}
    als auch flexible Atom-Strukturen aus llm_suggest (extra Felder erlaubt)

Felder:
- id?: str|int – optionale ID (z. B. "REQ_1")
- originalText: str – Ausgangstext
- rewrittenText?: str – umgeschriebene Variante (Aliases: correctedText, redefinedRequirement)
- evaluation: List[EvaluationItem] – pro Kriterium Bewertung/Begründung
- suggestions: List[SuggestionItem] – Text/Prio oder flexible Atom-Felder
- metadata: dict – beliebige Zusatzinformationen (Quelle, Scores, etc.)
- score?: float – aggregierter Score (optional)
- verdict?: str – "pass"|"fail" (optional)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, root_validator


class EvaluationItem(BaseModel):
    """Einzelnes Evaluationsergebnis zu einem Kriterium."""
    criterion: str = Field(..., description="Kriteriums-Schlüssel, z. B. clarity|testability|measurability")
    isValid: bool = Field(..., description="true wenn bestanden")
    reason: str = Field("", description="Begründung/Fallback-Text (leer bei bestanden)")


class SuggestionItem(BaseModel):
    """
    Vorschlags-/Atom-Eintrag.

    - Für einfache Vorschläge: text/priority
    - Für LLM-Atoms: flexible Zusatzfelder erlaubt (extra='allow')
    """
    text: Optional[str] = Field(None, description="Freitext für klassischen Vorschlag")
    priority: Optional[str] = Field(
        None,
        description="Priorität, typische Werte: high|medium|low|atom"
    )

    class Config:
        extra = "allow"  # Erlaube zusätzliche Atom-Felder (z. B. type, correction, metrics, etc.)


class StructuredRequirement(BaseModel):
    """
    Einheitliches Modell über Endpunkte hinweg.

    Aliases:
    - correctedText (validate_*): → rewrittenText
    - redefinedRequirement (apply/suggest/stream): → rewrittenText
    """
    id: Optional[Union[str, int]] = Field(None, description="Optionale ID (z. B. 'REQ_1')")
    originalText: str = Field(..., description="Originaler Anforderungstext")
    # rewrittenText bevorzugt, aber akzeptiert Inputs mit 'correctedText' oder 'redefinedRequirement'
    rewrittenText: Optional[str] = Field(None, description="Umschriebene Anforderung, falls vorhanden")
    evaluation: List[EvaluationItem] = Field(default_factory=list, description="Bewertungen je Kriterium")
    suggestions: List[SuggestionItem] = Field(default_factory=list, description="Vorschläge/Atoms")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Zusatzinfos/Quelle/Debug")
    score: Optional[float] = Field(None, description="Aggregierter Score (optional)")
    verdict: Optional[str] = Field(None, description="pass|fail (optional)")

    @root_validator(pre=True)
    def _accept_aliases(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Akzeptiere alternative Felder für rewrittenText:
        - correctedText (validate_*)
        - redefinedRequirement (apply/suggest/stream)
        """
        if "rewrittenText" not in values or values.get("rewrittenText") in (None, ""):
            if "correctedText" in values and values.get("correctedText"):
                values["rewrittenText"] = values.get("correctedText")
            elif "redefinedRequirement" in values and values.get("redefinedRequirement"):
                values["rewrittenText"] = values.get("redefinedRequirement")
        return values

    def to_dict(self) -> Dict[str, Any]:
        """Serialisierung ohne Nones, behält Feldnamen bei."""
        return self.dict(exclude_none=True)

    @staticmethod
    def from_validate_item(item: Dict[str, Any]) -> "StructuredRequirement":
        """
        Helper: Mappt ein Objekt aus validate_batch/stream zu StructuredRequirement.

        Erwartete Struktur (Beispiele):
        {
          "id": 1,
          "originalText": "...",
          "correctedText": "...",
          "status": "accepted"|"rejected",
          "evaluation": [{"criterion": "...", "isValid": true, "reason": ""}, ...],
          "score": 0.83,
          "verdict": "pass",
          "suggestions": [ {"text": "...", "priority": "high"}, ... ]  # optional
        }
        """
        ev_raw = item.get("evaluation") or []
        suggestions_raw = item.get("suggestions") or []

        evaluation = []
        for e in ev_raw:
            try:
                evaluation.append(EvaluationItem(**e))
            except Exception:
                # Fallback: weiche Validierung
                evaluation.append(
                    EvaluationItem(
                        criterion=str(e.get("criterion", "")),
                        isValid=bool(e.get("isValid", False)),
                        reason=str(e.get("reason", "")),
                    )
                )

        suggestions = []
        for s in suggestions_raw:
            # Erlaube flexible Struktur (extra=allow)
            try:
                suggestions.append(SuggestionItem(**s))
            except Exception:
                # Fallback: Mappe best effort
                suggestions.append(SuggestionItem(text=str(s), priority=None))

        meta: Dict[str, Any] = {}
        # Sammle unbekannte Felder best-effort in metadata
        known = {"id", "originalText", "correctedText", "redefinedRequirement", "evaluation", "suggestions", "score", "verdict"}
        for k, v in item.items():
            if k not in known:
                meta[k] = v

        return StructuredRequirement(
            id=item.get("id"),
            originalText=item.get("originalText") or "",
            rewrittenText=item.get("correctedText") or item.get("redefinedRequirement"),
            evaluation=evaluation,
            suggestions=suggestions,
            metadata=meta,
            score=item.get("score"),
            verdict=item.get("verdict"),
        )

    @staticmethod
    def from_agent_answer_item(item: Dict[str, Any]) -> "StructuredRequirement":
        """
        Optionaler Helper: Mappt ein Agent-/Stream-Item auf das Modell (best-effort).
        Erwartete Felder (variieren je Endpoint):
        {
          "reqId": "REQ_1",
          "originalText": "...",
          "redefinedRequirement": "...",
          "evaluation": [...],            # optional
          "suggestions": [...],           # optional (Atoms)
          "score": 0.71,                  # optional
          "verdict": "pass"|"fail"        # optional
        }
        """
        ev_raw = item.get("evaluation") or []
        suggestions_raw = item.get("suggestions") or []

        evaluation = []
        for e in ev_raw:
            try:
                evaluation.append(EvaluationItem(**e))
            except Exception:
                evaluation.append(
                    EvaluationItem(
                        criterion=str(e.get("criterion", "")),
                        isValid=bool(e.get("isValid", False)),
                        reason=str(e.get("reason", "")),
                    )
                )

        suggestions = []
        for s in suggestions_raw:
            try:
                suggestions.append(SuggestionItem(**s))
            except Exception:
                suggestions.append(SuggestionItem(text=str(s), priority=None))

        meta: Dict[str, Any] = {}
        known = {"reqId", "id", "originalText", "correctedText", "redefinedRequirement", "evaluation", "suggestions", "score", "verdict"}
        for k, v in item.items():
            if k not in known:
                meta[k] = v

        _id = item.get("id") or item.get("reqId")
        return StructuredRequirement(
            id=_id,
            originalText=item.get("originalText") or "",
            rewrittenText=item.get("redefinedRequirement") or item.get("correctedText"),
            evaluation=evaluation,
            suggestions=suggestions,
            metadata=meta,
            score=item.get("score"),
            verdict=item.get("verdict"),
        )


class StructuredRequirementList(BaseModel):
    """Hülle für Listenrückgaben in zukünftigen Endpunkten."""
    items: List[StructuredRequirement] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.dict(exclude_none=True)


__all__ = [
    "EvaluationItem",
    "SuggestionItem",
    "StructuredRequirement",
    "StructuredRequirementList",
]