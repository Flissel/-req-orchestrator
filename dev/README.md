# LangExtract Dev-Pipeline

Dieser Dev-Ordner enthält eine lauffähige, minimalistische Extraktions-Pipeline auf Basis von LangExtract. Ziel: Markdown-Anforderungen einlesen, in Chunks zerlegen, strukturierte Extraktionen mit exaktem Span-Grounding erzeugen, als JSONL exportieren und optional als interaktive HTML-Visualisierung überprüfen.

Wichtigste Datei:
- [dev/run_extract.py](dev/run_extract.py)

Standard-Eingabe:
- [data/requirements.out.md](data/requirements.out.md)

Ausgabeziel:
- [dev/output](dev/output) (wird beim Lauf automatisch angelegt)


## Funktionsumfang

- Einlesen einer Markdown-Quelldatei
- Chunking mit konfigurierbarer Größe und Überlappung
- Extraktion gemäß Angaben in Prompt und Beispielen mit Span-Grounding
- Speicherung als JSONL
- Generierung eines eigenständigen, interaktiven HTML-Reports zur Review


## Voraussetzungen

- Python 3.10 oder neuer
- pip
- LangExtract (wird per pip installiert)
- Für Cloud-Modelle: korrekte API-/Provider-Konfiguration in der Umgebung
- Für lokale Modelle: funktionsfähige lokale Inferenz (z. B. Ollama) und passender Modellname


## Installation

Windows (cmd):

1. Virtuelle Umgebung anlegen und aktivieren
   - python -m venv .venv
   - .venv\Scripts\activate

2. Pakete installieren
   - python -m pip install --upgrade pip
   - pip install langextract

Hinweis: Abhängig vom gewählten Modell/Provider sind zusätzlich Umgebungsvariablen oder Konfigurationsschritte notwendig (z. B. API-Key). Bitte den jeweiligen Provider-Hinweisen folgen.


## Konfiguration

Das Skript liest optionale Umgebungsvariablen:

- LX_INPUT: Pfad zur Eingabedatei
  - Default: data/requirements.out.md
- LX_OUTPUT_DIR: Ausgabeverzeichnis
  - Default: dev/output
- LX_MODEL_ID: Modell-ID
  - Default: gemini-2.5-flash
  - Beispiele: ein Cloud-Modell aus der Gemini-Familie oder ein lokales Ollama-Modellname
- LX_CHUNK_SIZE: Chunk-Limit in Zeichen
  - Default: 5000
- LX_CHUNK_OVERLAP: Überlappung in Zeichen
  - Default: 400


## Ausführung

Windows (cmd), im Projekt-Root:

1. Optional Umgebungsvariablen setzen, z. B.:
   - set LX_INPUT=data\requirements.out.md
   - set LX_MODEL_ID=gemini-2.5-flash
   - set LX_CHUNK_SIZE=5000
   - set LX_CHUNK_OVERLAP=400
   - set LX_OUTPUT_DIR=dev\output

2. Pipeline starten:
   - python dev\run_extract.py

Ergebnis:
- JSONL-Export liegt in [dev/output](dev/output) mit Zeitstempel im Dateinamen
- Interaktive HTML-Visualisierung liegt ebenfalls in [dev/output](dev/output)


## Hinweise zur Qualität

- Schema schlank und präzise halten, klare Klassen und Attribute definieren
- Wenige, hochwertige Beispiele mit exakten Textspannen
- Überlappung moderat wählen, um Kantenverluste zu vermeiden
- Nach der Extraktion Dubletten/Überlappungen konsolidieren
- Stichprobenhaft die HTML-Visualisierung prüfen


## Fehlerbehandlung und Limits

- Rate-Limits und Zeitüberschreitungen des Modells mit retries/backoff adressieren
- Chunk-Größe und Überlappung beeinflussen Kosten, Latenz und Dublettenquote
- Grounding-Offsets beziehen sich auf den tatsächlich verarbeiteten Text; starke Vorverarbeitung kann sich auf Offsets auswirken


## Anpassungen

- Prompt/Textbeispiele im Skript anpassen, um Domänenklassen, Attribute und Benennungen zu schärfen
- Modellwahl über LX_MODEL_ID variieren
- Chunking-Parameter feinjustieren, bis Recall/Präzision und Kosten im Zielbereich liegen