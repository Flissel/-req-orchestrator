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
import json
from queue import Queue

from flask import Flask, request, jsonify, send_from_directory, redirect, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Import des Mining-Agents
from arch_team.agents.chunk_miner import ChunkMinerAgent

# KG-Abstraktion (Qdrant)
from arch_team.agents.kg_agent import KGAbstractionAgent
from arch_team.memory.qdrant_kg import QdrantKGClient

# Validation Services (backend_app_v2)
from backend_app_v2.services import EvaluationService, RequestContext, ServiceError
from backend_app.llm import llm_suggest, llm_rewrite
# Projektverzeichnisse
PROJECT_DIR = Path(__file__).resolve().parent.parent  # .../test (Projektwurzel)
FRONTEND_DIR = PROJECT_DIR / "frontend"               # .../test/frontend

app = Flask(__name__, static_folder=None)
CORS(app)
load_dotenv()

# Global registry for SSE clarification streams
# {session_id: Queue}
clarification_streams: Dict[str, Queue] = {}


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

        # Chunk-Parameter (optional)
        chunk_size = request.form.get("chunk_size") or request.args.get("chunk_size")
        chunk_overlap = request.form.get("chunk_overlap") or request.args.get("chunk_overlap")

        chunk_options = {}
        if chunk_size:
            try:
                chunk_options['max_tokens'] = int(chunk_size)
            except ValueError:
                pass
        if chunk_overlap:
            try:
                chunk_options['overlap_tokens'] = int(chunk_overlap)
            except ValueError:
                pass

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
        items = agent.mine_files_or_texts_collect(
            records,
            model=model,
            neighbor_refs=neighbor_refs,
            chunk_options=chunk_options
        )

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


