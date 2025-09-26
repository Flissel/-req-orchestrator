# 10 Showcases – aus diesem Template ableitbar

Hinweis
- Alle Flows nutzen ausschließlich die vorhandenen Module/Endpunkte dieses Repos.
- Deep-Links sind klickbar und verweisen auf Dateien oder Sprachelemente inkl. Zeilenangaben, z. B. [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599), [frontend/app_optimized.js](../../frontend/app_optimized.js).

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
- [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599)

Beispiel
```
export API_BASE="http://localhost:8081"
curl -s -X POST "$API_BASE/api/v1/validate/batch" \
  -H "Content-Type: application/json" \
  -d '{"items":["System shall respond within 200 ms (p95)."],"includeSuggestions":true}' | jq .
```

Wesentliche Pfade
- Evaluation sichern/ermitteln: [backend_app.batch.ensure_evaluation_exists()](../../backend_app/batch.py:28)
- Scoring/Decision: [backend_app.utils.weighted_score()](../../backend_app/utils.py:14), [backend_app.utils.compute_verdict()](../../backend_app/utils.py:25)
- Heuristik-Fallback: [backend_app.llm.llm_evaluate()](../../backend_app/llm.py:102)

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
- Server: [backend_app.api.validate_suggest()](../../backend_app/api.py:571) → [backend_app.batch.process_suggestions()](../../backend_app/batch.py:152)

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
- Server: [backend_app.api.apply_corrections()](../../backend_app/api.py:255) → [backend_app.llm.llm_apply_with_suggestions()](../../backend_app/llm.py:339)

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
- [backend_app.batch.batch_evaluate()](../../backend_app/batch.py:282)
- [backend_app.batch.batch_suggest()](../../backend_app/batch.py:301)
- [backend_app.batch.batch_rewrite()](../../backend_app/batch.py:319)

Hilfen
- Markdown-Parser: [backend_app.utils.parse_requirements_md()](../../backend_app/utils.py:39)
- Merge-Tabelle: [backend_app.batch.merged_markdown()](../../backend_app/batch.py:66)

Konfiguration
- [.env REQUIREMENTS_MD_PATH](../../.env) → Pfad zur Markdown-Tabelle
- [.env OUTPUT_MD_PATH](../../.env) → optionaler Ausgabepfad für serverseitige „merged“ MD

----------------------------------------------------------------

## 5) RAG Suche „einfach“ (kurz)

Ziel
- Abfrage in Vektorraum, Treffer inkl. Quelle/Chunk ansehen.

Endpunkt
- [backend_app.api.rag_search()](../../backend_app/api.py:1286)

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
- [backend_app.api.files_ingest()](../../backend_app/api.py:1068)

Form-Data (Beispiel)
```
curl -s -X POST "$API_BASE/api/v1/files/ingest" \
  -F "files=@./docs/requirements.md;type=text/markdown" \
  -F "chunkMin=200" -F "chunkMax=400" -F "chunkOverlap=50" \
  -F "collection=requirements_v1" | jq .
```

Pipeline
- Extraktion: [backend_app.ingest.extract_texts()](../../backend_app/ingest.py:230)
- Chunking: [backend_app.ingest.chunk_payloads()](../../backend_app/ingest.py:287)
- Embeddings: [backend_app.embeddings.build_embeddings()](../../backend_app/embeddings.py:59)
- Upsert: [backend_app.vector_store.upsert_points()](../../backend_app/vector_store.py:109)

----------------------------------------------------------------

## 7) Agent-/Memory Antwort (lang)

Ziel
- Policy-/Memory-gestützte Antwort, Re-Ranking bevorzugter Quellen, Agent-Notizen.

Endpunkt
- [backend_app.api.agent_answer()](../../backend_app/api.py:1512)

Policies/Memory
- Default-Policies: [backend_app.memory.MemoryStore.load_policies()](../../backend_app/memory.py:71)
- Eventlog: [backend_app.memory.MemoryStore.append_event()](../../backend_app/memory.py:37)

Ranking/Context
- Re-Ranking: [backend_app.api._re_rank_hits()](../../backend_app/api.py:1389)
- Kontextfenster: [backend_app.api._build_context_from_hit()](../../backend_app/api.py:1412)

Optionaler Worker (Dokumenten-Mining)
- [agent_worker.app.mine()](../../agent_worker/app.py:261), [agent_worker.app.mine_team()](../../agent_worker/app.py:721)

----------------------------------------------------------------

## 8) Vector-Index Admin (kurz)

Ziel
- Reset, Health, Collections.

Endpunkte
- Reset: [backend_app.api.vector_reset()](../../backend_app/api.py:1158) / [backend_app.api.vector_reset_get()](../../backend_app/api.py:1202)
- Health/List: [backend_app.api.vector_health()](../../backend_app/api.py:1149), [backend_app.api.vector_collections()](../../backend_app/api.py:1140)

Hinweis UI
- Frontend-Button „Reset index“: [frontend/index.html](../../frontend/index.html), Handler [frontend.app_optimized.resetIndex()](../../frontend/app_optimized.js:424)

----------------------------------------------------------------

## 9) NDJSON Streaming-Validate (mittel)

Ziel
- Ergebnisse pro Item als NDJSON streamen (UX: erste Resultate sehr früh).

Endpunkte
- [backend_app.api.validate_batch_stream()](../../backend_app/api.py:828)
- [backend_app.api.validate_suggest_stream()](../../backend_app/api.py:967)

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
- App-Bootstrap: [backend_app.__init__.create_app()](../../backend_app/__init__.py:13)
- DB DDL/Migration: [backend_app.db.DDL](../../backend_app/db.py:11), [backend_app.db.ensure_schema_migrations()](../../backend_app/db.py:84)
- CORS/Preflight: [backend_app.__init__._global_api_preflight()](../../backend_app/__init__.py:37), [backend_app.api.options_cors_catch_all()](../../backend_app/api.py:45)