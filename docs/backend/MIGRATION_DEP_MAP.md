# Abhängigkeits-Inventar (Migration Flask → FastAPI v2)

Ziel: Überblick über Module, Verantwortlichkeiten, Seiteneffekte, ENV-abhängige Konfigurationen und wichtige Aufrufpfade. Dient als Leitfaden für Refactoring (Service-Layer) und schrittweise Migration.

----------------------------------------------------------------

Core-Konfiguration und Laufzeit
- Settings/Runtime
  - Quelle der Laufzeit-Config: [get_runtime_config()](backend_app/settings.py:108)
  - Settings-Modul: [backend_app/settings.py](backend_app/settings.py)
  - JSON-Log-Snapshot (Legacy): [log_runtime_config_once()](backend_app/logging_ext.py:248)
- App-Bootstrap
  - Legacy App-Factory: [create_app()](backend_app/__init__.py:13)
  - v2 FastAPI App inkl. Router-Registrierung und WSGI‑Mount: [fastapi_app](backend_app_v2/main.py:25)
  - v2 CORS-Policy: [backend_app_v2/main.py](backend_app_v2/main.py:31)
  - v2 Request-ID Middleware + Health/Readiness/Livez: [backend_app_v2/main.py](backend_app_v2/main.py:53)

----------------------------------------------------------------

LLM/Heuristik-Schicht
- LLM Sync/Apply (Legacy):
  - Evaluate/Suggest/Rewrite/Apply: [backend_app/llm.py](backend_app/llm.py)
  - Hauptaufrufe aus Legacy-API: z. B. [llm_evaluate()](backend_app/llm.py:102), [llm_apply_with_suggestions()](backend_app/llm.py:339)
- LLM Async (falls genutzt):
  - [backend_app/llm_async.py](backend_app/llm_async.py)

Seiteneffekte:
- Abhängigkeit von OPENAI_API_KEY/Model. Bei fehlendem Key greifen Heuristik-/Fallbackpfade (Legacy-Logik).

----------------------------------------------------------------

Datenhaltung/DB
- SQLite/DB‑Zugriffe:
  - DDL/Migrationen/Indices: [backend_app/db.py](backend_app/db.py)
  - Schema-Management: [ensure_schema_migrations()](backend_app/db.py:84)
- Batch-Resultat-Persistenz:
  - Evaluate/Rewrite-Zugriffe: [get_latest_rewrite_row_for_eval](backend_app/db.py:?) / [get_latest_evaluation_by_checksum](backend_app/db.py:?)

Seiteneffekte:
- Pfad/Datei abhängig von ENV (SQLITE_PATH), siehe [backend_app/settings.py](backend_app/settings.py)

----------------------------------------------------------------

Batch-Orchestrierung
- Kernprozesse:
  - ensure_evaluation_exists: [ensure_evaluation_exists()](backend_app/batch.py:28)
  - process_evaluations: [process_evaluations()](backend_app/batch.py:100)
  - process_suggestions: [process_suggestions()](backend_app/batch.py:152)
  - process_rewrites: [process_rewrites()](backend_app/batch.py:217)
- Flask g-Kontext Safe:
  - `_safe_g_attr` macht g‑Zugriffe kontext-sicher für FastAPI‑Aufrufe: [backend_app/batch.py](backend_app/batch.py:?) 

Aufrufer:
- Legacy-API Endpunkte für Validate/Suggest/Rewrite Streams: [backend_app/api.py](backend_app/api.py)
- v2 FastAPI Validate-Router: [backend_app_v2/routers/validate_router.py](backend_app_v2/routers/validate_router.py)

----------------------------------------------------------------

RAG / Embeddings / Vector (Qdrant)
- Embeddings:
  - Build/Dim: [build_embeddings()](backend_app/embeddings.py:59), [get_embeddings_dim()](backend_app/embeddings.py:?)
- Ingest/Chunking:
  - Extract/Chunk: [extract_texts()](backend_app/ingest.py:230), [chunk_payloads()](backend_app/ingest.py:287)
- Vector Store (Qdrant):
  - Client/Port-Fallback 6333/6401: [get_qdrant_client()](backend_app/vector_store.py:41)
  - Upsert: [upsert_points()](backend_app/vector_store.py:109)
  - Search: [search()](backend_app/vector_store.py:151)
  - Collections/Health/Reset: [list_collections()](backend_app/vector_store.py:?), [healthcheck()](backend_app/vector_store.py:?), [reset_collection()](backend_app/vector_store.py:197)
  - Fetch Window: [fetch_window_by_source_and_index](backend_app/vector_store.py:?)
- Legacy Routen:
  - files_ingest: [files_ingest()](backend_app/api.py:1068)
  - vector_* Verwaltung: [vector_collections()](backend_app/api.py:1140), [vector_health()](backend_app/api.py:1149), [vector_reset()](backend_app/api.py:1158), [vector_reset_get()](backend_app/api.py:1202)
  - rag_search: [rag_search()](backend_app/api.py:1286)
