# Distributed Runtime – Spezifikation (Entwurf)

Status: Draft / Design-Only. Keine produktive Netzwerk- oder Queue-Implementierung in diesem Commit.

Diese Spezifikation beschreibt eine künftige verteilte Laufzeitumgebung (Host ↔ Worker) als Vorbereitung für gRPC/RPC bzw. Message-Queues. Sie dient als Referenz für Schnittstellen, Topics und Privacy-Regeln. Implementierungs-Stubs siehe arch_team/distributed/host_stub.py und arch_team/distributed/worker_stub.py.

## Ziele
- Horizontale Skalierung durch 1..N Worker-Instanzen je Host.
- Lose Kopplung über Themen/Topics und einen klaren Nachrichten-Envelope.
- Rückführbare Ausführung über Trace-Spans (Start/Ende, Parent/Child), kompatibel zu bestehender Telemetrie.
- Klare Privacy-Grenzen: Chain-of-Thought-Inhalte werden nicht über UI-Kanal transportiert.
- Kompatibilität zur In-Process-Runtime (Sequencing, Events) zur schrittweisen Migration.

## Nicht-Ziele
- Heute: keine echte Netzwerk-, Queue- oder Threading-Logik.
- Keine Exactly-Once-Garantie; Ziel ist At-least-once mit Dedup.
- Keine globale Transaktionssemantik über mehrere Worker.

## Architektur-Topologie
- Komponenten:
  - HostRuntime: Orchestrierung, Topic-Router, (später) Anbindung an RPC/Queue.
  - WorkerRuntime: verarbeitet Subset an Topics, meldet Heartbeats, schreibt Antworten/Spans.
- Topologie:
  - 1 Host ↔ N Worker (N ≥ 0), Workers können auf demselben Host oder remote laufen.
  - Kommunikation über Topics/Kanäle: default, planning, solving, verifying, ui, trace.
- Interne Referenzen:
  - Sequenzierung/Events: siehe arch_team/runtime/sequencer.py und arch_team/runtime/SPEC.md.
  - Privacy/CoT-Filterung: siehe arch_team/runtime/cot_postprocessor.py.
  - RAG/Trace-Bezug (Telemetrie/Spans): siehe arch_team/memory/qdrant_trace_sink.py und arch_team/memory/retrieval.py.

## Nachrichtenmodell
Jede Nachricht wird in einem Envelope transportiert:

- id (UUID v4)
- ts (RFC3339-Zeitstempel, UTC)
- topic (string)
- sender (agentId, string)
- sessionId (string)
- payload (JSON-Objekt)
- trace (Objekt: spanId, parentSpanId, baggage)

Beispiel (JSON):

{
  "id": "3fb1f7c4-21b7-4d3e-8a8c-9d2d2b3b9d0e",
  "ts": "2025-08-23T12:00:00Z",
  "topic": "solving",
  "sender": "agent.solver.v1",
  "sessionId": "sess-123",
  "payload": {
    "task": "Resolve requirement gaps",
    "context": {"docId": "R-42"}
  },
  "trace": {
    "spanId": "span-abc",
    "parentSpanId": "span-root",
    "baggage": {"user": "u-1"}
  }
}

Privacy-Hinweis:
- THOUGHTS/EVIDENCE/CRITIQUE/DECISION dürfen niemals über Topic ui gesendet werden; einzig FINAL_ANSWER ist erlaubt (UI-Only-Policy).
- Für inhaltliche Filterung siehe arch_team/runtime/cot_postprocessor.py.

### Dedup/Order
- At-least-once-Lieferung mit Dedup anhand message.id.
- Keine globale Order-Garantie; Sequencing erfolgt logisch in Host/Sequencer.

## Topics/Kanäle und Feldfilter
Vorgesehene Topics:
- default
- planning
- solving
- verifying
- ui
- trace

Allow-/Deny-Listen (payload-Ebene):
- default/planning/solving/verifying:
  - Allow: domain-spezifische Inhalte inkl. THOUGHTS/EVIDENCE/CRITIQUE/DECISION.
  - Deny: PII ohne Redaction.
- ui:
  - Allow: FINAL_ANSWER, strukturierte Metadaten (z. B. confidence, citations).
  - Deny: THOUGHTS, EVIDENCE (rohe Notizen), CRITIQUE, DECISION; Debug-Interna.
