# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_rac_smoke_no_llm(monkeypatch):
    """
    Smoke-Test für das RAC-Team ohne echte LLM-Aufrufe.
    - Stubb't Console, sodass der Stream nicht ausgeführt wird (keine Tool-/LLM-Interaktion).
    - Stubb't OpenAIChatCompletionClient auf einen Fake-Client mit close()-Methode.
    - Erwartung: arch_team.autogen_rac.main() läuft ohne Exception durch.
    """
    import arch_team.autogen_rac as rac

    # Minimal-ENV für den Start
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "gpt-4o-mini")
    monkeypatch.setenv("ARCH_TASK", "Dummy task for smoke test")
    monkeypatch.setenv("RAC_MAX_MESSAGES", "1")

    # Console stubben: stream NICHT iterieren, damit keine LLM-Aufrufe passieren
    async def console_stub(stream):
        return None

    monkeypatch.setattr(rac, "Console", console_stub, raising=True)

    # Model-Client stubben, damit kein echter API-Call passiert
    class FakeClient:
        def __init__(self, model, api_key, temperature=0.0):
            self.model = model
            self.api_key = api_key
            self.temperature = temperature

        async def close(self):
            pass

    monkeypatch.setattr(rac, "OpenAIChatCompletionClient", FakeClient, raising=True)

    # Ausführen: sollte ohne Exception durchlaufen
    await rac.main()