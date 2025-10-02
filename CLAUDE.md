# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a **Requirements Engineering System** combining Flask (legacy) and FastAPI (v2) backends with LLM-powered validation, RAG capabilities, and multi-agent processing. The system validates requirements against quality criteria, suggests improvements, and extracts structured requirements from documents.

### Core Components

**Backend (Dual Stack)**
- **Flask (legacy)**: `backend_app/` - original API with validation, batch processing, RAG
- **FastAPI (v2)**: `backend_app_v2/` - enhanced version with LangExtract fixes, routers for LX/structure/gold/validate/vector/corrections/batch
- **Hybrid Entry**: `backend_app_v2/main.py` mounts Flask via WSGIMiddleware under FastAPI, unified on port 8087

**Multi-Agent System**
- `arch_team/` - AutoGen-based agent orchestration for requirements analysis
- `agent_worker/` - FastAPI worker service for distributed requirements mining

**Frontend**
- Static HTML/JS: `frontend/` (index.html, mining_demo.html, reports.html, kg_view.html, tag_view.html)
- React (new): `src/` with Vite build system
- TAG Viewer: `dev/external/TextAnnotationGraphs/` for annotation visualization

**Data Layer**
- SQLite: evaluation/suggestion/rewriting persistence (schema in `backend_app/db.py`)
- Qdrant: vector store for RAG (Docker Compose setup in `docker-compose.qdrant.yml`)

## Common Development Commands

### Backend

**Start Flask backend (legacy)**
```bash
python wsgi.py
# Runs on port 8000 (or API_PORT from .env)
```

**Start FastAPI v2 backend (recommended)**
```bash
python -m uvicorn backend_app_v2.main:fastapi_app --host 0.0.0.0 --port 8087 --reload
# Access at http://localhost:8087
# OpenAPI docs: http://localhost:8087/docs
```

**Start with Docker Compose**
```bash
docker-compose up --build
# Flask backend: http://localhost:8083
# Agent worker: http://localhost:8090
# Nginx frontend: http://localhost:8081
```

### Frontend

**React app (new)**
```bash
npm install
npm run dev
# Runs on port 3000, proxies /api to localhost:8001
```

**Static frontend**
Open `frontend/index.html` or `frontend/mining_demo.html` directly in browser. Configure `window.API_BASE = "http://localhost:8087"` in HTML files.

### Testing

**Run all tests**
```bash
pytest
# pytest.ini configures asyncio_mode=auto
```

**Run specific test suites**
```bash
# Backend tests
pytest tests/backend/

# Parity tests (v1 vs v2 compatibility, MOCK_MODE=true)
pytest tests/parity/test_parity_core.py

# Service layer tests
pytest tests/services/

# Agent tests
pytest tests/arch_team/

# UI tests (Playwright)
npx playwright test
```

**Single test execution**
```bash
pytest tests/backend/test_rag_models.py::test_specific_function -v
```

## Key Architecture Patterns

### Request Flow (V2)

1. Request hits FastAPI app → Request-ID middleware assigns UUID
2. Canary/Feature flag logic determines variant (v1/v2) - currently v2 at 100%
3. FastAPI routers handle `/api/v1/lx/*`, `/api/v1/structure/*`, etc.
4. Flask WSGI mount handles legacy routes like `/api/v1/evaluations`
5. Services layer (`backend_app_v2/services/`) encapsulates business logic
6. Persistence via SQLite (`backend_app/db.py`) or Qdrant vector store

### Validation Pipeline

```
POST /api/v1/validate/batch
  ↓
backend_app.api.validate_batch_optimized() [api.py:599]
  ↓
backend_app.batch.ensure_evaluation_exists() [batch.py:28]
  ↓
backend_app.llm.llm_evaluate() / llm_rewrite() / llm_suggest() [llm.py]
  ↓
Persist to SQLite (evaluation, evaluation_detail, suggestion tables)
  ↓
Return: {originalText, correctedText, evaluation[], score, verdict, suggestions?}
```

### LangExtract (Requirements Mining)

Located in `backend_app_v2/routers/lx_router.py` - extracts structured requirements from documents.

**Key endpoints:**
- `POST /api/v1/lx/extract` - mine requirements with chunking strategies
- `GET /api/v1/lx/config/list`, `POST /api/v1/lx/config/save` - manage extraction configs
- `POST /api/v1/lx/evaluate` - evaluate extraction quality

**Chunking modes** (configurable):
- `paragraph` (default): large chunks, 400 char overlap
- `token`: token-based with min/max/overlap params

**Options:**
- `neighbor_refs=1`: include ±1 chunk context in evidence
- `fast=1`: single-pass extraction (no self-consistency)
- `configId`: select prompt/examples configuration
- `goldId`, `useGoldAsFewshot=1`, `autoGold=1`: guided mining

