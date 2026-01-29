# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..runtime.logging import get_logger
from backend.core.embeddings import build_embeddings, get_embeddings_dim

# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

logger = get_logger("memory.qdrant_kg")


class QdrantKGClient:
    """
    Qdrant-gestützter Knowledge-Graph-Speicher für Requirements.

    Collections:
      - kg_nodes_v1: Knoten (Requirement, Actor, Action, Entity, Tag, ...)
      - kg_edges_v1: Kanten (HAS_ACTOR, HAS_ACTION, ON_ENTITY, HAS_TAG, ...)

    Embeddings:
      - Knoten: Embedding auf Basis von name/label (oder zusammengesetztem Text)
      - Kanten: Embedding auf Basis von "from_label REL to_label"

    Idempotenz/Dedupe:
      - Wir verwenden 'id' (oder 'canonical_key') als Point-ID.
      - Beim Upsert werden Duplicate Keys überschrieben (idempotent).

    ENV:
      - QDRANT_URL (z. B. http://host.docker.internal oder http://host.docker.internal:6401)
      - QDRANT_PORT (optional, falls URL ohne Port)
      - QDRANT_API_KEY (optional)
    """

    # Klassenweiter Schalter: Collections nur einmal pro Prozess sicherstellen
    _collections_ready: bool = False

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        api_key: Optional[str] = None,
        nodes_collection: str = "kg_nodes_v1",
        edges_collection: str = "kg_edges_v1",
        dim: Optional[int] = None,
    ) -> None:
        # URL/Port-Zusammensetzung with centralized port configuration
        if qdrant_url:
            self.qdrant_url = qdrant_url
        else:
            # Use centralized port configuration if available
            if _ports:
                self.qdrant_url = _ports.QDRANT_FULL_URL
            else:
                # Legacy fallback
                env_url = os.environ.get("QDRANT_URL")
                env_port = os.environ.get("QDRANT_PORT")
                if env_url and env_port and "://" in env_url and ":" not in env_url.split("://", 1)[1]:
                    self.qdrant_url = f"{env_url}:{env_port}"
                else:
                    # Fallback-HTTP-Port (falls Primary 6333 nicht erreichbar): 6401
                    self.qdrant_url = env_url or "http://localhost:6401"

        self.api_key = api_key or os.environ.get("QDRANT_API_KEY") or None
        self.nodes_collection = nodes_collection
        self.edges_collection = edges_collection
        self.dim = int(dim or get_embeddings_dim())

        # Batch-Größe für Upserts (anpassbar via ENV QDRANT_UPSERT_BATCH)
        self.batch_size = int(os.environ.get("QDRANT_UPSERT_BATCH", "500"))
        # einfacher In-Memory Embedding-Cache (Text -> Vektor)
        self._embed_cache: Dict[str, List[float]] = {}

        self._qdrant = None  # type: ignore

    # -----------------------------
    # Lazy Import + Client
    # -----------------------------
    def _lazy_import(self):
        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client import models as qmodels  # type: ignore
            return QdrantClient, qmodels
        except Exception:
            raise RuntimeError("qdrant-client nicht installiert. Bitte 'pip install qdrant-client' ausführen.")

    def _client(self):
        if self._qdrant is None:
            QdrantClient, _ = self._lazy_import()
            self._qdrant = QdrantClient(url=self.qdrant_url, api_key=self.api_key)
        return self._qdrant

    # -----------------------------
    # Ensure Collections
    # -----------------------------
    def ensure_collections(self) -> None:
        # Skip, falls bereits erledigt
        if QdrantKGClient._collections_ready:
            return
        client = self._client()
        _, qmodels = self._lazy_import()
        try:
            cols = client.get_collections()
            names = [c.name for c in (cols.collections or [])]

            if self.nodes_collection not in names:
                logger.info("KG: create nodes collection %s (dim=%d)", self.nodes_collection, self.dim)
                client.recreate_collection(
                    collection_name=self.nodes_collection,
                    vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
                )
            if self.edges_collection not in names:
                logger.info("KG: create edges collection %s (dim=%d)", self.edges_collection, self.dim)
                client.recreate_collection(
                    collection_name=self.edges_collection,
                    vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
                )
            # einmalig markieren
            QdrantKGClient._collections_ready = True
        except Exception as e:
            raise RuntimeError(f"QdrantKGClient.ensure_collections() fehlgeschlagen: {e}")

    # -----------------------------
    # Embeddings Helpers
    # -----------------------------
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Cache beachten und fehlende Texte in einem Batch nachziehen
        out: List[Optional[List[float]]] = [None] * len(texts)
        missing: List[str] = []
        missing_idx: List[int] = []
        for i, t in enumerate(texts):
            v = self._embed_cache.get(t)
            if v is not None:
                out[i] = v
            else:
                missing.append(t)
                missing_idx.append(i)
        if missing:
            # innerhalb der fehlenden deduplizieren
            uniq: List[str] = []
            idx_map: Dict[str, int] = {}
            for t in missing:
                if t not in idx_map:
                    idx_map[t] = len(uniq)
                    uniq.append(t)
            vecs = build_embeddings(uniq)
            for t, vec in zip(uniq, vecs):
                self._embed_cache[t] = vec
            for pos, i in enumerate(missing_idx):
                t = texts[i]
                out[i] = self._embed_cache[t]
        # type: ignore - alle None sollten gefüllt sein
        return out  # type: ignore

    # -----------------------------
    # Upserts
    # -----------------------------
    def upsert_nodes(self, nodes: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
        """
        nodes: [{ "id": str, "type": str, "name": str, "payload": {...}, "embed_text"?: str }, ...]
        id oder canonical_key MUSS eindeutig sein. Wir verwenden 'id' als Point-ID.
        """
        if not nodes:
            return 0, []
        self.ensure_collections()
        client = self._client()
        _, qmodels = self._lazy_import()

        ids: List[str] = []
        texts: List[str] = []
        payloads: List[Dict[str, Any]] = []

        for n in nodes:
            nid = str(n.get("id") or n.get("node_id") or n.get("canonical_key") or "")
            if not nid:
                # skip invalid
                continue
            ids.append(nid)
            name = str(n.get("name") or n.get("label") or n.get("type") or nid)
            et = str(n.get("embed_text") or name).strip()
            if not et:
                et = name
            texts.append(et)

            # assemble payload
            pld = dict(n.get("payload") or {})
            pld["node_id"] = nid
            pld["type"] = str(n.get("type") or pld.get("type") or "Unknown")
            pld["name"] = name
            payloads.append(pld)

        try:
            vecs = self._embed_texts(texts)
        except Exception as e:
            raise RuntimeError(f"KG Node-Embeddings fehlgeschlagen: {e}")

        # Qdrant verlangt als Point-ID int oder UUID. Wir erzeugen deterministische UUID5 aus der stabilen Knoten-ID.
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, str(nid))) for nid in ids]

        total = 0
        # batch upsert zur Reduktion von Payload-Spitzen
        for start in range(0, len(point_ids), max(1, self.batch_size)):
            end = min(len(point_ids), start + max(1, self.batch_size))
            points = []
            for pid, vec, pld in zip(point_ids[start:end], vecs[start:end], payloads[start:end]):
                points.append(qmodels.PointStruct(id=pid, vector=vec, payload=pld))
            try:
                if points:
                    client.upsert(collection_name=self.nodes_collection, points=points)
                    total += len(points)
            except Exception as e:
                raise RuntimeError(f"KG Node-Upsert fehlgeschlagen: {e}")

        return total, ids

    def upsert_edges(self, edges: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
        """
        edges: [{ "id": str, "from": str, "to": str, "rel": str, "payload": {...}, "embed_text"?: str }, ...]
        id/canonical_key MUSS eindeutig sein. Wir verwenden 'id' als Point-ID.
        """
        if not edges:
            return 0, []
        self.ensure_collections()
        client = self._client()
        _, qmodels = self._lazy_import()

        ids: List[str] = []
        texts: List[str] = []
        payloads: List[Dict[str, Any]] = []

        for e in edges:
            eid = str(e.get("id") or e.get("edge_id") or e.get("canonical_key") or "")
            if not eid:
                # skip
                continue
            ids.append(eid)

            fr = str(e.get("from") or e.get("from_node_id") or "")
            to = str(e.get("to") or e.get("to_node_id") or "")
            rel = str(e.get("rel") or "RELATES_TO")

            et = str(e.get("embed_text") or f"{fr} {rel} {to}").strip()
            texts.append(et)

            pld = dict(e.get("payload") or {})
            pld["edge_id"] = eid
            pld["from_node_id"] = fr
            pld["to_node_id"] = to
            pld["rel"] = rel
            payloads.append(pld)

        try:
            vecs = self._embed_texts(texts)
        except Exception as e:
            raise RuntimeError(f"KG Edge-Embeddings fehlgeschlagen: {e}")

        # deterministische UUID5 aus stabiler Kanten-ID
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, str(eid))) for eid in ids]

        total = 0
        # batch upsert zur Reduktion von Payload-Spitzen (analog zu Nodes)
        for start in range(0, len(point_ids), max(1, self.batch_size)):
            end = min(len(point_ids), start + max(1, self.batch_size))
            points = []
            for pid, vec, pld in zip(point_ids[start:end], vecs[start:end], payloads[start:end]):
                points.append(qmodels.PointStruct(id=pid, vector=vec, payload=pld))
            try:
                if points:
                    client.upsert(collection_name=self.edges_collection, points=points)
                    total += len(points)
            except Exception as e:
                raise RuntimeError(f"KG Edge-Upsert fehlgeschlagen: {e}")

        return total, ids

    # -----------------------------
    # Queries
    # -----------------------------
    def search_nodes(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        self.ensure_collections()
        client = self._client()
        try:
            vec = self._embed_texts([query])[0]
        except Exception as e:
            raise RuntimeError(f"KG Node-Suche: Embeddings fehlgeschlagen: {e}")

        try:
            res = client.search(collection_name=self.nodes_collection, query_vector=vec, with_payload=True, limit=max(1, int(top_k or 10)))
            out: List[Dict[str, Any]] = []
            for p in res:
                out.append({"id": str(getattr(p, "id", "")), "score": float(getattr(p, "score", 0.0) or 0.0), "payload": dict(getattr(p, "payload", {}) or {})})
            return out
        except Exception as e:
            raise RuntimeError(f"KG Node-Suche fehlgeschlagen: {e}")

    def search_edges(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []
        self.ensure_collections()
        client = self._client()
        try:
            vec = self._embed_texts([query])[0]
        except Exception as e:
            raise RuntimeError(f"KG Edge-Suche: Embeddings fehlgeschlagen: {e}")

        try:
            res = client.search(collection_name=self.edges_collection, query_vector=vec, with_payload=True, limit=max(1, int(top_k or 10)))
            out: List[Dict[str, Any]] = []
            for p in res:
                out.append({"id": str(getattr(p, "id", "")), "score": float(getattr(p, "score", 0.0) or 0.0), "payload": dict(getattr(p, "payload", {}) or {})})
            return out
        except Exception as e:
            raise RuntimeError(f"KG Edge-Suche fehlgeschlagen: {e}")

    def neighbors(
        self,
        node_id: str,
        rels: Optional[List[str]] = None,
        direction: str = "both",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Liefert 1-Hop Nachbarschaft:
          - edges: alle Kanten, die from_node_id==node_id (out) bzw. to_node_id==node_id (in) haben
          - nodes: alle beteiligten Gegenknoten (inkl. self node optional)
        Hinweis: Qdrant unterstützt Filter; wir nutzen scroll mit Filter.
        """
        if not node_id:
            return {"nodes": [], "edges": []}

        self.ensure_collections()
        client = self._client()

        try:
            # Filter-Modellobjekte importieren
            from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore
        except Exception:
            # Kein Filter verfügbar
            logger.error("KG neighbors: qdrant_client.models nicht verfügbar")
            return {"nodes": [], "edges": []}

        must_conditions = []
        if direction in ("out", "both"):
            must_conditions.append(FieldCondition(key="from_node_id", match=MatchValue(value=node_id)))
        if direction in ("in", "both"):
            must_conditions.append(FieldCondition(key="to_node_id", match=MatchValue(value=node_id)))
        if rels:
            # Einfache OR über mehrere RELs bilden: hier iterativ aufrufen (vereinfachend)
            edges_payload: List[Dict[str, Any]] = []
            for r in rels:
                flt = Filter(must=must_conditions + [FieldCondition(key="rel", match=MatchValue(value=r))])
                try:
                    result = client.scroll(collection_name=self.edges_collection, limit=max(1, int(limit or 200)), with_payload=True, scroll_filter=flt)
                    points = result[0] if isinstance(result, tuple) else result
                    for p in (points or []):
                        edges_payload.append(dict(getattr(p, "payload", {}) or {}))
                except Exception as e:
                    logger.error("KG neighbors scroll failed (rel=%s): %s", r, e)
            # resolve nodes
            node_ids = set()
            for pl in edges_payload:
                node_ids.add(str(pl.get("from_node_id") or ""))
                node_ids.add(str(pl.get("to_node_id") or ""))
            node_ids.discard("")
            nodes_payload = self._fetch_nodes_by_ids(list(node_ids))
            return {"nodes": nodes_payload, "edges": edges_payload}

        # Ohne REL-Filter
        flt = Filter(must=must_conditions)
        try:
            result = client.scroll(collection_name=self.edges_collection, limit=max(1, int(limit or 200)), with_payload=True, scroll_filter=flt)
            points = result[0] if isinstance(result, tuple) else result
            edges_payload = [dict(getattr(p, "payload", {}) or {}) for p in (points or [])]
        except Exception as e:
            logger.error("KG neighbors scroll failed: %s", e)
            edges_payload = []

        node_ids = set()
        for pl in edges_payload:
            node_ids.add(str(pl.get("from_node_id") or ""))
            node_ids.add(str(pl.get("to_node_id") or ""))
        node_ids.discard("")
        nodes_payload = self._fetch_nodes_by_ids(list(node_ids))
        return {"nodes": nodes_payload, "edges": edges_payload}

    # -----------------------------
    # Export all nodes and edges
    # -----------------------------
    def export_all(self, limit: int = 10000) -> Dict[str, Any]:
        """
        Export all nodes and edges from KG collections.
        Returns: {"nodes": [...], "edges": [...]}
        """
        self.ensure_collections()
        client = self._client()

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        try:
            # Scroll through all nodes
            offset = None
            while True:
                result = client.scroll(
                    collection_name=self.nodes_collection,
                    limit=min(100, limit - len(nodes)),
                    with_payload=True,
                    offset=offset
                )
                points, next_offset = result if isinstance(result, tuple) else (result, None)
                for p in (points or []):
                    nodes.append(dict(getattr(p, "payload", {}) or {}))
                if not next_offset or len(nodes) >= limit:
                    break
                offset = next_offset
        except Exception as e:
            logger.error("KG export nodes failed: %s", e)

        try:
            # Scroll through all edges
            offset = None
            while True:
                result = client.scroll(
                    collection_name=self.edges_collection,
                    limit=min(100, limit - len(edges)),
                    with_payload=True,
                    offset=offset
                )
                points, next_offset = result if isinstance(result, tuple) else (result, None)
                for p in (points or []):
                    edges.append(dict(getattr(p, "payload", {}) or {}))
                if not next_offset or len(edges) >= limit:
                    break
                offset = next_offset
        except Exception as e:
            logger.error("KG export edges failed: %s", e)

        return {"nodes": nodes, "edges": edges}

    # -----------------------------
    # Helper: fetch nodes by ids
    # -----------------------------
    def _fetch_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        if not node_ids:
            return []
        client = self._client()
        try:
            # Quick path: scroll by id not directly supported; we can search by payload filter node_id
            from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        for nid in node_ids:
            try:
                flt = Filter(must=[FieldCondition(key="node_id", match=MatchValue(value=nid))])
                res = client.scroll(collection_name=self.nodes_collection, limit=1, with_payload=True, scroll_filter=flt)
                points = res[0] if isinstance(res, tuple) else res
                if points:
                    p = points[0]
                    out.append(dict(getattr(p, "payload", {}) or {}))
            except Exception:
                continue
        return out