@app.route("/api/v2/evaluate/single", methods=["POST"])
def evaluate_single():
    """
    Service-Layer: Single requirement evaluation via EvaluationService.

    Request (JSON):
      {
        "text": "requirement text",
        "criteria_keys": ["clarity", "testability"],  // optional
        "threshold": 0.7,  // optional
        "context": {}  // optional
      }

    Response:
      {
        "requirementText": "...",
        "evaluation": [{"criterion": "clarity", "score": 0.8, "passed": true, "feedback": "..."}],
        "score": 0.75,
        "verdict": "pass"
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        text = body.get("text", "").strip()

        if not text:
            return jsonify({"error": "invalid_request", "message": "text is required"}), 400

        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()

        result = svc.evaluate_single(
            text,
            context=body.get("context") or {},
            criteria_keys=body.get("criteria_keys"),
            threshold=body.get("threshold"),
            ctx=ctx
        )

        return jsonify(result)

    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/v2/evaluate/batch", methods=["POST"])
def evaluate_batch():
    """
    Service-Layer: Batch evaluation via EvaluationService.

    Request (JSON):
      {
        "items": ["req1", "req2", ...],
        "criteria_keys": ["clarity"],  // optional
        "threshold": 0.7,  // optional
        "context": {}  // optional
      }

    Response:
      [
        {
          "id": "item-1",
          "originalText": "...",
          "evaluation": [...],
          "score": 0.75,
          "verdict": "pass"
        },
        ...
      ]
    """
    try:
        body = request.get_json(silent=True) or {}
        items = body.get("items") or []

        if not isinstance(items, list):
            return jsonify({"error": "invalid_request", "message": "items must be a list"}), 400

        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()

        result = svc.evaluate_batch(
            items,
            context=body.get("context") or {},
            criteria_keys=body.get("criteria_keys"),
            threshold=body.get("threshold"),
            ctx=ctx
        )

        return jsonify(result)

    except ServiceError as se:
        return jsonify({"error": se.code, "message": se.message, "details": se.details}), 400
    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/v1/validate/batch", methods=["POST"])
def validate_batch_rewrite():
    """
    Validate and rewrite requirements.

    Request (JSON):
      ["req1", "req2", ...] or {"items": ["req1", "req2", ...]}

    Response:
      [
        {
          "id": 1,
          "originalText": "...",
          "correctedText": "...",
          "status": "accepted" | "rejected",
          "evaluation": [...],
          "score": 0.75,
          "verdict": "pass"
        },
        ...
      ]
    """
    try:
        payload = request.get_json(silent=True) or []

        if isinstance(payload, dict):
            items = payload.get("items") or []
        else:
            items = payload

        if not isinstance(items, list):
            return jsonify({"error": "invalid_request", "message": "items must be a list"}), 400

        # Evaluate batch
        ctx = RequestContext(request_id=request.headers.get("X-Request-Id"))
        svc = EvaluationService()
        eval_results = svc.evaluate_batch(items, ctx=ctx)

        # Rewrite each requirement
        results = []
        for idx, (original, eval_result) in enumerate(zip(items, eval_results), 1):
            try:
                rewritten = llm_rewrite(original, {})
            except Exception:
                rewritten = original

            results.append({
                "id": idx,
                "originalText": original,
                "correctedText": rewritten if rewritten else original,
                "status": "accepted" if eval_result.get("verdict") == "pass" else "rejected",
                "evaluation": eval_result.get("evaluation", []),
                "score": eval_result.get("score", 0.0),
                "verdict": eval_result.get("verdict", "fail")
            })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/v1/validate/suggest", methods=["POST"])
def validate_suggest():
    """
    Generate improvement suggestions for requirements.

    Request (JSON):
      ["req1", "req2", ...] or {"items": ["req1", "req2", ...]}

    Response:
      {
        "items": {
          "REQ_1": {"suggestions": [{"issue": "...", "fix": "..."}]},
          "REQ_2": {"suggestions": [...]},
          ...
        }
      }
    """
    try:
        payload = request.get_json(silent=True) or []

        if isinstance(payload, dict):
            items = payload.get("items") or []
        else:
            items = payload

        if not isinstance(items, list):
            return jsonify({"error": "invalid_request", "message": "items must be a list"}), 400

        # Generate suggestions for each requirement
        result_map = {}
        for idx, text in enumerate(items, 1):
            req_id = f"REQ_{idx}"
            try:
                suggestions = llm_suggest(text, {}) or []
                result_map[req_id] = {"suggestions": suggestions}
            except Exception as e:
                result_map[req_id] = {"suggestions": [], "error": str(e)}

        return jsonify({"items": result_map})

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/kg/search/semantic", methods=["POST"])
def kg_search_semantic():
    """
    Semantic duplicate detection using Qdrant.

    Request (JSON):
      {
        "requirements": ["req1", "req2", ...],
        "similarity_threshold": 0.90  // optional, default 0.90
      }

    Response:
      [
        {
          "req1_index": 0,
          "req2_index": 2,
          "req1_text": "...",
          "req2_text": "...",
          "similarity": 0.95,
          "is_duplicate": true
        },
        ...
      ]
    """
    try:
        body = request.get_json(silent=True) or {}
        requirements = body.get("requirements") or []
        threshold = float(body.get("similarity_threshold", 0.90))

        if not isinstance(requirements, list):
            return jsonify({"error": "invalid_request", "message": "requirements must be a list"}), 400

        # Use Qdrant to find semantic duplicates
        client = QdrantKGClient()
        duplicates = []

        # For each requirement, search for similar ones
        for i, req1 in enumerate(requirements):
            try:
                # Search for similar nodes
                similar = client.search_nodes(req1, top_k=len(requirements))

                for item in similar:
                    score = item.get("score", 0.0)
                    payload = item.get("payload", {})
                    req2_text = payload.get("text", "")

                    # Find index in original list
                    try:
                        j = requirements.index(req2_text)
                    except ValueError:
                        # Not in original list, skip
                        continue

                    # Skip self-comparison and already reported pairs
                    if i >= j:
                        continue

                    if score >= threshold:
                        duplicates.append({
                            "req1_index": i,
                            "req2_index": j,
                            "req1_text": req1,
                            "req2_text": req2_text,
                            "similarity": score,
                            "is_duplicate": True
                        })

            except Exception as e:
                print(f"[kg] semantic search failed for req {i}: {e}")
                continue

        return jsonify(duplicates)

    except Exception as e:
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/clarification/stream")
def clarification_stream():
    """
    Server-Sent Events (SSE) stream for real-time clarification questions.

    Frontend connects once and receives questions as they are asked by agents.
    Query params:
      - session_id: Unique session identifier (e.g., correlation_id)

    Event format:
      data: {"type": "question", "question_id": "...", "question": "...", "suggested_answers": [...]}
    """
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    # Create queue for this session
    q = Queue()
    clarification_streams[session_id] = q

    def event_stream():
        try:
            print(f"[SSE] Client connected for session {session_id}")
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Stream events from queue
            while True:
                msg = q.get()  # Blocks until message available
                if msg is None:  # Shutdown signal
                    break
                print(f"[SSE] Sending to {session_id}: {msg}")
                yield f"data: {json.dumps(msg)}\n\n"
        except GeneratorExit:
            print(f"[SSE] Client disconnected for session {session_id}")
        finally:
            clarification_streams.pop(session_id, None)
            print(f"[SSE] Cleaned up session {session_id}")

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/validation/run", methods=["POST"])
def validation_run():
    """
    Run Society of Mind requirements validation with user clarification support.

    Request (JSON):
      {
        "requirements": ["req1", "req2", ...],
        "correlation_id": "session-123",  # Same as frontend sessionId
        "criteria_keys": ["clarity", "testability"],  # optional
        "threshold": 0.7  # optional
      }

    This triggers the Society of Mind validation which may ask clarification questions via SSE.
    """
    try:
        body = request.get_json(silent=True) or {}
        requirements = body.get("requirements", [])
        correlation_id = body.get("correlation_id")
        criteria_keys = body.get("criteria_keys")
        threshold = body.get("threshold", 0.7)

        if not requirements:
            return jsonify({"error": "requirements required"}), 400
        if not correlation_id:
            return jsonify({"error": "correlation_id required"}), 400

        print(f"[Validation] Starting validation for {len(requirements)} requirements (session: {correlation_id})")

        # Import and run validation (async)
        import asyncio
        from arch_team.agents.requirements_agent import validate_requirements

        # Run validation in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                validate_requirements(
                    requirements,
                    criteria_keys=criteria_keys,
                    threshold=threshold,
                    correlation_id=correlation_id
                )
            )
            return jsonify(result)
        finally:
            loop.close()

    except Exception as e:
        print(f"[Validation] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "validation_failed", "message": str(e)}), 500


@app.route("/api/clarification/answer", methods=["POST"])
def clarification_answer():
    """
    Receive user's answer to a clarification question.

    Request (JSON):
      {
        "correlation_id": "session-123",  # Same as session_id
        "answer": "user's answer text"
      }

    This writes the answer to a file that the ask_user tool is polling for.
    """
    try:
        body = request.get_json(silent=True) or {}
        correlation_id = body.get("correlation_id", "").strip()
        answer = body.get("answer", "").strip()

        if not correlation_id:
            return jsonify({"error": "correlation_id required"}), 400
        if not answer:
            return jsonify({"error": "answer required"}), 400

        # Write answer to file (same mechanism as ask_user tool expects)
        tmp_dir = PROJECT_DIR / "data" / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        response_file = tmp_dir / f"clarification_{correlation_id}.txt"
        response_file.write_text(answer, encoding='utf-8')

        print(f"[Clarification] Answer received for {correlation_id}: {answer[:50]}...")

        return jsonify({
            "success": True,
            "correlation_id": correlation_id,
            "message": "Answer received"
        })

    except Exception as e:
        print(f"[Clarification] Error saving answer: {e}")
        return jsonify({"error": "internal_error", "message": str(e)}), 500


@app.route("/api/arch_team/process", methods=["POST"])
def arch_team_process():
    """
    Master Society of Mind endpoint for complete arch_team workflow.

    Executes all phases:
    1. ChunkMiner: Extract requirements from uploaded files
    2. KG Agent: Build Knowledge Graph
    3. Validator: Evaluate and improve requirements
    4. RAG: Detect duplicates and cluster requirements
    5. QA: Final quality review
    6. UserClarification: Ask user if needed

    Request (multipart/form-data):
      - files: List of files to process (.md, .txt, .pdf, .docx)
      - correlation_id: Session ID for user clarification (required)
      - model: LLM model (optional, default: gpt-4o-mini)
      - chunk_size: Chunk size in tokens (optional, default: 800)
      - chunk_overlap: Chunk overlap (optional, default: 200)
      - use_llm_kg: Use LLM for KG extraction (optional, default: true)
      - validation_threshold: Quality threshold (optional, default: 0.7)

    Response (JSON):
      {
        "success": bool,
        "workflow_status": "completed|failed",
        "result": {...}  # Complete workflow results
      }
    """
    try:
        # Parse multipart form data
        files = request.files.getlist('files')
        correlation_id = request.form.get('correlation_id')
        model = request.form.get('model', 'gpt-4o-mini')
        chunk_size = int(request.form.get('chunk_size', 800))
        chunk_overlap = int(request.form.get('chunk_overlap', 200))
        use_llm_kg = request.form.get('use_llm_kg', 'true').lower() in ('true', '1', 'yes', 'on')
        validation_threshold = float(request.form.get('validation_threshold', 0.7))

        if not files:
            return jsonify({"error": "files required"}), 400
        if not correlation_id:
            return jsonify({"error": "correlation_id required"}), 400

        print(f"[MasterWorkflow] Starting with {len(files)} file(s) (session: {correlation_id})")

        # Save uploaded files temporarily
        import tempfile
        temp_dir = Path(tempfile.mkdtemp(prefix="arch_team_"))
        file_paths = []

        for file in files:
            file_path = temp_dir / file.filename
            file.save(str(file_path))
            file_paths.append(str(file_path))
            print(f"[MasterWorkflow] Saved: {file.filename}")

        # Import and run master workflow (async)
        import asyncio
        from arch_team.agents.master_agent import run_master_workflow

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            run_master_workflow(
                files=file_paths,
                correlation_id=correlation_id,
                model=model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                use_llm_kg=use_llm_kg,
                validation_threshold=validation_threshold
            )
        )

        # Cleanup temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify(result)

    except Exception as e:
        print(f"[MasterWorkflow] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "workflow_status": "failed",
            "error": str(e)
        }), 500


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
    print("[service] Starting without debug mode (no watchdog restarts)")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)