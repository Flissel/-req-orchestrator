# -*- coding: utf-8 -*-
"""
KORRIGIERTE LangExtract-Implementierung für backend_app/api.py
Diese Datei enthält die Fixes für die LangExtract-Integration basierend auf dev/run_extract.py
"""

from __future__ import annotations

import os
import time
import logging
import concurrent.futures as futures
from typing import Any, Dict, List, Tuple
import requests
import textwrap
import re

from flask import Blueprint, jsonify, request, g, make_response
from .logging_ext import _json_log as json_log

from . import settings
from .db import get_db, load_criteria, get_latest_rewrite_row_for_eval, get_latest_evaluation_by_checksum
from .llm import llm_evaluate, llm_suggest, llm_rewrite, llm_apply_with_suggestions
from .utils import compute_verdict, sha256_text, weighted_score, parse_requirements_md, chunked

# RAG/Vector-Ingest
from .ingest import extract_texts, chunk_payloads
from .embeddings import build_embeddings, get_embeddings_dim
from .vector_store import (
    get_qdrant_client,
    upsert_points,
    search as vs_search,
    list_collections as vs_list_collections,
    healthcheck as vs_health,
    fetch_window_by_source_and_index,
    reset_collection as vs_reset_collection,
)
from .memory import MemoryStore
from .rag import StructuredRequirement

api_bp = Blueprint("api", __name__)

# Lightweight Memory (Agent policies/outcomes)
_mem_store = MemoryStore()

# =========================
# KORRIGIERTE LANGEXTRACT-FUNKTIONEN
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
    """KORRIGIERTE Default-Konfiguration mit besserem Prompt und Examples"""
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
            # Beispiel 1: Strukturierte Requirements mit Attributen
            lx.data.ExampleData(
                text="Requirement: The system shall allow users to reset passwords within 5 minutes after request. Constraint: MFA is mandatory. Actor: user",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="requirement",
                        extraction_text="allow users to reset passwords",
                        attributes={"priority": "high", "category": "account_management", "rationale": "security usability"}
                    ),
                    lx.data.Extraction(
                        extraction_class="constraint",
                        extraction_text="MFA is mandatory",
                        attributes={"type": "security"}
                    ),
                    lx.data.Extraction(
                        extraction_class="actor",
                        extraction_text="user",
                        attributes={"role": "end_user"}
                    ),
                ]
            ),
            # Beispiel 2: Tabellen-Format (wie in tool_performance_requirements.md)
            lx.data.ExampleData(
                text="| TP-001 | Das Tool MUSS die Antwortzeit messen | {priority: must, category: performance_monitoring}",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="requirement",
                        extraction_text="Das Tool MUSS die Antwortzeit messen",
                        attributes={"priority": "must", "category": "performance_monitoring"}
                    )
                ]
            ),
            # Beispiel 3: Constraint mit Typ
            lx.data.ExampleData(
                text="Bei Überschreitung von 80% Ressourcenauslastung SOLL eine Benachrichtigung erfolgen",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="constraint",
                        extraction_text="Bei Überschreitung von 80% Ressourcenauslastung SOLL eine Benachrichtigung erfolgen",
                        attributes={"type": "performance"}
                    )
                ]
            )
        ],
    }

# =========================
# KORRIGIERTE INGEST-FUNKTION
# =========================

