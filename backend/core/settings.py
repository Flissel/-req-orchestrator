# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from dotenv import load_dotenv

# Load from .env if present
load_dotenv()

# Core API runtime
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8081"))

# LLM Settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
# Embeddings-Modell für Vektorindex (RAG)
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "text-embedding-3-small")
MOCK_MODE = os.environ.get("MOCK_MODE", "false").lower() in ("1", "true", "yes")

# DB
SQLITE_PATH = os.environ.get("SQLITE_PATH", "app.db")
PURGE_RETENTION_H = int(os.environ.get("PURGE_RETENTION_H", "24"))

# Vektor-DB (Qdrant)
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "requirements_v1")

# Batch and files
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
MAX_PARALLEL = int(os.environ.get("MAX_PARALLEL", "5"))
REQUIREMENTS_MD_PATH = os.environ.get("REQUIREMENTS_MD_PATH", "./docs/requirements.md")

# Chunking (Token-basiert)
CHUNK_TOKENS_MIN = int(os.environ.get("CHUNK_TOKENS_MIN", "200"))
CHUNK_TOKENS_MAX = int(os.environ.get("CHUNK_TOKENS_MAX", "400"))
CHUNK_OVERLAP_TOKENS = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "50"))

# LLM Feineinstellungen und Konfigpfade
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.0"))
LLM_TOP_P = float(os.environ.get("LLM_TOP_P", "1.0"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "0"))  # 0 = SDK Default

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json")  # json|console
LOG_SAMPLE_BODIES = os.environ.get("LOG_SAMPLE_BODIES", "false").lower() in ("1", "true", "yes")

# System-Prompts (optional über Dateien konfigurierbar)
EVAL_SYSTEM_PROMPT_PATH = os.environ.get("EVAL_SYSTEM_PROMPT_PATH", "./config/prompts/evaluate.system.txt")
SUGGEST_SYSTEM_PROMPT_PATH = os.environ.get("SUGGEST_SYSTEM_PROMPT_PATH", "./config/prompts/suggest.system.txt")
REWRITE_SYSTEM_PROMPT_PATH = os.environ.get("REWRITE_SYSTEM_PROMPT_PATH", "./config/prompts/rewrite.system.txt")

# Kriterien- und Entscheidungs-Konfiguration
CRITERIA_CONFIG_PATH = os.environ.get("CRITERIA_CONFIG_PATH", "./config/criteria.json")
VERDICT_THRESHOLD = float(os.environ.get("VERDICT_THRESHOLD", "0.7"))
SUGGEST_MAX = int(os.environ.get("SUGGEST_MAX", "10"))
OUTPUT_MD_PATH = os.environ.get("OUTPUT_MD_PATH", "")  # optional: schreibt mergedMarkdown serverseitig


