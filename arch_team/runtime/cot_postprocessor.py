# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Dict, List, Tuple, Any


_SECTION_KEYS = ["THOUGHTS", "PLAN", "EVIDENCE", "FINAL_ANSWER", "CRITIQUE", "DECISION", "TOOL_CALL"]

# Tolerante Regex: Abschnittsüberschriften wie "THOUGHTS:", "final answer -", "Decision", optionaler Whitespace/Fences
_SECTION_RE = re.compile(
    r"""
    ^\s*
    (?P<header>
        (?:THOUGHTS?|PLAN|EVIDENCE|FINAL[_\s-]?ANSWER|CRITIQUE|DECISION|TOOL[_\s-]?CALL)
    )
    \s*[:\-]?\s*
    (?P<inline>.+)?   # optional Inline-Inhalt auf derselben Zeile
    $                 # Zeilenende
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


def _normalize_key(header: str) -> str:
    h = header.upper().replace(" ", "_").replace("-", "_")
    if h.startswith("FINAL_ANSWER"):
        return "FINAL_ANSWER"
    if h.startswith("TOOL_CALL"):
        return "TOOL_CALL"
    return h


def extract_blocks(text: str) -> Dict[str, str]:
    """
    Extrahiert CoT-Blöcke aus freiem LLM-Text.
    Erlaubte Keys: THOUGHTS, PLAN, EVIDENCE, FINAL_ANSWER, CRITIQUE, DECISION

    - Tolerant gegenüber Groß-/Kleinschreibung, '-' oder ' ' in FINAL ANSWER
    - Unterstützt Inhalte bis zum nächsten erkannten Header oder Textende
    - Entfernt umschließende Code-Fences ```...```
    """
    if not isinstance(text, str):
        return {}

    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        # Kein strukturierter Output – alles als FINAL_ANSWER behandeln
        return {"FINAL_ANSWER": text.strip()}

    blocks: Dict[str, str] = {}
    for i, m in enumerate(matches):
        key = _normalize_key(m.group("header"))
        inline = m.groupdict().get("inline")
        if inline and str(inline).strip():
            chunk = str(inline).strip()
            # Inline-Fall: trotzdem Fences entfernen (z. B. "EVIDENCE: ```x```")
            chunk = _strip_fences(chunk)
        else:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()

            # Evidence: maximale Robustheit für ``` fenced blocks
            if key == "EVIDENCE":
                # 1) Wenn im lokalen Chunk bereits zwei Fences sind, nimm Inhalt dazwischen
                if chunk.count("```") >= 2:
                    lines = chunk.splitlines()
                    first_f = next((i for i, l in enumerate(lines) if l.lstrip().startswith("```")), None)
                    last_f = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].lstrip().startswith("```")), None)
                    if first_f is not None and last_f is not None and last_f > first_f:
                        chunk = "\n".join(lines[first_f + 1 : last_f]).strip()
                    else:
                        chunk = _strip_fences(chunk)
                else:
                    # 2) Regex im lokalen Abschnitt (zwischen EVIDENCE-Header und nächstem Header)
                    local_text = text[start:end]
                    m_fenced = re.search(r"```[^\r\n]*\r?\n(?P<body>.*?)\r?\n```", local_text, re.DOTALL)
                    if m_fenced:
                        chunk = (m_fenced.group("body") or "").strip()
                    else:
                        # 3) Fallback auf generisches Fence-Stripping
                        chunk = _strip_fences(chunk)
            else:
                # Nicht-EVIDENCE: generische Fence-Entfernung
                chunk = _strip_fences(chunk)

        blocks[key] = chunk

    # Post-Fix: Falls EVIDENCE leer oder nur ``` ist, extrahiere Body direkt aus dem Originaltext
    if "EVIDENCE" in blocks and (blocks["EVIDENCE"].strip() == "" or blocks["EVIDENCE"].strip() == "```"):
        m_ev = re.search(r"```[^\r\n]*\r?\n(?P<body>.*?)\r?\n```", text, re.DOTALL)
        if m_ev:
            blocks["EVIDENCE"] = (m_ev.group("body") or "").strip()

    return blocks


def _strip_fences(s: str) -> str:
    s = s.strip()
    # Schneller Pfad: rohes Slicing zwischen erstem und letztem ```
    if "```" in s:
        _first = s.find("```")
        _last = s.rfind("```")
        if _last > _first + 3:
            tail = s[_first + 3 : _last]
            # Normalisiere Zeilenenden
            tail = tail.replace("\r\n", "\n")
            body = ""
            if tail.startswith("\n"):
                # Kein Sprach-Token, direkt Inhalt nach der ersten Newline
                body = tail[1:]
            else:
                # Zeile bis zum ersten Zeilenumbruch als mögliches Sprach-Token interpretieren
                nl = tail.find("\n")
                if nl != -1:
                    first_line = tail[:nl].strip()
                    # Wenn first_line nicht leer ist, als Sprach-Token behandeln und verwerfen
                    body = tail[nl + 1 :] if first_line != "" else tail[nl + 1 :]
                else:
                    # Kein Newline im Tail, dann ist der gesamte Tail der Body
                    body = tail
            body = body.strip()
            if body:
                return body
    # Sammle Kandidaten aus allen eingebetteten fenced-Blöcken
    block_re = re.compile(
        r"```[a-zA-Z0-9_-]*\s*(?:\r?\n)(?P<body>.*?)(?:\r?\n)```",
        re.DOTALL,
    )
    candidates = []
    for m in block_re.finditer(s):
        body = (m.group("body") or "").strip()
        if body:
            candidates.append(body)
        else:
            # Auch leere Bodys als Kandidaten aufnehmen (zur Not später Fallback)
            candidates.append(body)

    if candidates:
        # Nimm den längsten (robust bei mehreren Blöcken; vermeidet leere Treffer)
        best = max(candidates, key=lambda x: len(x or ""))
        if best:
            return best

    # Strikter Volltreffer
    full_match_re = re.compile(
        r"^\s*```[a-zA-Z0-9_-]*\s*(?:\r?\n)(?P<body>.*?)(?:\r?\n)```(?:\s*)$",
        re.DOTALL | re.VERBOSE,
    )
    m2 = full_match_re.match(s)
    if m2:
        body = (m2.group("body") or "").strip()
        if body:
            return body

    # Zeilenbasierter Fallback: entferne erstes/letztes Fence, falls vorhanden
    lines = s.splitlines()
    # Finde erste/letzte Fence-Zeile robust (mit Leerzeichen)
    first = None
    last = None
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            first = idx
            break
    for idx in range(len(lines) - 1, -1, -1):
        if lines[idx].lstrip().startswith("```"):
            last = idx
            break
    if first is not None and last is not None and last > first:
        inner = "\n".join(lines[first + 1 : last]).strip()
        return inner

    # Letzter Fallback: entferne alle Fence-Zeilen und gib Rest zurück
    if "```" in s:
        stripped_lines = [ln for ln in s.splitlines() if not ln.lstrip().startswith("```")]
        candidate = "\n".join(stripped_lines).strip()
        if candidate:
            return candidate

    return s


def ui_payload(blocks_or_list: Any) -> str:
    """
    Liefert den UI-sicheren Text (nur FINAL_ANSWER oder DECISION).
    - Wenn Liste von Block-Dicts: nimmt den letzten vorhandenen FINAL_ANSWER, sonst den letzten DECISION
    - Wenn ein einzelnes Dict: bevorzugt FINAL_ANSWER, sonst DECISION
    """
    if isinstance(blocks_or_list, list):
        last_final = _find_last(blocks_or_list, "FINAL_ANSWER")
        if last_final:
            return last_final
        last_dec = _find_last(blocks_or_list, "DECISION")
        if last_dec:
            return last_dec
        # Fallback: leer
        return ""
    elif isinstance(blocks_or_list, dict):
        if "FINAL_ANSWER" in blocks_or_list and blocks_or_list["FINAL_ANSWER"]:
            return str(blocks_or_list["FINAL_ANSWER"])
        if "DECISION" in blocks_or_list and blocks_or_list["DECISION"]:
            return str(blocks_or_list["DECISION"])
        return ""
    else:
        return ""


def _find_last(lst: List[Dict[str, str]], key: str) -> str:
    for b in reversed(lst):
        v = b.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _extract_tool_calls_from_blocks(blocks: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Versucht TOOL_CALL JSON-Blöcke tolerant zu parsen. Liefert Liste von Dicts.
    """
    calls: List[Dict[str, Any]] = []
    raw = blocks.get("TOOL_CALL", "") if isinstance(blocks, dict) else ""
    if not raw:
        return calls
    # Suche JSON-Objekte im Text
    json_re = re.compile(r"\{.*?\}", re.DOTALL)
    import json
    for m in json_re.finditer(raw):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "name" in obj:
                calls.append(obj)
        except Exception:
            continue
    return calls


def to_trace_record(blocks_or_list: Any, meta: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Baut ein Trace-Record-Objekt (für Qdrant Trace Sink).
    CoT-Privacy gilt nur für UI – im Trace dürfen THOUGHTS/CRITIQUE liegen.
    Zusätzlich: erkennt TOOL_CALL-Blöcke und legt sie in meta.tool_calls ab.
    """
    meta = dict(meta or {})
    # Vereinheitliche zu einem Dict
    if isinstance(blocks_or_list, list):
        # Merge bevorzugt letzte Werte
        merged: Dict[str, str] = {}
        for b in blocks_or_list:
            for k in _SECTION_KEYS:
                if k in b and b[k]:
                    merged[k] = b[k]
        blocks = merged
    elif isinstance(blocks_or_list, dict):
        blocks = {k: v for k, v in blocks_or_list.items() if isinstance(v, str)}
    else:
        blocks = {"FINAL_ANSWER": str(blocks_or_list)}

    # TOOL_CALLS extrahieren
    tool_calls = _extract_tool_calls_from_blocks(blocks)
    if tool_calls:
        meta = {**meta, "tool_calls": tool_calls}

    out = {
        "thoughts": blocks.get("THOUGHTS", ""),
        "plan": blocks.get("PLAN", ""),
        "evidence": blocks.get("EVIDENCE", ""),
        "final": blocks.get("FINAL_ANSWER", ""),
        "critique": blocks.get("CRITIQUE", ""),
        "decision": blocks.get("DECISION", ""),
        "meta": meta,
    }
    return out