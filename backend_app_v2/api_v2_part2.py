# -*- coding: utf-8 -*-
"""
KORRIGIERTE API V2 - Teil 2: Korrigierte files_ingest Funktion
"""

import os
import time
import logging
from typing import Dict, Any, List
import traceback

from flask import jsonify, request

# Importiere aus Teil 1 die gemeinsamen Hilfen/Blueprint
from .api_v2 import api_bp, build_chunks_absatz, _lx_default_config, _normalize_lx_result

# Reuse Backend-Bausteine innerhalb v2
from backend_app import settings
from backend_app.ingest import extract_texts, chunk_payloads
from backend_app.embeddings import build_embeddings, get_embeddings_dim
from backend_app.vector_store import get_qdrant_client, upsert_points

# Optional: LangExtract global import (verhindert NameError bei fehlender Lib)
try:
    import langextract as lx  # type: ignore
except Exception:  # pragma: no cover
    lx = None  # type: ignore

# Logging helper
try:
    from backend_app.logging_ext import _json_log as json_log
except Exception:  # pragma: no cover
    def json_log(logger, level, event, **fields):  # type: ignore
        try:
            logger.log(level, f"{event} {fields}")
        except Exception:
            pass


def _debug_enabled() -> bool:
    try:
        q = request.args.get("debug") or request.form.get("debug")
        if isinstance(q, str) and q.lower() in ("1", "true", "yes", "on"):  # type: ignore
            return True
    except Exception:
        pass
    return str(os.environ.get("DEBUG_API", "")).lower() in ("1", "true", "yes", "on")


# =========================
# KORRIGIERTE INGEST-FUNKTION MIT LANGEXTRACT-FIXES
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

        # Chunking-Optionen (v2.1): chunkMode=paragraph|token, preserveSources=0|1
        chunk_mode = (request.form.get("chunkMode") or "paragraph").strip().lower()
        preserve_sources = str(request.form.get("preserveSources", "")).lower() in ("1", "true", "yes", "on")

        # Defaults für paragraph-mode (Zeichenbasiert)
        chunk_min = _to_int("chunkMin", 5000)
        chunk_max = _to_int("chunkMax", 5000)
        chunk_overlap = _to_int("chunkOverlap", 400)
        collection = request.form.get("collection") or getattr(settings, "QDRANT_COLLECTION", "requirements_v1")

        # Extract
        raw_records = []
        for f in files:
            filename = f.filename or "unknown"
            data = f.read() or b""
            ctype = f.mimetype or ""
            parts = extract_texts(filename, data, ctype)
            raw_records.extend(parts)

        # v2.1: Chunking abhängig von chunkMode/preserveSources
        payloads: List[Dict[str, Any]] = []
        if chunk_mode == "token":
            # Reuse tokenbasiertes Chunking (wie v1)
            payloads = chunk_payloads(raw_records, chunk_min, chunk_max, chunk_overlap)
        else:
            # Absatzbasiertes Chunking
            if preserve_sources:
                # pro Quelle separat chunken und Metadaten erhalten
                for rec in raw_records:
                    txt = str(rec.get("text") or "")
                    meta = dict(rec.get("meta") or {})
                    if not txt.strip():
                        continue
                    chunks_text = build_chunks_absatz(txt, chunk_size=chunk_min, overlap=chunk_overlap)
                    for idx, ch in enumerate(chunks_text):
                        pl = dict(meta)
                        pl["chunkIndex"] = idx
                        payloads.append({"text": ch, "payload": pl})
            else:
                # kombiniert (v2 Default)
                source_text = "\n\n".join([str(r.get("text") or "") for r in raw_records])
                chunks_text = build_chunks_absatz(source_text, chunk_size=chunk_min, overlap=chunk_overlap)
                payloads = [{"text": ch, "payload": {"sourceFile": "combined", "chunkIndex": i}} for i, ch in enumerate(chunks_text)]

        texts = [str(p.get("text") or "") for p in payloads]
        if not texts:
            return jsonify({"error": "empty", "message": "kein extrahierbarer Text gefunden"}), 200

        # Optional: LangExtract
        structured_flag = str(request.form.get("structured", "")).lower() in ("1", "true", "yes", "on")
        lx_enabled = False
        total_extractions = 0
        coverage_sum = 0.0

        if structured_flag:
            try:
                if lx is None:
                    raise RuntimeError("langextract not available")
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
            "qdrantPort": eff_port,
            "chunkMode": chunk_mode,
            "preserveSources": bool(preserve_sources),
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
                                    "alignment_status": (al if isinstance(al, (str, int, float, bool)) else (str(al) if al is not None else None)),
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
        if _debug_enabled():
            return jsonify({
                "error": "internal_error",
                "message": str(e),
                "trace": traceback.format_exc(limit=8),
            }), 500
        return jsonify({"error": "internal_error", "message": "files_ingest failed"}), 500

# =========================
# LangExtract Config/Extract/Mine (v2.1)
# =========================

def _lx_configs_dir() -> str:
    try:
        base = "./data"
        d = os.path.join(base, "lx_configs")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "./data/lx_configs"


def _lx_results_dir() -> str:
    try:
        base = "./data"
        d = os.path.join(base, "lx_results")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "./data/lx_results"


def _lx_config_path(config_id: str) -> str:
    return os.path.join(_lx_configs_dir(), f"{config_id}.json")


def _lx_result_path(save_id: str) -> str:
    return os.path.join(_lx_results_dir(), f"{save_id}.json")

def _lx_reports_dir() -> str:
    try:
        base = "./data"
        d = os.path.join(base, "lx_reports")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return "./data/lx_reports"

def _lx_report_path(save_id: str) -> str:
    return os.path.join(_lx_reports_dir(), f"{save_id}.json")

