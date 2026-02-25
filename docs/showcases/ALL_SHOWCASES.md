# 10 Showcases – aus diesem Template ableitbar

Hinweis
- Alle Flows nutzen ausschließlich die vorhandenen Module/Endpunkte dieses Repos.
- Deep-Links sind klickbar und verweisen auf Dateien oder Sprachelemente inkl. Zeilenangaben, z. B. [backend.core.api.validate_batch_optimized()](../../backend/core/api.py:599), [frontend/app_optimized.js](../../frontend/app_optimized.js).

Inhalt
1. Evaluate-Only API (kurz)
2. Suggestions → Apply (merge) → Re-Analyze (mittel)
3. Auto-Refine UI Loop (lang)
4. Markdown-Batch Verarbeitung (mittel)
5. RAG Suche „einfach“ (kurz)
6. Datei-Ingest → Qdrant-Index (mittel)
7. Agent-/Memory Antwort (lang)
8. Vector-Index Admin (kurz)
9. NDJSON Streaming-Validate (mittel)
10. RAG Benchmark Suite (lang)

----------------------------------------------------------------

## 1) Evaluate-Only API (kurz)

Ziel
- Schnelle Bewertung eines einzelnen Requirements ohne UI.

Primärer Endpunkt
- [backend.core.api.validate_batch_optimized()](../../backend/core/api.py:599)

Beispiel
```
export API_BASE="http://localhost:8081"
curl -s -X POST "$API_BASE/api/v1/validate/batch" \
  -H "Content-Type: application/json" \
  -d '{"items":["System shall respond within 200 ms (p95)."],"includeSuggestions":true}' | jq .
```

Wesentliche Pfade
- Evaluation sichern/ermitteln: [backend.core.batch.ensure_evaluation_exists()](../../backend/core/batch.py:28)
- Scoring/Decision: [backend.core.utils.weighted_score()](../../backend/core/utils.py:14), [backend.core.utils.compute_verdict()](../../backend/core/utils.py:25)
- Heuristik-Fallback: [backend.core.llm.llm_evaluate()](../../backend/core/llm.py:102)

----------------------------------------------------------------

## 2) Suggestions → Apply (merge) → Re-Analyze (mittel)

Ziel
- Vorschläge generieren, konsolidieren und erneut bewerten.

Ablauf
1) Vorschläge
```
curl -s -X POST "$API_BASE/api/v1/validate/suggest" \
  -H "Content-Type: application/json" \
  -d '["The API shall return JSON."]' | jq .
```
- Server: [backend.core.api.validate_suggest()](../../backend/core/api.py:571) → [backend.core.batch.process_suggestions()](../../backend/core/batch.py:152)

2) Apply (merge)
```
curl -s -X POST "$API_BASE/api/v1/corrections/apply" \
  -H "Content-Type: application/json" \
  -d @- <<'JSON'
{
  "originalText": "The API shall return JSON.",
  "selectedSuggestions": [
    { "correction": "The API shall return {\"status\":\"ok\"} as JSON object." }
  ],
  "mode": "merge",
  "context": {}
}
JSON
```
- Server: [backend.core.api.apply_corrections()](../../backend/core/api.py:255) → [backend.core.llm.llm_apply_with_suggestions()](../../backend/core/llm.py:339)

3) Re-Analyse
- POST /api/v1/validate/batch mit dem „merged“ Text (s. Showcase 1)

UI-Referenzen (bei Nutzung des Frontends)
- [frontend.app_optimized.ensureSuggestions()](../../frontend/app_optimized.js:162)
- [frontend.app_optimized.mergeApply()](../../frontend/app_optimized.js:211)
- [frontend.app_optimized.reanalyzeIndex()](../../frontend/app_optimized.js:1834)

----------------------------------------------------------------

## 3) Auto-Refine UI Loop (lang)

Ziel
- Automatisches Erreichen des Release-Gates (OK oder Score ≥ Threshold), sonst Eskalation „Review“.

Kernlogik (Frontend)
- Gates/Heuristik: [frontend.app_optimized.computeOk()](../../frontend/app_optimized.js:25), [frontend.app_optimized.releaseOk()](../../frontend/app_optimized.js:53)
- Loop: [frontend.app_optimized.autoRefineIndex()](../../frontend/app_optimized.js:1947), [frontend.app_optimized.autoRefineMany()](../../frontend/app_optimized.js:2017)
- UI-Schalter „Use modified“: [frontend.app_optimized.getVisibleIndexes()](../../frontend/app_optimized.js:81)

Testfälle (Playwright)
- [tests/ui/auto-refine.spec.ts](../../tests/ui/auto-refine.spec.ts)

Ablauf (vereinfacht)
1) Suggestions sicherstellen (falls fehlen)
2) Apply (merge) erzeugt neuen Text
3) Validate-Batch mit neuem Text
4) Gate-Check → ggf. Wiederholung oder „Review“-Badge

----------------------------------------------------------------

## 4) Markdown-Batch Verarbeitung (mittel)

Ziel
- Serverseitig Requirements aus Markdown-Tabelle verarbeiten und Merge-Report erzeugen.

Wichtige Endpunkte
- [backend.core.batch.batch_evaluate()](../../backend/core/batch.py:282)
- [backend.core.batch.batch_suggest()](../../backend/core/batch.py:301)
- [backend.core.batch.batch_rewrite()](../../backend/core/batch.py:319)

