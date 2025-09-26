# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import types
import pytest


@pytest.fixture
def monkeypatch_sys_module(monkeypatch):
    """
    Injiziert ein Fake-Modul in sys.modules unter einem vollqualifizierten Modulnamen.
    Beispiel:
        monkeypatch_sys_module("arch_team.memory.retrieval", fake_module)
    """
    def _inject(module_name: str, fake_module: types.ModuleType | object):
        # SimpleNamespace auf Modul hüllen
        if isinstance(fake_module, types.SimpleNamespace):
            mod = types.ModuleType(module_name)
            for k, v in fake_module.__dict__.items():
                setattr(mod, k, v)
        elif isinstance(fake_module, types.ModuleType):
            mod = fake_module
        else:
            # Beliebiges Objekt in Modul hüllen
            mod = types.ModuleType(module_name)
            for k in dir(fake_module):
                if not k.startswith("_"):
                    setattr(mod, k, getattr(fake_module, k))

        # Modul registrieren
        monkeypatch.setitem(sys.modules, module_name, mod)

        # Sicherstellen, dass Elternpaket existiert (für manche Importpfade relevant)
        if "." in module_name:
            parent = module_name.rsplit(".", 1)[0]
            if parent not in sys.modules:
                pkg = types.ModuleType(parent)
                # Markiere als Paket
                pkg.__path__ = []  # type: ignore[attr-defined]
                monkeypatch.setitem(sys.modules, parent, pkg)

        return mod

    return _inject


def _make_fake_retrieval_module(mode: str = "hits") -> types.SimpleNamespace:
    """
    Baut ein Fake-Modul für arch_team.memory.retrieval mit Klasse Retriever und Methode query_by_text.

    Modi:
      - "hits":    Liefert 2-3 deterministische Treffer
      - "nohits":  Liefert leere Liste
      - "raises":  Wirft RuntimeError bei query_by_text
    """
    ns = types.SimpleNamespace()

    class Retriever:
        def __init__(self, *args, **kwargs):
            pass

        def query_by_text(self, text: str, top_k: int = 5):
            if mode == "raises":
                raise RuntimeError("fake retriever error")
            if mode == "nohits":
                return []
            data = [
                {"id": "REQ-101", "payload": {"text": "Alpha beta gamma requirement text.", "sourceFile": "a.md"}},
                {"id": "REQ-202", "payload": {"text": "Delta epsilon zeta requirement text.", "sourceFile": "b.md"}},
                {"id": "REQ-303", "payload": {"text": "Eta theta iota requirement text.", "sourceFile": "c.md"}},
            ]
            return data[: int(top_k or 5)]

    ns.Retriever = Retriever
    return ns


@pytest.fixture
def fake_retrieval_module_hits():
    return _make_fake_retrieval_module("hits")


@pytest.fixture
def fake_retrieval_module_nohits():
    return _make_fake_retrieval_module("nohits")


@pytest.fixture
def fake_retrieval_module_raises():
    return _make_fake_retrieval_module("raises")

# Hinweis zu asyncio/pytest-asyncio:
# Falls pytest-asyncio nicht installiert ist, verwenden die einzelnen Testmodule
# pytest.importorskip("pytest_asyncio") und skippen sauber mit Meldung.