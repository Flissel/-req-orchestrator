# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import json
from typing import Any, Dict

from ..runtime.agent_base import AgentBase, AgentId, MessageContext
from ..runtime.logging import get_logger

logger = get_logger("agents.req_worker")


class ReqWorkerAgent(AgentBase):
    """
    Platzhalter-Agent für Frontend-Übergabe.
    - Nimmt DTOs entgegen (StructuredRequirement serialisiert) und würde sie an ein Frontend senden.
    - Der eigentliche Transport (REST/WS) ist TODO.
    """

    def __init__(self, source: str = "default") -> None:
        super().__init__(AgentId(type="req_worker", key=source))
        self.bus = None  # optional

    def set_bus(self, bus) -> None:
        self.bus = bus

    def send_to_frontend(self, dto: Dict[str, Any]) -> None:
        """
        TODO: Implementiere später REST/WS-Auslieferung.
        Aktuell nur Logging, um die Übergabestelle klar zu markieren.
        Zusätzliche DTO-Validierung: req_id, title, tag, evidence_refs erforderlich.
        """
        # Tolerante Feldzuordnung
        req_id = dto.get("req_id") or dto.get("reqId") or dto.get("id")
        title = dto.get("title") or dto.get("redefinedRequirement") or dto.get("final") or ""
        tag = dto.get("tag") or dto.get("category") or ""
        evidence_refs = dto.get("evidence_refs") or dto.get("evidenceRefs") or dto.get("citations") or []

        missing = []
        if not req_id:
            missing.append("req_id")
        if not title:
            missing.append("title")
        if not tag:
            missing.append("tag")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            missing.append("evidence_refs")

        if missing:
            logger.warning("[ReqWorker] DTO validation failed missing=%s dto=%s", ",".join(missing), {k: dto.get(k) for k in ["req_id","reqId","title","tag","evidence_refs"]})
        else:
            logger.info("[ReqWorker] DTO validated (req_id=%s, title.len=%d, tag=%s, evidence_refs=%d)", req_id, len(str(title)), tag, len(evidence_refs))
        # Optional REST-POST, falls konfiguriert
        endpoint = (os.environ.get("REQ_WORKER_ENDPOINT") or "").strip()
        if endpoint:
            try:
                # bevorzugt requests, sonst urllib
                try:
                    import requests  # type: ignore
                    resp = requests.post(endpoint, json=dto, timeout=float(os.environ.get("REQ_WORKER_TIMEOUT", "5")))
                    logger.info("[ReqWorker] POST %s -> %s", endpoint, resp.status_code)
                except Exception:
                    import urllib.request as _urlreq  # type: ignore
                    import urllib.error as _urlerr  # type: ignore
                    data = json.dumps(dto).encode("utf-8")
                    req = _urlreq.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
                    with _urlreq.urlopen(req, timeout=float(os.environ.get("REQ_WORKER_TIMEOUT", "5"))) as r:  # type: ignore
                        logger.info("[ReqWorker] POST %s (urllib) -> %s", endpoint, getattr(r, "status", "ok"))
            except Exception as e:
                logger.warning("[ReqWorker] transport failed: %s", e)
        else:
            logger.info("[ReqWorker] DTO ready for frontend transport (stub): %s", dto)

    async def on_message(self, message: Dict[str, Any], ctx: MessageContext) -> None:
        dto = message.get("dto")
        if not isinstance(dto, dict):
            logger.warning("ReqWorkerAgent: dto fehlt oder hat falsches Format")
            return
        self.send_to_frontend(dto)