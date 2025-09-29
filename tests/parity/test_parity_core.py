# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _keys_of(d: Dict[str, Any]) -> set:
    return set(d.keys())


def _assert_result_item_shape(item: Dict[str, Any], include_suggestions: bool) -> None:
    base_keys = {"id", "originalText", "correctedText", "status", "evaluation", "score", "verdict"}
    assert base_keys.issubset(_keys_of(item))
    assert isinstance(item["evaluation"], list)
    if include_suggestions:
        assert "suggestions" in item
        assert isinstance(item.get("suggestions", []), list)


def _assert_suggest_response_shape(data: Dict[str, Any]) -> None:
    assert "items" in data and isinstance(data["items"], dict)
    # mind. REQ_1 vorhanden
    # Form: { "REQ_1": { "suggestions": [...] } }
    for _, v in data["items"].items():
        assert isinstance(v, dict)
        assert "suggestions" in v
        assert isinstance(v["suggestions"], list)


def test_validate_batch_parity(clients) -> None:
    flask_client, fastapi_client = clients
    payload = {
        "items": [
            "Das System soll eine Antwortzeit von ≤200 ms (p95) bei 30 RPS einhalten.",
            "The API shall return JSON.",
        ],
        "includeSuggestions": True,
    }

    r_fast = fastapi_client.post("/api/v1/validate/batch", json=payload)
    r_legacy = flask_client.post("/api/v1/validate/batch", json=payload)

    assert r_fast.status_code == 200
    assert r_legacy.status_code == 200

    j_fast = r_fast.json()
    j_legacy = r_legacy.get_json()

    assert isinstance(j_fast, list)
    assert isinstance(j_legacy, list)
    assert len(j_fast) == len(j_legacy) == len(payload["items"])

    # Shape-Check pro Item
    for it in j_fast:
        _assert_result_item_shape(it, include_suggestions=True)
    for it in j_legacy:
        _assert_result_item_shape(it, include_suggestions=True)


def test_validate_suggest_parity(clients) -> None:
    flask_client, fastapi_client = clients
    payload = ["The API shall return JSON."]

    r_fast = fastapi_client.post("/api/v1/validate/suggest", json=payload)
    r_legacy = flask_client.post("/api/v1/validate/suggest", json=payload)

    assert r_fast.status_code == 200
    assert r_legacy.status_code == 200

    j_fast = r_fast.json()
    j_legacy = r_legacy.get_json()

    _assert_suggest_response_shape(j_fast)
    _assert_suggest_response_shape(j_legacy)


def test_corrections_apply_parity(clients) -> None:
    flask_client, fastapi_client = clients

    payload = {
        "originalText": "The API shall return JSON.",
        "selectedSuggestions": [
            {
                "correction": "The API shall return {\"status\":\"ok\"} as JSON object.",
                "acceptance_criteria": ["Given...", "When...", "Then..."],
                "metrics": [],
            }
        ],
        "mode": "merge",
        "context": {},
    }

    r_fast = fastapi_client.post("/api/v1/corrections/apply", json=payload)
    r_legacy = flask_client.post("/api/v1/corrections/apply", json=payload)

    assert r_fast.status_code == 200
    assert r_legacy.status_code == 200

    j_fast = r_fast.json()
    j_legacy = r_legacy.get_json()

    # Shape-Checks
    for obj in (j_fast, j_legacy):
        assert "evaluationId" in obj and isinstance(obj["evaluationId"], str)
        assert "items" in obj and isinstance(obj["items"], list)
        if obj["items"]:
            assert "redefinedRequirement" in obj["items"][0]


def test_vector_and_rag_parity(patch_vector, clients) -> None:
    # Verhindere echte Qdrant/OpenAI-Kommunikation
    patch_vector()

    flask_client, fastapi_client = clients

    # Collections
    r_fast = fastapi_client.get("/api/v1/vector/collections")
    r_legacy = flask_client.get("/api/v1/vector/collections")
    assert r_fast.status_code == 200 and r_legacy.status_code == 200
    assert "items" in r_fast.json() and "items" in r_legacy.get_json()

    # Health
    r_fast = fastapi_client.get("/api/v1/vector/health")
    r_legacy = flask_client.get("/api/v1/vector/health")
    assert r_fast.status_code == 200 and r_legacy.status_code == 200
    assert r_fast.json().get("status") == "ok"
    assert r_legacy.get_json().get("status") in ("ok", "error")  # Legacy kann 200 mit status:error liefern

    # Reset (POST)
    r_fast = fastapi_client.post("/api/v1/vector/reset", json={})
    r_legacy = flask_client.post("/api/v1/vector/reset", json={})
    assert r_fast.status_code == 200 and r_legacy.status_code == 200
    jf = r_fast.json()
    jl = r_legacy.get_json()
    for obj in (jf, jl):
        assert "status" in obj and "reset" in obj and "collections" in obj

    # RAG Search
    r_fast = fastapi_client.get("/api/v1/rag/search?query=health%20endpoint&top_k=2")
    r_legacy = flask_client.get("/api/v1/rag/search?query=health%20endpoint&top_k=2")
    assert r_fast.status_code == 200 and r_legacy.status_code == 200
    fast_hits = r_fast.json().get("hits", [])
    leg_hits = r_legacy.get_json().get("hits", [])
    assert isinstance(fast_hits, list) and isinstance(leg_hits, list)
    assert len(fast_hits) == len(leg_hits) == 2
    for h in fast_hits + leg_hits:
        assert "payload" in h and "score" in h