# -*- coding: utf-8 -*-
"""
KORRIGIERTE API V2 - LangExtract-Fixes
Teil 1: Imports und Hilfsfunktionen
"""

import os
import time
import logging
import concurrent.futures as futures
from typing import Any, Dict, List, Tuple
import requests
import textwrap
import re

from flask import Blueprint, jsonify, request, g, make_response
from backend_app.logging_ext import _json_log as json_log

from backend_app import settings
from backend_app.db import get_db, load_criteria, get_latest_rewrite_row_for_eval, get_latest_evaluation_by_checksum
from backend_app.llm import llm_evaluate, llm_suggest, llm_rewrite, llm_apply_with_suggestions
from backend_app.utils import compute_verdict, sha256_text, weighted_score, parse_requirements_md, chunked

# RAG/Vector-Ingest
from backend_app.ingest import extract_texts, chunk_payloads
from backend_app.embeddings import build_embeddings, get_embeddings_dim
from backend_app.vector_store import (
    get_qdrant_client,
    upsert_points,
    search as vs_search,
    list_collections as vs_list_collections,
    healthcheck as vs_health,
    fetch_window_by_source_and_index,
    reset_collection as vs_reset_collection,
)
from backend_app.memory import MemoryStore
from backend_app.rag import StructuredRequirement

api_bp = Blueprint("api", __name__)

# Lightweight Memory (Agent policies/outcomes)
_mem_store = MemoryStore()

# =========================
# KORRIGIERTE LANGEXTRACT-HILFSFUNKTIONEN
# =========================

def split_paragraphs(text: str) -> list[str]:
    """Aufteilen an Leerzeilen (Markdown-Absätze)"""
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]

def build_chunks_absatz(text: str, chunk_size: int = 5000, overlap: int = 400) -> list[str]:
    """Erzeugt überlappende Chunks basierend auf Absätzen"""
    paras = split_paragraphs(text)
    chunks: list[str] = []
    cur = ""
    for para in paras:
        candidate = (cur + ("\n\n" if cur else "") + para)
        if len(candidate) <= chunk_size:
            cur = candidate
        else:
            if cur:
                chunks.append(cur)
                tail = cur[-overlap:] if overlap > 0 and len(cur) > overlap else ""
                cur = (tail + ("\n\n" if tail else "") + para)
            else:
                # Einzelner Absatz ist größer als chunk_size: hart teilen
                start = 0
                while start < len(para):
                    end = min(start + chunk_size, len(para))
                    piece = para[start:end]
                    chunks.append(piece)
                    start = max(end - overlap, end)
    if cur:
        chunks.append(cur)
    return chunks

def _lx_default_config() -> dict:
    """Default-Konfiguration ohne SDK-Abhängigkeit (reine Dict-Beispiele)."""
    return {
        "prompt_description": textwrap.dedent("""\
            Extrahiere Anforderungen aus Software-Requirements in strukturierter Form.
            Regeln:
            - Nutze ausschließlich exakte Textspannen aus der Quelle (keine Paraphrasen).
            - Überschneide Extraktionen nicht.
            - Bevorzuge prägnante, aussagekräftige Textspannen.
            - Halte dich strikt an das Schema unten.
            - Falls ein Feld nicht sicher bestimmbar ist, lasse es leer/weg.

            Zielklassen und empfohlene Attribute:
            - requirement: attributes: priority (low/medium/high), category, rationale
            - actor: attributes: role (end_user/admin/system/external)
            - capability: attributes: area (module/feature)
            - constraint: attributes: type (security/compliance/performance/availability/other)
            - acceptance_criterion: attributes: kind (functional/nonfunctional)
            - relation: attributes: type (depends_on/conflicts_with/relates_to)

            Ausgabe: Erzeuge eine robuste, konsistente Struktur mit klaren Klassen und sinnvollen Attributen.
            """),
        "examples": [
            {
                "text": "Requirement: The system shall allow users to reset passwords within 5 minutes after request. Constraint: MFA is mandatory. Actor: user",
                "extractions": [
                    {"extraction_class": "requirement", "extraction_text": "allow users to reset passwords", "attributes": {"priority": "high", "category": "account_management", "rationale": "security usability"}},
                    {"extraction_class": "constraint", "extraction_text": "MFA is mandatory", "attributes": {"type": "security"}},
                    {"extraction_class": "actor", "extraction_text": "user", "attributes": {"role": "end_user"}}
                ]
            },
            {
                "text": "| TP-001 | Das Tool MUSS die Antwortzeit messen | {priority: must, category: performance_monitoring}",
                "extractions": [
                    {"extraction_class": "requirement", "extraction_text": "Das Tool MUSS die Antwortzeit messen", "attributes": {"priority": "must", "category": "performance_monitoring"}}
                ]
            },
            {
                "text": "Bei Überschreitung von 80% Ressourcenauslastung SOLL eine Benachrichtigung erfolgen",
                "extractions": [
                    {"extraction_class": "constraint", "extraction_text": "Bei Überschreitung von 80% Ressourcenauslastung SOLL eine Benachrichtigung erfolgen", "attributes": {"type": "performance"}}
                ]
            }
        ],
    }

