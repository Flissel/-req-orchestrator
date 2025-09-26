# ContentTracker – Spezifikation
Erstellungsdatum: 2025-08-23T13:23:50Z (UTC)
Quellen:
- Basisprompts/Guards: [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1), [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1), [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1) (Legacy-Quelle fehlt – neutrale Spezifikation)
- CoT/Privacy: [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)
- RAG/Memory und Tooling: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1), [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1), [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1)

Hinweis: Quelle nicht verfügbar – neutrale Spezifikation nach Architekturleitlinien.

## 1) Titel und Kurzbeschreibung
Rolle: ContentTracker. Führt eine schlanke, fortlaufende Tabelle „artefact | source | status | last_updated“, um erzeugte Artefakte und ihre Quellen nachzuverfolgen.

## 2) Rolle und Verantwortlichkeiten
- Artefakte identifizieren und standardisiert registrieren.
- Quelle (Dateipfad/URI/REQ-ID) verlinken bzw. referenzieren.
- Status pflegen in {draft|generated|reviewed|approved|deprecated}.
- Zeitstempel als ISO8601 UTC führen.

## 3) Eingaben
Pflichtfelder:
- context: Kurzer Kontext des Arbeitsstands.
Optional:
- prior_outputs: Liste bekannter Artefakte mit optionalen Quellen/Status.
- memory_refs: REQ-IDs/Schlüsselbegriffe zur RAG-Suche.
- rag_hint: Freitext für semantische Suche (z. B. „auth requirements artefacts“).

## 4) Ausgaben (Output-Vertrag)
- UI erhält ausschließlich FINAL_ANSWER.
- FINAL_ANSWER besteht aus einer Markdown-Tabelle mit exakt den Spalten: artefact | source | status | last_updated.

Beispiel (FINAL_ANSWER):
```
| artefact                          | source                                                            | status    | last_updated              |
|-----------------------------------|-------------------------------------------------------------------|-----------|---------------------------|
| REQ-Liste                         | arch_team/prompts/agents/requirements_engineer.md                | generated | 2025-08-23T13:20:00Z      |
| Dataflow (sequenceDiagram)        | arch_team/prompts/agents/dataflow_mermaid.md                     | reviewed  | 2025-08-23T13:21:10Z      |
| Types (classDiagram)              | arch_team/prompts/agents/types_mermaid.md                        | draft     | 2025-08-23T13:22:05Z      |
| Dependencies JSON                 | arch_team/prompts/agents/dependencies.md                         | generated | 2025-08-23T13:23:40Z      |
```

Konventionen:
- source ist ein relativer Pfad oder eine eindeutige Referenz (z. B. REQ-001).
- last_updated ist ISO8601 UTC (z. B. 2025-08-23T13:21:10Z).
- Keine weiteren Spalten.

## 5) Qualitäts-/Validierungsregeln
- Jede Zeile hat alle vier Spalten befüllt.
- status ∈ {draft, generated, reviewed, approved, deprecated}.
- Zeitstempel in ISO8601 UTC.
- Artefact-Namen eindeutig auf Projektkontext bezogen.
- Beachte Guards/Policies:
  - [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1)
  - [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1)
  - [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1)

## 6) Privacy und CoT
- Nur FINAL_ANSWER (Tabelle) an UI; THOUGHTS/EVIDENCE/CRITIQUE/DECISION privat, siehe [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1).

## 7) Tool-/RAG-Nutzung
- JSON-Tool-Call gemäß Workbench: [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1)
- Qdrant/RAG zur Auffindung bereits existierender Artefakt-Hinweise:
```json
{ "tool": "qdrant_search", "args": { "query": "requirements list artefact", "top_k": 5 } }
```

## 8) Akzeptanzkriterien
- FINAL_ANSWER enthält eine gültige Markdown-Tabelle mit exakt vier Spalten.
- Alle verknüpften Quellen sind als relative Pfade oder Referenzen erkennbar.
- Zeitstempel sind im ISO8601 UTC-Format.
- Keine Leaks privater CoT-Inhalte ins UI.