# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

try:
    from flask import Flask, Request, Response, g, request
    from werkzeug.wrappers.response import Response as WSGIResponse
    _HAS_FLASK = True
except ImportError:
    Flask = Request = Response = g = request = WSGIResponse = None  # type: ignore[assignment,misc]
    _HAS_FLASK = False

try:
    from . import settings
except Exception:
    # Fallbacks for tooling
    class settings:  # type: ignore
        LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        LOG_FORMAT = os.environ.get("LOG_FORMAT", "json")
        LOG_SAMPLE_BODIES = os.environ.get("LOG_SAMPLE_BODIES", "false").lower() in ("1", "true", "yes")
        API_HOST = os.environ.get("API_HOST", "0.0.0.0")
        API_PORT = int(os.environ.get("API_PORT", "8081"))


def _level_from_text(text: str) -> int:
    mapping = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    return mapping.get((text or "INFO").upper(), logging.INFO)


def setup_logging() -> logging.Logger:
    """
    Initialisiert das Root-Logging nach Env:
      - LOG_LEVEL: INFO|DEBUG|...
      - LOG_FORMAT: json|console
    """
    level = _level_from_text(getattr(settings, "LOG_LEVEL", "INFO"))
    fmt = str(getattr(settings, "LOG_FORMAT", "json")).lower()

    logger = logging.getLogger("app")
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    if fmt == "console":
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
    else:
        # JSON: wir loggen JSON-Strings, daher simple Formatter
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _stable_hash_bytes(b: bytes) -> str:
    try:
        return hashlib.sha256(b).hexdigest()
    except Exception:
        return ""


def _summarize_body(req: Request) -> Dict[str, Any]:
    """
    Gibt eine sichere Zusammenfassung des Request-Bodys zurück:
      - present (bool)
      - content_length (int oder None)
      - mimetype (str)
      - json_keys (Top-Level Keys bei JSON, KEINE Werte)
      - fields_count (Anzahl der Top-Level Keys / Array-Elemente)
      - sha256 (stabiler Hash der Bytes)
    Keine sensiblen Inhalte im Klartext.
    """
    summary: Dict[str, Any] = {
        "present": False,
        "content_length": req.content_length,
        "mimetype": req.mimetype,
        "json_keys": None,
        "fields_count": None,
        "sha256": None,
    }
    try:
        data_bytes: Optional[bytes] = None
        if req.content_length and req.content_length > 0:
            summary["present"] = True
            # get_data() ist in Flask gecached; vermeidet erneutes Lesen des Streams
            data_bytes = req.get_data(cache=True) or b""
            summary["sha256"] = _stable_hash_bytes(data_bytes)
            if (req.mimetype or "").startswith("application/json") and data_bytes:
                try:
                    parsed = json.loads(data_bytes.decode("utf-8", errors="ignore"))
                    if isinstance(parsed, dict):
                        summary["json_keys"] = list(parsed.keys())[:50]
                        summary["fields_count"] = len(parsed.keys())
                    elif isinstance(parsed, list):
                        summary["json_keys"] = None
                        summary["fields_count"] = len(parsed)
                except Exception:
                    pass
        else:
            # Kein Content-Length; evtl. trotzdem Body vorhanden
            data_bytes = req.get_data(cache=True) or b""
            if data_bytes:
                summary["present"] = True
                summary["content_length"] = len(data_bytes)
                summary["sha256"] = _stable_hash_bytes(data_bytes)
    except Exception:
        pass
    return summary


def _summarize_query(req: Request) -> Dict[str, Any]:
    try:
        keys = list(req.args.keys())
        return {"present": bool(keys), "keys": keys[:50], "count": len(keys)}
    except Exception:
        return {"present": False, "keys": None, "count": 0}


def _response_size(resp: Response | WSGIResponse) -> int:
    try:
        data = resp.get_data(as_text=False)
        return len(data or b"")
    except Exception:
        return 0


