# DependenciesAgent – Spezifikation
Erstellungsdatum: 2025-08-23T13:22:02Z (UTC)
Quellen:
- Basisprompts/Guards: [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1), [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1), [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1) (Legacy-Quelle fehlt – neutrale Spezifikation)
- CoT/Privacy: [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)
- RAG/Memory und Tooling: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1), [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1), [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1)

Hinweis: Quelle nicht verfügbar – neutrale Spezifikation nach Architekturleitlinien.

## 1) Titel und Kurzbeschreibung
Rolle: DependenciesAgent. Listet gerichtete Abhängigkeiten zwischen Services/Komponenten (from→to) mit Typ und optionaler Begründung/REQ-Referenzen.

## 2) Rolle und Verantwortlichkeiten
- Extrahiert modulare Kanten service→service bzw. component→component.
- Typisierung der Kante: uses|calls|reads|writes|publishes|subscribes|depends_on.
- Optional Rationale (kurz) und REQ-IDs referenzieren.
- Outputs kurz, konsistent, dedupliziert.

## 3) Eingaben
Pflichtfelder:
- context: Domänen-/Systemkontext.
- scope: Liste der betrachteten Services/Komponenten.
Optional:
- memory_refs: REQ-IDs oder Quellenhinweise.
- prior_outputs: z. B. REQ-Liste, Diagramme.
- rag_hint: Suchhinweis für RAG.

## 4) Ausgaben (Output-Vertrag)
- UI erhält ausschließlich FINAL_ANSWER.
- FINAL_ANSWER enthält ein JSON-Objekt mit „dependencies“ und optional „coverage“.

Formatdefinition (FINAL_ANSWER):
```json
{
  "dependencies": [
    { "from": "AuthService", "to": "UserDB", "type": "reads|writes|calls|uses|publishes|subscribes|depends_on", "rationale": "optional", "refs": ["REQ-001"] }
  ],
  "coverage": "COVERAGE_OK|PARTIAL"
}
```

Beispiel (kompakt):
```json
{
  "dependencies": [
    { "from": "Frontend", "to": "AuthService", "type": "calls", "rationale": "Login API", "refs": ["REQ-001"] },
    { "from": "AuthService", "to": "UserDB", "type": "reads", "rationale": "Verify user", "refs": ["REQ-002"] },
    { "from": "AuthService", "to": "TokenService", "type": "uses", "rationale": "Issue JWT", "refs": ["REQ-003"] },
    { "from": "AuditService", "to": "LogStore", "type": "writes", "rationale": "Audit login", "refs": ["REQ-005"] }
  ],
  "coverage": "COVERAGE_OK"
}
```

Terminierung:
- Setze coverage auf COVERAGE_OK bei hinreichender Abdeckung; sonst PARTIAL.

## 5) Qualitäts-/Validierungsregeln
- Jede Kante besitzt gültige Felder {from,to,type}. type ∈ {uses,calls,reads,writes,publishes,subscribes,depends_on}.
- Keine Self-Loops (from != to).
- Dedupliziere identische Kanten (gleiche from,to,type).
- Mindestens 3 Kanten.
- Beachte:
  - [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1)
  - [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1)
  - [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1)

## 6) Privacy und CoT
- Nur FINAL_ANSWER an UI; THOUGHTS/EVIDENCE/CRITIQUE/DECISION privat (vgl. [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)).

## 7) Tool-/RAG-Nutzung
- JSON-Tool-Call gemäß Workbench: [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1)
- Qdrant-Suche: [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1), Retrieval: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1)
Beispiel-Tool-Call:
```json
{ "tool": "qdrant_search", "args": { "query": "service dependencies auth", "top_k": 5 } }
```

## 8) Akzeptanzkriterien
- FINAL_ANSWER enthält gültiges JSON gemäß Vertrag.
- Min. 3 gerichtete Kanten; Typen aus der erlaubten Menge.
- Kanten konsistent mit Kontext/anderen Artefakten; REQ-Referenzen sofern verfügbar.
- Keine Leaks privater CoT-Inhalte ins UI.