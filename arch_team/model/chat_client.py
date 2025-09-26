# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


Message = Dict[str, Any]
Messages = List[Message]


class IChatClient(ABC):
    """
    Schlanke Chat-Client Schnittstelle für LLM-Aufrufe.
    Ergebnisse können als reiner Text (string) oder als Tool-Calls/Mehrfach-Nachrichten zurückkommen.
    """

    @abstractmethod
    def create(
        self,
        messages: Messages,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[str, Messages]:
        """
        Führt eine Chat-Completion aus.

        - messages: [{ "role": "system"|"user"|"assistant", "content": str }, ...]
        - temperature: Exploration-Grad (0.0 = deterministischer)
        - model: optionales Modell-Override
        - return: string (content) oder Liste von Nachrichten (für erweiterte Modi)

        Muss RuntimeError werfen, wenn ein erforderliches SDK nicht installiert ist
        oder z. B. OPENAI_API_KEY fehlt. Die Aufrufer fangen diese Exception ab.
        """
        raise NotImplementedError