# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
import sys
import pytest

pytest_asyncio = pytest.importorskip("pytest_asyncio")


@pytest.mark.asyncio
async def test_search_requirements_hits(monkeypatch_sys_module, fake_retrieval_module_hits):
    # Injiziere Fake-Retriever vor Import des Tools
    monkeypatch_sys_module("arch_team.memory.retrieval", fake_retrieval_module_hits)
    mod = importlib.import_module("arch_team.autogen_tools.requirements_rag")

    out = await mod.search_requirements("security logging", top_k=3)

    # Erwartet Markdown-Tabelle mit Header
    assert "| id | snippet | source |" in out
    assert "REQ-101" in out or "REQ-202" in out
    # Snippet-Text (normalisiert) sollte auftauchen
    assert "requirement text" in out


@pytest.mark.asyncio
async def test_search_requirements_no_hits(monkeypatch_sys_module, fake_retrieval_module_nohits):
    monkeypatch_sys_module("arch_team.memory.retrieval", fake_retrieval_module_nohits)
    mod = importlib.import_module("arch_team.autogen_tools.requirements_rag")

    out = await mod.search_requirements("nonexistent", top_k=2)
    assert "RAG not configured or no hits for" in out


@pytest.mark.asyncio
async def test_search_requirements_error(monkeypatch_sys_module, fake_retrieval_module_raises):
    monkeypatch_sys_module("arch_team.memory.retrieval", fake_retrieval_module_raises)
    mod = importlib.import_module("arch_team.autogen_tools.requirements_rag")

    out = await mod.search_requirements("boom", top_k=2)
    assert out.startswith("RAG not configured") or "error" in out.lower()