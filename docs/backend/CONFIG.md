# LLM-Konfiguration

Dieses Dokument beschreibt alle Konfigurationspunkte, die das Verhalten der LLM-Responses beeinflussen: Modell, Prompts, Kriterien und Entscheidungslogik.

Überblick
- Env-Variablen in [.env](../../.env.example)
- System-Prompts als Dateien unter ./config/prompts
- Kriterien-Datei unter ./config/criteria.json
- Schwellwerte und Feineinstellungen in Env

Pfad-Hinweise
- In Docker Compose sollten ./config und ./docs als Read-Only in den Container gemountet werden, z B:
  - -v ./config:/app/config:ro
  - -v ./docs:/app/docs:ro

---

## 1) Modell und LLM-Feineinstellungen

Env-Variablen (siehe [.env.example](../../.env.example))
- OPENAI_MODEL
  - z B gpt-4o-mini (Standard)
- OPENAI_API_KEY
  - Ist leer → MOCK_MODE steuert Heuristik; wenn gesetzt und MOCK_MODE=false → Live-LLM
- MOCK_MODE
  - true|false; true erzwingt Heuristik (ohne API-Calls)
- LLM_TEMPERATURE (Default 0.0)
  - Kreativitätsregler; 0.0 = deterministischer
- LLM_TOP_P (Default 1.0)
- LLM_MAX_TOKENS (Default 0 = SDK-Default)

Beispiel [.env](../../.env.example)
```
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-***
MOCK_MODE=false
LLM_TEMPERATURE=0.0
LLM_TOP_P=1.0
LLM_MAX_TOKENS=0
```

Code-Referenzen
- Einstellungen in [backend/core/settings.py](../../backend/core/settings.py)
- Anwendung der Feineinstellungen in [backend/core/llm.py](../../backend/core/llm.py)

---

## 2) System-Prompts

Dateien (optional, leerlassen → sichere Defaults):
- Bewertung: [config/prompts/evaluate.system.txt](../../config/prompts/evaluate.system.txt)
- Vorschläge: [config/prompts/suggest.system.txt](../../config/prompts/suggest.system.txt)
- Umschreiben: [config/prompts/rewrite.system.txt](../../config/prompts/rewrite.system.txt)

Env-Variablen (Pfadangaben)
- EVAL_SYSTEM_PROMPT_PATH=./config/prompts/evaluate.system.txt
- SUGGEST_SYSTEM_PROMPT_PATH=./config/prompts/suggest.system.txt
- REWRITE_SYSTEM_PROMPT_PATH=./config/prompts/rewrite.system.txt

Formatregeln
- Prompts fordern strikt JSON als Ausgabe (siehe Dateien)
- Keine freien Texte außerhalb des JSON

---

## 3) Kriterien (Weights, Aktivierung, Namen)

JSON-Datei: [config/criteria.json](../../config/criteria.json)
- Schema:
```
[
  { "key": "clarity", "name": "Klarheit", "description": "Ist die Anforderung eindeutig und verständlich", "weight": 0.4, "active": true },
  { "key": "testability", "name": "Testbarkeit", "description": "Kann die Anforderung verifiziert werden", "weight": 0.3, "active": true },
  { "key": "measurability", "name": "Messbarkeit", "description": "Sind messbare Kriterien definiert", "weight": 0.3, "active": true }
]
```

Wirkung
- Beim App-Start werden Einträge upserted (Create/Update) in Tabelle criterion
- Bewertungsaggregation nutzt die Gewichte (siehe [backend/core/utils.py](../../backend/core/utils.py))

---

## 4) Entscheidungslogik (Verdict Threshold)

Env-Variable
- VERDICT_THRESHOLD (Default 0.7)
  - Ab Score ≥ Threshold → verdict=pass, sonst fail

Wirkung im Code
- Anwendung in [backend/core/batch.py](../../backend/core/batch.py) und [backend/core/api.py](../../backend/core/api.py)

