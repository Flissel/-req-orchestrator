# -*- coding: utf-8 -*-
"""
Agent-Worker (P1a): Delegierter Mining-Service mit einfacher Multi-Schritt-Pipeline.
- Framework: FastAPI
- Zweck: Für eine Query das komplette Dokument (sourceFile) zusammensetzen, Anforderungen extrahieren
         und normalisieren, damit der Frontend-Button "Mine requirements to input" Demo-Qualität liefert.
- Interaktion mit Backend:
  * BACKEND_BASE_URL (ENV) -> z. B. http://backend:8081
  * GET  /api/v1/rag/search?query=...&top_k=...
  * GET  /api/v1/vector/source/full?source=...   (liefert alle Chunks + full text)
- Response-Shape kompatibel zum Backend-Endpoint /api/v1/agent/mine_requirements:
  {
    "query": str, "effectiveQuery": str,
    "topK": int, "window": int,
    "items": [ { "id": "R1", "requirementText": "...", "context": {...} }, ... ],
    "agentNotes": [ ... ],
    "triggeredPolicies": [ ... ]
  }

Hinweis:
- AutoGen kann hier optional ergänzt werden (Planner/Agents). Dieses Worker-Template abstrahiert bereits
  die Tools (rag_search, fetch_full_source, parse_md_table, normalize, verify) in Python-Funktionen.
"""

from __future__ import annotations

import os
import re
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, Body
from pydantic import BaseModel, Field

# -------------------------------------------------------
# Konfiguration
# -------------------------------------------------------

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://backend:8081").rstrip("/")
PORT = int(os.environ.get("PORT", "8090"))

app = FastAPI(title="Agent Worker", version="0.1.0")


# -------------------------------------------------------
# Modelle
# -------------------------------------------------------

class MineRequest(BaseModel):
    query: str = Field(..., description="User-Query")
    topK: int = Field(default=5)
    window: int = Field(default=2)


# -------------------------------------------------------
# Tools (Wrapper für Backend-Funktionen)
# -------------------------------------------------------

def tool_rag_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    url = f"{BACKEND_BASE_URL}/api/v1/rag/search"
    resp = requests.get(url, params={"query": query, "top_k": top_k}, timeout=25)
    resp.raise_for_status()
    return resp.json()


def tool_fetch_full_source(source_file: str) -> Dict[str, Any]:
    """
    Holt alle Chunks eines Dokuments zusammen mit full text (aus Backend-Utility-Endpoint).
    """
    url = f"{BACKEND_BASE_URL}/api/v1/vector/source/full"
    resp = requests.get(url, params={"source": source_file}, timeout=25)
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------
# Parsing / Normalisierung
# -------------------------------------------------------

_MD_ROW_RE = re.compile(r'^\|\s*(R\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*$', re.IGNORECASE)


def parse_md_table(text: str) -> List[Dict[str, Any]]:
    """
    Extrahiert Requirements aus Markdown-Tabelle:
    | R1 | requirementText | context |
    """
    items: List[Dict[str, Any]] = []
    if not text:
        return items
    for line in text.splitlines():
        s = line.strip()
        m = _MD_ROW_RE.match(s)
        if not m:
            continue
        rid, req, ctx = m.group(1), m.group(2), m.group(3)
        ctx_obj: Dict[str, Any]
        try:
            ctx_obj = json.loads(ctx) if ctx else {}
            if not isinstance(ctx_obj, dict):
                ctx_obj = {"note": ctx}
        except Exception:
            ctx_obj = {"note": ctx}
        items.append({"id": rid, "requirementText": req, "context": ctx_obj})
    return items


def extract_fallback_sentences(text: str) -> List[Dict[str, Any]]:
    """
    Heuristik: Falls keine Tabelle erkannt wird, extrahiere Sätze in de/en mit Schlüsselbegriffen.
    """
    out: List[Dict[str, Any]] = []
    if not text:
        return out
    # Split sehr einfach: Zeilen, die wie Requirements aussehen
    # Schlüssel: soll, muss, shall, should
    key_re = re.compile(r'\b(soll|muss|shall|should)\b', re.IGNORECASE)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    idx = 1
    for ln in lines:
        if len(ln) < 12:
            continue
        if key_re.search(ln):
            out.append({"id": f"Rfb_{idx}", "requirementText": ln, "context": {}})
            idx += 1
    return out


def normalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    - Entferne Duplikate anhand requirementText (lower)
    - Stelle context als dict sicher
    - Sortiere stable nach ID/Reihenfolge
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        rt = str(it.get("requirementText") or "").strip()
        if not rt:
            continue
        k = rt.lower()
        if k in seen:
            continue
        seen.add(k)
        rid = str(it.get("id") or f"R{len(out) + 1}")
        ctx = it.get("context")
        if not isinstance(ctx, dict):
            # best effort normalisieren
            try:
                ctx = json.loads(str(ctx))
                if not isinstance(ctx, dict):
                    ctx = {}
            except Exception:
                ctx = {}
        out.append({"id": rid, "requirementText": rt, "context": ctx})
    # Sortierung: numerisch nach R#, dann fallback insertion order
    def sort_key(it: Dict[str, Any]) -> Tuple[int, str]:
        rid = str(it.get("id") or "")
        m = re.match(r'R(\d+)$', rid, re.IGNORECASE)
        if m:
            try:
                return (int(m.group(1)), rid)
            except Exception:
                return (10**9, rid)
        return (10**9, rid)
    out.sort(key=sort_key)
    return out


def quick_verify(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Leichte Heuristik zur Qualitätssicherung:
    - Länge > 20 Zeichen
    - enthält ein Verb (rough)
    - nicht rein strukturlose Headerzeilen
    """
    notes: List[str] = []
    verified: List[Dict[str, Any]] = []
    for it in items:
        rt = str(it.get("requirementText") or "")
        ok = True
        if len(rt) < 20:
            ok = False
        if not re.search(r'\b(soll|muss|shall|should|wird|werden|be|must)\b', rt, re.IGNORECASE):
            # Tolerant – keine harte Ablehnung, nur Note
            notes.append(f"weak:no_verb_like: {rt[:40]}")
        if ok:
            verified.append(it)
    if not verified and items:
        # gib zumindest die Items zurück, auch wenn heuristisch schwach
        verified = items
    return verified, notes


# -------------------------------------------------------
# Pipeline
# -------------------------------------------------------

def run_pipeline(query: str, top_k: int = 5, window: int = 2) -> Dict[str, Any]:
    """
    1) RAG: Top-Hit finden und sourceFile bestimmen
    2) volles Dokument laden
    3) Tabelle parsen; Fallback: Sätze
    4) normalisieren + quick verify
    """
    rag = tool_rag_search(query, top_k=top_k)
    hits = rag.get("hits") or []
    top1 = hits[0] if hits else None
    source = None
    if top1 and isinstance(top1, dict):
        p = top1.get("payload") or {}
        source = p.get("sourceFile") or p.get("source")
    if not source:
        # Kein Treffer – Rückgabe leer
        return {
            "query": query,
            "effectiveQuery": query,
            "topK": top_k,
            "window": window,
            "items": [],
            "agentNotes": ["no_source_selected"],
            "triggeredPolicies": []
        }

    full = tool_fetch_full_source(str(source))
    full_text = str(full.get("text") or "")

    items = parse_md_table(full_text)
    agent_notes: List[str] = []
    if not items:
        fb = extract_fallback_sentences(full_text)
        if fb:
            items = fb
            agent_notes.append("fallback:sentence_extraction")

    items_norm = normalize(items)
    items_ver, notes = quick_verify(items_norm)
    agent_notes.extend(notes)

    return {
        "query": query,
        "effectiveQuery": query,
        "topK": top_k,
        "window": window,
        "items": items_ver,
        "agentNotes": agent_notes,
        "triggeredPolicies": []
    }


# -------------------------------------------------------
# Endpoints
# -------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "backend": BACKEND_BASE_URL}


@app.post("/mine")
def mine(req: MineRequest = Body(...)) -> Dict[str, Any]:
    q = (req.query or "").strip()
    if not q:
        return {
            "error": "invalid_request",
            "message": "query fehlt"
        }
    try:
        out = run_pipeline(q, top_k=req.topK, window=req.window)
        return out
    except requests.HTTPError as he:
        try:
            txt = he.response.text
        except Exception:
            txt = str(he)
        return {"error": "upstream_http_error", "message": txt}
    except Exception as e:
        return {"error": "internal_error", "message": str(e)}


# -------------------------------------------------------
# Team-based Mining (LLM Agents, ohne Heuristik-Fallback)
# -------------------------------------------------------

class TeamMineRequest(BaseModel):
    query: str = Field(..., description="User-Query")
    topK: int = Field(default=5)
    window: int = Field(default=2)
    maxChunks: int = Field(default=100, description="Max. Anzahl Chunks, die vom Top-Dokument verarbeitet werden")


def _env_model_cfg() -> Tuple[str, float]:
    # Bevorzugt MODELs aus ENV: MODEL_NAME oder OPENAI_MODEL; Default auf gpt-4o-mini
    model = os.getenv("MODEL_NAME") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    # Temperatur aus ARCH_TEMPERATURE oder OPENAI_TEMPERATURE; Default 0.2
    temperature = float(os.getenv("ARCH_TEMPERATURE", os.getenv("OPENAI_TEMPERATURE", "0.2")))
    return model, temperature


def _agent_base_guard() -> str:
    return (
        "General rules for all agents:\n"
        "- Keep outputs concise and structured.\n"
        "- Requirements MUST NOT include IDs; IDs (R1..Rn) werden im Backend zugewiesen.\n"
        "- Output STRICT JSON (keine Prosa, keine Erklärungen), UTF-8, ohne Kommentare.\n"
        "- JSON-Schema für Ausgabe: [{\"requirementText\": string, \"context\": object?}]\n"
        "- context wenn unbekannt: {}.\n"
    )


def _agent_extractor_prompt() -> str:
    return (
        "Task: Extract atomic software requirements from the given input text.\n"
        "- Input MAY contain Markdown table rows with this schema: '| Rn | requirementText | context |'.\n"
        "- If a Markdown table is present, parse each data row and extract requirementText; try to parse 'context' as JSON object; if parsing fails, use {}.\n"
        "- If no table is present, extract concrete, actionable requirements (functional or non-functional) from prose.\n"
        "- Skip headings, table headers, introductory prose, and duplicates.\n"
        "- Output STRICT JSON array ONLY with items shaped as: [{\"requirementText\": string, \"context\": {}}]\n"
        "- Do NOT include IDs; the backend assigns R1..Rn.\n"
        "- Keep requirementText preferably to a single sentence.\n"
    )


def _agent_normalizer_prompt() -> str:
    return (
        "Task: Normalize and deduplicate requirements:\n"
        "- Input is an array of {requirementText, context} items.\n"
        "- Remove near-duplicates (case-insensitive).\n"
        "- Ensure context is an object; if absent, set {}.\n"
        "- Output STRICT JSON array only with same schema.\n"
    )


def _agent_auditor_prompt() -> str:
    return (
        "Task: Audit JSON for schema compliance and minimal quality:\n"
        "- Ensure every item has non-empty requirementText (>= 8 chars).\n"
        "- Ensure context is an object.\n"
        "- Output STRICT JSON array only with the same schema.\n"
    )


def _extract_first_json_array(text: str) -> List[Dict[str, Any]]:
    import json as _json
    if not text:
        return []
    # Fast path: direct JSON
    try:
        data = _json.loads(text)
        return data if isinstance(data, list) else []
    except Exception:
        pass
    # Fenced code block or mixed text - try to locate first JSON array
    s = text
    lb = s.find("[")
    rb = s.rfind("]")
    if lb != -1 and rb != -1 and rb > lb:
        snippet = s[lb:rb+1]
        try:
            data = _json.loads(snippet)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _assign_sequential_ids(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, it in enumerate(items, start=1):
        rt = str(it.get("requirementText") or "").strip()
        if not rt:
            continue
        ctx = it.get("context")
        if not isinstance(ctx, dict):
            ctx = {}
        out.append({"id": f"R{i}", "requirementText": rt, "context": ctx})
    return out


def _build_markdown_table(items: List[Dict[str, Any]]) -> str:
    import json as _json
    lines: List[str] = []
    lines.append("| id | requirementText | context |")
    lines.append("|----|------------------|---------|")
    for it in items:
        rid = str(it.get("id") or "").strip()
        rt = str(it.get("requirementText") or "").strip().replace("\n", " ").strip()
        ctx = it.get("context")
        if not isinstance(ctx, dict):
            ctx = {}
        ctxs = _json.dumps(ctx, ensure_ascii=False)
        lines.append(f"| {rid} | {rt} | {ctxs} |")
    return "\n".join(lines)

def _agent_mine_doc_with_autogen(full_text: str) -> List[Dict[str, Any]]:
    """
    Doc-Level Extraktion mit einem kleinen Agent-Team (Extractor -> Normalizer -> Auditor).
    Erwartet den vollständigen Dokumenttext (inkl. Markdown-Tabellen) und liefert
    eine Liste von Objekten mit Schema: [{ "requirementText": str, "context": {} }].
    Kein Regex-/Heuristik-Fallback – ausschließlich LLM-Team.
    """
    try:
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.teams import RoundRobinGroupChat

        model, temperature = _env_model_cfg()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []

        client = OpenAIChatCompletionClient(model=model, temperature=temperature, api_key=api_key)

        extractor = AssistantAgent(
            "Extractor",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_extractor_prompt(),
        )
        normalizer = AssistantAgent(
            "Normalizer",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_normalizer_prompt(),
        )
        auditor = AssistantAgent(
            "Auditor",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_auditor_prompt(),
        )

        team = RoundRobinGroupChat(
            [extractor, normalizer, auditor],
            max_turns=int(os.getenv("MINE_TEAM_MAX_TURNS", "3")),
        )

        task = (
            "FULL_DOCUMENT_START\n"
            f"{full_text}\n"
            "FULL_DOCUMENT_END\n"
            "You MUST return a STRICT JSON array only.\n"
            "If the input contains a Markdown table with header '| id | requirementText | context |', you MUST parse every data row and output items accordingly.\n"
            "Parse 'context' as a JSON object when possible; if parsing fails, use {}.\n"
            "Output schema: [{\"requirementText\": string, \"context\": {}}]\n"
        )

        run_fn = getattr(team, "run", None)
        final_text = ""
        if callable(run_fn):
            maybe = run_fn(task=task)

            def _as_text(obj: Any) -> str:
                try:
                    if isinstance(obj, str):
                        return obj
                    parts: List[str] = []
                    for attr in ("text", "content", "final_text"):
                        val = getattr(obj, attr, None)
                        if isinstance(val, str) and val:
                            parts.append(val)
                    for attr in ("messages", "history", "chat_history"):
                        seq = getattr(obj, attr, None)
                        if isinstance(seq, (list, tuple)):
                            for m in seq:
                                if isinstance(m, str):
                                    parts.append(m)
                                else:
                                    for a2 in ("text", "content"):
                                        v2 = getattr(m, a2, None)
                                        if isinstance(v2, str) and v2:
                                            parts.append(v2)
                    s = "\n".join(p for p in parts if p)
                    return s or str(obj)
                except Exception:
                    return str(obj)

            final_text = _as_text(maybe)

            # Debug-Ausgabe für Doc-Level Agenten-Output
            if os.getenv("AGENT_DEBUG", "0") == "1":
                try:
                    print("AGENT_DEBUG: doc_final_text_len=", len(final_text))
                    print("AGENT_DEBUG: doc_final_text_sample=", (final_text or "")[:500])
                except Exception:
                    pass

        items = _extract_first_json_array(final_text)
        out: List[Dict[str, Any]] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            rt = str(it.get("requirementText") or "").strip()
            if not rt:
                continue
            ctx = it.get("context")
            if not isinstance(ctx, dict):
                ctx = {}
            out.append({"requirementText": rt, "context": ctx})
        return out
    except Exception:
        return []






def _agent_mine_chunk_with_autogen(chunk_text: str) -> List[Dict[str, Any]]:
    """
    Führt eine kleine RoundRobin-Agentenrunde (Extractor -> Normalizer -> Auditor) aus.
    Erwartet reinen Chunk-Text, liefert Liste von {requirementText, context}.
    Bei Fehlern/Importproblemen wird leere Liste zurückgegeben (kein Heuristik-Fallback!).
    """
    try:
        # Lazy imports, damit der Worker auch ohne Autogen startbar ist.
        from autogen_ext.models.openai import OpenAIChatCompletionClient
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.teams import RoundRobinGroupChat

        model, temperature = _env_model_cfg()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []

        client = OpenAIChatCompletionClient(model=model, temperature=temperature, api_key=api_key)

        extractor = AssistantAgent(
            "Extractor",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_extractor_prompt(),
        )
        normalizer = AssistantAgent(
            "Normalizer",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_normalizer_prompt(),
        )
        auditor = AssistantAgent(
            "Auditor",
            model_client=client,
            system_message=_agent_base_guard() + "\n" + _agent_auditor_prompt(),
        )

        team = RoundRobinGroupChat(
            [extractor, normalizer, auditor],
            max_turns=int(os.getenv("MINE_TEAM_MAX_TURNS", "3")),
        )

        task = (
            "INPUT_CHUNK_START\n"
            f"{chunk_text}\n"
            "INPUT_CHUNK_END\n"
            "You MUST return ONLY a STRICT JSON array with items shaped as [{\"requirementText\": string, \"context\": {}}]. No code fences or prose.\n"
        )

        # Synchronous run (returns final aggregated text or messages, depending on version)
        result = getattr(team, "run", None)
        final_text = ""
        if callable(result):
            maybe = result(task=task)

            def _as_text(obj: Any) -> str:
                try:
                    if isinstance(obj, str):
                        return obj
                    parts: List[str] = []
                    for attr in ("text", "content", "final_text"):
                        val = getattr(obj, attr, None)
                        if isinstance(val, str) and val:
                            parts.append(val)
                    for attr in ("messages", "history", "chat_history"):
                        seq = getattr(obj, attr, None)
                        if isinstance(seq, (list, tuple)):
                            for m in seq:
                                if isinstance(m, str):
                                    parts.append(m)
                                else:
                                    for a2 in ("text", "content"):
                                        v2 = getattr(m, a2, None)
                                        if isinstance(v2, str) and v2:
                                            parts.append(v2)
                    s = "\n".join(p for p in parts if p)
                    return s or str(obj)
                except Exception:
                    return str(obj)

            final_text = _as_text(maybe)
        else:
            # Fallback: try single agent if RoundRobinGroupChat API differs
            single = AssistantAgent(
                "ReqMiner",
                model_client=client,
                system_message=_agent_base_guard() + "\n" + _agent_extractor_prompt(),
            )
            one = getattr(single, "run", None)
            if callable(one):
                res = one(task=f"Extract from chunk:\n{chunk_text}")
                final_text = res if isinstance(res, str) else getattr(res, "text", "") or getattr(res, "content", "")
            else:
                final_text = ""

        if os.getenv("AGENT_DEBUG", "0") == "1":
            try:
                print("AGENT_DEBUG: chunk_final_text_len=", len(final_text))
                print("AGENT_DEBUG: chunk_final_text_sample=", (final_text or "")[:500])
            except Exception:
                pass

        items = _extract_first_json_array(final_text)
        # Post-shape: ensure objects and context dict
        out: List[Dict[str, Any]] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            rt = str(it.get("requirementText") or "").strip()
            if not rt:
                continue
            ctx = it.get("context")
            if not isinstance(ctx, dict):
                ctx = {}
            out.append({"requirementText": rt, "context": ctx})
        return out
    except Exception:
        # Kein Fallback auf Regex/Heuristik, bewusst leise leeren Satz liefern
        return []


def _team_mine_requirements_over_chunks(query: str, top_k: int, window: int, max_chunks: int) -> Tuple[List[Dict[str, Any]], List[str], Optional[str]]:
    """
    - RAG Top-1 Quelle bestimmen
    - Alle Chunks laden (vector/source/full)
    - Pro Chunk Agents laufen lassen (ohne Heuristik-Fallback)
    - Dedupe/Normalize, IDs R1..Rn zuweisen
    """
    agent_notes: List[str] = []
    try:
        rag = tool_rag_search(query, top_k=top_k)
        hits = rag.get("hits") or []
        top1 = hits[0] if hits else None
        source = None
        if top1 and isinstance(top1, dict):
            p = top1.get("payload") or {}
            source = p.get("sourceFile") or p.get("source")
        if not source:
            agent_notes.append("no_source_selected")
            return [], agent_notes, None

        full = tool_fetch_full_source(str(source))
        chunks = full.get("chunks") or []
        # sort by chunkIndex
        try:
            chunks.sort(key=lambda c: int(c.get("chunkIndex")))
        except Exception:
            pass

        items_all: List[Dict[str, Any]] = []
        processed = 0

        # Doc-level pass über gesamten Volltext (inkl. Markdown-Tabellen)
        full_text = str(full.get("text") or "")
        if full_text.strip():
            # Optionaler deterministischer Parse vor dem LLM-Team (kein heuristischer Fallback, nur Markdown-Tabelle)
            if os.getenv("MINE_TEAM_DOC_PARSE_FIRST", "1") == "1":
                pre = parse_md_table(full_text)
                if pre:
                    pre2: List[Dict[str, Any]] = []
                    for it in pre:
                        rt = str(it.get("requirementText") or "").strip()
                        if not rt:
                            continue
                        ctx = it.get("context")
                        if not isinstance(ctx, dict):
                            ctx = {}
                        pre2.append({"requirementText": rt, "context": ctx})
                    if pre2:
                        items_all.extend(pre2)
                        agent_notes.append("team:doc_parse")

            # LLM-Team nur ausführen, wenn bisher noch nichts gesammelt
            if not items_all:
                try:
                    doc_items = _agent_mine_doc_with_autogen(full_text)
                    if doc_items:
                        items_all.extend(doc_items)
                        agent_notes.append("team:doc_level")
                except Exception as e:
                    agent_notes.append(f"team:doc_error:{str(e)[:200]}")

        # Chunk-level pass nur, wenn Doc-Level nichts lieferte
        if not items_all:
            for c in chunks:
                if processed >= max_chunks:
                    break
                t = str(c.get("text") or "")
                if not t.strip():
                    continue
                # kleine Guard, um Vorworte/Headers zu überspringen
                if len(t.strip()) < 20:
                    continue
                try:
                    mined = _agent_mine_chunk_with_autogen(t)
                except Exception as e:
                    agent_notes.append(f"team:chunk_error:{processed+1}:{str(e)[:120]}")
                    mined = []
                if mined:
                    items_all.extend(mined)
                processed += 1

        # Normalize/Dedupe (nutzt bestehende Helper)
        items_norm = normalize(items_all)
        # Keine Heuristik-Fallbacks, aber leichte Verifikation als Hinweise zulässig
        items_ver, notes = quick_verify(items_norm)
        agent_notes.append(f"team:chunks_processed={processed}")
        agent_notes.extend(notes)

        # IDs neu (R1..Rn)
        final_items = _assign_sequential_ids(items_ver)
        return final_items, agent_notes, str(source)
    except Exception as e:
        return [], [f"team:error:{str(e)}"], None


@app.post("/mine_team")
def mine_team(req: TeamMineRequest = Body(...)) -> Dict[str, Any]:
    """
    Team-basiertes Mining ohne Heuristik-Fallback.
    Body: { query: string, topK?: int, window?: int, maxChunks?: int }
    Response: { query, effectiveQuery, topK, window, items, agentNotes, triggeredPolicies }
    """
    q = (req.query or "").strip()
    if not q:
        return {"error": "invalid_request", "message": "query fehlt"}
    items, notes, _source = _team_mine_requirements_over_chunks(q, req.topK, req.window, req.maxChunks)
    return {
        "query": q,
        "effectiveQuery": q,
        "topK": req.topK,
        "window": req.window,
        "items": items,
        "agentNotes": notes,
        "triggeredPolicies": [],
    }


class PrepParserDocRequest(BaseModel):
    query: str = Field(..., description="User-Query")
    topK: int = Field(default=5)
    window: int = Field(default=2)
    maxChunks: int = Field(default=100)


@app.post("/prep_parser_doc")
def prep_parser_doc(req: PrepParserDocRequest = Body(...)) -> Dict[str, Any]:
    """
    Erzeugt ein Parser-taugliches Markdown-Dokument (Tabelle) nur aus Agent-Ergebnissen (ohne Heuristik-Fallback).
    Body: { query, topK?, window?, maxChunks? }
    Response: { query, sourceFile, rowCount, markdown }
    """
    q = (req.query or "").strip()
    if not q:
        return {"error": "invalid_request", "message": "query fehlt"}
    items, notes, source = _team_mine_requirements_over_chunks(q, req.topK, req.window, req.maxChunks)
    md = _build_markdown_table(items)
    return {
        "query": q,
        "sourceFile": source,
        "rowCount": len(items),
        "markdown": md,
        "agentNotes": notes,
    }
if __name__ == "__main__":
    # Lokaler Start (entwicklungszwecke)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")