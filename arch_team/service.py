# -*- coding: utf-8 -*-
"""
Minimaler Web-Service (Flask) für Requirements-Mining:
- POST /api/mining/upload (multipart): Nimmt .md/.txt/.pdf/... entgegen
  und gibt die geminten Requirement-DTOs als JSON zurück.
- Statische Demo-Seite: /frontend/mining_demo.html (aus dem Ordner 'frontend')
Start:
  python -m arch_team.service
oder:
  python arch_team/service.py

ENV:
- MODEL_NAME: Default Modellname (z. B. "gpt-4o-mini")
- APP_PORT: Port (Default 8000)
- CHUNK_MINER_NEIGHBORS: "1|true|yes|on" um Nachbarschafts-Evidenz per Default zu aktivieren
"""
from __future__ import annotations

import io
import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Any
import threading

from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from dotenv import load_dotenv

# Import des Mining-Agents
from arch_team.agents.chunk_miner import ChunkMinerAgent

# KG-Abstraktion (Qdrant)
from arch_team.agents.kg_agent import KGAbstractionAgent
from arch_team.memory.qdrant_kg import QdrantKGClient
# Projektverzeichnisse
PROJECT_DIR = Path(__file__).resolve().parent.parent  # .../test (Projektwurzel)
FRONTEND_DIR = PROJECT_DIR / "frontend"               # .../test/frontend

app = Flask(__name__, static_folder=None)
CORS(app)
load_dotenv()


def _truthy(s: str | None) -> bool:
    if not s:
        return False
    return s.strip().lower() in ("1", "true", "yes", "on")


def _file_to_record(fs) -> Dict[str, Any]:
    # fs ist eine werkzeug.datastructures.FileStorage Instanz
    filename = fs.filename or "upload.bin"
    data = fs.read() or b""
    ct = fs.mimetype or mimetypes.guess_type(filename)[0] or ""
    return {"filename": filename, "data": data, "content_type": ct}


