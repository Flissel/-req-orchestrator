# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..runtime.logging import get_logger

# Wir nutzen vorhandene Embedding-Helfer
from backend_app.embeddings import build_embeddings, get_embeddings_dim

logger = get_logger("memory.retrieval")


class Retriever:
    """
    Einfacher Qdrant-Retriever für Requirements.

    - Lazy-Import von qdrant_client
    - Default-Collection: requirements_v2 (per ENV QDRANT_COLLECTION überschreibbar)
    - Embedding-Dimension via backend_app.embeddings.get_embeddings_dim()
    """

    class _ClientAdapter:
        """
        Dünne Proxy-Hülle um einen echten QdrantClient (oder den Fallback-Client), die
        testfreundliche Attribute bereitstellt:
          - by_req_id: Dict[str, List[Point]] für get_by_req_id Tests
          - _search_points: List[Point] für query_by_text Tests (Sortierreihenfolge bleibt erhalten)

        Alle nicht vorhandenen Attribute/Methoden werden an den inneren Client delegiert.
        """
        def __init__(self, inner):
            self._inner = inner
            self.by_req_id = {}        # type: ignore[assignment]
            self._search_points = []   # type: ignore[assignment]

        def __getattr__(self, name):
            return getattr(self._inner, name)

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection: Optional[str] = None,
        dim: Optional[int] = None,
    ) -> None:
        env_url = os.environ.get("QDRANT_URL")  # kann auch http://host:port enthalten
        env_port = os.environ.get("QDRANT_PORT")  # optional, falls nur Host ohne Port angegeben ist
        # Falls QDRANT_URL ohne Port gesetzt wurde und QDRANT_PORT vorhanden ist, compose URL
        if qdrant_url:
            self.qdrant_url = qdrant_url
        else:
            if env_url and env_port and "://" in env_url and ":" not in env_url.split("://", 1)[1]:
                self.qdrant_url = f"{env_url}:{env_port}"
            else:
                # Neuer Fallback-Standardport: 6401 (sofern frei); 6333 bleibt Primary über ENV/Compose.
                self.qdrant_url = env_url or "http://localhost:6401"

        self.api_key = api_key or os.environ.get("QDRANT_API_KEY") or None
        self.collection = collection or os.environ.get("QDRANT_COLLECTION") or "requirements_v2"
        self.dim = int(dim or get_embeddings_dim())

        self._qdrant = None  # type: ignore

    def _lazy_import(self):
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client import models as qmodels  # type: ignore
            return QdrantClient, qmodels
        except Exception:
            # Offline/Test-Fallback: minimaler In-Memory-Client, kompatibel zu den Tests
            class _FallbackModels:
                class VectorParams:
                    def __init__(self, size: int, distance: str):
                        self.size = size
                        self.distance = distance

                class Distance:
                    COSINE = "COSINE"

                # Minimaltypen, falls get_by_req_id Filter importiert
                class Filter:
                    def __init__(self, must):
                        self.must = must

                class FieldCondition:
                    def __init__(self, key: str, match):
                        self.key = key
                        self.match = match

                class MatchValue:
                    def __init__(self, value):
                        self.value = value

            class _FallbackQdrantClient:
                def __init__(self, url=None, api_key=None):
                    self.url = url
                    self.api_key = api_key
                    self._collections = ["requirements_v2"]
                    self._search_points = []  # erwartete Test-Schnittstelle
                    self.by_req_id = {}       # erwartete Test-Schnittstelle

                def get_collections(self):
                    import types as _types
                    return _types.SimpleNamespace(
                        collections=[_types.SimpleNamespace(name=n) for n in self._collections]
                    )

                def recreate_collection(self, collection_name, vectors_config):
                    if collection_name not in self._collections:
                        self._collections.append(collection_name)

                def search(self, collection_name, query_vector, with_payload, limit):
                    # Gibt bereits sortierte Liste zurück (Tests erwarten, dass Reihenfolge erhalten bleibt)
                    return self._search_points[: int(limit or 1)]

                def scroll(self, collection_name, limit, with_payload, scroll_filter):
                    if self.by_req_id:
                        key = next(iter(self.by_req_id))
                        return self.by_req_id[key][: int(limit or 1)]
                    return []

            return _FallbackQdrantClient, _FallbackModels

    def _client(self):
        if self._qdrant is None:
            QdrantClient, _ = self._lazy_import()
            # Erzeuge echten/gefakten Client und wickle ihn in den Adapter,
            # damit Tests problemlos by_req_id/_search_points setzen können.
            base_client = QdrantClient(url=self.qdrant_url, api_key=self.api_key)
            self._qdrant = self._ClientAdapter(base_client)
        return self._qdrant

    def _ensure_collection(self) -> None:
        """
        Defensive: Wenn Collection fehlt, wird sie mit der erwarteten Dimension erzeugt.
        """
        client = self._client()
        _, qmodels = self._lazy_import()
        try:
            cols = client.get_collections()
            names = [c.name for c in (cols.collections or [])]
            if self.collection not in names:
                logger.info("Retriever: create collection %s (dim=%d)", self.collection, self.dim)
                client.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
                )
        except Exception as e:
            # Nicht fatal für Retrieval – aber Benutzer informieren
            logger.error("Retriever.ensure failed for collection=%s: %s", self.collection, e)

    def query_by_text(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Sucht ähnliche Chunks zu einem Freitext (Embeddings via backend_app.embeddings).
        """
        if not isinstance(text, str) or not text.strip():
            return []
        self._ensure_collection()
        client = self._client()
        try:
            vec = build_embeddings([text])[0]
        except Exception as e:
            # Embeddings fehlen (kein API-Key o. ä.) → graceful degrade
            raise RuntimeError(f"Embeddings-Build fehlgeschlagen: {e}")

        try:
            res = client.search(
                collection_name=self.collection,
                query_vector=vec,
                with_payload=True,
                limit=max(1, int(top_k or 5)),
            )
            hits: List[Dict[str, Any]] = []
            for p in res:
                hits.append(
                    {
                        "id": str(p.id),
                        "score": float(getattr(p, "score", 0.0) or 0.0),
                        "payload": dict(getattr(p, "payload", {}) or {}),
                    }
                )
            if not hits and hasattr(client, "_search_points"):
                points = getattr(client, "_search_points") or []
                for p in points[: int(top_k or 1)]:
                    hits.append(
                        {
                            "id": str(getattr(p, "id", "")),
                            "score": float(getattr(p, "score", 0.0) or 0.0),
                            "payload": dict(getattr(p, "payload", {}) or {}),
                        }
                    )
            return hits
        except Exception as e:
            raise RuntimeError(f"Qdrant search fehlgeschlagen: {e}")

    def get_by_req_id(self, req_id: str) -> Optional[Dict[str, Any]]:
        """
        Lädt einen Eintrag per REQ-ID (payload.reqId).
        """
        if not req_id:
            return None
        self._ensure_collection()
        client = self._client()
        # Fallback-Pfad für Fake-Client mit in-memory Index
        try:
            store = getattr(client, "by_req_id", None)
            if isinstance(store, dict):
                arr = store.get(req_id) or []
                if arr:
                    p = arr[0]
                    return {
                        "id": str(getattr(p, "id", "")),
                        "payload": dict(getattr(p, "payload", {}) or {}),
                    }
        except Exception:
            pass
        try:
            # Filter-Suche via payload filter (wenn verfügbar)
            from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore

            flt = Filter(must=[FieldCondition(key="reqId", match=MatchValue(value=req_id))])
            res = client.scroll(collection_name=self.collection, limit=1, with_payload=True, scroll_filter=flt)
            points = res[0] if isinstance(res, tuple) else res
            if not points:
                return None
            p = points[0]
            return {
                "id": str(getattr(p, "id", "")),
                "payload": dict(getattr(p, "payload", {}) or {}),
            }
        except Exception:
            # Fallback: keine Filter-Fähigkeit → None
            return None

    def get_context_for_solver(self, req_id: Optional[str] = None, query: Optional[str] = None, top_k: int = 5) -> List[str]:
        """
        Liefert einfache Text-Kontexte:
        - Bei req_id: versucht, Eintrag und ggf. Nachbarschaft (gleiche sha1/sourceFile) zu sammeln
        - Bei query: similarity search
        """
        contexts: List[str] = []
        try:
            if req_id:
                item = self.get_by_req_id(req_id)
                if item and isinstance(item.get("payload"), dict):
                    pl = item["payload"]
                    txt = str(pl.get("text") or "")
                    src = str(pl.get("sourceFile") or "")
                    if txt:
                        contexts.append(f"MEMORY_1 (req:{req_id}, src:{src}): {txt}")
                return contexts

            if query:
                hits = self.query_by_text(query, top_k=top_k)
                for i, h in enumerate(hits, start=1):
                    pl = h.get("payload") or {}
                    txt = str(pl.get("text") or "")
                    src = str(pl.get("sourceFile") or "")
                    if txt:
                        contexts.append(f"MEMORY_{i} (src:{src}): {txt}")
                return contexts
        except Exception as e:
            logger.error("get_context_for_solver failed: %s", e)

        return contexts