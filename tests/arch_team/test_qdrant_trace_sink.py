# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import os
import sys
import types
import uuid

import pytest


def _build_fake_qdrant_and_st_modules(
    embedding_dim: int = 384,
    raise_on_upsert: bool = False,
    existing_collections: list[str] | None = None,
) -> tuple[types.ModuleType, types.ModuleType, types.ModuleType]:
    """
    Erzeugt Fake-Module für:
      - qdrant_client
      - qdrant_client.models
      - sentence_transformers

    embedding_dim: bestimmt die Länge der Embedding-Vektoren, die unser Fake SentenceTransformer liefert.
    raise_on_upsert: wenn True, wirft FakeQdrantClient.upsert() eine Exception.
    existing_collections: Liste bereits existierender Collections für get_collections().
    """
    existing_collections = list(existing_collections or [])

    # ---- Fake qdrant_client.models ----
    models_mod = types.ModuleType("qdrant_client.models")

    class Distance:
        COSINE = "COSINE"

    class VectorParams:
        def __init__(self, size: int, distance):
            self.size = size
            self.distance = distance

    class PointStruct:
        def __init__(self, id, vector, payload):
            self.id = id
            self.vector = vector
            self.payload = payload

    models_mod.Distance = Distance
    models_mod.VectorParams = VectorParams
    models_mod.PointStruct = PointStruct

    # ---- Fake qdrant_client with QdrantClient ----
    qdrant_mod = types.ModuleType("qdrant_client")

    class FakeQdrantClient:
        def __init__(self, url: str | None = None, api_key: str | None = None):
            self.url = url
            self.api_key = api_key
            self._existing_collections = set(existing_collections)
            self.calls = {
                "get_collections": 0,
                "recreate_collection": [],
                "upsert": [],
            }
            self.raise_on_upsert = raise_on_upsert

        # Mimic QdrantClient.get_collections() -> Objekt mit Attribut .collections (Liste mit .name)
        def get_collections(self):
            self.calls["get_collections"] += 1

            class _Collection:
                def __init__(self, name: str):
                    self.name = name

            class _Response:
                pass

            resp = _Response()
            resp.collections = [_Collection(n) for n in sorted(self._existing_collections)]
            return resp

        def recreate_collection(self, collection_name: str, vectors_config):
            self.calls["recreate_collection"].append(
                {
                    "collection_name": collection_name,
                    "vectors_config": vectors_config,
                }
            )
            self._existing_collections.add(collection_name)

        def upsert(self, collection_name: str, points):
            self.calls["upsert"].append(
                {
                    "collection_name": collection_name,
                    "points": points,
                }
            )
            if self.raise_on_upsert:
                raise RuntimeError("fake upsert failure")
            return {"status": "ok"}

    qdrant_mod.QdrantClient = FakeQdrantClient
    # Für Importstil: from qdrant_client import models as qmodels
    qdrant_mod.models = models_mod

    # ---- Fake sentence_transformers ----
    st_mod = types.ModuleType("sentence_transformers")

    class FakeSentenceTransformer:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, texts):
            # Liefert pro Input-Text einen Vektor der Länge embedding_dim
            return [[float(i) for i in range(embedding_dim)] for _ in texts]

    st_mod.SentenceTransformer = FakeSentenceTransformer

    return qdrant_mod, models_mod, st_mod


def _reload_sink_module():
    """
    Erzwingt Neuimport von arch_team.memory.qdrant_trace_sink,
    damit die zuvor injizierten Fake-Module bei Lazy-Imports verwendet werden.
    """
    if "arch_team.memory.qdrant_trace_sink" in sys.modules:
        del sys.modules["arch_team.memory.qdrant_trace_sink"]
    importlib.invalidate_caches()
    return importlib.import_module("arch_team.memory.qdrant_trace_sink")


def _inject_fakes(monkeypatch_sys_module, embedding_dim=384, raise_on_upsert=False, existing_collections=None):
    qdrant_mod, models_mod, st_mod = _build_fake_qdrant_and_st_modules(
        embedding_dim=embedding_dim,
        raise_on_upsert=raise_on_upsert,
        existing_collections=existing_collections,
    )
    # Wichtig: Beide Pfade injizieren, da der Produktionscode beides nutzt
    monkeypatch_sys_module("qdrant_client", qdrant_mod)
    monkeypatch_sys_module("qdrant_client.models", models_mod)
    # Zusätzlich SentenceTransformer faken (Offline, keine echten Dependencies)
    monkeypatch_sys_module("sentence_transformers", st_mod)


def _assert_uuid_like(s: str):
    # Validiert, dass die zurückgegebene ID eine UUID ist
    uuid.UUID(s)


def _collect_single_upsert_call(client):
    calls = client.calls.get("upsert") or []
    assert len(calls) == 1, f"Erwartet genau 1 upsert-Call, gesehen: {len(calls)}"
    return calls[0]


def _collect_single_recreate_call(client):
    calls = client.calls.get("recreate_collection") or []
    assert len(calls) == 1, f"Erwartet genau 1 recreate_collection-Call, gesehen: {len(calls)}"
    return calls[0]


