# -*- coding: utf-8 -*-
"""
Validation Stream Service - SSE (Server-Sent Events) Streaming

This service provides real-time streaming of validation updates from the
RequirementOrchestrator to the frontend. It manages session-based event queues
and provides SSE endpoints for clients to subscribe to validation updates.

Event Types:
- evaluation_started: Validation begins for a requirement
- evaluation_completed: All criteria evaluated, scores available
- requirement_updated: Requirement text changed after criterion fix
- requirement_split: Requirement split into atomic sub-requirements
- validation_complete: Validation finished (passed or failed)
- validation_error: Error occurred during validation

Usage (Backend):
    from backend.services.validation_stream_service import validation_stream_service

    # Create stream callback for orchestrator
    async def stream_callback(event_type, data):
        await validation_stream_service.emit_event(session_id, event_type, data)

    # Start orchestration with callback
    orchestrator = RequirementOrchestrator(stream_callback=stream_callback)
    result = await orchestrator.process(req_id, req_text, session_id=session_id)

Usage (Frontend - EventSource):
    const eventSource = new EventSource(`/api/v1/validation/stream/${sessionId}`);

    eventSource.addEventListener('requirement_updated', (event) => {
        const data = JSON.parse(event.data);
        console.log('Requirement updated:', data.old_text, '→', data.new_text);
    });

    eventSource.addEventListener('validation_complete', (event) => {
        const data = JSON.parse(event.data);
        console.log('Validation complete:', data.passed, data.final_score);
        eventSource.close();
    });
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, Optional, Set
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationEvent:
    """Single validation event with timestamp"""
    event_type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_sse_format(self) -> str:
        """
        Convert to SSE (Server-Sent Events) format

        Returns:
            SSE-formatted string: "event: {type}\ndata: {json}\n\n"
        """
        return f"event: {self.event_type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


class ValidationStreamService:
    """
    Manages SSE streams for validation sessions

    Features:
    - Session-based event queues
    - Automatic cleanup of old sessions (1 hour timeout)
    - Multiple subscribers per session
    - Thread-safe event emission
    """

    def __init__(self, session_timeout_minutes: int = 60):
        """
        Initialize validation stream service

        Args:
            session_timeout_minutes: Cleanup sessions older than this (default: 60)
        """
        # Session ID → Queue of events
        self._session_queues: Dict[str, asyncio.Queue[ValidationEvent]] = {}

        # Session ID → Set of active subscriber tasks
        self._session_subscribers: Dict[str, Set[asyncio.Task]] = defaultdict(set)

        # Session ID → Last activity timestamp
        self._session_timestamps: Dict[str, datetime] = {}

        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"ValidationStreamService initialized (timeout: {session_timeout_minutes}min)")

    def start_cleanup_task(self) -> None:
        """Start background cleanup task for old sessions"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_sessions())
            logger.info("Started session cleanup background task")

    async def _cleanup_old_sessions(self) -> None:
        """Background task to clean up old sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                now = datetime.utcnow()
                expired_sessions = [
                    session_id
                    for session_id, timestamp in self._session_timestamps.items()
                    if now - timestamp > self.session_timeout
                ]

                for session_id in expired_sessions:
                    await self.close_session(session_id)
                    logger.info(f"Cleaned up expired session: {session_id}")

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    def create_session(self, session_id: str) -> None:
        """
        Create a new validation session

        Args:
            session_id: Unique session identifier
        """
        if session_id not in self._session_queues:
            self._session_queues[session_id] = asyncio.Queue()
            self._session_timestamps[session_id] = datetime.utcnow()
            logger.info(f"Created validation session: {session_id}")

    async def emit_event(
        self,
        session_id: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Emit an event to all subscribers of a session

        Args:
            session_id: Session identifier
            event_type: Type of event (e.g., "requirement_updated")
            data: Event payload dictionary
        """
        # Auto-create session if it doesn't exist
        if session_id not in self._session_queues:
            self.create_session(session_id)

        event = ValidationEvent(event_type=event_type, data=data)

        # Update session activity timestamp
        self._session_timestamps[session_id] = datetime.utcnow()

        # Put event in queue
        await self._session_queues[session_id].put(event)

        logger.debug(f"[{session_id}] Emitted event: {event_type}")

    async def stream_events(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Stream events for a session (SSE generator)

        Args:
            session_id: Session identifier

        Yields:
            SSE-formatted event strings
        """
        # Auto-create session if it doesn't exist
        if session_id not in self._session_queues:
            self.create_session(session_id)

        queue = self._session_queues[session_id]

        # Track this subscriber
        current_task = asyncio.current_task()
        if current_task:
            self._session_subscribers[session_id].add(current_task)

        try:
            logger.info(f"[{session_id}] Client connected to validation stream")

            # Send initial connection confirmation
            yield f"event: connected\ndata: {json.dumps({'session_id': session_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            # Stream events from queue
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Send event to client
                    yield event.to_sse_format()

                    # Only close stream on batch_complete or explicit session_close
                    # Don't close on individual validation_complete (batch needs multiple)
                    if event.event_type in ("batch_validation_complete", "session_close"):
                        logger.info(f"[{session_id}] Validation stream ended: {event.event_type}")
                        break

                    # Log but don't close on individual validation events
                    if event.event_type == "validation_complete":
                        logger.debug(f"[{session_id}] Individual validation complete, keeping stream open for batch")

                except asyncio.TimeoutError:
                    # Send keepalive ping every 30 seconds
                    yield f": keepalive\n\n"
                    continue

        except asyncio.CancelledError:
            logger.info(f"[{session_id}] Client disconnected from validation stream")
            raise

        except Exception as e:
            logger.error(f"[{session_id}] Error in validation stream: {e}")
            error_event = ValidationEvent(
                event_type="stream_error",
                data={"error": str(e)}
            )
            yield error_event.to_sse_format()

        finally:
            # Remove subscriber
            if current_task and current_task in self._session_subscribers[session_id]:
                self._session_subscribers[session_id].discard(current_task)

    async def close_session(self, session_id: str) -> None:
        """
        Close a validation session and clean up resources

        Args:
            session_id: Session identifier
        """
        if session_id in self._session_queues:
            # Cancel all subscribers
            if session_id in self._session_subscribers:
                for task in self._session_subscribers[session_id]:
                    task.cancel()
                del self._session_subscribers[session_id]

            # Remove queue and timestamp
            del self._session_queues[session_id]
            if session_id in self._session_timestamps:
                del self._session_timestamps[session_id]

            logger.info(f"Closed validation session: {session_id}")

    def get_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all active sessions

        Returns:
            Dict mapping session_id to session info
        """
        return {
            session_id: {
                "queue_size": queue.qsize(),
                "subscribers": len(self._session_subscribers.get(session_id, set())),
                "last_activity": self._session_timestamps.get(session_id).isoformat()
                if session_id in self._session_timestamps else None
            }
            for session_id, queue in self._session_queues.items()
        }


# Global singleton instance
validation_stream_service = ValidationStreamService()


# ============================================================================
# ORCHESTRATOR INTEGRATION - Helper to create stream callback
# ============================================================================

def create_stream_callback(session_id: str):
    """
    Create a stream callback function for RequirementOrchestrator

    Args:
        session_id: Session identifier

    Returns:
        Async callback function(event_type, data)

    Usage:
        orchestrator = RequirementOrchestrator(
            stream_callback=create_stream_callback(session_id)
        )
    """
    async def callback(event_type: str, data: Dict[str, Any]) -> None:
        await validation_stream_service.emit_event(session_id, event_type, data)

    return callback


# ============================================================================
# FASTAPI INTEGRATION - SSE Response Helper
# ============================================================================

def create_sse_response():
    """
    Create FastAPI StreamingResponse configuration for SSE

    Returns:
        Dict with media_type and headers for SSE

    Usage:
        from fastapi.responses import StreamingResponse

        @router.get("/stream/{session_id}")
        async def stream_validation(session_id: str):
            return StreamingResponse(
                validation_stream_service.stream_events(session_id),
                **create_sse_response()
            )
    """
    return {
        "media_type": "text/event-stream",
        "headers": {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    }