Hilfen
- Markdown-Parser: [backend.core.utils.parse_requirements_md()](../../backend/core/utils.py:39)
- Merge-Tabelle: [backend.core.batch.merged_markdown()](../../backend/core/batch.py:66)

Konfiguration
- [.env REQUIREMENTS_MD_PATH](../../.env) → Pfad zur Markdown-Tabelle
- [.env OUTPUT_MD_PATH](../../.env) → optionaler Ausgabepfad für serverseitige „merged“ MD

----------------------------------------------------------------

## 5) RAG Suche „einfach“ (kurz)

Ziel
- Abfrage in Vektorraum, Treffer inkl. Quelle/Chunk ansehen.

Endpunkt
- [backend.core.api.rag_search()](../../backend/core/api.py:1286)

Voraussetzung
- Ingest durchgeführt (Showcase 6)

Beispiel
```
curl -s "$API_BASE/api/v1/rag/search?query=health%20endpoint&top_k=5" | jq .
```

----------------------------------------------------------------

## 6) Datei-Ingest → Qdrant-Index (mittel)

Ziel
- Dokumente hochladen, extrahieren, chunken, embedden, upserten.

Endpunkt
- [backend.core.api.files_ingest()](../../backend/core/api.py:1068)

Form-Data (Beispiel)
```
curl -s -X POST "$API_BASE/api/v1/files/ingest" \
  -F "files=@./docs/requirements.md;type=text/markdown" \
  -F "chunkMin=200" -F "chunkMax=400" -F "chunkOverlap=50" \
  -F "collection=requirements_v1" | jq .
```

Pipeline
- Extraktion: [backend.core.ingest.extract_texts()](../../backend/core/ingest.py:230)
- Chunking: [backend.core.ingest.chunk_payloads()](../../backend/core/ingest.py:287)
- Embeddings: [backend.core.embeddings.build_embeddings()](../../backend/core/embeddings.py:59)
- Upsert: [backend.core.vector_store.upsert_points()](../../backend/core/vector_store.py:109)

----------------------------------------------------------------

## 7) Agent-/Memory Antwort (lang)

Ziel
- Policy-/Memory-gestützte Antwort, Re-Ranking bevorzugter Quellen, Agent-Notizen.

Endpunkt
- [backend.core.api.agent_answer()](../../backend/core/api.py:1512)

Policies/Memory
- Default-Policies: [backend.core.memory.MemoryStore.load_policies()](../../backend/core/memory.py:71)
- Eventlog: [backend.core.memory.MemoryStore.append_event()](../../backend/core/memory.py:37)

Ranking/Context
- Re-Ranking: [backend.core.api._re_rank_hits()](../../backend/core/api.py:1389)
- Kontextfenster: [backend.core.api._build_context_from_hit()](../../backend/core/api.py:1412)

Optionaler Worker (Dokumenten-Mining)
- [agent_worker.app.mine()](../../agent_worker/app.py:261), [agent_worker.app.mine_team()](../../agent_worker/app.py:721)

----------------------------------------------------------------

## 8) Vector-Index Admin (kurz)

Ziel
- Reset, Health, Collections.

Endpunkte
- Reset: [backend.core.api.vector_reset()](../../backend/core/api.py:1158) / [backend.core.api.vector_reset_get()](../../backend/core/api.py:1202)
- Health/List: [backend.core.api.vector_health()](../../backend/core/api.py:1149), [backend.core.api.vector_collections()](../../backend/core/api.py:1140)

Hinweis UI
- Frontend-Button „Reset index“: [frontend/index.html](../../frontend/index.html), Handler [frontend.app_optimized.resetIndex()](../../frontend/app_optimized.js:424)

----------------------------------------------------------------

## 9) NDJSON Streaming-Validate (mittel)

Ziel
- Ergebnisse pro Item als NDJSON streamen (UX: erste Resultate sehr früh).

Endpunkte
- [backend.core.api.validate_batch_stream()](../../backend/core/api.py:828)
- [backend.core.api.validate_suggest_stream()](../../backend/core/api.py:967)

Client-Hinweise
- Browser: fetch + ReadableStream, zeilenweise JSON parse
- CLI: `curl --no-buffer` oder `wget -O -`

----------------------------------------------------------------

## 10) RAG Benchmark Suite (lang)

Ziel
- Heuristische Qualitätseinschätzung & Reporting.

Script
- [tests/rag_benchmark.py](../../tests/rag_benchmark.py)

Artefakte
- JSON: tests/out/rag_report.json
- Markdown: tests/out/rag_report.md

Metriken
- Keyword-Overlap: [tests.rag_benchmark.keyword_overlap()](../../tests/rag_benchmark.py:38)
- Referenz-Ähnlichkeit: [tests.rag_benchmark.ref_similarity()](../../tests/rag_benchmark.py:50)

----------------------------------------------------------------

Anhang (Kurz-Referenzen)
- App-Bootstrap: [backend.core.__init__.create_app()](../../backend/core/__init__.py:13)
- DB DDL/Migration: [backend.core.db.DDL](../../backend/core/db.py:11), [backend.core.db.ensure_schema_migrations()](../../backend/core/db.py:84)
- CORS/Preflight: [backend.core.__init__._global_api_preflight()](../../backend/core/__init__.py:37), [backend.core.api.options_cors_catch_all()](../../backend/core/api.py:45)