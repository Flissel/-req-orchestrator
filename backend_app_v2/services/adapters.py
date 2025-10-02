# -*- coding: utf-8 -*-
"""
Service-Layer Adapter (Implementierungen der Ports) – framework-frei

Bindet bestehende Implementierungen aus backend_app.* ein und stellt sie
über die Protokolle in [ports.py](backend_app_v2/services/ports.py) bereit.

Adapter:
- EmbeddingsAdapter    → backend_app.embeddings
- VectorStoreAdapter   → backend_app.vector_store (Qdrant)
- PersistenceAdapter   → backend_app.db

Hinweise
- Kein Import von FastAPI/Flask; Services konsumieren ausschließlich diese Adapter via Ports.
- Fehler werden in ServiceError (code/message) gekapselt.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .ports import (
    EmbeddingsPort,
    PersistencePort,
    RequestContext,
    ServiceError,
    VectorStorePort,
    safe_request_id,
    LLMPort,
)

# Bestehende Modul-Funktionen aus Legacy/Shared-Code
from backend_app.embeddings import build_embeddings as _build_embeddings, get_embeddings_dim as _get_dim
from backend_app.vector_store import (
    list_collections as _vs_list_collections,
    healthcheck as _vs_health,
    reset_collection as _vs_reset_collection,
    upsert_points as _vs_upsert_points,
    search as _vs_search,
    fetch_window_by_source_and_index as _vs_fetch_window_by_source_and_index,
)
# DB Functions
from backend_app.db import get_db as _get_db, load_criteria as _db_load_criteria

# Optional vorhanden (DDL/Migrationen)
try:
    from backend_app.db import ensure_schema_migrations as _db_ensure_schema
except Exception:  # pragma: no cover
    _db_ensure_schema = None

# LLM-Implementierungen (Legacy)
from backend_app.llm import (
    llm_evaluate as _llm_evaluate,
    llm_suggest as _llm_suggest,
    llm_rewrite as _llm_rewrite,
    llm_apply_with_suggestions as _llm_apply_with_suggestions,
)


class EmbeddingsAdapter(EmbeddingsPort):
    """Adapter für EmbeddingsPort via backend_app.embeddings"""

    def __init__(self, default_model: Optional[str] = None) -> None:
        self._default_model = default_model

    def build_embeddings(
        self,
        texts: Sequence[str],
        *,
        model: Optional[str] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[List[float]]:
        try:
            sel_model = model or self._default_model
            # backend_app.embeddings erwartet model als kwarg (optional)
            vectors = _build_embeddings(list(texts), model=sel_model)  # type: ignore[arg-type]
            if not isinstance(vectors, list):
                raise ServiceError("embeddings_failed", "Unexpected embeddings return type", details={"type": str(type(vectors))})
            return vectors  # List[List[float]]
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("embeddings_failed", "Failed to build embeddings", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def get_dim(self, *, ctx: Optional[RequestContext] = None) -> int:
        try:
            return int(_get_dim())
        except Exception as e:
            raise ServiceError("embeddings_dim_failed", "Failed to read embeddings dimension", details={"request_id": safe_request_id(ctx), "error": str(e)})


class VectorStoreAdapter(VectorStorePort):
    """Adapter für VectorStorePort via backend_app.vector_store (Qdrant)"""

    def list_collections(self, *, ctx: Optional[RequestContext] = None) -> List[str]:
        try:
            cols = _vs_list_collections()
            return list(cols or [])
        except Exception as e:
            raise ServiceError("vector_list_failed", "Failed to list collections", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def health(self, *, ctx: Optional[RequestContext] = None) -> Mapping[str, Any]:
        try:
            return _vs_health()
        except Exception as e:
            raise ServiceError("vector_health_failed", "Vector healthcheck failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def reset_collection(self, collection_name: str, dim: int, *, ctx: Optional[RequestContext] = None) -> Mapping[str, Any]:
        try:
            return _vs_reset_collection(collection_name=collection_name, dim=int(dim))
        except Exception as e:
            raise ServiceError(
                "vector_reset_failed",
                "Failed to reset collection",
                details={"request_id": safe_request_id(ctx), "collection": collection_name, "dim": dim, "error": str(e)},
            )

    def upsert_points(
        self,
        items: Sequence[Dict[str, Any]],
        *,
        collection_name: str,
        dim: int,
        ctx: Optional[RequestContext] = None,
    ) -> Mapping[str, Any]:
        try:
            return _vs_upsert_points(list(items), collection_name=collection_name, dim=int(dim))
        except Exception as e:
            raise ServiceError(
                "vector_upsert_failed",
                "Failed to upsert points",
                details={
                    "request_id": safe_request_id(ctx),
                    "collection": collection_name,
                    "dim": dim,
                    "count": len(items),
                    "error": str(e),
                },
            )

    def search(
        self,
        vector: Sequence[float],
        *,
        top_k: int,
        collection_name: str,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        try:
            hits = _vs_search(list(vector), top_k=int(top_k), collection_name=collection_name)
            return list(hits or [])
        except Exception as e:
            raise ServiceError(
                "vector_search_failed",
                "Vector search failed",
                details={
                    "request_id": safe_request_id(ctx),
                    "collection": collection_name,
                    "top_k": top_k,
                    "error": str(e),
                },
            )

    def fetch_window_by_source_and_index(
        self,
        source: str,
        start: int,
        end: int,
        *,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        try:
            rows = _vs_fetch_window_by_source_and_index(source, int(start), int(end))
            return list(rows or [])
        except Exception as e:
            raise ServiceError(
                "vector_fetch_window_failed",
                "Failed to fetch window by source/index",
                details={
                    "request_id": safe_request_id(ctx),
                    "source": source,
                    "start": start,
                    "end": end,
                    "error": str(e),
                },
            )


class PersistenceAdapter(PersistencePort):
    """Adapter für PersistencePort via backend_app.db"""

    def ensure_schema(self, *, ctx: Optional[RequestContext] = None) -> None:
        try:
            if _db_ensure_schema:
                _db_ensure_schema()
        except Exception as e:
            raise ServiceError("db_schema_failed", "Failed to ensure schema", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def get_latest_rewrite_row_for_eval(self, evaluation_id: str, *, ctx: Optional[RequestContext] = None) -> Optional[Mapping[str, Any]]:
        try:
            return _db_get_latest_rewrite_row_for_eval(str(evaluation_id))
        except Exception as e:
            raise ServiceError(
                "db_latest_rewrite_failed",
                "Failed to get latest rewrite row",
                details={"request_id": safe_request_id(ctx), "evaluation_id": evaluation_id, "error": str(e)},
            )

    def get_latest_evaluation_by_checksum(self, checksum: str, *, ctx: Optional[RequestContext] = None) -> Optional[Mapping[str, Any]]:
        try:
            return _db_get_latest_evaluation_by_checksum(str(checksum))
        except Exception as e:
            raise ServiceError(
                "db_latest_eval_failed",
                "Failed to get latest evaluation by checksum",
                details={"request_id": safe_request_id(ctx), "checksum": checksum, "error": str(e)},
            )

    def load_criteria(self, *, ctx: Optional[RequestContext] = None) -> List[Mapping[str, Any]]:
        try:
            conn = _get_db()
            rows = _db_load_criteria(conn)
            return list(rows or [])
        except Exception as e:
            raise ServiceError("db_load_criteria_failed", "Failed to load criteria", details={"request_id": safe_request_id(ctx), "error": str(e)})


class LLMAdapter(LLMPort):
    """Adapter für LLMPort via backend_app.llm"""

    def evaluate(
        self,
        requirement_text: str,
        criteria_keys: Sequence[str],
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        try:
            details = _llm_evaluate(str(requirement_text or ""), list(criteria_keys or []), dict(context or {}))
            if not isinstance(details, list):
                raise ServiceError("llm_evaluate_failed", "Unexpected evaluate return type", details={"type": str(type(details))})
            return details
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("llm_evaluate_failed", "LLM evaluate failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def suggest(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        try:
            atoms = _llm_suggest(str(requirement_text or ""), dict(context or {}))
            if not isinstance(atoms, list):
                raise ServiceError("llm_suggest_failed", "Unexpected suggest return type", details={"type": str(type(atoms))})
            return atoms
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("llm_suggest_failed", "LLM suggest failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def rewrite(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        ctx: Optional[RequestContext] = None,
    ) -> str:
        try:
            return str(_llm_rewrite(str(requirement_text or ""), dict(context or {})))
        except Exception as e:
            raise ServiceError("llm_rewrite_failed", "LLM rewrite failed", details={"request_id": safe_request_id(ctx), "error": str(e)})

    def apply_with_suggestions(
        self,
        requirement_text: str,
        *,
        context: Optional[Mapping[str, Any]] = None,
        selected_atoms: Sequence[Mapping[str, Any]] = (),
        mode: str = "merge",
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        try:
            items = _llm_apply_with_suggestions(
                str(requirement_text or ""),
                dict(context or {}),
                list(selected_atoms or []),  # type: ignore[arg-type]
                str(mode or "merge"),
            )
            if not isinstance(items, list):
                raise ServiceError("llm_apply_failed", "Unexpected apply return type", details={"type": str(type(items))})
            return items
        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError("llm_apply_failed", "LLM apply_with_suggestions failed", details={"request_id": safe_request_id(ctx), "error": str(e)})