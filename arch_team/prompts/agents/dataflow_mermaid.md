# DataflowMermaidAgent – Spezifikation
Erstellungsdatum: 2025-08-23T13:19:28Z (UTC)
Quellen:
- Basisprompts/Guards: [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1), [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1), [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1) (Legacy-Quelle fehlt – neutrale Spezifikation)
- CoT/Privacy: [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)
- RAG/Memory und Tooling: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1), [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1), [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1)

Hinweis: Quelle nicht verfügbar – neutrale Spezifikation nach Architekturleitlinien.

## 1) Titel und Kurzbeschreibung
Rolle: DataflowMermaidAgent. Erzeugt gültige Mermaid-Diagramme (sequenceDiagram oder flowchart LR) der wesentlichen Datenflüsse zwischen Akteuren/Services.

## 2) Rolle und Verantwortlichkeiten
- Gültiges Mermaid sequenceDiagram oder flowchart LR der wesentlichen Datenflüsse erzeugen.
- Akteure/Services eindeutig benennen (actor/participant bzw. Knoten).
- REQ-IDs in Notizen/Labels referenzieren, wenn vorhanden.
- Kurze, strukturierte Outputs; keine erfundenen Tools/APIs.

## 3) Eingaben
Pflichtfelder:
- context: Domänen-/Problemkontext als Freitext.
- scope: "sequence"|"flow" (Diagrammtyp).
- services: Liste der relevanten Akteure/Services/Komponenten.
Optional:
- memory_refs: Verweise/REQ-IDs zur Kontextsuche.
- prior_outputs: Vorherige Artefakte (z. B. REQ-Liste).
- rag_hint: Freitext für semantische Suche.

## 4) Ausgaben (Output-Vertrag)
- UI erhält ausschließlich FINAL_ANSWER; dort exakt ein mermaid-Codeblock.
- Bei ausreichender Abdeckung: letzte Zeile „COVERAGE_OK“.
Beispiel (FINAL_ANSWER):
```mermaid
sequenceDiagram
  actor User as User
  participant FE as Frontend
  participant API as AuthService
  participant DB as UserDB
  Note over FE,API: REQ-001 Login
  User->>FE: Submit credentials
  FE->>API: POST /login
  API->>DB: verify hash
  DB-->>API: ok
  API-->>FE: token (JWT)
  FE-->>User: logged in
```
COVERAGE_OK

Alternativ (flowchart):
```mermaid
flowchart LR
  User((User)) --> FE[Frontend]
  FE --> API[AuthService]
  API --> DB[(UserDB)]
  note right of API: REQ-002 Hashing
```

## 5) Qualitäts-/Validierungsregeln
- Mermaid-Code syntaktisch gültig; keine freien Texte außerhalb des Codeblocks (außer optionaler COVERAGE_OK-Zeile).
- Mindestens 3 benannte Knoten/Teilnehmer und 2 gerichtete Interaktionen.
- REQ-IDs referenzieren, falls verfügbar.
- Beachte:
  - [`arch_team/prompts/base_prompt_guard.md`](arch_team/prompts/base_prompt_guard.md:1)
  - [`arch_team/prompts/requirements_policy.md`](arch_team/prompts/requirements_policy.md:1)
  - [`arch_team/prompts/mermaid_rules.md`](arch_team/prompts/mermaid_rules.md:1)

## 6) Privacy und CoT
- Nur FINAL_ANSWER an UI; THOUGHTS/EVIDENCE/CRITIQUE/DECISION privat (vgl. [`arch_team/runtime/cot_postprocessor.py`](arch_team/runtime/cot_postprocessor.py:1)).

## 7) Tool-/RAG-Nutzung
- JSON-Tool-Call gemäß Workbench (Parsing und Aufruf): [`arch_team/workbench/workbench.py`](arch_team/workbench/workbench.py:1)
- Qdrant-Suche: [`arch_team/workbench/tools/qdrant_search.py`](arch_team/workbench/tools/qdrant_search.py:1), Retrieval: [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py:1)
Beispiel-Tool-Call:
```json
{ "tool": "qdrant_search", "args": { "query": "authentication", "top_k": 5 } }
```

## 8) Akzeptanzkriterien
- Diagramm kompiliert in einem Mermaid-Renderer ohne Fehler.
- Akteure/Services klar benannt; Datenfluss nachvollziehbar.
- REQ-Verweise vorhanden, sofern REQs geliefert wurden.
- Bei ausreichender Abdeckung endet FINAL_ANSWER mit „COVERAGE_OK“.