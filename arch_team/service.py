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
- ARCH_TEAM_PORT: Port (Default 8000) [replaces deprecated APP_PORT]
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
import logging
from queue import Queue, Empty

from flask import Flask, request, jsonify, send_from_directory, redirect, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

# Configure logger
logger = logging.getLogger(__name__)

# Import des Mining-Agents
from arch_team.agents.chunk_miner import ChunkMinerAgent

# KG-Abstraktion (Qdrant)
from arch_team.agents.kg_agent import KGAbstractionAgent
from arch_team.memory.qdrant_kg import QdrantKGClient

# Validation Services (consolidated backend)
from backend.services import EvaluationService, RequestContext, ServiceError
from backend.core.llm import llm_suggest, llm_rewrite

# Manifest Integration
from backend.services.manifest_integration import create_manifests_from_chunkminer
from backend.core import db as _db
# Projektverzeichnisse
PROJECT_DIR = Path(__file__).resolve().parent.parent  # .../test (Projektwurzel)
FRONTEND_DIR = PROJECT_DIR / "frontend"               # .../test/frontend

app = Flask(__name__, static_folder=None)
CORS(app)
# Load .env from project root explicitly
# Use override=True to force loading even if empty env var exists
load_dotenv(PROJECT_DIR / ".env", override=True)

# Debug: Check if API key loaded correctly
api_key_status = "SET" if os.environ.get("OPENAI_API_KEY") else "MISSING"
print(f"[service.py] OPENAI_API_KEY status after load_dotenv: {api_key_status}")

# Initialize database schema if needed (for validation endpoints)
from backend.core.db import init_db
try:
    init_db()
    print("[service.py] Database initialized successfully")
except Exception as e:
    print(f"[service.py] Database initialization warning: {e}")

# Global registry for SSE clarification streams
# {session_id: Queue}
clarification_streams: Dict[str, Queue] = {}

# Global registry for SSE workflow message streams
# {session_id: Queue}
workflow_streams: Dict[str, Queue] = {}


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


