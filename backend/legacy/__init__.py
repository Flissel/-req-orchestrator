# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from . import settings
from .db import init_db
from .api_lx_fixed import api_bp
from .batch import batch_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # Logging/Middleware registrieren
    from .logging_ext import setup_logging, register_request_logging, log_runtime_config_once
    logger = setup_logging()
    register_request_logging(app, logger)
    # Strukturierter runtime_config Snapshot einmalig
    log_runtime_config_once(logger)
    # CORS nur für API-Routen (explizit Methods/Headers für Preflight erlauben)
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
        max_age=86400,  # Preflight-Caching
    )

    # Globaler Preflight-Intercept vor Routing (verhindert 404/Redirects)
    @app.before_request
    def _global_api_preflight():
        # Intercept nur API-Preflights
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

# Globaler OPTIONS-Catch für alle /api/*-Pfade (verhindert 404 im Preflight)
    @app.route("/api/<path:_>", methods=["OPTIONS"])
    def _global_cors_preflight(_):
        # Leere 204-Antwort; Flask-CORS fügt die CORS-Header hinzu
        return ("", 204)
    # DB initialisieren (lazy - only when app is actually used)
    # Moved to first request handler to avoid import-time initialization
    # init_db()

    # Statische Auslieferung des Frontends (http://localhost:8081/)
    @app.get("/")
    def _index():
        return send_from_directory("frontend", "index.html")

    @app.get("/<path:filename>")
    def _assets(filename: str):
        return send_from_directory("frontend", filename)

    # Blueprints registrieren
    app.register_blueprint(api_bp, url_prefix="/")
    app.register_blueprint(batch_bp, url_prefix="/")

    return app


# Export für Gunicorn wsgi:app (lazy creation to avoid import-time DB init)
# app = create_app()
# Only create app when explicitly needed (e.g., in main.py via WSGIMiddleware)