- v2 Routen:
  - Vector/RAG Router: [vector_router](backend_app_v2/routers/vector_router.py:20)
  - RAG v2: [rag_search_v2()](backend_app_v2/routers/vector_router.py:148)

Seiteneffekte:
- Externe Qdrant‑Verbindung (QDRANT_URL/PORT) und OpenAI Embeddings Model (EMBEDDINGS_MODEL)
- Tests patchen gebundene Importe (Determinismus, Offline): [patch_vector()](tests/parity/conftest.py:?)

----------------------------------------------------------------

LX (Extract/Gold/Evaluate) – v2 Fokus
- v2 LX Router:
  - Config Preview: [lx_config_preview_v2()](backend_app_v2/routers/lx_router.py:23)
  - Gold CRUD/Evaluate: [gold_router](backend_app_v2/routers/gold_router.py:11)
  - Struktur-Analyse: [structure_router](backend_app_v2/routers/structure_router.py:7)
  - Validate/Batch/Streams: [validate_router](backend_app_v2/routers/validate_router.py:11)

Seiteneffekte:
- Dateibasierte Artefakte (./data/lx_results/*.json, ./data/lx_gold/*.json)

----------------------------------------------------------------

Frontend/Static
- Einstiegsseiten:
  - Haupt-UI: [frontend/index.html](frontend/index.html)
  - Mining Demo: [frontend/mining_demo.html](frontend/mining_demo.html)
  - Reports: [frontend/reports.html](frontend/reports.html)
  - KG View: [frontend/kg_view.html](frontend/kg_view.html)
- API-Basis vereinheitlicht:
  - window.API_BASE → http://localhost:8087 (v2): [index.html](frontend/index.html), [mining_demo.html](frontend/mining_demo.html), [reports.html](frontend/reports.html), [kg_view.html](frontend/kg_view.html), [ui.html](ui.html)

----------------------------------------------------------------

Tests/Qualität
- Parität (Legacy vs v2):
  - Testfälle: [tests/parity/test_parity_core.py](tests/parity/test_parity_core.py)
  - Monkeypatch/Vector/Embeddings: [tests/parity/conftest.py](tests/parity/conftest.py)
- UI/Playwright:
  - Konfiguration: [playwright.config.ts](playwright.config.ts)
  - Flows (Auto-Refine, Apply, Filter): [tests/ui/auto-refine.spec.ts](tests/ui/auto-refine.spec.ts), [tests/ui/apply-suggestion.spec.ts](tests/ui/apply-suggestion.spec.ts), [tests/ui/modified-filter.spec.ts](tests/ui/modified-filter.spec.ts)

----------------------------------------------------------------

Empfohlene Service-Layer-Zuschnitte (Zielstruktur)
- evaluation_service.py
  - Kapselt [process_evaluations()](backend_app/batch.py:100) und [compute_verdict()](backend_app/utils.py:25)
- batch_service.py
  - Kapselt [process_suggestions()](backend_app/batch.py:152), [process_rewrites()](backend_app/batch.py:217), Stream-Iteratoren
- corrections_service.py
  - Kapselt Legacy-/v2‑Corrections‑Routen
- vector_service.py
  - Kapselt [search()](backend_app/vector_store.py:151), [reset_collection()](backend_app/vector_store.py:197), [list_collections()](backend_app/vector_store.py:?)
- rag_service.py
  - Kapselt [rag_search_v2()](backend_app_v2/routers/vector_router.py:148) und Embeddings‑Aufrufe
- lx_service.py
  - Kapselt v2 LX‑Funktionen ([lx_router](backend_app_v2/routers/lx_router.py:18), [gold_router](backend_app_v2/routers/gold_router.py:11), [structure_router](backend_app_v2/routers/structure_router.py:7))

----------------------------------------------------------------

ENV/Settings Übersicht (Auszug)
- API_HOST/API_PORT: [backend_app/settings.py](backend_app/settings.py)
- OPENAI_API_KEY/OPENAI_MODEL/EMBEDDINGS_MODEL: [backend_app/settings.py](backend_app/settings.py)
- QDRANT_URL/QDRANT_PORT/QDRANT_COLLECTION: [backend_app/settings.py](backend_app/settings.py)
- SQLITE_PATH: [backend_app/settings.py](backend_app/settings.py)
- Prompts (Dateipfade): [get_system_prompt()](backend_app/settings.py:71)

----------------------------------------------------------------

Migrationshinweise
- Legacy‑Blueprint [api_bp](backend_app/api.py:41) ist in v2 via WSGI unter Root gemountet → schrittweise Substituierung durch v2 Router.
- Tests sind grün (Parität) unter MOCK_MODE, v2 Routen sind bevorzugt für neue Features.
- Für Stabilität: gebundene Importe in v2‑Routern beachten (Monkeypatch in Tests vorhanden). Für Produktion: optional MOCK‑Shortpaths in v2 ergänzen (falls Offline‑Mode erforderlich).