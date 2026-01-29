# -*- coding: utf-8 -*-
"""
FastAPI Router für arch_team Funktionalität.
Ersetzt arch_team/service.py Flask-Service für Single-Port-Architektur.

Enthält:
- Mining Endpoints: /api/mining/upload, /api/mining/report
- KG Endpoints: /api/kg/build, /api/kg/search/*, /api/kg/export, /api/kg/neighbors
- RAG Endpoints: /api/rag/duplicates, /api/rag/search, /api/rag/related, /api/rag/coverage
- Validation Endpoints: /api/validation/run
- Clarification Endpoints: /api/clarification/stream, /api/clarification/answer
- Workflow Endpoints: /api/workflow/stream
- Master Endpoint: /api/arch_team/process
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import shutil
import tempfile
import threading
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

# Configure logger
logger = logging.getLogger(__name__)

# Project directories
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

# ============================================================================
# Pydantic Models
# ============================================================================

class MiningReportRequest(BaseModel):
    items: List[Dict[str, Any]]

class KGBuildRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    data: Optional[List[Dict[str, Any]]] = Field(default=None)
    options: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    
    def get_items(self) -> List[Dict[str, Any]]:
        """Return items from either 'items' or 'data' field."""
        if self.items:
            return self.items
        if self.data:
            return self.data
        return []

class SemanticSearchRequest(BaseModel):
    requirements: List[str]
    similarity_threshold: float = 0.90

class RAGDuplicatesRequest(BaseModel):
    requirements: List[Dict[str, Any]]
    similarity_threshold: float = 0.90
    method: str = "embedding"

class RAGSearchRequest(BaseModel):
    query: str
    requirements: Optional[List[Dict[str, Any]]] = None
    top_k: int = 10
    min_score: float = 0.7
    use_qdrant: bool = True

class RAGRelatedRequest(BaseModel):
    requirement_id: str
    requirements: List[Dict[str, Any]]
    top_k: int = 5
    relationship_types: Optional[List[str]] = None

class RAGCoverageRequest(BaseModel):
    requirements: List[Dict[str, Any]]
    categories: Optional[List[str]] = None

class EvaluateSingleRequest(BaseModel):
    text: str
    criteria_keys: Optional[List[str]] = None
    threshold: Optional[float] = None
    context: Optional[Dict[str, Any]] = None

class EvaluateBatchRequest(BaseModel):
    items: List[str]
    criteria_keys: Optional[List[str]] = None
    threshold: Optional[float] = None
    context: Optional[Dict[str, Any]] = None

class ValidateBatchRequest(BaseModel):
    items: List[str]

class ValidationRunRequest(BaseModel):
    requirements: List[str]
    correlation_id: str
    criteria_keys: Optional[List[str]] = None
    threshold: float = 0.7

class ClarificationAnswerRequest(BaseModel):
    correlation_id: str
    answer: str

class StoreRequirementsRequest(BaseModel):
    requirements: List[Dict[str, Any]]
    version: str = "auto"
    metadata: Optional[Dict[str, Any]] = None

class SearchRequirementsRequest(BaseModel):
    query: str
    version: str
    top_k: int = 10

# ============================================================================
# Global SSE Registries
# ============================================================================

clarification_streams: Dict[str, Queue] = {}
workflow_streams: Dict[str, Queue] = {}

# ============================================================================
# Lazy Imports (to avoid circular imports)
# ============================================================================

def _get_chunk_miner():
    from arch_team.agents.chunk_miner import ChunkMinerAgent
    return ChunkMinerAgent

def _get_kg_agent():
    from arch_team.agents.kg_agent import KGAbstractionAgent
    return KGAbstractionAgent

def _get_qdrant_client():
    from arch_team.memory.qdrant_kg import QdrantKGClient
    return QdrantKGClient()

def _get_evaluation_service():
    from backend.services import EvaluationService, RequestContext
    return EvaluationService, RequestContext

def _get_llm_functions():
    from backend.core.llm import llm_suggest, llm_rewrite
    return llm_suggest, llm_rewrite

def _get_manifest_integration():
    from backend.services.manifest_integration import create_manifests_from_chunkminer
    from backend.core import db as _db
    return create_manifests_from_chunkminer, _db

def _get_requirements_store():
    from arch_team.memory.requirements_store import RequirementsStore
    return RequirementsStore()

# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(tags=["arch_team"])

# ============================================================================
# Helper Functions
# ============================================================================

def _truthy(s: str | None) -> bool:
    if not s:
        return False
    return s.strip().lower() in ("1", "true", "yes", "on")

async def _file_to_record(file: UploadFile) -> Dict[str, Any]:
    """Convert UploadFile to record dict."""
    filename = file.filename or "upload.bin"
    data = await file.read()
    ct = file.content_type or mimetypes.guess_type(filename)[0] or ""
    return {"filename": filename, "data": data, "content_type": ct}

def _persist_kg_async(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """Persist nodes/edges asynchronously to Qdrant."""
    try:
        client = _get_qdrant_client()
        client.ensure_collections()
        client.upsert_nodes(nodes or [])
        client.upsert_edges(edges or [])
    except Exception as e:
        logger.warning(f"[kg] async persist failed: {e}")

# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "service": "arch_team"}

# ============================================================================
# Mining Endpoints
# ============================================================================

@router.post("/api/mining/upload")
async def mining_upload(
    file: List[UploadFile] = File(default=None),
    files: List[UploadFile] = File(default=None),
    model: Optional[str] = Form(default=None),
    neighbor_refs: Optional[str] = Form(default=None),
    chunk_size: Optional[str] = Form(default=None),
    chunk_overlap: Optional[str] = Form(default=None),
):
    """Multipart Upload for requirements mining."""
    try:
        all_files = []
        if file:
            all_files.extend(file)
        if files:
            all_files.extend(files)
        
        if not all_files:
            return JSONResponse({"success": False, "message": "No files uploaded"}, status_code=400)
        
        use_neighbor_refs = _truthy(neighbor_refs)
        
        chunk_options = {}
        if chunk_size:
            try:
                chunk_options['max_tokens'] = int(chunk_size)
            except ValueError:
                pass
        if chunk_overlap:
            try:
                chunk_options['overlap_tokens'] = int(chunk_overlap)
            except ValueError:
                pass
        
        records: List[Dict[str, Any]] = []
        for f in all_files:
            try:
                records.append(await _file_to_record(f))
            except Exception as e:
                logger.warning(f"[mining] read failed for {f.filename}: {e}")
        
        if not records:
            return JSONResponse({"success": False, "message": "Failed to read uploads"}, status_code=400)
        
        ChunkMinerAgent = _get_chunk_miner()
        agent = ChunkMinerAgent(source="web", default_model=os.environ.get("MODEL_NAME"))
        items = agent.mine_files_or_texts_collect(
            records,
            model=model,
            neighbor_refs=use_neighbor_refs,
            chunk_options=chunk_options
        )
        
        manifest_ids = []
        try:
            create_manifests, _db = _get_manifest_integration()
            conn = _db.get_db()
            try:
                manifest_ids = create_manifests(conn, items)
                logger.info(f"[mining] Created {len(manifest_ids)} manifests")
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"[mining] Manifest creation failed: {e}")
        
        return {
            "success": True,
            "count": len(items),
            "items": items,
            "manifest_ids": manifest_ids
        }
    
    except Exception as e:
        logger.error(f"[mining] Error: {e}")
        return JSONResponse({"success": False, "message": f"Mining failed: {e}"}, status_code=500)

@router.post("/api/mining/report")
async def mining_report(request: MiningReportRequest):
    """Generate a compact Markdown report from mined DTOs."""
    try:
        items = request.items
        if not items:
            return JSONResponse({"success": False, "message": "items must be a non-empty list"}, status_code=400)
        
        lines = ["# Requirements Report", ""]
        for it in items:
            rid = it.get("req_id") or it.get("reqId") or it.get("id") or "REQ-XXX"
            title = it.get("title") or it.get("redefinedRequirement") or it.get("final") or ""
            tag = (it.get("tag") or it.get("category") or "").lower()
            cites = it.get("evidence_refs") or it.get("evidenceRefs") or it.get("citations") or []
            sources = []
            if isinstance(cites, list):
                for c in cites:
                    if isinstance(c, dict):
                        src = c.get("sourceFile") or c.get("source") or ""
                        if src:
                            sources.append(src)
            src_str = ", ".join(sorted(set(sources)))
            lines.append(f"- {rid} [{tag}]: {title} (src: {src_str})")
        
        md = "\n".join(lines)
        return {"success": True, "markdown": md, "count": len(items), "items": items}
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"Report generation failed: {e}"}, status_code=500)

# ============================================================================
# KG Endpoints
# ============================================================================

@router.post("/api/kg/build")
async def kg_build(request: KGBuildRequest):
    """Build Knowledge Graph from mined DTOs and persist to Qdrant."""
    try:
        items = request.get_items()
        if not items:
            return JSONResponse({"success": False, "message": "items must be a non-empty list"}, status_code=400)
        
        options = request.options or {}
        
        def _to_bool(v: Any) -> bool:
            if isinstance(v, bool):
                return v
            if v is None:
                return False
            return str(v).strip().lower() in ("1", "true", "yes", "on")
        
        use_llm = _to_bool(options.get("use_llm"))
        llm_fallback = _to_bool(options.get("use_llm_fallback")) if options.get("use_llm_fallback") is not None else True
        persist_async = _to_bool(options.get("persist_async")) if options.get("persist_async") is not None else True
        persist = (options.get("persist") or "qdrant").strip().lower()
        model = request.model or options.get("model")
        
        KGAbstractionAgent = _get_kg_agent()
        agent = KGAbstractionAgent(default_model=os.environ.get("MODEL_NAME"))
        
        if persist_async:
            result = agent.run(items, model=model, persist="none", use_llm=use_llm, llm_fallback=llm_fallback, dedupe=True)
            nodes = result.get("nodes") or []
            edges = result.get("edges") or []
            try:
                threading.Thread(target=_persist_kg_async, args=(nodes, edges), daemon=True).start()
            except Exception as e:
                logger.warning(f"[kg] persist_async spawn failed: {e}")
            stats = result.get("stats") or {}
            stats["persist_async"] = True
            return {
                "success": True,
                "stats": stats,
                "nodes": nodes,
                "edges": edges,
            }
        else:
            result = agent.run(items, model=model, persist=persist, use_llm=use_llm, llm_fallback=llm_fallback, dedupe=True)
            return {
                "success": True,
                "stats": result.get("stats") or {},
                "nodes": result.get("nodes") or [],
                "edges": result.get("edges") or []
            }
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"KG build failed: {e}"}, status_code=500)

@router.get("/api/kg/search/nodes")
async def kg_search_nodes(query: str = Query(...), top_k: int = Query(default=10)):
    """Semantic node search in KG."""
    try:
        if not query.strip():
            return JSONResponse({"success": False, "message": "query required"}, status_code=400)
        
        client = _get_qdrant_client()
        items = client.search_nodes(query, top_k=top_k)
        return {"success": True, "items": items}
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"KG search nodes failed: {e}"}, status_code=500)

@router.get("/api/kg/search/edges")
async def kg_search_edges(query: str = Query(...), top_k: int = Query(default=10)):
    """Semantic edge search in KG."""
    try:
        if not query.strip():
            return JSONResponse({"success": False, "message": "query required"}, status_code=400)
        
        client = _get_qdrant_client()
        items = client.search_edges(query, top_k=top_k)
        return {"success": True, "items": items}
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"KG search edges failed: {e}"}, status_code=500)

@router.get("/api/kg/export")
async def kg_export(limit: int = Query(default=10000)):
    """Export all KG nodes and edges from Qdrant."""
    try:
        client = _get_qdrant_client()
        data = client.export_all(limit=limit)
        return {
            "success": True,
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
            "stats": {
                "node_count": len(data.get("nodes", [])),
                "edge_count": len(data.get("edges", []))
            }
        }
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"KG export failed: {e}"}, status_code=500)

@router.get("/api/kg/neighbors")
async def kg_neighbors(
    node_id: str = Query(...),
    rel: Optional[str] = Query(default=None),
    dir: str = Query(default="both"),
    limit: int = Query(default=200)
):
    """1-hop neighborhood of a node."""
    try:
        if not node_id.strip():
            return JSONResponse({"success": False, "message": "node_id required"}, status_code=400)
        
        direction = dir.strip().lower()
        rels = None
        if rel:
            rels = [r.strip() for r in rel.split(",") if r.strip()]
        
        client = _get_qdrant_client()
        data = client.neighbors(node_id=node_id, rels=rels, direction=direction, limit=limit)
        return {
            "success": True,
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
        }
    
    except Exception as e:
        return JSONResponse({"success": False, "message": f"KG neighbors failed: {e}"}, status_code=500)

@router.post("/api/kg/search/semantic")
async def kg_search_semantic(request: SemanticSearchRequest):
    """Semantic duplicate detection using Qdrant."""
    try:
        requirements = request.requirements
        threshold = request.similarity_threshold
        
        client = _get_qdrant_client()
        duplicates = []
        
        for i, req1 in enumerate(requirements):
            try:
                similar = client.search_nodes(req1, top_k=len(requirements))
                
                for item in similar:
                    score = item.get("score", 0.0)
                    payload = item.get("payload", {})
                    req2_text = payload.get("text", "")
                    try:
                        j = requirements.index(req2_text)
                    except ValueError:
                        continue
                    if i >= j:
                        continue
                    if score >= threshold:
                        duplicates.append({
                            "req1_index": i,
                            "req2_index": j,
                            "req1_text": req1,
                            "req2_text": req2_text,
                            "similarity": score,
                            "is_duplicate": True
                        })
            except Exception as e:
                logger.warning(f"[kg] semantic search failed for req {i}: {e}")
                continue
        return duplicates
    except Exception as e:
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

# ============================================================================
# RAG Endpoints
# ============================================================================

@router.post("/api/rag/duplicates")
async def rag_find_duplicates(request: RAGDuplicatesRequest):
    """Find semantic duplicate requirements using embeddings."""
    try:
        requirements = request.requirements
        threshold = request.similarity_threshold
        
        if not requirements:
            return {
                "success": True,
                "duplicate_groups": [],
                "stats": {"total_requirements": 0, "unique_requirements": 0, "duplicate_groups": 0, "total_duplicates": 0}
            }
        req_texts = [r.get("text", "") for r in requirements]
        client = _get_qdrant_client()
        pairs = []
        
        for i, req1 in enumerate(req_texts):
            if not req1.strip():
                continue
            try:
                similar = client.search_nodes(req1, top_k=len(req_texts))
                for item in similar:
                    score = item.get("score", 0.0)
                    payload = item.get("payload", {})
                    req2_text = payload.get("text", "")

                    try:
                        j = req_texts.index(req2_text)
                    except ValueError:
                        continue

                    if i >= j:
                        continue

                    if score >= threshold:
                        pairs.append((i, j, score))
            except Exception as e:
                logger.warning(f"[RAG] Duplicate search failed for req {i}: {e}")
                continue

        # Union-Find grouping
        parent = list(range(len(requirements)))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i, j, _ in pairs:
            union(i, j)

        groups_dict = {}
        for i in range(len(requirements)):
            root = find(i)
            if root not in groups_dict:
                groups_dict[root] = []
            groups_dict[root].append(i)

        duplicate_groups = []
        group_counter = 1

        for indices in groups_dict.values():
            if len(indices) > 1:
                group_reqs = []
                similarities = []
                for idx in indices:
                    req = requirements[idx]
                    max_sim = 1.0 if len(indices) == 1 else 0.0
                    for i, j, sim in pairs:
                        if (i == idx and j in indices) or (j == idx and i in indices):
                            max_sim = max(max_sim, sim)
                    group_reqs.append({
                        "req_id": req.get("req_id", f"REQ-{idx}"),
                        "text": req.get("text", ""),
                        "similarity": max_sim
                    })
                    similarities.append(max_sim)
                avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
                duplicate_groups.append({
                    "group_id": f"dup_{group_counter}",
                    "requirements": group_reqs,
                    "avg_similarity": avg_sim
                })
                group_counter += 1
        total_duplicates = sum(len(g["requirements"]) - 1 for g in duplicate_groups)
        unique_requirements = len(requirements) - total_duplicates
        return {
            "success": True,
            "duplicate_groups": duplicate_groups,
            "stats": {
                "total_requirements": len(requirements),
                "unique_requirements": unique_requirements,
                "duplicate_groups": len(duplicate_groups),
                "total_duplicates": total_duplicates
            }
        }
    except Exception as e:
        logger.error(f"[RAG] Duplicate detection failed: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "duplicate_groups": [],
            "stats": {"total_requirements": 0}
        }, status_code=500)

@router.post("/api/rag/search")
async def rag_semantic_search(request: RAGSearchRequest):
    """Semantic search for requirements similar to query."""
    try:
        query = request.query.strip()
        requirements = request.requirements or []
        top_k = request.top_k
        min_score = request.min_score
        
        if not query:
            return JSONResponse({"results": []}, status_code=400)
        client = _get_qdrant_client()
        results = []
        for req in requirements:
            req_text = req.get("text", "")
            if not req_text.strip():
                continue
            try:
                similar = client.search_nodes(req_text, top_k=1)
                if similar:
                    score = similar[0].get("score", 0.0)
                    if score >= min_score:
                        results.append({
                            "req_id": req.get("req_id", ""),
                            "text": req_text,
                            "score": score,
                            "source": req.get("source", ""),
                            "metadata": req.get("metadata", {})
                        })
            except Exception as e:
                logger.warning(f"[RAG] Search failed for requirement: {e}")
                continue
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"results": results[:top_k]}
    except Exception as e:
        logger.error(f"[RAG] Semantic search failed: {e}")
        return JSONResponse({"error": str(e), "results": []}, status_code=500)

@router.post("/api/rag/related")
async def rag_get_related(request: RAGRelatedRequest):
    """Find requirements related to a specific requirement."""
    try:
        requirement_id = request.requirement_id.strip()
        requirements = request.requirements
        top_k = request.top_k
        relationship_types = request.relationship_types or ["depends", "conflicts", "similar", "implements"]
        if not requirement_id or not requirements:
            return JSONResponse({"related": []}, status_code=400)
        source_req = None
        for req in requirements:
            if req.get("req_id") == requirement_id:
                source_req = req
                break
        if not source_req:
            return JSONResponse({"related": []}, status_code=404)
        source_text = source_req.get("text", "")
        client = _get_qdrant_client()
        related = []
        try:
            similar = client.search_nodes(source_text, top_k=top_k * 2)
            for item in similar:
                payload = item.get("payload", {})
                req_id = payload.get("node_id", "")
                if req_id == requirement_id:
                    continue
                score = item.get("score", 0.0)
                req_text = payload.get("text", payload.get("name", ""))
                relationship_type = "similar"
                explanation = f"Semantically similar (score: {score:.2f})"
                if score >= 0.95:
                    relationship_type = "similar"
                    explanation = f"Very similar requirement (score: {score:.2f})"
                elif "depend" in source_text.lower() or "require" in source_text.lower():
                    relationship_type = "depends"
                    explanation = f"Potential dependency relationship (score: {score:.2f})"
                elif "not" in source_text.lower() or "conflict" in source_text.lower():
                    relationship_type = "conflicts"
                    explanation = f"Potential conflict (score: {score:.2f})"
                if relationship_type in relationship_types:
                    related.append({
                        "req_id": req_id,
                        "text": req_text,
                        "relationship_type": relationship_type,
                        "score": score,
                        "explanation": explanation
                    })
                if len(related) >= top_k:
                    break
        except Exception as e:
            logger.error(f"[RAG] Related requirements search failed: {e}")
        return {"related": related}
    except Exception as e:
        logger.error(f"[RAG] Get related failed: {e}")
        return JSONResponse({"error": str(e), "related": []}, status_code=500)

@router.post("/api/rag/coverage")
async def rag_analyze_coverage(request: RAGCoverageRequest):
    """Analyze requirement coverage across categories."""
    try:
        requirements = request.requirements
        categories = request.categories or ["functional", "non-functional", "security", "performance", "usability"]
        if not requirements:
            return JSONResponse({
                "success": False,
                "error": "No requirements provided",
                "coverage": {},
                "gaps": [],
                "stats": {"total_requirements": 0}
            }, status_code=400)
        coverage_data = {cat: {"count": 0, "percentage": 0.0, "subcategories": {}} for cat in categories}
        uncategorized = []
        category_keywords = {
            "functional": ["must", "shall", "should", "function", "feature", "capability"],
            "non-functional": ["performance", "scalability", "reliability", "maintainability"],
            "security": ["security", "auth", "encrypt", "access", "permission", "secure"],
            "performance": ["performance", "speed", "latency", "response time", "throughput"],
            "usability": ["usability", "user", "interface", "experience", "ui", "ux"]
        }
        for req in requirements:
            text = req.get("text", "").lower()
            categorized = False
            for cat in categories:
                if cat in category_keywords:
                    keywords = category_keywords[cat]
                    if any(kw in text for kw in keywords):
                        coverage_data[cat]["count"] += 1
                        categorized = True
                        break
            if not categorized:
                uncategorized.append(req.get("req_id", ""))
        total = len(requirements)
        for cat in categories:
            count = coverage_data[cat]["count"]
            coverage_data[cat]["percentage"] = (count / total * 100) if total > 0 else 0.0
        gaps = []
        for cat in categories:
            percentage = coverage_data[cat]["percentage"]
            if percentage < 10:
                gaps.append({
                    "category": cat,
                    "severity": "critical",
                    "description": f"Only {percentage:.1f}% coverage in {cat} requirements",
                    "recommendation": f"Add more {cat} requirements to ensure comprehensive coverage"
                })
            elif percentage < 20:
                gaps.append({
                    "category": cat,
                    "severity": "medium",
                    "description": f"Low coverage ({percentage:.1f}%) in {cat} requirements",
                    "recommendation": f"Consider expanding {cat} requirements"
                })
        return {
            "success": True,
            "coverage": coverage_data,
            "gaps": gaps,
            "stats": {
                "total_requirements": total,
                "categorized": total - len(uncategorized),
                "uncategorized": len(uncategorized)
            }
        }
    except Exception as e:
        logger.error(f"[RAG] Coverage analysis failed: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "coverage": {},
            "gaps": [],
            "stats": {"total_requirements": 0}
        }, status_code=500)

# ============================================================================
# Evaluation Endpoints (V2)
# ============================================================================

@router.post("/api/v2/evaluate/single")
async def evaluate_single(request: EvaluateSingleRequest, req: Request):
    """Single requirement evaluation via EvaluationService."""
    try:
        text = request.text.strip()
        if not text:
            return JSONResponse({"error": "invalid_request", "message": "text is required"}, status_code=400)
        EvaluationService, RequestContext = _get_evaluation_service()
        ctx = RequestContext(request_id=req.headers.get("X-Request-Id"))
        svc = EvaluationService()
        result = svc.evaluate_single(text, context=request.context, criteria_keys=request.criteria_keys, threshold=request.threshold, ctx=ctx)
        return result
    except Exception as e:
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

@router.post("/api/v2/evaluate/batch")
async def evaluate_batch(request: EvaluateBatchRequest, req: Request):
    """Batch evaluation via EvaluationService."""
    try:
        items = request.items
        EvaluationService, RequestContext = _get_evaluation_service()
        ctx = RequestContext(request_id=req.headers.get("X-Request-Id"))
        svc = EvaluationService()
        result = svc.evaluate_batch(items, context=request.context, criteria_keys=request.criteria_keys, threshold=request.threshold, ctx=ctx)
        return result
    except Exception as e:
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

# ============================================================================
# Validation Endpoints (V1)
# ============================================================================

@router.post("/api/v1/validate/batch")
async def validate_batch_rewrite(request: ValidateBatchRequest, req: Request):
    """Validate and rewrite requirements."""
    try:
        items = request.items
        EvaluationService, RequestContext = _get_evaluation_service()
        llm_suggest, llm_rewrite = _get_llm_functions()
        ctx = RequestContext(request_id=req.headers.get("X-Request-Id"))
        svc = EvaluationService()
        eval_results = svc.evaluate_batch(items, ctx=ctx)
        results = []
        for idx, (original, eval_result) in enumerate(zip(items, eval_results), 1):
            try:
                rewritten = llm_rewrite(original, {})
            except Exception:
                rewritten = original
            results.append({
                "id": idx,
                "originalText": original,
                "correctedText": rewritten if rewritten else original,
                "status": "accepted" if eval_result.get("verdict") == "pass" else "rejected",
                "evaluation": eval_result.get("evaluation", []),
                "score": eval_result.get("score", 0.0),
                "verdict": eval_result.get("verdict", "fail")
            })
        return results
    except Exception as e:
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

@router.post("/api/v1/validate/suggest")
async def validate_suggest(request: ValidateBatchRequest):
    """Generate improvement suggestions for requirements."""
    try:
        items = request.items
        llm_suggest, _ = _get_llm_functions()
        result_map = {}
        for idx, text in enumerate(items, 1):
            req_id = f"REQ_{idx}"
            try:
                suggestions = llm_suggest(text, {}) or []
                result_map[req_id] = {"suggestions": suggestions}
            except Exception as e:
                result_map[req_id] = {"suggestions": [], "error": str(e)}
        return {"items": result_map}
    except Exception as e:
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

@router.post("/api/validation/run")
async def validation_run(request: ValidationRunRequest):
    """Run Society of Mind requirements validation with user clarification support."""
    try:
        requirements = request.requirements
        correlation_id = request.correlation_id
        criteria_keys = request.criteria_keys
        threshold = request.threshold
        if not requirements:
            return JSONResponse({"error": "requirements required"}, status_code=400)
        if not correlation_id:
            return JSONResponse({"error": "correlation_id required"}, status_code=400)
        logger.info(f"[Validation] Starting validation for {len(requirements)} requirements (session: {correlation_id})")
        from arch_team.agents.requirements_agent import validate_requirements
        result = await validate_requirements(requirements, criteria_keys=criteria_keys, threshold=threshold, correlation_id=correlation_id)
        return result
    except Exception as e:
        logger.error(f"[Validation] Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": "validation_failed", "message": str(e)}, status_code=500)

# ============================================================================
# SSE Streams
# ============================================================================

@router.get("/api/clarification/stream")
async def clarification_stream(session_id: str = Query(...)):
    """Server-Sent Events stream for real-time clarification questions."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    q: Queue = Queue()
    clarification_streams[session_id] = q
    async def event_generator():
        try:
            logger.info(f"[SSE] Client connected for session {session_id}")
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    if msg is None:
                        break
                    logger.info(f"[SSE] Sending to {session_id}: {msg}")
                    yield f"data: {json.dumps(msg)}\n\n"
                except Empty:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except asyncio.CancelledError:
            logger.info(f"[SSE] Client disconnected for session {session_id}")
        finally:
            clarification_streams.pop(session_id, None)
            logger.info(f"[SSE] Cleaned up session {session_id}")
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/api/workflow/stream")
async def workflow_stream(session_id: str = Query(...)):
    """Server-Sent Events stream for real-time workflow messages."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    q: Queue = Queue()
    workflow_streams[session_id] = q
    async def event_generator():
        try:
            logger.info(f"[Workflow SSE] Client connected for session {session_id}")
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    if msg is None:
                        break
                    logger.info(f"[Workflow SSE] Sending to {session_id}: {msg.get('type', 'unknown')}")
                    yield f"data: {json.dumps(msg)}\n\n"
                except Empty:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except asyncio.CancelledError:
            logger.info(f"[Workflow SSE] Client disconnected for session {session_id}")
        finally:
            workflow_streams.pop(session_id, None)
            logger.info(f"[Workflow SSE] Cleaned up session {session_id}")
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ============================================================================
# Clarification Answer
# ============================================================================

@router.post("/api/clarification/answer")
async def clarification_answer(request: ClarificationAnswerRequest):
    """Receive user's answer to a clarification question."""
    try:
        correlation_id = request.correlation_id.strip()
        answer = request.answer.strip()
        if not correlation_id:
            return JSONResponse({"error": "correlation_id required"}, status_code=400)
        if not answer:
            return JSONResponse({"error": "answer required"}, status_code=400)
        tmp_dir = PROJECT_DIR / "data" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        response_file = tmp_dir / f"clarification_{correlation_id}.txt"
        response_file.write_text(answer, encoding='utf-8')
        logger.info(f"[Clarification] Answer received for {correlation_id}: {answer[:50]}...")
        return {"success": True, "correlation_id": correlation_id, "message": "Answer received"}
    except Exception as e:
        logger.error(f"[Clarification] Error saving answer: {e}")
        return JSONResponse({"error": "internal_error", "message": str(e)}, status_code=500)

