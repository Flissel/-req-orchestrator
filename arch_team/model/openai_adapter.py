# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from .chat_client import IChatClient, Messages

# Try to import backend settings for provider config
try:
    from backend.core.settings import get_llm_config
    _has_backend_settings = True
except ImportError:
    _has_backend_settings = False


class OpenAIAdapter(IChatClient):
    """
    Adapter für OpenRouter ChatCompletions via OpenAI SDK.
    Uses OpenRouter as the LLM provider (OpenAI-compatible API).

    Umgebungsvariablen:
    - OPENROUTER_API_KEY (erforderlich)
    - MODEL_NAME (optional; Default: google/gemini-2.5-flash:nitro)
    """

    def __init__(self, default_model: Optional[str] = None) -> None:
        self.default_model = default_model or os.environ.get("MODEL_NAME", "google/gemini-2.5-flash:nitro")

    def create(
        self,
        messages: Messages,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Union[str, Messages]:
        # Get OpenRouter configuration
        if _has_backend_settings:
            llm_config = get_llm_config()
            api_key = llm_config["api_key"]
            base_url = llm_config["base_url"]
        else:
            # Fallback to direct env var if backend settings not available
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY nicht gesetzt.")

        model_name = model or self.default_model
        temp = float(temperature) if temperature is not None else float(os.environ.get("ARCH_TEMPERATURE", "0.2"))

        # Versuch: neues SDK (>=1.0) - this should always work with openai>=1.0
        try:
            from openai import OpenAI  # type: ignore
            # Pass base_url for OpenRouter support
            client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
            # Tools (falls vorhanden) nur an das neue SDK weiterreichen
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temp,
                tools=tools,
                **kwargs,
            )
            # If tools are used and LLM called a function, return the full response
            message = resp.choices[0].message
            if tools and message.tool_calls:
                return resp
            # Otherwise return just the content string (backward compatibility)
            content = (message.content or "").strip()
            return content
        except ImportError:
            # Only fall back to legacy if new SDK is not installed
            pass
        except Exception as e:
            # If we have the new SDK but it failed, re-raise the error
            # Don't fall back to legacy when using openai>=1.0
            raise RuntimeError(f"OpenAI API call failed: {e}")

        # Legacy fallback - should only be reached if openai>=1.0 is not installed
        # This code path should not be reached in production with openai>=1.0
        try:
            import openai  # type: ignore
            openai.api_key = api_key
            # Legacy SDK uses openai.api_base for OpenRouter support
            if base_url:
                openai.api_base = base_url
            resp = openai.ChatCompletion.create(model=model_name, messages=messages, temperature=temp)
            content = (resp["choices"][0]["message"]["content"] or "").strip()
            return content
        except (ImportError, AttributeError) as e:
            # ChatCompletion doesn't exist in openai>=1.0
            raise RuntimeError(
                f"openai Python SDK version mismatch. Please use 'pip install openai>=1.0'. Error: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI Chat-Aufruf fehlgeschlagen: {e}")