# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os
import sys
import argparse
import glob
import mimetypes
from typing import Any, Dict, List

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

from arch_team.runtime.logging import get_logger, banner
from arch_team.runtime.event_bus import EventBus
from arch_team.runtime.sequencer import Sequencer
from arch_team.model.model_context import ChatCompletionContext
from arch_team.workbench.workbench import get_default_workbench
from arch_team.runtime.topics import TOPIC_PLAN, TOPIC_SOLVE, TOPIC_VERIFY, TOPIC_DTO, TOPIC_TRACE
from arch_team.runtime.cot_postprocessor import ui_payload

from arch_team.model.openai_adapter import OpenAIAdapter
from arch_team.memory.retrieval import Retriever
from arch_team.memory.qdrant_trace_sink import QdrantTraceSink

from arch_team.agents.planner import PlannerAgent
from arch_team.agents.solver import SolverAgent
from arch_team.agents.verifier import VerifierAgent
from arch_team.agents.req_worker import ReqWorkerAgent


logger = get_logger("main")

def _read_files_for_chunk_miner(paths: List[str]) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for pat in paths:
        for p in glob.glob(pat):
            if not os.path.isfile(p):
                continue
            ct, _ = mimetypes.guess_type(p)
            try:
                with open(p, "rb") as f:
                    data = f.read()
                files.append({"filename": os.path.basename(p), "data": data, "content_type": ct or ""})
            except Exception as e:
                logger.warning("chunk_miner: could not read %s: %s", p, e)
    return files

def run_chunk_miner_cli(paths: List[str], model: str | None, neighbor_refs: bool) -> int:
    # Lazy import to avoid hard dependency if not used
    try:
        from arch_team.agents.chunk_miner import ChunkMinerAgent  # type: ignore
    except Exception as e:
        logger.error("chunk_miner: ChunkMinerAgent not available: %s", e)
        return 0

    files_or_texts = _read_files_for_chunk_miner(paths)
    if not files_or_texts:
        logger.warning("chunk_miner: no readable files for patterns: %s", paths)
        return 0

    agent = ChunkMinerAgent(source="cli", default_model=model or os.environ.get("MODEL_NAME", "gpt-4o-mini"))
    # use environment fallback if CLI flag not set
    if not neighbor_refs:
        env_flag = (os.environ.get("CHUNK_MINER_NEIGHBORS", "") or "").strip().lower()
        neighbor_refs = env_flag in ("1", "true", "yes", "on")
    count = agent.mine_files_or_texts(files_or_texts, model=model, neighbor_refs=neighbor_refs)
    logger.info("chunk_miner: produced %d DTO(s)", count)
    return count


