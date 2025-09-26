# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional

from .topics import TopicId
from .logging import get_logger

logger = get_logger("runtime.agent_base")


@dataclass(frozen=True)
class AgentId:
    """
    Identität eines Agents innerhalb der Runtime.

    Felder:
    - type: logischer Agent-Typ (z. B. planner|solver|verifier|req_worker)
    - key: Instanz-Schlüssel (z. B. default|session-abc)
    """
    type: str
    key: str = "default"


@dataclass
class MessageContext:
    """
    Kontextinformationen für Nachrichtenfluss im Single-Process-Bus.
    CoT-Privacy: Niemals THOUGHTS/CRITIQUE ins Frontend leaken.
    """
    correlation_id: str
    req_id: Optional[str] = None
    session_id: Optional[str] = None
    topic_id: Optional[TopicId] = None
    origin_agent: Optional[AgentId] = None
    # Frei nutzbare Metadaten
    meta: Dict[str, Any] = field(default_factory=dict)


class AgentBase(ABC):
    """
    Basisklasse für Worker/Agents. Implementiert nur die Nachrichtenschnittstelle.
    """

    def __init__(self, agent_id: AgentId):
        self.id = agent_id

    @abstractmethod
    async def on_message(self, message: Dict[str, Any], ctx: MessageContext) -> None:
        """
        Verarbeitet eine Nachricht. Implementierungen MÜSSEN nicht-blockierend arbeiten.
        """
        ...

    async def publish(
        self,
        bus: "EventBus",
        topic_id: TopicId,
        message: Dict[str, Any],
        ctx: MessageContext,
    ) -> None:
        """
        Helper: Publish mit Logging und weitergegebenem Kontext.
        """
        try:
            await bus.publish(topic_id=topic_id, message=message, ctx=ctx)
        except Exception as e:
            logger.error("Publish failed for topic=%s by agent=%s: %s", topic_id.type, self.id.type, e, exc_info=True)
            raise