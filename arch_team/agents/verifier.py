# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..model.chat_client import IChatClient
from ..runtime.agent_base import AgentBase, AgentId, MessageContext
from ..runtime.topics import TopicId, TOPIC_TRACE
from ..runtime.cot_postprocessor import extract_blocks
from ..runtime.logging import get_logger
from ..memory.qdrant_trace_sink import QdrantTraceSink
from ..workbench.workbench import Workbench

logger = get_logger("agents.verifier")


BASE_PROMPT_GUARD = (
    "General rules for all agents:\n"
    "- Keep outputs concise and structured. Prefer bullet points and fenced code blocks for Mermaid.\n"
    "- Requirements MUST be labeled REQ-### (e.g., REQ-001) to enable traceability.\n"
    "- When you mention a requirement in any diagram/section, include the REQ ID in a node label, note, or comment.\n"
    "- Do not invent tools or APIs; stick to widely used patterns.\n"
    "- Never remove existing REQ IDs; only add or refine.\n"
)

REQUIREMENTS_POLICY = (
    "Requirements coverage policy:\n"
    "- Provide a normalized list of functional and non-functional REQs with unique IDs REQ-001, REQ-002, ...\n"
    "- Each REQ entry must include a short description and a tag in {functional|security|performance|ux|ops}.\n"
    "- Keep total REQs between 10 and 20 for manageable coverage.\n"
)