async def main() -> None:
    # ENV laden (optional)
    if load_dotenv:
        try:
            load_dotenv()
        except Exception:
            pass

    model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    arch_temp = float(os.environ.get("ARCH_TEMPERATURE", "0.2"))
    task_text = os.environ.get(
        "ARCH_TASK",
        "Elicit and normalize requirements for a secure, scalable CSV upload & validation system. "
        "Output refined requirement(s) and a short rationale.",
    )
    qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.environ.get("QDRANT_API_KEY", "")
    req_id = os.environ.get("REQ_ID", "REQ-001")

    banner(logger, "Requirements Mining - Single-Process Baseline (Planner → Solver → Verifier)")

    # Clients / Memory
    chat = OpenAIAdapter(default_model=model_name)
    retriever = Retriever(qdrant_url=qdrant_url, api_key=qdrant_api_key, collection=os.environ.get("QDRANT_COLLECTION") or "requirements_v2")
    trace_sink = QdrantTraceSink(qdrant_url=qdrant_url, api_key=qdrant_api_key, collection="arch_trace")

    # Workbench-Factory (registriert python_exec und qdrant_search)
    # Sicherheit/Privacy: Tool-Resultate werden nur intern (EVIDENCE) genutzt und nicht ungefiltert im UI ausgegeben.
    workbench = get_default_workbench()

    # Model Context (Buffered)
    max_ctx = int(os.environ.get("ARCH_MODEL_CONTEXT_MAX", "12"))
    shared_ctx = ChatCompletionContext(max_len=max_ctx)

    # Agents
    planner = PlannerAgent(chat_client=chat, context=shared_ctx, workbench=workbench)
    solver = SolverAgent(chat_client=chat, retriever=retriever, trace_sink=trace_sink, workbench=workbench, context=shared_ctx)
    verifier = VerifierAgent(chat_client=chat, trace_sink=trace_sink, workbench=workbench, context=shared_ctx)
    req_worker = ReqWorkerAgent()

    # EventBus
    bus = EventBus()
    planner.set_bus(bus)
    solver.set_bus(bus)
    verifier.set_bus(bus)
    req_worker.set_bus(bus)

    # CoT-Trace Collector (für UI-Ausgabe; keine PII)
    trace_blocks: List[Dict[str, str]] = []

    async def trace_collector(message: Dict[str, Any], ctx) -> None:
        blocks = message.get("blocks")
        if isinstance(blocks, dict):
            trace_blocks.append({k: str(v) for k, v in blocks.items() if isinstance(v, str)})

    # Subscriptions
    await bus.subscribe(TOPIC_PLAN, "planner", planner.on_message)
    await bus.subscribe(TOPIC_SOLVE, "solver", solver.on_message)
    await bus.subscribe(TOPIC_VERIFY, "verifier", verifier.on_message)
    await bus.subscribe(TOPIC_DTO, "req_worker", req_worker.on_message)
    await bus.subscribe(TOPIC_TRACE, "collector", trace_collector)

    # Sequencer orchestriert je nach ENV Reflection
    seq = Sequencer(source="default")
    rounds = int(os.environ.get("ARCH_REFLECTION_ROUNDS", "1"))
    if rounds and rounds > 1:
        await seq.run_with_reflection(
            bus=bus,
            planner=planner,
            solver=solver,
            verifier=verifier,
            task_text=task_text,
            req_id=req_id,
            session_id="session-1",
            max_rounds=rounds,
        )
    else:
        await seq.run_once(bus=bus, planner=planner, solver=solver, verifier=verifier, task_text=task_text, req_id=req_id, session_id="session-1")

    # Nur UI-sichere Ausgabe (FINAL_ANSWER oder DECISION)
    ui_text = ui_payload(trace_blocks)
    if ui_text:
        banner(logger, "FINAL OUTPUT (UI-safe)")
        print(ui_text)
    else:
        logger.info("Kein FINAL_ANSWER/DECISION ermittelt.")

    # Hinweis bei fehlendem OPENAI_API_KEY (defensiv, Programm nicht abstürzen lassen)
    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY fehlt. LLM-Aufrufe nutzen Fallback. Setze OPENAI_API_KEY in .env, um echte Antworten zu erhalten.")

    # Hinweis zu Qdrant-Konfiguration
    logger.info("Qdrant URL: %s | Collection (retrieval): %s", qdrant_url, os.environ.get("QDRANT_COLLECTION") or "requirements_v2")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARCH Team Runner")
    parser.add_argument("--mode", choices=["rac", "chunk_miner"], default=os.environ.get("ARCH_MODE", "rac"))
    parser.add_argument("--path", action="append", help="Dateipfad oder Glob (mehrfach nutzbar) für chunk_miner")
    parser.add_argument("--model", help="Modelname für OpenAIAdapter (überschreibt MODEL_NAME)")
    parser.add_argument("--neighbor-evidence", action="store_true", help="Fügt chunkIndex±1 als evidence_refs hinzu (chunk_miner)")
    args, unknown = parser.parse_known_args()

    if args.mode == "chunk_miner":
        if not args.path:
            print("chunk_miner requires at least one --path")
            sys.exit(2)
        count = run_chunk_miner_cli(paths=args.path, model=args.model, neighbor_refs=bool(args.neighbor_evidence))
        # exit code 0 even if 0 DTOs, but print info
        sys.exit(0)
    else:
        asyncio.run(main())