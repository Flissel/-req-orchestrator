# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass


class MemoryStore:
    """
    Sehr leichte JSONL-basierte Memory-Implementierung.
    - events_path: JSONL (eine Zeile pro Event)
    - policies_path: JSON (Array von Policy-Regeln)
    Eignet sich als Stub für AutoGen Memory – kann später gegen Redis/SQLite/Qdrant ausgetauscht werden.
    """

    def __init__(
        self,
        events_path: str = "/data/memory.jsonl",
        policies_path: str = "/data/policies.json",
    ) -> None:
        self.events_path = events_path
        self.policies_path = policies_path
        _ensure_dir(events_path)
        _ensure_dir(policies_path)

    # ------------- Events (Outcome/Session) -------------

    def append_event(self, event: Dict[str, Any]) -> None:
        """
        event: {ts, sessionId?, type: "query|rewrite|result|note", ...}
        """
        try:
            e = dict(event or {})
            e.setdefault("ts", int(time.time()))
            with open(self.events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def read_events(self, limit: int = 2000) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            if not os.path.exists(self.events_path):
                return out
            with open(self.events_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
            if limit and len(out) > limit:
                return out[-limit:]
            return out
        except Exception:
            return out

    # ------------- Policies -------------

    def load_policies(self) -> List[Dict[str, Any]]:
        """
        Lädt Policy-Regeln. Falls Datei fehlt, werden Default-Policies geliefert.
        Struktur der Regel (Beispiel):
        {
          "id": "count-requirements",
          "match": {"includes": ["wie", "viele", "requirement"]},
          "action": {"type": "use_ref_count"}
        }
        """
        try:
            if os.path.exists(self.policies_path):
                with open(self.policies_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        # Defaults
        return [
            {
                "id": "count-requirements",
                "match": {"includes": ["wie", "viele", "requirement"]},
                "action": {"type": "use_ref_count"},
            },
            {
                "id": "cors-prefer",
                "match": {"includes": ["cors"]},
                "action": {
                    "type": "prefer_sources",
                    "prefer": ["requirements.md", "README.md", "C4.md"],
                    "top_k": 10,
                },
            },
            {
                "id": "health-json",
                "match": {"includes": ["health"]},
                "action": {
                    "type": "rewrite_hint",
                    "rewrite_add": ' returns {"status":"ok"}',
                    "prefer": ["requirements.md", "README.md"],
                    "top_k": 10,
                },
            },
            {
                "id": "endpoints",
                "match": {"includes": ["endpunkt", "endpoint", "endpunkte", "endpoints"]},
                "action": {
                    "type": "prefer_sources",
                    "prefer": ["README.md", "requirements.md", "C4.md"],
                    "top_k": 8,
                },
            },
            {
                "id": "ports",
                "match": {"includes": ["port", "ports"]},
                "action": {
                    "type": "prefer_sources",
                    "prefer": ["README.md"],
                    "top_k": 10,
                },
            },
        ]