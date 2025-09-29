# Deployment Leitfaden

Dieses Dokument beschreibt Build, Konfiguration und Betrieb des Backends in der modularisierten Struktur.

Struktur-Überblick
- Paket: [backend_app](../backend_app/__init__.py)
  - [backend_app/settings.py](../backend_app/settings.py)
  - [backend_app/db.py](../backend_app/db.py)
  - [backend_app/utils.py](../backend_app/utils.py)
  - [backend_app/llm.py](../backend_app/llm.py)
  - [backend_app/api.py](../backend_app/api.py)
  - [backend_app/batch.py](../backend_app/batch.py)
- WSGI Entry: [wsgi.py](../wsgi.py)
- Beispiel-Input: [docs/requirements.md](../docs/requirements.md)
- Compose: [docker-compose.yml](../docker-compose.yml)
- Dockerfile: [Dockerfile](../Dockerfile)
- Env Vorlage: [.env.example](../.env.example)

Konfiguration über Env Variablen
- API_HOST, API_PORT
- OPENAI_API_KEY, OPENAI_MODEL (z B gpt-4o-mini)
- MOCK_MODE=true|false (true = Heuristik, keine externen LLM-Calls)
- SQLITE_PATH (Compose setzt /data/app.db)
- PURGE_RETENTION_H (Stunden bis Purge)
- BATCH_SIZE, MAX_PARALLEL (Steuerung für parallele LLM-Calls)
- REQUIREMENTS_MD_PATH (Standard ./docs/requirements.md)

Beispiel .env
```
# Runtime
API_HOST=0.0.0.0
API_PORT=5000

# LLM
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
MOCK_MODE=false

# DB
SQLITE_PATH=/data/app.db
PURGE_RETENTION_H=24

# Batch
BATCH_SIZE=10
MAX_PARALLEL=3
REQUIREMENTS_MD_PATH=./docs/requirements.md
```
# Deployment Leitfaden

Dieses Dokument beschreibt Build, Konfiguration und Betrieb des Backends in der modularisierten Struktur.

Struktur-Überblick
- Paket: [backend_app](../backend_app/__init__.py)
  - [backend_app/settings.py](../backend_app/settings.py)
  - [backend_app/db.py](../backend_app/db.py)
  - [backend_app/utils.py](../backend_app/utils.py)
  - [backend_app/llm.py](../backend_app/llm.py)
  - [backend_app/api.py](../backend_app/api.py)
  - [backend_app/batch.py](../backend_app/batch.py)
- WSGI Entry: [wsgi.py](../wsgi.py)
- Beispiel-Input: [docs/requirements.md](../docs/requirements.md)
- Compose: [docker-compose.yml](../docker-compose.yml)
- Dockerfile: [Dockerfile](../Dockerfile)
- Env Vorlage: [.env.example](../.env.example)

Konfiguration über Env Variablen
- API_HOST, API_PORT
- OPENAI_API_KEY, OPENAI_MODEL (z B gpt-4o-mini)
- MOCK_MODE=true|false (true = Heuristik, keine externen LLM-Calls)
- SQLITE_PATH (Compose setzt /data/app.db)
- PURGE_RETENTION_H (Stunden bis Purge)
- BATCH_SIZE, MAX_PARALLEL (Steuerung für parallele LLM-Calls)
- REQUIREMENTS_MD_PATH (Standard ./docs/requirements.md)

Beispiel .env
```
# Runtime
API_HOST=0.0.0.0
API_PORT=5000

# LLM
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
MOCK_MODE=false

# DB
SQLITE_PATH=/data/app.db
PURGE_RETENTION_H=24

# Batch
BATCH_SIZE=10
MAX_PARALLEL=3
REQUIREMENTS_MD_PATH=./docs/requirements.md
```

Docker Build und Run
- Build
  ```
  docker build -t req-eval-backend:dev .
  ```
