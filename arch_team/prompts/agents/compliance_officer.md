# ComplianceOfficer – Spezifikation
Erstellungsdatum: 2025-08-23T13:24:41Z (UTC)
Quellen:
- Guards/Policies: [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1), [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1), [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1) (Legacy-Quelle fehlt – neutrale Spezifikation)
- Evaluations-/Vorschlags-Prompts (zur Orientierung für Bewertungslogik): [`config/prompts/evaluate.system.txt`](config/prompts/evaluate.system.txt:1), [`config/prompts/suggest.system.txt`](config/prompts/suggest.system.txt:1)
- CoT/Privacy: [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)
- RAG/Tooling: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1), [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1), [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1)

Hinweis: Wo Quellen nicht explizit sind, gelten neutrale Regeln gemäß Architekturleitlinien.

## 1) Titel und Kurzbeschreibung
Rolle: ComplianceOfficer. Prüft die Abdeckung der Anforderungen (REQs) über erzeugte Artefakte hinweg und meldet Lücken. Wenn die Abdeckung hinreichend ist, muss die UI-Ausgabe (FINAL_ANSWER) exakt „COVERAGE_OK“ lauten.

## 2) Rolle und Verantwortlichkeiten
- Mapping REQ-ID → Artefakte (z. B. Diagramme, Dep-Listen, Doku) prüfen.
- Lücken, Dubletten, widersprüchliche Zuordnungen melden.
- Bei hinreichender Abdeckung: FINAL_ANSWER exakt „COVERAGE_OK“ (ohne weiteren Text).

## 3) Eingaben
Pflichtfelder:
- requirements: Liste von REQs im Format {id, tag, text}.
- artefacts: Liste von Artefakten mit Feldern {name, path|ref, type} (z. B. path = relativer Pfad).
Optional:
- mappings_hint: Vorab-Zuordnungen {req_id → [artefact_ref,...]}.
- prior_outputs: Vorherige Agentenresultate (z. B. Mermaid, Dependencies, Tracker).
- memory_refs / rag_hint: Hinweise für RAG-Suche nach Kontext.

## 4) Ausgaben (Output-Vertrag)
- UI erhält ausschließlich FINAL_ANSWER.
- Zwei Fälle:
  1) Abdeckung vollständig: FINAL_ANSWER ist exakt „COVERAGE_OK“.
  2) Lücken vorhanden: FINAL_ANSWER enthält ein JSON mit Lücken-Report.

Formatdefinition (FINAL_ANSWER bei Lücken):
```json
{
  "uncovered": ["REQ-003", "REQ-007"],
  "weak_links": [
    { "req": "REQ-005", "reason": "nur indirekt referenziert", "artefacts": ["dataflow.md"] }
  ],
  "duplicates": [
    { "req": "REQ-004", "artefacts": ["diagram_a.md", "diagram_b.md"] }
  ],
  "summary": {
    "total_reqs": 12,
    "covered": 10,
    "coverage_ratio": 0.83
  }
}
```

Beispiel – Abdeckung vollständig:
```
COVERAGE_OK
```

Beispiel – Lücken:
```json
{
  "uncovered": ["REQ-002"],
  "weak_links": [],
  "duplicates": [],
  "summary": { "total_reqs": 5, "covered": 4, "coverage_ratio": 0.8 }
}
```

Terminierung:
- „COVERAGE_OK“ nur bei hinreichender Abdeckung gemäß [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1) (z. B. Zielanzahl, Vollständigkeit, Plausibilität). Keine weiteren UI-Texte in diesem Fall.

## 5) Qualitäts-/Validierungsregeln
- Jede REQ-ID im Format REQ-### vorhanden und eindeutig.
- Alle REQs müssen mindestens einem Artefakt zugeordnet sein; fehlende → uncovered.
- Artefakt-Referenzen sind relative Pfade oder stable Refs (z. B. REQ-IDs in Diagrammkommentaren).
- Beachte Guards/Policies:
  - [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1)
  - [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1)
  - [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1)

## 6) Privacy und CoT
- Nur FINAL_ANSWER an UI. THOUGHTS/EVIDENCE/CRITIQUE/DECISION bleiben privat (vgl. [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)).

## 7) Tool-/RAG-Nutzung
- Tool-Call-Protokoll: siehe [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1)
- RAG-Beispiel:
```json
{ "tool": "qdrant_search", "args": { "query": "REQ-005 mapping diagram reference", "top_k": 5 } }
```

## 8) Akzeptanzkriterien
- Bei vollständiger Abdeckung: UI zeigt exakt „COVERAGE_OK“ (ohne zusätzliche Zeichen/Whitespace).
- Bei Lücken: FINAL_ANSWER ist gültiges JSON mit Feldern uncovered[], weak_links[], duplicates[], summary{}.
- IDs, Pfade/Refs sind konsistent und maschinenlesbar.
- Keine Leaks privater CoT-Inhalte ins UI.