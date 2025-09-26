# LLM Workflow und Konfigurationsspezifikation

Ziel
- Präzise Definition des End-to-End-Workflows und aller LLM-relevanten Konfigurationen, Prompts, Regeln, Token-Limits und Response-Formate.
- Sicherstellen, dass jedes Requirement einzeln analysierbar ist und die Ergebnisse in konsistenter Tabellenform geschrieben werden.

Überblick Workflow (E2E)
1) Markdown einlesen: Quelle ist REQUIREMENTS_MD_PATH (Default ./docs/requirements.md)
2) Evaluieren: Pro Requirement werden Kriterien geprüft und ein Verdict gebildet
3) Entscheidung (Evaluation notwendig): Falls mind. ein Kriterium nicht bestanden/unter Schwellwert → Suggestions generieren
4) Suggestions: Pro Requirement kontextbezogene, handlungsleitende Empfehlungen erzeugen
5) Rewrite: Neue präzise, testbare, messbare Formulierung erzeugen
6) Zusammenführen und persistieren: Merged Markdown mit zusätzlichen Spalten (evaluationScore, verdict, suggestions, redefinedRequirement) in Datei schreiben

Konfiguration (Konfigurierbar via Env/Dateien)
- Modell und Laufzeit: siehe [backend_app/settings.py](backend_app/settings.py:1)
  - OPENAI_MODEL, OPENAI_API_KEY, MOCK_MODE
  - LLM_TEMPERATURE, LLM_TOP_P, LLM_MAX_TOKENS
- System-Prompts (Dateien, optional): siehe [backend_app/settings.py](backend_app/settings.py:33)
  - EVAL_SYSTEM_PROMPT_PATH, SUGGEST_SYSTEM_PROMPT_PATH, REWRITE_SYSTEM_PROMPT_PATH
  - Standard-Prompts in:
    - [config/prompts/evaluate.system.txt](config/prompts/evaluate.system.txt)
    - [config/prompts/suggest.system.txt](config/prompts/suggest.system.txt)
    - [config/prompts/rewrite.system.txt](config/prompts/rewrite.system.txt)
- Kriterien (Gewichte, Aktivierung, Texte)
  - Datei: [config/criteria.json](config/criteria.json)
  - Upsert beim Start: [backend_app/db.py](backend_app/db.py:85)
- Entscheidungsgrenzen
  - VERDICT_THRESHOLD (z B 0.7), Anwendung in [backend_app/api.py](backend_app/api.py:1) und [backend_app/batch.py](backend_app/batch.py:1)
- Vorschlagsmenge
  - SUGGEST_MAX (Default 3), Anwendung in [backend_app/llm.py](backend_app/llm.py:1)

Input Tabellenformat (Markdown)
- Eingabe (anforderungen): Pflichtspalten
  - id: String (z B R1)
  - requirementText: String
  - context: JSON oder Freitext (wird als {"note": "..."} interpretiert)
- Beispiel Kopf
  | id | requirementText | context |
  |----|------------------|---------|
  | R1 | ... | {"language":"de","domain":"search"} |

Output Tabellenformat (Merged)
- Spalten:
  - id | requirementText | context | evaluationScore | verdict | suggestions | redefinedRequirement
- Vorschläge: Semikolon-getrennt "Text (priority)"

Entscheidungslogik Evaluation notwendig
- evaluationScore (gewichteter Score) < VERDICT_THRESHOLD → notwendig
- detail.passed == false für mindestens ein Kriterium → notwendig
- Beispiel-Kriterien (erweiterbar per criteria.json)
  - clarity, testability, measurability, atomic, concise, unambiguous, consistent_language, follows_template, design_independent, purpose_independent

LLM Prompts und Regeln

A) Evaluation Prompt
- Datei/Default: [config/prompts/evaluate.system.txt](config/prompts/evaluate.system.txt)
- Regeln:
  - Antworte ausschließlich als JSON
  - Verwende exakt die übergebenen Kriteriennamen (criteriaKeys)
  - Scores in [0.0,1.0], gerundet (2 Nachkommastellen empfohlen)
  - passed = true falls score ≥ verdictThreshold (Kontext) sonst false
  - feedback kurz und spezifisch
- Response-Format:
  {
    "details": [
      { "criterion": "clarity", "score": 0.92, "passed": true, "feedback": "klare, knappe Formulierung" },
      ...
    ]
  }
- Token-Limits:
  - LLM_MAX_TOKENS: Default 0 (SDK-Default)
  - Kleiner Temperaturwert (0.0) für deterministische Ergebnisse
  - top_p ggf. 1.0