# ============================================================================
# Requirements Store Endpoints (Versioned Collections)
# ============================================================================

@router.get("/api/requirements/versions")
async def list_requirement_versions():
    """List all stored requirement versions."""
    try:
        store = _get_requirements_store()
        versions = store.list_versions()
        return {"success": True, "versions": versions}
    except Exception as e:
        logger.error(f"[RequirementsStore] List versions failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.post("/api/requirements/store")
async def store_requirements(request: StoreRequirementsRequest):
    """Store enhanced validated requirements to a versioned Qdrant collection."""
    try:
        requirements = request.requirements
        version = request.version
        metadata = request.metadata
        if not requirements:
            return JSONResponse({"success": False, "error": "No requirements provided"}, status_code=400)
        store = _get_requirements_store()
        result = store.store_requirements(requirements, version=version, metadata=metadata)
        if result.get("success"):
            return result
        else:
            return JSONResponse(result, status_code=500)
    except Exception as e:
        logger.error(f"[RequirementsStore] Store failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.get("/api/requirements/{version}")
async def get_requirements_by_version(version: str, limit: int = Query(default=10000)):
    """Get all requirements from a specific version."""
    try:
        store = _get_requirements_store()
        requirements = store.get_requirements(version, limit=limit)
        return {
            "success": True,
            "version": version,
            "count": len(requirements),
            "requirements": requirements
        }
    except Exception as e:
        logger.error(f"[RequirementsStore] Get requirements failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.post("/api/requirements/search")
async def search_requirements_in_version(request: SearchRequirementsRequest):
    """Semantic search within a specific version."""
    try:
        store = _get_requirements_store()
        results = store.search_requirements(
            query=request.query,
            version=request.version,
            top_k=request.top_k
        )
        return {
            "success": True,
            "version": request.version,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"[RequirementsStore] Search failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.delete("/api/requirements/{version}")
async def delete_requirements_version(version: str):
    """Delete a requirements version collection."""
    try:
        store = _get_requirements_store()
        success = store.delete_version(version)
        if success:
            return {"success": True, "message": f"Deleted version {version}"}
        else:
            return JSONResponse({"success": False, "error": f"Failed to delete {version}"}, status_code=500)
    except Exception as e:
        logger.error(f"[RequirementsStore] Delete failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# ============================================================================
# Master Workflow Endpoint
# ============================================================================

@router.post("/api/arch_team/process")
async def arch_team_process(
    files: List[UploadFile] = File(...),
    correlation_id: str = Form(...),
    model: str = Form(default="gpt-4o-mini"),
    provider: str = Form(default="openai"),
    chunk_size: str = Form(default="800"),
    chunk_overlap: str = Form(default="200"),
    use_llm_kg: str = Form(default="true"),
    validation_threshold: str = Form(default="0.7"),
    mode: str = Form(default="quick"),  # "quick" or "guided"
):
    """
    Master Society of Mind endpoint for complete arch_team workflow.
    
    Executes all phases:
    1. ChunkMiner: Extract requirements from uploaded files
    2. KG Agent: Build Knowledge Graph
    3. Validator: Evaluate and improve requirements
    4. RAG: Detect duplicates and cluster requirements
    5. QA: Final quality review
    6. UserClarification: Ask user if needed
    """
    import sys
    logger.info("[arch_team_process] === FUNCTION ENTERED ===")
    sys.stderr.write("[arch_team_process] === FUNCTION ENTERED ===\n")
    sys.stderr.flush()
    try:
        try:
            chunk_size_int = int(chunk_size) if chunk_size and chunk_size != 'undefined' else 800
        except ValueError:
            chunk_size_int = 800
        try:
            chunk_overlap_int = int(chunk_overlap) if chunk_overlap and chunk_overlap != 'undefined' else 200
        except ValueError:
            chunk_overlap_int = 200
        use_llm_kg_bool = use_llm_kg.lower() in ('true', '1', 'yes', 'on')
        validation_threshold_float = float(validation_threshold) if validation_threshold else 0.7
        if not files:
            return JSONResponse({"error": "files required"}, status_code=400)
        if not correlation_id:
            return JSONResponse({"error": "correlation_id required"}, status_code=400)
        sys.stderr.write(f"[MasterWorkflow] Starting with {len(files)} file(s) (session: {correlation_id})\n")
        sys.stderr.write(f"[MasterWorkflow] Provider: {provider}, Model: {model}\n")
        sys.stderr.flush()
        os.environ['LLM_PROVIDER'] = provider
        os.environ['OPENAI_MODEL'] = model
        temp_dir = Path(tempfile.mkdtemp(prefix="arch_team_"))
        file_paths = []
        for file in files:
            file_path = temp_dir / file.filename
            content = await file.read()
            file_path.write_bytes(content)
            file_paths.append(str(file_path))
            logger.info(f"[MasterWorkflow] Saved: {file.filename}")
        from arch_team.agents.master_agent import run_master_workflow
        result = await run_master_workflow(
            files=file_paths,
            correlation_id=correlation_id,
            model=model,
            chunk_size=chunk_size_int,
            chunk_overlap=chunk_overlap_int,
            use_llm_kg=use_llm_kg_bool,
            validation_threshold=validation_threshold_float,
            mode=mode,  # "quick" or "guided"
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        return result
    except Exception as e:
        import traceback
        error_msg = f"[MasterWorkflow] Error: {e}"
        traceback_str = traceback.format_exc()
        logger.error(error_msg)
        logger.error(traceback_str)
        return JSONResponse({
            "success": False,
            "workflow_status": "failed",
            "error": str(e),
            "traceback": traceback_str
        }, status_code=500)
