# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json as _json
import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from backend.core import settings
from backend.core.ingest import extract_texts, chunk_payloads
# Absatzbasiertes Chunking (v2-Hilfsfunktion)
from backend.api_v2 import build_chunks_absatz
# Reuse v2-Helfer – wir verwenden die bereits etablierte Normalisierung/Speicherlogik
from backend.api_v2_part2 import (
    _lx_load_config,
    _lx_examples_to_sdk,
    _lx_preview_from_payloads,
    _lx_result_path,
    _normalize_lx_result,
)

router = APIRouter(tags=["lx"])


@router.get("/api/v1/lx/config/preview")
def lx_config_preview_v2(id: Optional[str] = None) -> JSONResponse:
    """
    FastAPI-Port: Konfiguration + optionales Schema ausgeben
    """
    try:
        cid = id or "default"
        cfg = _lx_load_config(cid)
        schema = None
        try:
            # Optionales Schema (falls verfügbar)
            from backend.core.rag import StructuredRequirement  # type: ignore
            schema = StructuredRequirement.schema()
        except Exception:
            schema = None
        return JSONResponse(
            content={"configId": cid, "config": cfg, "structuredRequirementSchema": schema},
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/lx/extract")
async def lx_extract_v2(
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    # multipart form fields (optional)
    configId: Optional[str] = Form(default=None),
    chunkMode: Optional[str] = Form(default=None),  # "token" | "paragraph"
    chunkMin: Optional[int] = Form(default=None),
    chunkMax: Optional[int] = Form(default=None),
    chunkOverlap: Optional[int] = Form(default=None),
    structured: Optional[bool] = Form(default=None),
    fast: Optional[bool] = Form(default=None),
    temperature: Optional[float] = Form(default=None),
) -> JSONResponse:
    """
    FastAPI-Port: LangExtract ausführen.
    Unterstützt:
      - multipart/form-data mit files=[...] (und optionalen Parametern)
      - application/json mit { text, configId?, prompt_description?, examples? }
    Response kompatibel zu v2-Implementierung: { lxPreview, savedAs, saveId, configId, chunks }
    """
    try:
        # 1) Eingabe erkennen (multipart vs. json)
        payloads: List[Dict[str, Any]] = []
        texts: List[str] = []
        sources: List[Dict[str, Any]] = []

        content_type = (request.headers.get("content-type") or "").lower()
        is_multipart = "multipart/form-data" in content_type

        if is_multipart and files:
            # multipart: Dateien einlesen und in Records konvertieren
            raw_records: List[Dict[str, Any]] = []
            for f in files:
                data = await f.read()
                fname = f.filename or "upload"
                ctype = f.content_type or ""
                parts = extract_texts(fname, data, ctype)
                raw_records.extend(parts)

            # Chunking
            def _int_or_default(v: Optional[int], default: int) -> int:
                try:
                    return int(v) if v is not None else default
                except Exception:
                    return default

            cmin = _int_or_default(chunkMin, getattr(settings, "CHUNK_TOKENS_MIN", 200))
            cmax = _int_or_default(chunkMax, getattr(settings, "CHUNK_TOKENS_MAX", 400))
            cover = _int_or_default(chunkOverlap, getattr(settings, "CHUNK_OVERLAP_TOKENS", 50))
            mode = (chunkMode or "token").strip().lower()

            if mode == "paragraph":
                # Absatzbasiert, je Quelle separat (Metadaten erhalten)
                for rec in raw_records:
                    txt = str(rec.get("text") or "")
                    meta = dict(rec.get("meta") or {})
                    if not txt.strip():
                        continue
                    chunks_text = build_chunks_absatz(txt, chunk_size=max(1000, cmin), overlap=min(800, max(0, cover)))
                    for idx, ch in enumerate(chunks_text):
                        pl = dict(meta)
                        pl["chunkIndex"] = idx
                        payloads.append({"text": ch, "payload": pl})
            else:
                # Token-basiert (bestehende Heuristik)
                payloads = chunk_payloads(raw_records, cmin, cmax, cover)

            texts = [p["text"] for p in payloads]
            sources = [{"sourceFile": (p["payload"] or {}).get("sourceFile"), "chunkIndex": (p["payload"] or {}).get("chunkIndex")} for p in payloads]

        else:
            # JSON: erwarte { text, configId?, prompt_description?, examples? }
            try:
                body = await request.json()
            except Exception:
                body = {}
            txt = str((body or {}).get("text") or "").strip()
            if not txt:
                return JSONResponse(content={"error": "invalid_request", "message": "text fehlt oder multipart files fehlen"}, status_code=400)
            cfg_id_body = body.get("configId")
            if isinstance(cfg_id_body, str):
                configId = cfg_id_body
            payloads = [{"text": txt, "payload": {"sourceFile": "json:text", "chunkIndex": 0}}]
            texts = [txt]
            sources = [{"sourceFile": "json:text", "chunkIndex": 0}]
            # overrides aus JSON (optional)
            if body.get("chunkMode"):
                chunkMode = body.get("chunkMode")
            if body.get("structured") is not None:
                structured = bool(body.get("structured"))
            if body.get("fast") is not None:
                fast = bool(body.get("fast"))
            if body.get("temperature") is not None:
                try:
                    temperature = float(body.get("temperature"))
                except Exception:
                    temperature = None

        # 2) Konfiguration laden
        cfg = _lx_load_config(configId)
        prompt_desc = cfg.get("prompt_description") or "Extract requirements from text using exact spans and char_interval."
        examples_sdk = _lx_examples_to_sdk(cfg.get("examples") or [])

        # 3) LangExtract ausführen
        try:
            import langextract as lx  # type: ignore
        except Exception as imp_err:
            return JSONResponse(content={"error": "lx_unavailable", "message": str(imp_err)}, status_code=500)

        total_extractions = 0
        coverage_sum = 0.0

        for i, p in enumerate(payloads):
            txt = p.get("text") or ""
            # Temperaturstrategie: fast → eine Temperatur (0.2 / override), sonst konservativ (0.0)
            temp = temperature if isinstance(temperature, (int, float)) else (0.2 if bool(fast) else 0.0)
            try:
                res = lx.extract(
                    text_or_documents=txt,
                    prompt_description=prompt_desc,
                    examples=examples_sdk,
                    model_id=getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=getattr(settings, "OPENAI_API_KEY", None),
                    temperature=float(temp),
                )
                exts, covered, ratio = _normalize_lx_result(res, txt)
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({
                    "version": "le.v1",
                    "provider": "openai",
                    "model": getattr(settings, "OPENAI_MODEL", "gpt-4o-mini"),
                    "run_id": str(int(time.time())),
                    "extractions": exts,
                    "coverage": {"chunk_len": len(txt), "covered": covered, "coverage_ratio": round(ratio, 4)},
                    "evidence": {"sourceFile": (p["payload"] or {}).get("sourceFile"), "chunkIndex": (p["payload"] or {}).get("chunkIndex")},
                })
                total_extractions += len(exts)
                coverage_sum += ratio
            except Exception as le:
                p.setdefault("payload", {}).setdefault("lx", {})
                p["payload"]["lx"].update({"version": "le.v1", "error": str(le)})

        # 4) Vorschau erzeugen
        lx_preview = _lx_preview_from_payloads(payloads)

        # 5) Persistieren
        sha = hashlib.sha1(("||".join(texts)).encode("utf-8")).hexdigest() if texts else str(int(time.time()))
        save_id = f"lx_{sha[:10]}_{int(time.time())}"
        out = {
            "savedAt": int(time.time()),
            "configId": configId or "default",
            "prompt_description": prompt_desc,
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
            # Nicht kritisch
            pth = None

        return JSONResponse(
            content={
                "lxPreview": lx_preview,
                "savedAs": pth,
                "saveId": save_id,
                "configId": configId or "default",
                "chunks": len(payloads),
                "sourceText": "\n\n".join(texts) if texts else "",
            },
            status_code=200,
        )

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/lx/result/get")
def lx_result_get_v2(saveId: Optional[str] = None, latest: Optional[bool] = False) -> JSONResponse:
    """
    FastAPI-Port: komplettes gespeichertes LX-Ergebnis zurückgeben.
    - ?saveId=... | ?latest=1
    """
    try:
        target: Optional[str] = None
        if saveId:
            p = _lx_result_path(saveId)
            if os.path.exists(p):
                target = p
        if not target:
            # latest
            base_dir = os.path.dirname(_lx_result_path("dummy"))
            files = [os.path.join(base_dir, fn) for fn in os.listdir(base_dir) if fn.endswith(".json")]
            if not files:
                return JSONResponse(content={"result": None}, status_code=200)
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            target = files[0]
        with open(target, "r", encoding="utf-8") as f:
            data = _json.load(f)
        return JSONResponse(content={"result": data}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/lx/result/chunk")
def lx_result_chunk_v2(saveId: str, idx: int) -> JSONResponse:
    """
    FastAPI-Port: einzelnen Chunk (Text + Payload) aus gespeicherten Ergebnissen liefern.
    """
    try:
        if saveId is None:
            return JSONResponse(content={"error": "invalid_request", "message": "saveId fehlt"}, status_code=400)
        p = _lx_result_path(saveId)
        if not os.path.exists(p):
            return JSONResponse(content={"error": "not_found", "message": "result not found"}, status_code=404)
        with open(p, "r", encoding="utf-8") as f:
            data = _json.load(f)
        payloads = data.get("payloads") or []
        if idx < 0 or idx >= len(payloads):
            return JSONResponse(content={"error": "out_of_range", "message": "idx außerhalb des Bereichs"}, status_code=400)
        it = payloads[idx] or {}
        return JSONResponse(content={"idx": idx, "text": it.get("text"), "payload": it.get("payload")}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.get("/api/v1/lx/mine")
def lx_mine_from_results_v2(saveId: Optional[str] = None, latest: Optional[bool] = False) -> JSONResponse:
    """
    FastAPI-Port: Requirements-Items aus lxPreview ableiten (class=requirement).
    - ?saveId=... | ?latest=1
    """
    try:
        target: Optional[str] = None
        if saveId:
            p = _lx_result_path(saveId)
            if os.path.exists(p):
                target = p
        if not target:
            base_dir = os.path.dirname(_lx_result_path("dummy"))
            files = [os.path.join(base_dir, fn) for fn in os.listdir(base_dir) if fn.endswith(".json")]
            if not files:
                return JSONResponse(content={"items": []}, status_code=200)
            files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            target = files[0]
        with open(target, "r", encoding="utf-8") as f:
            data = _json.load(f)
        preview = data.get("lxPreview") or []
        items: List[Dict[str, Any]] = []
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
        return JSONResponse(content={"items": items}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)