B) Suggest Prompt
- Datei/Default: [config/prompts/suggest.system.txt](config/prompts/suggest.system.txt)
- Regeln:
  - Antworte ausschließlich als JSON
  - Maximal SUGGEST_MAX Vorschläge (Default 3)
  - Jede Empfehlung ist präzise, handlungsleitend und kurz
  - Priorität low|medium|high
- Response-Format:
  {
    "suggestions": [
      { "text": "Definiere Messbedingung (Serverlast)", "priority": "high" },
      { "text": "Präzisiere Terminologie", "priority": "medium" }
    ]
  }
- Token-Limits:
  - LLM_MAX_TOKENS analog Evaluation
  - Temperatur typ. 0.0–0.2

C) Rewrite Prompt
- Datei/Default: [config/prompts/rewrite.system.txt](config/prompts/rewrite.system.txt)
- Regeln:
  - Antworte ausschließlich als JSON
  - Eine präzise, testbare, messbare Formulierung (ein Satz)
  - Keine zusätzlichen Annahmen, Kontext respektieren
- Response-Format:
  {
    "redefinedRequirement": "Das System beantwortet Suchanfragen binnen 2 Sekunden bei 95% der Anfragen unter Nennlast."
  }
- Token-Limits:
  - LLM_MAX_TOKENS: z B 128–256 ausreichend
  - Temperatur typ. 0.0–0.3

Response-Formate (Backend-API)
- Einzel Evaluation: POST /api/v1/evaluations
  {
    "evaluationId": "ev_...",
    "verdict": "pass|fail",
    "score": 0.82,
    "latencyMs": 1240,
    "model": "gpt-4o-mini|mock",
    "details": [{...}],
    "suggestions": [{ "text": "...", "priority": "high" }]
  }
- Batch Evaluate: POST /api/v1/batch/evaluate
  {
    "items": { "R1": { "evaluationId":"...", "score":..., "verdict":"..." }, ... },
    "mergedMarkdown": "..."
  }
- Batch Suggest: POST /api/v1/batch/suggest
  {
    "items": { "R1": { "suggestions":[...] }, ... },
    "mergedMarkdown": "..."
  }
- Batch Rewrite: POST /api/v1/batch/rewrite
  {
    "items": { "R1": { "redefinedRequirement":"..." }, ... },
    "mergedMarkdown": "..."
  }
- Correction Decision: POST /api/v1/corrections/decision
  { "evaluationId": "ev_...", "decision": "accepted|rejected" }

Token Budgetierung (Empfehlung)
- evaluate:
  - Input tokens: kriterienahe Kapselung, requirementText + Kriterienliste + Kontext
  - Output tokens: ~ (Kriterienanzahl × 30) (score+reason)
  - LLM_MAX_TOKENS: 256–512
- suggest:
  - Output klein halten: SUGGEST_MAX × ~40
  - LLM_MAX_TOKENS: 128–256
- rewrite:
  - Output: ein Satz + begrenzte Länge
  - LLM_MAX_TOKENS: 128
- Falls Tokenlimit zu klein:
  - Backend setzt robustes Fallback (Heuristik)
  - Logischer Retry optional (nicht standardmäßig aktiviert)

Kriteriensteuerung
- Datei [config/criteria.json](config/criteria.json) bestimmt:
  - Aktivierte Kriterien (active=true|false)
  - Gewichte (weight) → Einfluss auf evaluationScore
  - Anzeigenamen/Description
- Upsert beim Start: [backend_app/db.py](backend_app/db.py:85)
- Aggregation: [backend_app/utils.py](backend_app/utils.py:14)

Ablage/Output-Dateien
- mergedMarkdown: Der API-Response enthält den fertigen Tabellentext; das Frontend/Caller schreibt ihn in Zielpfad (z B ./docs/requirements.out.md)
- Jede Route erzeugt auf Wunsch eigenständige Ausgabe (oder kumuliert)

Parallelität/Rate Limits
- Batch: BATCH_SIZE (Default 10)
- Parallel: MAX_PARALLEL (Default 3) (LLM-Calls), DB-Schreibvorgänge sequenziell
- Timeouts/Resilienz: Upstream-Timeouts empfohlen (nicht global erzwungen), MOCK_MODE für lokale Tests

Testreferenzen
- Siehe [docs/backend/TESTS.md](docs/backend/TESTS.md)

Akzeptanzkriterien
- Jedes Requirement wird einzeln analysiert
- Entscheidungen (Accept/Reject) persistiert (correction_decision)
- Zusammenführung in Tabellenformat vollständig und konsistent
- Konfigurationen wirken ohne Codeänderung (Env/Dateien)