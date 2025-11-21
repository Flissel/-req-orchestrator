# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Union

from ..runtime.logging import get_logger
from ..runtime.agent_base import AgentBase, AgentId, MessageContext
from ..model.openai_adapter import OpenAIAdapter
from .req_worker import ReqWorkerAgent
from .extraction_schema import REQUIREMENT_EXTRACTION_TOOL, EXTRACTION_SYSTEM_PROMPT

# Reuse ingestion helpers directly to avoid Qdrant dependency during mining
from backend.core.ingest import extract_texts, chunk_payloads  # noqa: E402

logger = get_logger("agents.chunk_miner")


def _coerce_files_or_texts(files_or_texts: List[Union[str, bytes, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Normalisiert Eingaben auf eine Liste von {filename, data, content_type}.
    Erlaubte Eingaben:
    - str: roher Text (als .txt)
    - bytes: roher Text/Bytes (als .txt)
    - dict: {filename, data, content_type?} oder {text}
    """
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(files_or_texts or []):
        if isinstance(item, str):
            out.append({"filename": f"input_{i}.txt", "data": item.encode("utf-8"), "content_type": "text/plain"})
        elif isinstance(item, bytes):
            out.append({"filename": f"input_{i}.txt", "data": item, "content_type": "text/plain"})
        elif isinstance(item, dict):
            if "text" in item:
                txt = str(item.get("text") or "")
                out.append({"filename": f"input_{i}.txt", "data": txt.encode("utf-8"), "content_type": "text/plain"})
            else:
                fn = str(item.get("filename") or f"input_{i}.txt")
                data = item.get("data") or b""
                if isinstance(data, str):
                    data = data.encode("utf-8")
                ct = str(item.get("content_type") or "")
                out.append({"filename": fn, "data": data, "content_type": ct})
        else:
            # Ignoriere unbekannte Typen
            continue
    return out


class ChunkMinerAgent(AgentBase):
    """
    Chunk-zu-Requirement Miner:
    - Nimmt Dateien/Texte entgegen
    - Extrahiert Text → erzeugt Overlap-Chunks
    - Ruft pro Chunk ein kompaktes Mining-Prompt (OpenAIAdapter) auf
    - Liefert pro erkanntem Requirement ein DTO an ReqWorkerAgent

    Nutzung:
      agent = ChunkMinerAgent()
      await agent.on_message({"files_or_texts": [...], "options": {"model": "gpt-4o-mini"}}, ctx)

    DTO-Format (an ReqWorkerAgent):
      {
        "req_id": "REQ-<stable>",
        "title": "Kurzbeschreibung",
        "tag": "functional|security|performance|ux|ops",
        "evidence_refs": [{"sourceFile": "...", "sha1": "...", "chunkIndex": 0}]
      }
    """

    SYSTEM_PROMPT = (
        "Du bist ein Requirements-Mining-Agent. "
        "Analysiere den gegebenen Textausschnitt und extrahiere 0..n konkrete Software-Requirements. "
        "Gib ausschließlich JSON im Format:\n"
        '{ "items": [ { "req_id": "REQ-...", "title": "...", "tag": "functional|security|performance|ux|ops", '
        '"evidence_refs": [ { "sourceFile": "...", "sha1": "...", "chunkIndex": 0 } ] } ] }\n'
        "- Keine Zusatzerklärungen, keinen Freitext außerhalb des JSON. "
        "Wenn kein Requirement erkennbar ist, gib {\"items\":[]} zurück."
    )

    USER_PROMPT_TEMPLATE = (
        "Nutze die folgende Vorgabe für req_id als stabile Basis für Requirements aus diesem Chunk: {suggested_req_id}. "
        "Wenn mehrere Requirements im Chunk vorkommen, hänge -a, -b, ... an.\n\n"
        "Text-Chunk:\n"
        "----\n"
        "{chunk_text}\n"
        "----\n"
        "Gib nur das JSON-Objekt zurück."
    )

    def __init__(self, source: str = "default", default_model: Optional[str] = None, temperature: float = 0.2) -> None:
        super().__init__(AgentId(type="chunk_miner", key=source))
        self.source = source
        self.temperature = float(temperature)
        self.adapter = OpenAIAdapter(default_model=default_model)
        self.req_worker = ReqWorkerAgent(source=source)

    def _build_messages(self, chunk_text: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        sha1 = str(payload.get("sha1") or "")
        chunk_idx = int(payload.get("chunkIndex") or 0)
        suggested_req_id = f"REQ-{(sha1 or 'X')[:6]}-{chunk_idx:03d}"

        user_prompt = self.USER_PROMPT_TEMPLATE.format(
            suggested_req_id=suggested_req_id,
            chunk_text=chunk_text.strip(),
        )
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_items(self, content: str) -> List[Dict[str, Any]]:
        try:
            data = json.loads(content)
            items = data.get("items") if isinstance(data, dict) else None
            if isinstance(items, list):
                return [i for i in items if isinstance(i, dict)]
        except Exception:
            pass
        # Fallback: Kein valides JSON → leere Liste
        return []

    def _ensure_item_fields(self, item: Dict[str, Any], payload: Dict[str, Any], additional_evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        # Pflichtfelder anreichern/normalisieren
        req_id = item.get("req_id") or item.get("reqId") or ""
        title = item.get("title") or item.get("redefinedRequirement") or item.get("final") or ""
        tag = (item.get("tag") or "").lower()
        if tag not in {"functional", "security", "performance", "ux", "ops"}:
            tag = "functional"

        ev = item.get("evidence_refs") or item.get("evidenceRefs") or item.get("citations") or []
        base_ev: List[Dict[str, Any]] = []
        if isinstance(ev, list):
            base_ev = [e for e in ev if isinstance(e, dict)]
        if not base_ev:
            base_ev = [
                {
                    "sourceFile": payload.get("sourceFile") or payload.get("source") or "",
                    "sha1": payload.get("sha1") or "",
                    "chunkIndex": payload.get("chunkIndex") or 0,
                }
            ]
        if additional_evidence:
            # Deduplicate by (sourceFile, sha1, chunkIndex)
            seen = {(e.get("sourceFile"), e.get("sha1"), e.get("chunkIndex")) for e in base_ev}
            for e in additional_evidence:
                key = (e.get("sourceFile"), e.get("sha1"), e.get("chunkIndex"))
                if key not in seen:
                    base_ev.append(e)
                    seen.add(key)

        return {
            "req_id": str(req_id or f"REQ-{(payload.get('sha1') or 'X')[:6]}-{int(payload.get('chunkIndex') or 0):03d}"),
            "title": str(title),
            "tag": tag,
            "evidence_refs": base_ev,
        }

    def _ensure_item_fields_from_tool_call(self, item: Dict[str, Any], payload: Dict[str, Any], suggested_req_id: str, additional_evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Process requirement item from tool call with enriched metadata"""
        # Extract tool call fields
        req_id = item.get("req_id") or suggested_req_id
        title = item.get("title") or ""
        tag = (item.get("tag") or "functional").lower()
        priority = (item.get("priority") or "must").lower()
        measurable_criteria = item.get("measurable_criteria") or ""
        actors = item.get("actors") or []
        evidence_text = item.get("evidence") or ""

        # Validate tag
        valid_tags = {"functional", "security", "performance", "ux", "ops", "usability", "reliability", "compliance", "interface", "data", "constraint"}
        if tag not in valid_tags:
            tag = "functional"

        # Build evidence_refs from evidence text or payload
        base_ev: List[Dict[str, Any]] = [
            {
                "sourceFile": payload.get("sourceFile") or payload.get("source") or "",
                "sha1": payload.get("sha1") or "",
                "chunkIndex": payload.get("chunkIndex") or 0,
            }
        ]

        if additional_evidence:
            # Deduplicate by (sourceFile, sha1, chunkIndex)
            seen = {(e.get("sourceFile"), e.get("sha1"), e.get("chunkIndex")) for e in base_ev}
            for e in additional_evidence:
                key = (e.get("sourceFile"), e.get("sha1"), e.get("chunkIndex"))
                if key not in seen:
                    base_ev.append(e)
                    seen.add(key)

        # Build result with core fields + optional enriched fields
        result = {
            "req_id": str(req_id),
            "title": str(title),
            "tag": tag,
            "evidence_refs": base_ev,
        }

        # Add optional enriched fields if present
        if priority:
            result["priority"] = priority
        if measurable_criteria:
            result["measurable_criteria"] = measurable_criteria
        if actors:
            result["actors"] = actors if isinstance(actors, list) else [actors]
        if evidence_text:
            result["evidence"] = evidence_text

        return result

    def _mine_chunk(self, chunk_text: str, payload: Dict[str, Any], model_override: Optional[str]) -> List[Dict[str, Any]]:
        """Extract requirements using tool calling for structured, high-quality output"""
        sha1 = str(payload.get("sha1") or "")
        chunk_idx = int(payload.get("chunkIndex") or 0)
        suggested_req_id = f"REQ-{(sha1 or 'X')[:6]}-{chunk_idx:03d}"

        # Build messages for tool-based extraction
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract all requirements from the following text chunk.\n"
                    f"Use '{suggested_req_id}' as the base for req_id, adding -a, -b, -c... for multiple requirements.\n\n"
                    f"Text:\n---\n{chunk_text.strip()}\n---"
                )
            }
        ]

        try:
            response = self.adapter.create(
                messages=messages,
                temperature=self.temperature,
                model=model_override,
                tools=[REQUIREMENT_EXTRACTION_TOOL],
                tool_choice={"type": "function", "function": {"name": "submit_requirements"}}
            )

            # Check if we got a tool call response
            if hasattr(response, 'choices'):
                # Full response object with tool calls
                message = response.choices[0].message
                if message.tool_calls:
                    tool_call = message.tool_calls[0]
                    requirements_data = json.loads(tool_call.function.arguments)
                    items = requirements_data.get("requirements", [])
                else:
                    logger.warning("Tool call expected but not received - fallback to parsing")
                    items = self._parse_items(str(message.content or "").strip())
            else:
                # Backward compatibility: string response (fallback to old JSON parsing)
                logger.warning("String response received instead of tool call - using legacy parser")
                items = self._parse_items(str(response or "").strip())

        except Exception as e:
            logger.warning("Chunk mining failed (adapter): %s", e)
            return []

        # Process extracted items and ensure required fields
        # Add unique suffixes -a, -b, -c... if multiple requirements from same chunk
        out: List[Dict[str, Any]] = []
        suffixes = [''] + [f'-{chr(97+i)}' for i in range(26)]  # '', '-a', '-b', ..., '-z'

        for idx, it in enumerate(items):
            enriched = self._ensure_item_fields_from_tool_call(it, payload, suggested_req_id)

            # Override req_id with unique suffix if multiple items
            if len(items) > 1:
                suffix = suffixes[idx] if idx < len(suffixes) else f'-{idx}'
                enriched['req_id'] = f"{suggested_req_id}{suffix}"

            out.append(enriched)
        return out

    def mine_files_or_texts(
        self,
        files_or_texts: List[Union[str, bytes, Dict[str, Any]]],
        *,
        model: Optional[str] = None,
        neighbor_refs: bool = False,
    ) -> int:
        """
        Führt Mining end-to-end aus. Gibt die Anzahl generierter DTOs zurück.
        """
        normalized = _coerce_files_or_texts(files_or_texts)
        raw_records: List[Dict[str, Any]] = []
        for rec in normalized:
            try:
                parts = extract_texts(rec["filename"], rec["data"], rec.get("content_type") or "")
                raw_records.extend(parts)
            except Exception as e:
                logger.warning("extract_texts failed for %s: %s", rec.get("filename"), e)

        if not raw_records:
            logger.info("ChunkMiner: keine extrahierten Rohtexte – Abbruch")
            return 0

        payloads = chunk_payloads(raw_records)
        # Fallback: Wenn Nachbarschaft aktiviert ist aber nur 1 Chunk entstanden ist,
        # erzwinge feinere Chunking-Parameter, um mindestens 2 Chunks zu ermöglichen.
        if neighbor_refs and len(payloads) < 2:
            try:
                payloads = chunk_payloads(raw_records, min_tokens=1, max_tokens=8, overlap_tokens=1)
            except Exception:
                pass
            # Letzter Rückfall: harte Zweiteilung des ersten Rohblocks, um ≥2 Chunks zu garantieren
            if len(payloads) < 2 and raw_records:
                try:
                    rec0 = raw_records[0]
                    text0 = str(rec0.get("text") or "")
                    words = text0.split()
                    if len(words) > 1:
                        mid = max(1, len(words) // 2)
                        parts = [" ".join(words[:mid]), " ".join(words[mid:])]
                    else:
                        # Falls extrem kurz, dupliziere – Ziel ist nur, die Neighbor-Logik zu demonstrieren
                        parts = [text0, text0]
                    meta0 = dict(rec0.get("meta") or {})
                    forced_payloads: List[Dict[str, Any]] = []
                    for idx, ch in enumerate(parts):
                        pld = dict(meta0)
                        pld["chunkIndex"] = idx
                        # tokenLen nur grob (Wortanzahl)
                        forced_payloads.append({"text": ch, "payload": {**pld, "tokenLen": max(1, len(ch.split()))}})
                    payloads = forced_payloads
                except Exception:
                    pass
        if not payloads:
            logger.info("ChunkMiner: keine Chunks erzeugt – Abbruch")
            return 0

        produced = 0

        # Nachbarschafts-Belege (chunkIndex±1) innerhalb derselben Datei/sha1
        def _neighbor_evidence(idx: int) -> List[Dict[str, Any]]:
            if not neighbor_refs:
                return []
            evs: List[Dict[str, Any]] = []
            cur_pl = payloads[idx].get("payload") or {}
            cur_sha = cur_pl.get("sha1") or ""
            cur_src = cur_pl.get("sourceFile") or cur_pl.get("source") or ""
            for j in (idx - 1, idx + 1):
                if j < 0 or j >= len(payloads):
                    continue
                plj = payloads[j].get("payload") or {}
                if (plj.get("sha1") or "") == cur_sha and (plj.get("sourceFile") or plj.get("source") or "") == cur_src:
                    evs.append(
                        {
                            "sourceFile": plj.get("sourceFile") or plj.get("source") or "",
                            "sha1": plj.get("sha1") or "",
                            "chunkIndex": plj.get("chunkIndex") or 0,
                        }
                    )
            return evs

        for idx, p in enumerate(payloads):
            chunk_text = str(p.get("text") or "")
            payload = dict(p.get("payload") or {})
            if not chunk_text.strip():
                continue

            items = self._mine_chunk(chunk_text, payload, model_override=model)
            if not items:
                continue

            add_evs = _neighbor_evidence(idx)
            for dto in items:
                try:
                    enriched = self._ensure_item_fields(dto, payload, additional_evidence=add_evs)
                    # Ausgabe an Frontend-Worker (Stub/optional REST)
                    self.req_worker.send_to_frontend(enriched)
                    produced += 1
                except Exception as e:
                    logger.warning("ReqWorker send failed: %s", e)

        logger.info("ChunkMiner: %d DTO(s) erzeugt", produced)
        return produced

    def mine_files_or_texts_collect(
        self,
        files_or_texts: List[Union[str, bytes, Dict[str, Any]]],
        *,
        model: Optional[str] = None,
        neighbor_refs: bool = False,
        chunk_options: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Wie mine_files_or_texts(), sammelt jedoch alle erzeugten DTOs und gibt sie als Liste zurück
        anstatt sie an den ReqWorker zu senden.

        Args:
            chunk_options: Optional dict mit 'max_tokens', 'min_tokens', 'overlap_tokens'
        """
        normalized = _coerce_files_or_texts(files_or_texts)
        raw_records: List[Dict[str, Any]] = []
        for rec in normalized:
            try:
                parts = extract_texts(rec["filename"], rec["data"], rec.get("content_type") or "")
                raw_records.extend(parts)
            except Exception as e:
                logger.warning("extract_texts failed for %s: %s", rec.get("filename"), e)

        if not raw_records:
            logger.info("ChunkMiner: keine extrahierten Rohtexte – Abbruch")
            return []

        # Verwende chunk_options wenn vorhanden
        chunk_kwargs = chunk_options or {}
        payloads = chunk_payloads(raw_records, **chunk_kwargs)
        # Fallback: Wenn Nachbarschaft aktiviert ist aber nur 1 Chunk entstanden ist,
        # erzwinge feinere Chunking-Parameter, um mindestens 2 Chunks zu ermöglichen.
        if neighbor_refs and len(payloads) < 2:
            try:
                payloads = chunk_payloads(raw_records, min_tokens=1, max_tokens=8, overlap_tokens=1)
            except Exception:
                pass
            # Letzter Rückfall: harte Zweiteilung des ersten Rohblocks, um ≥2 Chunks zu garantieren
            if len(payloads) < 2 and raw_records:
                try:
                    rec0 = raw_records[0]
                    text0 = str(rec0.get("text") or "")
                    words = text0.split()
                    if len(words) > 1:
                        mid = max(1, len(words) // 2)
                        parts = [" ".join(words[:mid]), " ".join(words[mid:])]
                    else:
                        # Falls extrem kurz, dupliziere – Ziel ist nur, die Neighbor-Logik zu demonstrieren
                        parts = [text0, text0]
                    meta0 = dict(rec0.get("meta") or {})
                    forced_payloads: List[Dict[str, Any]] = []
                    for idx, ch in enumerate(parts):
                        pld = dict(meta0)
                        pld["chunkIndex"] = idx
                        # tokenLen nur grob (Wortanzahl)
                        forced_payloads.append({"text": ch, "payload": {**pld, "tokenLen": max(1, len(ch.split()))}})
                    payloads = forced_payloads
                except Exception:
                    pass

        if not payloads:
            logger.info("ChunkMiner: keine Chunks erzeugt – Abbruch")
            return []

        # Nachbarschafts-Belege (chunkIndex±1) innerhalb derselben Datei/sha1
        def _neighbor_evidence(idx: int) -> List[Dict[str, Any]]:
            if not neighbor_refs:
                return []
            evs: List[Dict[str, Any]] = []
            cur_pl = payloads[idx].get("payload") or {}
            cur_sha = cur_pl.get("sha1") or ""
            cur_src = cur_pl.get("sourceFile") or cur_pl.get("source") or ""
            for j in (idx - 1, idx + 1):
                if j < 0 or j >= len(payloads):
                    continue
                plj = payloads[j].get("payload") or {}
                if (plj.get("sha1") or "") == cur_sha and (plj.get("sourceFile") or plj.get("source") or "") == cur_src:
                    evs.append(
                        {
                            "sourceFile": plj.get("sourceFile") or plj.get("source") or "",
                            "sha1": plj.get("sha1") or "",
                            "chunkIndex": plj.get("chunkIndex") or 0,
                        }
                    )
            return evs

        items_out: List[Dict[str, Any]] = []

        for idx, p in enumerate(payloads):
            chunk_text = str(p.get("text") or "")
            payload = dict(p.get("payload") or {})
            if not chunk_text.strip():
                continue

            items = self._mine_chunk(chunk_text, payload, model_override=model)
            if not items:
                continue

            add_evs = _neighbor_evidence(idx)
            for dto in items:
                try:
                    enriched = self._ensure_item_fields(dto, payload, additional_evidence=add_evs)
                    items_out.append(enriched)
                except Exception as e:
                    logger.warning("collect dto failed: %s", e)

        logger.info("ChunkMiner: %d DTO(s) gesammelt", len(items_out))
        return items_out

    async def on_message(self, message: Dict[str, Any], ctx: MessageContext) -> None:
        """
        Erwartet:
          {
            "files_or_texts": [str|bytes|{filename,data,content_type}|{text}, ...],
            "options": {"model": "gpt-4o-mini"}
          }
        """
        files_or_texts = message.get("files_or_texts") or []
        opts = message.get("options") or {}
        model = opts.get("model")
        neighbor_refs = bool(opts.get("neighbor_refs"))

        if not neighbor_refs:
            env_flag = (os.environ.get("CHUNK_MINER_NEIGHBORS", "") or "").strip().lower()
            neighbor_refs = env_flag in ("1", "true", "yes", "on")

        if not isinstance(files_or_texts, list) or not files_or_texts:
            logger.warning("ChunkMinerAgent.on_message: files_or_texts fehlt/leer")
            return

        try:
            count = self.mine_files_or_texts(files_or_texts, model=model, neighbor_refs=neighbor_refs)
            logger.info("ChunkMinerAgent: Mining abgeschlossen, erzeugt=%d", count)
        except Exception as e:
            logger.error("ChunkMinerAgent.on_message fehlgeschlagen: %s", e, exc_info=True)