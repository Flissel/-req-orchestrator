#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UVICORN-KOMPATIBLE MAIN.PY FÜR BACKEND_APP_V2
Startet die korrigierte Version mit LangExtract-Fixes
"""

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

# Import der korrigierten Flask-App
from . import app as flask_app

# Erstelle FastAPI-App als Wrapper
fastapi_app = FastAPI(
    title="Requirements Mining API V2",
    description="Korrigierte Version mit LangExtract-Fixes",
    version="2.0.0"
)

# Mount Flask-App unter Root, damit Routen wie /api/v1/* direkt erreichbar sind
fastapi_app.mount("/", WSGIMiddleware(flask_app))

# Health-Endpoint für FastAPI
@fastapi_app.get("/health")
async def health():
    return {"status": "ok", "version": "v2"}

if __name__ == "__main__":
    # Konfiguration aus Umgebungsvariablen
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8082"))  # Anderer Port als V1

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