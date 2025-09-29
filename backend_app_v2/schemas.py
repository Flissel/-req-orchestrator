# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------- Suggest/Validate ----------

class SuggestAtom(BaseModel):
    correction: Optional[str] = Field(default=None, description="Vorgeschlagene neue Fassung oder Teilkorrektur")
    acceptance_criteria: Optional[List[str]] = Field(default=None, description="Gherkin-ähnliche Kriterien")
    metrics: Optional[List[Dict[str, Any]]] = Field(default=None, description="Messkriterien/Schwellen")
    criteria: Optional[Dict[str, Any]] = Field(default=None, description="Heuristische Kriterien-Flags")
    notes: Optional[str] = None
    original_fragment: Optional[str] = None


class ValidateSuggestRequest(BaseModel):
    items: List[str] = Field(description="Liste von Requirement-Texten")


class SuggestionsForReq(BaseModel):
    suggestions: List[SuggestAtom] = Field(default_factory=list)


class ValidateSuggestResponse(BaseModel):
    items: Dict[str, SuggestionsForReq]


class EvaluationDetail(BaseModel):
    criterion: str
    isValid: bool
    reason: str


class ValidateItemResult(BaseModel):
    id: int
    originalText: str
    correctedText: str
    status: str
    evaluation: List[EvaluationDetail] = Field(default_factory=list)
    score: float = 0.0
    verdict: str
    suggestions: Optional[List[SuggestAtom]] = None


class ValidateBatchRequest(BaseModel):
    items: List[str]
    includeSuggestions: Optional[bool] = False


# ---------- Corrections ----------

class CorrectionsApplyRequest(BaseModel):
    originalText: Optional[str] = None
    evaluationId: Optional[str] = None
    selectedSuggestions: List[SuggestAtom]
    mode: Optional[str] = "merge"
    context: Optional[Dict[str, Any]] = None


class CorrectionsApplyItem(BaseModel):
    rewrittenId: Optional[int] = None
    redefinedRequirement: str


class CorrectionsApplyResponse(BaseModel):
    evaluationId: str
    items: List[CorrectionsApplyItem] = Field(default_factory=list)


# ---------- Vector/RAG ----------

class VectorCollectionsResponse(BaseModel):
    items: List[str]


class VectorResetResponse(BaseModel):
    status: str
    reset: Dict[str, Any]
    collections: List[str]
    method: Optional[str] = None


class RagSearchHit(BaseModel):
    id: Optional[str] = None
    score: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
    query: str
    topK: int
    collection: str
    hits: List[RagSearchHit] = Field(default_factory=list)

# ---------- V2 Evaluate (Service-Layer) ----------

class EvalDetailV2(BaseModel):
    criterion: str = Field(..., description="Kriteriumsschlüssel, z. B. clarity|testability|measurability")
    score: float = Field(0.0, ge=0.0, le=1.0, description="Score 0..1")
    passed: bool = Field(..., description="true, wenn Schwelle für dieses Kriterium erreicht")
    feedback: str = Field("", description="Optionale Begründung/Rückmeldung des LLM/Heuristik")


class EvaluateSingleRequest(BaseModel):
    text: str = Field(..., description="Zu bewertender Requirement-Text")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Kontextobjekt (optional)")
    criteria_keys: Optional[List[str]] = Field(default=None, description="Teilmenge der Kriterien; Default: alle aktiven")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Schwellwert für Gesamtscore (verdict)")


class EvaluateSingleResponse(BaseModel):
    requirementText: str = Field(..., description="Originaltext der Anforderung")
    evaluation: List[EvalDetailV2] = Field(default_factory=list, description="Bewertungsdetails je Kriterium")
    score: float = Field(..., ge=0.0, le=1.0, description="Aggregierter Score 0..1")
    verdict: str = Field(..., description="pass|fail")


class EvaluateBatchRequestV2(BaseModel):
    items: List[str] = Field(..., description="Liste von Requirement-Texten")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Kontextobjekt (optional, global)")
    criteria_keys: Optional[List[str]] = Field(default=None, description="Teilmenge der Kriterien; Default: alle aktiven")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Schwellwert für Gesamtscore (verdict)")


class EvaluateBatchItem(BaseModel):
    id: str = Field(..., description="Item-Id (z. B. 'item-1')")
    originalText: str = Field(..., description="Originaltext der Anforderung")
    evaluation: List[EvalDetailV2] = Field(default_factory=list, description="Bewertungsdetails je Kriterium")
    score: float = Field(..., ge=0.0, le=1.0, description="Aggregierter Score 0..1")
    verdict: str = Field(..., description="pass|fail")


# ---------- Fehler/Errors (einheitlich) ----------
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Fehlercode, z. B. invalid_request, internal_error")
    message: str = Field(..., description="Menschlich lesbare Fehlermeldung")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optionale Detailinformationen (z. B. request_id)")