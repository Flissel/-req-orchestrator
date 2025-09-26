# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Union

from ..runtime.logging import get_logger

# Reuse existing helpers from the project
from backend_app.ingest import extract_texts, chunk_payloads
from backend_app.embeddings import build_embeddings, get_embeddings_dim

logger = get_logger("pipeline.upload_ingest")


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
            logger.info("upload_ingest: create collection %s (dim=%d)", collection, dim)
            client.recreate_collection(
                collection_name=collection,
                vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
            )
    except Exception as e:
        raise RuntimeError(f"upload_ingest.ensure_collection fehlgeschlagen: {e}")


def _coerce_files_or_texts(files_or_texts: List[Union[str, bytes, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Normalisiert Eingaben auf eine Liste von {filename, data, content_type}.
    Erlaubte Eingaben:
    - str: roher Text (als .txt)
    - bytes: roher Text/Bytes (als .txt)
    - dict: {filename, data, content_type?} oder {text}
    """
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(files_or_texts or []):
        if isinstance(item, str):
            out.append({"filename": f"input_{i}.txt", "data": item.encode("utf-8"), "content_type": "text/plain"})
        elif isinstance(item, bytes):
            out.append({"filename": f"input_{i}.txt", "data": item, "content_type": "text/plain"})
        elif isinstance(item, dict):
            if "text" in item:
                txt = str(item.get("text") or "")
                out.append({"filename": f"input_{i}.txt", "data": txt.encode("utf-8"), "content_type": "text/plain"})
            else:
                fn = str(item.get("filename") or f"input_{i}.txt")
                data = item.get("data") or b""
                if isinstance(data, str):
                    data = data.encode("utf-8")
                ct = str(item.get("content_type") or "")
                out.append({"filename": fn, "data": data, "content_type": ct})
        else:
            # Ignoriere unbekannte Typen
            continue
    return out


def upload_to_requirements_v2(files_or_texts: List[Union[str, bytes, Dict[str, Any]]], *, collection: str = "requirements_v2") -> List[Dict[str, Any]]:
    """
    Pipeline:
    - extract_texts pro Datei
    - chunk_payloads
    - build_embeddings
    - upsert in Qdrant (collection=requirements_v2)
    Rückgabe: einfache MEMORY-Referenzen [{id, score?, payload}]
    """
    QdrantClient, qmodels = _lazy_import_qdrant()

    import os

    qdrant_url = os.environ.get("QDRANT_URL") or "http://localhost:6333"
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    dim = int(get_embeddings_dim())
    _ensure_collection(client, qmodels, collection=collection, dim=dim)

    # 1) Extract
    normalized = _coerce_files_or_texts(files_or_texts)
    raw_records: List[Dict[str, Any]] = []
    for rec in normalized:
        try:
            parts = extract_texts(rec["filename"], rec["data"], rec.get("content_type") or "")
            raw_records.extend(parts)
        except Exception as e:
            logger.error("extract_texts failed for %s: %s", rec.get("filename"), e)

    if not raw_records:
        return []

    # 2) Chunk
    payloads = chunk_payloads(raw_records)
    texts = [p["text"] for p in payloads]
    if not texts:
        return []

    # 3) Embeddings
    try:
        vectors = build_embeddings(texts)
    except Exception as e:
        # klarer Fehler (fehlender API-Key)
        raise RuntimeError(f"Embeddings fehlgeschlagen: {e}")

    # 4) Upsert
    points = []
    mem_refs: List[Dict[str, Any]] = []
    for i, p in enumerate(payloads):
        payload = dict(p.get("payload") or {})
        payload["text"] = p.get("text") or ""
        points.append(qmodels.PointStruct(id=None, vector=vectors[i], payload=payload))

    try:
        res = client.upsert(collection_name=collection, points=points)
        # Wir haben keine IDs gesetzt; Qdrant vergibt sie. Für die Baseline liefern wir die Payloads zurück.
        for p in payloads:
            mem_refs.append({"id": None, "payload": dict(p.get("payload") or {}), "score": None})
        return mem_refs
    except Exception as e:
        raise RuntimeError(f"Qdrant upsert fehlgeschlagen: {e}")