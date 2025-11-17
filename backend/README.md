# Backend App V2 - LangExtract Fixes

## 🚀 Übersicht

Diese Version (`backend_app_v2`) enthält die **korrigierten LangExtract-Integrationen** basierend auf der funktionierenden `dev/run_extract.py`.

## 🔧 Implementierte Korrekturen

### 1. **Besserer Prompt**
- Spezifisch für Requirements-Dokumente
- Klare Attribute-Schemata
- Strukturierte Anweisungen

### 2. **Verbesserte Examples**
- 3 Beispiele statt 1
- Strukturierte Attribute
- Tabellen-Format-Unterstützung

### 3. **Absatzbasiertes Chunking**
- Statt Token-Limits: absatzbasierte Chunking
- Größere Chunks (5000 Zeichen)
- Mehr Überlappung (400 Zeichen)

### 4. **Robuste Fehlerbehandlung**
- Detaillierte Logs für jeden Chunk
- Fallback-Mechanismen
- Coverage-Berechnung

## 📁 Dateistruktur

```
backend_app_v2/
├── __init__.py          # Flask-App-Initialisierung
├── api_v2.py           # Teil 1: Hilfsfunktionen
├── api_v2_part2.py     # Teil 2: Korrigierte files_ingest
├── main.py             # Uvicorn-kompatibler Start
└── README.md           # Diese Datei
```

## 🏃‍♂️ Verwendung

### 1. **Starte die korrigierte Version:**

```bash
# Von Projekt-Root
cd backend_app_v2
python main.py
```

Oder mit Uvicorn:
```bash
uvicorn backend_app_v2.main:fastapi_app --host 0.0.0.0 --port 8082 --reload
```

### 2. **Teste die LangExtract-Funktionalität:**

```bash
# Test mit Requirements-Datei
curl -X POST http://localhost:8082/api/v1/files/ingest \
  -F "files=@../data/tool_performance_requirements.md" \
  -F "structured=1"
```

**Erwartete Verbesserungen:**
- `lxExtracted: 10` (statt 0)
- `lxPreview` enthält alle 10 Requirements
- Detaillierte Logs zeigen die Verarbeitung

### 2.1 Optionen (v2.1)

- **chunkMode**: `paragraph` | `token`
  - `paragraph` (Default): absatzbasiertes Chunking (große Chunks, overlap=400)
  - `token`: tokenbasiertes Chunking wie v1 (min/max/overlap Tokens)
- **preserveSources**: `1|0`
  - `1`: behält ursprüngliches `sourceFile` pro Dokument, chunking je Quelle
  - `0` (Default): kombiniert Texte zu einem „combined“-Dokument, einfacher Überblick

Beispiele:

```bash
# Paragraph + combined (Default)
curl -X POST http://localhost:8082/api/v1/files/ingest \
  -F "files=@../data/tool_performance_requirements.md" \
  -F "structured=1"

# Paragraph + preserveSources
curl -X POST http://localhost:8082/api/v1/files/ingest \
  -F "files=@../data/tool_performance_requirements.md" \
  -F "structured=1" \
  -F "preserveSources=1"

# Token-Chunking wie v1
curl -X POST http://localhost:8082/api/v1/files/ingest \
  -F "files=@../data/tool_performance_requirements.md" \
  -F "structured=1" \
  -F "chunkMode=token"
```

Response enthält zusätzlich:

```json
{
  "chunkMode": "paragraph",
  "preserveSources": false
}
```

### LangExtract Konfiguration (v2)

- `GET /api/v1/lx/config/list` – Liste verfügbarer Konfigurationen
- `GET /api/v1/lx/config/get?id=default` – Konfiguration laden
- `POST /api/v1/lx/config/save` – Konfiguration speichern
  - Body: `{ "configId": "mycfg", "prompt_description": "...", "examples": [...] }`
- `POST /api/v1/lx/extract` – führt LangExtract auf Text/Dateien aus und persistiert Ergebnis
- `GET /api/v1/lx/mine` – baut Items aus zuletzt gespeicherten LX-Ergebnissen

### 3. **Frontend verwenden:**

Besuche: `http://localhost:8082/mining_demo.html`

## 🔍 Was wurde korrigiert

### Vorher (Probleme):
- ❌ Generischer Prompt
- ❌ Nur 1 Beispiel
- ❌ Token-basierte Chunking (zerreißt Requirements)
- ❌ lxExtracted: 0

### Nachher (Lösungen):
- ✅ Spezifischer Requirements-Prompt
- ✅ 3 strukturierte Examples
- ✅ Absatzbasiertes Chunking
- ✅ lxExtracted: 10+ (erwartet)
 - ✅ Optional: token-Chunking + preserveSources in v2.1

## 📊 Vergleich mit dev/run_extract.py

| Aspekt | Alte API | Neue API V2 | dev/run_extract.py |
|--------|----------|-------------|-------------------|
| Prompt | Generisch | Spezifisch | Spezifisch ✅ |
| Examples | 1 | 3 | Mehrere ✅ |
| Chunking | Token | Absatz | Absatz ✅ |
| Logging | Minimal | Detailliert | Detailliert ✅ |
| Ergebnis | lxExtracted: 0 | lxExtracted: 10+ | Funktioniert ✅ |

## 🧪 Test-Szenarien

### 1. **Erfolgreicher Test:**
```json
{
  "lxEnabled": true,
  "lxExtracted": 10,
  "lxPreview": [
    {
      "extraction_class": "requirement",
      "extraction_text": "Das Tool MUSS die Antwortzeit messen",
      "attributes": {"priority": "must", "category": "performance_monitoring"}
    }
  ]
}
```

### 2. **Fehler-Test:**
```json
{
  "lxEnabled": false,
  "lxExtracted": 0,
  "error": "LangExtract setup failed"
}
```

## 🔄 Migration

Die alte `backend_app/` bleibt unverändert. Die neue Version läuft parallel auf Port 8082.

**Für Produktion:** Kopieren Sie die korrigierten Funktionen zurück in `backend_app/api.py`.

## 📈 Erwartete Performance

- **Vorher:** 0 Extraktionen aus tool_performance_requirements.md
- **Nachher:** 10+ Extraktionen mit korrekten Attributen
- **KG-Bau:** Erfolgreich aus lxPreview-Daten</content>
</edit_file>
</edit_file>