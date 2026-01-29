# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------- Suggest/Validate (Basic Types) ----------

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
    isValid: bool = Field(default=False, description="Alias for passed (frontend compatibility)")
    passed: bool = Field(default=False, description="Whether the criterion passed")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Criterion score (0.0-1.0)")
    reason: str = Field(default="", description="Feedback or reason")
    feedback: str = Field(default="", description="Alias for reason")


# ---------- Manifest System (Requirement Lifecycle Tracking) ----------
# NOTE: These must be defined BEFORE ValidateItemResult which references RequirementManifest

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
    validation_score: Optional[float] = Field(default=None, description="Latest validation score (0.0-1.0)")
    validation_verdict: Optional[str] = Field(default=None, description="Latest validation verdict (pass/fail)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata (JSON)")

    # Relationships (populated via joins)
    processing_stages: List[ProcessingStage] = Field(default_factory=list, description="Full timeline of processing stages")
    evidence_refs: List[EvidenceReference] = Field(default_factory=list, description="Source evidence references")
    split_children: List[str] = Field(default_factory=list, description="Child requirement IDs (if split)")
    evaluation: List[EvaluationDetail] = Field(default_factory=list, description="Evaluation criteria results")


# ---------- ValidateItemResult (uses RequirementManifest) ----------

class ValidateItemResult(BaseModel):
    id: int
    originalText: str
    correctedText: str
    status: str
    evaluation: List[EvaluationDetail] = Field(default_factory=list)
    score: float = 0.0
    verdict: str
    suggestions: Optional[List[SuggestAtom]] = None
    manifest: Optional[RequirementManifest] = Field(default=None, description="Linked requirement manifest (if tracking enabled)")


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
    criterion: str = Field(..., description="Kriteriumsschluessel, z. B. clarity|testability|measurability")
    score: float = Field(0.0, ge=0.0, le=1.0, description="Score 0..1")
    passed: bool = Field(..., description="true, wenn Schwelle fuer dieses Kriterium erreicht")
    feedback: str = Field("", description="Optionale Begruendung/Rueckmeldung des LLM/Heuristik")


class EvaluateSingleRequest(BaseModel):
    text: str = Field(..., description="Zu bewertender Requirement-Text")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Kontextobjekt (optional)")
    criteria_keys: Optional[List[str]] = Field(default=None, description="Teilmenge der Kriterien; Default: alle aktiven")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Schwellwert fuer Gesamtscore (verdict)")


class EvaluateSingleResponse(BaseModel):
    requirementText: str = Field(..., description="Originaltext der Anforderung")
    evaluation: List[EvalDetailV2] = Field(default_factory=list, description="Bewertungsdetails je Kriterium")
    score: float = Field(..., ge=0.0, le=1.0, description="Aggregierter Score 0..1")
    verdict: str = Field(..., description="pass|fail")


class EvaluateBatchRequestV2(BaseModel):
    items: List[str] = Field(..., description="Liste von Requirement-Texten")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Kontextobjekt (optional, global)")
    criteria_keys: Optional[List[str]] = Field(default=None, description="Teilmenge der Kriterien; Default: alle aktiven")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Schwellwert fuer Gesamtscore (verdict)")


class EvaluateBatchItem(BaseModel):
    id: str = Field(..., description="Item-Id (z. B. 'item-1')")
    originalText: str = Field(..., description="Originaltext der Anforderung")
    evaluation: List[EvalDetailV2] = Field(default_factory=list, description="Bewertungsdetails je Kriterium")
    score: float = Field(..., ge=0.0, le=1.0, description="Aggregierter Score 0..1")
    verdict: str = Field(..., description="pass|fail")


# ---------- Manifest Responses ----------

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


# ---------- Project Metadata (TechStack Generated Projects) ----------

class ValidationSummary(BaseModel):
    """Validation statistics at time of project creation"""
    total: int = Field(default=0, description="Total number of requirements")
    passed: int = Field(default=0, description="Number of requirements that passed validation")
    failed: int = Field(default=0, description="Number of requirements that failed validation")
    avg_score: float = Field(default=0.0, description="Average validation score")
    criteria_breakdown: Optional[Dict[str, float]] = Field(default=None, description="Per-criterion average scores")


class ProjectMetadata(BaseModel):
    """Metadata for a TechStack-generated project"""
    project_id: str = Field(..., description="Unique project identifier")
    project_name: str = Field(..., description="Human-readable project name")
    project_path: str = Field(..., description="Filesystem path to generated project")
    template_id: str = Field(..., description="Template ID used (e.g., '02-api-service')")
    template_name: Optional[str] = Field(default=None, description="Template display name")
    template_category: Optional[str] = Field(default=None, description="Template category (web, backend, mobile, etc.)")
    tech_stack: List[str] = Field(default_factory=list, description="Technologies used in this project")
    requirements_count: int = Field(default=0, description="Number of requirements imported")
    source_file: Optional[str] = Field(default=None, description="Original requirements source file")
    validation_summary: Optional[ValidationSummary] = Field(default=None, description="Validation stats at project creation")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional project metadata")

    # Optional: linked requirements (populated via joins)
    linked_requirements: List[str] = Field(default_factory=list, description="Requirement IDs linked to this project")


