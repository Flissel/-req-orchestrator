# Backend Tests und Beispiel-Responses

Ziel: Manuelle Tests mit Beispiel-Requests und erwarteten Responses als Referenz. Die Beispiele sind so gewählt, dass sie sowohl im MOCK_MODE=true als auch mit echtem LLM funktionieren. Bei Live-LLM können Inhalte variieren; Felder und Strukturen bleiben gleich.

Voraussetzungen
- Container läuft via Docker Compose
- Health erreichbar unter http://localhost:5000/health
- Datei [docs/requirements.md](requirements.md) vorhanden (Batch-Tests)
- Optional: MOCK_MODE=true in [.env](../.env.example), um stabile Antworten zu erhalten

Hinweise
- Windows PowerShell nutzt Invoke-RestMethod, CMD nutzt curl.exe
- Content-Type: application/json bei POST

---

## 1) Health

Befehl
```bash
curl -sS http://localhost:5000/health
```

Erwartete Response
```json
{"status":"ok"}
```

---

## 2) Kriterien

Befehl
```bash
curl -sS http://localhost:5000/api/v1/criteria
```

Beispiel-Response
```json
{
  "items": [
    {"key":"clarity","name":"Klarheit","description":"Ist die Anforderung eindeutig und verständlich","weight":0.4,"active":1},
    {"key":"testability","name":"Testbarkeit","description":"Kann die Anforderung verifiziert werden","weight":0.3,"active":1},
    {"key":"measurability","name":"Messbarkeit","description":"Sind messbare Kriterien definiert","weight":0.3,"active":1}
  ]
}
```

---

## 3) Einzel-Evaluation

Befehl (curl)
```bash
curl -sS -X POST http://localhost:5000/api/v1/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "requirementText":"Das System muss innerhalb von 2 Sekunden auf Suchanfragen reagieren.",
    "context":{"language":"de"},
    "criteriaKeys":["clarity","testability","measurability"]
  }'
```

Beispiel-Response (MOCK_MODE=true)
```json
{
  "evaluationId":"ev_1754995302_50676969",
  "verdict":"pass",
  "score":0.855,
  "latencyMs":3,
  "model":"mock",
  "details":[
    {"criterion":"clarity","score":0.9,"passed":true,"feedback":"Formulierung ist überwiegend eindeutig."},
    {"criterion":"testability","score":0.85,"passed":true,"feedback":"Prüfkriterien sind teilweise ableitbar."},
    {"criterion":"measurability","score":0.8,"passed":true,"feedback":"Messbare Aspekte sind erkennbar."}
  ],
  "suggestions":[]
}
```

Beispiel-Response (LLM aktiv, Inhalte können abweichen)
```json
{
  "evaluationId":"ev_1754995642_50676969",
  "verdict":"pass",
  "score":1.0,
  "latencyMs":4141,
  "model":"gpt-4o-mini",
  "details":[
    {"criterion":"clarity","score":1.0,"passed":true,"feedback":"Die Anforderung ist klar und verständlich formuliert."},
    {"criterion":"testability","score":1.0,"passed":true,"feedback":"Die Reaktionszeit kann gemessen werden."},
    {"criterion":"measurability","score":1.0,"passed":true,"feedback":"Die Reaktionszeit ist quantifiziert."}
  ],
  "suggestions":[]
}
```

Fehlerfälle
- 400 invalid_request wenn requirementText fehlt oder leer ist

---

## 4) Batch Evaluate (Markdown-Eingabe)

Voraussetzung: Tabelle in [docs/requirements.md](requirements.md) (id | requirementText | context)

Befehl
```bash
curl -sS -X POST http://localhost:5000/api/v1/batch/evaluate
```

Beispiel-Response (Auszug)
```json
{
  "items": {
    "R1": {"evaluationId":"ev_...","latencyMs":3000,"model":"gpt-4o-mini","score":1.0,"verdict":"pass"},
    "R2": {"evaluationId":"ev_...","latencyMs":3200,"model":"gpt-4o-mini","score":0.94,"verdict":"pass"}
  },
  "mergedMarkdown": "| id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement |\n|----|------------------|---------|-----------------|--------|-------------|----------------------|\n| R1 | ... | {...} | 1.0 | pass |  |  |\n| R2 | ... | {...} | 0.94 | pass |  |  |"
}
```

Fehlerfälle
- 500 internal_error, wenn REQUIREMENTS_MD_PATH nicht gefunden wird

---

## 5) Batch Suggest

