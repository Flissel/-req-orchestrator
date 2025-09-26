# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from .chat_client import IChatClient, Messages


class OpenAIAdapter(IChatClient):
    """
    Adapter für OpenAI ChatCompletions mit Lazy-Import und Dual-Support:
    - openai>=1.0 (OpenAI().chat.completions.create)
    - legacy openai<1.0 (openai.ChatCompletion.create)

    Umgebungsvariablen:
    - OPENAI_API_KEY (erforderlich)
    - MODEL_NAME (optional; Default: gpt-4o-mini)
    """

    def __init__(self, default_model: Optional[str] = None) -> None:
        self.default_model = default_model or os.environ.get("MODEL_NAME", "gpt-4o-mini")

    def create(
        self,
        messages: Messages,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Union[str, Messages]:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY nicht gesetzt. Bitte Umgebungsvariable setzen, z. B. via .env")

        model_name = model or self.default_model
        temp = float(temperature) if temperature is not None else float(os.environ.get("ARCH_TEMPERATURE", "0.2"))

        # Versuch: neues SDK (>=1.0)
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=api_key)
            # Tools (falls vorhanden) nur an das neue SDK weiterreichen
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                tools=tools,
                **kwargs,
            )
            content = (resp.choices[0].message.content or "").strip()
            return content
        except ModuleNotFoundError:
            pass
        except Exception as e:
            # Fallback auf Legacy versuchen, außer bei klaren Auth/Quota-Fehlern
            if "status_code" in str(e).lower() or "401" in str(e) or "invalid api key" in str(e).lower():
                raise

        # Versuch: legacy SDK (<1.0)
        try:
            import openai  # type: ignore
            openai.api_key = api_key
            resp = openai.ChatCompletion.create(model=model_name, messages=messages, temperature=temp)
            content = (resp["choices"][0]["message"]["content"] or "").strip()
            return content
        except ModuleNotFoundError:
            raise RuntimeError(
                "openai Python SDK nicht installiert. Bitte 'pip install openai' ausführen (>=1.0 bevorzugt)."
            )
        except Exception as e:
            # Einheitliche, verständliche Fehlermeldung
            raise RuntimeError(f"OpenAI Chat-Aufruf fehlgeschlagen: {e}")