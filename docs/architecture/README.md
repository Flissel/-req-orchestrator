# Architektur-Index

Ziel: Zentrale Einstiegspunkt für alle Architektur-/Feature-/Stack-Dokumente, inkl. klickbarer Deep-Links in den Code.

Hinweis zur Link-Konvention:
- Sprachelemente werden als z. B. [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599) verlinkt (mit Zeile).
- Dateien werden als z. B. [docs/architecture/SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) verlinkt.


----------------------------------------------------------------

## 1) Systemüberblick und Abhängigkeits-Matrix

- Überblick & End-to-End-Logik: [docs/architecture/SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- Kern-Bootstrap: [backend_app.__init__.create_app()](../../backend_app/__init__.py:13)
- Wichtigste API-Orchestrierung: [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599)


----------------------------------------------------------------

## 2) Features, Diagramme, Stacks

- Features & Stacks (kompakt, mit Diagrammen): [docs/architecture/FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
- Einzel-Feature-Doks (nach und nach separat ausführlich):
  - Validate Batch → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
  - Suggestions + Apply (merge) → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
  - Auto-Refine (Detaildoku vorhanden): [docs/feature-auto-refine.md](../feature-auto-refine.md)
  - Files Ingest → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
  - RAG Search → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
  - Agent Answer → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)
  - Vector Reset → siehe Abschnitt in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md)

Geplante Aufteilung (dedizierte Dateien):
- features/validate-batch.md
- features/suggestions-apply.md
- features/files-ingest.md
- features/rag-search.md
- features/agent-answer.md
- features/vector-reset.md

Alle Inhalte sind bereits in [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md) enthalten; die oben genannten Dateien werden bei Bedarf als Deep-Dives ergänzt.


----------------------------------------------------------------

## 3) Technologie-Stacks

- Backend/Flask: siehe [backend_app.__init__.create_app()](../../backend_app/__init__.py:13), [backend_app.api.*](../../backend_app/api.py)
- LLM/OpenAI: [backend_app.llm.llm_evaluate()](../../backend_app/llm.py:102), [backend_app.llm.llm_suggest()](../../backend_app/llm.py:158), [backend_app.llm.llm_rewrite()](../../backend_app/llm.py:253), [backend_app.llm.llm_apply_with_suggestions()](../../backend_app/llm.py:339)
- Vector/Qdrant: [backend_app.vector_store.get_qdrant_client()](../../backend_app/vector_store.py:41), [backend_app.vector_store.search()](../../backend_app/vector_store.py:151)
- Frontend/UI: [frontend/app_optimized.js](../../frontend/app_optimized.js)
- Tests/Playwright: [tests/ui/auto-refine.spec.ts](../../tests/ui/auto-refine.spec.ts), [playwright.config.ts](../../playwright.config.ts)
- Docker/Infra: [Dockerfile](../../Dockerfile), [docker-compose.qdrant.yml](../../docker-compose.qdrant.yml)

Hinweis: Eigene Stack-Dateien (stacks/*.md) sind optional, da [FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md) bereits pro Stack zusammenfasst.


----------------------------------------------------------------

## 4) Showcases (10 Varianten)

- Übersicht: [docs/showcases/README.md](../showcases/README.md)
- Vollständige Sammlung: [docs/showcases/ALL_SHOWCASES.md](../showcases/ALL_SHOWCASES.md)

Abdeckung u. a.:
- Evaluate-Only API
- Suggestions → Apply → Re-Analyze
- Auto-Refine Loop
- Markdown-Batch „Merge-Report“
- RAG Search, Files Ingest → Qdrant
- Agent-/Memory Antwort
- Vector Admin (Reset/Health/Collections)
- NDJSON Streaming-Validate
- RAG Benchmark Suite


----------------------------------------------------------------

## 5) C4-Übersicht (Zielbild)

- Aktuelle C4-Preview: [docs/architecture/C4.md](./C4.md)

Bezüge (Beispiele):
- System-Kontext: Backend (Flask API), Frontend (statische Auslieferung), SQLite, OpenAI, Qdrant
- Komponenten: API-Layer [backend_app.api](../../backend_app/api.py), LLM-Wrapper [backend_app.llm](../../backend_app/llm.py), Vector-Store [backend_app.vector_store](../../backend_app/vector_store.py), Logging [backend_app.logging_ext](../../backend_app/logging_ext.py)


----------------------------------------------------------------

## 6) Relevante Code-Deep-Links (Kurzliste)

- API Kern-Endpunkte: [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599), [backend_app.api.files_ingest()](../../backend_app/api.py:1068), [backend_app.api.rag_search()](../../backend_app/api.py:1286), [backend_app.api.agent_answer()](../../backend_app/api.py:1512)
- Batch-Prozesse: [backend_app.batch.ensure_evaluation_exists()](../../backend_app/batch.py:28), [backend_app.batch.process_evaluations()](../../backend_app/batch.py:100), [backend_app.batch.process_suggestions()](../../backend_app/batch.py:152), [backend_app.batch.process_rewrites()](../../backend_app/batch.py:217)
- LLM Integration: [backend_app.llm.llm_evaluate()](../../backend_app/llm.py:102), [backend_app.llm.llm_apply_with_suggestions()](../../backend_app/llm.py:339)
- Vektor-DB: [backend_app.vector_store.upsert_points()](../../backend_app/vector_store.py:109)
- Frontend Auto-Refine: [frontend.app_optimized.autoRefineIndex()](../../frontend/app_optimized.js:1947)


----------------------------------------------------------------

## 7) Betrieb/Debug

- Runtime-Konfiguration (Snapshot): [backend_app.settings.get_runtime_config()](../../backend_app/settings.py:108), Logging beim Start via [backend_app.logging_ext.log_runtime_config_once()](../../backend_app/logging_ext.py:248)
- CORS/Preflight: [backend_app.__init__._global_api_preflight()](../../backend_app/__init__.py:37), [backend_app.api.options_cors_catch_all()](../../backend_app/api.py:45)
- DB DDL/Migrationen: [backend_app.db.DDL](../../backend_app/db.py:11), [backend_app.db.ensure_schema_migrations()](../../backend_app/db.py:84)


----------------------------------------------------------------

Stand: generiert aus aktueller Arbeitskopie. Alle Links beziehen sich auf diese Repository-Struktur.