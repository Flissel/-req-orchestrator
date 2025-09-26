# AutoGen RAC-Team (Planner, Solver, Verifier)

Dieses Dokument beschreibt das neue AutoGen 0.4+ basierte Requirements Architecture Chat Team (RAC) im Namespace `arch_team`. Das neue Team läuft parallel und unabhängig vom bestehenden `arch_team`-Flow und nutzt ausschließlich moderne AutoGen-APIs.

## Features

- Team aus drei `AssistantAgent`s: Planner, Solver, Verifier
- Termination: `TextMentionTermination("COVERAGE_OK")` ODER `MaxMessageTermination(10)`
- RAG-Tool (AutoGen-Tool) bindet den internen Retriever [`arch_team/memory/retrieval.py`](arch_team/memory/retrieval.py) ein
- .env-Unterstützung via `python-dotenv` (Pflicht-ENV: `OPENAI_API_KEY`; optional: `MODEL_NAME`)

## Installation

Aktualisiere/Installiere Abhängigkeiten:

```bash
pip install -U "autogen-agentchat" "autogen-core" "autogen-ext[openai]" python-dotenv qdrant-client
```

Hinweis: Der interne Retriever verwendet Embeddings-Helfer aus `backend_app/embeddings.py`. Stelle sicher, dass dortige Requirements (z. B. OpenAI-Embeddings) erfüllt sind.

## ENV (.env)

Lege im Projektverzeichnis eine `.env` an:

```
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o  # optional, Default gpt-4o
ARCH_TASK=Mine requirements for our backend platform focusing security, performance, ops and UX. Return REQ-IDs and tags.
```

- `OPENAI_API_KEY` ist Pflicht, andernfalls stoppt das Skript mit einer verständlichen Fehlermeldung.
- `MODEL_NAME` ist optional (Default: `gpt-4o`).
- `ARCH_TASK` optional, Standard-Task siehe oben.

## Start

Starte das RAC-Team per Modul:

```bash
python -m arch_team.autogen_rac
```

- Streamt die Konversation in die Konsole.
- Beendet automatisch, wenn der Text `COVERAGE_OK` auftaucht oder nach maximal 10 Nachrichten.

## Team-Prompts (Kurz)

- Planner:
  - Ziel: Minimalen, umsetzbaren Plan mit 3–5 Schritten für Requirements Mining.
  - Ende mit `HANDOFF: solver`.
- Solver:
  - Nutzt Tools.
  - Extrahiert Liste mit stabilen IDs `REQ-001..`, kurze Beschreibung, Tag in `{functional|security|performance|ux|ops}`.
  - Wenn Abdeckung ausreichend: Am Ende `COVERAGE_OK`.
- Verifier:
  - Prüft die Liste auf Deckung und Tags (mindestens ~5 Einträge).
  - Wenn ausreichend: exakt `COVERAGE_OK`, sonst kurze `CRITIQUE` mit konkreten Hinweisen.

## Dateien

- Neuer Entry-Point: [`arch_team/autogen_rac.py`](arch_team/autogen_rac.py)
- Tools-Paket:
  - [`arch_team/autogen_tools/__init__.py`](arch_team/autogen_tools/__init__.py)
  - [`arch_team/autogen_tools/requirements_rag.py`](arch_team/autogen_tools/requirements_rag.py) — AutoGen-Tool `search_requirements(query: str, top_k: int = 5)`

## Fehlerbehandlung / Troubleshooting

- Fehlender API-Key:
  - Ausgabe: `ERROR: OPENAI_API_KEY ist leer oder nicht gesetzt...`
  - Lösung: `.env` mit gültigem `OPENAI_API_KEY` anlegen.
- Fehlende Pakete (z. B. `autogen_agentchat`):
  - `pip install -U "autogen-agentchat" "autogen-core" "autogen-ext[openai]" python-dotenv qdrant-client`
- Qdrant/Embeddings nicht verfügbar:
  - Das RAG-Tool gibt dann eine freundliche Meldung wie `RAG not configured or no hits for '...'` zurück.