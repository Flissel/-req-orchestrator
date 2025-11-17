# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from backend.core import settings
# Service-Layer
from backend.services.vector_service import VectorService

# Initialisiere Service einmal (Adapter nutzen backend_app.* Implementierungen)
_vector_service = VectorService()

# SHIMs für Test-Kompatibilität (Monkeypatch in tests/parity/conftest.py ersetzt diese Namen)
# Signaturen bewusst einfach gehalten, damit Fakes ohne Parameter funktionieren.
def vs_list_collections():
    return _vector_service._vs.list_collections()

def vs_health():
    return _vector_service._vs.health()

def vs_reset_collection(collection_name: str, dim: int):
    return _vector_service._vs.reset_collection(collection_name=collection_name, dim=int(dim))

def vs_search(vector, top_k: int, collection_name: str):
    return _vector_service._vs.search(vector, top_k=int(top_k), collection_name=collection_name)

def fetch_window_by_source_and_index(source: str, start: int, end: int):
    return _vector_service._vs.fetch_window_by_source_and_index(source, int(start), int(end))

def build_embeddings(texts, model: str = None):
    return _vector_service._emb.build_embeddings(list(texts), model=model)

def get_embeddings_dim():
    return _vector_service._emb.get_dim()

router = APIRouter(tags=["vector", "rag"])


@router.get("/api/v1/vector/collections")
def vector_collections_v2() -> JSONResponse:
    try:
        cols = vs_list_collections()
        return JSONResponse(content={"items": cols}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/vector/health")
def vector_health_v2() -> JSONResponse:
    try:
        h = vs_health()
        return JSONResponse(content=h, status_code=200)
    except Exception as e:
        return JSONResponse(content={"status": "error", "error": str(e)}, status_code=200)


@router.api_route("/api/v1/vector/reset", methods=["POST", "DELETE"])
async def vector_reset_v2(request: Request) -> JSONResponse:
    """
    Droppt die Qdrant-Collection und legt sie neu an.
    Body oder Query: { collection?: str, dim?: int }
    """
    try:
        body = {}
        try:
            body = await request.json()
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}

        collection = (
            body.get("collection")
            or request.query_params.get("collection")
            or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        )
        dim_val = body.get("dim") or request.query_params.get("dim")
        try:
            dim_int = int(dim_val) if dim_val is not None else None
        except Exception:
            dim_int = None
        if not isinstance(dim_int, int) or dim_int <= 0:
            dim_int = get_embeddings_dim()

        res = vs_reset_collection(collection_name=str(collection), dim=int(dim_int))
        cols = vs_list_collections()
        payload = {"status": "ok", "reset": res, "collections": cols}
        return JSONResponse(content=payload, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/vector/reset")
def vector_reset_get_v2(
    confirm: Optional[str] = Query(None),
    collection: Optional[str] = Query(None),
    dim: Optional[int] = Query(None),
) -> JSONResponse:
    """
    GET-Variante mit confirm=1, optional collection, dim.
    """
    try:
        if str(confirm or "").lower() not in ("1", "true", "yes"):
            return JSONResponse(
                content={"error": "confirm_required", "message": "Use confirm=1 to reset the vector collection."},
                status_code=400,
            )
        coll = collection or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        d = int(dim) if isinstance(dim, int) and dim > 0 else get_embeddings_dim()
        res = vs_reset_collection(collection_name=str(coll), dim=int(d))
        cols = vs_list_collections()
        return JSONResponse(content={"status": "ok", "reset": res, "collections": cols, "method": "GET"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/vector/source/full")
def vector_source_full_v2(source: Optional[str] = Query(None)) -> JSONResponse:
    """
    Liefert alle Chunks eines sourceFile zusammen mit aggregiertem Text.
    Response: { sourceFile, chunks: [{chunkIndex,text}], text }
    """
    try:
        if not isinstance(source, str) or not source.strip():
            return JSONResponse(content={"error": "invalid_request", "message": "source fehlt"}, status_code=400)

        window = 256
        start = 0
        out_chunks: List[Dict[str, Any]] = []
        seen = set()
        while True:
            batch = fetch_window_by_source_and_index(source, start, start + window)
            if not batch:
                break
            added = 0
            for c in batch:
                p = c.get("payload") or {}
                ci = p.get("chunkIndex")
                try:
                    ci = int(ci)
                except Exception:
                    ci = None
                t = str(p.get("text") or "")
                if ci is None:
                    continue
                if ci in seen:
                    continue
                seen.add(ci)
                out_chunks.append({"chunkIndex": ci, "text": t})
                added += 1
            if added == 0:
                break
            start += window + 1
            if len(seen) > 5000:
                break

        out_chunks.sort(key=lambda x: (x["chunkIndex"] if x["chunkIndex"] is not None else 0))
        full_text = "\n".join([c["text"] for c in out_chunks if c["text"]])
        return JSONResponse(content={"sourceFile": source, "chunks": out_chunks, "text": full_text}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/rag/search")
def rag_search_v2(
    query: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=100),
    collection: Optional[str] = Query(None),
) -> JSONResponse:
    """
    Einfache Vektor-Suche: GET /api/v1/rag/search?query=...&top_k=5&collection=...
    """
    try:
        q = (query or "").strip()
        if not q:
            return JSONResponse(content={"error": "invalid_request", "message": "query fehlt"}, status_code=400)
        coll = collection or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
        qvec = build_embeddings([q], model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))[0]
        hits = vs_search(qvec, top_k=int(top_k or 5), collection_name=str(coll))
        return JSONResponse(content={"query": q, "topK": int(top_k or 5), "collection": coll, "hits": hits}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)