def _persist_requirements(items: list[dict], path: str) -> dict:
    import json as _json
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump({"items": items}, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "path": path, "count": len(items)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _lx_list_configs() -> list[str]:
    try:
        d = _lx_configs_dir()
        out = []
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                out.append(os.path.splitext(fn)[0])
        return sorted(out)
    except Exception:
        return []


def _lx_save_config(config_id: str, data: dict) -> dict:
    import json as _json
    cid = config_id or f"cfg_{int(time.time())}"
    p = _lx_config_path(cid)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        _json.dump(data or {}, f, ensure_ascii=False, indent=2)
    return {"configId": cid, "path": p}


def _lx_load_config(config_id: str | None) -> dict:
    import json as _json
    try:
        if not config_id:
            p = _lx_config_path("default")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    return _json.load(f)
            return _lx_default_config()
        p = _lx_config_path(config_id)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return _json.load(f)
        return _lx_default_config()
    except Exception:
        return _lx_default_config()


def _lx_examples_to_sdk(examples: list) -> list:
    # Konvertiert examples[] in LangExtract ExampleData/Extraction
    try:
        import langextract as lx  # type: ignore
        out = []
        if isinstance(examples, list):
            for ex in examples:
                if not isinstance(ex, dict):
                    continue
                txt = str(ex.get("text") or "")
                exts = []
                for it in (ex.get("extractions") or []):
                    if not isinstance(it, dict):
                        continue
                    exts.append(
                        lx.data.Extraction(
                            extraction_class=str(it.get("extraction_class") or it.get("cls") or it.get("class") or ""),
                            extraction_text=str(it.get("extraction_text") or it.get("text") or ""),
                            attributes=(it.get("attributes") if isinstance(it.get("attributes"), dict) else {}),
                        )
                    )
                out.append(lx.data.ExampleData(text=txt, extractions=exts))
        return out
    except Exception:
        return []
def _lx_default_structure_config() -> dict:
    """Generic structure-mining config for Markdown-like/plain text documents."""
    return {
        "prompt_description": (
            "Identify structural components in markdown/plain text. Emit only: section, table_row, "
            "bullet_item, numbered_item, paragraph. Rules: (1) Use exact spans with char_interval for every "
            "extraction. (2) Keep order via start_pos. (3) section.attributes={level,title,section_path}. "
            "(4) table_row.attributes={columns: object if a table-like row is detected}. (5) bullet_item/numbered_item.attributes={section_path}. "
            "(6) paragraph.attributes={section_path}. Do not paraphrase; return exact spans."
        ),
        "examples": [
            {
                "text": "# Anforderungen an die aktuelle Backend-Software\n\n| id  | requirementText | context |\n| --- | ---------------- | ------- |\n| R1  | Das Backend stellt einen Health-Endpoint unter GET /health bereit | {\"language\":\"de\",\"area\":\"ops\"} \n",
                "extractions": [
                    {
                        "extraction_class": "section",
                        "extraction_text": "# Anforderungen an die aktuelle Backend-Software",
                        "attributes": {"level": 1, "title": "Anforderungen an die aktuelle Backend-Software", "section_path": ["Anforderungen an die aktuelle Backend-Software"]}
                    },
                    {
                        "extraction_class": "table_row",
                        "extraction_text": "| R1  | Das Backend stellt einen Health-Endpoint unter GET /health bereit | {\"language\":\"de\",\"area\":\"ops\"} |",
                        "attributes": {"columns": {"id": "R1", "requirementText": "Das Backend stellt einen Health-Endpoint unter GET /health bereit", "context": "{\"language\":\"de\",\"area\":\"ops\"}"}, "section_path": ["Anforderungen an die aktuelle Backend-Software"]}
                    }
                ]
            }
        ]
    }


def _bootstrap_structure_examples_from_text(text: str) -> list:
    """Heuristically build minimal structure examples (section + table_row + bullet) from a document.
    Returns a list suitable for LX config 'examples'.
    """
    lines = (text or "").splitlines()
    h1 = None
    # find first heading (#..###)
    for ln in lines:
        s = ln.strip()
        if s.startswith("#"):
            # count #'s
            level = len(s) - len(s.lstrip('#'))
            title = s[level:].strip()
            if title:
                h1 = {"line": ln, "level": level, "title": title}
                break
    # find first markdown table header + data row
    header_cells = None
    data_row_line = None
    for i in range(len(lines)-2):
        a = lines[i].strip()
        b = lines[i+1].strip()
        c = lines[i+2].strip()
        if a.startswith('|') and a.endswith('|') and set(b.replace('|','').replace(' ','')).issubset(set('-:')) and c.startswith('|') and c.endswith('|'):
            # parse header/data cells
            header_cells = [x.strip() for x in a.strip('|').split('|')]
            data_cells = [x.strip() for x in c.strip('|').split('|')]
            # build columns map if equal length
            columns = {}
            if header_cells and len(header_cells) == len(data_cells):
                for k, v in zip(header_cells, data_cells):
                    if k:
                        columns[k] = v
            data_row_line = lines[i+2]
            example_table_text = "\n".join([lines[i], lines[i+1], lines[i+2]])
            break
    # first bullet
    bullet_line = None
    for ln in lines:
        s = ln.lstrip()
        if s.startswith('- '):
            bullet_line = ln
            break

    extractions = []
    if h1:
        extractions.append({
            "extraction_class": "section",
            "extraction_text": h1["line"].strip(),
            "attributes": {"level": h1["level"], "title": h1["title"], "section_path": [h1["title"]]},
        })
    if data_row_line and header_cells:
        extractions.append({
            "extraction_class": "table_row",
            "extraction_text": data_row_line.strip(),
            "attributes": {"columns": columns, "section_path": [h1["title"]] if h1 else []},
        })
    if bullet_line:
        extractions.append({
            "extraction_class": "bullet_item",
            "extraction_text": bullet_line.strip(),
            "attributes": {"section_path": [h1["title"]] if h1 else []},
        })

    example_text_parts = []
    if h1: example_text_parts.append(h1["line"]) 
    if data_row_line and header_cells: example_text_parts.append(example_table_text)
    if bullet_line: example_text_parts.append(bullet_line)
    example_text = "\n\n".join(example_text_parts) or (lines[0] if lines else "")
    return [{"text": example_text, "extractions": extractions}] if extractions else []



# ----------------------
# Validation & alignment helpers
# ----------------------
def _compress_ws(s: str) -> str:
    try:
        return " ".join(str(s or "").split())
    except Exception:
        return str(s or "")


def _align_char_interval(text: str, extraction_text: str) -> dict | None:
    """Find start/end positions of extraction_text in text using relaxed whitespace matching."""
    if not isinstance(text, str) or not isinstance(extraction_text, str):
        return None
    if not extraction_text.strip():
        return None
    # fast path
    idx = text.find(extraction_text)
    if idx >= 0:
        return {"start_pos": idx, "end_pos": idx + len(extraction_text)}
    # relaxed: lowercase & compress whitespace
    t_norm = _compress_ws(text.lower())
    e_norm = _compress_ws(extraction_text.lower())
    if not e_norm:
        return None
    # attempt sliding window match
    try:
        import difflib
        m = difflib.SequenceMatcher(a=t_norm, b=e_norm)
        match = max(m.get_matching_blocks(), key=lambda x: x.size, default=None)
        if match and match.size >= max(10, int(0.6 * len(e_norm))):
            # map back approximate index by searching the matched substring in original text
            sub = t_norm[match.a:match.a + match.size]
            idx2 = _compress_ws(text).find(sub)
            if idx2 >= 0:
                # best-effort mapping: not exact, but provides a span
                return {"start_pos": idx2, "end_pos": idx2 + len(sub)}
    except Exception:
        pass
    return None


def _constrain_and_validate(exts: list, text: str, allowed_classes: set[str]) -> list:
    """Ensure extractions adhere to our schema; align evidence if needed; drop invalid."""
    out = []
    n = len(text or "")
    for e in exts or []:
        try:
            cls = str((e.get("extraction_class") if isinstance(e, dict) else getattr(e, "extraction_class", "")) or "").lower()
            if cls not in allowed_classes:
                continue
            et = (e.get("extraction_text") if isinstance(e, dict) else getattr(e, "extraction_text", "")) or ""
            et = str(et)
            if not et.strip():
                continue
            ci = (e.get("char_interval") if isinstance(e, dict) else getattr(e, "char_interval", None)) or {}
            if not isinstance(ci, dict):
                ci = {}
            st = ci.get("start_pos")
            en = ci.get("end_pos")
            if not isinstance(st, int) or not isinstance(en, int) or st < 0 or en <= st or en > n:
                aligned = _align_char_interval(text, et)
                if aligned:
                    ci = aligned
                else:
                    # cannot validate span -> skip
                    continue
            attrs = e.get("attributes") if isinstance(e, dict) else getattr(e, "attributes", {})
            if not isinstance(attrs, dict):
                attrs = {}
            out.append({
                "extraction_class": cls,
                "extraction_text": et,
                "char_interval": {"start_pos": int(ci.get("start_pos") or 0), "end_pos": int(ci.get("end_pos") or 0)},
                "attributes": attrs,
            })
        except Exception:
            continue
    return out


def _dedupe_merge_by_text(items: list[dict]) -> list[dict]:
    """Deduplicate by (class, normalized text). Merge votes/confidence and keep earliest span."""
    from collections import defaultdict
    buckets = defaultdict(list)
    for e in items or []:
        try:
            cls = str(e.get("extraction_class") or "")
            txt = _compress_ws(str(e.get("extraction_text") or "").lower())
            buckets[(cls, txt)].append(e)
        except Exception:
            continue
    out = []
    for (_, _), arr in buckets.items():
        def _start(x):
            try:
                return int(((x.get("char_interval") or {}).get("start_pos") or 0))
            except Exception:
                return 0
        # prefer earliest occurrence
        best = min(arr, key=_start)
        merged = best.copy()
        merged_votes = sum(int(a.get("votes") or 1) for a in arr)
        merged["votes"] = merged_votes
        try:
            temps_total = 5  # we use 5 temps in self-consistency
            merged["confidence"] = round(min(1.0, merged_votes / max(1.0, float(temps_total))), 3)
        except Exception:
            merged["confidence"] = None
        out.append(merged)
    # stable ordering: by source, chunk, then position
    def _pos(x):
        try:
            return int(((x.get("char_interval") or {}).get("start_pos") or 0))
        except Exception:
            return 0
    out.sort(key=lambda x: (str(x.get("sourceFile") or ""), int(x.get("chunkIndex") or 0), _pos(x)))
    return out


def _repair_pass(text: str, prompt: str, examples_sdk: list, temperatures: list[float] | None = None) -> list:
    """Run a targeted repair pass at higher temperatures if previous result was weak."""
    if temperatures is None:
        temperatures = [0.8, 0.95]
    votes = []
    for t in temperatures:
        try:
            res = lx.extract(
                text_or_documents=text,
                prompt_description=(prompt + "\nIf you found nothing previously, carefully look for missed items."),
                examples=examples_sdk,
                model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                api_key=getattr(settings, "OPENAI_API_KEY", None),
                temperature=t,
            )
            exts, _, _ = _normalize_lx_result(res, text)
            votes.extend(exts or [])
        except Exception:
            continue
    return votes


def _dedupe_nearby_by_similarity(items: list[dict], threshold: float = 0.85) -> list[dict]:
    """Merge near-duplicates using simple Jaccard similarity over token sets. Keep longer text.
    threshold in [0,1].
    """
    def _norm_tokens(s: str) -> set[str]:
        s = str(s or "").lower()
        for ch in [",", ".", ":", ";", "(", ")", "[", "]", "{", "}"]:
            s = s.replace(ch, " ")
        toks = [t for t in s.split() if t]
        return set(toks)
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        den = len(a | b) or 1
        return inter / den
    used = [False] * len(items)
    result: list[dict] = []
    for i, it in enumerate(items):
        if used[i]:
            continue
        ti = _norm_tokens(it.get("extraction_text"))
        winner = it
        used[i] = True
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            tj = _norm_tokens(items[j].get("extraction_text"))
            sim = _jaccard(ti, tj)
            if sim >= threshold:
                # merge: prefer longer text; sum votes
                cand = items[j]
                if len(str(cand.get("extraction_text") or "")) > len(str(winner.get("extraction_text") or "")):
                    winner = cand
                    ti = tj
                used[j] = True
        result.append(winner)
    return result


def _dedupe_mined_items_by_text(items: list[dict], threshold: float = 0.88) -> list[dict]:
    """Dedupe mined items by requirementText using Jaccard similarity; keep longer text.
    """
    def _norm_tokens(s: str) -> set[str]:
        s = str(s or "").lower()
        for ch in [",", ".", ":", ";", "(", ")", "[", "]", "{", "}"]:
            s = s.replace(ch, " ")
        toks = [t for t in s.split() if t]
        return set(toks)
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        den = len(a | b) or 1
        return inter / den
    used = [False] * len(items)
    out: list[dict] = []
    for i, it in enumerate(items):
        if used[i]:
            continue
        ti = _norm_tokens(it.get("requirementText"))
        winner = it
        used[i] = True
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            tj = _norm_tokens(items[j].get("requirementText"))
            sim = _jaccard(ti, tj)
            if sim >= threshold:
                cand = items[j]
                if len(str(cand.get("requirementText") or "")) > len(str(winner.get("requirementText") or "")):
                    winner = cand
                    ti = tj
                used[j] = True
        out.append(winner)
    return out


# =========================
# Gold Set Management & Evaluation
# =========================
def _lx_gold_dir() -> str:
    try:
        base = "./data"
        d = os.path.join(base, "lx_gold")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        d = "./data/lx_gold"
        os.makedirs(d, exist_ok=True)
        return d


def _lx_gold_path(gold_id: str) -> str:
    return os.path.join(_lx_gold_dir(), f"{gold_id}.json")


def _gold_items_load(gold_id: str) -> list[dict]:
    """Load gold items list for a given goldId. Returns a list of dicts with requirementText fields.
    If not found, returns empty list.
    """
    try:
        p = _lx_gold_path(gold_id)
        if not os.path.exists(p):
            return []
        import json as _json
        with open(p, "r", encoding="utf-8") as f:
            data = _json.load(f)
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            return items
        # fallback when saved as {gold: {items: [...]}}
        gold = data.get("gold") if isinstance(data, dict) else None
        if isinstance(gold, dict) and isinstance(gold.get("items"), list):
            return gold.get("items")
    except Exception:
        pass
    return []


def _gold_to_examples(gold_items: list[dict], max_items: int = 50) -> list[dict]:
    """Convert gold items into config-style examples that `_lx_examples_to_sdk` can consume.
    Each example uses the requirement text as both input text and extraction span for class 'requirement'.
    """
    examples: list[dict] = []
    count = 0
    for it in (gold_items or []):
        if count >= max_items:
            break
        try:
            req_txt = str(it.get("requirementText") or it.get("text") or "").strip()
            if not req_txt:
                continue
            examples.append({
                "text": req_txt,
                "extractions": [
                    {
                        "extraction_class": "requirement",
                        "extraction_text": req_txt,
                        "attributes": {"source": "gold"}
                    }
                ]
            })
            count += 1
        except Exception:
            continue
    return examples

@api_bp.get("/api/v1/lx/gold/list")
def lx_gold_list():
    try:
        d = _lx_gold_dir()
        names = []
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                names.append(os.path.splitext(fn)[0])
        names.sort()
        return jsonify({"items": names}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/lx/gold/get")
def lx_gold_get():
    try:
        import json as _json
        gid = request.args.get("id") or "default"
        p = _lx_gold_path(gid)
        if not os.path.exists(p):
            return jsonify({"goldId": gid, "gold": {"items": []}}), 200
        with open(p, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return jsonify({"goldId": gid, "gold": data}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/lx/gold/save")
def lx_gold_save():
    try:
        import json as _json
        data = request.get_json(silent=True) or {}
        gid = (data.get("goldId") or "default").strip() or "default"
        gold = data.get("gold")
        if not isinstance(gold, dict) or not isinstance(gold.get("items"), list):
            return jsonify({"error": "invalid_request", "message": "gold.items muss Liste sein"}), 400
        p = _lx_gold_path(gid)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(gold, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "ok", "goldId": gid, "path": p}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/lx/gold/auto")
def lx_gold_auto():
    """Auto-generate gold items from uploaded files or JSON text by parsing markdown tables."""
    try:
        content_type = (request.content_type or "").lower()
        gid = None
        items: list[dict] = []
        if "multipart/form-data" in content_type:
            gid = (request.form.get("goldId") or "auto").strip() or "auto"
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file"); files = [f] if f else []
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            for f in files:
                txt = (f.read() or b"").decode("utf-8", errors="ignore")
                items.extend(_parse_markdown_tables_to_gold(txt))
        else:
            data = request.get_json(silent=True) or {}
            gid = (data.get("goldId") or "auto").strip() or "auto"
            txt = str(data.get("text") or "")
            if not txt.strip():
                return jsonify({"error": "invalid_request", "message": "text oder files erforderlich"}), 400
            items = _parse_markdown_tables_to_gold(txt)
        # fallback if no table items: heuristic mining
        if not items:
            items = _mine_heuristic_requirements("\n".join(texts) if 'texts' in locals() else (txt or ""))
        # save
        res = _lx_gold_path(gid)
        os.makedirs(os.path.dirname(res), exist_ok=True)
        import json as _json
        with open(res, "w", encoding="utf-8") as f:
            _json.dump({"items": items}, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "ok", "goldId": gid, "count": len(items)}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "gold auto failed"}), 500


@api_bp.post("/api/v1/lx/evaluate/auto")
def lx_evaluate_auto():
    """One-shot: extract + auto-gold + evaluate. Accepts multipart files or JSON text.
    Returns metrics and matches.
    """
    try:
        import json as _json
        content_type = (request.content_type or "").lower()
        threshold = 0.7
        try:
            if "multipart/form-data" in content_type:
                threshold = float(request.form.get("threshold") or 0.7)
            else:
                threshold = float((request.json or {}).get("threshold") or 0.7)
        except Exception:
            threshold = 0.7

        # 1) collect text
        texts: list[str] = []
        if "multipart/form-data" in content_type:
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file"); files = [f] if f else []
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            for f in files:
                texts.append((f.read() or b"").decode("utf-8", errors="ignore"))
        else:
            data = request.get_json(silent=True) or {}
            t = str(data.get("text") or "")
            if not t.strip():
                return jsonify({"error": "invalid_request", "message": "text oder files erforderlich"}), 400
            texts = [t]

        full_text = "\n\n".join(texts)

        # 2) auto-gold
        gold_items = _parse_markdown_tables_to_gold(full_text)
        if not gold_items:
            gold_items = _mine_heuristic_requirements(full_text)
        gold_strs = [_normalize_req_text(x) for x in gold_items]

        # 3) run extract quickly (paragraph mode, neighbors)
        # Reuse extract flow via internal call (simple): split into large chunk
        # For simplicity, evaluate directly on full_text with lx.extract
        if lx is None:
            return jsonify({"error": "lx_unavailable", "message": "langextract library not installed"}), 500
        cfg = _lx_load_config(None)
        prompt = cfg.get("prompt_description") or _lx_default_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk(cfg.get("examples") or _lx_default_config()["examples"])
        res = lx.extract(
            text_or_documents=full_text,
            prompt_description=prompt,
            examples=examples_sdk,
            model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            api_key=getattr(settings, "OPENAI_API_KEY", None),
            temperature=0.2,
        )
        exts, _, _ = _normalize_lx_result(res, full_text)
        pred_texts = [
            _normalize_req_text(e.get("extraction_text"))
            for e in exts if str(e.get("extraction_class") or "").lower() == "requirement"
        ]
        pred_texts = [s for s in pred_texts if s]
        # table-first exact copy boost: include gold (table) items as predictions
        pred_texts = list({*pred_texts, *gold_strs})

        # 4) evaluate
        used_g = [False] * len(gold_strs)
        tp = 0
        matches = []
        for p in pred_texts:
            best_j = -1; best_sim = 0.0
            for j, g in enumerate(gold_strs):
                if used_g[j]:
                    continue
                sim = _similarity_score(p, g)
                if sim > best_sim:
                    best_sim = sim; best_j = j
            if best_j >= 0 and best_sim >= threshold:
                used_g[best_j] = True
                tp += 1
                matches.append({"pred": p, "gold": gold_strs[best_j], "score": round(best_sim, 3)})
        fp = max(0, len(pred_texts) - tp)
        fn = max(0, len(gold_strs) - tp)
        prec = (tp / max(1, tp + fp))
        rec = (tp / max(1, tp + fn))
        f1 = (2 * prec * rec / max(1e-9, prec + rec)) if (prec + rec) > 0 else 0.0

        return jsonify({
            "gold_count": len(gold_strs),
            "pred_count": len(pred_texts),
            "metrics": {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)},
            "matches": matches,
        }), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "evaluate auto failed"}), 500
