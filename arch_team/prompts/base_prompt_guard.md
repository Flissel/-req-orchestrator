# Base Prompt Guard

Baseline-Regelwerk für alle Agenten im RAC-Team. Text semantisch unverändert aus den aktuellen Agenten-Konstanten übernommen. Dient als zentrales Guardrail-Dokument für Ausgabeformat und REQ-Kennzeichnung.

Quelle: [`arch_team/agents/planner.py`](arch_team/agents/planner.py), [`arch_team/agents/solver.py`](arch_team/agents/solver.py), [`arch_team/agents/verifier.py`](arch_team/agents/verifier.py)
Stand: 2025-08-23 (UTC)

Inhalt (unverändert):

General rules for all agents:
- Keep outputs concise and structured. Prefer bullet points and fenced code blocks for Mermaid.
- Requirements MUST be labeled REQ-### (e.g., REQ-001) to enable traceability.
- When you mention a requirement in any diagram/section, include the REQ ID in a node label, note, or comment.
- Do not invent tools or APIs; stick to widely used patterns.
- Never remove existing REQ IDs; only add or refine.