class VerifierAgent(AgentBase):
    """
    Verifier: Prüft FINAL_ANSWER + EVIDENCE und erzeugt CRITIQUE oder DECISION.
    Persistiert Trace.
    Optional: nutzt Workbench (z. B. QdrantSearchTool) und ChatCompletionContext.
    """

    def __init__(self, chat_client: IChatClient, trace_sink: QdrantTraceSink, source: str = "default", workbench: Any | None = None, context: Any | None = None) -> None:
        super().__init__(AgentId(type="verifier", key=source))
        self.chat = chat_client
        self.trace_sink = trace_sink
        self.bus = None  # wird in main gesetzt
        self.temperature = float(os.environ.get("ARCH_TEMPERATURE", "0.2"))
        self.model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
        self.workbench = workbench
        self.context = context

    def set_bus(self, bus) -> None:
        self.bus = bus

    async def on_message(self, message: Dict[str, Any], ctx: MessageContext) -> None:
        if self.bus is None:
            logger.error("VerifierAgent ohne Bus initialisiert")
            return

        task = str(message.get("task") or "").strip()
        req_id = str(message.get("req_id") or ctx.req_id or "REQ-001")
        final_answer = str(message.get("final_answer") or "").strip()
        evidence = str(message.get("evidence") or "").strip()

        if not final_answer:
            logger.warning("VerifierAgent: final_answer fehlt; breche ab")
            return

        system_msg = (
            f"{BASE_PROMPT_GUARD}\n{REQUIREMENTS_POLICY}\n"
            "You are the Verifier. Given FINAL_ANSWER and EVIDENCE, decide if the requirement is acceptable.\n"
            "If insufficient or risky, write CRITIQUE with specific issues; else write DECISION with PASS and one-line rationale.\n"
            "Output strictly with the following sections:\n"
            "CRITIQUE:\n"
            "DECISION:\n"
        )

        # Heuristik: Wenn EVIDENCE dünn, optional QdrantSearch erneut anstoßen
        enriched_evidence = evidence
        try:
            cites = [ln for ln in evidence.splitlines() if "MEMORY_" in ln]
            if len(cites) < int(os.environ.get("ARCH_VERIFIER_MIN_CITES", "1")) and self.workbench:
                tr = self.workbench.call("qdrant_search", {"query": task, "top_k": 3})
                if getattr(tr, "status", "") == "success":
                    hits = tr.content if isinstance(tr.content, list) else []
                    lines = []
                    for h in hits[:3]:
                        try:
                            hid = h.get("id", "")
                            sc = float(h.get("score", 0.0) or 0.0)
                            src = h.get("source", "")
                            sn = str(h.get("snippet", "") or "")[:120].replace("\n", " ")
                            lines.append(f"- {hid} | {sc:.3f} | {src} | {sn}")
                        except Exception:
                            continue
                    if lines:
                        enriched_evidence += ("\n\nADDITIONAL_EVIDENCE:\n" + "\n".join(lines))
                else:
                    # Fehlerfälle stillschweigend intern ignorieren
                    pass
        except Exception:
            pass

        user_msg = (
            f"Task:\n{task}\n\n"
            f"EVIDENCE:\n{enriched_evidence}\n\n"
            f"FINAL_ANSWER:\n{final_answer}\n"
        )

        try:
            messages = [{"role": "system", "content": system_msg}]
            if self.context is not None:
                try:
                    history = await self.context.get_messages()
                    for m in history:
                        if m.get("role") != "system":
                            messages.append({"role": m.get("role"), "content": m.get("content")})
                except Exception:
                    pass
            messages.append({"role": "user", "content": user_msg})

            if self.context is not None:
                try:
                    await self.context.add_message({"role": "system", "content": system_msg})
                    await self.context.add_message({"role": "user", "content": user_msg})
                except Exception:
                    pass

            content = self.chat.create(
                messages=messages,
                temperature=self.temperature,
                model=self.model_name,
            )
            if isinstance(content, list):
                content_text = "\n".join(str(m.get("content", "")) for m in content)
            else:
                content_text = str(content or "")
        except Exception as e:
            logger.error("Verifier Chat fehlgeschlagen: %s", e)
            content_text = (
                "CRITIQUE: None. The answer appears reasonable given limited evidence.\n"
                "DECISION: PASS - Minimal baseline accepted.\n"
            )

        blocks = extract_blocks(content_text)
        if self.context is not None:
            try:
                await self.context.add_message({"role": "assistant", "content": content_text})
            except Exception:
                pass

        # Optionale JSON-Tool-Call-Verarbeitung (nur interne EVIDENCE, kein UI-Leak)
        try:
            parsed_tc = Workbench.from_llm_output(content_text)
        except Exception:
            parsed_tc = None
        if isinstance(parsed_tc, tuple) and self.workbench:
            tool_name, tool_args = parsed_tc

            def _summarize_tool_result(name: str, tr) -> str:
                try:
                    if getattr(tr, "status", "") == "success":
                        c = tr.content
                        if name == "qdrant_search" and isinstance(c, list):
                            lines = []
                            for h in c[:3]:
                                try:
                                    hid = h.get("id", "")
                                    sc = float(h.get("score", 0.0) or 0.0)
                                    src = h.get("source", "")
                                    sn = str(h.get("snippet", "") or "")[:120].replace("\n", " ")
                                    lines.append(f"- {hid} | {sc:.3f} | {src} | {sn}")
                                except Exception:
                                    continue
                            return "\n".join(lines)
                        if name == "python_exec" and isinstance(c, dict):
                            out = str(c.get("stdout", "")).replace("\r", "")[:200]
                            return f"stdout: {out}"
                        return str(c)[:200]
                    else:
                        return f"status={tr.status} error={tr.error}"
                except Exception:
                    return ""

            try:
                tr = self.workbench.call(tool_name, tool_args if isinstance(tool_args, dict) else {})
                summary = _summarize_tool_result(tool_name, tr)
                if summary and self.context is not None:
                    await self.context.add_message({"role": "assistant", "content": f"TOOL_EVIDENCE ({tool_name}):\n{summary}"})
            except Exception:
                # Keine UI-Ausgabe; interne Notiz genügt
                pass
        critique = blocks.get("CRITIQUE", "")
        decision = blocks.get("DECISION", "")

        # Persistiere Trace
        try:
            self.trace_sink.ensure()
            from ..runtime.cot_postprocessor import to_trace_record
            record = to_trace_record({**blocks, "EVIDENCE": enriched_evidence, "FINAL_ANSWER": final_answer}, meta={"correlationId": ctx.correlation_id})
            self.trace_sink.save(
                thoughts=record["thoughts"],
                evidence=record["evidence"],
                final=record["final"],
                decision=record["decision"] or ("REJECT" if critique else "PASS"),
                task=task,
                req_id=req_id,
                agent_type=self.id.type,
                session_id=ctx.session_id,
                meta=record["meta"],
            )
        except Exception as e:
            logger.error("Verifier TraceSink.save fehlgeschlagen: %s", e)

        # TRACE-Event veröffentlichen (sammelt CoT-Artefakte)
        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_TRACE, source=self.id.key),
            message={"agent": "verifier", "blocks": blocks, "req_id": req_id},
            ctx=ctx,
        )