def _normalize_req_text(x) -> str:
    if isinstance(x, dict):
        s = x.get("requirementText") or x.get("text") or x.get("title") or ""
    else:
        s = str(x or "")
    s = _compress_ws(s).lower().strip()
    return s


def _as_token_set(s: str) -> set[str]:
    s = str(s or "").lower()
    for ch in [",", ".", ":", ";", "(", ")", "[", "]", "{", "}"]:
        s = s.replace(ch, " ")
    return set([t for t in s.split() if t])


def _similarity_score(a: str, b: str) -> float:
    """Robust similarity = max(Jaccard, token-containment, char-level ratio)."""
    a_norm = _compress_ws(str(a or "").lower())
    b_norm = _compress_ws(str(b or "").lower())
    if not a_norm or not b_norm:
        return 0.0
    sa, sb = _as_token_set(a_norm), _as_token_set(b_norm)
    inter = len(sa & sb)
    den = len(sa | sb) or 1
    jacc = inter / den
    contain = 0.0
    if sa and sb:
        contain = min(inter / len(sa), inter / len(sb))
    try:
        import difflib
        char_ratio = difflib.SequenceMatcher(a=a_norm, b=b_norm).ratio()
    except Exception:
        char_ratio = 0.0
    return max(jacc, contain, char_ratio)


def _cosine_sim(u: list[float], v: list[float]) -> float:
    try:
        import math
        du = math.sqrt(sum(x*x for x in u)) or 1.0
        dv = math.sqrt(sum(x*x for x in v)) or 1.0
        dot = sum(x*y for x, y in zip(u, v))
        return dot/(du*dv)
    except Exception:
        return 0.0


def _parse_markdown_tables_to_gold(text: str) -> list[dict]:
    """Parse markdown tables and return gold items with requirementText if header matches."""
    lines = (text or "").splitlines()
    items: list[dict] = []
    i = 0
    while i < len(lines) - 2:
        header = lines[i].strip()
        sep = lines[i+1].strip()
        if header.startswith('|') and header.endswith('|') and set(sep.replace('|','').replace(' ','')) <= set('-:'):
            headers_raw = [h.strip() for h in header.strip('|').split('|')]
            headers = [h.lower() for h in headers_raw]
            # find requirementText/requirement column
            req_idx = -1
            for alias in ('requirementtext', 'requirement', 'requirement text'):
                if alias in headers:
                    req_idx = headers.index(alias)
                    break
            if req_idx < 0:
                i += 1; continue
            # scan subsequent data rows until break
            j = i + 2
            while j < len(lines):
                row = lines[j].strip()
                if not (row.startswith('|') and row.endswith('|')):
                    break
                cells = [c.strip() for c in row.strip('|').split('|')]
                if len(cells) >= req_idx + 1:
                    req_text = cells[req_idx]
                    if req_text:
                        items.append({"requirementText": req_text})
                j += 1
            i = j
            continue
        i += 1
    return items


