# Datenmodelle

Dieses Dokument definiert die fachlichen Datenmodelle, inklusive Datenbankschema, API-DTOs, Validierungsregeln und Beispiele. Wir starten modellweise und erweitern iterativ.

---

## 1. Criterion

Zweck
- Beschreibt Evaluationskriterien, die bei der Bewertung von Requirements verwendet werden.
- Typische Kriterien: clarity, testability, measurability.

Persistenz (SQLite)
- Tabelle: `criterion`
- Quelle: siehe bestehendes DDL in [schema.sql](schema.sql)

Aktuelles DDL (Referenz)
```sql
CREATE TABLE IF NOT EXISTS criterion (
  key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  weight REAL NOT NULL DEFAULT 1.0,
  active INTEGER NOT NULL DEFAULT 1
);
```

Empfohlene fachliche Constraints
- key
  - Pflichtfeld, eindeutig (PK)
  - Pattern: ^[a-z][a-z0-9_]{2,30}$ (lowercase, 3–31 Zeichen, Unterstrich erlaubt)
- name
  - Pflichtfeld, Länge 1–80 Zeichen
- description
  - Optional, Länge 0–500 Zeichen
- weight
  - Pflichtfeld, Wertebereich 0.0–1.0 (Standard 1.0)
  - Wird als Gewicht im gewichteten Score verwendet
- active
  - Pflichtfeld, bool (0/1), Standard 1
- Hinweis: Bereichs- und Längenchecks werden applikativ validiert; CHECK-Constraints in SQLite sind optional ergänzbar.

API-DTOs

1) Lesen (Public Read)
- Endpoint: `GET /api/v1/criteria`
- Response
  ```json
  {
    "items": [
      {
        "key": "clarity",
        "name": "Klarheit",
        "description": "Ist die Anforderung eindeutig und verständlich",
        "weight": 0.4,
        "active": true
      }
    ]
  }
  ```

2) Anlegen/Ändern (Admin Use-Case – zukunftig/optional)
- Derzeit keine Public-Admin-Endpoints. Für spätere Erweiterungen:
  - Create DTO (Vorschlag)
    ```json
    {
      "key": "testability",
      "name": "Testbarkeit",
      "description": "Kann die Anforderung verifiziert werden",
      "weight": 0.3,
      "active": true
    }
    ```
  - Update DTO (Vorschlag)
    ```json
    {
      "name": "Testbarkeit",
      "description": "Kann die Anforderung verifiziert werden",
      "weight": 0.3,
      "active": true
    }
    ```
- Konfliktfälle
  - 409 conflict bei doppeltem key (Create)
  - 404 not_found bei fehlendem Datensatz (Update/Delete)
  - 400 invalid_request bei Validierungsverletzungen

Validierungsregeln (applikativ)
- key: Pflicht, Regex ^[a-z][a-z0-9_]{2,30}$, keine führenden/trailing Spaces
- name: Pflicht, 1–80 Zeichen, Trim, keine reinen Whitespaces
- description: optional, max. 500 Zeichen, Trim
- weight: Pflicht, float, 0.0 ≤ weight ≤ 1.0
- active: Pflicht, bool (true/false)

Beispiele

1) Gültige Datensätze
```json
{
  "key": "clarity",
  "name": "Klarheit",
  "description": "Ist die Anforderung eindeutig und verständlich",
  "weight": 0.4,
  "active": true
}
```
```json
{
  "key": "measurability",
  "name": "Messbarkeit",
  "description": "Sind messbare Kriterien definiert",
  "weight": 0.3,
  "active": true
}
```

2) Ungültige Datensätze (Beispiele)
- key: "Clarity" (Großbuchstabe → Regex-Verstoß)
- name: "" (leer → Pflichtfeld)
- weight: 1.5 (außerhalb 0..1)
- description: Länge > 500 (zu lang)

Domänenregeln
- Summe der aktiven Gewichte kann 1.0 sein, muss es aber nicht. Die Aggregation normalisiert auf Summe der Gewichte (siehe Scoring in [backend/core/utils.py](../../backend/core/utils.py)).

Migrationshinweise (optional)
- Für SQLite kann ein CHECK auf weight ergänzt werden (nur bei Neuaufbau; ALTER TABLE eingeschränkt).

Tests (Beispiele)
- GET /api/v1/criteria: 200 und DTO-Validierung je Item
- Scoring-Integration: Deaktivierte Kriterien werden ausgeschlossen

