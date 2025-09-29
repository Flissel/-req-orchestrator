# -*- coding: utf-8 -*-
"""
BatchService (framework-frei)

Zweck
- Kapselt Batch-Operationen für Evaluate/Suggest/Rewrite und Hilfen wie merged_markdown.
- Nutzt bestehende Implementierungen in backend_app.batch, bleibt aber unabhängig von
  FastAPI/Flask und bietet eine klare Service-API (DI-fähig, testbar).

Hinweis
- Die in backend_app.batch vorhandenen Funktionen sind g-kontext-sicher (siehe _safe_g_attr),
  sodass Aufrufe aus FastAPI-Kontexten möglich sind.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .ports import RequestContext, ServiceError, safe_request_id

# Bestehende Implementierungen aus der Legacy/Shared-Schicht
from backend_app.batch import (
    process_evaluations as _process_evaluations,
    process_suggestions as _process_suggestions,
    process_rewrites as _process_rewrites,
    merged_markdown as _merged_markdown,
)


class BatchService:
    """
    BatchService – API
    - evaluate_items(items, ...)
    - suggest_items(items, ...)
    - rewrite_items(items, ...)
    - merged_markdown(rows, ...)
    """

    # -----------------------
    # Evaluate
    # -----------------------

    def evaluate_items(
        self,
        items: Sequence[str],
        *,
        batch_size: Optional[int] = None,
        max_parallel: Optional[int] = None,
        threshold: Optional[float] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Führt Evaluations-Batch aus. Parameter werden an backend_app.batch.process_evaluations
        weitergereicht, sofern unterstützt (batch_size/max_parallel/threshold sind implizit
        über Settings wirksam; explizite Übergabe ist optional).
        """
        try:
            if not items:
                return []
            # process_evaluations akzeptiert aktuell nur items (Sequenz von Texten) + Settings.
            # Threshold/Parallelität werden über Settings (ENV) gesteuert.
            return list(_process_evaluations(list(items)))
        except Exception as e:
            raise ServiceError(
                "batch_evaluate_failed",
                "Failed to evaluate batch items",
                details={"request_id": safe_request_id(ctx), "count": len(items), "error": str(e)},
            )

    # -----------------------
    # Suggest
    # -----------------------

    def suggest_items(
        self,
        items: Sequence[str],
        *,
        max_suggestions: Optional[int] = None,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Erzeugt Korrekturvorschläge (Suggest) für Items via backend_app.batch.process_suggestions.
        """
        try:
            if not items:
                return []
            return list(_process_suggestions(list(items)))
        except Exception as e:
            raise ServiceError(
                "batch_suggest_failed",
                "Failed to suggest corrections for batch items",
                details={"request_id": safe_request_id(ctx), "count": len(items), "error": str(e)},
            )

    # -----------------------
    # Rewrite
    # -----------------------

    def rewrite_items(
        self,
        items: Sequence[str],
        *,
        ctx: Optional[RequestContext] = None,
    ) -> List[Dict[str, Any]]:
        """
        Führt Rewrite für Items via backend_app.batch.process_rewrites aus.
        """
        try:
            if not items:
                return []
            return list(_process_rewrites(list(items)))
        except Exception as e:
            raise ServiceError(
                "batch_rewrite_failed",
                "Failed to rewrite batch items",
                details={"request_id": safe_request_id(ctx), "count": len(items), "error": str(e)},
            )

    # -----------------------
    # Markdown Merge
    # -----------------------

    def merged_markdown(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        ctx: Optional[RequestContext] = None,
    ) -> str:
        """
        Erzeugt ein zusammengeführtes Markdown gemäß backend_app.batch.merged_markdown.
        Erwartet Iterable von Zeilen (mit id/original/corrections etc. analog Legacy).
        """
        try:
            return str(_merged_markdown(rows))
        except Exception as e:
            raise ServiceError(
                "batch_merge_md_failed",
                "Failed to create merged markdown",
                details={"request_id": safe_request_id(ctx), "error": str(e)},
            )