# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional


class ChatCompletionContext:
    """
    Puffer für Chat-Completion Nachrichten (Buffered Context).
    Speichert die letzten N Nachrichten (system|user|assistant) in chronologischer Reihenfolge.

    - add_message(message: dict)
    - get_messages(limit: Optional[int]) -> List[dict]
    - reset()
    - max_len: int
    """

    def __init__(self, max_len: int = 12) -> None:
        self.max_len = int(max_len or 12)
        self._messages: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def add_message(self, message: Dict[str, Any]) -> None:
        """
        Fügt eine Nachricht hinzu. Schneidet den Puffer auf max_len von hinten.
        """
        if not isinstance(message, dict):
            return
        role = str(message.get("role") or "").strip()
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            return
        async with self._lock:
            self._messages.append({"role": role, "content": content})
            # Auf letzte N begrenzen (behalte die jüngsten)
            if len(self._messages) > self.max_len:
                overflow = len(self._messages) - self.max_len
                self._messages = self._messages[overflow:]

    async def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Liefert eine Kopie der letzten 'limit' Nachrichten (oder alle, wenn None).
        """
        lim = int(limit) if isinstance(limit, int) and limit > 0 else None
        async with self._lock:
            if lim is None or lim >= len(self._messages):
                return list(self._messages)
            return list(self._messages[-lim:])

    async def reset(self) -> None:
        """
        Leert den Puffer.
        """
        async with self._lock:
            self._messages.clear()