class ProjectListResponse(BaseModel):
    """Response for listing projects"""
    projects: List[ProjectMetadata] = Field(default_factory=list, description="List of projects")
    total: int = Field(default=0, description="Total number of projects")


class CreateProjectRequest(BaseModel):
    """Request to create a new project from template"""
    template_id: str = Field(..., description="Template ID to use")
    project_name: str = Field(..., description="Project name")
    requirements: Optional[List[Dict[str, Any]]] = Field(default=None, description="Requirements to import (raw objects)")
    requirement_ids: Optional[List[str]] = Field(default=None, description="Requirement IDs to link from database")
    output_path: Optional[str] = Field(default=None, description="Custom output path (optional)")


class CreateProjectResponse(BaseModel):
    """Response after creating a project"""
    success: bool = Field(..., description="Whether project creation succeeded")
    project_id: str = Field(..., description="Unique project ID")
    project_name: str = Field(..., description="Project name")
    project_path: str = Field(..., description="Filesystem path to project")
    files_created: int = Field(default=0, description="Number of files created")
    requirements_linked: int = Field(default=0, description="Number of requirements linked")
    template_id: str = Field(..., description="Template used")
    message: Optional[str] = Field(default=None, description="Status message")


# ---------- All-in-One Validation (Unified Pipeline) ----------

class AllInOneValidationRequest(BaseModel):
    """Request for unified all-in-one validation workflow"""
    requirements: List[Dict[str, Any]] = Field(..., description="Requirements to validate [{id, text}, ...]")
    mode: str = Field(default="quick", description="Validation mode: 'quick' (auto-fix) or 'guided' (with questions)")
    session_id: Optional[str] = Field(default=None, description="Session ID for SSE correlation")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Quality threshold (fixed at 0.7)")
    max_iterations: int = Field(default=3, ge=1, le=10, description="Max improvement iterations (fixed at 3)")


class AllInOneValidationResult(BaseModel):
    """Result from all-in-one validation"""
    success: bool = Field(..., description="Whether validation completed successfully")
    mode: str = Field(..., description="Mode used: quick or guided")
    session_id: Optional[str] = Field(default=None, description="Session ID for tracking")
    stage: str = Field(default="complete", description="Current pipeline stage")

    # Statistics
    total_processed: int = Field(default=0, description="Total requirements processed")
    passed_count: int = Field(default=0, description="Requirements that passed validation")
    failed_count: int = Field(default=0, description="Requirements that failed validation")
    improved_count: int = Field(default=0, description="Requirements improved during processing")
    average_score: float = Field(default=0.0, description="Average validation score")
    total_time_ms: int = Field(default=0, description="Total processing time in milliseconds")

    # Results
    requirements: List[Dict[str, Any]] = Field(default_factory=list, description="Processed requirements with scores")

    # Guided mode only
    pending_questions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Questions awaiting user input (guided mode)")

    error: Optional[str] = Field(default=None, description="Error message if failed")


# ---------- Project Merge & Coding Engine Integration ----------

class MergeProjectsRequest(BaseModel):
    """Request for merging multiple projects"""
    project_ids: List[str] = Field(..., description="List of project IDs to merge")
    include_failed: bool = Field(default=False, description="Include non-validated requirements")


# NOTE: ValidationSummary is defined above at line ~228 - do not duplicate


class MergedProjectPayload(BaseModel):
    """Merged project payload for Coding Engine"""
    projects: List[str] = Field(..., description="List of merged project IDs")
    requirements: List[Dict[str, Any]] = Field(default_factory=list, description="All merged requirements")
    tech_stack: List[str] = Field(default_factory=list, description="Combined tech stack")
    validation_summary: ValidationSummary = Field(default_factory=ValidationSummary, description="Validation statistics")
    merged_at: str = Field(..., description="Merge timestamp (ISO 8601)")


class SendToCodingEngineRequest(BaseModel):
    """Request for sending merged projects to Coding Engine"""
    project_ids: List[str] = Field(..., description="List of project IDs to merge and send")
    coding_engine_url: Optional[str] = Field(default=None, description="Coding Engine URL (uses env default if not set)")
    include_failed: bool = Field(default=False, description="Include non-validated requirements")


class SendToCodingEngineResponse(BaseModel):
    """Response from Coding Engine send operation"""
    success: bool = Field(..., description="Whether send was successful")
    projects_sent: int = Field(default=0, description="Number of projects sent")
    requirements_sent: int = Field(default=0, description="Number of requirements sent")
    engine_response: Optional[Dict[str, Any]] = Field(default=None, description="Response from Coding Engine")
    error: Optional[str] = Field(default=None, description="Error message if failed")
