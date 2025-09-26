# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from ..runtime.logging import get_logger
from ..memory.qdrant_kg import QdrantKGClient
from ..model.openai_adapter import OpenAIAdapter  # optional LLM mapping

logger = get_logger("agents.kg_agent")


def _norm_key(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9äöüß\s:\-_/\.]", "", s)
    return s


def _entity_id(prefix: str, name: str) -> str:
    return f"{prefix}:{_norm_key(name).replace(' ', '_')}"


class KGAbstractionAgent:
    """
    Baut aus Requirement-DTOs (req_id,title,tag,evidence_refs) einen Knowledge Graph.

    Minimaler Heuristik-Mapping (LLM-optional):
      - Requirement-Node pro DTO
      - Tag-Node und HAS_TAG-Kante
      - Heuristik: Actor/Entity/Action (best effort) aus title
      - Evidenz-Infos in Payload der Kanten/Nodes (keine separaten Evidence-Nodes v1)

    Persistenz:
      - Qdrant über QdrantKGClient (kg_nodes_v1, kg_edges_v1)
    """

    def __init__(self, default_model: Optional[str] = None) -> None:
        self.default_model = default_model or os.environ.get("MODEL_NAME", "gpt-4o-mini")
        self._llm_available = bool(os.environ.get("OPENAI_API_KEY"))

    # -------------------------
    # Public API
    # -------------------------
    def run(
        self,
        items: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        persist: Optional[str] = "qdrant",
        use_llm: bool = False,
        llm_fallback: bool = True,
        dedupe: bool = True,
    ) -> Dict[str, Any]:
        if not items:
            return {"nodes": [], "edges": [], "stats": {"nodes": 0, "edges": 0, "deduped": 0}}

        all_nodes: List[Dict[str, Any]] = []
        all_edges: List[Dict[str, Any]] = []

        # Map pro DTO
        for it in items:
            n, e = self._map_item_to_graph(
                it,
                use_llm=(use_llm and self._llm_available),
                model=model or self.default_model,
                llm_fallback=(llm_fallback and self._llm_available),
            )
            all_nodes.extend(n)
            all_edges.extend(e)

        if dedupe:
            all_nodes, ded_n = self._dedupe_nodes(all_nodes)
            all_edges, ded_e = self._dedupe_edges(all_edges)
        else:
            ded_n = ded_e = 0

        stats = {"nodes": len(all_nodes), "edges": len(all_edges), "deduped": ded_n + ded_e}

        # Persistenz
        if persist == "qdrant":
            qkg = QdrantKGClient()
            try:
                qkg.ensure_collections()
                _, node_ids = qkg.upsert_nodes(all_nodes)
                _, edge_ids = qkg.upsert_edges(all_edges)
                stats["persisted_nodes"] = len(node_ids)
                stats["persisted_edges"] = len(edge_ids)
            except Exception as e:
                logger.error("Qdrant persist failed: %s", e)
                stats["persist_error"] = str(e)

        return {"nodes": all_nodes, "edges": all_edges, "stats": stats}

    # -------------------------
    # Dedupe Helpers
    # -------------------------
    def _dedupe_nodes(self, nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Entfernt Dubletten anhand stabiler Schlüssel in Reihenfolge:
        id | node_id | payload.canonical_key | payload.node_id | (fallback) type#name
        Gibt (kompakte Liste, Anzahl entfernter Elemente) zurück.
        """
        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        removed = 0
        for n in nodes or []:
            payload = dict(n.get("payload") or {})
            key = str(
                n.get("id")
                or n.get("node_id")
                or payload.get("canonical_key")
                or payload.get("node_id")
                or ""
            ).strip()
            if not key:
                # Fallback: type#name normalisiert
                ntype = str(n.get("type") or payload.get("type") or "Unknown")
                nname = str(n.get("name") or payload.get("name") or ntype)
                key = f"{ntype}#{_norm_key(nname)}"
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            out.append(n)
        return out, removed

    def _dedupe_edges(self, edges: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """
        Entfernt Dubletten anhand stabiler Schlüssel in Reihenfolge:
        id | edge_id | payload.canonical_key | (from_node_id, rel, to_node_id)
        Gibt (kompakte Liste, Anzahl entfernter Elemente) zurück.
        """
        seen: set[str] = set()
        out: List[Dict[str, Any]] = []
        removed = 0
        for e in edges or []:
            payload = dict(e.get("payload") or {})
            key = str(
                e.get("id")
                or e.get("edge_id")
                or payload.get("canonical_key")
                or ""
            ).strip()
            if not key:
                fr = str(e.get("from") or payload.get("from_node_id") or "")
                to = str(e.get("to") or payload.get("to_node_id") or "")
                rel = str(e.get("rel") or payload.get("rel") or "RELATES_TO")
                key = f"from={fr}|rel={rel}|to={to}"
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            out.append(e)
        return out, removed

    # -------------------------
    # Mapping per Item
    # -------------------------
    def _map_item_to_graph(self, it: Dict[str, Any], use_llm: bool, model: str, llm_fallback: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        req_id = str(it.get("req_id") or "").strip() or f"REQ-{_norm_key(it.get('title',''))[:16] or 'unknown'}"
        title = str(it.get("title") or req_id).strip()
        tag = str(it.get("tag") or "functional").strip()
        evs = it.get("evidence_refs") or []
        first_src = {}
        if isinstance(evs, list) and evs:
            ref0 = evs[0] if isinstance(evs[0], dict) else {}
            first_src = {
                "file": ref0.get("sourceFile"),
                "sha1": ref0.get("sha1"),
                "chunkIndex": ref0.get("chunkIndex"),
            }

        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        # Requirement
        req_node = {
            "id": req_id,
            "type": "Requirement",
            "name": title,
            "payload": {
                "node_id": req_id,
                "type": "Requirement",
                "name": title,
                "tag": tag,
                "source": first_src,
                "raw": it,
                "canonical_key": f"requirement#{_norm_key(req_id)}",
            },
            "embed_text": title,
        }
        nodes.append(req_node)

        # Tag
        tag_id = _entity_id("Tag", tag)
        nodes.append(
            {
                "id": tag_id,
                "type": "Tag",
                "name": tag,
                "payload": {
                    "node_id": tag_id,
                    "type": "Tag",
                    "name": tag,
                    "canonical_key": f"tag#{_norm_key(tag)}",
                },
            }
        )
        edges.append(
            {
                "id": f"{req_id}#HAS_TAG#{tag_id}",
                "from": req_id,
                "to": tag_id,
                "rel": "HAS_TAG",
                "payload": {
                    "edge_id": f"{req_id}#HAS_TAG#{tag_id}",
                    "from_node_id": req_id,
                    "to_node_id": tag_id,
                    "rel": "HAS_TAG",
                    "evidence": evs,
                    "canonical_key": f"from={req_id}|rel=HAS_TAG|to={tag_id}",
                },
                "embed_text": f"{title} HAS_TAG {tag}",
            }
        )

        # Heuristik Actor/Entity/Action (best effort)
        extra_nodes, extra_edges = self._heuristic_actor_entity_action(req_id, title, evs)
        nodes.extend(extra_nodes)
        edges.extend(extra_edges)

        # Optional LLM für feinere Zerlegung (striktes JSON Schema)
        # Fallback: Falls Heuristik nichts zusätzlich gefunden hat, darf (bei aktivem llm_fallback) LLM nachziehen.
        sparse = (len(extra_nodes) == 0 and len(extra_edges) == 0)
        if use_llm or (llm_fallback and sparse):
            try:
                llm_nodes, llm_edges = self._llm_expand(title=title, req_id=req_id, tag=tag, model=model)
                nodes.extend(llm_nodes)
                edges.extend(llm_edges)
            except Exception as e:
                logger.warning("LLM KG expand skipped: %s", e)

        return nodes, edges

    # -------------------------
    # Heuristics
    # -------------------------
    def _heuristic_actor_entity_action(self, req_id: str, title: str, evs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        lower = title.lower()

        # Actor candidates
        actor = None
        if "benutzer" in lower:
            actor = "Benutzer"
        elif "nutzer" in lower:
            actor = "Nutzer"
        elif "user" in lower:
            actor = "User"

        if actor:
            act_id = _entity_id("Actor", actor)
            nodes.append(
                {
                    "id": act_id,
                    "type": "Actor",
                    "name": actor,
                    "payload": {"node_id": act_id, "type": "Actor", "name": actor, "canonical_key": f"actor#{_norm_key(actor)}"},
                }
            )
            edges.append(
                {
                    "id": f"{req_id}#HAS_ACTOR#{act_id}",
                    "from": req_id,
                    "to": act_id,
                    "rel": "HAS_ACTOR",
                    "payload": {
                        "edge_id": f"{req_id}#HAS_ACTOR#{act_id}",
                        "from_node_id": req_id,
                        "to_node_id": act_id,
                        "rel": "HAS_ACTOR",
                        "evidence": evs,
                        "canonical_key": f"from={req_id}|rel=HAS_ACTOR|to={act_id}",
                    },
                    "embed_text": f"{title} HAS_ACTOR {actor}",
                }
            )

        # Entity candidates (simple keywords)
        entity_candidates = []
        for key in ["profil", "passwort", "token", "rollen", "rolle", "account", "formular", "suchergebnis", "deployment", "metriken"]:
            if key in lower:
                entity_candidates.append(key.capitalize())
        entity_candidates = list(dict.fromkeys(entity_candidates))  # uniq

        ent_nodes = []
        last_action_id = None

        # Action guess: first word ending with 'en' as a naive German verb heuristic
        action_guess = None
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß\-]+", title)
        for t in tokens:
            tl = t.lower()
            if len(tl) > 3 and tl.endswith("en"):
                action_guess = t
                break
        if action_guess:
            action_id = _entity_id("Action", action_guess)
            last_action_id = action_id
            nodes.append(
                {
                    "id": action_id,
                    "type": "Action",
                    "name": action_guess,
                    "payload": {"node_id": action_id, "type": "Action", "verb": action_guess, "canonical_key": f"action#{_norm_key(action_guess)}"},
                }
            )
            edges.append(
                {
                    "id": f"{req_id}#HAS_ACTION#{action_id}",
                    "from": req_id,
                    "to": action_id,
                    "rel": "HAS_ACTION",
                    "payload": {
                        "edge_id": f"{req_id}#HAS_ACTION#{action_id}",
                        "from_node_id": req_id,
                        "to_node_id": action_id,
                        "rel": "HAS_ACTION",
                        "evidence": evs,
                        "canonical_key": f"from={req_id}|rel=HAS_ACTION|to={action_id}",
                    },
                    "embed_text": f"{title} HAS_ACTION {action_guess}",
                }
            )

        for ename in entity_candidates:
            eid = _entity_id("Entity", ename)
            ent_nodes.append(
                {
                    "id": eid,
                    "type": "Entity",
                    "name": ename,
                    "payload": {"node_id": eid, "type": "Entity", "name": ename, "canonical_key": f"entity#{_norm_key(ename)}"},
                }
            )
            # Link action to entity if action exists
            if last_action_id:
                edges.append(
                    {
                        "id": f"{last_action_id}#ON_ENTITY#{eid}",
                        "from": last_action_id,
                        "to": eid,
                        "rel": "ON_ENTITY",
                        "payload": {
                            "edge_id": f"{last_action_id}#ON_ENTITY#{eid}",
                            "from_node_id": last_action_id,
                            "to_node_id": eid,
                            "rel": "ON_ENTITY",
                            "evidence": evs,
                            "canonical_key": f"from={last_action_id}|rel=ON_ENTITY|to={eid}",
                        },
                        "embed_text": f"{last_action_id} ON_ENTITY {ename}",
                    }
                )

        nodes.extend(ent_nodes)
        return nodes, edges

    # -------------------------
    # Optional LLM expansion
    # -------------------------
    def _llm_expand(self, *, title: str, req_id: str, tag: str, model: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fragt ein striktes JSON vom LLM ab:
          { "nodes": [...], "edges": [...] }
        Akzeptiert nur valide JSONs, invalid → ignoriert.
        """
        prompt = [
            {"role": "system", "content": "Extrahiere aus dem Requirement-Titel eine KG-Ansicht. Antworte NUR mit JSON (keine Erklärungen)."},
            {
                "role": "user",
                "content": (
                    "Gib ein JSON mit Knoten und Kanten zurück.\n"
                    "Schema:\n"
                    "{\n"
                    '  "nodes": [{"id": "...", "type": "...", "name": "..."}],\n'
                    '  "edges": [{"from": "...", "to": "...", "rel": "..."}]\n'
                    "}\n"
                    f'Titel: "{title}"\n'
                    f"ReqId: {req_id}\n"
                    f"Tag: {tag}\n"
                ),
            },
        ]
        try:
            client = OpenAIAdapter(default_model=model)
            content = client.create(messages=prompt, temperature=0.0, model=model)
            import json  # local import
            data = json.loads(content or "{}")
            raw_nodes = data.get("nodes") or []
            raw_edges = data.get("edges") or []
            nodes: List[Dict[str, Any]] = []
            edges: List[Dict[str, Any]] = []
            for n in raw_nodes:
                nid = str(n.get("id") or "").strip()
                name = str(n.get("name") or nid or "").strip()
                ntype = str(n.get("type") or "Entity").strip()
                if not nid:
                    nid = _entity_id(ntype, name or ntype)
                nodes.append({"id": nid, "type": ntype, "name": name or nid, "payload": {"node_id": nid, "type": ntype, "name": name or nid}})
            for e in raw_edges:
                fr = str(e.get("from") or "").strip()
                to = str(e.get("to") or "").strip()
                rel = str(e.get("rel") or "RELATES_TO").strip()
                if fr and to:
                    eid = f"{fr}#{rel}#{to}"
                    edges.append({"id": eid, "from": fr, "to": to, "rel": rel, "payload": {"edge_id": eid, "from_node_id": fr, "to_node_id": to, "rel": rel}})
            return nodes, edges
        except Exception as e:
            logger.debug("LLM expand parse failed: %s", e)
            return [], []


# Convenience request/response types (für API)
class KGBuildRequest(Dict[str, Any]):
    pass


class KGBuildResult(Dict[str, Any]):
    pass