def _strip_code_blocks(text: str) -> list[str]:
    lines = (text or "").splitlines()
    out = []
    in_code = False
    for ln in lines:
        s = ln.rstrip("\n\r")
        if s.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        out.append(s)
    return out


def _mine_heuristic_requirements(text: str) -> list[dict]:
    import re
    lines = _strip_code_blocks(text)
    items: list[dict] = []
    pat_modal = re.compile(r"\b(muss|müssen|soll|sollen|should|shall|erforderlich|verpflichtend|dürfen nicht|verboten)\b", re.IGNORECASE)
    pat_api = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+/[A-Za-z0-9_\-/]*", re.IGNORECASE)
    pat_perf = re.compile(r"\b(ms|s|rps|p95|p99|latency)\b", re.IGNORECASE)
    pat_sec = re.compile(r"\b(TLS|OAuth|SAML|2FA|PII|DSGVO|GDPR|Security|Logs)\b", re.IGNORECASE)
    bullet = re.compile(r"^\s*([*\-\+]\s|\d+[\).]\s|\[[ xX]?\]\s)")
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith('#') or s.startswith('>'):
            continue
        score = 0
        if bullet.search(s):
            score += 1
        if pat_modal.search(s):
            score += 1
        if pat_api.search(s):
            score += 1
        if pat_perf.search(s) or pat_sec.search(s):
            score += 1
        # keep reasonably short/long sentences
        if 12 <= len(s) <= 400 and score >= 2:
            items.append({"requirementText": s})
    # dedupe by normalized text
    seen = set()
    out: list[dict] = []
    for it in items:
        norm = _compress_ws(str(it.get("requirementText") or "").lower())
        if norm and norm not in seen:
            seen.add(norm)
            out.append(it)
    return out


def _analyze_structure(text: str) -> list[dict]:
    """Heuristic structure analysis (no LLM): sections, table_row, bullet_item, paragraph with offsets."""
    if not isinstance(text, str):
        return []
    components: list[dict] = []
    # Precompute positions per line to map line-local spans to global char offsets
    lines = text.splitlines(keepends=True)
    starts = []
    pos = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln)

    # Track section path via markdown headings
    section_path: list[str] = []
    import re
    heading_re = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
    bullet_re = re.compile(r"^\s*(?:[-*+]\s|\d+[\).]\s|\[[ xX]?\]\s)(.+)$")

    # Tables: detect header + separator and parse rows
    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n\r')
        m = heading_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # update section path
            if level <= len(section_path):
                section_path = section_path[:level-1]
            while len(section_path) < level-1:
                section_path.append("")
            if level >= 1:
                if len(section_path) == level-1:
                    section_path.append(title)
                else:
                    section_path[level-1] = title
            start_pos = starts[i]
            end_pos = start_pos + len(lines[i])
            components.append({
                "extraction_class": "section",
                "extraction_text": line,
                "char_interval": {"start_pos": start_pos, "end_pos": end_pos},
                "attributes": {"level": level, "title": title, "section_path": [p for p in section_path if p]},
            })
            i += 1
            continue

        # table detection
        if line.strip().startswith('|') and line.strip().endswith('|') and i+1 < len(lines):
            sep = lines[i+1].strip()
            if set(sep.replace('|','').replace(' ','')) <= set('-:'):
                headers = [h.strip() for h in line.strip('|').split('|')]
                j = i+2
                while j < len(lines) and lines[j].strip().startswith('|') and lines[j].strip().endswith('|'):
                    row = lines[j].strip()
                    cells = [c.strip() for c in row.strip('|').split('|')]
                    cols = {}
                    for k, v in zip(headers, cells):
                        if k:
                            cols[k] = v
                    start_pos = starts[j]
                    end_pos = start_pos + len(lines[j])
                    components.append({
                        "extraction_class": "table_row",
                        "extraction_text": row,
                        "char_interval": {"start_pos": start_pos, "end_pos": end_pos},
                        "attributes": {"columns": cols, "section_path": [p for p in section_path if p]},
                    })
                    j += 1
                i = j
                continue

        # bullet items
        mb = bullet_re.match(line)
        if mb:
            text_only = mb.group(1).strip()
            start_pos = starts[i]
            end_pos = start_pos + len(lines[i])
            components.append({
                "extraction_class": "bullet_item",
                "extraction_text": text_only,
                "char_interval": {"start_pos": start_pos, "end_pos": end_pos},
                "attributes": {"section_path": [p for p in section_path if p]},
            })
            i += 1
            continue

        i += 1

    # paragraphs: join consecutive non-empty, non-heading, non-table, non-bullet lines
    # Build a mask of consumed spans (sections/table_row/bullet covered)
    covered = []
    for c in components:
        ci = c.get("char_interval") or {}
        covered.append((int(ci.get("start_pos") or 0), int(ci.get("end_pos") or 0)))
    covered.sort()

    def is_covered(a: int, b: int) -> bool:
        # quick overlap check
        for sa, sb in covered:
            if sb <= a: continue
            if sa >= b: break
            if max(sa, a) < min(sb, b):
                return True
        return False

    text_no = text
    # paragraphs by blank lines
    paras = text_no.split('\n\n')
    cursor = 0
    for para in paras:
        start = text_no.find(para, cursor)
        if start < 0:
            start = cursor
        end = start + len(para)
        cursor = end + 2
        ptxt = para.strip()
        if not ptxt:
            continue
        if is_covered(start, end):
            continue
        if 20 <= len(ptxt) <= 800:
            components.append({
                "extraction_class": "paragraph",
                "extraction_text": ptxt,
                "char_interval": {"start_pos": start, "end_pos": end},
                "attributes": {"section_path": [p for p in section_path if p]},
            })

    # sort by start
    def _st(c):
        try: return int(((c.get("char_interval") or {}).get("start_pos") or 0))
        except: return 0
    components.sort(key=_st)

    # dedupe identical/overlapping components
    def _norm_txt(s: str) -> str:
        return _compress_ws(str(s or "").lower())
    deduped: list[dict] = []
    for c in components:
        if not deduped:
            deduped.append(c); continue
        last = deduped[-1]
        if (str(last.get("extraction_class") or "") == str(c.get("extraction_class") or "") and
            _norm_txt(last.get("extraction_text")) == _norm_txt(c.get("extraction_text"))):
            la, lb = (last.get("char_interval") or {}), (c.get("char_interval") or {})
            sa, ea = int(la.get("start_pos") or 0), int(la.get("end_pos") or 0)
            sb, eb = int(lb.get("start_pos") or 0), int(lb.get("end_pos") or 0)
            inter = max(0, min(ea, eb) - max(sa, sb))
            den = max(1, max(ea-sa, eb-sb))
            if inter/den > 0.6:
                # keep earlier and wider span
                if (eb - sb) > (ea - sa):
                    deduped[-1] = c
                continue
        deduped.append(c)

    # neighbor linking (indices)
    for idx, c in enumerate(deduped):
        attrs = c.get("attributes") or {}
        prev_ci = (deduped[idx-1].get("char_interval") if idx-1 >= 0 else None) or {}
        next_ci = (deduped[idx+1].get("char_interval") if idx+1 < len(deduped) else None) or {}
        try:
            attrs["neighbor_prev_start"] = int(prev_ci.get("start_pos") or 0)
            attrs["neighbor_next_start"] = int(next_ci.get("start_pos") or 0)
        except Exception:
            pass
        c["attributes"] = attrs

    components = deduped
    return components


@api_bp.post("/api/v1/structure/analyze")
def structure_analyze_endpoint():
    """Heuristic structure analysis without LLM; returns components with offsets."""
    try:
        content_type = (request.content_type or "").lower()
        txt = None
        if "multipart/form-data" in content_type:
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file"); files = [f] if f else []
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            buf = []
            for f in files:
                buf.append((f.read() or b"").decode("utf-8", errors="ignore"))
            txt = "\n\n".join(buf)
        else:
            data = request.get_json(silent=True) or {}
            txt = str(data.get("text") or "")
            if not txt.strip():
                return jsonify({"error": "invalid_request", "message": "text oder files erforderlich"}), 400
        # optional wtpsplit (if requested)
        use_wtpsplit = False
        try:
            if "multipart/form-data" in content_type:
                use_wtpsplit = str(request.form.get("use_wtpsplit", "")).lower() in ("1","true","yes","on")
            else:
                use_wtpsplit = bool((request.json or {}).get("use_wtpsplit") or False)
        except Exception:
            use_wtpsplit = False
        comps = _analyze_structure(txt)
        if use_wtpsplit:
            try:
                # refine paragraphs into sentences
                from wtpsplit import WtP  # type: ignore
                splitter = WtP()
                refined: list[dict] = []
                for c in comps:
                    if str(c.get("extraction_class") or "").lower() == "paragraph":
                        ptxt = str(c.get("extraction_text") or "")
                        base_start = int(((c.get("char_interval") or {}).get("start_pos") or 0))
                        spans = splitter.split(ptxt, return_spans=True)  # list of (start,end)
                        if spans:
                            for (s,e) in spans:
                                st = base_start + int(s); en = base_start + int(e)
                                seg = ptxt[s:e].strip()
                                if len(seg) >= 8:
                                    nc = dict(c)
                                    nc["extraction_class"] = "paragraph"
                                    nc["extraction_text"] = seg
                                    nc["char_interval"] = {"start_pos": st, "end_pos": en}
                                    refined.append(nc)
                            continue
                    refined.append(c)
                comps = refined
            except Exception:
                pass
        return jsonify({"components": comps, "count": len(comps)}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "structure analyze failed"}), 500


