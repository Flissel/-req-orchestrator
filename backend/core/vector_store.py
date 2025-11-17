# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    Range,
    MatchValue,
)

from . import settings

# OpenAI text-embedding-3-small dimensionality (as of 2025-08)
DEFAULT_EMBEDDING_DIM: int = 1536


def _build_url_with_port(base_url: str, port: int) -> str:
    """
    Baut eine Qdrant-URL inkl. Port. Akzeptiert Werte wie:
    - http://localhost
    - http://127.0.0.1
    Ergänzt :port, falls nicht vorhanden.
    """
    base = str(base_url or "http://localhost").rstrip("/")
    if ":" in base.split("://", 1)[-1]:
        # Port vermutlich bereits gesetzt
        return base
    return f"{base}:{port}"


def get_qdrant_client(timeout: float = 5.0) -> Tuple[QdrantClient, int]:
    """
    Liefert einen Qdrant-Client. Versucht Fallback auf Port 6401, falls 6333 nicht erreichbar.
    Gibt (client, effektiver_port) zurück.
    Hinweis: 6334 ist gRPC, HTTP bleibt 6333. Alternativer HTTP-Fallback kann 6401 sein.
    """
    base_url = getattr(settings, "QDRANT_URL", "http://localhost")
    port = int(getattr(settings, "QDRANT_PORT", 6333))
    # Primär
    try:
        url = _build_url_with_port(base_url, port)
        client = QdrantClient(url=url, timeout=timeout)
        # Health-Check
        _ = client.get_collections()
        return client, port
    except Exception:
        pass

    # Fallback auf 6401, falls primärer Port 6333 war
    if port == 6333:
        try:
            url = _build_url_with_port(base_url, 6401)
            client = QdrantClient(url=url, timeout=timeout)
            _ = client.get_collections()
            return client, 6401
        except Exception:
            pass

    # Letzte Option: Fehler auf Primär-Port durchreichen
    url = _build_url_with_port(base_url, port)
    client = QdrantClient(url=url, timeout=timeout)
    return client, port


def ensure_collection(
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
    dim: int = DEFAULT_EMBEDDING_DIM,
    distance: Distance = Distance.COSINE,
) -> None:
    """
    Stellt sicher, dass die Collection existiert. Falls nicht, wird sie erstellt.
    """
    coll = collection_name or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    cli = client or get_qdrant_client()[0]
    try:
        info = cli.get_collection(collection_name=coll)
        # Optional: Vektorparam prüfen (dim/distance)
        vp = getattr(info.config, "params", None)
        if vp and hasattr(vp, "vectors") and vp.vectors:
            # vectors kann VectorParams oder Mapping sein
            try:
                configured_dim = int(getattr(vp.vectors, "size", dim))
                configured_dist = getattr(vp.vectors, "distance", distance)
                if configured_dim != dim or configured_dist != distance:
                    # Abweichende Konfiguration – wir belassen sie (kein destructive change).
                    pass
            except Exception:
                pass
        return
    except UnexpectedResponse:
        # Collection fehlt → erstellen
        cli.recreate_collection(
            collection_name=coll,
            vectors_config=VectorParams(size=dim, distance=distance),
        )


def upsert_points(
    items: Sequence[Dict[str, Any]],
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
    dim: int = DEFAULT_EMBEDDING_DIM,
) -> int:
    """
    Upsert von Punkten in die Collection.

    items: Liste von Dicts mit Feldern:
      - vector: List[float]  # Embedding-Vektor, Länge = dim
      - payload: Dict[str, Any]  # Metadaten, z. B. {sourceFile, chunkIndex, text, sha1, createdAt}
      - id: Optional[str|int]    # optional, ansonsten wird UUID4 vergeben

    Returns: Anzahl upserted Punkte
    """
    coll = collection_name or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    cli = client or get_qdrant_client()[0]
    ensure_collection(cli, coll, dim=dim)

    points: List[PointStruct] = []
    now = int(time.time())
    for it in items:
        vec = it.get("vector") or it.get("embedding")
        if not isinstance(vec, (list, tuple)) or len(vec) != dim:
            # invalid vector, skip
            continue
        pid = it.get("id")
        if pid is None:
            pid = uuid.uuid4().hex
        # Vereinheitlichung: 'payload' und 'metadata' unterstützen; zusammenführen
        _pl = it.get("payload") if isinstance(it.get("payload"), dict) else None
        _md = it.get("metadata") if isinstance(it.get("metadata"), dict) else None
        payload: Dict[str, Any] = {}
        if _pl:
            payload.update(_pl)
        if _md:
            payload.update(_md)
        if "createdAt" not in payload:
            payload["createdAt"] = now
        points.append(PointStruct(id=pid, vector=list(vec), payload=payload))

    if not points:
        return 0

    cli.upsert(collection_name=coll, points=points, wait=True)
    return len(points)


