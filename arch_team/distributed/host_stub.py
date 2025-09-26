from __future__ import annotations

"""
Distributed Host Runtime – Design Stubs.

Zweck:
  - Schnittstellen und Envelope-Formate für eine künftige verteilte Runtime (Host ↔ Worker).
  - Keine echten Netzwerk-/Queue-Implementierungen; reine No-ops/Platzhalter.

Privacy:
  - Niemals THOUGHTS/EVIDENCE/CRITIQUE/DECISION über Topic "ui" transportieren.
  - Siehe arch_team/runtime/cot_postprocessor.py für Chain-of-Thought-Filterung.
"""

from typing import Any, Dict, List, Set
import uuid
from datetime import datetime, timezone

DISALLOWED_UI_FIELDS: Set[str] = {"THOUGHTS", "EVIDENCE", "CRITIQUE", "DECISION"}


def _rfc3339_now() -> str:
    """Return current UTC timestamp in RFC3339 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class InMemoryQueue:
    """Kleine, nicht-threadsafe In-Memory-Queue ausschließlich für Spezifikationszwecke.

    Diese Klasse ist kein Produktionscode. Sie existiert nur, um das
    Nachrichtenmodell in Tests/Skizzen zu veranschaulichen. Keine Persistenz,
    kein Netzwerk, keine Nebenwirkungen außerhalb des Prozesses.
    """

    def __init__(self) -> None:
        self._topics: Dict[str, List[Dict[str, Any]]] = {}
        # print("[InMemoryQueue] init")  # deaktiviertes Logging

    def publish(self, topic: str, envelope: Dict[str, Any]) -> None:
        """Lege die Nachricht lokal im Topic-Puffer ab (No-op-ähnlich)."""
        self._topics.setdefault(topic, []).append(envelope)
        # print(f"[InMemoryQueue] publish topic={topic} id={envelope.get('id')}")  # deaktiviert

    def consume(self, topic: str) -> List[Dict[str, Any]]:
        """Gib und lösche alle Nachrichten eines Topics (nur Demo)."""
        return self._topics.pop(topic, [])


class HostRuntime:
    """Host-Orchestrator für eine künftige verteilte Runtime.

    Diese Klasse definiert die minimale API, ohne echte Remote-I/O. Sie kann
    später an gRPC/HTTP/AMQP gebunden werden, behält dabei aber den Envelope
    stabil bei.

    Wichtige Privacy-Regel:
      - Über Topic "ui" sind ausschließlich FINAL_ANSWER und harmlose Metadaten
        erlaubt; niemals THOUGHTS/EVIDENCE/CRITIQUE/DECISION.
    """

    def __init__(self, *, default_topic: str = "default") -> None:
        """Initialisiere HostRuntime.

        Args:
            default_topic: Fallback-Topic, falls beim Publish kein Topic angegeben ist.
        """
        self._default_topic = default_topic
        self._workers: Dict[str, Set[str]] = {}
        # Interne Demo-Queue; nicht als Produktions-Transport verwenden.
        self._queue = InMemoryQueue()
        # print(f"[HostRuntime] init default_topic={default_topic}")  # deaktiviert

    def register_worker(self, worker_id: str, topics: List[str]) -> None:
        """Registriere einen Worker und seine abonnierten Topics.

        Args:
            worker_id: Logische Worker-ID.
            topics: Liste unterstützter Topics (z. B. ["planning", "solving"]).
        """
        self._workers[worker_id] = set(topics)
        # print(f"[HostRuntime] register_worker id={worker_id} topics={topics}")  # deaktiviert

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        session_id: str,
        sender: str,
        trace: Dict[str, Any] | None = None,
    ) -> str:
        """Publiziere eine Nachricht (No-op bzgl. Netzwerk), erzeuge Envelope.

        Diese Methode erzeugt lediglich einen Envelope und merkt ihn optional in
        einer InMemoryQueue vor. Kein Netzwerk, keine Threads.

        Privacy:
            - Für topic == "ui" werden THOUGHTS/EVIDENCE/CRITIQUE/DECISION abgewiesen.

        Args:
            topic: Ziel-Topic.
            payload: JSON-kompatibler Inhalt.
            session_id: Sitzungsbezug.
            sender: Sender-Identität (agentId).
            trace: Trace-Metadaten (spanId, parentSpanId, baggage).

        Returns:
            str: Generierte message.id (UUID v4).

        Raises:
            ValueError: Bei Verletzung der UI-Only-Policy.
        """
        if topic == "ui":
            bad = DISALLOWED_UI_FIELDS.intersection(payload.keys())
            if bad:
                raise ValueError(
                    f"UI-Only-Policy verletzt; unzulässige Felder in payload: {sorted(bad)}. "
                    "Siehe arch_team/runtime/cot_postprocessor.py"
                )

        message_id = str(uuid.uuid4())
        envelope: Dict[str, Any] = {
            "id": message_id,
            "ts": _rfc3339_now(),
            "topic": topic or self._default_topic,
            "sender": sender,
            "sessionId": session_id,
            "payload": payload,
            "trace": trace or {},
        }
        # No-op-Transport: nur lokal vormerken, keine I/O
        self._queue.publish(envelope["topic"], envelope)
        # print(f"[HostRuntime] publish topic={topic} id={message_id}")  # deaktiviert
        return message_id

    def shutdown(self) -> None:
        """Fahre die HostRuntime logisch herunter (No-op).

        Räumt interne Strukturen auf. Keine Netzwerk- oder Prozess-Steuerung.
        """
        self._workers.clear()
        # Topics leeren (rein lokal).
        for t in list(self._queue._topics.keys()):
            self._queue.consume(t)
        # print("[HostRuntime] shutdown")  # deaktiviert


__all__ = ["HostRuntime", "InMemoryQueue", "DISALLOWED_UI_FIELDS"]