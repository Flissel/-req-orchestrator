# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

from ..model.chat_client import IChatClient
from ..runtime.agent_base import AgentBase, AgentId, MessageContext
from ..runtime.topics import TopicId, TOPIC_VERIFY, TOPIC_TRACE, TOPIC_DTO
from ..runtime.cot_postprocessor import extract_blocks
from ..runtime.logging import get_logger
from ..memory.retrieval import Retriever
from ..memory.qdrant_trace_sink import QdrantTraceSink
from backend_app.rag import StructuredRequirement  # DTO-Erzeugung
from ..workbench.workbench import Workbench

logger = get_logger("agents.solver")


# Guards als konstante Strings
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


class SolverAgent(AgentBase):
    """
    Solver: Nutzt Retrieval-Kontext und erzeugt THOUGHTS, EVIDENCE, FINAL_ANSWER.
    Persistiert Trace und gibt ein DTO an das Frontend weiter (TOPIC_DTO).
    Optional: nutzt Workbench (Tools) und ChatCompletionContext.
    """

    def __init__(self, chat_client: IChatClient, retriever: Retriever, trace_sink: QdrantTraceSink, source: str = "default", workbench: Any | None = None, context: Any | None = None) -> None:
        super().__init__(AgentId(type="solver", key=source))
        self.chat = chat_client
        self.retriever = retriever
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
            logger.error("SolverAgent ohne Bus initialisiert")
            return

        task = str(message.get("task") or "").strip()
        req_id = str(message.get("req_id") or ctx.req_id or "REQ-001")
        plan = str(message.get("plan") or "").strip()
        if not task:
            logger.warning("SolverAgent: task fehlt; abbrechen")
            return

        # Retrieval-Kontexte
        memory_lines: List[str] = []
        try:
            if req_id:
                memory_lines = self.retriever.get_context_for_solver(req_id=req_id) or []
            if not memory_lines:
                memory_lines = self.retriever.get_context_for_solver(query=task, top_k=5) or []
        except Exception as e:
            logger.error("SolverAgent Retrieval fehlgeschlagen: %s", e)
            memory_lines = []

        memory_section = ""
        if memory_lines:
            memory_section = "MEMORY:\n" + "\n".join(f"- {line}" for line in memory_lines) + "\n"

        system_msg = (
            f"{BASE_PROMPT_GUARD}\n{REQUIREMENTS_POLICY}\n"
            "You are the Solver. Use the provided MEMORY (if any) and PLAN to craft refined requirement(s).\n"
            "If you need tools, you may propose one TOOL_CALL: {\"name\": \"...\", \"arguments\": {...}}.\n"
            "Output strictly with the following sections:\n"
            "THOUGHTS:\n"
            "EVIDENCE:\n"
            "FINAL_ANSWER:\n"
        )
        user_msg = (
            f"Task:\n{task}\n\n"
            f"Plan:\n{plan}\n\n"
            f"{memory_section}"
            "Constraints:\n- Keep output short and actionable\n- Avoid code\n"
        )

        critique_prev = str(message.get("critique") or "").strip()
        if critique_prev:
            user_msg += f"\nPRIOR_CRITIQUE:\n{critique_prev}\n"

        # Tools-Schemas (OpenAI-Style) aus Workbench
        tools_payload = None
        if self.workbench:
            try:
                tools_list = self.workbench.list_tools()
            except Exception:
                tools_list = []
            if tools_list:
                tools_payload = []
                for t in tools_list:
                    name = t.get("name")
                    desc = t.get("description")
                    params = t.get("input_schema") or {}
                    tools_payload.append({"type": "function", "function": {"name": name, "description": desc, "parameters": params}})

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
                tools=tools_payload,
            )
            if isinstance(content, list):
                content_text = "\n".join(str(m.get("content", "")) for m in content)
            else:
                content_text = str(content or "")

            # Assistant in Verlauf puffern
            if self.context is not None:
                try:
                    await self.context.add_message({"role": "assistant", "content": content_text})
                except Exception:
                    pass
        except Exception as e:
            logger.error("Solver Chat fehlgeschlagen: %s", e)
            content_text = (
                "THOUGHTS: fallback reasoning without LLM\n"
                "EVIDENCE: gathered minimal context from prior steps\n"
                "FINAL_ANSWER: REQ-001: The system shall allow uploading CSV files up to 10MB and validate schema with clear error messages.\n"
            )

        blocks = extract_blocks(content_text)

        # Optionale JSON-Tool-Call-Verarbeitung via Workbench.from_llm_output
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

        if self.workbench:
            try:
                parsed = Workbench.from_llm_output(content_text)
            except Exception:
                parsed = None
            if isinstance(parsed, tuple):
                tool_name, tool_args = parsed
                try:
                    tr = self.workbench.call(tool_name, tool_args if isinstance(tool_args, dict) else {})
                    summary = _summarize_tool_result(tool_name, tr)
                    # In Verlauf zurückspeisen (intern, nicht fürs UI)
                    if summary and self.context is not None:
                        try:
                            await self.context.add_message({"role": "assistant", "content": f"TOOL_EVIDENCE ({tool_name}):\n{summary}"})
                        except Exception:
                            pass
                    # Zweiter Call: Tool-EVIDENCE berücksichtigen
                    try:
                        follow_user = (
                            "Incorporate the following tool evidence into EVIDENCE and refine FINAL_ANSWER.\n"
                            f"{summary}\n\n"
                            "Output sections: THOUGHTS, EVIDENCE, FINAL_ANSWER."
                        )
                        messages2 = [{"role": "system", "content": system_msg}]
                        if self.context is not None:
                            try:
                                history2 = await self.context.get_messages()
                                for m in history2:
                                    if m.get("role") != "system":
                                        messages2.append({"role": m.get("role"), "content": m.get("content")})
                            except Exception:
                                pass
                        messages2.append({"role": "user", "content": follow_user})
                        content2 = self.chat.create(
                            messages=messages2,
                            temperature=self.temperature,
                            model=self.model_name,
                            tools=tools_payload,
                        )
                        content_text2 = "\n".join(str(m.get("content", "")) for m in content2) if isinstance(content2, list) else str(content2 or "")
                        blocks2 = extract_blocks(content_text2)
                        if self.context is not None:
                            try:
                                await self.context.add_message({"role": "assistant", "content": content_text2})
                            except Exception:
                                pass
                        # Merge (bevorzuge zweite Antwort)
                        for k in ["THOUGHTS", "EVIDENCE", "FINAL_ANSWER"]:
                            if blocks2.get(k):
                                blocks[k] = blocks2[k]
                    except Exception as e:
                        logger.warning("Follow-up after tool call failed: %s", e)
                except Exception as e:
                    logger.warning("Tool call handling failed: %s", e)

        thoughts = blocks.get("THOUGHTS", "")
        evidence = blocks.get("EVIDENCE", "")
        final = blocks.get("FINAL_ANSWER", "")

        # Trace persistieren (gedankliche Inhalte nicht ins UI!)
        try:
            self.trace_sink.ensure()
            from ..runtime.cot_postprocessor import to_trace_record
            record = to_trace_record(blocks, meta={"correlationId": ctx.correlation_id})
            self.trace_sink.save(
                thoughts=record["thoughts"],
                evidence=record["evidence"],
                final=record["final"],
                decision=record["decision"],
                task=task,
                req_id=req_id,
                agent_type=self.id.type,
                session_id=ctx.session_id,
                meta=record["meta"],
            )
        except Exception as e:
            logger.error("Solver TraceSink.save fehlgeschlagen: %s", e)

        # TRACE-Event veröffentlichen (z. B. zum Sammeln/Logging)
        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_TRACE, source=self.id.key),
            message={"agent": "solver", "blocks": blocks, "req_id": req_id},
            ctx=ctx,
        )

        # DTO für Frontend (Platzhalter) – nutzt StructuredRequirement
        try:
            dto = StructuredRequirement.from_agent_answer_item(
                {
                    "reqId": req_id,
                    "originalText": task,
                    "redefinedRequirement": final,
                    "evaluation": [],
                    "suggestions": [],
                }
            ).to_dict()
        except Exception:
            dto = {"reqId": req_id, "originalText": task, "redefinedRequirement": final}

        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_DTO, source=self.id.key),
            message={"dto": dto},
            ctx=ctx,
        )

        # Handoff an Verifier
        await self.bus.publish(
            topic_id=TopicId(type=TOPIC_VERIFY, source=self.id.key),
            message={
                "task": task,
                "req_id": req_id,
                "final_answer": final,
                "evidence": evidence,
            },
            ctx=ctx,
        )