### RAG (Retrieval-Augmented Generation)

**Ingest flow:**
```
POST /api/v1/files/ingest (multipart files)
  ↓
backend_app.ingest.extract_texts() [ingest.py:230]
  ↓
backend_app.ingest.chunk_payloads() [ingest.py:287]
  ↓
backend_app.embeddings.build_embeddings() [embeddings.py:59]
  ↓
backend_app.vector_store.upsert_points() [vector_store.py:109]
  ↓
Qdrant collection
```

**Search:**
```bash
GET /api/v1/rag/search?query=...&top_k=5
```

**Admin:**
- `GET /api/v1/vector/collections` - list collections
- `POST /api/v1/vector/reset` - reset collection (requires confirm=1)
- `GET /api/v1/vector/health` - Qdrant health check

### Auto-Refine Loop (Frontend)

Implemented in `frontend/app_optimized.js`:
1. `ensureSuggestions()` [line 162] - fetch suggestions if missing
2. `mergeApply()` [line 211] - apply selected suggestions via `/api/v1/corrections/apply`
3. `reanalyzeIndex()` [line 1834] - re-validate merged requirement
4. Gate check: `releaseOk()` [line 53] - score ≥ threshold or all criteria pass
5. Loop until gate passes or max iterations → escalate to "Review"

Main function: `autoRefineIndex()` [app_optimized.js:1947]

## Configuration

**Environment setup:**
```bash
cp .env.example .env
# Edit .env - critical vars:
# - OPENAI_API_KEY (leave empty for MOCK_MODE)
# - OPENAI_MODEL (default: gpt-4o-mini)
# - QDRANT_URL, QDRANT_PORT (default: http://host.docker.internal:6335)
# - SQLITE_PATH (default: /app/data/app.db)
```

**Key environment variables:**
- `MOCK_MODE=true` - use heuristic evaluation without OpenAI API
- `FEATURE_FLAG_USE_V2=true` - enable v2 routing (default: true)
- `CANARY_PERCENT=0-100` - sticky canary percentage for A/B testing
- `VERDICT_THRESHOLD=0.8` - minimum score for "release ok"
- `EMBEDDINGS_MODEL=text-embedding-3-small` - OpenAI embedding model

**Runtime config inspection:**
```bash
GET http://localhost:8087/api/runtime-config
# Returns all effective settings (API key presence only, not actual value)
```

## Health & Observability

**Health checks:**
```bash
GET /health        # Basic health
GET /ready         # Readiness probe
GET /livez         # Liveness probe
```

**Logging:**
- Structured JSON logging via `backend_app/logging_ext.py`
- Request-ID tracking (X-Request-Id header)
- Runtime config logged at startup: `log_runtime_config_once()` [logging_ext.py:248]

**Feature flags logged per request:**
- `variant`: v1 or v2
- `variantReason`: flag/canary/default

## Important Code Locations

**App initialization:**
- Flask: `backend_app.__init__.create_app()` [__init__.py:13]
- FastAPI: `backend_app_v2.main.fastapi_app` [main.py:32]

**Core validation:**
- `backend_app.api.validate_batch_optimized()` [api.py:599]
- `backend_app.batch.ensure_evaluation_exists()` [batch.py:28]

**LLM integration:**
- `backend_app.llm.llm_evaluate()` [llm.py:102]
- `backend_app.llm.llm_suggest()` [llm.py:158]
- `backend_app.llm.llm_apply_with_suggestions()` [llm.py:339]

**Database:**
- Schema DDL: `backend_app.db.DDL` [db.py:11]
- Migrations: `backend_app.db.ensure_schema_migrations()` [db.py:84]

**Vector store:**
- `backend_app.vector_store.get_qdrant_client()` [vector_store.py:41]
- `backend_app.vector_store.search()` [vector_store.py:151]

**Frontend:**
- Batch UI: `frontend/app_optimized.js`
- Auto-refine: `autoRefineIndex()` [app_optimized.js:1947]
- React app: `src/App.jsx`

## Multi-Agent System (arch_team)

The `arch_team/` module provides a sophisticated multi-agent system for requirements analysis, mining, and knowledge graph construction.

### Architecture Variants

**AutoGen 0.4+ (Modern, Recommended)**
```bash
python -m arch_team.autogen_rac
```
- Entry: `arch_team/autogen_rac.py`
- Uses AssistantAgent, RoundRobinGroupChat, TextMentionTermination
- Agents: Planner → Solver (with RAG tool) → Verifier
- Terminates on "COVERAGE_OK" or max 10 messages
- ENV: `OPENAI_API_KEY` (required), `MODEL_NAME` (optional, default: gpt-4o), `ARCH_TASK`

