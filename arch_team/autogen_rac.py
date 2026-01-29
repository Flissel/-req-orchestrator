# -*- coding: utf-8 -*-
from __future__ import annotations

"""
AutoGen 0.4+ RAC-Team (Planner, Solver, Verifier) für Requirements Architecture Chat (RAC).

- Verwendet moderne AutoGen 0.4+ APIs:
  - AssistantAgent, RoundRobinGroupChat, Termination-Conditions, Console-Streaming
  - OpenAIChatCompletionClient (autogen-ext) with OpenRouter
- .env wird automatisch geladen (OPENROUTER_API_KEY Pflicht, MODEL_NAME optional)
- Tools: RAG-Suche via arch_team.autogen_tools.search_requirements (nutzt internen Retriever)
- Termination: TextMentionTermination("COVERAGE_OK") ODER MaxMessageTermination(10)

Start:
  python -m arch_team.autogen_rac
"""

import os
import asyncio
import logging

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console

# Hinweis: Kein Top-Level-Import des OpenAI-Clients, um Offline-Tests zu ermöglichen.
# Wir stellen einen Platzhalter bereit, den Tests via monkeypatch ersetzen können,
# und importieren ansonsten lazy mit Fallback auf einen Dummy-Client.
OpenAIChatCompletionClient = None  # type: ignore

def _import_openai_client():
    try:
        from autogen_ext.models.openai import OpenAIChatCompletionClient as _Client  # type: ignore
        return _Client
    except Exception as e:
        logger = logging.getLogger("arch_team.autogen_rac")
        logger.warning(
            "RAC: OpenAIChatCompletionClient not available (%s). Falling back to Dummy client.",
            type(e).__name__,
        )
        return None

class _DummyClient:
    def __init__(self, model: str, api_key: str, temperature: float = 0.0, base_url: str | None = None):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.base_url = base_url
        # ensure interface expected by AssistantAgent when tools are present
        self.model_info = {"function_calling": True}

    async def close(self):
        return None

def create_model_client(model_name: str, api_key: str, temperature: float, base_url: str | None = None):
    # Wenn Tests das Symbol per monkeypatch setzen, dieses bevorzugen
    if OpenAIChatCompletionClient is not None:
        try:
            # Pass base_url for OpenRouter support
            client_kwargs = {"model": model_name, "api_key": api_key, "temperature": temperature}
            if base_url:
                client_kwargs["base_url"] = base_url
            client = OpenAIChatCompletionClient(**client_kwargs)  # type: ignore
            # Ensure expected interface for tool support
            if not hasattr(client, "model_info") or "function_calling" not in getattr(client, "model_info", {}):
                try:
                    client.model_info = {"function_calling": True}  # type: ignore[attr-defined]
                except Exception:
                    pass
            return client
        except Exception:
            # Fallback auf lazy import unten
            pass
    _Client = _import_openai_client()
    if _Client is not None:
        client_kwargs = {"model": model_name, "api_key": api_key, "temperature": temperature}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = _Client(**client_kwargs)
        if not hasattr(client, "model_info") or "function_calling" not in getattr(client, "model_info", {}):
            try:
                client.model_info = {"function_calling": True}  # type: ignore[attr-defined]
            except Exception:
                pass
        return client
    logger = logging.getLogger("arch_team.autogen_rac")
    logger.info("RAC: Using Dummy model client (no real LLM calls).")
    return _DummyClient(model=model_name, api_key=api_key, temperature=temperature, base_url=base_url)

# Tools im Namespace arch_team.autogen_tools
from . import autogen_tools as rac_tools

# Try to import backend settings for provider config
try:
    from backend.core.settings import get_llm_config
    _has_backend_settings = True
except ImportError:
    _has_backend_settings = False

# .env laden (optional/robust)
# Use override=True to force loading even if empty env var exists
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=True)
except Exception:
    pass

logger = logging.getLogger("arch_team.autogen_rac")


async def main() -> None:
    # Get OpenRouter configuration
    if _has_backend_settings:
        llm_config = get_llm_config()
        api_key = llm_config["api_key"]
        base_url = llm_config["base_url"]
        model_name = llm_config["model"]
    else:
        # Fallback to direct env vars (OpenRouter only)
        api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
        base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model_name = os.getenv("MODEL_NAME", "google/gemini-2.5-flash:nitro")

    if not api_key:
        print("ERROR: OPENROUTER_API_KEY ist leer oder nicht gesetzt.")
        return

    # Temperatur leicht reduziert für deterministischere REQs
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
    model_client = create_model_client(model_name=model_name, api_key=api_key, temperature=temperature, base_url=base_url)

    # Konfigurationen
    rag_enabled = os.getenv("RAC_RAG_ENABLED", "1").lower() not in ("0", "false", "")
    try:
        max_messages = int(os.getenv("RAC_MAX_MESSAGES") or os.getenv("MAX_MESSAGES") or "10")
    except Exception:
        max_messages = 10

    logger.info("RAC start: model=%s temperature=%.3f rag_enabled=%s max_messages=%d", model_name, temperature, rag_enabled, max_messages)

    try:
        # Systemprompts laut Vorgabe
        planner_sys = (
            "You are the Planner. Create a minimal actionable plan for requirements mining of a backend system. "
            "The plan should list 3–5 concrete steps. Do not print internal thoughts. End with: HANDOFF: solver."
        )
        solver_sys = (
            "You are the Solver. Use tools if helpful. Extract a clean list of requirements with stable IDs REQ-001.., "
            "each with a short description and a tag in {functional|security|performance|ux|ops}. Keep it concise. "
            "If coverage is sufficient print COVERAGE_OK at the very end."
        )
        verifier_sys = (
            "You are the Verifier. Validate the REQ list for coverage and tags. If sufficient, reply exactly: COVERAGE_OK. "
            "Otherwise produce a short CRITIQUE with precise improvement hints."
        )

        # Agents definieren
        planner = AssistantAgent(
            name="planner",
            system_message=planner_sys,
            model_client=model_client,
        )
        solver_tools = [rac_tools.search_requirements] if rag_enabled else []
        solver = AssistantAgent(
            name="solver",
            system_message=solver_sys,
            model_client=model_client,
            tools=solver_tools,  # RAG-Tool optional registrieren
        )
        verifier = AssistantAgent(
            name="verifier",
            system_message=verifier_sys,
            model_client=model_client,
        )

        # Termination-Bedingungen: COVERAGE_OK oder konfigurierbare max. Nachrichten
        termination = TextMentionTermination("COVERAGE_OK") | MaxMessageTermination(max_messages)

        # Team erstellen (Round-Robin)
        team = RoundRobinGroupChat([planner, solver, verifier], termination_condition=termination)

        # Task definieren (aus ENV ARCH_TASK oder Default)
        task = os.getenv(
            "ARCH_TASK",
            "Mine requirements for our backend platform focusing security, performance, ops and UX. Return REQ-IDs and tags.",
        )

        # Console-Streaming
        await Console(team.run_stream(task=task))
    finally:
        # Modell-Client schließen
        try:
            await model_client.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())