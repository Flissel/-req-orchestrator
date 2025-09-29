# -*- coding: utf-8 -*-
"""
FastAPI-Port der zentralen Flask-Endpunkte (Backup bleibt: backend_app/api.py).
Start (lokal):
  uvicorn backend_app_fastapi.api_fast:app --host 0.0.0.0 --port 8084

Hinweis:
- Nutzt die bestehenden Services/Helper aus backend_app/* (DB, LLM, Utils, Settings).
- Response-Struktur ist zu Flask kompatibel, damit Frontend-Aufrufe unverändert bleiben.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Reuse bestehende Codebasis (keine Web-Abhängigkeiten)
from backend_app import settings
from backend_app.db import get_db, load_criteria
from backend_app.llm import llm_evaluate
from backend_app.utils import weighted_score, compute_verdict, sha256_text

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Pydantic Modelle (kompatibel zur Flask-Form)
# ------------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    requirementText: str = Field(..., min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    criteriaKeys: Optional[List[str]] = None


class EvaluateResponse(BaseModel):
    evaluationId: str
    verdict: str
    score: float
    latencyMs: int
    model: str
    details: List[Dict[str, Any]]
    suggestions: Optional[List[Dict[str, Any]]] = None


# ------------------------------------------------------------------------------
# FastAPI App + Router
# ------------------------------------------------------------------------------

app = FastAPI(
    title="Requirements API (FastAPI Port)",
    description="Portierung zentraler Flask-Routen nach FastAPI. Backup bleibt bestehen.",
    version="1.0.0",
)
router = APIRouter(prefix="")

# CORS (vereinheitlicht; Frontends können API_BASE beliebig setzen)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


# ------------------------------------------------------------------------------
# Runtime Config (nur Metadaten, kein Secret-Leak)
# ------------------------------------------------------------------------------

@router.get("/api/runtime-config")
def runtime_config() -> JSONResponse:
    try:
        cfg = settings.get_runtime_config()
        return JSONResponse(content=cfg, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


# ------------------------------------------------------------------------------
# Kriterien
# ------------------------------------------------------------------------------

@router.get("/api/v1/criteria")
def list_criteria() -> JSONResponse:
    try:
        conn = get_db()
        items = load_criteria(conn)
        return JSONResponse(content={"items": items}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


# ------------------------------------------------------------------------------
# Evaluate (Einzelanforderung) – Port von Flask /api/v1/evaluations
# ------------------------------------------------------------------------------

@router.post("/api/v1/evaluations", response_model=EvaluateResponse)
def create_evaluation(req: EvaluateRequest) -> EvaluateResponse:
    ts_start = time.time()
    try:
        requirement_text = (req.requirementText or "").strip()
        if not requirement_text:
            raise HTTPException(status_code=400, detail="requirementText fehlt oder ist leer")

        context = req.context or {}
        conn = get_db()

        # Kriterien laden: angefordert oder alle aktiven
        if req.criteriaKeys is None:
            crits = load_criteria(conn)
            criteria_keys = [c["key"] for c in crits]
        else:
            if not isinstance(req.criteriaKeys, list) or not all(isinstance(k, str) for k in req.criteriaKeys):
                raise HTTPException(status_code=400, detail="criteriaKeys muss eine Liste von Strings sein")
            crits = load_criteria(conn, req.criteriaKeys)
            if not crits:
                raise HTTPException(status_code=400, detail="keine gültigen Kriterien gefunden")
            criteria_keys = [c["key"] for c in crits]

        # Evaluierung (LLM oder Mock)
        details = llm_evaluate(requirement_text, criteria_keys, context)

        # Score/Verdict
        agg_score = weighted_score(details, crits)
        verdict = compute_verdict(agg_score, settings.VERDICT_THRESHOLD)

        # Speichern nur Metadaten
        latency_ms = int((time.time() - ts_start) * 1000)
        requirement_checksum = sha256_text(requirement_text)
        eval_id = f"ev_{int(time.time())}_{requirement_checksum[:8]}"

        with conn:
            conn.execute(
                "INSERT INTO evaluation(id, requirement_checksum, model, latency_ms, score, verdict) VALUES (?, ?, ?, ?, ?, ?)",
                (eval_id, requirement_checksum, settings.OPENAI_MODEL, latency_ms, agg_score, verdict),
            )
            for d in details:
                conn.execute(
                    "INSERT INTO evaluation_detail(evaluation_id, criterion_key, score, passed, feedback) VALUES (?, ?, ?, ?, ?)",
                    (eval_id, d["criterion"], float(d["score"]), 1 if d.get("passed") else 0, d.get("feedback", "")),
                )

            # Einfache Heuristik für Suggestions (kompatibel zu Flask)
            suggestions: List[Dict[str, Any]] = []
            if verdict == "fail":
                suggestions.append(
                    {"text": "Schwellwerte konkretisieren, z. B. Antwortzeit/Fehlertoleranz/Lastprofil spezifizieren.", "priority": "high"}
                )
            elif agg_score < 0.8:
                suggestions.append(
                    {"text": "Begriffe präzisieren und Randbedingungen definieren, um Eindeutigkeit zu erhöhen.", "priority": "medium"}
                )
            for s in suggestions:
                conn.execute(
                    "INSERT INTO suggestion(evaluation_id, text, priority) VALUES (?, ?, ?)",
                    (eval_id, s["text"], s["priority"]),
                )

        return EvaluateResponse(
            evaluationId=eval_id,
            verdict=verdict,
            score=round(agg_score, 4),
            latencyMs=latency_ms,
            model=settings.OPENAI_MODEL,
            details=details,
            suggestions=suggestions or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_evaluation failed")
        raise HTTPException(status_code=500, detail=str(e))


# Router registrieren
app.include_router(router)