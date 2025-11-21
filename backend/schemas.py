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
    manifest: Optional["RequirementManifest"] = Field(default=None, description="Linked requirement manifest (if tracking enabled)")


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


# ---------- Manifest System (Requirement Lifecycle Tracking) ----------

class EvidenceReference(BaseModel):
    """Evidence reference tracking for requirement source provenance"""
    source_file: Optional[str] = Field(default=None, description="Original filename of source document")
    sha1: Optional[str] = Field(default=None, description="SHA1 hash of source document (from ChunkMiner)")
    chunk_index: Optional[int] = Field(default=None, description="Position in chunked document (0-based)")
    is_neighbor: bool = Field(default=False, description="Flag indicating ±1 chunk context (neighbor evidence)")
    evidence_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional evidence metadata (JSON)")


class ProcessingStage(BaseModel):
    """Processing stage timeline entry for requirement lifecycle tracking"""
    id: Optional[int] = Field(default=None, description="Auto-incremented stage ID")
    requirement_id: str = Field(..., description="Requirement ID (FK to requirement_manifest)")
    stage_name: str = Field(..., description="Stage name: input|mining|evaluation|atomicity|suggestion|rewrite|validation|completed|failed")
    status: str = Field(..., description="Stage status: pending|in_progress|completed|failed")
    started_at: str = Field(..., description="Stage start timestamp (ISO 8601)")
    completed_at: Optional[str] = Field(default=None, description="Stage completion timestamp (ISO 8601)")
    evaluation_id: Optional[str] = Field(default=None, description="Link to evaluation table (if applicable)")
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Overall score for this stage")
    verdict: Optional[str] = Field(default=None, description="Verdict: pass|fail")
    atomic_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Atomic criterion score (atomicity stage)")
    was_split: bool = Field(default=False, description="Flag indicating requirement was split in this stage")
    model_used: Optional[str] = Field(default=None, description="LLM model used (e.g., gpt-4o-mini)")
    latency_ms: Optional[int] = Field(default=None, ge=0, description="Processing time in milliseconds")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage: {prompt_tokens, completion_tokens, total_tokens}")
    error_message: Optional[str] = Field(default=None, description="Error details if status=failed")
    stage_metadata: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific additional data (JSON)")


class SplitRelationship(BaseModel):
    """Parent-child split relationship (when AtomicityAgent splits requirements)"""
    parent_id: str = Field(..., description="Parent requirement ID")
    child_id: str = Field(..., description="Child requirement ID")
    split_rationale: str = Field(..., description="Explanation for split (from AtomicityAgent)")
    split_timestamp: str = Field(..., description="Split timestamp (ISO 8601)")
    split_model: Optional[str] = Field(default=None, description="Model used for splitting (e.g., gpt-4o-mini)")


class RequirementManifest(BaseModel):
    """Main manifest tracking requirement from source to final state"""
    requirement_id: str = Field(..., description="Stable requirement ID: REQ-{sha1[:6]}-{chunk:03d}")
    requirement_checksum: str = Field(..., description="SHA256 hash of current requirement text")
    source_type: str = Field(..., description="Source type: upload|manual|chunk_miner|api")
    source_file: Optional[str] = Field(default=None, description="Original filename (if applicable)")
    source_file_sha1: Optional[str] = Field(default=None, description="Document SHA1 hash (from ChunkMiner)")
    chunk_index: Optional[int] = Field(default=None, description="Position in chunked document (0-based)")
    original_text: str = Field(..., description="Initial raw requirement text (immutable)")
    current_text: str = Field(..., description="Latest version after processing (updated after rewrites)")
    current_stage: Optional[str] = Field(default=None, description="Latest processing stage name")
    parent_id: Optional[str] = Field(default=None, description="Parent requirement ID (for split requirements)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (JSON)")

    # Relationships (populated via joins)
    processing_stages: List[ProcessingStage] = Field(default_factory=list, description="Full timeline of processing stages")
    evidence_refs: List[EvidenceReference] = Field(default_factory=list, description="Source evidence references")
    split_children: List[str] = Field(default_factory=list, description="Child requirement IDs (if split)")


class ManifestTimelineResponse(BaseModel):
    """Response for GET /api/v1/manifest/{requirement_id}/timeline"""
    requirement_id: str = Field(..., description="Requirement ID")
    timeline: List[ProcessingStage] = Field(default_factory=list, description="Chronological processing stages")


class ManifestChildrenResponse(BaseModel):
    """Response for GET /api/v1/manifest/{requirement_id}/children"""
    parent_id: str = Field(..., description="Parent requirement ID")
    children: List[RequirementManifest] = Field(default_factory=list, description="Child manifests (if split)")
    split_relationships: List[SplitRelationship] = Field(default_factory=list, description="Split relationship metadata")


# ---------- Fehler/Errors (einheitlich) ----------
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Fehlercode, z. B. invalid_request, internal_error")
    message: str = Field(..., description="Menschlich lesbare Fehlermeldung")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Optionale Detailinformationen (z. B. request_id)")