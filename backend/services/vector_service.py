# -*- coding: utf-8 -*-
"""
VectorService (framework-frei)

Zweck
- Kapselt Vektor- und einfache RAG-Funktionalität (RAG-Search) ohne Web-Framework.
- Nutzt Ports/Adapter aus services.ports/adapters, um bestehende Implementierungen
  aus backend_app.* einzubinden, bleibt aber testbar und unabhängig von FastAPI/Flask.

Abhängigkeiten (DI)
- embeddings: EmbeddingsPort (Default: EmbeddingsAdapter)
- vector_store: VectorStorePort (Default: VectorStoreAdapter)

Hinweis
- Dieser Service ist bewusst schlank gehalten; er bildet die aktuell in den Routern
  verwendeten Operationen ab, sodass die Router auf diesen Service umgestellt werden können.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .ports import EmbeddingsPort, VectorStorePort, RequestContext, ServiceError, safe_request_id
from .adapters import EmbeddingsAdapter, VectorStoreAdapter

# Defaults/Settings aus Legacy-Settings beziehen (nur Werte, keine Framework-Kopplung)
from backend.core import settings as _settings


class VectorService:
    def __init__(
        self,
        embeddings: Optional[EmbeddingsPort] = None,
        vector_store: Optional[VectorStorePort] = None,
        *,
        default_collection: Optional[str] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self._emb = embeddings or EmbeddingsAdapter(default_model=default_model or getattr(_settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))
        self._vs = vector_store or VectorStoreAdapter()
        self._default_collection = default_collection or getattr(_settings, "QDRANT_COLLECTION", "requirements_v1")
        self._default_model = default_model or getattr(_settings, "EMBEDDINGS_MODEL", "text-embedding-3-small")

    # -----------------------
    # Verwaltung / Health
    # -----------------------

    def list_collections(self, *, ctx: Optional[RequestContext] = None) -> Dict[str, Any]:
        cols = self._vs.list_collections(ctx=ctx)
        return {"items": cols}

    def health(self, *, ctx: Optional[RequestContext] = None) -> Dict[str, Any]:
        return dict(self._vs.health(ctx=ctx))

    def reset_collection(
        self,
        collection: Optional[str] = None,
        dim: Optional[int] = None,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> Dict[str, Any]:
        coll = collection or self._default_collection
        d = dim if isinstance(dim, int) and dim > 0 else self._emb.get_dim(ctx=ctx)
        reset_res = self._vs.reset_collection(coll, d, ctx=ctx)
        cols = self._vs.list_collections(ctx=ctx)
        return {"status": "ok", "reset": reset_res, "collections": cols}

    # -----------------------
    # Source Full (Dokument-Fenster)
    # -----------------------

    def source_full(self, source: str, *, ctx: Optional[RequestContext] = None, window: int = 256, limit: int = 5000) -> Dict[str, Any]:
        if not isinstance(source, str) or not source.strip():
            raise ServiceError("invalid_request", "source fehlt", details={"request_id": safe_request_id(ctx)})
        start = 0
        out_chunks: List[Dict[str, Any]] = []
        seen = set()
        while True:
            batch = self._vs.fetch_window_by_source_and_index(source, start, start + window, ctx=ctx)
            if not batch:
                break
            added = 0
            for c in batch:
                p = dict(c.get("payload") or {})
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
            if len(seen) > limit:
                break

        out_chunks.sort(key=lambda x: (x["chunkIndex"] if x["chunkIndex"] is not None else 0))
        full_text = "\n".join([c["text"] for c in out_chunks if c["text"]])
        return {"sourceFile": source, "chunks": out_chunks, "text": full_text}

    # -----------------------
    # RAG Search (einfach)
    # -----------------------

    def rag_search(
        self,
        query: str,
        *,
        top_k: int = 5,
        collection: Optional[str] = None,
        model: Optional[str] = None,
        ctx: Optional[RequestContext] = None,
    ) -> Dict[str, Any]:
        q = (query or "").strip()
        if not q:
            raise ServiceError("invalid_request", "query fehlt", details={"request_id": safe_request_id(ctx)})

        coll = collection or self._default_collection
        mdl = model or self._default_model
        qvec = self._emb.build_embeddings([q], model=mdl, ctx=ctx)[0]
        hits = self._vs.search(qvec, top_k=int(top_k or 5), collection_name=str(coll), ctx=ctx)
        return {"query": q, "topK": int(top_k or 5), "collection": coll, "hits": hits}