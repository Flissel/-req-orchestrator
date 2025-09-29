# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional, Sequence, Tuple
import types
import pytest

import backend_app.vector_store as vs


class _FakeHit:
    def __init__(self, _id: Any, score: float, payload: Dict[str, Any]) -> None:
        self.id = _id
        self.score = score
        self.payload = payload


class _FakeClient:
    def __init__(self) -> None:
        self._upserts: List[Dict[str, Any]] = []
        self._collections = {"requirements_v1": {}}

    # emulate qdrant_client.get_collections minimal
    def get_collections(self):
        return types.SimpleNamespace(collections=[types.SimpleNamespace(name=n) for n in self._collections.keys()])

    # emulate qdrant_client.get_collection minimal
    def get_collection(self, collection_name: str):
        if collection_name not in self._collections:
            # Simuliere Qdrant UnexpectedResponse-Duktus: raise → ensure_collection erstellt
            raise Exception("collection not found")
        # config.params.vectors.size
        vectors = types.SimpleNamespace(size=1536, distance="COSINE")
        params = types.SimpleNamespace(vectors=vectors)
        cfg = types.SimpleNamespace(params=params)
        return types.SimpleNamespace(config=cfg)

    # emulate qdrant_client.recreate_collection
    def recreate_collection(self, collection_name: str, vectors_config: Any):
        self._collections[collection_name] = {"vectors": vectors_config}

    # emulate qdrant_client.upsert
    def upsert(self, collection_name: str, points: Any, wait: bool = True):
        for p in points:
            # p.payload existiert bei PointStruct
            self._upserts.append({"id": getattr(p, "id", None), "payload": getattr(p, "payload", {})})

    # emulate qdrant_client.search
    def search(self, collection_name: str, query_vector: Sequence[float], limit: int = 5):
        # liefere zwei Hits mit payload-Feldern
        return [
            _FakeHit("p1", 0.9, {"text": "hit-1", "sourceFile": "a.md", "chunkIndex": 0}),
            _FakeHit("p2", 0.8, {"text": "hit-2", "sourceFile": "b.md", "chunkIndex": 1}),
        ]

    # emulate qdrant_client.scroll
    def scroll(self, collection_name: str, scroll_filter: Any, with_payload: bool, with_vectors: bool, limit: int, offset: Optional[Any]):
        # einfache Seite (2 Einträge), danach kein Offset mehr
        if offset:
            return ([], None)
        rows = [
            types.SimpleNamespace(id="p1", payload={"sourceFile": "a.md", "chunkIndex": 0, "text": "A"}),
            types.SimpleNamespace(id="p2", payload={"sourceFile": "a.md", "chunkIndex": 1, "text": "B"}),
        ]
        return (rows, "end")


def _fake_get_client() -> Tuple[_FakeClient, int]:
    return _FakeClient(), 6333


def test_search_returns_payload_and_metadata(monkeypatch):
    # Patch get_qdrant_client, damit keine echte Verbindung aufgebaut wird
    monkeypatch.setattr(vs, "get_qdrant_client", _fake_get_client)
    hits = vs.search([0.0] * 1536, top_k=2, collection_name="requirements_v1")
    assert isinstance(hits, list) and len(hits) == 2
    for h in hits:
        assert "payload" in h and isinstance(h["payload"], dict)
        assert "metadata" in h and isinstance(h["metadata"], dict)
        # Der Alias muss den gleichen Inhalt haben
        assert h["metadata"] == h["payload"]


def test_upsert_accepts_metadata_and_merges(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(vs, "get_qdrant_client", lambda: (client, 6333))
    items = [
        {"id": "x1", "vector": [0.0] * 1536, "metadata": {"k": 1}, "payload": {"m": 2}},
        {"id": "x2", "vector": [0.0] * 1536, "metadata": {"only_md": True}},
        {"id": "x3", "vector": [0.0] * 1536, "payload": {"only_pl": True}},
    ]
    n = vs.upsert_points(items, collection_name="requirements_v1", dim=1536)
    assert n == 3
    # Prüfe, dass in gespeicherten Upserts beide Quellen gemerged wurden
    merged = {u["id"]: u["payload"] for u in client._upserts}
    assert merged["x1"]["k"] == 1 and merged["x1"]["m"] == 2
    assert merged["x2"]["only_md"] is True
    assert merged["x3"]["only_pl"] is True


def test_fetch_window_returns_metadata_alias(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(vs, "get_qdrant_client", lambda: (client, 6333))
    rows = vs.fetch_window_by_source_and_index("a.md", 0, 1, collection_name="requirements_v1")
    assert isinstance(rows, list) and len(rows) == 2
    # Sorted by chunkIndex ascending (already ordered here)
    assert rows[0]["payload"]["chunkIndex"] == 0
    for r in rows:
        assert "payload" in r and "metadata" in r
        assert r["metadata"] == r["payload"]