def test_save_success(monkeypatch, monkeypatch_sys_module):
    # Arrange: Fakes injizieren (mit definierter Embedding-Dimension)
    embedding_dim = 7
    _inject_fakes(monkeypatch_sys_module, embedding_dim=embedding_dim, raise_on_upsert=False, existing_collections=[])

    # ENV für URL/API-Key setzen (das Modul liest diese)
    monkeypatch.setenv("QDRANT_URL", "http://fake-host:9999")
    monkeypatch.setenv("QDRANT_API_KEY", "FAKE_API_KEY")

    mod = _reload_sink_module()
    QdrantTraceSink = mod.QdrantTraceSink

    sink = QdrantTraceSink()  # nutzt Default-Collection "arch_trace"
    pid = sink.save(
        thoughts="T",
        evidence="E",
        final="F",
        decision="D",
        task="X",
        req_id="RID-1",
        agent_type="solver",
        session_id="S-1",
        meta={"k": "v"},
    )

    # Assert: Rückgabewert ist UUID
    assert isinstance(pid, str) and pid
    _assert_uuid_like(pid)

    # Zugriff auf Fake-Client
    client = sink._qdrant
    assert client.url == "http://fake-host:9999"
    assert client.api_key == "FAKE_API_KEY"

    # ensure() sollte recreate_collection ausgelöst haben (da keine Collections existierten)
    rc = _collect_single_recreate_call(client)
    assert rc["collection_name"] == "arch_trace"
    assert getattr(rc["vectors_config"], "size", None) == embedding_dim

    up = _collect_single_upsert_call(client)
    assert up["collection_name"] == "arch_trace"
    points = up["points"]
    assert isinstance(points, list) and len(points) == 1
    p0 = points[0]
    # vector-Länge prüfen
    assert hasattr(p0, "vector") and len(getattr(p0, "vector")) == embedding_dim
    # payload-Felder prüfen
    payload = getattr(p0, "payload", {})
    assert payload["reqId"] == "RID-1"
    assert payload["agentType"] == "solver"
    assert payload["sessionId"] == "S-1"
    assert payload["task"] == "X"
    assert payload["thoughts"] == "T"
    assert payload["evidence"] == "E"
    assert payload["final"] == "F"
    assert payload["decision"] == "D"
    assert payload["meta"] == {"k": "v"}


def test_save_error_path(monkeypatch, monkeypatch_sys_module):
    # Arrange: Fakes injizieren, aber upsert soll fehlschlagen
    _inject_fakes(monkeypatch_sys_module, embedding_dim=5, raise_on_upsert=True, existing_collections=[])

    # ENV für URL/API-Key setzen (optional, hier egal)
    monkeypatch.setenv("QDRANT_URL", "http://fake:7777")
    monkeypatch.setenv("QDRANT_API_KEY", "XYZ")

    mod = _reload_sink_module()
    QdrantTraceSink = mod.QdrantTraceSink

    sink = QdrantTraceSink()
    with pytest.raises(RuntimeError) as ex:
        sink.save(thoughts="boom")
    # Der Produktionscode kapselt Upsert-Fehler in RuntimeError mit Präfix
    assert "QdrantTraceSink.save() fehlgeschlagen" in str(ex.value)


def test_save_custom_collection_from_env(monkeypatch, monkeypatch_sys_module):
    """
    Testet Custom-Collection-Name.
    Hinweis: Das Modul arch_team.memory.qdrant_trace_sink liest die Collection NICHT aus ENV,
             daher verwenden wir den ENV-Wert im Test, um den Konstruktor-Parameter zu setzen
             (exakt am Code orientiert: ENV unterstützt URL/API-Key; Collection wird via Parameter gesteuert).
    """
    _inject_fakes(monkeypatch_sys_module, embedding_dim=9, raise_on_upsert=False, existing_collections=[])

    # ENV setzen
    monkeypatch.setenv("QDRANT_URL", "http://custom-host:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "KEY-123")
    monkeypatch.setenv("QDRANT_COLLECTION", "cot_traces_test")

    mod = _reload_sink_module()
    QdrantTraceSink = mod.QdrantTraceSink

    # Collection explizit mit ENV-Wert belegen (da Modul ENV für Collection nicht nutzt)
    collection_from_env = os.environ["QDRANT_COLLECTION"]
    sink = QdrantTraceSink(collection=collection_from_env)

    pid = sink.save(thoughts="T", evidence="E", final="F", decision="D", task="X")
    assert isinstance(pid, str) and pid
    _assert_uuid_like(pid)

    client = sink._qdrant
    # Sicherstellen, dass Custom-Collection im Client-Aufruf verwendet wurde
    rc = _collect_single_recreate_call(client)
    assert rc["collection_name"] == "cot_traces_test"
    up = _collect_single_upsert_call(client)
    assert up["collection_name"] == "cot_traces_test"

    # Auch prüfen, dass ENV-URL tatsächlich an den Client ging
    assert client.url == "http://custom-host:6333"
    assert client.api_key == "KEY-123"