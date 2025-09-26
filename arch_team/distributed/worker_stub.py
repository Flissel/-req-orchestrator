from __future__ import annotations

"""
Distributed Worker Runtime – Design Stubs.

Zweck:
  - Minimalistische Schnittstellen für eine künftige Worker-Laufzeit, die Nachrichten
    aus bestimmten Topics verarbeitet. Keine Netzwerk-/Queue-Implementierung.

Privacy:
  - Niemals THOUGHTS/EVIDENCE/CRITIQUE/DECISION an Topic "ui" senden.
  - Rückkanal-Policy: Nur FINAL_ANSWER an "ui"; Trace-/Span-Metadaten an "trace".
  - Siehe arch_team/runtime/cot_postprocessor.py für Chain-of-Thought-Filterung.

Hinweis:
  - Diese Datei ist rein für Design/Import vorgesehen; keine echten Nebenwirkungen.
"""

from typing import Any, Dict, List, Set
from datetime import datetime, timezone


def _rfc3339_now() -> str:
    """Gibt die aktuelle UTC-Zeit als RFC3339-String zurück."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class WorkerRuntime:
    """Worker-Laufzeit-Stub für Topic-basierte Verarbeitung.

    Diese Klasse verwaltet nur die Subskriptionen und stellt Hook-Methoden bereit.
    Es erfolgt keine echte Netzwerk-, Queue- oder Thread-Verarbeitung.

    Privacy- und Policy-Hinweise:
      - THOUGHTS/EVIDENCE/CRITIQUE/DECISION niemals an Topic "ui" publizieren.
      - Rückkanal: Nur FINAL_ANSWER an "ui"; Trace-/Span-Daten an "trace".
        (Die Durchsetzung liegt in der Zukunft in Host/Transport-Policy.)
    """

    def __init__(self, worker_id: str, *, subscribed_topics: List[str]) -> None:
        """Erzeugt eine WorkerRuntime-Instanz.

        Args:
            worker_id: Logische Worker-ID.
            subscribed_topics: Anfangsmenge der abonnierten Topics (z. B. ["planning"]).
        """
        self.worker_id: str = worker_id
        self._topics: Set[str] = set(subscribed_topics)
        self._last_heartbeat_ts: str = _rfc3339_now()
        # print(f"[WorkerRuntime] init worker_id={worker_id} topics={sorted(self._topics)}")  # deaktiviert

    def on_message(self, topic: str, envelope: Dict[str, Any]) -> None:
        """Hook zur Verarbeitung einer eingehenden Nachricht.

        Design-Stub: Keine Implementierung. Diese Methode wird später in
        konkreten Workern (Planner/Solver/Verifier) überschrieben oder
        hier mit konkreter Logik gefüllt.

        Args:
            topic: Topic der eingehenden Nachricht.
            envelope: Nachrichten-Envelope mit Feldern wie:
                id, ts, topic, sender, sessionId, payload, trace.

        Returns:
            None

        Raises:
            NotImplementedError: Der Stub führt keine Verarbeitung durch.
        """
        # print(f"[WorkerRuntime] on_message topic={topic} id={envelope.get('id')}")  # deaktiviert
        raise NotImplementedError("Design-Stub: on_message ist nicht implementiert.")

    def subscribe(self, topic: str) -> None:
        """Abonniert ein Topic für diesen Worker (No-op bzgl. Netzwerk)."""
        self._topics.add(topic)
        # print(f"[WorkerRuntime] subscribe topic={topic}")  # deaktiviert

    def unsubscribe(self, topic: str) -> None:
        """Kündigt die Subskription eines Topics (No-op bzgl. Netzwerk)."""
        self._topics.discard(topic)
        # print(f"[WorkerRuntime] unsubscribe topic={topic}")  # deaktiviert

    def heartbeat(self) -> Dict[str, Any]:
        """Erzeugt ein Heartbeat-Objekt für Monitoring/Health-Checks.

        Returns:
            dict: Minimaler Heartbeat mit workerId, ts und topics.
        """
        self._last_heartbeat_ts = _rfc3339_now()
        hb = {
            "workerId": self.worker_id,
            "ts": self._last_heartbeat_ts,
            "topics": sorted(self._topics),
            "status": "OK",
        }
        # print(f"[WorkerRuntime] heartbeat {hb}")  # deaktiviert
        return hb


if __name__ == "__main__":
    # Minimaler Demonstrationsblock (ohne Netzwerk, nur Prints), damit die API-Ausrichtung klar ist.
    w = WorkerRuntime("worker.demo", subscribed_topics=["planning", "solving"])
    print("Heartbeat (initial):", w.heartbeat())

    print("Subscribe: verifying")
    w.subscribe("verifying")
    print("Heartbeat (after subscribe):", w.heartbeat())

    print("Unsubscribe: planning")
    w.unsubscribe("planning")
    print("Heartbeat (after unsubscribe):", w.heartbeat())

    # on_message ist ein Design-Stub und wirft NotImplementedError:
    try:
        demo_envelope = {
            "id": "demo-id",
            "ts": _rfc3339_now(),
            "topic": "solving",
            "sender": "agent.solver.v1",
            "sessionId": "sess-demo",
            "payload": {"demo": True},
            "trace": {"spanId": "span-demo"},
        }
        w.on_message("solving", demo_envelope)
    except NotImplementedError as e:
        print("on_message() NotImplementedError (expected in stub):", str(e))

    # Privacy-Reminder (nur als Demo-Output; keine Durchsetzung hier):
    print(
        "Privacy-Hinweis: Niemals THOUGHTS/EVIDENCE/CRITIQUE/DECISION an 'ui' senden. "
        "Nur FINAL_ANSWER an 'ui'; Trace/Spans an 'trace'."
    )