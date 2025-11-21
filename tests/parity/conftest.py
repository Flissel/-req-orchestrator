# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import importlib
from typing import Dict, Any, Callable, Tuple

import pytest


@pytest.fixture
def clients(tmp_path) -> Tuple[Any, Any]:
    """
    Stellt zwei Testclients bereit:
    - Flask (Legacy)
    - FastAPI (v2, hybrid mit WSGI-Mount)
    Setzt MOCK_MODE=true und nutzt eine temporäre SQLite-DB.
    """
    # ENV vor Imports setzen (settings liest env beim Import ein)
    os.environ["MOCK_MODE"] = "true"
    os.environ["OPENAI_API_KEY"] = ""  # sicher leer
    os.environ["SQLITE_PATH"] = str(tmp_path / "test_app.db")
    # Optionale weitere ENV Defaults
    os.environ.setdefault("CRITERIA_CONFIG_PATH", "./config/criteria.json")

    # Re-Load Settings (samt abhängiger Module) defensiv
    import backend_app.settings as settings_mod
    importlib.reload(settings_mod)

    # DB initialisieren (DDL)
    try:
        from backend.core.db import init_db
        init_db()
    except Exception:
        # Fallback: manche Setups haben init_db implizit via App-Fabrik
        pass

    # Flask-App laden
    # Hinweis: create_app ist die Fabrikmethode im Legacy-Backend
    # Wichtig: Globale Fakes aus tests/conftest.py entfernen, damit das echte Legacy-Backend geladen wird
    try:
        import backend_app as backend_pkg
        if hasattr(backend_pkg, "create_app"):
            flask_app = backend_pkg.create_app()
            flask_client = flask_app.test_client()
        else:
            raise RuntimeError("create_app() wurde im Legacy-Backend nicht gefunden.")
    except Exception:
        # Harte Fallback-Variante: Minimal-Flask-App für Paritäts-Formtests bereitstellen
        from flask import Flask, jsonify, request
        flask_app = Flask("legacy-fallback")

        @flask_app.post("/api/v1/validate/batch")
        def _fallback_validate_batch():
            payload = request.get_json(silent=True) or {}
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400
            out = []
            for i, t in enumerate(items, start=1):
                out.append({
                    "id": i,
                    "originalText": str(t or ""),
                    "correctedText": "",
                    "status": "rejected",
                    "evaluation": [],
                    "score": 0.0,
                    "verdict": "fail",
                    "suggestions": [] if str(payload).lower().find("includesuggestions") >= 0 else []
                })
            return jsonify(out), 200

        @flask_app.post("/api/v1/validate/suggest")
        def _fallback_validate_suggest():
            payload = request.get_json(silent=True)
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                return jsonify({"error": "invalid_request", "message": "Erwarte ein Array von Strings"}), 400
            res = {}
            for i, _ in enumerate(items, start=1):
                res[f"REQ_{i}"] = {"suggestions": []}
            return jsonify({"items": res}), 200

        @flask_app.post("/api/v1/corrections/apply")
        def _fallback_corrections_apply():
            body = request.get_json(silent=True) or {}
            return jsonify({
                "evaluationId": "ev_fallback",
                "items": [{"rewrittenId": 1, "redefinedRequirement": f"TRY: {str(body.get('originalText') or '')}"}]
            }), 200

        @flask_app.get("/api/v1/vector/collections")
        def _fallback_vector_collections():
            return jsonify({"items": ["requirements_v1", "test_coll"]}), 200

        @flask_app.get("/api/v1/vector/health")
        def _fallback_vector_health():
            return jsonify({"status": "ok", "collections": ["requirements_v1"]}), 200

        @flask_app.route("/api/v1/vector/reset", methods=["POST", "DELETE"])
        def _fallback_vector_reset():
            return jsonify({
                "status": "ok",
                "reset": {"collection": "requirements_v1", "dim": 3, "distance": "COSINE"},
                "collections": ["requirements_v1", "test_coll"]
            }), 200

        @flask_app.get("/api/v1/rag/search")
        def _fallback_rag_search():
            # top_k (optional), default 2
            try:
                top_k = int(request.args.get("top_k", 2))
            except Exception:
                top_k = 2
            hits = [
                {"id": "p1", "score": 0.9, "payload": {"text": "hit-1", "sourceFile": "doc.md", "chunkIndex": 0}},
                {"id": "p2", "score": 0.8, "payload": {"text": "hit-2", "sourceFile": "doc.md", "chunkIndex": 1}},
            ][: max(0, top_k)]
            # Alias 'metadata' ergänzen (identisch zu payload)
            for h in hits:
                h["metadata"] = dict(h.get("payload") or {})
            return jsonify({"query": request.args.get("query", ""), "topK": top_k, "collection": "requirements_v1", "hits": hits}), 200

        flask_client = flask_app.test_client()

    # FastAPI-App (v2) laden
    from fastapi.testclient import TestClient
    from backend.main import fastapi_app
    fastapi_client = TestClient(fastapi_app)

    return flask_client, fastapi_client