# =========================
# WEITERE HILFSFUNKTIONEN
# =========================

def _normalize_lx_result(res, chunk_text: str):
    """Robuste Normalisierung von LangExtract-Ergebnissen"""
    try:
        if hasattr(res, "to_dict"):
            data = res.to_dict()
        elif isinstance(res, dict):
            data = res
        else:
            data = getattr(res, "__dict__", {}) or {}

        exts_raw = []
        if isinstance(data, dict):
            if isinstance(data.get("extractions"), list):
                exts_raw.extend(data.get("extractions") or [])
            docs = data.get("documents") or data.get("items") or []
            if isinstance(docs, list):
                for d in docs:
                    if isinstance(d, dict) and isinstance(d.get("extractions"), list):
                        exts_raw.extend(d.get("extractions") or [])

        out = []
        intervals = []
        n = len(chunk_text or "")

        def _coerce_int(v, default=0):
            try:
                return int(v)
            except Exception:
                return default

        for e in exts_raw or []:
            try:
                get = (lambda k: (e.get(k) if isinstance(e, dict) else getattr(e, k, None)))

                ec = get("extraction_class") or get("cls") or get("class") or get("label")
                et = get("extraction_text") or get("text") or get("span_text")

                ci = get("char_interval") or get("char_span") or get("span") or get("interval")
                s, epos = None, None
                if isinstance(ci, dict):
                    s = _coerce_int(ci.get("start_pos", ci.get("start")))
                    epos = _coerce_int(ci.get("end_pos", ci.get("end")))

                if (s is None or epos is None or epos <= s) and isinstance(et, str) and et.strip():
                    idx = (chunk_text or "").find(et)
                    if idx >= 0:
                        s = idx
                        epos = idx + len(et)

                s = 0 if s is None else max(0, min(s, n))
                epos = 0 if epos is None else max(0, min(epos, n))
                if epos < s:
                    s, epos = epos, s

                al = get("alignment_status")
                attrs = get("attributes")
                if not isinstance(attrs, dict):
                    attrs = {}

                if isinstance(ec, str) and isinstance(et, str) and et.strip() and epos > s:
                    out.append({
                        "extraction_class": ec,
                        "extraction_text": et,
                        "char_interval": {"start_pos": s, "end_pos": epos},
                        "alignment_status": (al if isinstance(al, (str, int, float, bool)) else (str(al) if al is not None else "match_exact")),
                        "attributes": attrs,
                    })
                    intervals.append((s, epos))
            except Exception as ex_err:
                logging.debug(f"Error processing extraction: {ex_err}")
                continue

        # Coverage berechnen
        try:
            merged = []
            for st, en in sorted(intervals):
                if not merged:
                    merged.append((st, en))
                else:
                    pst, pen = merged[-1]
                    if st <= pen:
                        merged[-1] = (pst, max(pen, en))
                    else:
                        merged.append((st, en))
            covered = sum(en - st for st, en in merged)
            ratio = float(covered) / float(n) if n > 0 else 0.0
        except Exception:
            covered, ratio = 0, 0.0

        return out, covered, ratio
    except Exception as norm_err:
        logging.error(f"Error in _normalize_lx_result: {norm_err}")
        return [], 0, 0.0

# =========================
# FORTSETZUNG IN TEIL 2
# =========================