---

## 2. Evaluation und EvaluationDetail

Zweck
- Evaluation: Aggregat je geprüfter Anforderung (anhand der Prüfsummen-Identifikation).
- EvaluationDetail: Detailwerte je Kriterium für eine Evaluation.

Persistenz (SQLite)
- Tabellen: `evaluation`, `evaluation_detail`
- Quelle: DDL bereits enthalten in [schema.sql](schema.sql) und [backend/core/db.py](../../backend/core/db.py)

DDL (Konsolidierte Referenz)
```sql
CREATE TABLE IF NOT EXISTS evaluation (
  id TEXT PRIMARY KEY,
  requirement_checksum TEXT NOT NULL,
  model TEXT NOT NULL,
  latency_ms INTEGER,
  score REAL,
  verdict TEXT CHECK (verdict IN ('pass','fail')),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evaluation_created_at ON evaluation (created_at);
CREATE INDEX IF NOT EXISTS idx_evaluation_checksum ON evaluation (requirement_checksum);

CREATE TABLE IF NOT EXISTS evaluation_detail (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  criterion_key TEXT NOT NULL,
  score REAL,
  passed INTEGER NOT NULL,
  feedback TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE,
  FOREIGN KEY (criterion_key) REFERENCES criterion(key)
);
```

Empfohlene fachliche Constraints
- evaluation.id
  - Pflichtfeld, eindeutig; Formatvorschlag: ev_{epochSeconds}_{8-hex}
  - Beispiel: ev_1754995302_50676969
- evaluation.requirement_checksum
  - Pflichtfeld, SHA-256 Hex (64 Zeichen)
  - Index vorhanden (Suchen nach letzter Evaluation)
- evaluation.model
  - Pflichtfeld, nicht leer (z B "gpt-4o-mini" oder "mock")
- evaluation.latency_ms
  - integer ≥ 0
- evaluation.score
  - 0.0 ≤ score ≤ 1.0 (applikativ validieren)
- evaluation.verdict
  - "pass" | "fail" (CHECK vorhanden)
- evaluation.created_at
  - default CURRENT_TIMESTAMP
- evaluation_detail.evaluation_id
  - Pflicht, FK → evaluation.id
- evaluation_detail.criterion_key
  - Pflicht, FK → criterion.key
- evaluation_detail.score
  - 0.0 ≤ score ≤ 1.0 (applikativ validieren)
- evaluation_detail.passed
  - bool (0/1)
- Empfehlung: UNIQUE(evaluation_id, criterion_key) zur Vermeidung doppelter Detailzeilen (optional Migration)

Indizes
- evaluation: created_at, requirement_checksum (bereits vorhanden)
- evaluation_detail: implizit über FK; optional INDEX auf (evaluation_id)

API-DTOs

1) Einzel-Evaluation (bereits implementiert)
- Endpoint: `POST /api/v1/evaluations`
- Request
  ```json
  {
    "requirementText": "Das System muss innerhalb von 2 Sekunden auf Suchanfragen reagieren.",
    "context": {"domain":"search","language":"de"},
    "criteriaKeys": ["clarity","testability","measurability"]
  }
  ```
- Response
  ```json
  {
    "evaluationId": "ev_1754995302_50676969",
    "verdict": "pass",
    "score": 0.855,
    "latencyMs": 1240,
    "model": "gpt-4o-mini",
    "details": [
      {"criterion": "clarity", "score": 0.9, "passed": true, "feedback": "klar formuliert"},
      {"criterion": "testability", "score": 0.8, "passed": true, "feedback": "messbarer Schwellenwert vorhanden"},
      {"criterion": "measurability", "score": 0.78, "passed": true, "feedback": "Zielzeit 2 Sekunden spezifiziert"}
    ],
    "suggestions": []
  }
  ```

2) Batch Evaluate (übersicht)
- Endpoint: `POST /api/v1/batch/evaluate`
- Response: items je id, sowie `mergedMarkdown` mit Spalten evaluationScore, verdict

Validierungsregeln (applikativ)
- requirementText: Pflicht (für Einzel-Evaluation), Trim; kein Speichern als Klartext
- score: float 0..1
- verdict: aus {pass, fail}
- details[].criterion: muss existieren und aktiv sein (oder bewusst zugelassen, wenn explizit angefordert)
- details[].feedback: max. 1000 Zeichen (Empfehlung)
- model: nicht leer
- latencyMs: ≥ 0

