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
- Einstellungen in [backend_app/settings.py](../../backend_app/settings.py)
- Anwendung der Feineinstellungen in [backend_app/llm.py](../../backend_app/llm.py)

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
- Bewertungsaggregation nutzt die Gewichte (siehe [backend_app/utils.py](../../backend_app/utils.py))

---

## 4) Entscheidungslogik (Verdict Threshold)

Env-Variable
- VERDICT_THRESHOLD (Default 0.7)
  - Ab Score ≥ Threshold → verdict=pass, sonst fail

Wirkung im Code
- Anwendung in [backend_app/batch.py](../../backend_app/batch.py) und [backend_app/api.py](../../backend_app/api.py)

---

## 5) Suggest-Max (Anzahl Vorschläge)

Env-Variable
- SUGGEST_MAX (Default 3)

Wirkung im Code
- Limitierung bei Vorschlägen in [backend_app/llm.py](../../backend_app/llm.py)

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