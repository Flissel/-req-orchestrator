# Showcases (10 Varianten aus diesem Template ableitbar)

Diese Sammlung enthält 10 praxisnahe, unterschiedlich lange Showcase-Szenarien. Alle Flows basieren ausschließlich auf dieser Codebasis. Verlinkungen führen direkt in die Implementierung (klickbar bis auf Funktionen/Zeilen).

Weitere Systemübersicht:
- [docs/architecture/SYSTEM_OVERVIEW.md](../architecture/SYSTEM_OVERVIEW.md)
- Feature-/Stack-Übersichten: [docs/architecture/FEATURES_AND_STACKS.md](../architecture/FEATURES_AND_STACKS.md)

Hinweis Link-Konvention:
- Sprachelement: z. B. [backend.core.api.validate_batch_optimized()](../../backend/core/api.py:599)
- Datei: z. B. [frontend/app_optimized.js](../../frontend/app_optimized.js)


----------------------------------------------------------------

## 1) Evaluate-Only API (Kurz, API-fokussiert)

Ziel
- Ein einzelnes Requirement (oder Array) gegen die Bewertungslogik prüfen.

Primärer Endpunkt
- [backend.core.api.validate_batch_optimized()](../../backend/core/api.py:599)

Beispiel
```
curl -s -X POST "$API_BASE/api/v1/validate/batch" \
  -H "Content-Type: application/json" \
  -d '{"items":["System shall respond within 200 ms (p95)."],"includeSuggestions":true}' | jq .
```

Was passiert intern
- Sicherung oder Erstellung der Evaluation: [backend.core.batch.ensure_evaluation_exists()](../../backend/core/batch.py:28)
- LLM-/Heuristikbewertung: [backend.core.llm.llm_evaluate()](../../backend/core/llm.py:102)
- Aggregation/Decision: [backend.core.utils.weighted_score()](../../backend/core/utils.py:14), [backend.core.utils.compute_verdict()](../../backend/core/utils.py:25)


----------------------------------------------------------------

## 2) Suggestions → Apply (merge) → Re-Analyze (Mittel, Editing-Flow)

Ziel
- Zu einem Text atomare Vorschläge abrufen, konsolidieren und neu bewerten.

Endpunkte
- Vorschläge: [backend.core.api.validate_suggest()](../../backend/core/api.py:571)
- Anwenden: [backend.core.api.apply_corrections()](../../backend/core/api.py:255) → [backend.core.llm.llm_apply_with_suggestions()](../../backend/core/llm.py:339)
- Re-Analyse: [backend.core.api.validate_batch_optimized()](../../backend/core/api.py:599)

Ablauf (vereinfacht)
1. POST /api/v1/validate/suggest mit `[originalText]`
2. POST /api/v1/corrections/apply mit `selectedSuggestions` und `mode:"merge"`
3. POST /api/v1/validate/batch mit dem zusammengeführten Text

UI-Referenzen
- [frontend.app_optimized.ensureSuggestions()](../../frontend/app_optimized.js:162)
- [frontend.app_optimized.mergeApply()](../../frontend/app_optimized.js:211)
- [frontend.app_optimized.reanalyzeIndex()](../../frontend/app_optimized.js:1834)


----------------------------------------------------------------

## 3) Auto-Refine (Loop bis Release-Gate) (Lang, UI-automatisiert)

Ziel
- Vollautomatisches Erreichen des Release-Gates (OK oder Score ≥ Threshold), ansonsten Eskalation auf Review.

Kernlogik (Frontend)
- Gate/Heuristik: [frontend.app_optimized.computeOk()](../../frontend/app_optimized.js:25), [frontend.app_optimized.releaseOk()](../../frontend/app_optimized.js:53)
- Loop: [frontend.app_optimized.autoRefineIndex()](../../frontend/app_optimized.js:1947), [frontend.app_optimized.autoRefineMany()](../../frontend/app_optimized.js:2017)

Backend-Aufrufe
- Suggest → Apply → Validate Batch (siehe Showcase 2)

Testabdeckung (Playwright)
- [tests/ui/auto-refine.spec.ts](../../tests/ui/auto-refine.spec.ts)


----------------------------------------------------------------

## 4) Markdown-Batch Verarbeitung (Server-Quelle, „Merge-Report“) (Mittel)

Ziel
- Markdown-Datei (Tabelle) serverseitig verarbeiten und Merge-Report erzeugen.

Endpunkte
- Evaluate/Suggest/Rewrite Batch: [backend.core.batch.batch_evaluate()](../../backend/core/batch.py:282), [backend.core.batch.batch_suggest()](../../backend/core/batch.py:301), [backend.core.batch.batch_rewrite()](../../backend/core/batch.py:319)

Wichtige Helfer
- Parser: [backend.core.utils.parse_requirements_md()](../../backend/core/utils.py:39)
- Merge-Tabelle: [backend.core.batch.merged_markdown()](../../backend/core/batch.py:66)

Konfiguration
- Pfad: [.env REQUIREMENTS_MD_PATH](../../.env), Ausgabe optional [.env OUTPUT_MD_PATH](../../.env)