Befehl
```bash
curl -sS -X POST http://localhost:5000/api/v1/batch/suggest
```

Beispiel-Response (Auszug)
```json
{
  "items": {
    "R1": {
      "suggestions":[
        {"text":"Die Bedingungen der Messung (z B Serverlast) definieren.","priority":"high"},
        {"text":"Präzisieren, ob die 2 Sekunden für alle Suchtypen gelten.","priority":"medium"}
      ]
    }
  },
  "mergedMarkdown": "| id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement |\n|----|------------------|---------|-----------------|--------|-------------|----------------------|\n| R1 | ... | {...} | 1.0 | pass | Die Bedingungen ... (high); Präzisieren ... (medium) |  |"
}
```

Hinweis
- Suggestions werden sequenziell in die DB geschrieben (Vermeidung von SQLite I/O Fehlern)
- Mehrfacher Aufruf hängt Suggestions an

---

## 6) Batch Rewrite

Befehl
```bash
curl -sS -X POST http://localhost:5000/api/v1/batch/rewrite
```

Beispiel-Response (Auszug, MOCK_MODE=true mit deterministischer Umschreibung)
```json
{
  "items": {
    "R1": {"redefinedRequirement":"Das System soll Suchanfragen in maximal 2 Sekunden beantworten."}
  },
  "mergedMarkdown": "| id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement |\n|----|------------------|---------|-----------------|--------|-------------|----------------------|\n| R1 | ... | {...} | 1.0 | pass | ... | Das System soll Suchanfragen in maximal 2 Sekunden beantworten. |"
}
```

Hinweis
- Bei Live-LLM kann der Text variieren
- DB-Schreiben erfolgt sequenziell

---

## 7) Correction Decision (Accept/Reject)

Voraussetzung: Es existiert eine Umschreibung (rewritten_requirement) für die Evaluation.

Einzel-Entscheidung setzen
```bash
curl -sS -X POST http://localhost:5000/api/v1/corrections/decision \
  -H "Content-Type: application/json" \
  -d '{"evaluationId":"ev_1754995302_50676969","decision":"accepted","decidedBy":"qa_user"}'
```

Beispiel-Response
```json
{"evaluationId":"ev_1754995302_50676969","decision":"accepted"}
```

Batch-Entscheidungen
```bash
curl -sS -X POST http://localhost:5000/api/v1/corrections/decision/batch \
  -H "Content-Type: application/json" \
  -d '{"items":[
        {"evaluationId":"ev_1754995302_50676969","decision":"accepted","decidedBy":"qa_user"},
        {"evaluationId":"ev_1754997810_679dfbb6","decision":"rejected","decidedBy":"qa_user"}
      ]}'
```

Beispiel-Response
```json
{"updated":2,"errors":[]}
```

Fehlerfälle
- 404 not_found wenn keine Correction vorhanden
- 400 invalid_request bei falscher decision oder leerer evaluationId
- Idempotenz: Bei gleicher Entscheidung keine Seiteneffekte; bei Veränderung wird decided_at aktualisiert

---

## 8) PowerShell-Varianten (Windows)

Einzel-Evaluation
```powershell
$body = @{
  requirementText = 'Das System muss innerhalb von 2 Sekunden auf Suchanfragen reagieren.'
  context = @{ language = 'de' }
  criteriaKeys = @('clarity','testability','measurability')
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Uri 'http://localhost:5000/api/v1/evaluations' -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6
```

Batch Evaluate
```powershell
Invoke-RestMethod -Uri 'http://localhost:5000/api/v1/batch/evaluate' -Method Post | ConvertTo-Json -Depth 6
```

Decision (einzeln)
```powershell
$dec = @{ evaluationId = 'ev_1754995302_50676969'; decision = 'accepted'; decidedBy = 'qa_user' } | ConvertTo-Json
Invoke-RestMethod -Uri 'http://localhost:5000/api/v1/corrections/decision' -Method Post -ContentType 'application/json' -Body $dec
```

---

Tipps zur Fehlersuche
- Worker Timeout bei /batch/rewrite: temporär MOCK_MODE=true setzen oder OpenAI-Timeouts/Retries anpassen
- SQLite disk I/O error: Sicherstellen, dass /data beschreibbar gemountet ist; parallele Schreibvorgänge werden bereits sequenziell durchgeführt
- Markdown nicht gefunden: REQUIREMENTS_MD_PATH prüfen (in [.env](../.env.example) oder Compose Volume ./docs:/app/docs:ro)