@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint for monitoring and testing."""
    return jsonify({"status": "ok", "service": "arch_team"}), 200


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

        # Create manifests in database
        manifest_ids = []
        try:
            conn = _db.get_db()
            try:
                manifest_ids = create_manifests_from_chunkminer(conn, items)
                logger.info(f"[mining] Created {len(manifest_ids)} manifests")
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"[mining] Manifest creation failed: {e}")
            # Continue anyway - manifests are optional

        return jsonify({
            "success": True,
            "count": len(items),
            "items": items,
            "manifest_ids": manifest_ids
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


# ============================================================================
# RAG Endpoints (Semantic Analysis, Duplicate Detection, Coverage)
# ============================================================================

@app.route("/api/rag/duplicates", methods=["POST"])
def rag_find_duplicates():
    """
    Find semantic duplicate requirements using embeddings.

    Request (JSON):
      {
        "requirements": [{"req_id": "...", "text": "...", ...}, ...],
        "similarity_threshold": 0.90,  // optional, default 0.90
        "method": "embedding"  // optional, default "embedding"
      }

    Response:
      {
        "success": true,
        "duplicate_groups": [
          {
            "group_id": "dup_1",
            "requirements": [
              {"req_id": "REQ-001", "text": "...", "similarity": 1.0},
              {"req_id": "REQ-005", "text": "...", "similarity": 0.94}
            ],
            "avg_similarity": 0.97
          }
        ],
        "stats": {
          "total_requirements": 25,
          "unique_requirements": 23,
          "duplicate_groups": 2,
          "total_duplicates": 2
        }
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        requirements = body.get("requirements") or []
        threshold = float(body.get("similarity_threshold", 0.90))
        method = body.get("method", "embedding")

        if not isinstance(requirements, list):
            return jsonify({
                "success": False,
                "error": "requirements must be a list",
                "duplicate_groups": [],
                "stats": {"total_requirements": 0}
            }), 400

        if not requirements:
            return jsonify({
                "success": True,
                "duplicate_groups": [],
                "stats": {
                    "total_requirements": 0,
                    "unique_requirements": 0,
                    "duplicate_groups": 0,
                    "total_duplicates": 0
                }
            })

        # Use Qdrant for semantic duplicate detection
        client = QdrantKGClient()

        # Build similarity matrix
        req_texts = [r.get("text", "") for r in requirements]
        pairs = []  # List of (i, j, similarity)

        for i, req1 in enumerate(req_texts):
            if not req1.strip():
                continue

            try:
                # Search for similar requirements
                similar = client.search_nodes(req1, top_k=len(req_texts))

                for item in similar:
                    score = item.get("score", 0.0)
                    payload = item.get("payload", {})
                    req2_text = payload.get("text", "")

                    # Find index in original list
                    try:
                        j = req_texts.index(req2_text)
                    except ValueError:
                        continue

                    # Skip self-comparison
                    if i >= j:
                        continue

                    if score >= threshold:
                        pairs.append((i, j, score))

            except Exception as e:
                logger.warning(f"[RAG] Duplicate search failed for req {i}: {e}")
                continue

        # Group duplicates using Union-Find
        parent = list(range(len(requirements)))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Build groups
        for i, j, _ in pairs:
            union(i, j)

        # Collect groups
        groups_dict = {}
        for i in range(len(requirements)):
            root = find(i)
            if root not in groups_dict:
                groups_dict[root] = []
            groups_dict[root].append(i)

        # Filter groups with duplicates (size > 1)
        duplicate_groups = []
        group_counter = 1

        for indices in groups_dict.values():
            if len(indices) > 1:
                # Calculate similarities within group
                group_reqs = []
                similarities = []

                for idx in indices:
                    req = requirements[idx]
                    # Find max similarity to other members
                    max_sim = 1.0 if len(indices) == 1 else 0.0
                    for i, j, sim in pairs:
                        if (i == idx and j in indices) or (j == idx and i in indices):
                            max_sim = max(max_sim, sim)

                    group_reqs.append({
                        "req_id": req.get("req_id", f"REQ-{idx}"),
                        "text": req.get("text", ""),
                        "similarity": max_sim
                    })
                    similarities.append(max_sim)

                avg_sim = sum(similarities) / len(similarities) if similarities else 0.0

                duplicate_groups.append({
                    "group_id": f"dup_{group_counter}",
                    "requirements": group_reqs,
                    "avg_similarity": avg_sim
                })
                group_counter += 1

        # Calculate stats
        total_duplicates = sum(len(g["requirements"]) - 1 for g in duplicate_groups)
        unique_requirements = len(requirements) - total_duplicates

        return jsonify({
            "success": True,
            "duplicate_groups": duplicate_groups,
            "stats": {
                "total_requirements": len(requirements),
                "unique_requirements": unique_requirements,
                "duplicate_groups": len(duplicate_groups),
                "total_duplicates": total_duplicates
            }
        })

    except Exception as e:
        logger.error(f"[RAG] Duplicate detection failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "duplicate_groups": [],
            "stats": {"total_requirements": len(requirements) if requirements else 0}
        }), 500