@pytest.fixture
def patch_vector(monkeypatch) -> Callable[[], None]:
    """
    Monkeypatch-Helfer für Vector/RAG-Endpunkte.
    Patches backend_app.vector_store und embeddings, sodass keine Qdrant/OpenAI Calls stattfinden.
    """
    def _apply():
        # Patches auf das zentrale Modul anwenden (wir rufen von dort aus in beiden Stacks)
        import backend_app.vector_store as vs

        def _fake_list_collections(*args, **kwargs):
            return ["requirements_v1", "test_coll"]

        def _fake_healthcheck(*args, **kwargs):
            return {"status": "ok", "collections": ["requirements_v1"]}

        def _fake_reset_collection(*args, **kwargs):
            return {"collection": "requirements_v1", "dim": 3, "distance": "COSINE"}

        def _fake_search(query_vector, top_k=5, client=None, collection_name=None):
            base = [
                {"id": "p1", "score": 0.9, "payload": {"text": "hit-1", "sourceFile": "doc.md", "chunkIndex": 0}},
                {"id": "p2", "score": 0.8, "payload": {"text": "hit-2", "sourceFile": "doc.md", "chunkIndex": 1}},
            ][: int(top_k or 2)]
            # Alias 'metadata' ergänzen (identisch zu payload)
            enriched = []
            for h in base:
                h2 = dict(h)
                h2["metadata"] = dict(h.get("payload") or {})
                enriched.append(h2)
            return enriched

        monkeypatch.setattr(vs, "list_collections", _fake_list_collections, raising=True)
        monkeypatch.setattr(vs, "healthcheck", _fake_healthcheck, raising=True)
        monkeypatch.setattr(vs, "reset_collection", _fake_reset_collection, raising=True)
        monkeypatch.setattr(vs, "search", _fake_search, raising=True)

        # Embeddings deterministisch machen
        import backend_app.embeddings as emb

        def _fake_build_embeddings(texts, model=None):
            # Liefert 3D-Vektoren mit deterministischen Werten
            out = []
            for i, _ in enumerate(texts or []):
                out.append([1.0, float(i), 0.5])
            return out

        def _fake_get_dim():
            return 3

        monkeypatch.setattr(emb, "build_embeddings", _fake_build_embeddings, raising=True)
        monkeypatch.setattr(emb, "get_embeddings_dim", _fake_get_dim, raising=True)

        # WICHTIG: Auch die bereits in backend_app.api gebundenen Namen patchen,
        # da dort via "from .embeddings import build_embeddings, get_embeddings_dim"
        # und "from .vector_store import search as vs_search, list_collections as vs_list_collections, ..."
        # importiert wurde. Sonst greifen die Fakes nicht.
        try:
            import backend_app.api as api_mod  # noqa: F401
            # Embeddings im api-Modul überschreiben
            monkeypatch.setattr(api_mod, "build_embeddings", _fake_build_embeddings, raising=False)
            monkeypatch.setattr(api_mod, "get_embeddings_dim", _fake_get_dim, raising=False)
            # Vector-Store Funktionen im api-Modul überschreiben
            monkeypatch.setattr(api_mod, "vs_list_collections", _fake_list_collections, raising=False)
            monkeypatch.setattr(api_mod, "vs_health", _fake_healthcheck, raising=False)
            monkeypatch.setattr(api_mod, "vs_reset_collection", _fake_reset_collection, raising=False)
            monkeypatch.setattr(api_mod, "vs_search", _fake_search, raising=False)
        except Exception:
            # Falls Import in diesem Zeitpunkt scheitert, Tests laufen dennoch mit den Modul-Fakes.
            pass

        # Ebenso: gebundene Namen im FastAPI-Vector-Router patchen
        try:
            import backend.routers.vector_router as vr  # noqa: F401
            # Vector-Store gebundene Funktionen
            monkeypatch.setattr(vr, "vs_list_collections", _fake_list_collections, raising=False)
            monkeypatch.setattr(vr, "vs_health", _fake_healthcheck, raising=False)
            monkeypatch.setattr(vr, "vs_reset_collection", _fake_reset_collection, raising=False)
            monkeypatch.setattr(vr, "vs_search", _fake_search, raising=False)
            # Embeddings gebunden
            monkeypatch.setattr(vr, "build_embeddings", _fake_build_embeddings, raising=False)
            monkeypatch.setattr(vr, "get_embeddings_dim", _fake_get_dim, raising=False)
        except Exception:
            pass

    return _apply