@app.route("/api/mining/upload", methods=["POST"])
def mining_upload():
    """
    Multipart Upload:
      - Feldname: "file" (einzeln oder mehrfach) oder "files" (mehrfach)
      - Form Felder:
          model: optionaler Modellname
          neighbor_refs: "1|true|yes|on" für Nachbarschafts-Belege (±1)
    Antwort:
      { "success": true, "count": N, "items": [ DTO, ... ] }
    """
    try:
        # Dateien einsammeln (unterstützt "file" oder "files")
        files = []
        if "file" in request.files:
            files.extend(request.files.getlist("file"))
        if "files" in request.files:
            files.extend(request.files.getlist("files"))

        if not files:
            return jsonify({"success": False, "message": "No files uploaded"}), 400

        neighbor_refs = _truthy(request.form.get("neighbor_refs")) or _truthy(request.args.get("neighbor_refs"))
        model = (request.form.get("model") or request.args.get("model") or "").strip() or None

        # In Agent-Records normalisieren
        records: List[Dict[str, Any]] = []
        for fs in files:
            try:
                records.append(_file_to_record(fs))
            except Exception as e:
                # fahre fort, wenn eine Datei fehlschlägt
                print(f"[mining] read failed for {getattr(fs, 'filename', '?')}: {e}")

        if not records:
            return jsonify({"success": False, "message": "Failed to read uploads"}), 400

        # Agent ausführen (sammelt DTOs, sendet sie nicht an ReqWorker)
        agent = ChunkMinerAgent(source="web", default_model=os.environ.get("MODEL_NAME"))
        items = agent.mine_files_or_texts_collect(records, model=model, neighbor_refs=neighbor_refs)

        return jsonify({
            "success": True,
            "count": len(items),
            "items": items
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Mining failed: {e}"}), 500

@app.route("/api/mining/report", methods=["POST"])
def mining_report():
    """
    Erzeugt einen kompakten Markdown-Report aus bereits geminten DTOs.

    Request (JSON):
      { "items": [ {"req_id","title","tag","evidence_refs":[...]}, ... ] }

    Response (JSON):
      { "success": true, "markdown": "...", "count": N, "items": [...] }
    """
    try:
        body = request.get_json(silent=True) or {}
        items = body.get("items") or []
        if not isinstance(items, list) or not items:
            return jsonify({"success": False, "message": "items must be a non-empty list"}), 400

        lines = ["# Requirements Report", ""]
        for it in items:
            rid = it.get("req_id") or it.get("reqId") or it.get("id") or "REQ-XXX"
            title = it.get("title") or it.get("redefinedRequirement") or it.get("final") or ""
            tag = (it.get("tag") or it.get("category") or "").lower()
            cites = it.get("evidence_refs") or it.get("evidenceRefs") or it.get("citations") or []
            sources = []
            if isinstance(cites, list):
                try:
                    for c in cites:
                        if isinstance(c, dict):
                            src = c.get("sourceFile") or c.get("source") or ""
                            if src:
                                sources.append(src)
                except Exception:
                    pass
            src_str = ", ".join(sorted(set(sources)))
            lines.append(f"- {rid} [{tag}]: {title} (src: {src_str})")

        md = "\n".join(lines)
        return jsonify({"success": True, "markdown": md, "count": len(items), "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": f"Report generation failed: {e}"}), 500
def _persist_kg_async(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """Persistiert Nodes/Edges asynchron in Qdrant (Best Effort)."""
    try:
        client = QdrantKGClient()
        client.ensure_collections()
        client.upsert_nodes(nodes or [])
        client.upsert_edges(edges or [])
    except Exception as e:
        print(f"[kg] async persist failed: {e}")

@app.route("/api/kg/build", methods=["POST"])
def kg_build():
    """
    Baut aus den geminten Requirement-DTOs einen Knowledge Graph und persistiert in Qdrant.
    Request (JSON):
      {
        "items": [DTO, ...],               # Liste der Mining-DTOs (req_id,title,tag,evidence_refs)
        "options": {
          "persist": "qdrant",             # default: "qdrant"
          "use_llm": false,                # optional: LLM-gestützte Verfeinerung (benötigt OPENAI_API_KEY)
          "use_llm_fallback": true,        # optional: Falls Heuristik nichts findet, einmaliger LLM-Fallback
          "model": "gpt-4o-mini"           # optional: Modelloverride
        },
        "model": "..."                     # optionaler Modellname (Top-Level alternative zu options.model)
      }
    Antwort:
      { "success": true, "stats": {...}, "nodes": [...], "edges": [...] }
    """
    try:
        body = request.get_json(silent=True) or {}
        items = body.get("items") or body.get("data") or []
        if not isinstance(items, list) or not items:
            return jsonify({"success": False, "message": "items must be a non-empty list"}), 400

        options = body.get("options") or {}

        def _to_bool(v: Any) -> bool:
            if isinstance(v, bool):
                return v
            if v is None:
                return False
            return str(v).strip().lower() in ("1", "true", "yes", "on")

        use_llm = _to_bool(options.get("use_llm") or request.args.get("use_llm"))
        llm_fallback = _to_bool(options.get("use_llm_fallback"))
        # Default: Fallback aktiv, wenn nicht explizit gesetzt
        if options.get("use_llm_fallback") is None and request.args.get("use_llm_fallback") is None:
            llm_fallback = True
        persist_async = _to_bool(options.get("persist_async") or request.args.get("persist_async"))
        # Default: persist_async aktiv für schnellere Antwort, wenn nicht explizit gesetzt
        if options.get("persist_async") is None and request.args.get("persist_async") is None:
            persist_async = True
        persist = (options.get("persist") or request.args.get("persist") or "qdrant").strip().lower()
        model = (body.get("model") or options.get("model") or request.args.get("model") or "").strip() or None

        agent = KGAbstractionAgent(default_model=os.environ.get("MODEL_NAME"))

        if persist_async:
            # Zügig Nodes/Edges erzeugen (ohne Sync-Persistenz) und im Hintergrund persistieren
            result = agent.run(items, model=model, persist="none", use_llm=use_llm, llm_fallback=llm_fallback, dedupe=True)
            nodes = result.get("nodes") or []
            edges = result.get("edges") or []
            try:
                threading.Thread(target=_persist_kg_async, args=(nodes, edges), daemon=True).start()
            except Exception as e:
                # beste Mühe, aber Antwort soll nicht blockieren
                print(f"[kg] persist_async spawn failed: {e}")
            stats = result.get("stats") or {}
            stats["persist_async"] = True
            return jsonify({
                "success": True,
                "stats": stats,
                "nodes": nodes,
                "edges": edges,
            })
        else:
            # synchrone Persistenz (wie bisher)
            result = agent.run(items, model=model, persist=persist, use_llm=use_llm, llm_fallback=llm_fallback, dedupe=True)
            return jsonify({
                "success": True,
                "stats": result.get("stats") or {},
                "nodes": result.get("nodes") or [],
                "edges": result.get("edges") or [],
            })
    except Exception as e:
        return jsonify({"success": False, "message": f"KG build failed: {e}"}), 500


@app.route("/api/kg/search/nodes", methods=["GET"])
def kg_search_nodes():
    """
    Semantische Knotensuche im KG.
    Query-Parameter:
      - query: Suchtext (Pflicht)
      - top_k: Anzahl Ergebnisse (optional, Default 10)
    Antwort: { success, items: [{id, score, payload}, ...] }
    """
    try:
        query = (request.args.get("query") or "").strip()
        top_k = int(request.args.get("top_k") or "10")
        if not query:
            return jsonify({"success": False, "message": "query required"}), 400
        client = QdrantKGClient()
        items = client.search_nodes(query, top_k=top_k)
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": f"KG search nodes failed: {e}"}), 500


@app.route("/api/kg/search/edges", methods=["GET"])
def kg_search_edges():
    """
    Semantische Kantensuche im KG.
    Query-Parameter:
      - query: Suchtext (Pflicht)
      - top_k: Anzahl Ergebnisse (optional, Default 10)
    Antwort: { success, items: [{id, score, payload}, ...] }
    """
    try:
        query = (request.args.get("query") or "").strip()
        top_k = int(request.args.get("top_k") or "10")
        if not query:
            return jsonify({"success": False, "message": "query required"}), 400
        client = QdrantKGClient()
        items = client.search_edges(query, top_k=top_k)
        return jsonify({"success": True, "items": items})
    except Exception as e:
        return jsonify({"success": False, "message": f"KG search edges failed: {e}"}), 500


@app.route("/api/kg/neighbors", methods=["GET"])
def kg_neighbors():
    """
    1-Hop Nachbarschaft eines Knotens.
    Query-Parameter:
      - node_id: ID des Ausgangsknotens (Pflicht)
      - rel: optionale kommaseparierte Liste von Relationstypen (z. B. "HAS_ACTION,ON_ENTITY")
      - dir: "in" | "out" | "both" (Default "both")
      - limit: Max. Anzahl Kanten (Default 200)
    Antwort: { success, nodes: [...], edges: [...] } (Payloads aus Qdrant)
    """
    try:
        node_id = (request.args.get("node_id") or "").strip()
        if not node_id:
            return jsonify({"success": False, "message": "node_id required"}), 400
        direction = (request.args.get("dir") or "both").strip().lower()
        rel = (request.args.get("rel") or "").strip()
        rels = None
        if rel:
            rels = [r.strip() for r in rel.split(",") if r.strip()]
        limit = int(request.args.get("limit") or "200")

        client = QdrantKGClient()
        data = client.neighbors(node_id=node_id, rels=rels, direction=direction, limit=limit)
        return jsonify({
            "success": True,
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"KG neighbors failed: {e}"}), 500


@app.route("/")
def index():
    # Leite auf die Demo-Seite weiter, falls vorhanden
    demo_path = FRONTEND_DIR / "mining_demo.html"
    if demo_path.exists():
        return redirect("/frontend/mining_demo.html", code=302)
    return jsonify({"message": "Service up. POST /api/mining/upload or open /frontend/mining_demo.html"})


@app.route("/frontend/<path:filename>")
def serve_frontend(filename: str):
    """
    Statische Dateien aus dem 'frontend' Ordner ausliefern.
    """
    directory = str(FRONTEND_DIR.resolve())
    return send_from_directory(directory, filename)

# Explizite Route für die Demo-HTML (Diagnose gegen 404)
@app.route("/frontend/mining_demo.html")
def serve_demo_html():
    directory = str(FRONTEND_DIR.resolve())
    return send_from_directory(directory, "mining_demo.html")

# Favicon-Stub, um 404 zu vermeiden
@app.route("/favicon.ico")
def favicon():
    return ("", 204)


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", "8000"))
    # Hinweis: Für Produktion eher über WSGI/ASGI-Server starten (gunicorn/uvicorn).
    print(f"[service] FRONTEND_DIR={FRONTEND_DIR.resolve()}")
    print("[service] Try: http://localhost:%d/frontend/mining_demo.html" % port)
    app.run(host="0.0.0.0", port=port, debug=True)