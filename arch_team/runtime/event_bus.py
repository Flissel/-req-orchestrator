# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Tuple

from .topics import TopicId
from .agent_base import MessageContext
from .logging import get_logger

logger = get_logger("runtime.event_bus")


Handler = Callable[[Dict[str, Any], MessageContext], Awaitable[None]]


class EventBus:
    """
    In-Process EventBus.
    - subscribe(topic_type, agent_type, handler)
    - publish(topic_id, message, ctx)
    """

    def __init__(self) -> None:
        # Map: topic_type -> list of (agent_type, handler)
        self._subs: Dict[str, List[Tuple[str, Handler]]] = {}
        # simple lock for subscribe/publish mutation
        self._lock = asyncio.Lock()

    async def subscribe(self, topic_type: str, agent_type: str, handler: Handler) -> None:
        """
        Registriert einen asynchronen Handler für einen Topic-Typ.
        """
        async with self._lock:
            arr = self._subs.setdefault(topic_type, [])
            arr.append((agent_type, handler))
            logger.info("Subscribed agent=%s to topic=%s (now=%d)", agent_type, topic_type, len(arr))

    async def publish(self, topic_id: TopicId, message: Dict[str, Any], ctx: MessageContext) -> None:
        """
        Verteilt eine Nachricht an alle Subscriber für topic_id.type.
        """
        topic_type = topic_id.type
        if not topic_type:
            logger.warning("publish called with empty topic.type; dropping message")
            return

        # Snapshot handlers without holding lock during awaits
        async with self._lock:
            handlers = list(self._subs.get(topic_type, []))

        if not handlers:
            logger.info("No subscribers for topic=%s; message ignored", topic_type)
            return

        logger.debug("Publishing to topic=%s subscribers=%d", topic_type, len(handlers))
        # Sequential dispatch to keep ordering deterministic for baseline
        for agent_type, handler in handlers:
            try:
                await handler(message, ctx)
            except Exception as e:
                logger.error("Handler failed (agent=%s, topic=%s): %s", agent_type, topic_type, e, exc_info=True)