**Custom EventBus (Legacy)**
```bash
python -m arch_team.main
# or with chunk_miner mode:
python -m arch_team.main --mode chunk_miner --path "data/*.md" --neighbor-evidence
```
- Entry: `arch_team/main.py`
- Event-driven with topics: TOPIC_PLAN, TOPIC_SOLVE, TOPIC_VERIFY, TOPIC_DTO, TOPIC_TRACE
- Supports reflection rounds via Sequencer
- ENV: `ARCH_REFLECTION_ROUNDS` (default: 1), `ARCH_MODEL_CONTEXT_MAX` (default: 12)

### Agent Types

**PlannerAgent** (`arch_team/agents/planner.py`)
- Creates minimal 3-5 step execution plan
- Outputs: THOUGHTS, PLAN sections
- Hands off to Solver with plan context
- Optional tool execution via Workbench

**SolverAgent** (`arch_team/agents/solver.py`)
- Uses RAG retrieval from Qdrant for context
- Executes workbench tools (qdrant_search, python_exec)
- Chain-of-Thought output: THOUGHTS, EVIDENCE, FINAL_ANSWER
- Persists traces to QdrantTraceSink
- Creates StructuredRequirement DTOs for frontend
- Two-pass tool integration: initial response + tool evidence incorporation

**VerifierAgent** (`arch_team/agents/verifier.py`)
- Validates solver output for coverage and tags
- Returns "COVERAGE_OK" or CRITIQUE with improvement hints
- Minimal REQ count: 5-20 items recommended

**ChunkMinerAgent** (`arch_team/agents/chunk_miner.py`)
- Mines requirements from documents via chunk-based LLM calls
- Extracts text → overlap chunks → JSON mining per chunk
- DTO format: `{req_id, title, tag, evidence_refs: [{sourceFile, sha1, chunkIndex}]}`
- Neighbor evidence: includes ±1 chunk context when `neighbor_refs=True`
- Usage:
  ```python
  agent = ChunkMinerAgent(source="web", default_model="gpt-4o-mini")
  items = agent.mine_files_or_texts_collect(files, neighbor_refs=True)
  ```

**KGAbstractionAgent** (`arch_team/agents/kg_agent.py`)
- Builds knowledge graphs from requirement DTOs
- Node types: Requirement, Tag, Actor, Entity, Action
- Edge types: HAS_TAG, HAS_ACTOR, HAS_ACTION, ON_ENTITY
- Heuristic extraction + optional LLM refinement
- Persists to Qdrant (kg_nodes_v1, kg_edges_v1 collections)

### Web Service (Flask)

```bash
python -m arch_team.service
# Runs on port 8000 (or APP_PORT env)
# Frontend: http://localhost:8000/frontend/mining_demo.html
```

**Key endpoints:**

`POST /api/mining/upload` - Chunk-based requirements mining
- Multipart: `file` or `files` fields
- Form params: `model` (optional), `neighbor_refs` (1|true|yes for ±1 context)
- Response: `{success, count, items: [DTO, ...]}`

`POST /api/mining/report` - Generate markdown report
- JSON: `{items: [{req_id, title, tag, evidence_refs}, ...]}`
- Response: `{success, markdown, count, items}`

`POST /api/kg/build` - Build knowledge graph
- JSON: `{items: [DTO, ...], options: {persist: "qdrant", use_llm: false, llm_fallback: true}}`
- Response: `{success, stats, nodes, edges}`
- Options:
  - `persist`: "qdrant" | "none"
  - `use_llm`: true for LLM-enhanced extraction
  - `llm_fallback`: true to use LLM when heuristics fail
  - `persist_async`: true for background persistence (faster response)

`GET /api/kg/search/nodes?query=...&top_k=10` - Semantic node search

`GET /api/kg/search/edges?query=...&top_k=10` - Semantic edge search

`GET /api/kg/neighbors?node_id=...&rel=HAS_ACTION,ON_ENTITY&dir=both&limit=200`
- 1-hop neighborhood query
- `dir`: "in" | "out" | "both"
- `rel`: comma-separated relation types (optional filter)

### Key Patterns

**Chain-of-Thought (CoT) Processing**
- Agents produce structured blocks: THOUGHTS, EVIDENCE, FINAL_ANSWER, DECISION
- `extract_blocks()` in `arch_team/runtime/cot_postprocessor.py` parses output
- `ui_payload()` filters safe content for frontend (no internal thoughts/tool results)

**Privacy & Security**
- Tool execution results stay internal (marked as EVIDENCE)
- Only FINAL_ANSWER/DECISION exposed to UI
- No PII in traces or logs
- Tool failures logged internally, not exposed to user

**Context Management**
- `ChatCompletionContext` buffers messages (max_len configurable)
- Avoids context explosion with rolling window
- System prompts prepended, history appended per call

