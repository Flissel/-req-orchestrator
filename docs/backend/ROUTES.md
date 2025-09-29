# Backend API Routenübersicht (Legacy Flask vs. FastAPI v2)

Ziel: Schneller Überblick über relevante Endpunkte, Parität zwischen Legacy (Flask) und v2 (FastAPI), sowie Deep-Links in den Code.

Hinweise
- Legacy-Blueprint: [`api_bp`](backend_app/api.py)
- v2 FastAPI App: [`fastapi_app`](backend_app_v2/main.py)
- V2 Router: [`vector_router`](backend_app_v2/routers/vector_router.py), [`validate_router`](backend_app_v2/routers/validate_router.py), [`gold_router`](backend_app_v2/routers/gold_router.py), [`structure_router`](backend_app_v2/routers/structure_router.py), [`lx_router`](backend_app_v2/routers/lx_router.py), [`corrections_router`](backend_app_v2/routers/corrections_router.py), [`batch_router`](backend_app_v2/routers/batch_router.py)

----------------------------------------------------------------

1) Health/Runtime
- GET /health
  - Legacy: [`health()`](backend_app/api.py:72)
  - v2: [`health()`](backend_app_v2/main.py:53)
- GET /api/runtime-config
  - Legacy: [`runtime_config()`](backend_app/api.py:76)
  - v2: via WSGI‑Mount (Legacy unter Root gemountet)
- GET /ready, GET /livez
  - v2: [`readiness()`](backend_app_v2/main.py:58), [`liveness()`](backend_app_v2/main.py:61)

----------------------------------------------------------------

2) Kriterien/Evaluation (Core)
- GET /api/v1/criteria
  - Legacy: [`list_criteria()`](backend_app/api.py:88)
- POST /api/v1/evaluations
  - Legacy: [`create_evaluation()`](backend_app/api.py:98)
- Batch Orchestrierung (siehe 6)

----------------------------------------------------------------

3) Corrections
- POST /api/v1/corrections/text
  - Legacy: [`save_correction_text()`](backend_app/api.py:220)
- POST /api/v1/corrections/decision
  - Legacy: [`set_correction_decision()`](backend_app/api.py:176)
- POST /api/v1/corrections/decision/batch
  - Legacy: [`set_correction_decision_batch()`](backend_app/api.py:320)
- v2 Pendant (z. T. integriert in Batch/Apply):
  - v2: [`corrections_router`](backend_app_v2/routers/corrections_router.py)

----------------------------------------------------------------

4) RAG / Vector
- Upload/Indexierung
  - POST /api/v1/files/ingest
    - Legacy: [`files_ingest()`](backend_app/api.py:1068)
    - Legacy (fixe Variante, integriert): [`files_ingest()`](backend_app/api_lx_fixed.py:154)
- Verwaltung
  - GET /api/v1/vector/collections
    - Legacy: [`vector_collections()`](backend_app/api.py:1140)
    - v2: [`vector_collections_v2()`](backend_app_v2/routers/vector_router.py:23)
  - GET /api/v1/vector/health
    - Legacy: [`vector_health()`](backend_app/api.py:1149)
    - v2: [`vector_health_v2()`](backend_app_v2/routers/vector_router.py:32)
  - POST/DELETE /api/v1/vector/reset
    - Legacy: [`vector_reset()`](backend_app/api.py:1158)
    - v2: [`vector_reset_v2()`](backend_app_v2/routers/vector_router.py:41)
  - GET /api/v1/vector/reset?confirm=1
    - Legacy: [`vector_reset_get()`](backend_app/api.py:1202)
    - v2: [`vector_reset_get_v2()`](backend_app_v2/routers/vector_router.py:77)
  - GET /api/v1/vector/source/full?source=...
    - Legacy: [`vector_source_full()`](backend_app/api.py:1233)
    - v2: [`vector_source_full_v2()`](backend_app_v2/routers/vector_router.py:101)
- Suche (RAG)
  - GET /api/v1/rag/search?query=...&top_k=5
    - Legacy: [`rag_search()`](backend_app/api.py:1286)
    - v2: [`rag_search_v2()`](backend_app_v2/routers/vector_router.py:148)
