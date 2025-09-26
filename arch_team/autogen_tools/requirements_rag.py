# -*- coding: utf-8 -*-
from __future__ import annotations

"""
AutoGen Tool: search_requirements

Asynchrone RAG-Suche über den internen Retriever (arch_team.memory.retrieval.Retriever).
- Lazy-Import im Funktionskörper, damit das Modul ohne Qdrant/Embeddings ladbar bleibt.
- Gibt bei Treffern eine kompakte Markdown-Tabelle zurück: | id | snippet | source |
- Keine Exceptions nach außen; bei Fehlern oder keinen Treffern: freundliche Meldung.

Parameters
----------
query : str
    Freitext-Query.
top_k : int, default 5
    Anzahl gewünschter Treffer.

Returns
-------
str
    Markdown-String (Tabelle) oder freundliche Meldung.
"""
from typing import Any, Dict, List


async def search_requirements(query: str, top_k: int = 5) -> str:
    """
    AutoGen-Tool: Suche relevante Requirement-Snippets in semantischer Memory.
    """
    try:
        q = (query or "").strip()
        if not q:
            return "RAG not configured or no hits for empty query."

        try:
            # Lazy-Import des Retrievers
            from arch_team.memory.retrieval import Retriever  # type: ignore
        except Exception:
            return f"RAG not configured or no hits for '{q}'."

        try:
            retriever = Retriever()
            hits: List[Dict[str, Any]] = retriever.query_by_text(q, top_k=int(top_k or 5))
        except Exception:
            return f"RAG not configured or no hits for '{q}'."

        if not hits:
            return f"RAG not configured or no hits for '{q}'."

        def _esc(s: str) -> str:
            return s.replace("|", "\\|")

        # Baue Markdown-Tabelle
        lines: List[str] = []
        lines.append("| id | snippet | source |")
        lines.append("|---:|:--------|:-------|")
        for h in hits:
            pid = str(h.get("id", ""))
            payload = h.get("payload") or {}
            text = str(payload.get("text") or "")
            text = " ".join(text.split())
            snippet = text[:180]
            source = str(payload.get("sourceFile") or payload.get("source") or "")
            lines.append(f"| {_esc(pid)} | {_esc(snippet)} | {_esc(source)} |")

        return "\n".join(lines)
    except Exception:
        return f"RAG not configured or no hits for '{(query or '').strip()}'."