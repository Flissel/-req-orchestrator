#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UVICORN-KOMPATIBLE MAIN.PY FÜR BACKEND_APP_V2
Startet die korrigierte Version mit LangExtract-Fixes
"""

import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Import der korrigierten Flask-App
# DISABLED: Flask import disabled to prevent route conflicts with FastAPI
# from . import app as flask_app
# Neon: FastAPI-Router (LX)
from .routers.lx_router import router as lx_router
from .routers.structure_router import router as structure_router
from .routers.gold_router import router as gold_router
from .routers.validate_router import router as validate_router
from .routers.vector_router import router as vector_router
from .routers.corrections_router import router as corrections_router
from .routers.batch_router import router as batch_router
from .routers.manifest_router import router as manifest_router
import uuid
import json
import logging
import hashlib  # für sticky Variant-Berechnung
# Import für Runtime-Config
from backend.core.settings import get_runtime_config as get_runtime_config_v1
# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None

# Erstelle FastAPI-App als Wrapper
fastapi_app = FastAPI(
    title="Requirements Mining API V2",
    description="Korrigierte Version mit LangExtract-Fixes (Hybrid: FastAPI-Router + eingebettetes Flask).",
    version="2.0.0"
)
# Globale CORS-Policy (vereinheitlicht)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Request-ID Middleware (Observability)

@fastapi_app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())

    # Canary/Cutover Feature Flags (nur Markierung/Observability, kein Routing-Umschalter):
    # - FEATURE_FLAG_USE_V2: wenn true → v2 (100%)
    # - CANARY_PERCENT: 0..100 (int), sticky via Hash(Request-Id)
    feature_use_v2 = (os.environ.get("FEATURE_FLAG_USE_V2", "false").strip().lower() in ("1", "true", "yes", "on"))
    try:
        canary_percent = int(os.environ.get("CANARY_PERCENT", "0"))
    except Exception:
        canary_percent = 0
    canary_percent = max(0, min(100, canary_percent))

    # Sticky Auswahl basierend auf Request-ID Hash
    def _sticky_canary_choice(req_id: str) -> bool:
        try:
            h = hashlib.sha256((req_id or "").encode("utf-8")).hexdigest()
            bucket = int(h[:8], 16) % 100  # 0..99
            return bucket < canary_percent
        except Exception:
            return False

    variant = "v2" if (feature_use_v2 or _sticky_canary_choice(rid)) else "v1"
    variant_reason = "flag" if feature_use_v2 else ("canary" if canary_percent > 0 else "default")

    # Structured JSON log (request start)
    try:
        logging.info(json.dumps({
            "event": "request_start",
            "requestId": rid,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query or ""),
            "client": getattr(request.client, "host", None),
            "userAgent": request.headers.get("user-agent"),
            "variant": variant,
            "variantReason": variant_reason,
            "canaryPercent": canary_percent
        }))
    except Exception:
        pass

    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    response.headers["X-Variant"] = variant
    response.headers["X-Variant-Reason"] = variant_reason
    # optionales Sticky-Cookie (nur Info)
    try:
        response.set_cookie("variant", variant, max_age=3600, httponly=False, samesite="Lax")
    except Exception:
        pass

    # Structured JSON log (request end)
    try:
        logging.info(json.dumps({
            "event": "request_end",
            "requestId": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "variant": variant
        }))
    except Exception:
        pass
    return response

# FastAPI-Router registrieren (erscheint in /docs)
fastapi_app.include_router(lx_router)
fastapi_app.include_router(structure_router)
fastapi_app.include_router(gold_router)
fastapi_app.include_router(validate_router)
fastapi_app.include_router(vector_router)
fastapi_app.include_router(corrections_router)
fastapi_app.include_router(batch_router)
fastapi_app.include_router(manifest_router)

# Mount Flask-App unter Root, damit Routen wie /api/v1/* direkt erreichbar sind
# DISABLED: Flask mount conflicts with FastAPI routers - using FastAPI v2 exclusively
# fastapi_app.mount("/", WSGIMiddleware(flask_app))

# Health-Endpoint für FastAPI
@fastapi_app.get("/health")
async def health():
    return {"status": "ok", "version": "v2"}

@fastapi_app.get("/api/runtime-config")
async def runtime_config_v2():
    try:
        return get_runtime_config_v1()
    except Exception as e:
        return {"error": "internal_error", "message": str(e)}

@fastapi_app.get("/ready")
async def readiness():
    return {"status": "ok", "checks": {"app": "fastapi", "flask_mount": False}}

@fastapi_app.get("/livez")
async def liveness():
    return {"status": "ok"}

if __name__ == "__main__":
    # Konfiguration aus Umgebungsvariablen
    host = os.getenv("API_HOST", "0.0.0.0")
    # Use centralized port configuration with legacy fallback
    port = _ports.BACKEND_PORT if _ports else int(os.getenv("BACKEND_PORT", os.getenv("API_PORT", "8087")))

    print("🚀 Starting Requirements Mining API V2" )
    print(f"📍 Host: {host}:{port}")
    print(f"🔗 Frontend: http://{host}:{port}/mining_demo.html")
    print(f"📊 API: http://{host}:{port}/api/v1/files/ingest")

    uvicorn.run(
        "backend_app_v2.main:fastapi_app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )