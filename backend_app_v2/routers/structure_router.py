# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from backend_app.ingest import extract_texts
from backend_app_v2.api_v2_part2 import (
    _analyze_structure,
    _build_graph_from_components,
)

router = APIRouter(tags=["structure"])


@router.post("/api/v1/structure/analyze")
async def structure_analyze_endpoint_fastapi(
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    use_wtpsplit: Optional[bool] = Form(default=False),
) -> JSONResponse:
    """
    FastAPI-Port: Heuristische Struktur-Analyse (Abschnitte, Tabellenzeilen, Bullets, Paragraphs)
    - multipart/form-data: files=[...]
    - application/json: { text?: string, use_wtpsplit?: bool }
    """
    try:
        text = None
        content_type = (request.headers.get("content-type") or "").lower()
        if "multipart/form-data" in content_type:
            if not files:
                return JSONResponse(content={"error": "invalid_request", "message": "keine Dateien übergeben"}, status_code=400)
            parts = []
            for f in files:
                data = await f.read()
                fname = f.filename or "upload"
                ctype = f.content_type or ""
                parts.extend(extract_texts(fname, data, ctype))
            text = "\n\n".join([str(p.get("text") or "") for p in parts])
            # optional flag per form
            # use_wtpsplit wird bereits als Form-Parameter entgegengenommen
        else:
            try:
                body = await request.json()
            except Exception:
                body = {}
            text = str((body or {}).get("text") or "")
            use_wtpsplit = bool((body or {}).get("use_wtpsplit") or False)
        if not text or not text.strip():
            return JSONResponse(content={"error": "invalid_request", "message": "text oder files erforderlich"}, status_code=400)

        components = _analyze_structure(text)
        if use_wtpsplit:
            # Optional: feingranular Paragraphen in Sätze aufteilen (best-effort)
            try:
                from wtpsplit import WtP  # type: ignore
                splitter = WtP()
                refined: List[Dict[str, Any]] = []
                for c in components:
                    if str(c.get("extraction_class") or "").lower() == "paragraph":
                        ptxt = str(c.get("extraction_text") or "")
                        base_start = int(((c.get("char_interval") or {}).get("start_pos") or 0))
                        spans = splitter.split(ptxt, return_spans=True)
                        if spans:
                            for (s, e) in spans:
                                st = base_start + int(s)
                                en = base_start + int(e)
                                seg = ptxt[s:e].strip()
                                if len(seg) >= 8:
                                    nc = dict(c)
                                    nc["extraction_text"] = seg
                                    nc["char_interval"] = {"start_pos": st, "end_pos": en}
                                    refined.append(nc)
                            continue
                    refined.append(c)
                components = refined
            except Exception:
                # Wenn wtpsplit fehlt, liefern wir die grobe Struktur
                pass

        return JSONResponse(content={"components": components, "count": len(components)}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/structure/graph_export")
async def structure_graph_export_fastapi(
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    components: Optional[List[Dict[str, Any]]] = None,
) -> JSONResponse:
    """
    FastAPI-Port: Graph-Export
    - multipart/form-data: files=[...] -> führt analyze intern aus und exportiert Graph
    - application/json: { text?: string, components?: [...] }
    """
    try:
        text = None
        content_type = (request.headers.get("content-type") or "").lower()
        comps: List[Dict[str, Any]] = []

        if "multipart/form-data" in content_type:
            if not files:
                return JSONResponse(content={"error": "invalid_request", "message": "keine Dateien übergeben"}, status_code=400)
            parts = []
            for f in files:
                data = await f.read()
                fname = f.filename or "upload"
                ctype = f.content_type or ""
                parts.extend(extract_texts(fname, data, ctype))
            text = "\n\n".join([str(p.get("text") or "") for p in parts])
            comps = _analyze_structure(text)
        else:
            try:
                body = await request.json()
            except Exception:
                body = {}
            if isinstance(body.get("components"), list):
                comps = body.get("components") or []
            else:
                text = str((body or {}).get("text") or "")
                if not text.strip():
                    return JSONResponse(content={"error": "invalid_request", "message": "text oder components erforderlich"}, status_code=400)
                comps = _analyze_structure(text)

        nodes, edges = _build_graph_from_components(comps)
        jsonld = {
            "@context": {"@vocab": "https://example.org/req#"},
            "@graph": [
                {"@id": n["id"], "@type": n.get("type"), "name": n.get("payload", {}).get("name"),
                 "section_path": (n.get("payload", {}).get("section_path") or []),
                 "char_interval": n.get("payload", {}).get("char_interval")} for n in nodes
            ] + [
                {"@id": e["id"], "@type": "Edge", "from": e["from"], "to": e["to"], "rel": e["rel"]} for e in edges
            ]
        }
        return JSONResponse(content={"nodes": nodes, "edges": edges, "jsonld": jsonld}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)