# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Iterable, List, Sequence

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from . import settings

# Wir nutzen das Legacy OpenAI SDK 0.28.x nur für Chat, für Embeddings rufen wir die REST API,
# damit text-embedding-3-small konsistent nutzbar ist und wir Timeout/Retry sauber kontrollieren können.

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
DEFAULT_EMBEDDINGS_MODEL = getattr(settings, "EMBEDDINGS_MODEL", "text-embedding-3-small")

# Embedding dimension von text-embedding-3-small ist i. d. R. 1536
EMBEDDINGS_DIM = 1536


def get_embeddings_dim() -> int:
    return EMBEDDINGS_DIM


def _auth_headers() -> dict:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY nicht gesetzt")
    return {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }


@retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=0.5, max=8))
def _embed_batch(texts: Sequence[str], model: str) -> List[List[float]]:
    """
    Ruft die OpenAI Embeddings REST-API auf. Nutzt Retries bei Transienten Fehlern.
    """
    payload = {
        "model": model,
        "input": list(texts),
    }
    resp = requests.post(OPENAI_EMBEDDINGS_URL, headers=_auth_headers(), json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI embeddings HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json() or {}
    arr = data.get("data") or []
    out = []
    for item in arr:
        vec = item.get("embedding") or []
        out.append(vec)
    if len(out) != len(texts):
        # Defensive Guard
        raise RuntimeError("Embedding-Antwort hatte unerwartete Länge")
    return out


def build_embeddings(
    texts: Sequence[str],
    model: str = DEFAULT_EMBEDDINGS_MODEL,
    batch_size: int = 64,
) -> List[List[float]]:
    """
    Baut Embeddings für eine Liste von Texten. Chunked-Batching mit Retries.
    """
    if not texts:
        return []
    out: List[List[float]] = []
    n = len(texts)
    bs = max(1, int(batch_size or 1))
    for i in range(0, n, bs):
        chunk = texts[i : i + bs]
        vecs = _embed_batch(chunk, model=model)
        out.extend(vecs)
        # Light rate-limit smoothing
        time.sleep(0.05)
    return out