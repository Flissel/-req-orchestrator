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