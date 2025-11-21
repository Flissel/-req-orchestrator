# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Union

from ..runtime.logging import get_logger
from backend.core.embeddings import build_embeddings, get_embeddings_dim

# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

logger = get_logger("pipeline.store_requirements")


def _lazy_import_qdrant():
    try:
        from qdrant_client import QdrantClient  # type: ignore
        from qdrant_client import models as qmodels  # type: ignore
        return QdrantClient, qmodels
    except Exception:
        raise RuntimeError("qdrant-client nicht installiert. Bitte 'pip install qdrant-client' ausführen.")


def _ensure_collection(client, qmodels, collection: str, dim: int) -> None:
    try:
        cols = client.get_collections()
        names = [c.name for c in (cols.collections or [])]
        if collection not in names:
            logger.info("store_requirements: create collection %s (dim=%d)", collection, dim)
            client.recreate_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
    except Exception as e:
        raise RuntimeError(f"store_requirements.ensure_collection fehlgeschlagen: {e}")


def _normalize_req_id(raw: Optional[Union[str, int]], next_index: int) -> Tuple[str, int]:
    """
    Normalisiert eine REQ-ID auf das Format REQ-###.
    - Wenn raw leer/None → generiere basierend auf next_index.
    - Wenn raw schon im Format REQ-### → nutze es direkt.
    - Wenn raw eine Zahl oder beliebiger String → extrahiere Ziffern und normiere.
    """
    if raw is None or str(raw).strip() == "":
        return f"REQ-{next_index:03d}", next_index + 1
    s = str(raw).strip()
    # Bereits korrekt?
    if s.upper().startswith("REQ-"):
        # Versuche Nummer zu extrahieren
        try:
            n = int("".join(ch for ch in s.split("-", 1)[-1] if ch.isdigit()))
            return f"REQ-{n:03d}", max(next_index, n + 1)
        except Exception:
            return s, next_index
    # Nur Zahl?
    if s.isdigit():
        n = int(s)
        return f"REQ-{n:03d}", max(next_index, n + 1)
    # Extrahiere Nummern
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        n = int(digits)
        return f"REQ-{n:03d}", max(next_index, n + 1)
    # Fallback: verwende Generator
    return f"REQ-{next_index:03d}", next_index + 1


def _coerce_text(item: Dict[str, Any]) -> str:
    """
    Wählt einen geeigneten Text zur Einbettung/Speicherung.
    Präferenz: rewrittenText|redefinedRequirement|correctedText|text|originalText
    """
    for k in ("rewrittenText", "redefinedRequirement", "correctedText", "text", "originalText", "requirementText"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # Fallback: kompaktes JSON
    try:
        import json
        return json.dumps(item, ensure_ascii=False)[:2000]
    except Exception:
        return str(item)[:2000]


def store_isolated_requirements(items: List[Dict[str, Any]], *, collection: str = "requirements_v2") -> List[str]:
    """
    Upsert normalisierte REQ-IDs in Qdrant (requirements_v2).
    - items: Liste beliebiger Objekte; es werden reqId/Id normalisiert und als payload.reqId gespeichert.
    - Vector wird aus dem gewählten Text (_coerce_text) via backend_app.embeddings.build_embeddings erzeugt.

    Rückgabe: Liste der REQ-IDs in der gleichen Reihenfolge der Eingaben.
    """
    if not isinstance(items, list) or not items:
        return []

    QdrantClient, qmodels = _lazy_import_qdrant()

    # Use centralized port configuration with legacy fallback
    qdrant_url = _ports.QDRANT_FULL_URL if _ports else (os.environ.get("QDRANT_URL") or "http://localhost:6333")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    dim = int(get_embeddings_dim())
    _ensure_collection(client, qmodels, collection=collection, dim=dim)

    # Normalisiere IDs und sammle Texte
    req_ids: List[str] = []
    texts: List[str] = []
    next_index = 1
    normalized_items: List[Dict[str, Any]] = []
    for it in items:
        it = dict(it or {})
        raw_id = it.get("id") or it.get("reqId")
        norm_id, next_index = _normalize_req_id(raw_id, next_index)
        it["reqId"] = norm_id
        req_ids.append(norm_id)
        texts.append(_coerce_text(it))
        normalized_items.append(it)

    # Embeddings bauen
    try:
        vectors = build_embeddings(texts)
        if len(vectors) != len(normalized_items):
            raise RuntimeError("Embeddings-Länge passt nicht zu Items.")
    except Exception as e:
        raise RuntimeError(f"Embeddings fehlgeschlagen: {e}")

    # Upsert
    points = []
    for i, it in enumerate(normalized_items):
        payload = dict(it)
        # optionales Minimum
        payload.setdefault("sourceType", "isolated")
        points.append(qmodels.PointStruct(id=None, vector=vectors[i], payload=payload))

    try:
        client.upsert(collection_name=collection, points=points)
        return req_ids
    except Exception as e:
        raise RuntimeError(f"Qdrant upsert fehlgeschlagen: {e}")