def _build_graph_from_components(components: list[dict]) -> tuple[list[dict], list[dict]]:
    # nodes: one per component; edges: prev->next within same section_path; duplicate edges by high similarity
    comps = components or []
    # sort by start
    def _st(c):
        try: return int(((c.get("char_interval") or {}).get("start_pos") or 0))
        except: return 0
    comps = sorted(comps, key=_st)
    nodes: list[dict] = []
    edges: list[dict] = []
    # build nodes
    for idx, c in enumerate(comps):
        nid = f"c{idx}"
        ctype = str(c.get("extraction_class") or "")
        txt = str(c.get("extraction_text") or "")
        nodes.append({
            "id": nid,
            "type": ctype,
            "name": (txt[:120] + ("…" if len(txt) > 120 else "")),
            "payload": {
                "node_id": nid,
                "type": ctype,
                "name": txt,
                "section_path": (c.get("attributes") or {}).get("section_path") or [],
                "char_interval": c.get("char_interval") or {},
            }
        })
    # prev/next within same section_path
    def _norm_path(p):
        return tuple((p or []))
    for i in range(len(comps) - 1):
        a, b = comps[i], comps[i+1]
        pa = _norm_path((a.get("attributes") or {}).get("section_path"))
        pb = _norm_path((b.get("attributes") or {}).get("section_path"))
        if pa == pb:
            edges.append({
                "id": f"e{i}_next",
                "from": f"c{i}",
                "to": f"c{i+1}",
                "rel": "NEXT"
            })
    # duplicate edges for high text similarity
    norm_texts = [ _compress_ws(str(c.get("extraction_text") or "").lower()) for c in comps ]
    for i in range(len(comps)):
        for j in range(i+1, len(comps)):
            if not norm_texts[i] or not norm_texts[j]:
                continue
            sim = _similarity_score(norm_texts[i], norm_texts[j])
            if sim >= 0.95:
                edges.append({
                    "id": f"d{i}_{j}",
                    "from": f"c{i}",
                    "to": f"c{j}",
                    "rel": "DUPLICATE_OF"
                })
    return nodes, edges


@api_bp.post("/api/v1/structure/graph_export")
def structure_graph_export():
    """Export structure as nodes/edges and JSON-LD.
    Body: multipart with file(s) or JSON { text?: str, components?: [...] }
    """
    try:
        content_type = (request.content_type or "").lower()
        comps: list[dict] = []
        if "multipart/form-data" in content_type:
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file"); files = [f] if f else []
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            buf = []
            for f in files:
                buf.append((f.read() or b"").decode("utf-8", errors="ignore"))
            txt = "\n\n".join(buf)
            comps = _analyze_structure(txt)
        else:
            data = request.get_json(silent=True) or {}
            if isinstance(data.get("components"), list):
                comps = data.get("components")
            else:
                txt = str(data.get("text") or "")
                if not txt.strip():
                    return jsonify({"error": "invalid_request", "message": "text oder components erforderlich"}), 400
                comps = _analyze_structure(txt)
        nodes, edges = _build_graph_from_components(comps)
        # simple JSON-LD
        jsonld = {
            "@context": {"@vocab": "https://example.org/req#"},
            "@graph": [
                {"@id": n["id"], "@type": n.get("type"), "name": n.get("payload", {}).get("name"), "section_path": (n.get("payload", {}).get("section_path") or []), "char_interval": n.get("payload", {}).get("char_interval") } for n in nodes
            ] + [
                {"@id": e["id"], "@type": "Edge", "from": e["from"], "to": e["to"], "rel": e["rel"] } for e in edges
            ]
        }
        return jsonify({"nodes": nodes, "edges": edges, "jsonld": jsonld}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "graph export failed"}), 500


@api_bp.post("/api/v1/lx/evaluate")
def lx_evaluate():
    """Evaluate predicted requirements against a gold set.
    Body: {
      goldId?: str,
      gold?: { items: [ { requirementText } | str ] },
      saveId?: str, latest?: bool, items?: [ { requirementText } ], threshold?: float
    }
    """
    try:
        import json as _json
        body = request.get_json(silent=True) or {}
        threshold = float(body.get("threshold") or 0.9)
        use_embeddings = bool(body.get("use_embeddings") or False)
        embed_threshold = float(body.get("embed_threshold") or 0.9)

        # Load GOLD
        gold_items = []
        if isinstance(body.get("gold"), dict):
            gold_items = list(body.get("gold", {}).get("items") or [])
        elif body.get("goldId"):
            gid = str(body.get("goldId"))
            p = _lx_gold_path(gid)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        gold_items = (_json.load(f) or {}).get("items") or []
                except Exception:
                    gold_items = []
        # normalize gold strings
        gold_strs = [_normalize_req_text(x) for x in (gold_items or []) if _normalize_req_text(x)]

        # Load PRED
        pred_texts = []
        if isinstance(body.get("items"), list):
            for x in body.get("items"):
                pred_texts.append(_normalize_req_text(x))
        else:
            sid = body.get("saveId")
            if not sid and bool(body.get("latest")):
                d = _lx_results_dir()
                files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith(".json")]
                files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                sid = os.path.splitext(os.path.basename(files[0]))[0] if files else None
            if sid:
                p = _lx_result_path(str(sid))
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            data = _json.load(f)
                        for e in (data.get("lxPreview") or []):
                            if str(e.get("extraction_class") or "").lower() == "requirement":
                                pred_texts.append(_normalize_req_text(e.get("extraction_text")))
                    except Exception:
                        pass

        pred_texts = [s for s in pred_texts if s]

        # Evaluate using robust similarity (+ optional embeddings)
        used_g = [False] * len(gold_strs)
        tp = 0
        matches = []
        pred_vecs = []
        gold_vecs = []
        if use_embeddings and pred_texts and gold_strs:
            try:
                # reuse embedding model used in ingest
                from backend_app.embeddings import build_embeddings as _be
                pred_vecs = _be(pred_texts, model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))
                gold_vecs = _be(gold_strs, model=getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small"))
            except Exception:
                pred_vecs = []; gold_vecs = []
        for i, pred in enumerate(pred_texts):
            best_j = -1
            best_sim = 0.0
            for j, gold in enumerate(gold_strs):
                if used_g[j]:
                    continue
                sim = _similarity_score(pred, gold)
                if use_embeddings and pred_vecs and gold_vecs:
                    try:
                        cs = _cosine_sim(pred_vecs[i], gold_vecs[j])
                        sim = max(sim, cs if cs >= embed_threshold else sim)
                    except Exception:
                        pass
                if sim > best_sim:
                    best_sim = sim; best_j = j
            if best_j >= 0 and best_sim >= threshold:
                used_g[best_j] = True
                tp += 1
                matches.append({"pred": pred_texts[i], "gold": gold_strs[best_j], "score": round(best_sim, 3)})

        fp = max(0, len(pred_texts) - tp)
        fn = max(0, len(gold_strs) - tp)
        prec = (tp / max(1, tp + fp))
        rec = (tp / max(1, tp + fn))
        f1 = (2 * prec * rec / max(1e-9, prec + rec)) if (prec + rec) > 0 else 0.0

        # examples for errors
        unmatched_gold = [gold_strs[i] for i, u in enumerate(used_g) if not u]

        return jsonify({
            "metrics": {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3)},
            "matches": matches,
            "unmatched_gold": unmatched_gold[:20],
            "pred_count": len(pred_texts),
            "gold_count": len(gold_strs),
        }), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "evaluation failed"}), 500


