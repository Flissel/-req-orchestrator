# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

from ..model.chat_client import IChatClient
from ..runtime.agent_base import AgentBase, AgentId, MessageContext
from ..runtime.topics import TopicId, TOPIC_SOLVE, TOPIC_TRACE
from ..runtime.cot_postprocessor import extract_blocks
from ..runtime.logging import get_logger
from ..workbench.workbench import Workbench

logger = get_logger("agents.planner")


# Guards als konstante Strings (nicht aus autogen-Datei importieren!)
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


class PlannerAgent(AgentBase):
    """
    Planner: Erstellt einen groben Plan (PLAN) und internes Denken (THOUGHTS) aus dem Task.
    Handoff an Solver mit PLAN.
    Optional: nutzt ChatCompletionContext für Verlauf.
    """

    def __init__(self, chat_client: IChatClient, source: str = "default", context: Any | None = None, workbench: Any | None = None) -> None:
        super().__init__(AgentId(type="planner", key=source))
        self.chat = chat_client
        self.bus = None  # wird in main gesetzt
        self.temperature = float(os.environ.get("ARCH_TEMPERATURE", "0.2"))
        self.model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
        self.context = context
        self.workbench = workbench

    def set_bus(self, bus) -> None:
        self.bus = bus

    async def on_message(self, message: Dict[str, Any], ctx: MessageContext) -> None:
        if self.bus is None:
            logger.error("PlannerAgent ohne Bus initialisiert")
            return

        task = str(message.get("task") or "").strip()
        req_id = message.get("req_id")
        if not task:
            logger.warning("PlannerAgent: task fehlt; abbrechen")
            return

        system_msg = (
            f"{BASE_PROMPT_GUARD}\n{REQUIREMENTS_POLICY}\n"
            "You are the Planner. Produce a short execution plan for the team to derive refined requirements.\n"
            "Output strictly with the following sections:\n"
            "THOUGHTS:\n"
            "PLAN:\n"
        )
        user_msg = (
            "Task:\n"
            f"{task}\n\n"
            "Constraints:\n- Keep plan minimal (3-6 bullets)\n- Do not include implementation code\n"
        )

        try:
            messages = [{"role": "system", "content": system_msg}]
            # bisherigen Verlauf anhängen (ohne weitere system Nachrichten)
            if self.context is not None:
                try:
                    history = await self.context.get_messages()
                    for m in history:
                        if m.get("role") != "system":
                            messages.append({"role": m.get("role"), "content": m.get("content")})
                except Exception:
                    pass
            messages.append({"role": "user", "content": user_msg})

            # Context aktualisieren (system/user)
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
                # Falls das Modell Nachrichtenliste liefert, konkatenieren
                content_text = "\n".join(str(m.get("content", "")) for m in content)
            else:
                content_text = str(content or "")
        except Exception as e:
            logger.error("Planner Chat fehlgeschlagen: %s", e)
            content_text = "THOUGHTS: fallback\nPLAN:\n- Analyze the task and constraints\n- Retrieve relevant context\n- Propose refined requirement(s)\n- Verify\n"

        blocks = extract_blocks(content_text)
        # Assistant in Verlauf
        if self.context is not None:
            try:
                await self.context.add_message({"role": "assistant", "content": content_text})
            except Exception:
                pass

            # Optionale JSON-Tool-Call-Verarbeitung via Workbench
            # Sicherheit/Privacy: Tool-Resultate werden ausschließlich intern als EVIDENCE in den Verlauf geschrieben,
            # nicht ungefiltert an das UI. UI-Filterung erfolgt über arch_team/runtime/cot_postprocessor.py.
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
                                lines: List[str] = []
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
                    # Toolfehler werden nicht ans UI gereicht; intern nur notiert.
                    if self.context is not None:
                        try:
                            await self.context.add_message({"role": "assistant", "content": f"TOOL_NOTE ({tool_name}): execution failed"})
                        except Exception:
                            pass
        # Defensive Defaults
        if "PLAN" not in blocks or not blocks["PLAN"].strip():
            blocks["PLAN"] = "- Analyze\n- Retrieve context\n- Propose refined requirement\n- Verify\n"

        # Trace-Event nur als Bus-Event (Persistenz erfolgt im Solver/Verifier)
        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_TRACE, source=self.id.key),
            message={"agent": "planner", "blocks": blocks, "req_id": req_id},
            ctx=ctx,
        )

        # Handoff an Solver
        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_SOLVE, source=self.id.key),
            message={
                "task": task,
                "req_id": req_id,
                "plan": blocks.get("PLAN", ""),
                # Gedanken gehen intern weiter (nicht an Frontend)
                "thoughts": blocks.get("THOUGHTS", ""),
            },
            ctx=ctx,
        )