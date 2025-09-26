# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, Any

from .agent_base import MessageContext, AgentBase, AgentId
from .event_bus import EventBus
from .topics import TopicId, TOPIC_PLAN, TOPIC_SOLVE, TOPIC_VERIFY
from .logging import get_logger

logger = get_logger("runtime.sequencer")


class Sequencer:
    """
    Führt einen einfachen sequentiellen Durchlauf Planner → Solver → Verifier aus.
    Nutzt den In-Process EventBus für die Zustellung.
    Zusätzlich: Reflection-Loop (Verifier↔Solver) via run_with_reflection().
    """

    def __init__(self, source: str = "default") -> None:
        self.source = source

    def _ctx_base(self, correlation_id: str, req_id: str | None, session_id: str | None) -> MessageContext:
        return MessageContext(
            correlation_id=correlation_id,
            req_id=req_id,
            session_id=session_id,
            topic_id=None,
            origin_agent=AgentId(type="sequencer", key=self.source),
            meta={},
        )

    async def run_once(
        self,
        bus: EventBus,
        planner: AgentBase,
        solver: AgentBase,
        verifier: AgentBase,
        task_text: str,
        req_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        Orchestriert genau einen Turn:
        1) Planner erhält Task → erzeugt PLAN (und ggf. THOUGHTS), Hands-off an Solver
        2) Solver nutzt Retrieval/Memory → erzeugt EVIDENCE/FINAL_ANSWER → Hands-off an Verifier
        3) Verifier prüft FINAL_ANSWER → erzeugt DECISION oder CRITIQUE
        """
        correlation_id = str(uuid.uuid4())
        base_ctx = self._ctx_base(correlation_id, req_id=req_id, session_id=session_id)

        # Schritt 1: Planner
        ctx1 = base_ctx
        ctx1.topic_id = TopicId(type=TOPIC_PLAN, source=self.source)
        ctx1.origin_agent = planner.id
        logger.info("Sequencer: dispatch Planner (corr=%s req=%s)", correlation_id, req_id)
        await bus.publish(topic_id=TopicId(type=TOPIC_PLAN, source=self.source), message={"task": task_text, "req_id": req_id}, ctx=ctx1)

        # Schritt 2: Solver (wird vom Planner via publish getriggert), dennoch Sequenz-Gate:
        # In dieser Baseline erfolgt die Reihenfolge deterministisch, da wir sequential dispatch nutzen.

        # Schritt 3: Verifier (wird vom Solver via publish getriggert)

        # Nichts weiter zu tun: die Agenten veröffentlichen Folge-Ereignisse selbst.
        logger.info("Sequencer: run_once finished (corr=%s req=%s)", correlation_id, req_id)

    async def run_with_reflection(
        self,
        bus: EventBus,
        planner: AgentBase,
        solver: AgentBase,
        verifier: AgentBase,
        task_text: str,
        req_id: str | None = None,
        session_id: str | None = None,
        max_rounds: int = 3,
        wait_timeout_sec: float = 30.0,
    ) -> None:
        """
        Ablauf:
        Planner → Solver → Verifier; wenn Verifier CRITIQUE liefert und DECISION nicht PASS/ACCEPT,
        dann erneut Solver mit CRITIQUE als zusätzlichem Input; bis PASS/ACCEPT oder max_rounds.
        """
        import asyncio as _asyncio

        correlation_id = str(uuid.uuid4())
        base_ctx = self._ctx_base(correlation_id, req_id=req_id, session_id=session_id)

        # Lokale Sammlung aus TOPIC_TRACE
        latest_plan: str = ""
        latest_verifier_blocks: Dict[str, Any] | None = None
        verifier_event = _asyncio.Event()

        async def _collector(message: Dict[str, Any], ctx) -> None:
            nonlocal latest_plan, latest_verifier_blocks
            blocks = message.get("blocks") or {}
            agent = message.get("agent") or ""
            if agent == "planner":
                p = blocks.get("PLAN", "")
                if isinstance(p, str):
                    latest_plan = p
            if agent == "verifier":
                latest_verifier_blocks = {k: v for k, v in blocks.items() if isinstance(v, str)}
                verifier_event.set()

        # Subscribe temporär
        await bus.subscribe(TOPIC_TRACE, "sequencer_reflect", _collector)

        # Runde 1: normaler Durchlauf (Planner triggert Solver, dieser triggert Verifier)
        ctx1 = base_ctx
        ctx1.topic_id = TopicId(type=TOPIC_PLAN, source=self.source)
        ctx1.origin_agent = planner.id
        logger.info("Sequencer: run_with_reflection dispatch Planner (corr=%s req=%s)", correlation_id, req_id)
        await bus.publish(topic_id=TopicId(type=TOPIC_PLAN, source=self.source), message={"task": task_text, "req_id": req_id}, ctx=ctx1)

        try:
            await _asyncio.wait_for(verifier_event.wait(), timeout=wait_timeout_sec)
        except Exception:
            logger.warning("Sequencer: Reflection Runde 1 timeout – keine Verifier-Antwort empfangen")
            return

        round_idx = 1
        while round_idx < max_rounds:
            verifier_event.clear()
            decision = (latest_verifier_blocks or {}).get("DECISION", "")
            critique = (latest_verifier_blocks or {}).get("CRITIQUE", "")
            accept = "ACCEPT" in decision.upper() or "PASS" in decision.upper()

            if accept or not critique.strip():
                logger.info("Sequencer: Reflection stop – decision=%s, critique_len=%d", decision.strip()[:40], len(critique))
                break

            # Erneuter Solver-Call mit CRITIQUE als Zusatzinput
            logger.info("Sequencer: Reflection Runde %d → Solver mit Critique", round_idx + 1)
            ctxs = base_ctx
            ctxs.topic_id = TopicId(type=TOPIC_SOLVE, source=self.source)
            ctxs.origin_agent = solver.id
            await bus.publish(
                topic_id=TopicId(type=TOPIC_SOLVE, source=self.source),
                message={"task": task_text, "req_id": req_id, "plan": latest_plan, "critique": critique},
                ctx=ctxs,
            )

            try:
                await _asyncio.wait_for(verifier_event.wait(), timeout=wait_timeout_sec)
            except Exception:
                logger.warning("Sequencer: Reflection Runde %d timeout – keine Verifier-Antwort", round_idx + 1)
                break

            round_idx += 1

        logger.info("Sequencer: run_with_reflection finished (corr=%s req=%s, rounds=%d)", correlation_id, req_id, round_idx)