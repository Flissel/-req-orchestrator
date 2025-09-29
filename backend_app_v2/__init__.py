# -*- coding: utf-8 -*-
"""
KORRIGIERTE BACKEND-APP V2
LangExtract-Fixes implementiert
"""

from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS

from backend_app import settings
from backend_app.db import init_db
from .api_v2 import api_bp
from backend_app.batch import batch_bp
from pathlib import Path

def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    # Projektpfade (absolut), damit Static-Serving unabhängig vom CWD funktioniert
    PROJECT_DIR = Path(__file__).resolve().parent.parent  # .../test
    FRONTEND_DIR = PROJECT_DIR / "frontend"

    # Lightweight debug context
    import os
    import sys
    import platform
    import time
    import importlib

    APP_VERSION = os.environ.get("APP_VERSION", "v2.1")

    def _module_available(name: str) -> bool:
        try:
            return importlib.util.find_spec(name) is not None
        except Exception:
            return False
    
    def _optional_modules_state():
        names = [
            "magika",
            "docling",
            "wtpsplit",
            "sentence_transformers",
            "transformers",
            "torch",
            "fitz",
            "docx",
            "tiktoken",
        ]
        return {n: _module_available(n) for n in names}

    # Logging/Middleware registrieren
    from backend_app.logging_ext import setup_logging, register_request_logging, log_runtime_config_once
    logger = setup_logging()
    register_request_logging(app, logger)
    log_runtime_config_once(logger)

    # CORS für API-Routen
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": ["http://localhost:8081", "*"],
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Accept", "Authorization"],
            }
        },
        supports_credentials=False,
        max_age=86400,
    )

    # Globaler Preflight-Intercept
    @app.before_request
    def _global_api_preflight():
        if request.method == "OPTIONS" and request.path.startswith("/api/"):
            resp = app.make_response(("", 204))
            h = resp.headers
            origin = request.headers.get("Origin", "*")
            h["Access-Control-Allow-Origin"] = origin
            h["Vary"] = "Origin"
            h["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            req_headers = request.headers.get(
                "Access-Control-Request-Headers",
                "Content-Type, Accept, Authorization",
            )
            h["Access-Control-Allow-Headers"] = req_headers
            h["Access-Control-Max-Age"] = "86400"
            return resp
        return None

    # Nach jeder API-Antwort: knappe Debug-Header mitschicken
    @app.after_request
    def _attach_debug_headers(response):
        try:
            if request.path.startswith("/api/"):
                response.headers["X-Proc-PID"] = str(os.getpid())
                response.headers["X-Python"] = platform.python_version()
                response.headers["X-Python-Impl"] = platform.python_implementation()
                response.headers["X-App-Version"] = APP_VERSION
        except Exception:
            # Keine Debug-Fehler in den normalen Fluss propagieren
            pass
        return response

    @app.route("/api/<path:_>", methods=["OPTIONS"])
    def _global_cors_preflight(_):
        return ("", 204)

    # DB initialisieren
    init_db()

    # Statische Auslieferung des Frontends
    @app.get("/")
    def _index():
        return send_from_directory(str(FRONTEND_DIR.resolve()), "index.html")

    @app.get("/<path:filename>")
    def _assets(filename: str):
        return send_from_directory(str(FRONTEND_DIR.resolve()), filename)

    # Static-Serve für das eingebettete TAG-Repo (TextAnnotationGraphs)
    # Beispiel: http://localhost:8087/tag/demo/index.html
    @app.get("/tag/<path:filename>")
    def _serve_tag_repo(filename: str):
        tag_dir = PROJECT_DIR / "dev" / "external" / "TextAnnotationGraphs"
        return send_from_directory(str(tag_dir.resolve()), filename)

    # Blueprints und v2-Teilmodule registrieren
    # WICHTIG: api_v2_part2 importieren, damit die Routen (z. B. /api/v1/lx/*) gebunden werden
    try:
        from . import api_v2_part2  # noqa: F401
    except Exception:
        pass

    app.register_blueprint(api_bp, url_prefix="/")
    app.register_blueprint(batch_bp, url_prefix="/")

    # Leichtgewichtiger Debug-Endpoint
    @app.get("/api/v1/debug/info")
    def debug_info():
        now = time.time()
        return jsonify({
            "status": "ok",
            "timestamp": now,
            "process": {
                "pid": os.getpid(),
                "python_executable": sys.executable,
                "python_version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "platform": platform.platform(),
            },
            "app": {
                "version": APP_VERSION,
                "cwd": os.getcwd(),
            },
            "env": {
                "API_HOST": os.environ.get("API_HOST"),
                "API_PORT": os.environ.get("API_PORT"),
            },
            "modules": _optional_modules_state(),
        })

    return app

# Export für Gunicorn
app = create_app()