@api_bp.post("/api/v1/files/ingest")
def files_ingest():
    """
    KORRIGIERTE Version mit besserer LangExtract-Integration
    """
    try:
        files = []
        try:
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f:
                    files = [f]
        except Exception:
            files = []

        if not files:
            return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400

        # Parameter
        def _to_int(name: str, default: int) -> int:
            v = request.form.get(name)
            try:
                return int(v)
            except Exception:
                return default

        chunk_min = _to_int("chunkMin", 5000)  # Größere Chunks
        chunk_max = _to_int("chunkMax", 5000)
        chunk_overlap = _to_int("chunkOverlap", 400)  # Mehr Überlappung
        collection = request.form.get("collection") or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")

        # Extract
        raw_records = []
        for f in files:
            filename = f.filename or "unknown"
            data = f.read() or b""
            ctype = f.mimetype or ""
            parts = extract_texts(filename, data, ctype)
            raw_records.extend(parts)

        # KORRIGIERT: Absatzbasiertes Chunking statt Token-Limits
        source_text = "\n\n".join([r["text"] for r in raw_records])
        chunks_text = build_chunks_absatz(source_text, chunk_size=chunk_min, overlap=chunk_overlap)
        payloads = [{"text": chunk, "payload": {"sourceFile": "combined", "chunkIndex": i}} for i, chunk in enumerate(chunks_text)]

        texts = [p["text"] for p in payloads]
        if not texts:
            return jsonify({"error": "empty", "message": "kein extrahierbarer Text gefunden"}), 200

        # Optional: LangExtract
        structured_flag = str(request.form.get("structured", "")).lower() in ("1", "true", "yes", "on")
        lx_enabled = False
        total_extractions = 0
        coverage_sum = 0.0

        if structured_flag:
            try:
                import langextract as lx
                lx_enabled = True

                # KORRIGIERT: Bessere Prompt und Examples verwenden
                config = _lx_default_config()
                prompt = config.get("prompt_description")
                examples_sdk = []
                for ex in config.get("examples", []):
                    if hasattr(ex, 'text') and hasattr(ex, 'extractions'):
                        examples_sdk.append(ex)

                logging.info(f"LangExtract: Processing {len(payloads)} chunks with {len(examples_sdk)} examples")

                for idx, p in enumerate(payloads):
                    txt = p.get("text") or ""
                    logging.info(f"LangExtract processing chunk {idx}: text length={len(txt)}, first 200 chars='{txt[:200]}'")

                    try:
                        res = lx.extract(
                            text_or_documents=txt,
                            prompt_description=prompt,
                            examples=examples_sdk,
                            model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                            api_key=getattr(settings, "OPENAI_API_KEY", None),
                        )

                        logging.info(f"LangExtract result for chunk {idx}: type={type(res)}, has_to_dict={hasattr(res, 'to_dict')}")

                        # KORRIGIERT: Bessere Normalisierung
                        def _normalize_lx_result(res, chunk_text: str):
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
                                            idx_found = (chunk_text or "").find(et)
                                            if idx_found >= 0:
                                                s = idx_found
                                                epos = idx_found + len(et)

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
                                                "alignment_status": al or "match_exact",
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

                        exts, covered, ratio = _normalize_lx_result(res, txt)
                        logging.info(f"Normalized extractions for chunk {idx}: count={len(exts)}, coverage={ratio}")

                        p["payload"].setdefault("lx", {})
                        p["payload"]["lx"].update({
                            "version": "le.v1",
                            "provider": "openai",
                            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                            "run_id": str(int(time.time())),
                            "extractions": exts,
                            "coverage": {
                                "chunk_len": len(txt),
                                "covered": covered,
                                "coverage_ratio": round(ratio, 4),
                            },
                            "evidence": {
                                "sourceFile": p["payload"].get("sourceFile"),
                                "chunkIndex": p["payload"].get("chunkIndex"),
                            },
                        })
                        total_extractions += len(exts)
                        coverage_sum += ratio
                    except Exception as _le:
                        logging.error(f"LangExtract failed for chunk {idx}: {_le}")
                        p["payload"].setdefault("lx", {})
                        p["payload"]["lx"].update({"version": "le.v1", "error": str(_le)})

            except Exception as lx_err:
                logging.error(f"LangExtract setup failed: {lx_err}")
                lx_enabled = False

        # Embeddings
        vectors = build_embeddings(texts, model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))
        dim = get_embeddings_dim()

        # Upsert
        items = []
        for i, p in enumerate(payloads):
            items.append({
                "vector": vectors[i],
                "payload": p["payload"] | {"text": p["text"]},
            })

        client, eff_port = get_qdrant_client()
        upserted = upsert_points(items, client=client, collection_name=collection, dim=dim)

        resp = {
            "countFiles": len(files),
            "countBlocks": len(raw_records),
            "countChunks": len(payloads),
            "upserted": upserted,
            "collection": collection,
            "qdrantPort": eff_port
        }

        if structured_flag:
            lx_chunks = len(payloads) if lx_enabled else 0
            lx_cov_avg = round((coverage_sum / lx_chunks), 4) if lx_chunks > 0 else 0.0

            lx_preview = []
            if lx_enabled:
                try:
                    for p in payloads:
                        pl = p.get("payload") or {}
                        lx_data = pl.get("lx") or {}
                        exts = lx_data.get("extractions") or []
                        for e in exts:
                            try:
                                if isinstance(e, dict):
                                    ec = e.get("extraction_class")
                                    et = e.get("extraction_text")
                                    ci = e.get("char_interval")
                                    al = e.get("alignment_status")
                                    attrs = e.get("attributes") if isinstance(e.get("attributes"), dict) else {}
                                else:
                                    ec = getattr(e, "extraction_class", None)
                                    et = getattr(e, "extraction_text", None)
                                    ci = getattr(e, "char_interval", None)
                                    al = getattr(e, "alignment_status", None)
                                    attrs = getattr(e, "attributes", {}) or {}
                                    if not isinstance(attrs, dict):
                                        attrs = {}
                                lx_preview.append({
                                    "extraction_class": ec,
                                    "extraction_text": et,
                                    "char_interval": ci,
                                    "alignment_status": al,
                                    "attributes": attrs,
                                    "sourceFile": pl.get("sourceFile"),
                                    "chunkIndex": pl.get("chunkIndex"),
                                })
                            except Exception:
                                continue
                except Exception:
                    lx_preview = []

            resp.update({
                "lxEnabled": bool(lx_enabled),
                "lxChunks": lx_chunks,
                "lxExtracted": int(total_extractions),
                "lxCoverageAvg": lx_cov_avg,
                "lxPreview": lx_preview,
            })

        return jsonify(resp), 200

    except Exception as e:
        logging.error(f"files_ingest error: {e}")
        return jsonify({"error": "internal_error", "message": str(e)}), 500

# =========================
# RESTLICHE FUNKTIONEN (unverändert)
# =========================

# [Der Rest der Datei bleibt unverändert - nur die LangExtract-spezifischen Teile wurden korrigiert]</result>
</edit_file>