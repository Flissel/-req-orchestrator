# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import pytest


# -----------------------------------------------------------------------------
# Fakes für qdrant_client (+ models) mit globalem In-Memory-Store.
# - create_collection/recreate_collection: no-op (merkt Namen)
# - upsert: Punkte in STORE persistieren (id, vector, payload)
# - search: deterministische Substring/Token-Score und sortierte Treffer
# -----------------------------------------------------------------------------

def _build_fake_qdrant_modules(shared_dim: int = 8):
    """
    Liefert (qdrant_client_mod, qdrant_client.models_mod) mit gemeinsamem STORE.
    """
    STORE: Dict[str, Any] = {
        "collections": set(),                 # set[str]
        "points": {},                         # dict[collection_name, list[Point]]
        "next_id": 1,
        "force_no_hits": False,
        "dim": shared_dim,
    }

    # ---- models ----
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

    # Für get_by_req_id-Importpfad (Filter, FieldCondition, MatchValue) minimal bereitstellen
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

    models_mod.Distance = Distance
    models_mod.VectorParams = VectorParams
    models_mod.PointStruct = PointStruct
    models_mod.Filter = Filter
    models_mod.FieldCondition = FieldCondition
    models_mod.MatchValue = MatchValue

    # ---- qdrant_client ----
    qdrant_mod = types.ModuleType("qdrant_client")

    class _FakePoint:
        def __init__(self, id: str, score: float, payload: dict):
            self.id = id
            self.score = score
            self.payload = payload

    def _tokenize(s: str) -> List[str]:
        return [t for t in "".join([c.lower() if c.isalnum() else " " for c in str(s)]).split() if t]

    def _score(query: str, text: str) -> float:
        # Einfache deterministische Ähnlichkeit: Anzahl gemeinsamer Tokens
        q = set(_tokenize(query))
        d = set(_tokenize(text))
        if not q or not d:
            return 0.0
        return float(len(q & d))

    class QdrantClient:
        def __init__(self, url: str | None = None, api_key: str | None = None):
            self.url = url
            self.api_key = api_key

        def get_collections(self):
            class _Collection:
                def __init__(self, name: str):
                    self.name = name

            class _Response:
                pass

            resp = _Response()
            resp.collections = [_Collection(n) for n in sorted(STORE["collections"])]
            return resp

        def recreate_collection(self, collection_name: str, vectors_config):
            # Nur registrieren (dim wird in vectors_config.size erwartet)
            STORE["collections"].add(collection_name)
            STORE["points"].setdefault(collection_name, [])

        def upsert(self, collection_name: str, points):
            STORE["collections"].add(collection_name)
            STORE["points"].setdefault(collection_name, [])
            for p in list(points or []):
                pid = p.id
                if pid is None:
                    pid = str(STORE["next_id"])
                    STORE["next_id"] += 1
                payload = dict(getattr(p, "payload", {}) or {})
                vec = list(getattr(p, "vector", []) or [])
                # Persistiere
                STORE["points"][collection_name].append({"id": str(pid), "vector": vec, "payload": payload})
            return {"status": "ok"}

        def search(self, collection_name: str, query_vector, with_payload: bool, limit: int):
            if STORE.get("force_no_hits"):
                return []
            arr = []
            for rec in STORE["points"].get(collection_name, []):
                txt = str(rec.get("payload", {}).get("text", "") or "")
                sc = _score(" ".join([str(x) for x in query_vector]) if isinstance(query_vector, list) else "", txt)
                # Alternativ: Score anhand Query-String (realistischer) – client kennt Query-Vector, nicht Query-Text.
                # Für deterministische Tests verbessern: Wenn Score=0, versuche einfachen Textscore anhand 'mfa'/'auth'
                if sc == 0 and txt:
                    sc = _score("mfa authentication auth security logs", txt)
                arr.append(_FakePoint(id=rec["id"], score=sc, payload=rec["payload"]))
            arr.sort(key=lambda p: p.score, reverse=True)
            k = max(1, int(limit or 1))
            return arr[:k]

        def scroll(self, collection_name: str, limit: int, with_payload: bool, scroll_filter):
            # Minimal: keine echte Filterauswertung – leer zurück (reicht für E2E in diesem Test)
            return []

    # API auf Modul legen
    qdrant_mod.QdrantClient = QdrantClient
    qdrant_mod.models = models_mod

    # Hilfsfunktionen, um STORE im Test zu lesen/konfigurieren
    def get_store():
        return STORE

    def set_force_no_hits(v: bool):
        STORE["force_no_hits"] = bool(v)

    qdrant_mod.get_store = get_store  # type: ignore[attr-defined]
    qdrant_mod.set_force_no_hits = set_force_no_hits  # type: ignore[attr-defined]

    return qdrant_mod, models_mod