def _json_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    try:
        msg = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        # Fallback
        msg = json.dumps({"event": event, "error": "json_dump_failed"})
    logger.log(level, msg)


def register_request_logging(app: Flask, logger: Optional[logging.Logger] = None) -> None:
    """
    Registriert Framework-weit:
      - Request-Start- und Ende-Logging
      - Korrelation via X-Request-ID (Header) oder generiertem UUID4
      - Response-Header X-Request-ID
      - Fehler-Logging (teardown)
    """
    lg = logger or logging.getLogger("app")
    sample_bodies = bool(getattr(settings, "LOG_SAMPLE_BODIES", False))
    log_json = str(getattr(settings, "LOG_FORMAT", "json")).lower() == "json"

    @app.before_request
    def _log_start():
        g._req_ts = time.time()
        # Übernehme X-Request-ID oder generiere
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.correlation_id = rid
        # Operation-ID kann für längere Prozesse abgeleitet werden
        g.operation_id = f"{rid}"
        # Optionale Body/Query-Summary nur, wenn gewünscht
        body_summary = _summarize_body(request) if sample_bodies else {
            "present": request.content_length and request.content_length > 0,
            "content_length": request.content_length,
            "mimetype": request.mimetype,
        }
        query_summary = _summarize_query(request)
        # Optionaler Benutzerkontext (keine sensiblen Daten im Klartext)
        user_ctx = {}
        x_user = request.headers.get("X-User-Id")
        if x_user:
            user_ctx["id"] = x_user
        user_ctx["auth_present"] = bool(request.headers.get("Authorization"))

        _json_log(
            lg,
            logging.INFO,
            "http.request",
            phase="start",
            correlation_id=rid,
            method=request.method,
            path=request.path,
            route=request.endpoint,
            query=query_summary,
            body=body_summary,
            user=user_ctx,
            client_ip=request.headers.get("X-Forwarded-For") or request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
        )

    @app.after_request
    def _log_end(resp: Response):
        rid = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        duration_ms = int((time.time() - (getattr(g, "_req_ts", time.time()))) * 1000)
        req_size = int(request.content_length or 0)
        resp_size = _response_size(resp)
        # Rückgabe der Request-ID
        try:
            resp.headers["X-Request-ID"] = rid
        except Exception:
            pass

        _json_log(
            lg,
            logging.INFO,
            "http.request",
            phase="end",
            correlation_id=rid,
            method=request.method,
            path=request.path,
            route=request.endpoint,
            status_code=resp.status_code,
            duration_ms=duration_ms,
            request_size=req_size,
            response_size=resp_size,
        )
        return resp

    @app.teardown_request
    def _log_teardown(exc: Optional[BaseException]):
        if exc is None:
            return
        rid = getattr(g, "correlation_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
        _json_log(
            lg,
            logging.ERROR,
            "http.error",
            correlation_id=rid,
            method=request.method,
            path=request.path,
            route=request.endpoint,
            exc_type=exc.__class__.__name__,
            message=str(exc),
        )


def log_runtime_config_once(logger: Optional[logging.Logger] = None) -> None:
    """
    Loggt genau einmal einen strukturierten runtime_config Snapshot.
    """
    lg = logger or logging.getLogger("app")
    try:
        from .settings import get_runtime_config
        cfg = get_runtime_config()
    except Exception:
        cfg = {}
    # Commit/Version aus Env nutzen, wenn vorhanden
    meta = {
        "git_commit": os.environ.get("GIT_COMMIT"),
        "image_tag": os.environ.get("IMAGE_TAG"),
        "log_level": getattr(settings, "LOG_LEVEL", "INFO"),
        "log_format": getattr(settings, "LOG_FORMAT", "json"),
        "api_host": getattr(settings, "API_HOST", "0.0.0.0"),
        "api_port": getattr(settings, "API_PORT", 8081),
    }
    payload = {"event": "runtime_config", "config": cfg, "meta": meta}
    try:
        lg.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        lg.info(json.dumps({"event": "runtime_config", "error": "dump_failed"}))