----------------------------------------------------------------

## 5) RAG Suche (einfach, ohne Agent) (Kurz)

Ziel
- Eine Query in Vektorraum suchen und Treffer mit Quelle/Chunk anzeigen.

Endpunkt
- [backend.core.api.rag_search()](../../backend/core/api.py:1286)

Voraussetzung
- Ingest/Indexierung vorgenommen (siehe Showcase 6)

Beispiel
```
curl -s "$API_BASE/api/v1/rag/search?query=health endpoint&top_k=5" | jq .
```


----------------------------------------------------------------

## 6) Datei-Ingest → Qdrant-Index (Mittel, Admin/Operator)

Ziel
- Dokumente hochladen, extrahieren, chunken, embedden und in Qdrant upserten.

Endpunkt
- [backend.core.api.files_ingest()](../../backend/core/api.py:1068)

Pipeline
- Extraktion/Chunking: [backend.core.ingest.extract_texts()](../../backend/core/ingest.py:230), [backend.core.ingest.chunk_payloads()](../../backend/core/ingest.py:287)
- Embeddings: [backend.core.embeddings.build_embeddings()](../../backend/core/embeddings.py:59)
- Upsert: [backend.core.vector_store.upsert_points()](../../backend/core/vector_store.py:109)

Hinweise
- Chunk-Parameter: `chunkMin`, `chunkMax`, `chunkOverlap`
- Collection/Dim: ENV in [backend.core.settings](../../backend/core/settings.py:26)


----------------------------------------------------------------

## 7) Agent-/Memory Antwort (Policy-Bias, Re-Ranking) (Lang)

Ziel
- Agent-/Policy-gestütztes Antwortformat, inkl. prefer_sources, topK-Anpassung, agentNotes.

Endpunkt
- [backend.core.api.agent_answer()](../../backend/core/api.py:1512)

Policies & Memory
- Regeln/Defaults: [backend.core.memory.MemoryStore.load_policies()](../../backend/core/memory.py:71)
- Ereignisprotokoll: [backend.core.memory.MemoryStore.append_event()](../../backend/core/memory.py:37)

Ranking/Context
- Re-Ranking: [backend.core.api._re_rank_hits()](../../backend/core/api.py:1389)
- Kontextfenster: [backend.core.api._build_context_from_hit()](../../backend/core/api.py:1412)

Optionaler externer Worker
- [agent_worker.app.mine()](../../agent_worker/app.py:261)


----------------------------------------------------------------

## 8) Vector-Index Admin (Reset, Health, Collections) (Kurz)

Ziel
- Collection neu aufsetzen, Status prüfen, Collections listen.

Endpunkte
- Reset (POST/DELETE/GET confirm=1): [backend.core.api.vector_reset()](../../backend/core/api.py:1158), [backend.core.api.vector_reset_get()](../../backend/core/api.py:1202)
- Health/List: [backend.core.api.vector_health()](../../backend/core/api.py:1149), [backend.core.api.vector_collections()](../../backend/core/api.py:1140)

Qdrant-Client
- [backend.core.vector_store.get_qdrant_client()](../../backend/core/vector_store.py:41) mit Port-Fallback (6333/6401)


----------------------------------------------------------------

## 9) NDJSON Streaming-Validate (Fortgeschritten, Streaming-Clients) (Mittel)

Ziel
- Ergebnisse pro Item streamen (schnelle Sichtbarkeit), kompatibel mit Browser-Streams.

Endpunkt
- [backend.core.api.validate_batch_stream()](../../backend/core/api.py:828)
- Suggestions-Stream: [backend.core.api.validate_suggest_stream()](../../backend/core/api.py:967)

Client-Hinweise
- Browser: fetch + ReadableStream + Zeilenweise JSON parse
- CLI: `curl --no-buffer ...`


----------------------------------------------------------------

## 10) RAG Benchmark Suite (Lang, Auswertung/Reporting)

Ziel
- Einfache Heuristik-Bewertung der RAG-Qualität über Promptliste.

Script
- [tests/rag_benchmark.py](../../tests/rag_benchmark.py)

Ergebnisse
- JSON/Markdown: tests/out/rag_report.json, tests/out/rag_report.md

Bewertungsheuristiken
- Keyword-Overlap: [tests/rag_benchmark.keyword_overlap()](../../tests/rag_benchmark.py:38)
- Referenz-Ähnlichkeit: [tests/rag_benchmark.ref_similarity()](../../tests/rag_benchmark.py:50)


----------------------------------------------------------------

## Anhang: Mini-Diagramme (Mermaid)

Validate Batch (sequenziell, komprimiert)
```mermaid
sequenceDiagram
  participant UI
  participant API
  participant DB
  UI->>API: POST /api/v1/validate/batch
  API->>DB: ensure_evaluation_exists()
  API-->>UI: Ergebnisse
```

Ingest (komprimiert)
```mermaid
flowchart LR
  U-->API[/files/ingest/]
  API-->EX
  EX-->CH
  CH-->EM
  EM-->UP
  UP-->Q[Qdrant]