**Workbench Tools** (`arch_team/workbench/workbench.py`)
- `qdrant_search(query, top_k)` - vector search
- `python_exec(code)` - sandboxed Python execution
- Tool calls parsed from LLM output: `TOOL_CALL: {"name": "...", "arguments": {...}}`
- Results summarized and fed back to context

**Evidence Tracking**
- ChunkMiner tracks source chunks with sha1 + chunkIndex
- Neighbor evidence: ±1 chunks from same document
- Evidence preserved through graph construction
- KG edges include evidence_refs in payload

### Environment Variables

```bash
# AutoGen RAC
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o                    # default: gpt-4o
ARCH_TASK="Mining task description"
RAC_RAG_ENABLED=1                    # enable RAG tool
RAC_MAX_MESSAGES=10                  # max conversation turns

# Custom EventBus
ARCH_TEMPERATURE=0.2
ARCH_MODEL_CONTEXT_MAX=12
ARCH_REFLECTION_ROUNDS=1             # 1=single pass, >1=reflection
CHUNK_MINER_NEIGHBORS=1              # enable neighbor evidence

# Qdrant (shared)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=requirements_v2    # for RAG retrieval
# KG collections: kg_nodes_v1, kg_edges_v1, arch_trace (auto-created)

# Service
APP_PORT=8000
```

### Testing

```bash
# AutoGen smoke tests
pytest tests/arch_team/test_autogen_rac_smoke.py

# E2E pipeline
pytest tests/arch_team/test_e2e_pipeline.py

# ChunkMiner CLI test
pytest tests/arch_team/test_chunk_miner_cli.py

# RAG tool test
pytest tests/arch_team/test_autogen_rag_tool.py

# Qdrant trace sink
pytest tests/arch_team/test_qdrant_trace_sink.py
```

### Common Workflows

**1. Requirements Mining from Documents**
```bash
# CLI mode
python -m arch_team.main --mode chunk_miner \
  --path "data/*.md" --neighbor-evidence

# Or via web service
curl -X POST http://localhost:8000/api/mining/upload \
  -F "files=@data/requirements.md" \
  -F "neighbor_refs=1"
```

**2. Build Knowledge Graph**
```bash
# From mining results
curl -X POST http://localhost:8000/api/kg/build \
  -H "Content-Type: application/json" \
  -d '{"items": [...], "options": {"use_llm": false, "llm_fallback": true}}'
```

**3. AutoGen Requirements Analysis**
```bash
# Set task in .env or export
export ARCH_TASK="Analyze security requirements for auth system"
python -m arch_team.autogen_rac
# Streams conversation until "COVERAGE_OK" or max messages
```

### Important Code Locations

- AutoGen entry: `arch_team/autogen_rac.py` [main():98]
- EventBus entry: `arch_team/main.py` [main():75]
- Web service: `arch_team/service.py` [create_app():341]
- Planner: `arch_team/agents/planner.py` [on_message():54]
- Solver: `arch_team/agents/solver.py` [on_message():59]
- ChunkMiner: `arch_team/agents/chunk_miner.py` [mine_files_or_texts():176]
- KG Agent: `arch_team/agents/kg_agent.py` [run():47]
- CoT processing: `arch_team/runtime/cot_postprocessor.py` [extract_blocks(), ui_payload()]
- RAG tool: `arch_team/autogen_tools/requirements_rag.py` [search_requirements()]
- Workbench: `arch_team/workbench/workbench.py` [get_default_workbench()]

## Troubleshooting

**LangExtract returns 0 extractions:**
- Check chunking mode: use `chunkMode=paragraph` for better results
- Verify prompt config: `GET /api/v1/lx/config/get?id=default`
- Enable debug: check logs in `backend_app_v2/routers/lx_router.py`

**Qdrant connection fails:**
- Port fallback: tries 6333 then 6401 (see `vector_store.py:41`)
- Docker: use `host.docker.internal` for host network access
- Standalone: `docker-compose -f docker-compose.qdrant.yml up`

**CORS issues:**
- Global preflight handler: `backend_app.__init__._global_api_preflight()` [__init__.py:37]
- FastAPI CORS: configured in `backend_app_v2/main.py:38` (allow_origins=["*"])

**Mock mode (no API key):**
- Set `MOCK_MODE=true` or leave `OPENAI_API_KEY` empty
- Heuristic evaluation: `backend_app.llm._heuristic_mock_evaluation()` [llm.py:18]
- Suggestions may be empty in mock mode

## Additional Documentation

- System overview: `docs/architecture/SYSTEM_OVERVIEW.md`
- Features & stacks: `docs/architecture/FEATURES_AND_STACKS.md`
- Backend details: `docs/backend/README.md`
- Routes reference: `docs/backend/ROUTES.md`
- FastAPI migration: `README_FASTAPI.md`
- Backend v2 (LangExtract fixes): `backend_app_v2/README.md`
- merk dir den stand wir machen einen kurzen ausflug