def _lx_preview_from_payloads(payloads: list[dict]) -> list[dict]:
    preview = []
    for p in payloads or []:
        try:
            pl = p.get("payload") or {}
            lx = pl.get("lx") or {}
            exts = lx.get("extractions") or []
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
                    preview.append({
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
            continue
    return preview


@api_bp.get("/api/v1/lx/config/list")
def lx_config_list_v2():
    try:
        return jsonify({"items": _lx_list_configs()}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.get("/api/v1/lx/config/get")
def lx_config_get_v2():
    try:
        cid = request.args.get("id") or "default"
        cfg = _lx_load_config(cid)
        return jsonify({"configId": cid, "config": cfg}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/lx/config/save")
def lx_config_save_v2():
    try:
        data = request.get_json(silent=True) or {}
        cid = str(data.get("configId") or "").strip() or f"cfg_{int(time.time())}"
        prompt = data.get("prompt_description") or data.get("prompt") or _lx_default_config()["prompt_description"]
        examples = data.get("examples") or _lx_default_config()["examples"]
        saved = _lx_save_config(cid, {"prompt_description": prompt, "examples": examples})
        return jsonify({"saved": saved}), 200
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@api_bp.post("/api/v1/lx/extract")
def lx_extract_endpoint_v2():
    """
    Führt LangExtract mit konfigurierbarem Prompt/Examples aus und persistiert das Ergebnis.
    Akzeptiert:
      - multipart/form-data mit 'files' (oder 'file'), optional: chunkMin, chunkMax, chunkOverlap, configId
      - application/json mit { text?: str, configId?: str, prompt_description?, examples? }
    Persistiert nach /data/lx_results/{save_id}.json.
    Response: { lxPreview: [...], savedAs: str, configId: str, chunks: int }
    """
    try:
        import json as _json
        import hashlib
        if lx is None:
            return jsonify({
                "error": "lx_unavailable",
                "message": "langextract library not installed",
                "hint": "pip install langextract",
            }), 500

        content_type = (request.content_type or "").lower()
        cfg_id = None
        prompt_desc = None
        examples_in = None

        texts: list[str] = []
        sources: list[dict] = []

        if "multipart/form-data" in content_type:
            cfg_id = request.form.get("configId")
            prompt_desc = request.form.get("prompt_description") or request.form.get("prompt")
            try:
                ex_str = request.form.get("examples")
                if ex_str:
                    examples_in = _json.loads(ex_str)
            except Exception:
                examples_in = None

            def _to_int(name: str, default: int) -> int:
                v = request.form.get(name)
                try:
                    return int(v)
                except Exception:
                    return default
            cmin = _to_int("chunkMin", getattr(settings, "CHUNK_TOKENS_MIN", 200))
            cmax = _to_int("chunkMax", getattr(settings, "CHUNK_TOKENS_MAX", 400))
            cover = _to_int("chunkOverlap", getattr(settings, "CHUNK_OVERLAP_TOKENS", 50))
            chunk_mode = (request.form.get("chunkMode") or "token").strip().lower()
            use_neighbors = str(request.form.get("neighbor_refs", "")).lower() in ("1", "true", "yes", "on")

            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f:
                    files = [f]
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400

            raw_records = []
            for f in files:
                filename = f.filename or "unknown"
                data = f.read() or b""
                ctype = f.mimetype or ""
                parts = extract_texts(filename, data, ctype)
                raw_records.extend(parts)
            if chunk_mode == "paragraph":
                # Absatzbasiert, basierend auf build_chunks_absatz
                payloads = []
                for rec in raw_records:
                    txt = str(rec.get("text") or "")
                    meta = dict(rec.get("meta") or {})
                    if not txt.strip():
                        continue
                    chunks_text = build_chunks_absatz(txt, chunk_size=cmin, overlap=cover)
                    for idx, ch in enumerate(chunks_text):
                        pl = dict(meta)
                        pl["chunkIndex"] = idx
                        payloads.append({"text": ch, "payload": pl})
            else:
                payloads = chunk_payloads(raw_records, cmin, cmax, cover)
            texts = [p["text"] for p in payloads]
            sources = [{"sourceFile": (p["payload"] or {}).get("sourceFile"), "chunkIndex": (p["payload"] or {}).get("chunkIndex")} for p in payloads]
        else:
            data = request.get_json(silent=True) or {}
            cfg_id = data.get("configId")
            prompt_desc = data.get("prompt_description") or data.get("prompt")
            examples_in = data.get("examples")
            txt = data.get("text")
            if isinstance(txt, str) and txt.strip():
                texts = [txt]
                payloads = [{"text": txt, "payload": {"sourceFile": "json:text", "chunkIndex": 0}}]
                sources = [{"sourceFile": "json:text", "chunkIndex": 0}]
            else:
                return jsonify({"error": "invalid_request", "message": "text fehlt oder multipart files fehlen"}), 400

        cfg = _lx_load_config(cfg_id)
        # Optional: Guided mining via gold (saved or auto-generated)
        gold_id = None
        use_gold = False
        auto_gold = False
        fast_mode = False
        user_temperature = None
        if "multipart/form-data" in content_type:
            gold_id = request.form.get("goldId")
            use_gold = str(request.form.get("useGoldAsFewshot", "")).lower() in ("1","true","yes","on")
            auto_gold = str(request.form.get("autoGold", "")).lower() in ("1","true","yes","on")
            fast_mode = str(request.form.get("fast", "")).lower() in ("1","true","yes","on")
            try:
                if request.form.get("temperature") is not None:
                    user_temperature = float(request.form.get("temperature"))
            except Exception:
                user_temperature = None
        else:
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict):
                gold_id = body.get("goldId")
                use_gold = bool(body.get("useGoldAsFewshot"))
                auto_gold = bool(body.get("autoGold"))
                fast_mode = bool(body.get("fast"))
                try:
                    if body.get("temperature") is not None:
                        user_temperature = float(body.get("temperature"))
                except Exception:
                    user_temperature = None
        
        if prompt_desc:
            cfg["prompt_description"] = prompt_desc
        if isinstance(examples_in, list):
            cfg["examples"] = examples_in
        # merge gold items as extra examples if requested
        if use_gold:
            try:
                gold_items = []
                if gold_id:
                    gold_items = _gold_items_load(str(gold_id))
                if (not gold_items) and auto_gold:
                    # auto-generate gold from provided text(s)
                    try:
                        full_text = "\n\n".join([p.get("text") or "" for p in (locals().get("payloads") or [])])
                    except Exception:
                        full_text = "\n\n".join(texts or [])
                    gold_items = _parse_markdown_tables_to_gold(full_text)
                    if not gold_items:
                        gold_items = _mine_heuristic_requirements(full_text)
                gold_examples = _gold_to_examples(gold_items)
                if gold_examples:
                    cfg.setdefault("examples", [])
                    cfg["examples"] = (cfg["examples"] or []) + gold_examples
            except Exception:
                pass
        prompt = cfg.get("prompt_description") or _lx_default_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk(cfg.get("examples") or _lx_default_config()["examples"])

        total_extractions = 0
        coverage_sum = 0.0
        for i, p in enumerate(payloads):
            txt = p.get("text") or ""
            if "use_neighbors" in locals() and use_neighbors:
                try:
                    prev_txt = payloads[i-1]["text"] if i-1 >= 0 else ""
                    next_txt = payloads[i+1]["text"] if i+1 < len(payloads) else ""
                    # Kontext links/rechts begrenzen
                    prefix = prev_txt[-500:] if prev_txt else ""
                    suffix = next_txt[:500] if next_txt else ""
                    txt = (prefix + "\n" + txt + "\n" + suffix).strip()
                except Exception:
                    pass
            try:
                # Self-consistency (disabled in fast mode): multiple temperatures, then merge
                def _once(temp: float) -> list:
                    try:
                        r = lx.extract(
                            text_or_documents=txt,
                            prompt_description=prompt,
                            examples=examples_sdk,
                            model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                            api_key=getattr(settings, "OPENAI_API_KEY", None),
                            temperature=temp,
                        )
                        ex, _, _ = _normalize_lx_result(r, txt)
                        return ex
                    except Exception:
                        return []
                if fast_mode:
                    t = user_temperature if isinstance(user_temperature, (int, float)) else 0.2
                    temps = [float(t)]
                else:
                    temps = [0.0, 0.2, 0.6, 0.8, 0.9]
                votes = []
                for t in temps:
                    votes.extend(_once(t))
                if (not votes) and (not fast_mode):
                    votes = _repair_pass(txt, prompt, examples_sdk)
                from collections import defaultdict
                buckets = defaultdict(list)
                for e in votes:
                    key = (str(e.get("extraction_class") or ""), str(e.get("extraction_text") or ""))
                    buckets[key].append(e)
                exts = []
                for _, arr in buckets.items():
                    validated = _constrain_and_validate(arr, txt, {"requirement", "section", "paragraph", "bullet_item", "numbered_item", "table_row"})
                    if not validated:
                        continue
                    # pick longest span, attach votes
                    def _span_len(x):
                        ci = x.get("char_interval") or {}
                        return int(ci.get("end_pos") or 0) - int(ci.get("start_pos") or 0)
                    best = max(validated, key=_span_len)
                    best = best.copy()
                    best["votes"] = len(arr)
                    exts.append(best)
                covered = sum(max(0, int(((e.get("char_interval") or {}).get("end_pos") or 0)) - int(((e.get("char_interval") or {}).get("start_pos") or 0))) for e in exts)
                ratio = (covered / max(1, len(txt))) if txt else 0.0
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({
                    "version": "le.v1",
                    "provider": "openai",
                    "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    "run_id": str(int(time.time())),
                    "extractions": exts,
                    "coverage": {"chunk_len": len(txt), "covered": covered, "coverage_ratio": round(ratio, 4)},
                    "evidence": {"sourceFile": p["payload"].get("sourceFile"), "chunkIndex": p["payload"].get("chunkIndex")},
                })
                total_extractions += len(exts)
                coverage_sum += ratio
            except Exception as _le:
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({"version": "le.v1", "error": str(_le)})

        lx_preview = _lx_preview_from_payloads(payloads)
        # final dedupe/merge with confidence
        try:
            lx_preview = _dedupe_merge_by_text(lx_preview)
            lx_preview = _dedupe_nearby_by_similarity(lx_preview, threshold=0.88)
        except Exception:
            pass

        sha = hashlib.sha1(("||".join(texts)).encode("utf-8")).hexdigest() if texts else str(int(time.time()))
        save_id = f"lx_{sha[:10]}_{int(time.time())}"
        out = {
            "savedAt": int(time.time()),
            "configId": cfg_id or "default",
            "prompt_description": prompt,
            "examples": cfg.get("examples"),
            "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
            "sources": sources,
            "total_extractions": total_extractions,
            "coverage_avg": (coverage_sum / (len(payloads) or 1)) if payloads else 0.0,
            "payloads": payloads,
            "lxPreview": lx_preview,
        }
        pth = _lx_result_path(save_id)
        try:
            os.makedirs(os.path.dirname(pth), exist_ok=True)
            with open(pth, "w", encoding="utf-8") as f:
                _json.dump(out, f, ensure_ascii=False, indent=2)
        except Exception:
            pth = None

        # Persistiere kompakten Analyse-Report
        try:
            rpt = {
                "saveId": save_id,
                "ts": int(time.time()),
                "configId": cfg_id or "default",
                "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                "chunks": len(payloads),
                "total_extractions": total_extractions,
                "coverage_avg": out.get("coverage_avg"),
                "sources": sources,
            }
            rp = _lx_report_path(save_id)
            os.makedirs(os.path.dirname(rp), exist_ok=True)
            with open(rp, "w", encoding="utf-8") as rf:
                _json.dump(rpt, rf, ensure_ascii=False, indent=2)
        except Exception:
            pass

        resp = {"lxPreview": lx_preview, "savedAs": pth, "saveId": save_id, "configId": cfg_id or "default", "chunks": len(payloads)}
        if _debug_enabled():
            resp["debug"] = {
                "texts": len(texts),
                "payloads": len(payloads),
                "total_extractions": total_extractions,
                "coverage_avg": out.get("coverage_avg") if 'out' in locals() else None,
                "model": getattr(settings, "OPENAI_MODEL", None),
                "api_key_present": bool(getattr(settings, "OPENAI_API_KEY", None)),
            }
        return jsonify(resp), 200
    except Exception as e:
        logging.error(f"lx_extract error: {e}")
        if _debug_enabled():
            return jsonify({
                "error": "internal_error",
                "message": str(e),
                "trace": traceback.format_exc(limit=8),
            }), 500
        return jsonify({"error": "internal_error", "message": "lx_extract failed"}), 500


@api_bp.get("/api/v1/lx/mine")
def lx_mine_from_results_v2():
    try:
        import json as _json
        d = _lx_results_dir()
        save_id = request.args.get("saveId")
        latest = str(request.args.get("latest", "")).lower() in ("1", "true", "yes")
        target = None
        if save_id:
            p = _lx_result_path(save_id)
            if os.path.exists(p):
                target = p
        if not target:
            files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith(".json")]
            if not files:
                return jsonify({"items": []}), 200
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            target = files[0]

        with open(target, "r", encoding="utf-8") as f:
            data = _json.load(f)

        preview = data.get("lxPreview") or []
        items = []
        for i, e in enumerate(preview, start=1):
            try:
                if str(e.get("extraction_class") or "").lower() != "requirement":
                    continue
                rt = str(e.get("extraction_text") or "").strip()
                if not rt:
                    continue
                items.append({
                    "id": f"R{i}",
                    "requirementText": rt,
                    "context": {"source": e.get("sourceFile"), "chunkIndex": e.get("chunkIndex")},
                })
            except Exception:
                continue
        try:
            items = _dedupe_mined_items_by_text(items, threshold=0.9)
        except Exception:
            pass
        return jsonify({"items": items}), 200
    except Exception as e:
        logging.error(f"lx_mine error: {e}")
        if _debug_enabled():
            return jsonify({
                "error": "internal_error",
                "message": str(e),
                "trace": traceback.format_exc(limit=8),
            }), 500
        return jsonify({"error": "internal_error", "message": "lx_mine failed"}), 500


@api_bp.post("/api/v1/lx/structure")
def lx_structure_endpoint():
    """Step 1: Mine structural components using a structure config (default: generic)."""
    try:
        import json as _json
        if lx is None:
            return jsonify({"error": "lx_unavailable", "message": "langextract library not installed"}), 500
        content_type = (request.content_type or "").lower()
        cfg_id = None
        texts: list[str] = []
        sources: list[dict] = []
        if "multipart/form-data" in content_type:
            cfg_id = request.form.get("configId") or "generic_structure"
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f:
                    files = [f]
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            raw_records = []
            for f in files:
                filename = f.filename or "unknown"
                data = f.read() or b""
                ctype = f.mimetype or ""
                parts = extract_texts(filename, data, ctype)
                raw_records.extend(parts)
            # paragraph-based for stable spans
            payloads = []
            for rec in raw_records:
                txt = str(rec.get("text") or "")
                meta = dict(rec.get("meta") or {})
                if not txt.strip():
                    continue
                chunks_text = build_chunks_absatz(txt, chunk_size=8000, overlap=300)
                for idx, ch in enumerate(chunks_text):
                    pl = dict(meta)
                    pl["chunkIndex"] = idx
                    payloads.append({"text": ch, "payload": pl})
            texts = [p["text"] for p in payloads]
            sources = [{"sourceFile": (p.get("payload") or {}).get("sourceFile"), "chunkIndex": (p.get("payload") or {}).get("chunkIndex")} for p in payloads]
        else:
            data = request.get_json(silent=True) or {}
            cfg_id = data.get("configId") or "generic_structure"
            txt = data.get("text")
            if not isinstance(txt, str) or not txt.strip():
                return jsonify({"error": "invalid_request", "message": "text fehlt oder files fehlen"}), 400
            texts = [txt]
            sources = [{"sourceFile": "json:text", "chunkIndex": 0}]

        # load structure config
        cfg = _lx_load_config(cfg_id)
        if cfg_id == "generic_structure" and (not cfg or not isinstance(cfg, dict)):
            cfg = _lx_default_structure_config()
        # Bootstrap per-document examples to anchor the model
        boot_examples = _bootstrap_structure_examples_from_text("\n\n".join(texts))
        prompt = cfg.get("prompt_description") or _lx_default_structure_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk((cfg.get("examples") or []) + boot_examples)

        components = []
        # Self-consistency voting with temperature scheduling
        def _run_once_struct(text: str, temperature: float) -> list:
            try:
                res = lx.extract(
                    text_or_documents=text,
                    prompt_description=prompt,
                    examples=examples_sdk,
                    model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=getattr(settings, "OPENAI_API_KEY", None),
                    temperature=temperature,
                )
                exts, _, _ = _normalize_lx_result(res, text)
                return [e for e in exts if str(e.get("extraction_class") or "").lower() in ("section", "table_row", "bullet_item", "numbered_item", "paragraph")]
            except Exception:
                return []

        for i, txt in enumerate(texts):
            votes = []
            for t in [0.0, 0.2, 0.6, 0.8, 0.9]:
                votes.extend(_run_once_struct(txt, t))
            if not votes:
                votes = _repair_pass(txt, prompt, examples_sdk)
            # merge by class + text + interval, count votes
            from collections import defaultdict
            buckets = defaultdict(list)
            for e in votes:
                ci = e.get("char_interval") or {}
                key = (str(e.get("extraction_class") or ""), str(e.get("extraction_text") or ""), int(ci.get("start_pos") or 0), int(ci.get("end_pos") or 0))
                buckets[key].append(e)
            merged = []
            for _, arr in buckets.items():
                # constrained validation & alignment
                validated = _constrain_and_validate(arr, txt, {"section", "table_row", "bullet_item", "numbered_item", "paragraph"})
                if not validated:
                    continue
                base = validated[0].copy()
                base["votes"] = len(arr)
                merged.append(base)
            # add to components with source metadata
            for e in merged:
                try:
                    item = {
                        "extraction_class": str(e.get("extraction_class") or "").lower(),
                        "extraction_text": e.get("extraction_text"),
                        "char_interval": e.get("char_interval"),
                        "attributes": e.get("attributes") or {},
                        "sourceFile": sources[i].get("sourceFile"),
                        "chunkIndex": sources[i].get("chunkIndex"),
                        "votes": int(e.get("votes") or 1),
                    }
                    components.append(item)
                except Exception:
                    continue

        # order
        def _start(x):
            try:
                return int(((x or {}).get("char_interval") or {}).get("start_pos") or 0)
            except Exception:
                return 0
        components.sort(key=lambda x: (str(x.get("sourceFile") or ""), int(x.get("chunkIndex") or 0), _start(x)))
        return jsonify({"components": components, "sources": sources}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "lx_structure failed"}), 500


@api_bp.post("/api/v1/lx/extract_from_components")
def lx_extract_from_components():
    """Step 2: Accepts components[] and runs requirement extraction per component."""
    try:
        import json as _json
        if lx is None:
            return jsonify({"error": "lx_unavailable", "message": "langextract library not installed"}), 500
        data = request.get_json(silent=True) or {}
        components = data.get("components")
        cfg_id = data.get("configId") or None
        if not isinstance(components, list):
            return jsonify({"error": "invalid_request", "message": "components[] fehlt"}), 400
        cfg = _lx_load_config(cfg_id)
        prompt = cfg.get("prompt_description") if isinstance(cfg, dict) else _lx_default_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk((cfg or {}).get("examples") or _lx_default_config()["examples"])
        out_preview = []
        for i, c in enumerate(components):
            try:
                txt = str(c.get("extraction_text") or "")
                if not txt.strip():
                    continue
                res = lx.extract(
                    text_or_documents=txt,
                    prompt_description=prompt,
                    examples=examples_sdk,
                    model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=getattr(settings, "OPENAI_API_KEY", None),
                )
                exts, _, _ = _normalize_lx_result(res, txt)
                for e in exts:
                    try:
                        e["sourceFile"] = c.get("sourceFile")
                        e["chunkIndex"] = c.get("chunkIndex")
                        out_preview.append(e)
                    except Exception:
                        continue
            except Exception:
                continue
        return jsonify({"lxPreview": out_preview}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "extract_from_components failed"}), 500