def _inject_fake_qdrant(monkeypatch_sys_module, dim: int = 8):
    qdrant_mod, models_mod = _build_fake_qdrant_modules(shared_dim=dim)
    monkeypatch_sys_module("qdrant_client", qdrant_mod)
    monkeypatch_sys_module("qdrant_client.models", models_mod)
    return qdrant_mod


# -----------------------------------------------------------------------------
# Deterministische Fake-Embeddings
# -----------------------------------------------------------------------------

def _fake_get_embeddings_dim_factory(dim: int):
    return lambda: dim


def _fake_build_embeddings_factory(dim: int):
    def _build(texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts or []:
            base = sum(ord(c) for c in str(t))
            vec = [float(((base + 31 * i) % 97) / 97.0) for i in range(dim)]
            out.append(vec)
        return out
    return _build


def _inject_fake_backend_deps(monkeypatch_sys_module, dim: int = 8):
    """
    Injiziert Fakes für backend_app.api und backend_app.embeddings, um Importkette
    backend_app.ingest -> backend_app/__init__ -> backend_app.api -> backend_app.embeddings
    zu entkoppeln. Dadurch werden keine realen Abhängigkeiten (Flask, requests, tenacity) geladen.

    Wichtig:
    - Vor dem Import/Reload von arch_team.pipeline.upload_ingest aufrufen.
    - Zusätzlich wird das Elternpaket 'backend_app' mit realem __path__ eingetragen, damit
      reale Submodule wie backend_app.ingest weiterhin normal importiert werden können,
      ohne dass backend_app/__init__.py ausgeführt werden muss.
    """
    # Elternpaket 'backend_app' als Paket mit realem Pfad anlegen, damit Submodule (ingest) ladbar bleiben
    root_dir = Path(__file__).resolve().parents[2]
    backend_pkg_path = str((root_dir / "backend_app").resolve())
    pkg_mod = types.ModuleType("backend_app")
    pkg_mod.__path__ = [backend_pkg_path]  # type: ignore[attr-defined]
    # Explizit als Paket im sys.modules registrieren (mit echtem Suchpfad)
    monkeypatch_sys_module("backend_app", pkg_mod)

    # Fake-Embeddings-Modul mit deterministischen Funktionen
    emb_mod = types.ModuleType("backend_app.embeddings")
    emb_mod.get_embeddings_dim = _fake_get_embeddings_dim_factory(dim)
    emb_mod.build_embeddings = _fake_build_embeddings_factory(dim)

    # Minimal-Dummy für backend_app.api, damit "from .api import api_bp" erfolgreich ist
    api_mod = types.ModuleType("backend_app.api")
    api_mod.api_bp = None

    # In sys.modules injizieren; durch das zuvor registrierte Elternpaket bleibt ingest importierbar
    monkeypatch_sys_module("backend_app.embeddings", emb_mod)
    monkeypatch_sys_module("backend_app.api", api_mod)

    # Optional: Referenzen zurückgeben für mögliche Assertions/Inspektionen
    return {"embeddings": emb_mod, "api": api_mod}
# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def _reload_module(mod_name: str):
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    importlib.invalidate_caches()
    return importlib.import_module(mod_name)


def _patch_module_embeddings(monkeypatch, module, dim: int):
    # Wichtig: Produktionsmodule importieren build_embeddings/get_embeddings_dim per 'from ... import ...'
    # Deshalb müssen wir die Symbole in den ZIELMODULEN patchen.
    monkeypatch.setattr(module, "get_embeddings_dim", _fake_get_embeddings_dim_factory(dim), raising=False)
    monkeypatch.setattr(module, "build_embeddings", _fake_build_embeddings_factory(dim), raising=False)


def _assert_ingested_points(qdrant_mod, collection: str, min_expected: int = 1):
    store = qdrant_mod.get_store()  # type: ignore[attr-defined]
    pts = store["points"].get(collection, [])
    assert isinstance(pts, list) and len(pts) >= min_expected, f"Keine Punkte in Collection {collection} gefunden"


def _assert_retrieval_shape(hits):
    assert isinstance(hits, list)
    if not hits:
        return
    h0 = hits[0]
    assert "id" in h0 and isinstance(h0["id"], str)
    assert "payload" in h0 and isinstance(h0["payload"], dict)
    assert "text" in h0["payload"]
    assert "sourceFile" in h0["payload"]


def test_e2e_dummy_upload_ingest_retrieve_cot(monkeypatch, monkeypatch_sys_module):
    # Arrange: Fakes vor dem Import der Produktionsmodule injizieren
    dim = 8
    qdrant_mod = _inject_fake_qdrant(monkeypatch_sys_module, dim=dim)

    # Zusätzlich: Fakes für backend_app.api und backend_app.embeddings injizieren,
    # um die Importkette backend_app.ingest -> backend_app/__init__ -> backend_app.api -> backend_app.embeddings
    # zu entkoppeln und Offline-Dependencies (tenacity/requests/Flask) zu vermeiden.
    _inject_fake_backend_deps(monkeypatch_sys_module, dim=dim)

    # Produktionsmodule neu laden (Sicherheit bzgl. Lazy-Imports und symbolischer Importe)
    upload_ingest = _reload_module("arch_team.pipeline.upload_ingest")
    retrieval_mod = _reload_module("arch_team.memory.retrieval")
    cot_post = _reload_module("arch_team.runtime.cot_postprocessor")

    # Embeddings-Funktionen deterministisch faken (in den Zielmodulen!)
    _patch_module_embeddings(monkeypatch, upload_ingest, dim)
    _patch_module_embeddings(monkeypatch, retrieval_mod, dim)

    # Dummy-Dokumente
    docs = [
        "Auth must use MFA",
        "Logs retained for 30 days",
        "Passwords must be at least 12 characters",
    ]

    # Act: Upload/Ingest in Fake-Qdrant
    mem_refs = upload_ingest.upload_to_requirements_v2(docs, collection="requirements_v2")

    # Assert: Ingest hat Punkte abgelegt
    assert isinstance(mem_refs, list) and len(mem_refs) >= 1
    _assert_ingested_points(qdrant_mod, "requirements_v2", min_expected=1)

    # Act: Retrieval (Top-k=3) – Query passend zu 'MFA'
    r = retrieval_mod.Retriever(collection="requirements_v2")
    hits = r.query_by_text("mfa authentication", top_k=3)

    # Assert: Treffer vorhanden; Struktur prüfen
    assert isinstance(hits, list) and len(hits) >= 1
    _assert_retrieval_shape(hits)

    # CoT-Postprozess: FINAL_ANSWER extrahieren und UI-Privacy prüfen
    cot_text = """THOUGHTS:
Internal chain-of-thought, do not leak.

FINAL_ANSWER: REQ-001: Use MFA [tag: security]
EVIDENCE:
- source: policy.md
CRITIQUE:
- shorten
"""
    blocks = cot_post.extract_blocks(cot_text)
    ui = cot_post.ui_payload(blocks)

    assert "REQ-001: Use MFA [tag: security]" in ui
    # Sicherstellen, dass keine internen Inhalte in der UI-Payload auftauchen
    assert "THOUGHTS" not in ui and "CRITIQUE" not in ui and "EVIDENCE" not in ui


def test_e2e_no_hits_path(monkeypatch, monkeypatch_sys_module):
    # Arrange: Fakes injizieren; Suche soll leere Liste liefern
    dim = 8
    qdrant_mod = _inject_fake_qdrant(monkeypatch_sys_module, dim=dim)

    # Zusätzlich: Fakes für backend_app.api und backend_app.embeddings injizieren,
    # damit beim Import von upload_ingest keine realen Abhängigkeiten geladen werden.
    _inject_fake_backend_deps(monkeypatch_sys_module, dim=dim)

    # Module laden und Embeddings in Zielmodulen patchen
    upload_ingest = _reload_module("arch_team.pipeline.upload_ingest")
    retrieval_mod = _reload_module("arch_team.memory.retrieval")
    cot_post = _reload_module("arch_team.runtime.cot_postprocessor")

    _patch_module_embeddings(monkeypatch, upload_ingest, dim)
    _patch_module_embeddings(monkeypatch, retrieval_mod, dim)

    # Ingest minimal (damit Pfad robust ist, obwohl force_no_hits aktiv ist)
    _ = upload_ingest.upload_to_requirements_v2(["irrelevant document"], collection="requirements_v2")

    # Suche global deaktivieren
    qdrant_mod.set_force_no_hits(True)  # type: ignore[attr-defined]

    # Act: Retrieval-Query – erwartet: keine Treffer, keine Exception
    r = retrieval_mod.Retriever(collection="requirements_v2")
    hits = r.query_by_text("query that should not match", top_k=3)

    # Assert: leerer Pfad
    assert hits == []

    # CoT-Postprozessor: Minimaltext mit FINAL_ANSWER bleibt robust
    cot_text = "FINAL_ANSWER: NO MATCH"
    blocks = cot_post.extract_blocks(cot_text)
    ui = cot_post.ui_payload(blocks)
    assert ui.strip() == "NO MATCH"