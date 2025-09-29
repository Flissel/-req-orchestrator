# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend_app import settings
from backend_app.utils import parse_requirements_md
from backend_app.batch import (
    process_evaluations,
    process_suggestions,
    process_rewrites,
    merged_markdown,
)

router = APIRouter(tags=["batch"])


@router.post("/api/v1/batch/evaluate")
def batch_evaluate_v2() -> JSONResponse:
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        eval_map = process_evaluations(rows)
        merged = merged_markdown(rows)
        return JSONResponse(content={"items": eval_map, "mergedMarkdown": merged}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/batch/suggest")
def batch_suggest_v2() -> JSONResponse:
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        sug_map = process_suggestions(rows)
        merged = merged_markdown(rows)
        return JSONResponse(content={"items": sug_map, "mergedMarkdown": merged}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)


@router.post("/api/v1/batch/rewrite")
def batch_rewrite_v2() -> JSONResponse:
    try:
        rows = parse_requirements_md(settings.REQUIREMENTS_MD_PATH)
        rw_map = process_rewrites(rows)
        merged = merged_markdown(rows)
        return JSONResponse(content={"items": rw_map, "mergedMarkdown": merged}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": "internal_error", "message": str(e)}, status_code=500)