Beispiele

Gültige Evaluation (aggregiert)
```json
{
  "evaluationId": "ev_1754995302_50676969",
  "verdict": "pass",
  "score": 0.9,
  "latencyMs": 1100,
  "model": "gpt-4o-mini",
  "details": [
    {"criterion": "clarity", "score": 1.0, "passed": true, "feedback": "eindeutig"},
    {"criterion": "testability", "score": 0.8, "passed": true, "feedback": "verifizierbar"},
    {"criterion": "measurability", "score": 0.9, "passed": true, "feedback": "Schwellwerte vorhanden"}
  ],
  "suggestions": []
}
```

Ungültige Fälle
- score außerhalb [0,1]
- details[].criterion unbekannt
- verdict ≠ "pass"|"fail"

Domänenregeln
- Aggregation: gewichteter Score gemäß `criterion.weight`, Normalisierung auf Summe der Gewichte (siehe [backend/core/utils.py](../../backend/core/utils.py))
- Idempotenz: es existieren mehrere Evaluationen zur gleichen checksum über die Zeit; die „neueste“ wird über created_at selektiert
- Klartext-Schutz: kein Ablegen des requirementText, nur die Prüfsumme

Tests (Beispiele)
- POST /api/v1/evaluations: 200 mit gültigem DTO, Latenz- und Modellangaben
- Mehrfachevaluation derselben Anforderung: letzte per checksum abrufbar (indirekt via Batch-merge)
- Detailzeilen pro Evaluation: je aktives Kriterium genau eine (optional UNIQUE sichern)

---

Nächstes Modell (Vorschlag)
- Suggestion
- Inhalte: Felder, DTO, Validierung, Prioritätenregeln, Deduplizierungsszenarien
---

## 0. Workflow-Interpretation aus UI-Bildern

Beobachtung
- Eingabe (Requirements Input): Liste von Anforderungen mit Index. Buttons zum Hinzufügen/Entfernen, Process/ Clear.
- Ausgabe (Requirements Output):
  - Pro Requirement ein Panel mit Status (grün Haken = ok, rot = Issue).
  - Evaluation-Tabelle je Requirement mit Spalten Criterion und Reason.
    - Kriterien-Beispiele: Atomic, Concise, Unambiguous, Consistent Language, Follows Template, Design Independent, Purpose Independent.
    - Reason zeigt Begründung, z B "The requirement is not written in English language."
  - Correction: Ein umgeschriebener Satz (z B "The shuttle must be able to be driven manually in reverse.")
  - Aktionen: Accept und Reject pro Correction sowie Accept All / Reject All global.

Abgeleitete Schritte
1) Batch-Input: Liste von requirementText wird gesendet (Frontend-Herkunft), Backend speichert KEINEN Klartext im Ruhezustand.
2) Evaluation: Für jedes Requirement entstehen Details pro Kriterium inkl. passed und reason (bei uns: feedback).
3) Correction: Eine umformulierte Fassung wird erzeugt (redefinedRequirement).
4) Entscheidung: Nutzer akzeptiert oder verwirft die Korrektur (pro Requirement) oder global (alle).
5) Output-Status pro Requirement stellt Ergebnis (ok / issue) und ggf. Correction dar.

Mapping auf bestehende Modelle
- evaluation_detail.feedback = Reason in der Tabelle (UI).
- rewritten_requirement.text = Correction (UI).
- Wir benötigen zusätzlich eine persistierte Entscheidung (accept/reject) pro Correction und eine Operation für Accept All / Reject All.

---

## 3. CorrectionDecision (neu)

Zweck
- Erfasst die Entscheidung des Nutzers zu einer generierten Correction (redefinedRequirement) je Evaluation.
- Dient dem UI-Workflow (Accept/Reject pro Requirement, Accept All/Reject All global).

Persistenz (SQLite)
- Tabelle: `correction_decision` (neu)
- Beziehungen:
  - evaluation_id → evaluation.id (FK)
  - rewritten_id → rewritten_requirement.id (FK)

Vorgeschlagenes DDL
```sql
CREATE TABLE IF NOT EXISTS correction_decision (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  evaluation_id TEXT NOT NULL,
  rewritten_id INTEGER NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('accepted','rejected')),
  decided_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_by TEXT,
  FOREIGN KEY (evaluation_id) REFERENCES evaluation(id) ON DELETE CASCADE,
  FOREIGN KEY (rewritten_id) REFERENCES rewritten_requirement(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_correction_decision_eval ON correction_decision(evaluation_id);
```

