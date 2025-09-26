# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def weighted_score(details: List[Dict[str, Any]], crits: List[Dict[str, Any]]) -> float:
    weights = {c["key"]: float(c.get("weight") or 1.0) for c in crits}
    total_w = sum(weights.values()) or 1.0
    s = 0.0
    for d in details:
        k = d["criterion"]
        sc = float(d.get("score") or 0.0)
        s += sc * weights.get(k, 1.0)
    return max(0.0, min(1.0, s / total_w))


def compute_verdict(score: float, threshold: float = 0.7) -> str:
    return "pass" if score >= threshold else "fail"


def parse_context_cell(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"note": s}


def parse_requirements_md(md_path: str) -> List[Dict[str, str]]:
    """
    Erwartetes Format: Markdown-Tabelle mit Header
    | id | requirementText | context |
    |----|------------------|---------|
    | R1 | ...              | {...}   |
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown-Datei nicht gefunden: {md_path}")
    rows: List[Dict[str, str]] = []
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f.readlines()]

    header_idx = -1
    headers: List[str] = []
    for i, ln in enumerate(lines):
        if "|" in ln and "id" in ln and "requirementText" in ln:
            headers = [h.strip().strip("`") for h in ln.strip().strip("|").split("|")]
            header_idx = i
            break
    if header_idx == -1 or len(headers) < 2:
        raise ValueError("Konnte keinen gültigen Tabellen-Header finden (id | requirementText | context).")

    for j in range(header_idx + 1, len(lines)):
        ln = lines[j].strip()
        if not ln or "|" not in ln:
            continue
        # Trenner-Zeilen mit --- überspringen
        if set(ln.replace("|", "").replace(":", "").replace("-", "").strip()) == set():
            continue
        cells = [c.strip().strip("`") for c in ln.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        data = dict(zip(headers, cells))
        data.setdefault("context", "")
        rows.append(
            {
                "id": data.get("id", ""),
                "requirementText": data.get("requirementText", ""),
                "context": data.get("context", ""),
            }
        )
    return rows


def chunked(seq: List[Any], size: int) -> List[List[Any]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]