def search(
    query_vector: Sequence[float],
    top_k: int = 5,
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Führt eine Vektor-Suche durch und liefert Treffer als Liste von Dicts:
      { "id": "...", "score": float, "payload": {...} }
    """
    coll = collection_name or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    cli = client or get_qdrant_client()[0]
    ensure_collection(cli, coll, dim=len(query_vector) if query_vector else DEFAULT_EMBEDDING_DIM)
    results = cli.search(collection_name=coll, query_vector=list(query_vector), limit=int(top_k or 5))
    out: List[Dict[str, Any]] = []
    for r in results:
        _pl = getattr(r, "payload", {}) or {}
        out.append({
            "id": getattr(r, "id", None),
            "score": getattr(r, "score", None),
            "payload": _pl,
            # Alias für vereinheitlichte Schlüssel-Namensgebung
            "metadata": dict(_pl),
        })
    return out


def list_collections(client: Optional[QdrantClient] = None) -> List[str]:
    """
    Liefert die verfügbaren Collections.
    """
    cli = client or get_qdrant_client()[0]
    data = cli.get_collections()
    cols = getattr(data, "collections", []) or []
    return [c.name for c in cols]


def healthcheck(client: Optional[QdrantClient] = None) -> Dict[str, Any]:
    """
    Gibt Statusinformationen aus Qdrant zurück.
    """
    cli = client or get_qdrant_client()[0]
    try:
        cols = list_collections(cli)
        return {"status": "ok", "collections": cols}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def reset_collection(
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
    dim: int = DEFAULT_EMBEDDING_DIM,
    distance: Distance = Distance.COSINE,
) -> Dict[str, Any]:
    """
    Droppt (recreate) die Qdrant-Collection und legt sie mit gegebener Konfiguration neu an.
    Achtung: Alle Punkte werden gelöscht.
    """
    coll = collection_name or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    cli = client or get_qdrant_client()[0]
    cli.recreate_collection(
        collection_name=coll,
        vectors_config=VectorParams(size=int(dim), distance=distance),
    )
    # Versuche Distanznamen aus der Collection zu lesen (best effort)
    try:
        info = cli.get_collection(collection_name=coll)
        _vp = getattr(getattr(info, "config", None), "params", None)
        _vec = getattr(_vp, "vectors", None)
        _dist = getattr(_vec, "distance", None)
        dist_name = getattr(_dist, "name", str(distance))
    except Exception:
        dist_name = getattr(distance, "name", str(distance))
    return {"collection": coll, "dim": int(dim), "distance": dist_name}


def fetch_window_by_source_and_index(
    source_file: str,
    index_min: int,
    index_max: int,
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
    limit: int = 256,
) -> List[Dict[str, Any]]:
    """
    Holt alle Chunks eines Fensters (chunkIndex ∈ [index_min, index_max]) aus demselben sourceFile
    via Qdrant-Scroll mit Payload-Filter. Liefert Liste von Dicts {id, payload}.
    """
    coll = collection_name or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")
    cli = client or get_qdrant_client()[0]

    flt = Filter(
        must=[
            FieldCondition(key="sourceFile", match=MatchValue(value=str(source_file))),
            FieldCondition(key="chunkIndex", range=Range(gte=int(index_min), lte=int(index_max))),
        ]
    )

    out: List[Dict[str, Any]] = []
    next_offset = None
    # Scroll in Seiten, bis keine Punkte mehr vorhanden
    while True:
        res, next_offset = cli.scroll(
            collection_name=coll,
            scroll_filter=flt,
            with_payload=True,
            with_vectors=False,
            limit=limit,
            offset=next_offset,
        )
        for r in res:
            _pl = getattr(r, "payload", {}) or {}
            out.append({
                "id": getattr(r, "id", None),
                "payload": _pl,
                # Alias für vereinheitlichte Schlüssel-Namensgebung
                "metadata": dict(_pl),
            })
        if not next_offset:
            break

    # Nach chunkIndex sortieren (falls vorhanden)
    def _idx(p):
        try:
            return int((p.get("payload") or {}).get("chunkIndex", 0))
        except Exception:
            return 0

    out.sort(key=_idx)
    return out