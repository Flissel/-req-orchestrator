# CoT Prompt – Solver

Kurzbeschreibung: Der Solver extrahiert aus Task, Plan und optionalem Retrieval-Kontext eine normalisierte Liste von Anforderungen mit stabilen IDs. Jeder Eintrag enthält eine kurze Beschreibung und einen Tag aus der festen Menge {functional|security|performance|ux|ops}. Bei ausreichender Abdeckung endet die Ausgabe mit COVERAGE_OK.

Quelle: Konzeptionell basierend auf den RAC-Team-Agenten [`arch_team/agents/solver.py`](arch_team/agents/solver.py), [`arch_team/agents/planner.py`](arch_team/agents/planner.py), [`arch_team/agents/verifier.py`](arch_team/agents/verifier.py)
Stand: 2025-08-23 (UTC)

Hinweis Sichtbarkeit:
- Nur FINAL_ANSWER ist UI-sichtbar.
- THOUGHTS und EVIDENCE sind privat und können im Trace gespeichert werden.

Output-Vertrag:
- THOUGHTS: knappe interne Ableitungsschritte (optional, privat)
- EVIDENCE: Belege/Zitate inkl. relativer Pfade; optional, privat
- FINAL_ANSWER: Liste oder Tabelle der REQs mit stabilem Schema:
  - ID: REQ-001, REQ-002, …
  - Description: kurze, präzise Aussage (eine Zeile bevorzugt)
  - Tag: einer aus {functional|security|performance|ux|ops}
  - Optional: Am Ende exakt der Marker COVERAGE_OK, wenn Abdeckung ausreichend ist (z. B. ≥ 5 REQs und Tags gesetzt)

Formatempfehlung (Tabelle):
- Spalten: ID | Description | Tag
- Eine Zeile pro Requirement

Beispiel (Marker-Einbettung):
```
THOUGHTS:
- Prüfe PLAN und MEMORY auf dedizierte Ziele, Risiken, Randbedingungen.
- Dedupliziere und normalisiere in kurze REQs mit Tags.

EVIDENCE:
- docs/backend/CONFIG.md: "Upload-Limits"
- frontend/styles.css: "Thematische Konsistenzhinweise"

FINAL_ANSWER:
ID       | Description                                                          | Tag
REQ-001  | The system shall allow CSV upload up to 10MB with schema validation. | functional
REQ-002  | Audit logs must record upload attempts incl. user and timestamp.     | security
REQ-003  | Average validation response shall be < 500ms for 95th percentile.  | performance
REQ-004  | Show clear, actionable error messages for invalid CSV schema.        | ux
REQ-005  | Provide ops dashboard for ingestion status and retries.              | ops
COVERAGE_OK