# Backend-Dokumentation

Ziel: Backend für Requirements-Validierung mit LLM-Integration auf Basis FastAPI, OpenAI API und SQLite. Keine Speicherung sensibler Klartextinhalte, nur Metadaten und Ergebnisse.

Architekturvorgaben
- LLM: OpenAI API mit Mock-Fallback
- Datenbank: SQLite (Prototyp)
- Authentifizierung: keine, Single User
- Deployment: Docker, Docker Compose
- Datenschutz: keine Klartextspeicherung, Purge-Job bei Start
- Nichtfunktionale Anforderungen: 30 rpm, p95 ≤ 2000 ms

Struktur
- Paket: backend/core/
  - settings.py: Env-Variablen und Defaults
  - db.py: SQLite DDL, Init, Queries
  - utils.py: Hash, Parser, Scoring
  - llm.py: OpenAI-Adapter + Mock
  - api.py: Basis-API Endpunkte
  - batch.py: Batch-API Endpunkte
- Entry: backend/main.py (FastAPI)
- Beispiel-Input: docs/requirements.md (Markdown-Tabelle)

Konfiguration (Auszug)
- OPENAI_API_KEY, OPENAI_MODEL
- MOCK_MODE=true|false
- SQLITE_PATH, PURGE_RETENTION_H
- BATCH_SIZE, MAX_PARALLEL
- REQUIREMENTS_MD_PATH (Standard: ./docs/requirements.md)

Basis-API
- GET /health
- GET /api/v1/criteria
- POST /api/v1/evaluations
  Request Beispiel
  ```json
  {
    "requirementText": "Das System muss innerhalb von 2 Sekunden auf Suchanfragen reagieren.",
    "context": {"domain":"search","language":"de"},
    "criteriaKeys": ["clarity","testability","measurability"]
  }
  ```

Batch-API
- POST /api/v1/batch/evaluate
  - Liest Markdown unter REQUIREMENTS_MD_PATH
  - Bewertet je Zeile (id, requirementText, context)
  - Persistiert Evaluationen
  - Response: items je id, mergedMarkdown mit Spalten evaluationScore, verdict
- POST /api/v1/batch/suggest
  - Erzeugt Suggestions je Requirement
  - Schreibt Suggestions sequenziell in DB
  - Response: items je id, mergedMarkdown mit suggestions
- POST /api/v1/batch/rewrite
  - Erzeugt redefinedRequirement je Requirement
  - Schreibt sequenziell in DB 
  - Response: items je id, mergedMarkdown mit redefinedRequirement

Markdown-Inputformat
Datei: docs/requirements.md
```
| id | requirementText | context |
|----|------------------|---------|
| R1 | Das System muss innerhalb von 2 Sekunden auf Suchanfragen reagieren. | {"language":"de","domain":"search"} |
| R2 | Benutzer sollen sich mit E-Mail und Passwort anmelden können. | {"language":"de","domain":"auth"} |
```
- context: JSON bevorzugt; Freitext wird als note abgelegt

Datenbankmodell (zusätzlich)
- Tabellen: criterion, evaluation, evaluation_detail, suggestion, rewritten_requirement
- Klartext der Requirements wird nicht gespeichert, Identifikation via SHA-256 checksum

Sicherheit und Betrieb
- Keine Klartextlogs, nur IDs und Latenzen
- Secrets über Umgebungsvariablen
- Purge alter Daten via PURGE_RETENTION_H

Deployment Kurzleitfaden
- Dockerfile nutzt uvicorn backend.main:fastapi_app
- docker-compose bindet
  - ./docs nach /app/docs:ro (Markdown-Input)
  - ./data nach /data (SQLite persist)
- Start:
  - docker compose up -d
  - Health: http://localhost:5000/health

Akzeptanzkriterien
- p95 Latenz ≤ 2000 ms bei 30 rpm
- Keine Klartextspeicherung
- API stabil und versioniert
- Diagramme und DDL vorhanden

---

## v2 LangExtract – Extraction & Requirements-Erstellung

Endpoints (Auszug)
- POST `/api/v1/lx/extract` – Mining aus Dateien mit Chunking/Guided/Fast Mode
- GET/POST `/api/v1/lx/config/*` – Konfiguration (Prompt+Examples)
- GET/POST `/api/v1/lx/gold/*` – Gold-Management und Auto‑Gold
- POST `/api/v1/lx/evaluate` | POST `/api/v1/lx/evaluate/auto`

Parameter bei Extract
- `chunkMode`: token|paragraph, `chunkMin`, `chunkMax`, `chunkOverlap`
- `neighbor_refs=1` für ±1 Nachbarschaft in Evidence
- `fast=1` für Einzel-Lauf ohne Self‑Consistency/Repair
- `temperature` 0.0..1.0 (insb. in Fast Mode)
- `configId` (Prompt/Beispiele), `goldId`, `useGoldAsFewshot=1`, `autoGold=1`

Ablauf (vereinfacht)
1) Chunks erzeugen (Token‑ oder Paragraph‑basiert, Overlap). Optional: Evidence mit Nachbarn verlinken.
2) LLM-Aufrufe:
   - Fast Mode: 1 Lauf mit `temperature` (Default 0.2)
   - Normal Mode: Self‑Consistency über `temps=[0.0,0.2,0.6,0.8,0.9]`, optional Repair‑Pass
3) Constrain/Validate: erlaubte Klassen, robuste Alignment-Felder, JSON‑sichere Normalisierung
4) Dedupe/Merge: exakte Duplikate (id/text) entfernen, Near‑Dup via Jaccard/Contain/Char‑Ratio; Confidence aus Votes
5) Guided Mining (optional): Gold‑Items als Few‑Shot mischen, fehlendes Gold automatisch generieren
6) Rückgabe `lxPreview` inkl. `char_interval` und Quellen‑Metadaten

Evaluation
- Robust Similarity=max(Jaccard, Token‑Containment, Char‑Ratio, optional Embeddings‑Cosine)
- Threshold steuerbar; Reports via `frontend/reports.html`