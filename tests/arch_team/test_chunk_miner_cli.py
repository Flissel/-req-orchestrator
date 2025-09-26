# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import List, Dict

import pytest


@pytest.mark.asyncio
async def test_chunk_miner_cli_counts_and_rest_stub(tmp_path, monkeypatch):
    """
    E2E-ähnlicher Test für CLI-Hook:
    - Erstellt eine einfache Textdatei.
    - Stubbt OpenAIAdapter.create auf determinantes JSON.
    - Stubbt ReqWorkerAgent.send_to_frontend zum Sammeln der DTOs.
    - Ruft run_chunk_miner_cli() mit --neighbor-evidence=False Verhalten.
    Erwartung:
      - count == len(captured) >= 1
      - Kein echter REST-Call (REQ_WORKER_ENDPOINT nicht gesetzt)
    """
    # Datei vorbereiten
    p = tmp_path / "spec.txt"
    p.write_text("The system shall support SSO login. Response time under 200ms.", encoding="utf-8")

    # Stubs importieren/setzen
    import arch_team.agents.chunk_miner as cm
    captured: List[Dict] = []

    def fake_create(self, messages, temperature=None, model=None, tools=None, **kwargs):
        # Liefere ein einzelnes Requirement-Item zurück
        return '{"items":[{"req_id":"", "title":"SSO support", "tag":"security"}]}'

    def fake_send(self, dto):
        captured.append(dto)

    monkeypatch.setattr(cm.OpenAIAdapter, "create", fake_create, raising=True)
    monkeypatch.setattr(cm.ReqWorkerAgent, "send_to_frontend", fake_send, raising=True)

    # CLI-Helfer importieren und ausführen
    from arch_team.main import run_chunk_miner_cli

    count = run_chunk_miner_cli(paths=[str(p)], model="gpt-4o-mini", neighbor_refs=False)

    assert count == len(captured)
    assert count >= 1
    # evidence_refs müssen vorhanden sein
    assert isinstance(captured[0].get("evidence_refs"), list) and len(captured[0]["evidence_refs"]) >= 1


@pytest.mark.asyncio
async def test_chunk_miner_cli_neighbor_evidence(tmp_path, monkeypatch):
    """
    Testet Nachbarschaftskontext (chunkIndex±1) bei aktivierter Option.
    - Senkt die Chunk-Parameter via settings (Min/Max/Overlap), um mehrere Chunks zu erzwingen.
    - Prüft, dass mindestens ein DTO mehr als 1 evidence_ref hat.
    """
    # Langer Text, damit mehrere Chunks entstehen (mit kleinen max_tokens)
    long_text = (
        "The system shall support SSO and OAuth. The API shall rate-limit requests. "
        "Users shall be able to reset passwords securely. The system shall log admin actions. "
        "Ensure data encryption at rest and in transit. Performance target under 200ms p95."
    )
    p = tmp_path / "spec_long.txt"
    p.write_text(long_text, encoding="utf-8")

    # Settings für kleines Chunking
    import backend_app.ingest as ingest
    # Falls settings keine Attribute hat, wird AttributeError geworfen; dann überspringen wir nicht, sondern setzen minimal:
    if hasattr(ingest, "settings"):
        setattr(ingest.settings, "CHUNK_TOKENS_MAX", 8)
        setattr(ingest.settings, "CHUNK_TOKENS_MIN", 1)
        setattr(ingest.settings, "CHUNK_OVERLAP_TOKENS", 1)

    import arch_team.agents.chunk_miner as cm
    captured: List[Dict] = []

    def fake_create(self, messages, temperature=None, model=None, tools=None, **kwargs):
        # Liefere Item pro Chunk, damit wir mehrere DTOs erhalten
        return '{"items":[{"req_id":"", "title":"Req from chunk", "tag":"functional"}]}'

    def fake_send(self, dto):
        captured.append(dto)

    monkeypatch.setattr(cm.OpenAIAdapter, "create", fake_create, raising=True)
    monkeypatch.setattr(cm.ReqWorkerAgent, "send_to_frontend", fake_send, raising=True)

    from arch_team.main import run_chunk_miner_cli

    count = run_chunk_miner_cli(paths=[str(p)], model=None, neighbor_refs=True)

    # Mindestens ein DTO muss existieren
    assert count == len(captured)
    assert count >= 1

    # Mindestens ein DTO sollte mehr als 1 evidence_ref erhalten haben (Nachbarschaft)
    assert any(isinstance(dto.get("evidence_refs"), list) and len(dto["evidence_refs"]) > 1 for dto in captured)