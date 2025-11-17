# -*- coding: utf-8 -*-
"""
RagService (framework-frei)

Zweck
- Kapselt die einfache RAG-Suche.
- Delegiert an VectorService.rag_search(), um Embeddings + VectorStore zu nutzen.
- Dient als klarer Einstiegspunkt für zukünftige RAG-Erweiterungen (z. B. Hybrid-Search,
  Re-Ranking, Kontextaggregation).

Hinweis
- Keine Framework-/HTTP-Kopplung; reine Python-API, DI-fähig und testbar.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .ports import RequestContext
from .vector_service import VectorService


class RagService:
    def __init__(self, vector_service: Optional[VectorService] = None) -> None:
        self._vs = vector_service or VectorService()

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        collection: Optional[str] = None,
        model: Optional[str] = None,
        ctx: Optional[RequestContext] = None,
    ) -> Dict[str, Any]:
        """
        Führt eine einfache RAG-Suche aus (Query → Embeddings → VectorStore.search).
        """
        return self._vs.rag_search(
            query,
            top_k=top_k,
            collection=collection,
            model=model,
            ctx=ctx,
        )