def _env_bool(name: str, default: str = "false") -> bool:
    """
    Liest ein Bool-ENV. Akzeptiert: 1,true,yes,on (case-insensitive).
    """
    return (os.environ.get(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


def _compose_qdrant_url(base_url: str, port: int) -> str:
    """
    Baut eine Qdrant-URL inkl. Port, wenn keiner im Hostteil enthalten ist.
    Beispiele:
      - http://localhost  + 6333 -> http://localhost:6333
      - http://127.0.0.1  + 6401 -> http://127.0.0.1:6401
      - http://host:6333  + 6333 -> http://host:6333 (unverändert)
    """
    base = str(base_url or "http://localhost").rstrip("/")
    try:
        hostpart = base.split("://", 1)[-1]
        if ":" in hostpart:
            return base
        return f"{base}:{int(port)}"
    except Exception:
        # Fallback: naive Zusammensetzung
        return f"{base}:{int(port)}"


def _read_file_text(path: str) -> str:
    try:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""

def get_system_prompt(kind: str) -> str:
    """
    Liefert den Systemprompt je Anwendungsfall. Falls keine Datei vorhanden ist,
    wird ein sinnvoller Default zurückgegeben.
    kind ∈ {evaluate, suggest, rewrite}
    """
    if kind == "evaluate":
        txt = _read_file_text(EVAL_SYSTEM_PROMPT_PATH)
        if txt:
            return txt
        return (
            "Du bist ein Qualitätsprüfer für Software-Requirements. "
            "Bewerte die Anforderung entlang vorgegebener Kriterien mit Scores 0.0 bis 1.0. "
            "Gib NUR JSON zurück mit: {details: [{criterion, score, passed, feedback}]}. "
            "Keinen zusätzlichen Text, keine Code-Fences, keine Erklärungen."
        )
    if kind == "suggest":
        txt = _read_file_text(SUGGEST_SYSTEM_PROMPT_PATH)
        if txt:
            return txt
        return (
            "Du bist ein erfahrener Requirements Engineer. "
            "Erzeuge prägnante Verbesserungsvorschläge. "
            "Gib NUR JSON: {suggestions: [{text: string, priority: one of [low, medium, high]}]}. "
            "Keinen zusätzlichen Text, keine Code-Fences, keine Erklärungen."
        )
    if kind == "rewrite":
        txt = _read_file_text(REWRITE_SYSTEM_PROMPT_PATH)
        if txt:
            return txt
        return (
            "Du bist ein erfahrener Requirements Engineer. "
            "Formuliere die folgende Anforderung präzise, testbar und messbar um. "
            "Gib NUR JSON zurück: {redefinedRequirement: string}. "
            "Keinen zusätzlichen Text, keine Code-Fences, keine Erklärungen."
        )
    return ""
def get_runtime_config() -> dict:
    """
    Snapshot der aktuellen Runtime-Konfiguration.
    Hinweis:
    - Es wird niemals der API-Key ausgegeben, nur ein Boolean openai_api_key_present.
    - Liefert zusätzlich Hinweise zu häufigen Env-Verwechslungen.
    """
    unused_env_hints = []
    if os.environ.get("OPENAI_TEMPERATURE") is not None and os.environ.get("LLM_TEMPERATURE") is None:
        unused_env_hints.append("OPENAI_TEMPERATURE ist gesetzt, wird aber ignoriert. Bitte LLM_TEMPERATURE verwenden.")
    if os.environ.get("OPENAI_MAX_TOKENS") is not None and os.environ.get("LLM_MAX_TOKENS") is None:
        unused_env_hints.append("OPENAI_MAX_TOKENS ist gesetzt, wird aber ignoriert. Bitte LLM_MAX_TOKENS verwenden.")

    # Autodetect: Embeddings-Dimension
    embeddings_detected_dim = None  # type: ignore[assignment]
    try:
        # Bevorzugt statisch reportete Dimension aus embeddings-Modul
        from .embeddings import get_embeddings_dim, build_embeddings  # lazy import
        embeddings_detected_dim = int(get_embeddings_dim())
        # Optional aktive Probe gegen das konfiguriere Modell (nur wenn explizit gewünscht)
        if _env_bool("EMBEDDINGS_AUTOPROBE", "false") and OPENAI_API_KEY:
            try:
                vecs = build_embeddings(["probe_text_for_dim_detection"], model=EMBEDDINGS_MODEL, batch_size=1)
                if vecs and isinstance(vecs[0], list):
                    embeddings_detected_dim = int(len(vecs[0]))
            except Exception:
                # Probe fehlgeschlagen → still, wir behalten die statische Dim
                pass
    except Exception:
        # embeddings-Modul nicht verfügbar → ignorieren
        pass

    # Autodetect: Qdrant Collection (Existenz/Dimension) und optional Auto-Create
    q_exists: bool | None = None
    q_coll_dim: int | None = None
    q_matches_dim: bool | None = None
    q_auto_created: bool = False
    q_effective_url: str | None = None
    q_error: str | None = None

    if _env_bool("QDRANT_AUTODETECT", "true"):
        try:
            # Lazy Imports, um harte Abhängigkeiten in Settings zu vermeiden
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import VectorParams, Distance  # type: ignore

            q_effective_url = _compose_qdrant_url(QDRANT_URL, QDRANT_PORT)
            cli = QdrantClient(url=q_effective_url, timeout=3.0, api_key=os.environ.get("QDRANT_API_KEY") or None)

            try:
                info = cli.get_collection(collection_name=QDRANT_COLLECTION)
                q_exists = True
                vp = getattr(getattr(info, "config", None), "params", None)
                v = getattr(vp, "vectors", None)
                cdim = getattr(v, "size", None)
                if cdim is not None:
                    q_coll_dim = int(cdim)
            except Exception:
                q_exists = False

            desired_dim = int(embeddings_detected_dim or 1536)
            # Optional: Auto-Create/Recreate (destruktiv) nur wenn ausdrücklich angefordert
            if _env_bool("QDRANT_AUTOCREATE", "false") and (not q_exists or (q_coll_dim and int(q_coll_dim) != desired_dim)):
                cli.recreate_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=desired_dim, distance=Distance.COSINE),
                )
                q_auto_created = True
                q_exists = True
                q_coll_dim = desired_dim

            if embeddings_detected_dim and q_coll_dim:
                q_matches_dim = (int(embeddings_detected_dim) == int(q_coll_dim))
        except Exception as e:
            q_error = str(e)

    cfg = {
        "api": {
            "host": API_HOST,
            "port": API_PORT,
        },
        "db": {
            "sqlite_path": SQLITE_PATH,
            "purge_retention_h": PURGE_RETENTION_H,
        },
        "vector": {
            "qdrant_url": QDRANT_URL,
            "qdrant_port": QDRANT_PORT,
            "collection": QDRANT_COLLECTION,
            # Autodetect-Erweiterungen
            "effective_url": q_effective_url,
            "detected_dim": q_coll_dim,
            "exists": q_exists,
            "matches_dim": q_matches_dim,
            "auto_created": q_auto_created,
            **({"error": q_error} if q_error else {}),
        },
        "batch": {
            "batch_size": BATCH_SIZE,
            "max_parallel": MAX_PARALLEL,
            "verdict_threshold": VERDICT_THRESHOLD,
        },
        "llm": {
            "mock_mode": MOCK_MODE,
            "openai_model": OPENAI_MODEL,
            "openai_api_key_present": bool(OPENAI_API_KEY),
            "temperature": LLM_TEMPERATURE,
            "top_p": LLM_TOP_P,
            "max_tokens": LLM_MAX_TOKENS,
        },
        "embeddings": {
            "provider": "openai",
            "model": EMBEDDINGS_MODEL,
            # Autodetect-Erweiterung
            "detected_dim": embeddings_detected_dim,
        },
        "prompts": {
            "evaluate_path": EVAL_SYSTEM_PROMPT_PATH,
            "suggest_path": SUGGEST_SYSTEM_PROMPT_PATH,
            "rewrite_path": REWRITE_SYSTEM_PROMPT_PATH,
        },
        "criteria": {
            "criteria_config_path": CRITERIA_CONFIG_PATH,
            "suggest_max": SUGGEST_MAX,
        },
        "io": {
            "requirements_md_path": REQUIREMENTS_MD_PATH,
            "output_md_path": OUTPUT_MD_PATH,
        },
        "chunking": {
            "min_tokens": CHUNK_TOKENS_MIN,
            "max_tokens": CHUNK_TOKENS_MAX,
            "overlap_tokens": CHUNK_OVERLAP_TOKENS,
        },
        "hints": {
            "unused_env": unused_env_hints,
            # Nützlicher Hinweis bei Dimensions-Mismatch
            **(
                {"vector_dim_mismatch": True}
                if (q_matches_dim is False)
                else {}
            ),
        },
    }
    return cfg


def log_runtime_config() -> None:
    """
    Gibt die Runtime-Konfiguration auf stdout aus (beim Container-Start aufrufbar).
    """
    try:
        cfg = get_runtime_config()
        print("=== Runtime Configuration Snapshot ===")
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        print("======================================")
    except Exception as e:
        print("[config][error]", str(e))