@app.route("/api/rag/search", methods=["POST"])
def rag_semantic_search():
    """
    Semantic search for requirements similar to query.

    Request (JSON):
      {
        "query": "authentication and security",
        "requirements": [...],  // optional, if provided searches in this list
        "top_k": 10,  // optional, default 10
        "min_score": 0.7,  // optional, default 0.7
        "use_qdrant": true  // optional, default true
      }

    Response:
      {
        "results": [
          {
            "req_id": "REQ-001",
            "text": "System must authenticate users",
            "score": 0.92,
            "source": "requirements.docx",
            "metadata": {...}
          }
        ]
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        query = body.get("query", "").strip()
        requirements = body.get("requirements")
        top_k = int(body.get("top_k", 10))
        min_score = float(body.get("min_score", 0.7))
        use_qdrant = body.get("use_qdrant", True)

        if not query:
            return jsonify({"results": []}), 400

        client = QdrantKGClient()

        if requirements:
            # Search in provided list
            results = []

            for req in requirements:
                req_text = req.get("text", "")
                if not req_text.strip():
                    continue

                try:
                    # Use semantic similarity
                    similar = client.search_nodes(req_text, top_k=1)

                    if similar:
                        score = similar[0].get("score", 0.0)

                        if score >= min_score:
                            results.append({
                                "req_id": req.get("req_id", ""),
                                "text": req_text,
                                "score": score,
                                "source": req.get("source", ""),
                                "metadata": req.get("metadata", {})
                            })

                except Exception as e:
                    logger.warning(f"[RAG] Search failed for requirement: {e}")
                    continue

            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]

            return jsonify({"results": results})

        elif use_qdrant:
            # Search in Qdrant
            try:
                similar = client.search_nodes(query, top_k=top_k)

                results = []
                for item in similar:
                    score = item.get("score", 0.0)

                    if score >= min_score:
                        payload = item.get("payload", {})
                        results.append({
                            "req_id": payload.get("node_id", ""),
                            "text": payload.get("text", payload.get("name", "")),
                            "score": score,
                            "source": payload.get("source", ""),
                            "metadata": payload
                        })

                return jsonify({"results": results})

            except Exception as e:
                logger.error(f"[RAG] Qdrant search failed: {e}")
                return jsonify({"results": []}), 500

        else:
            return jsonify({"results": []}), 400

    except Exception as e:
        logger.error(f"[RAG] Semantic search failed: {e}")
        return jsonify({"error": str(e), "results": []}), 500


@app.route("/api/rag/related", methods=["POST"])
def rag_get_related():
    """
    Find requirements related to a specific requirement.

    Request (JSON):
      {
        "requirement_id": "REQ-001",
        "requirements": [...],
        "top_k": 5,  // optional, default 5
        "relationship_types": ["depends", "similar"]  // optional
      }

    Response:
      {
        "related": [
          {
            "req_id": "REQ-003",
            "text": "System must validate OAuth tokens",
            "relationship_type": "depends",
            "score": 0.88,
            "explanation": "REQ-001 authentication depends on token validation"
          }
        ]
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        requirement_id = body.get("requirement_id", "").strip()
        requirements = body.get("requirements") or []
        top_k = int(body.get("top_k", 5))
        relationship_types = body.get("relationship_types") or ["depends", "conflicts", "similar", "implements"]

        if not requirement_id or not requirements:
            return jsonify({"related": []}), 400

        # Find the source requirement
        source_req = None
        for req in requirements:
            if req.get("req_id") == requirement_id:
                source_req = req
                break

        if not source_req:
            return jsonify({"related": []}), 404

        source_text = source_req.get("text", "")

        # Use semantic search to find similar requirements
        client = QdrantKGClient()
        related = []

        try:
            similar = client.search_nodes(source_text, top_k=top_k * 2)

            for item in similar:
                payload = item.get("payload", {})
                req_id = payload.get("node_id", "")

                # Skip self
                if req_id == requirement_id:
                    continue

                score = item.get("score", 0.0)
                req_text = payload.get("text", payload.get("name", ""))

                # Determine relationship type based on score and text analysis
                relationship_type = "similar"
                explanation = f"Semantically similar (score: {score:.2f})"

                if score >= 0.95:
                    relationship_type = "similar"
                    explanation = f"Very similar requirement (score: {score:.2f})"
                elif "depend" in source_text.lower() or "require" in source_text.lower():
                    relationship_type = "depends"
                    explanation = f"Potential dependency relationship (score: {score:.2f})"
                elif "not" in source_text.lower() or "conflict" in source_text.lower():
                    relationship_type = "conflicts"
                    explanation = f"Potential conflict (score: {score:.2f})"

                # Filter by requested types
                if relationship_type in relationship_types:
                    related.append({
                        "req_id": req_id,
                        "text": req_text,
                        "relationship_type": relationship_type,
                        "score": score,
                        "explanation": explanation
                    })

                if len(related) >= top_k:
                    break

        except Exception as e:
            logger.error(f"[RAG] Related requirements search failed: {e}")

        return jsonify({"related": related})

    except Exception as e:
        logger.error(f"[RAG] Get related failed: {e}")
        return jsonify({"error": str(e), "related": []}), 500


@app.route("/api/rag/coverage", methods=["POST"])
def rag_analyze_coverage():
    """
    Analyze requirement coverage across categories.

    Request (JSON):
      {
        "requirements": [...],
        "categories": ["functional", "security", "performance"]  // optional
      }

    Response:
      {
        "success": true,
        "coverage": {
          "functional": {
            "count": 15,
            "percentage": 60.0,
            "subcategories": {"authentication": 5, "data": 10}
          },
          "security": {"count": 5, "percentage": 20.0},
          ...
        },
        "gaps": [
          {
            "category": "performance",
            "severity": "medium",
            "description": "Only 12% coverage in performance requirements",
            "recommendation": "Add performance benchmarks and SLAs"
          }
        ],
        "stats": {
          "total_requirements": 25,
          "categorized": 23,
          "uncategorized": 2
        }
      }
    """
    try:
        body = request.get_json(silent=True) or {}
        requirements = body.get("requirements") or []
        categories = body.get("categories") or ["functional", "non-functional", "security", "performance", "usability"]

        if not requirements:
            return jsonify({
                "success": False,
                "error": "No requirements provided",
                "coverage": {},
                "gaps": [],
                "stats": {"total_requirements": 0}
            }), 400

        # Categorize requirements using simple keyword matching
        coverage_data = {cat: {"count": 0, "percentage": 0.0, "subcategories": {}} for cat in categories}
        uncategorized = []

        # Category keywords
        category_keywords = {
            "functional": ["must", "shall", "should", "function", "feature", "capability"],
            "non-functional": ["performance", "scalability", "reliability", "maintainability"],
            "security": ["security", "auth", "encrypt", "access", "permission", "secure"],
            "performance": ["performance", "speed", "latency", "response time", "throughput"],
            "usability": ["usability", "user", "interface", "experience", "ui", "ux"]
        }

        for req in requirements:
            text = req.get("text", "").lower()
            categorized = False

            for cat in categories:
                if cat in category_keywords:
                    keywords = category_keywords[cat]
                    if any(kw in text for kw in keywords):
                        coverage_data[cat]["count"] += 1
                        categorized = True
                        break

            if not categorized:
                uncategorized.append(req.get("req_id", ""))

        # Calculate percentages
        total = len(requirements)
        for cat in categories:
            count = coverage_data[cat]["count"]
            coverage_data[cat]["percentage"] = (count / total * 100) if total > 0 else 0.0

        # Identify gaps
        gaps = []
        for cat in categories:
            percentage = coverage_data[cat]["percentage"]

            if percentage < 10:
                gaps.append({
                    "category": cat,
                    "severity": "critical",
                    "description": f"Only {percentage:.1f}% coverage in {cat} requirements",
                    "recommendation": f"Add more {cat} requirements to ensure comprehensive coverage"
                })
            elif percentage < 20:
                gaps.append({
                    "category": cat,
                    "severity": "medium",
                    "description": f"Low coverage ({percentage:.1f}%) in {cat} requirements",
                    "recommendation": f"Consider expanding {cat} requirements"
                })

        return jsonify({
            "success": True,
            "coverage": coverage_data,
            "gaps": gaps,
            "stats": {
                "total_requirements": total,
                "categorized": total - len(uncategorized),
                "uncategorized": len(uncategorized)
            }
        })

    except Exception as e:
        logger.error(f"[RAG] Coverage analysis failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "coverage": {},
            "gaps": [],
            "stats": {"total_requirements": 0}
        }), 500


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

            # Stream events from queue with timeout
            while True:
                try:
                    msg = q.get(timeout=30)  # Timeout after 30 seconds
                    if msg is None:  # Shutdown signal
                        break
                    print(f"[SSE] Sending to {session_id}: {msg}")
                    yield f"data: {json.dumps(msg)}\n\n"
                except Empty:
                    # Send keepalive ping every 30 seconds
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except GeneratorExit:
            print(f"[SSE] Client disconnected for session {session_id}")
        finally:
            clarification_streams.pop(session_id, None)
            print(f"[SSE] Cleaned up session {session_id}")

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/workflow/stream")
def workflow_stream():
    """
    Server-Sent Events (SSE) stream for real-time workflow messages.

    Frontend connects once and receives agent messages as they occur during workflow.
    Query params:
      - session_id: Unique session identifier (e.g., correlation_id)

    Event format:
      data: {"type": "agent_message", "agent": "Orchestrator", "message": "...", "timestamp": "..."}
      data: {"type": "workflow_status", "status": "running|completed|failed"}
      data: {"type": "workflow_result", "result": {...}}
    """
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    # Create queue for this session
    q = Queue()
    workflow_streams[session_id] = q

    def event_stream():
        try:
            print(f"[Workflow SSE] Client connected for session {session_id}")
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Stream events from queue with timeout
            while True:
                try:
                    msg = q.get(timeout=30)  # Timeout after 30 seconds
                    if msg is None:  # Shutdown signal
                        break
                    print(f"[Workflow SSE] Sending to {session_id}: {msg.get('type', 'unknown')}")
                    yield f"data: {json.dumps(msg)}\n\n"
                except Empty:
                    # Send keepalive ping every 30 seconds
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except GeneratorExit:
            print(f"[Workflow SSE] Client disconnected for session {session_id}")
        finally:
            workflow_streams.pop(session_id, None)
            print(f"[Workflow SSE] Cleaned up session {session_id}")

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
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.error("[arch_team_process] === FUNCTION ENTERED ===")
    sys.stderr.write("[arch_team_process] === FUNCTION ENTERED ===\n")
    sys.stderr.flush()

    try:
        # Parse multipart form data
        files = request.files.getlist('files')
        correlation_id = request.form.get('correlation_id')
        model = request.form.get('model', 'gpt-4o-mini')

        # Safely parse chunk_size with fallback
        chunk_size_raw = request.form.get('chunk_size', '800')
        try:
            chunk_size = int(chunk_size_raw) if chunk_size_raw and chunk_size_raw != 'undefined' else 800
        except ValueError:
            chunk_size = 800

        # Safely parse chunk_overlap with fallback
        chunk_overlap_raw = request.form.get('chunk_overlap', '200')
        try:
            chunk_overlap = int(chunk_overlap_raw) if chunk_overlap_raw and chunk_overlap_raw != 'undefined' else 200
        except ValueError:
            chunk_overlap = 200

        use_llm_kg = request.form.get('use_llm_kg', 'true').lower() in ('true', '1', 'yes', 'on')
        validation_threshold = float(request.form.get('validation_threshold', 0.7))

        if not files:
            return jsonify({"error": "files required"}), 400
        if not correlation_id:
            return jsonify({"error": "correlation_id required"}), 400

        import sys
        sys.stderr.write(f"[MasterWorkflow] Starting with {len(files)} file(s) (session: {correlation_id})\n")
        sys.stderr.flush()

        # Debug: Check API key status before workflow
        api_key_check = os.environ.get("OPENAI_API_KEY", "")
        sys.stderr.write(f"[MasterWorkflow] OPENAI_API_KEY length before workflow: {len(api_key_check)}\n")
        sys.stderr.flush()

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
        import sys
        import traceback
        error_msg = f"[MasterWorkflow] Error: {e}"
        traceback_str = traceback.format_exc()

        # Log to multiple outputs to ensure visibility
        print(error_msg)
        print(traceback_str)
        sys.stderr.write(f"{error_msg}\n")
        sys.stderr.write(f"{traceback_str}\n")
        sys.stderr.flush()

        return jsonify({
            "success": False,
            "workflow_status": "failed",
            "error": str(e),
            "traceback": traceback_str
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
    # Use centralized port configuration with legacy fallback
    port = _ports.ARCH_TEAM_PORT if _ports else int(os.environ.get("ARCH_TEAM_PORT", os.environ.get("APP_PORT", "8000")))
    # Hinweis: Für Produktion eher über WSGI/ASGI-Server starten (gunicorn/uvicorn).
    print(f"[service] FRONTEND_DIR={FRONTEND_DIR.resolve()}")
    print("[service] Try: http://localhost:%d/frontend/mining_demo.html" % port)
    print("[service] Starting without debug mode (no watchdog restarts)")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)