// ... existing code ...
    - Response-Format (v2):
      - hits: Liste von Treffern mit Feldern:
        - id: String (Qdrant Point ID)
        - score: Float (Ähnlichkeits-Score)
        - payload: Objekt (ursprüngliche gespeicherte Payload, z. B. text, sourceFile, chunkIndex)
        - metadata: Objekt (Alias auf payload, identischer Inhalt; eingeführt zur Rückwärtskompatibilität)
      - Hinweis: 'metadata' ist ein Alias zu 'payload' und enthält exakt die gleichen Schlüssel/Werte. Clients können wahlweise 'payload' oder 'metadata' verwenden.

      Beispiel:
      ```json
      {
        "query": "user authentication" ,
        "topK": 3,
        "collection": "requirements_v1",
        "hits": [
          {
            "id": "p1",
            "score": 0.9123,
            "payload": { "text": "hit-1", "sourceFile": "a.md", "chunkIndex": 0 },
            "metadata": { "text": "hit-1", "sourceFile": "a.md", "chunkIndex": 0 }
          },
          {
            "id": "p2",
            "score": 0.8745,
            "payload": { "text": "hit-2", "sourceFile": "b.md", "chunkIndex": 1 },
            "metadata": { "text": "hit-2", "sourceFile": "b.md", "chunkIndex": 1 }
          }
        ]
      }
      ```

----------------------------------------------------------------

5) LX (Extract/Gold/Evaluate v2)
- GET /api/v1/lx/config/preview?id=...
  - v2: [`lx_config_preview_v2()`](backend_app_v2/routers/lx_router.py:23)
- GET /api/v1/lx/gold/list
  - v2: [`lx_gold_list_fastapi()`](backend_app_v2/routers/gold_router.py:24)
- GET /api/v1/lx/gold/get?id=...
  - v2: [`lx_gold_get_fastapi()`](backend_app_v2/routers/gold_router.py:41)
- POST /api/v1/lx/gold/save
  - v2: [`lx_gold_save_fastapi()`](backend_app_v2/routers/gold_router.py:?)
- POST /api/v1/lx/evaluate
  - v2: [`lx_evaluate_fastapi()`](backend_app_v2/routers/gold_router.py:?)
- Struktur-Analyse
  - POST /api/v1/structure/analyze
    - v2: [`structure_analyze_v2()`](backend_app_v2/routers/structure_router.py:?)
  - POST /api/v1/structure/graph_export
    - v2: [`structure_graph_export_v2()`](backend_app_v2/routers/structure_router.py:?)

Hinweis: Die mit ? markierten Zeilen variieren je nach aktuellem Stand; die Datei [`gold_router`](backend_app_v2/routers/gold_router.py) enthält die vollständige Liste.

----------------------------------------------------------------

6) Validate/Batch/Streaming (Parität getestet)
- POST /api/v1/validate/suggest
  - v2: [`validate_suggest_v2()`](backend_app_v2/routers/validate_router.py:?)
- POST /api/v1/validate/batch
  - v2: [`validate_batch_v2()`](backend_app_v2/routers/validate_router.py:?)
- Streams (NDJSON)
  - POST /api/v1/validate/suggest/stream
  - POST /api/v1/validate/batch/stream
    - v2: [`StreamingResponse`](backend_app_v2/routers/validate_router.py:?)

Batch-Implementierung
- Kernprozesse: [`process_evaluations()`](backend_app/batch.py:100), [`process_suggestions()`](backend_app/batch.py:152), [`process_rewrites()`](backend_app/batch.py:217)
- Kontext-sicheres g: [`_safe_g_attr()`](backend_app/batch.py:?)

----------------------------------------------------------------

7) Agent/Memory (Legacy)
- POST /api/v1/agent/answer
  - Legacy: [`agent_answer()`](backend_app/api.py:1512)
- POST /api/v1/agent/mine_requirements
  - Legacy: [`agent_mine_requirements()`](backend_app/api.py:1675)
- MemoryStore
  - Legacy: [`MemoryStore`](backend_app/memory.py:?)

----------------------------------------------------------------

8) Frontend-Statisch (Legacy-Serve, v2 FastAPI + Static)
- Legacy-Static: [`create_app()`](backend_app/__init__.py:13)
- v2: FastAPI mit eingebettetem Flask (WSGI‑Mount): [`fastapi_app.mount("/", WSGIMiddleware(flask_app))`](backend_app_v2/main.py:49)

----------------------------------------------------------------

Parität und Tests
- Paritäts-Tests (MOCK_MODE=true): [`test_parity_core.py`](tests/parity/test_parity_core.py)
  - Validate Batch/Suggest, Corrections Apply, Vector/Health/Collections, RAG Search
- Patches/Monkeypatch:
  - [`patch_vector()`](tests/parity/conftest.py:?) setzt deterministische Embeddings/Vector-Stubs (auch gebundene Namen im v2‑Router)

----------------------------------------------------------------

Anmerkungen
- MOCK/Maintenance: Für Offline-/Determinismus in Tests werden in v2 gebundene Funktionsnamen in [`vector_router`](backend_app_v2/routers/vector_router.py) via [`conftest.py`](tests/parity/conftest.py) gepatcht.
- Observability v2: Request‑ID Header Middleware und Readiness/Livez in [`main.py`](backend_app_v2/main.py:?)
- CORS: Global in v2 aktiv (alle Methoden/Headers) in [`main.py`](backend_app_v2/main.py:31)