---

## 5) Suggest-Max (Anzahl Vorschläge)

Env-Variable
- SUGGEST_MAX (Default 3)

Wirkung im Code
- Limitierung bei Vorschlägen in [backend/core/llm.py](../../backend/core/llm.py)

---

## 6) Zusammenfassung der wichtigsten Env-Keys

Minimal
- OPENAI_MODEL
- OPENAI_API_KEY
- MOCK_MODE
- VERDICT_THRESHOLD
- SUGGEST_MAX

Optional Feintuning
- LLM_TEMPERATURE
- LLM_TOP_P
- LLM_MAX_TOKENS
- EVAL_SYSTEM_PROMPT_PATH, SUGGEST_SYSTEM_PROMPT_PATH, REWRITE_SYSTEM_PROMPT_PATH
- CRITERIA_CONFIG_PATH

---

## 7) Checkliste: Konfig anwenden

1) Dateien anlegen/prüfen
- config/prompts/*.txt
- config/criteria.json

2) .env setzen
- OPENAI_API_KEY, OPENAI_MODEL, MOCK_MODE=false
- VERDICT_THRESHOLD, SUGGEST_MAX ggf. anpassen

3) Compose neu starten
```
docker compose up -d --build
```

4) Verifizieren
- Health: GET /health
- Evaluate: POST /api/v1/batch/evaluate
- Suggest: POST /api/v1/batch/suggest
- Rewrite: POST /api/v1/batch/rewrite

Hinweis
- Bei langen LLM-Zeiten ggf. MOCK_MODE=true für schnelle Tests verwenden.

# Backend-Konfiguration

## Neue/erweiterte ENV-Variablen

Diese Variablen ergänzen die bestehende Konfiguration und wurden im Zuge der v2‑Migration und des Vector/RAG‑Hardenings eingeführt.

- EMBEDDINGS_AUTOPROBE
  - Typ: boolean (1/true/yes/on)
  - Default: false
  - Wirkung: Wenn aktiv und OPENAI_API_KEY vorhanden ist, wird beim Runtime‑Snapshot eine 1‑Element‑Probe gegen das Embeddings‑Modell durchgeführt, um die effektive Vektordimension zu ermitteln. Fallback bleibt die statische Dimension aus dem Embeddings‑Modul.
  - Quelle/Implementierung: [python.get_runtime_config()](../../backend/core/settings.py:108)

- QDRANT_AUTODETECT
  - Typ: boolean (1/true/yes/on)
  - Default: true
  - Wirkung: Ermittelt in der Runtime‑Konfiguration effective_url, Collection‑Existenz und (falls vorhanden) die konfigurierte Collection‑Dimension. Fehler werden non‑fatal als error‑Feld im vector‑Block ausgegeben.
  - Quelle/Implementierung: [python.get_runtime_config()](../../backend/core/settings.py:108)

- QDRANT_AUTOCREATE
  - Typ: boolean (1/true/yes/on)
  - Default: false
  - Wirkung: Wenn aktiv, wird die Collection bei fehlender Existenz (oder Dim‑Mismatch) automatisch (re)erstellt. Achtung: „recreate“ ist destruktiv (Drop + Create). Verwenden Sie dies nur in nicht‑produktiven Umgebungen oder mit ausdrücklicher Freigabe.
  - Alternativ/Tooling: CLI‑Skript [dev/qdrant_migrate.py](../../dev/qdrant_migrate.py) für Dry‑Run/Auto‑Create/Recreate.
  - Quelle/Implementierung: [python.get_runtime_config()](../../backend/core/settings.py:108), [python.reset_collection()](../../backend/core/vector_store.py:197)

- FEATURE_FLAG_USE_V2
  - Typ: boolean (1/true/yes/on)
  - Default: false
  - Wirkung: Canary/Cutover‑Flag – wenn gesetzt, markiert alle Requests als „v2“. Dient im aktuellen Hybrid‑Setup der Observability (Header/Cookies/Logs), nicht dem harten Routing‑Umschalter.
  - Observability: Response‑Header X‑Variant, X‑Variant‑Reason; Cookie „variant“. Logging enthält variant/variantReason.
  - Quelle/Implementierung: [python.add_request_id_header()](../../backend/main.py:46)

- CANARY_PERCENT
  - Typ: integer (0..100)
  - Default: 0
  - Wirkung: Prozentualer Anteil (sticky via SHA‑256(Request‑Id) Bucket), der als „v2“ markiert wird, sofern FEATURE_FLAG_USE_V2=false ist. 0 = aus, 100 = alle.
  - Observability wie oben; nur Markierung/Telemetry, kein hartes Umschalten.
  - Quelle/Implementierung: [python.add_request_id_header()](../../backend/main.py:46)

### Beispiel (.env)

```dotenv
# Embeddings/Vector
EMBEDDINGS_MODEL=text-embedding-3-small
EMBEDDINGS_AUTOPROBE=false

QDRANT_URL=http://host.docker.internal
QDRANT_PORT=6333
QDRANT_COLLECTION=requirements_v1
QDRANT_AUTODETECT=true
QDRANT_AUTOCREATE=false

# Canary/Cutover (Observability)
FEATURE_FLAG_USE_V2=false
CANARY_PERCENT=0
```

### Hinweise

- Runtime‑Snapshot (/api/runtime-config) zeigt die erkannten Werte im Block vector/embeddings an:
  - vector: { effective_url, exists, detected_dim (Collection), matches_dim, auto_created, error? }
  - embeddings: { model, detected_dim }
- Für destruktive Operationen (Reset/Recreate) wird empfohlen, das Tool [dev/qdrant_migrate.py](../../dev/qdrant_migrate.py) zu nutzen (Dry‑Run/Bestätigungspfad).

---

## 8) Test-/CI-Umgebungen

### DISABLE_GRPC (Tests/Lokal)

- Zweck: Überspringt den gRPC/AutoGen Lifespan‑Startup in der FastAPI‑App, damit Unit/Parity‑Tests ohne Netzwerk-/Worker‑Abhängigkeiten laufen.
- ENV:
  - `DISABLE_GRPC=true|1|yes`
- Implementierung: Guard im Lifespan von [fastapi_main.lifespan()](../../fastapi_main.py:353)
- Empfohlen für:
  - pytest lokal/CI, Smoke‑Tests ohne Worker
- Beispiel:
  - Windows (cmd): `set DISABLE_GRPC=true && pytest -q`
  - Linux/macOS: `DISABLE_GRPC=true pytest -q`

### Empfohlene CI‑ENV (deterministisch, ohne externe Dienste)

Diese Variablen minimieren externe Abhängigkeiten in CI‑Läufen:

```yaml
env:
  DISABLE_GRPC: "true"
  MOCK_MODE: "true"
  OPENAI_API_KEY: ""
  QDRANT_URL: "http://localhost"
  QDRANT_PORT: "6333"
  QDRANT_AUTODETECT: "false"
  QDRANT_AUTOCREATE: "false"
  CANARY_PERCENT: "0"
  FEATURE_FLAG_USE_V2: "false"
```

- Beispiel GitHub Actions Schritt (mit Coverage‑Gate ≥ 80%):
  ```yaml
  - name: Pytest
    env:
      DISABLE_GRPC: "true"
      MOCK_MODE: "true"
      OPENAI_API_KEY: ""
      QDRANT_URL: "http://localhost"
      QDRANT_PORT: "6333"
      QDRANT_AUTODETECT: "false"
      QDRANT_AUTOCREATE: "false"
      CANARY_PERCENT: "0"
      FEATURE_FLAG_USE_V2: "false"
    run: |
      pytest -q
      coverage report --rcfile=pyproject.toml --fail-under=80 --show-missing
  ```