@api_bp.post("/api/v1/lx/structure_sampled")
def lx_structure_sampled():
    """Infer structure by sampling random windows and merging structure JSON.

    Body: { text?: str, files?: multipart, samples?: int=6, window?: int=1200, stride?: int=600, configId?: str }
    Returns: { components: [...], coverage_estimate: float }
    """
    try:
        import json as _json
        import random
        if lx is None:
            return jsonify({"error": "lx_unavailable", "message": "langextract library not installed"}), 500
        content_type = (request.content_type or "").lower()
        cfg_id = None
        base_text = ""
        source_meta = {"sourceFile": "json:text"}
        if "multipart/form-data" in content_type:
            cfg_id = request.form.get("configId") or "generic_structure"
            files = []
            if "files" in request.files:
                files = request.files.getlist("files")
            elif "file" in request.files:
                f = request.files.get("file")
                if f: files = [f]
            if not files:
                return jsonify({"error": "invalid_request", "message": "keine Dateien übergeben"}), 400
            parts = []
            for f in files:
                parts.extend(extract_texts(f.filename or "unknown", f.read() or b"", f.mimetype or ""))
            base_text = "\n\n".join([str(p.get("text") or "") for p in parts])
            if parts:
                meta0 = parts[0].get("meta") or {}
                source_meta = {"sourceFile": meta0.get("sourceFile") or "combined"}
        else:
            data = request.get_json(silent=True) or {}
            cfg_id = data.get("configId") or "generic_structure"
            base_text = str(data.get("text") or "")
            if not base_text.strip():
                return jsonify({"error": "invalid_request", "message": "text fehlt oder files fehlen"}), 400

        samples = int(request.form.get("samples") or (request.json or {}).get("samples") or 6)
        window = int(request.form.get("window") or (request.json or {}).get("window") or 1200)
        stride = int(request.form.get("stride") or (request.json or {}).get("stride") or 600)

        cfg = _lx_load_config(cfg_id)
        if cfg_id == "generic_structure" and (not cfg or not isinstance(cfg, dict)):
            cfg = _lx_default_structure_config()
        boot_examples = _bootstrap_structure_examples_from_text(base_text)
        prompt = cfg.get("prompt_description") or _lx_default_structure_config()["prompt_description"]
        examples_sdk = _lx_examples_to_sdk((cfg.get("examples") or []) + boot_examples)

        n = len(base_text)
        if n == 0:
            return jsonify({"components": [], "coverage_estimate": 0.0}), 200

        # generate sample windows
        starts = list(range(0, max(1, n - window), stride))
        if len(starts) > samples:
            random.shuffle(starts)
            starts = starts[:samples]

        merged = []
        for s in starts:
            sub = base_text[s:s+window]
            try:
                res = lx.extract(
                    text_or_documents=sub,
                    prompt_description=prompt,
                    examples=examples_sdk,
                    model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=getattr(settings, "OPENAI_API_KEY", None),
                )
                exts, _, _ = _normalize_lx_result(res, sub)
                for e in exts:
                    try:
                        cls = str(e.get("extraction_class") or "").lower()
                        if cls not in ("section", "table_row", "bullet_item", "numbered_item", "paragraph"):
                            continue
                        ci = e.get("char_interval") or {}
                        st = int(ci.get("start_pos") or 0) + s
                        en = int(ci.get("end_pos") or 0) + s
                        item = {
                            "extraction_class": cls,
                            "extraction_text": e.get("extraction_text"),
                            "char_interval": {"start_pos": st, "end_pos": en},
                            "attributes": e.get("attributes") or {},
                            "sourceFile": source_meta.get("sourceFile"),
                            "chunkIndex": 0,
                        }
                        merged.append(item)
                    except Exception:
                        continue
            except Exception:
                continue

        # merge overlapping by class + interval proximity
        def _key(it):
            return (str(it.get("extraction_class") or ""))
        def _ov(a, b):
            sa, ea = int(((a.get("char_interval") or {}).get("start_pos") or 0)), int(((a.get("char_interval") or {}).get("end_pos") or 0))
            sb, eb = int(((b.get("char_interval") or {}).get("start_pos") or 0)), int(((b.get("char_interval") or {}).get("end_pos") or 0))
            inter = max(0, min(ea, eb) - max(sa, sb))
            den = max(1, max(ea-sa, eb-sb))
            return inter/den
        merged.sort(key=lambda x: (str(x.get("sourceFile") or ""), _key(x), int(((x.get("char_interval") or {}).get("start_pos") or 0))))
        dedup = []
        for it in merged:
            if not dedup:
                dedup.append(it); continue
            last = dedup[-1]
            if _key(last) == _key(it) and _ov(last, it) > 0.6:
                # extend range
                la, lb = last.get("char_interval") or {}, it.get("char_interval") or {}
                last["char_interval"] = {"start_pos": min(int(la.get("start_pos") or 0), int(lb.get("start_pos") or 0)),
                                          "end_pos": max(int(la.get("end_pos") or 0), int(lb.get("end_pos") or 0))}
                continue
            dedup.append(it)

        coverage = 0.0
        if dedup:
            covered = sum(max(0, int((c.get("char_interval") or {}).get("end_pos") or 0) - int((c.get("char_interval") or {}).get("start_pos") or 0)) for c in dedup)
            coverage = min(1.0, covered / max(1, len(base_text)))

        try:
            dedup = _dedupe_merge_by_text(dedup)
            dedup = _dedupe_nearby_by_similarity(dedup, threshold=0.9)
        except Exception:
            pass
        return jsonify({"components": dedup, "coverage_estimate": round(coverage, 3)}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "structure_sampled failed"}), 500


