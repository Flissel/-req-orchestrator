# -*- coding: utf-8 -*-
from __future__ import annotations

"""
QdrantSearchTool

Semantische Suche über die lokale RAG-Speicher-Schicht (Qdrant). Abhängigkeiten
werden per Lazy-Import geladen, sodass Offline-Tests nicht brechen.

Beispiel (JSON-Tool-Call):
{
  "tool": "qdrant_search",
  "args": { "query": "Wie starte ich das Ingest?", "top_k": 3 }
}
"""

from typing import Any, Dict, List, Optional

from .base import BaseTool, ToolResult


class QdrantSearchTool(BaseTool):
    """
    Führt eine semantische Suche durch und gibt minimal strukturierte Treffer zurück.

    Lazy-Import-Strategie:
    - Versuche, eine passende Retrieval-API zu importieren:
      - Primär: from arch_team.memory.retrieval import query_by_text (falls vorhanden)
      - Fallback: from arch_team.memory.retrieval import Retriever und nutze dessen query_by_text(...)
    - Jede Exception wird abgefangen und als ToolResult.fail mit freundlicher Meldung zurückgegeben.
    """

    name: str = "qdrant_search"
    description: str = "Semantische Suche (Qdrant). Gibt minimale Treffer mit id, snippet, source, score zurück."
    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "default": 5},
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def validate(self, args: Dict[str, Any]) -> Optional[ToolResult]:
        if not isinstance(args, dict):
            return ToolResult.fail("Arguments must be a dict")
        q = args.get("query")
        if not isinstance(q, str) or not q.strip():
            return ToolResult.fail("Field 'query' must be a non-empty string")
        tk = args.get("top_k", 5)
        try:
            tk_int = int(tk)
            if tk_int <= 0:
                return ToolResult.fail("Field 'top_k' must be a positive integer")
        except Exception:
            return ToolResult.fail("Field 'top_k' must be an integer")
        return None

    def run(self, args: Dict[str, Any]) -> ToolResult:
        val = self.validate(args)
        if isinstance(val, ToolResult):
            return val

        query = str(args.get("query") or "").strip()
        top_k = int(args.get("top_k") or 5)

        try:
            call_fn = None  # type: ignore

            # Primärer Versuch: funktionale API (falls in Projekt vorhanden)
            try:
                from arch_team.memory.retrieval import query_by_text as _query_by_text  # type: ignore

                def _call_query(q: str, k: int):
                    return _query_by_text(q, top_k=k)

                call_fn = _call_query  # type: ignore
            except Exception:
                call_fn = None

            # Fallback: Klasse Retriever
            if call_fn is None:
                from arch_team.memory.retrieval import Retriever  # type: ignore

                retriever = Retriever()

                def _call_query(q: str, k: int):
                    return retriever.query_by_text(q, top_k=k)

                call_fn = _call_query  # type: ignore

            hits = call_fn(query, top_k)  # type: ignore

            results: List[Dict[str, Any]] = []
            for h in hits or []:
                try:
                    hid = str(h.get("id", ""))
                    score = float(h.get("score", 0.0) or 0.0)
                    payload = h.get("payload") or {}
                    snippet = str(payload.get("text", "") or "")
                    snippet = snippet.replace("\n", " ").strip()[:300]
                    source = str(payload.get("sourceFile", "") or "")
                    results.append(
                        {
                            "id": hid,
                            "snippet": snippet,
                            "source": source,
                            "score": score,
                        }
                    )
                except Exception:
                    # Robustheit: Im Fehlerfall einzelnen Treffer auslassen
                    continue

            return ToolResult.ok(results)

        except Exception as e:
            return ToolResult.fail(f"RAG not configured or error: {e}")