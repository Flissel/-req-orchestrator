# -*- coding: utf-8 -*-
from __future__ import annotations

import types
import pytest

from arch_team.memory.retrieval import Retriever


# Fake qdrant models and client used via monkeypatch in tests
class FakeDistance:
    COSINE = "COSINE"


class FakeVectorParams:
    def __init__(self, size: int, distance: str):
        self.size = size
        self.distance = distance


class FakeFilter:
    def __init__(self, must):
        self.must = must


class FakeFieldCondition:
    def __init__(self, key: str, match):
        self.key = key
        self.match = match


class FakeMatchValue:
    def __init__(self, value):
        self.value = value


class FakePoint:
    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


class FakeQdrantClient:
    def __init__(self, url=None, api_key=None):
        self.url = url
        self.api_key = api_key
        self._collections = ["requirements_v2"]
        self._search_points = []  # type: list[FakePoint]
        self.by_req_id = {}       # type: dict[str, list[FakePoint]]

    def get_collections(self):
        return types.SimpleNamespace(collections=[types.SimpleNamespace(name=n) for n in self._collections])

    def recreate_collection(self, collection_name, vectors_config):
        if collection_name not in self._collections:
            self._collections.append(collection_name)

    def search(self, collection_name, query_vector, with_payload, limit):
        # Simuliere Qdrant: bereits sortierte Reihenfolge zurückgeben (DESC by score)
        return self._search_points[: int(limit or 1)]

    def scroll(self, collection_name, limit, with_payload, scroll_filter):
        # Ignoriere Filter-Parsing, gib deterministische Liste zurück, falls vorhanden
        if self.by_req_id:
            key = next(iter(self.by_req_id))
            return self.by_req_id[key][: int(limit or 1)]
        return []


FakeModels = types.SimpleNamespace(
    VectorParams=FakeVectorParams,
    Distance=types.SimpleNamespace(COSINE=FakeDistance.COSINE),
    Filter=FakeFilter,
    FieldCondition=FakeFieldCondition,
    MatchValue=FakeMatchValue,
)


def _setup_fake_env(monkeypatch, monkeypatch_sys_module):
    # Patch lazy import to return our fakes
    monkeypatch.setattr(
        "arch_team.memory.retrieval.Retriever._lazy_import",
        lambda self: (FakeQdrantClient, FakeModels),
        raising=False,
    )
    # Patch embeddings helpers
    monkeypatch.setattr("backend_app.embeddings.get_embeddings_dim", lambda: 3, raising=False)
    monkeypatch.setattr(
        "backend_app.embeddings.build_embeddings",
        lambda texts: [[0.1, 0.2, 0.3] for _ in texts],
        raising=False,
    )
    # Stelle qdrant_client.models bereit für direkten Import in get_by_req_id
    models_mod = types.ModuleType("qdrant_client.models")
    models_mod.Filter = FakeFilter
    models_mod.FieldCondition = FakeFieldCondition
    models_mod.MatchValue = FakeMatchValue
    models_mod.VectorParams = FakeVectorParams
    models_mod.Distance = types.SimpleNamespace(COSINE=FakeDistance.COSINE)
    monkeypatch_sys_module("qdrant_client.models", models_mod)

    r = Retriever()
    return r


def test_top_k_returns_sorted(monkeypatch, monkeypatch_sys_module):
    r = _setup_fake_env(monkeypatch, monkeypatch_sys_module)
    # Bereite sortierte Punkte (absteigend nach Score) vor
    client = r._client()
    client._search_points = [
        FakePoint(id="B", score=0.95, payload={"text": "Second", "sourceFile": "s2.md"}),
        FakePoint(id="C", score=0.80, payload={"text": "Third", "sourceFile": "s3.md"}),
        FakePoint(id="A", score=0.50, payload={"text": "First", "sourceFile": "s1.md"}),
    ]

    hits = r.query_by_text("any text", top_k=3)
    assert isinstance(hits, list) and len(hits) == 3

    # Format-Mapping prüfen
    assert all(isinstance(h["id"], str) for h in hits)
    assert all("payload" in h and isinstance(h["payload"], dict) for h in hits)
    assert all("text" in h["payload"] for h in hits)
    assert all("sourceFile" in h["payload"] for h in hits)

    # Sortierung: nicht ansteigend (Qdrant liefert normalerweise bereits sortiert)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_by_id_returns_item(monkeypatch, monkeypatch_sys_module):
    r = _setup_fake_env(monkeypatch, monkeypatch_sys_module)
    client = r._client()
    # Stelle einen Treffer für eine reqId bereit
    client.by_req_id["REQ-42"] = [
        FakePoint(id="42", score=0.7, payload={"reqId": "REQ-42", "text": "Hello", "sourceFile": "src.md"})
    ]

    item = r.get_by_req_id("REQ-42")
    assert item is not None
    assert item["id"] == "42"
    assert item["payload"]["reqId"] == "REQ-42"
    assert item["payload"]["text"] == "Hello"


def test_no_results(monkeypatch, monkeypatch_sys_module):
    r = _setup_fake_env(monkeypatch, monkeypatch_sys_module)
    client = r._client()
    client._search_points = []  # keine Treffer

    hits = r.query_by_text("no results expected", top_k=5)
    assert hits == []