@api_bp.post("/api/v1/lx/save_requirements")
def lx_save_requirements_v2():
    """
    Persistiert eine Liste geminter Requirements in eine Datei.
    Body (JSON): { items: [ { id, requirementText, context? }, ... ], path?: "data/requirements.out.json" }
    Default-Pfad: ./data/requirements.out.json
    """
    try:
        import json as _json
        data = request.get_json(silent=True) or {}
        items = data.get("items")
        if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
            return jsonify({"error": "invalid_request", "message": "items muss eine Liste von Objekten sein"}), 400
        out_path = data.get("path") or "./data/requirements.out.json"
        res = _persist_requirements(items, out_path)
        if res.get("status") != "ok":
            return jsonify(res), 500
        return jsonify(res), 200
    except Exception as e:
        logging.error(f"lx_save_requirements error: {e}")
        if _debug_enabled():
            return jsonify({
                "error": "internal_error",
                "message": str(e),
                "trace": traceback.format_exc(limit=8),
            }), 500
        return jsonify({"error": "internal_error", "message": "lx_save_requirements failed"}), 500


@api_bp.get("/api/v1/lx/config/preview")
def lx_config_preview_v2():
    """Liefert die aktive LX-Konfiguration und das StructuredRequirement-Schema."""
    try:
        cid = request.args.get("id") or "default"
        cfg = _lx_load_config(cid)
        schema = None
        try:
            from backend_app.rag import StructuredRequirement
            schema = StructuredRequirement.schema()
        except Exception:
            # Fallback: Kein Schema verfügbar, aber Config liefern
            schema = None
        return jsonify({"configId": cid, "config": cfg, "structuredRequirementSchema": schema}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "config preview failed"}), 500


@api_bp.get("/api/v1/lx/report/list")
def lx_report_list():
    try:
        d = _lx_reports_dir()
        files = [fn for fn in os.listdir(d) if fn.endswith(".json")]
        files.sort(key=lambda n: os.path.getmtime(os.path.join(d, n)), reverse=True)
        return jsonify({"items": files}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "report list failed"}), 500


@api_bp.get("/api/v1/lx/report/get")
def lx_report_get():
    try:
        import json as _json
        sid = request.args.get("saveId")
        path = _lx_report_path(sid) if sid else None
        if not sid:
            # latest
            d = _lx_reports_dir()
            files = [os.path.join(d, fn) for fn in os.listdir(d) if fn.endswith(".json")]
            if not files:
                return jsonify({"report": None}), 200
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            path = files[0]
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return jsonify({"report": data}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "report get failed"}), 500


@api_bp.post("/api/v1/lx/schema/save")
def lx_schema_save():
    """
    Persistiert ein Schema (z. B. StructuredRequirement-ähnlich) zur späteren Anzeige/Vergleich.
    Body: { "schemaId": "mySchema", "schema": { ... } }
    Pfad: ./data/lx_configs/schemas/{schemaId}.json
    """
    try:
        import json as _json
        data = request.get_json(silent=True) or {}
        sid = (data.get("schemaId") or "custom").strip() or "custom"
        schema = data.get("schema")
        if not isinstance(schema, dict):
            return jsonify({"error": "invalid_request", "message": "schema muss ein Objekt sein"}), 400
        base = _lx_configs_dir()
        d = os.path.join(base, "schemas")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{sid}.json")
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(schema, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "ok", "schemaId": sid, "path": p}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "schema save failed"}), 500


# Zusätzliche Endpoints: vollständiges Ergebnis und einzelne Chunks anzeigen
@api_bp.get("/api/v1/lx/result/get")
def lx_result_get():
    try:
        import json as _json
        sid = request.args.get("saveId")
        if not sid:
            return jsonify({"error": "invalid_request", "message": "saveId fehlt"}), 400
        path = _lx_result_path(sid)
        if not os.path.exists(path):
            return jsonify({"error": "not_found", "message": "result not found"}), 404
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return jsonify({"result": data}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "result get failed"}), 500


@api_bp.get("/api/v1/lx/result/chunk")
def lx_result_chunk():
    try:
        import json as _json
        sid = request.args.get("saveId")
        idx_raw = request.args.get("idx")
        if not sid or idx_raw is None:
            return jsonify({"error": "invalid_request", "message": "saveId und idx erforderlich"}), 400
        try:
            idx = int(idx_raw)
        except Exception:
            return jsonify({"error": "invalid_request", "message": "idx muss int sein"}), 400
        path = _lx_result_path(sid)
        if not os.path.exists(path):
            return jsonify({"error": "not_found", "message": "result not found"}), 404
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        payloads = data.get("payloads") or []
        if idx < 0 or idx >= len(payloads):
            return jsonify({"error": "out_of_range", "message": "idx außerhalb des Bereichs"}), 400
        p = payloads[idx] or {}
        txt = p.get("text") or ""
        return jsonify({"idx": idx, "text": txt, "payload": p.get("payload")}), 200
    except Exception as e:
        if _debug_enabled():
            return jsonify({"error": "internal_error", "message": str(e), "trace": traceback.format_exc(limit=8)}), 500
        return jsonify({"error": "internal_error", "message": "result chunk failed"}), 500


# =========================
# WEITERE ENDPOINTS (Platzhalter für spätere Teile)
# =========================

@api_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

# Weitere Endpoints werden in späteren Teilen hinzugefügt...