Fachliche Constraints
- Pro Evaluation genau eine finale Entscheidung (UNIQUE auf evaluation_id).
- decision ∈ {accepted, rejected}.
- decided_by optional (Freitext provisorisch; später an Benutzerkonzept adaptieren).

API-DTOs

1) Entscheidung setzen (Einzel)
- Endpoint (Vorschlag): `POST /api/v1/corrections/decision`
- Request
  ```json
  {
    "evaluationId": "ev_1754995302_50676969",
    "decision": "accepted"
  }
  ```
  - Das Backend wählt die jüngste `rewritten_requirement` für die Evaluation.
- Response
  ```json
  {
    "evaluationId": "ev_1754995302_50676969",
    "decision": "accepted",
    "decidedAt": "2025-08-12T10:10:00Z"
  }
  ```
- Fehlerfälle
  - 404 not_found, wenn keine Evaluation existiert
  - 409 conflict, wenn bereits Entscheidung getroffen (optional mit Override-Flag)

2) Entscheidung setzen (Batch)
- Endpoint (Vorschlag): `POST /api/v1/corrections/decision/batch`
- Request
  ```json
  {
    "items": [
      {"evaluationId": "ev_..._a1", "decision": "accepted"},
      {"evaluationId": "ev_..._b2", "decision": "rejected"}
    ]
  }
  ```
- Response
  ```json
  { "updated": 2, "errors": [] }
  ```

Validierungsregeln
- evaluationId: Pflicht, existierend
- decision: Pflicht, "accepted" | "rejected"
- rewritten_id: implizit Jüngste Umschreibung je Evaluation (oder optional explizit mitgegeben)

Domänenregeln
- Accept/Reject All: Frontend liefert Liste von evaluationIds; Backend setzt Entscheidungen in einem Batch (Transaktion).
- Idempotenz: Wiederholtes Setzen derselben Entscheidung ist ok (no-op), abweichende Entscheidung optional per Override zulassen.

---

## 4. Erweiterung: rewritten_requirement

Ergänzende Felder (optional, falls Präferenz für Audit in einer Tabelle)
- accepted INTEGER NULL (0/1) — nur setzen, wenn entschieden
- decided_at DATETIME NULL
- decided_by TEXT NULL

Vorteile
- Schnellere Abfrage „zeige akzeptierte Korrekturen“ ohne Join.
Nachteile
- Semantische Trennung (Entscheidung ist fachlich ein Ereignis) geht verloren. Empfehlung bleibt: separate Tabelle `correction_decision`.

---

## 5. Request/Response-Statusmodell (UI-Workflow)

Status je Requirement (nicht persistiert, aus evaluierten Daten + Entscheidung abgeleitet)
- ok: alle Kriterien passed, keine Korrektur nötig (oder Korrektur existiert, aber nicht erforderlich)
- issue: mindestens ein Kriterium failed → Correction vorgeschlagen
- accepted: Entscheidung accepted für die jüngste Correction
- rejected: Entscheidung rejected für die jüngste Correction

Ableitung
- issue = exists(detail.passed=false) oder (exists(reason) mit fail)
- accepted/rejected = decision-Eintrag für evaluation vorhanden

---

## 6. Offene Punkte / Annahmen

- Benutzeridentität (decided_by): aktuell Freitext; für spätere Auth kann hier eine User-ID gespeichert werden.
- Mehrere umformulierte Vorschläge: Derzeit genau ein Text je Evaluation (letzter zählt). Für Multi-Proposals könnte `rewritten_requirement` mehrere Varianten fassen und der Decision-Endpoint einen `rewrittenId` annehmen.
- Deduplizierung von Suggestions: Aktuell werden Suggestions angehängt; optional UNIQUE(evaluation_id, text).

---

## 7. Nächste Schritte (Datenmodell-Reihenfolge)

1) Implementieren `correction_decision` (DDL, DB-Access) in [backend/core/db.py](../../backend/core/db.py)
2) API-Endpoints für Entscheidungen spezifizieren und implementieren
3) Frontend-Flow: Accept/Reject Buttons binden (Einzel & „Accept All/Reject All“)
4) Optional: Erweiterter Audit (decided_by, Quelle der Entscheidung)