- Run (mit Bind-Mounts)
  - Windows PowerShell (Beispiel):
    ```
    docker run -p 5000:5000 --env-file .env `
      -v ${PWD}/data:/data `
      -v ${PWD}/docs:/app/docs:ro `
      req-eval-backend:dev
    ```
  - Linux/Mac:
    ```
    docker run -p 5000:5000 --env-file .env \
      -v $(pwd)/data:/data \
      -v $(pwd)/docs:/app/docs:ro \
      req-eval-backend:dev
    ```

Docker Compose
- Volumes: ./data -> /data (SQLite), ./docs -> /app/docs:ro (Markdown)
- Start
  ```
  docker compose up -d
  ```
- Health
  ```
  curl http://localhost:5000/health
  ```

WSGI und Start
- Gunicorn startet [wsgi:app](../wsgi.py:1), was die App-Factory aus [backend_app](../backend_app/__init__.py:1) lädt.
- Flask-Debug ist im WSGI-Skript nur für lokalen Direktstart vorgesehen.

APIs kurz getestet
- Health
  ```
  curl http://localhost:5000/health
  ```
- Kriterien
  ```
  curl http://localhost:5000/api/v1/criteria
  ```
- Einzel-Evaluation (Beispiel)
  ```
  curl -X POST http://localhost:5000/api/v1/evaluations \
    -H "Content-Type: application/json" \
    -d '{"requirementText":"Das System muss innerhalb von 2 Sekunden reagieren.","context":{"language":"de"},"criteriaKeys":["clarity","testability","measurability"]}'
  ```

Batch-Endpoints
- Evaluate
  ```
  curl -X POST http://localhost:5000/api/v1/batch/evaluate
  ```
- Suggest
  ```
  curl -X POST http://localhost:5000/api/v1/batch/suggest
  ```
- Rewrite
  ```
  curl -X POST http://localhost:5000/api/v1/batch/rewrite
  ```
- Input: [docs/requirements.md](../docs/requirements.md)
  - Tabelle mit Spalten: id | requirementText | context
  - context im JSON-Format empfohlen (z B {"language":"de"})

OpenAI vs Mock
- MOCK_MODE=true: Heuristische Bewertung/Vorschläge/Umschreibungen ohne externe Calls.
- MOCK_MODE=false und OPENAI_API_KEY gesetzt: Live-Anfragen an OpenAI.
- Modellname via OPENAI_MODEL (z B gpt-4o-mini).

## Rollback-Plan (v2 → v1, Flag-/Canary‑basiert)

Ziel
- Sichere und schnelle Rückkehr zum stabilen Zustand (v1), falls nach einem v2‑Rollout Probleme auftreten.
- Minimierung von Daten-/Indexrisiken und Ausfallzeit.

Voraussetzungen
- v1 (Flask, WSGI-Mount) bleibt lauffähig und erreichbar (Hybridbetrieb).
- Canary-Mechanik und Flags sind konfiguriert:
  - FEATURE_FLAG_USE_V2 (bool, Standard: false)
  - CANARY_PERCENT (0..100, Standard: 0)
- v2 (FastAPI) ist als separater Container/Prozess verfügbar (Uvicorn), aber per Flags steuerbar.
- Vector-Store (Qdrant) kann getrennt validiert werden (keine destruktiven Migrationsschritte ohne Confirm/Flags).

Schnell-Rollback (Flags, ohne Re-Deploy)
1) Sofort v2 deaktivieren:
   - FEATURE_FLAG_USE_V2=false
   - CANARY_PERCENT=0
2) Konfiguration neu laden bzw. Prozess neu starten (falls Flags nur beim Start gelesen werden).
3) Validierung:
   - GET /health (soll ok liefern)
   - Funktionstest: POST /api/v1/validate/batch (Baseline-Flow)
   - UI gegen /index.html (API_BASE zeigt auf 8087, WSGI-Mount liefert v1‑Routen)

Canary stoppen (wenn v2 nur teilweise aktiv war)
- CANARY_PERCENT schrittweise auf 0 setzen (z. B. 10 → 0) und Monitoring prüfen (Fehler/Latenz).

Container-/Image-Rollback (optional)
1) Vorheriges, als stabil markiertes Image‑Tag deployen (z. B. :stable-YYYYMMDD-HHMM).
2) docker-compose.* / Orchestrator-Stack aktualisieren.
3) Healthchecks beobachten (Ready/Livez), dann Traffic (ggf. per LB) umschwenken.
4) Post‑Checks (siehe Validierung unten).

Qdrant/Index-Schutz (keine Datenverluste)
- Reset/Schema-Änderungen sind destruktiv. Diese NUR mit Confirm/Flags auslösen.
- Bei Problemen KEIN reset_collection durchführen.
- Validierungen:
  - GET /api/v1/vector/collections (Liste)
  - GET /api/v1/vector/health (Status)
  - Optional: GET /api/v1/vector/source/full?source=… (Stichprobe)

Validierungs-Checkliste nach Rollback
- API:
  - /health, /api/runtime-config (Snapshot plausibel)
  - /api/v1/validate/batch (Beispiel-Request)
  - Streams (optional): /api/v1/validate/batch/stream
- UI:
  - index/mining_demo/reports: Bedienelemente/Flows ok
- Logs/Metriken:
  - Fehlerquote niedrig, Latenz im bekannten Bereich
  - Keine Exceptions/Tracebacks im Uvicorn/Gunicorn‑Log

Entscheidung: v2 isolieren oder weiter debuggen
- v2 weiterlaufen lassen (nur deaktiviert) für Debugging (keine Kundentransaktionen).
- Optional v2 stoppen, wenn Ressourcenverbrauch relevant ist oder Fehler Spam erzeugt.

Nachbereitung / Post-Mortem
- Ursachenanalyse dokumentieren (Was? Warum? Wie erkannt? Wie behoben?).
- Regressionstests erweitern (Unit/Integration/E2E).
- Canary‑Plan anpassen (schrittweise, mit klaren SLOs/Abort‑Kriterien).
- Dokumentation/Runbooks aktualisieren.

Rollforward (erneuter v2‑Versuch)
- Fixes/Mitigationen implementieren.
- v2 schrittweise reaktivieren:
  - FEATURE_FLAG_USE_V2=false, CANARY_PERCENT von 0 → 5 → 10 → … (SLO‑basiert)
  - Bei Stabilität FEATURE_FLAG_USE_V2=true (100% Umschaltung).
- Messbar machen: Header (X-Variant), Logs (variant/variantReason) prüfen.

Hinweise
- Flags/Canary wirken lediglich auf Markierung/Observability im aktuellen Hybrid-Setup. Routing‑Änderungen erfolgen kontrolliert über den WSGI‑Mount/Infra‑LB und Release‑Prozesse.
- Für destruktive Vektor‑Operationen (Reset/Migration) stets Confirm/Tools nutzen (siehe dev/qdrant_migrate.py). 
- Backups/Export der Collections (falls geschäftskritisch) vor großen Änderungen einplanen.

Datenschutz und Speicherung
- Klartext-Requirements werden nicht persistiert; es wird eine SHA-256 Checksumme gespeichert.
- Tabellen siehe [docs/backend/README.md](../docs/backend/README.md) und [docs/backend/schema.sql](../docs/backend/schema.sql).

Troubleshooting
- disk I/O error bei SQLite:
  - Ursache: parallele Schreibvorgänge
  - Lösung: In Batch-Routen werden LLM-Calls parallel ausgeführt, DB-Schreibvorgänge jedoch sequenziell.
  - Sicherstellen, dass /data als beschreibbares Volume gemountet ist.
- Markdown-Datei nicht gefunden:
  - Pfad über REQUIREMENTS_MD_PATH prüfen
  - In Compose wird ./docs nach /app/docs:ro gemountet

Leistungsziele
- p95 Latenz ≤ 2000 ms bei 30 rpm
- Parallelität über MAX_PARALLEL/BATCH_SIZE feinsteuerbar

Änderungen für Deployment
- Modularisierung in backend_app/*
- WSGI-Entry auf backend_app umgestellt ([wsgi.py](../wsgi.py:1))
- Compose bindet Docs und Data