- trace:
  - Allow: Trace- bzw. Span-Metadaten (Start/End, Fehler, Tags, Baggage).
  - Deny: fachliche Inhalte; CoT.

Diese Regeln werden in Zukunft vor dem Versand erzwungen (Policy-Enforcer), bereits heute in Docstrings und Spezifikation festgehalten.

## Fehler- und Retry-Strategie
- Semantik: At-least-once.
- Deduplication: Speicherung verarbeiteter message.id je Topic/Session.
- Retry: Exponentielles Backoff mit Jitter.
- Dead-letter: Nach X Fehlversuchen Wandern in Dead-letter-Protokoll samt letzter Fehlermeldung/Stack.
- Idempotenz: Worker-Operationen sollten idempotent entworfen werden (message.id berücksichtigen).

## Sicherheitsaspekte
- Authentifizierung/Autorisierung via Service-Token (mTTL, Rotation).
- PII-Redaction vor Persistenz und Versand (z. B. E-Mail, Tel.-Nr., Personenbezug).
- Transportverschlüsselung: TLS/HTTP2 (gRPC), HTTPS/AMQP – erst bei echter Remote-Anbindung.
- Least-Privilege-Prinzip für Worker-Scope (Topic-basiert).

## Deployment-Skizzen
- Single-Host, Multi-Worker (lokal): HostRuntime + N WorkerRuntime-Prozesse.
- Zukunft: Kubernetes mit gemanagter Queue (z. B. Kafka, NATS, RabbitMQ).
- Konfiguration über Topics/Bindings pro Worker.

## Kompatibilität zur In-Process-Runtime
- Mapping zu arch_team/runtime/SPEC.md (Terminologie, Events).
- Sequencing: HostRuntime integriert mit arch_team/runtime/sequencer.py (künftig über Ereignisse).
- Trace: Persistenz/Suche kompatibel zu arch_team/memory/qdrant_trace_sink.py und arch_team/memory/retrieval.py.

## Beispielsequenz (Planner → Solver → Verifier)
1) planner sendet auf planning: Start-Span, task-beschreibung.
2) solver konsumiert planning, erzeugt solving-Nachrichten, schreibt trace-start/-end.
3) verifier konsumiert solving, prüft Kriterien, emittiert verifying mit Resultat COVERAGE_OK | COVERAGE_FAIL.
4) Bei COVERAGE_OK publiziert HostRuntime auf ui ausschließlich FINAL_ANSWER.
5) Sämtliche Trace-Spans gehen zusätzlich auf trace.

Beispiel-UI-Nachricht (zulässig):

{
  "id": "5e5d9e2e-cf83-4b7b-8d70-1f4f7a2e9f10",
  "ts": "2025-08-23T12:05:00Z",
  "topic": "ui",
  "sender": "host",
  "sessionId": "sess-123",
  "payload": {
    "FINAL_ANSWER": "Die Lücke wurde geschlossen. Siehe Abschnitt 4.",
    "confidence": 0.82,
    "citations": ["R-42", "R-13"]
  },
  "trace": {"spanId": "span-ui", "parentSpanId": "span-root", "baggage": {}}
}

Beispiel-UI-Nachricht (unzulässig – würde verworfen):

{
  "topic": "ui",
  "payload": {
    "THOUGHTS": "...",
    "EVIDENCE": ["rohe Notizen"]
  }
}

## Migration zu gRPC/Queue (Ausblick)
- HostRuntime publish wird an RPC/Queue-Transport gebunden; WorkerRuntime on_message als RPC-Handler/Consumer.
- Envelope bleibt stabil; Policies (Allow/Deny) werden vor Versenden/Anzeige strikt validiert.

## Appendix: Minimaler Envelope-Schemaentwurf (informell)

type Envelope = {
  id: string,              // UUID v4
  ts: string,               // RFC3339 UTC
  topic: "default"|"planning"|"solving"|"verifying"|"ui"|"trace",
  sender: string,           // agentId
  sessionId: string,
  payload: object,          // JSON
  trace?: {
    spanId: string,
    parentSpanId?: string,
    baggage?: object
  }
}