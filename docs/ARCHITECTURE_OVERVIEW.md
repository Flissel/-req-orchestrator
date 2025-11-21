# Requirements Engineering System - Architecture Overview

**Last Updated:** 2025-11-10
**System Version:** 2.0 (Consolidated Backend + Society of Mind Agents)

## Executive Summary

This is a **hybrid requirements engineering system** combining:
- **FastAPI + Flask** hybrid backend (port 8087) for validation, RAG, and LangExtract
- **AutoGen 0.4+ Society of Mind** multi-agent system (arch_team) for requirements mining
- **React + Vite** frontend with real-time SSE streaming
- **Qdrant** vector store for semantic search and knowledge graphs
- **SQLite** for persistence of evaluations and metadata

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  React App (Vite)                Static HTML/JS                 │
│  - Configuration.jsx             - mining_demo.html             │
│  - KnowledgeGraph.jsx            - kg_view.html                 │
│  - Requirements.jsx              - tag_view.html                │
│  - AgentStatus.jsx               - reports.html                 │
│  - ChatInterface.jsx                                            │
│  Port: 5173 (dev)                Port: 8000/frontend/           │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTP/SSE
┌─────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                          │
├───────────────────────────┬─────────────────────────────────────┤
│  BACKEND (FastAPI+Flask)  │  ARCH_TEAM (Flask)                  │
│  Port: 8087               │  Port: 8000                         │
├───────────────────────────┼─────────────────────────────────────┤
│  FastAPI Routers:         │  Society of Mind Agents:            │
│  - lx_router              │  - Orchestrator (coordination)      │
│  - validate_router        │  - ChunkMiner (extraction)          │
│  - vector_router          │  - KG Agent (graph building)        │
│  - batch_router           │  - Validator (quality check)        │
│  - corrections_router     │  - RAG Agent (semantic search)      │
│  - gold_router            │  - QA Agent (final review)          │
│  - structure_router       │  - UserClarification (human loop)   │
│                           │                                     │
│  Flask Legacy (WSGI):     │  Endpoints:                         │
│  - /api/v1/evaluations    │  - /api/mining/upload               │
│  - /api/v1/files/*        │  - /api/kg/build                    │
│                           │  - /api/arch_team/process           │
│                           │  - /api/clarification/stream (SSE)  │
│                           │  - /api/workflow/stream (SSE)       │
└───────────────────────────┴─────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│  backend/services/ (Port-Adapter Pattern)                       │
│  - EvaluationService      - VectorService                       │
│  - CorrectionsService     - RAGService                          │
│  - BatchService           - Adapters (LLM, Embeddings, DB)      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      BUSINESS LOGIC LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│  backend/core/            │  arch_team/agents/                  │
│  - llm.py (LLM calls)     │  - chunk_miner.py                   │
│  - db.py (SQLite)         │  - kg_agent.py                      │
│  - embeddings.py          │  - master_agent.py                  │
│  - vector_store.py        │  - requirements_agent.py            │
│  - rag.py                 │                                     │
│  - ingest.py              │  arch_team/memory/                  │
│  - batch.py               │  - qdrant_kg.py (KG storage)        │
│                           │  - retrieval.py (RAG)               │
│                           │  - qdrant_trace_sink.py             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
├───────────────────────┬─────────────────────────────────────────┤
│  SQLite               │  Qdrant Vector Store                    │
│  - evaluation         │  - requirements_v2 (RAG docs)           │
│  - evaluation_detail  │  - kg_nodes_v1 (KG nodes)               │
│  - suggestion         │  - kg_edges_v1 (KG edges)               │
│  - rewrite            │  - arch_trace (agent traces)            │
│  - gold_examples      │                                         │
│  - lx_config          │  Port: 6401 (fallback) / 6333 (primary)│
└───────────────────────┴─────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       EXTERNAL SERVICES                         │
├─────────────────────────────────────────────────────────────────┤
│  OpenAI API (GPT-4o, GPT-4o-mini, text-embedding-3-small)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module Structure

### 1. Backend (Consolidated - Port 8087)

**Location:** `backend/`

**Purpose:** Unified production backend combining FastAPI v2 routers with Flask legacy via WSGIMiddleware.

#### Sub-modules:

**`backend/core/`** - Shared business logic (framework-agnostic)
- `agents.py` - AutoGen Core agent implementations (Evaluator, Suggester, Rewriter, Orchestrator, Monitor)
- `db.py` - SQLite schema, migrations, and CRUD operations
- `llm.py` - OpenAI LLM integration (evaluate, suggest, rewrite, apply)
- `llm_async.py` - Async LLM operations
- `embeddings.py` - OpenAI embeddings (text-embedding-3-small)
- `vector_store.py` - Qdrant client wrapper
- `rag.py` - RAG query logic
- `ingest.py` - Document chunking and ingestion pipeline
- `utils.py` - Shared utilities (verdict computation, checksums, scoring)
- `memory.py` - In-memory caching for LLM responses
- `logging_ext.py` - Structured JSON logging with request IDs
- `settings.py` - Runtime configuration and environment validation

**`backend/services/`** - Service layer (Port-Adapter pattern)
- `ports.py` - Protocol definitions (LLMPort, EmbeddingsPort, VectorStorePort, PersistencePort)
- `adapters.py` - Concrete adapter implementations
- `evaluation_service.py` - Single/batch requirement evaluation
- `batch_service.py` - Batch processing orchestration
- `corrections_service.py` - Suggestion application (merge/split)
- `vector_service.py` - Vector store management
- `rag_service.py` - RAG query service

**`backend/routers/`** - FastAPI v2 routers
- `lx_router.py` - LangExtract (requirements mining from documents)
- `validate_router.py` - Validation endpoints (v1 & v2)
- `vector_router.py` - Vector store operations (health, reset, search)
- `batch_router.py` - Batch processing endpoints
- `corrections_router.py` - Suggestion application endpoints
- `gold_router.py` - Gold example management for few-shot learning
- `structure_router.py` - Structural analysis (traceability, dependency graphs)

**`backend/legacy/`** - Original Flask code (reference only, phased out)

**`backend/main.py`** - FastAPI entry point with Flask WSGI mount

**Key Patterns:**
- **Hybrid Architecture**: FastAPI handles new v2 routes, Flask WSGI handles legacy v1 routes
- **Port-Adapter (Hexagonal)**: Services depend on abstract ports, adapters bind to concrete implementations
- **Request-ID Middleware**: All requests get UUID for tracing and observability
- **Canary Routing**: Feature flags + sticky canary for A/B testing (v1 vs v2)
- **Mock Mode**: Heuristic evaluation when `MOCK_MODE=true` or `OPENAI_API_KEY` missing

---

### 2. Arch Team (Society of Mind - Port 8000)

**Location:** `arch_team/`

**Purpose:** Multi-agent system for requirements analysis, mining, and knowledge graph construction using AutoGen 0.4+.

#### Sub-modules:

**`arch_team/agents/`** - Agent implementations
- `master_agent.py` - Society of Mind orchestration (7-agent team)
- `chunk_miner.py` - Requirements extraction from documents (chunk-based LLM mining)
- `kg_agent.py` - Knowledge graph construction (nodes: Requirement/Actor/Action/Entity/Tag, edges: HAS_*/ON_*)
- `requirements_agent.py` - Society of Mind validation workflow
- `planner.py` - Minimal 3-5 step execution planning
- `solver.py` - RAG-assisted problem solving with workbench tools
- `verifier.py` - Coverage validation and feedback
- `req_worker.py` - Distributed worker for requirement processing

**`arch_team/agents/prompts/`** - System prompts for each agent
- `orchestrator_prompt.py` - Workflow coordination
- `chunk_miner_prompt.py` - Document mining instructions
- `kg_agent_prompt.py` - Graph construction guidelines
- `validation_agent_prompt.py` - Quality evaluation criteria
- `rag_agent_prompt.py` - Semantic search strategies
- `qa_validator_prompt.py` - Final QA review checklist
- `user_clarification_prompt.py` - Human interaction protocol

**`arch_team/tools/`** - Tool implementations for agents
- `mining_tools.py` - FunctionTools for ChunkMiner (extract_requirements, parse_documents)
- `kg_tools.py` - FunctionTools for KG Agent (build_graph, query_graph)
- `validation_tools.py` - FunctionTools for Validator (evaluate_quality, suggest_improvements)
- `rag_tools.py` - FunctionTools for RAG Agent (semantic_search, find_duplicates, cluster_requirements)

**`arch_team/memory/`** - Persistence and retrieval
- `qdrant_kg.py` - Knowledge graph storage in Qdrant (kg_nodes_v1, kg_edges_v1)
- `retrieval.py` - RAG retrieval from Qdrant (requirements_v2 collection)
- `qdrant_trace_sink.py` - Agent conversation trace persistence

**`arch_team/pipeline/`** - Data pipelines
- `upload_ingest.py` - File upload and chunking pipeline
- `store_requirements.py` - Requirement DTO persistence

**`arch_team/runtime/`** - Agent runtime infrastructure
- `cot_postprocessor.py` - Chain-of-Thought output parsing (THOUGHTS, EVIDENCE, FINAL_ANSWER)
- `logging.py` - Structured logging for agents

**`arch_team/workbench/`** - Tool execution sandbox
- `workbench.py` - Tool registry (qdrant_search, python_exec)

**`arch_team/autogen_tools/`** - AutoGen-compatible tools
- `requirements_rag.py` - RAG search tool for AutoGen agents

**`arch_team/distributed/`** - Distributed processing (future)
- `host_stub.py` - gRPC host stub
- `worker_stub.py` - gRPC worker stub

**`arch_team/service.py`** - Flask web service with SSE streaming

**Key Patterns:**
- **Society of Mind**: 7 specialized agents coordinated via RoundRobinGroupChat
- **AutoGen 0.4+**: Uses AssistantAgent, RoundRobinGroupChat, TextMentionTermination
- **SSE Streaming**: Real-time agent messages to frontend via `/api/clarification/stream` and `/api/workflow/stream`
- **Human-in-the-Loop**: UserClarification agent asks questions via SSE, polls for file-based responses
- **Chain-of-Thought**: Structured agent output (THOUGHTS, EVIDENCE, FINAL_ANSWER) for transparency
- **Evidence Tracking**: Source chunks tracked with sha1 + chunkIndex, neighbor context (±1 chunks)
- **Knowledge Graph**: Heuristic + LLM entity extraction, Qdrant persistence

---

### 3. Frontend

**Location:** `frontend/` (static) + `src/` (React)

#### React App (`src/`)
- **Framework:** Vite + React
- **Port:** 5173 (dev)
- **Key Components:**
  - `App.jsx` - Main orchestration, state management
  - `Configuration.jsx` - File upload, model selection, settings
  - `KnowledgeGraph.jsx` - Interactive Cytoscape.js visualization
  - `Requirements.jsx` - Requirements list with filtering
  - `AgentStatus.jsx` - Real-time agent status via SSE
  - `ChatInterface.jsx` - Master workflow chat interaction
  - `ClarificationModal.jsx` - User clarification dialog
  - `ValidationTest.jsx` - Validation testing interface
  - `ErrorBoundary.jsx` - React error boundary

#### Static HTML/JS (`frontend/`)
- `mining_demo.html` - Requirements mining demo UI
- `kg_view.html` - Knowledge graph visualization
- `tag_view.html` - TAG (Text Annotation Graphs) viewer
- `reports.html` - Markdown report viewer
- `app_optimized.js` - Auto-refine loop implementation

**Key Features:**
- **SSE Integration**: Real-time agent messages via EventSource
- **Knowledge Graph**: Interactive visualization with Cytoscape.js (export to PNG/JSON/GraphML)
- **Auto-Refine Loop**: Iterative improvement until quality gate passes
- **File Upload**: Multipart form data with chunking options
- **Master Workflow**: Start Mining button triggers Society of Mind pipeline

---

## Key Workflows

### 1. Requirements Validation Pipeline

```
POST /api/v1/validate/batch
  ↓
backend.routers.validate_router.validate_batch()
  ↓
backend.services.evaluation_service.evaluate_batch()
  ↓
backend.core.llm.llm_evaluate() [or _heuristic_mock_evaluation()]
  ↓
backend.core.db.upsert_evaluation()
  ↓
Response: {originalText, correctedText, evaluation[], score, verdict, suggestions?}
```

**Key Functions:**
- [validate_router.py:129](backend/routers/validate_router.py#L129) - `validate_batch()`
- [evaluation_service.py:88](backend/services/evaluation_service.py#L88) - `evaluate_batch()`
- [llm.py:102](backend/core/llm.py#L102) - `llm_evaluate()`
- [db.py:163](backend/core/db.py#L163) - `upsert_evaluation()`

### 2. Requirements Mining (LangExtract)

```
POST /api/v1/lx/extract
  ↓
backend.routers.lx_router.lx_extract()
  ↓
backend.core.ingest.chunk_payloads()
  ↓
backend.core.llm.llm_langextract_per_chunk()
  ↓
backend.core.db.store_lx_result()
  ↓
Response: {status, lxId, count, items: [{req_id, originalRequirement, evidence}]}
```

**Chunking Modes:**
- `paragraph` (default): Large chunks with 400 char overlap
- `token`: Token-based with configurable min/max/overlap

**Options:**
- `neighbor_refs=1`: Include ±1 chunk context in evidence
- `fast=1`: Single-pass extraction (no self-consistency)
- `configId`: Select prompt/examples configuration
- `goldId`, `useGoldAsFewshot=1`, `autoGold=1`: Guided mining

**Key Functions:**
- [lx_router.py:180](backend/routers/lx_router.py#L180) - `lx_extract()`
- [ingest.py:287](backend/core/ingest.py#L287) - `chunk_payloads()`
- [llm.py:458](backend/core/llm.py#L458) - `llm_langextract_per_chunk()`

### 3. RAG Ingestion & Search

**Ingest:**
```
POST /api/v1/files/ingest (multipart)
  ↓
backend.core.ingest.extract_texts()
  ↓
backend.core.ingest.chunk_payloads()
  ↓
backend.core.embeddings.build_embeddings()
  ↓
backend.core.vector_store.upsert_points()
  ↓
Qdrant collection: requirements_v2
```

**Search:**
```
GET /api/v1/rag/search?query=...&top_k=5
  ↓
backend.routers.vector_router.rag_search()
  ↓
backend.core.embeddings.build_embeddings([query])
  ↓
backend.core.vector_store.search(vector, top_k)
  ↓
Response: [{text, payload, score}]
```

**Key Functions:**
- [ingest.py:230](backend/core/ingest.py#L230) - `extract_texts()`
- [ingest.py:287](backend/core/ingest.py#L287) - `chunk_payloads()`
- [embeddings.py:59](backend/core/embeddings.py#L59) - `build_embeddings()`
- [vector_store.py:109](backend/core/vector_store.py#L109) - `upsert_points()`
- [vector_store.py:151](backend/core/vector_store.py#L151) - `search()`

### 4. Society of Mind Workflow (Master Agent)

```
POST /api/arch_team/process (multipart: files, correlation_id)
  ↓
arch_team.service.arch_team_process()
  ↓
arch_team.agents.master_agent.run_master_workflow()
  ↓
┌────────────────────────────────────────────────────┐
│ Phase 1: ChunkMiner                                │
│ - chunk_miner.mine_files_or_texts_collect()       │
│ - Extracts requirements with ±1 chunk context     │
│ - Output: DTO list [{req_id, title, tag, evidence_refs}]
└────────────────────────────────────────────────────┘
  ↓ Stream: "Extracted N requirements"
┌────────────────────────────────────────────────────┐
│ Phase 2: KG Agent                                  │
│ - kg_agent.run(items, persist="qdrant")           │
│ - Heuristic + LLM entity extraction               │
│ - Output: {nodes, edges, stats}                   │
└────────────────────────────────────────────────────┘
  ↓ Stream: "Created N nodes, M edges"
┌────────────────────────────────────────────────────┐
│ Phase 3: Validator                                 │
│ - Heuristic validation (clarity/testability/measurability)
│ - Score: 0.33 per criterion                       │
│ - Verdict: pass if score >= 0.7                   │
└────────────────────────────────────────────────────┘
  ↓ Stream: "Validated N requirements (X passed, Y failed)"
┌────────────────────────────────────────────────────┐
│ Phase 4: Workflow Complete                         │
│ - Send workflow_result via SSE                    │
│ - Return {success, requirements, kg_data, validation_results}
└────────────────────────────────────────────────────┘
```

**SSE Streams:**
- `/api/workflow/stream?session_id=<correlation_id>` - Agent messages and workflow status
- `/api/clarification/stream?session_id=<correlation_id>` - User clarification questions

**Key Functions:**
- [service.py:1358](arch_team/service.py#L1358) - `arch_team_process()`
- [master_agent.py:305](arch_team/agents/master_agent.py#L305) - `run_master_workflow()`
- [chunk_miner.py:176](arch_team/agents/chunk_miner.py#L176) - `mine_files_or_texts_collect()`
- [kg_agent.py:47](arch_team/agents/kg_agent.py#L47) - `run()`

### 5. Auto-Refine Loop (Frontend)

```
Frontend: app_optimized.js
  ↓
1. ensureSuggestions() [line 162]
   - Fetch suggestions if missing: POST /api/v1/validate/suggest
  ↓
2. User selects suggestions in UI
  ↓
3. mergeApply() [line 211]
   - Apply selected suggestions: POST /api/v1/corrections/apply
  ↓
4. reanalyzeIndex() [line 1834]
   - Re-validate merged requirement: POST /api/v1/validate/batch
  ↓
5. releaseOk() [line 53]
   - Check if score >= threshold OR all criteria pass
  ↓
6. Loop until gate passes or max iterations
   - If fail: escalate to "Review" state
  ↓
Main: autoRefineIndex() [line 1947]
```

**Key Functions:**
- [app_optimized.js:162](frontend/app_optimized.js#L162) - `ensureSuggestions()`
- [app_optimized.js:211](frontend/app_optimized.js#L211) - `mergeApply()`
- [app_optimized.js:1834](frontend/app_optimized.js#L1834) - `reanalyzeIndex()`
- [app_optimized.js:53](frontend/app_optimized.js#L53) - `releaseOk()`
- [app_optimized.js:1947](frontend/app_optimized.js#L1947) - `autoRefineIndex()`

---

## API Endpoints

### Backend (Port 8087)

#### Validation & Evaluation
- `POST /api/v1/validate/batch` - Validate and rewrite requirements
- `POST /api/v1/validate/suggest` - Generate improvement suggestions
- `POST /api/v1/validate/batch/stream` - Streaming validation (SSE)
- `POST /api/v1/validate/suggest/stream` - Streaming suggestions (SSE)
- `POST /api/v2/evaluate/single` - Single requirement evaluation
- `POST /api/v2/evaluate/batch` - Batch evaluation

#### LangExtract (Requirements Mining)
- `POST /api/v1/lx/extract` - Extract requirements from documents
- `GET /api/v1/lx/mine` - Simple text mining (legacy)
- `POST /api/v1/lx/evaluate` - Evaluate extraction quality
- `GET /api/v1/lx/config/list` - List extraction configs
- `POST /api/v1/lx/config/save` - Save extraction config
- `GET /api/v1/lx/gold/list` - List gold examples
- `POST /api/v1/lx/gold/save` - Save gold example
- `GET /api/v1/lx/result/get` - Retrieve extraction result

#### Vector Store & RAG
- `GET /api/v1/vector/health` - Qdrant health check
- `GET /api/v1/vector/collections` - List collections
- `POST /api/v1/vector/reset` - Reset collection (requires confirm=1)
- `GET /api/v1/rag/search` - Semantic search
- `GET /api/v1/vector/source/full` - Fetch full source document

#### Corrections & Batch
- `POST /api/v1/corrections/apply` - Apply suggestions (merge/split)
- `POST /api/v1/corrections/decision` - Decision tracking
- `POST /api/v1/corrections/decision/batch` - Batch decision
- `POST /api/v1/batch/evaluate` - Batch evaluation
- `POST /api/v1/batch/rewrite` - Batch rewrite
- `POST /api/v1/batch/suggest` - Batch suggestions

#### Structure Analysis
- `POST /api/v1/structure/analyze` - Analyze traceability/dependencies
- `POST /api/v1/structure/graph_export` - Export dependency graph

#### Observability
- `GET /health` - Health check
- `GET /ready` - Readiness probe
- `GET /livez` - Liveness probe
- `GET /api/runtime-config` - Runtime configuration

### Arch Team (Port 8000)

#### Requirements Mining
- `POST /api/mining/upload` - Upload files for chunk-based mining
- `POST /api/mining/report` - Generate markdown report from DTOs

#### Knowledge Graph
- `POST /api/kg/build` - Build KG from requirements DTOs
- `GET /api/kg/search/nodes` - Semantic node search
- `GET /api/kg/search/edges` - Semantic edge search
- `GET /api/kg/neighbors` - 1-hop neighborhood query
- `POST /api/kg/search/semantic` - Semantic duplicate detection

#### Validation & RAG
- `POST /api/v2/evaluate/single` - Service-layer single evaluation
- `POST /api/v2/evaluate/batch` - Service-layer batch evaluation
- `POST /api/v1/validate/batch` - Validate and rewrite
- `POST /api/v1/validate/suggest` - Generate suggestions
- `POST /api/rag/duplicates` - Find semantic duplicates with grouping
- `POST /api/rag/search` - Semantic search in requirements
- `POST /api/rag/related` - Find related requirements
- `POST /api/rag/coverage` - Analyze requirement coverage

#### Society of Mind Workflow
- `POST /api/arch_team/process` - Master workflow (multipart: files, correlation_id)
- `POST /api/validation/run` - Society of Mind validation
- `GET /api/clarification/stream` - SSE stream for user clarifications
- `POST /api/clarification/answer` - Submit user answer
- `GET /api/workflow/stream` - SSE stream for agent messages

#### Frontend
- `GET /` - Redirect to mining_demo.html
- `GET /frontend/<path>` - Serve static files
- `GET /health` - Health check

---

## Configuration & Environment

### Critical Environment Variables

```bash
# OpenAI API (required unless MOCK_MODE=true)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini                    # default model
EMBEDDINGS_MODEL=text-embedding-3-small     # embeddings model

# Qdrant Vector Store
QDRANT_URL=http://localhost                 # or http://host.docker.internal
QDRANT_PORT=6401                            # fallback 6401, primary 6333
QDRANT_API_KEY=                             # optional
QDRANT_COLLECTION=requirements_v2           # RAG collection

# SQLite Persistence
SQLITE_PATH=/app/data/app.db                # database path

# Feature Flags & Canary
FEATURE_FLAG_USE_V2=true                    # enable v2 routing (default: true)
CANARY_PERCENT=0                            # sticky canary % (0-100)

# Validation
VERDICT_THRESHOLD=0.8                       # min score for "release ok"
MOCK_MODE=false                             # use heuristics when true

# Arch Team (Society of Mind)
MODEL_NAME=gpt-4o-mini                      # agent model
APP_PORT=8000                               # arch_team service port
ARCH_REFLECTION_ROUNDS=1                    # reflection iterations
ARCH_MODEL_CONTEXT_MAX=12                   # max context messages
CHUNK_MINER_NEIGHBORS=1                     # enable neighbor evidence

# Backend
API_HOST=0.0.0.0                            # backend host
API_PORT=8087                               # backend port (consolidated)

# Logging
LOG_LEVEL=INFO                              # logging level
```

### Runtime Config Inspection

```bash
GET http://localhost:8087/api/runtime-config
```

Returns effective settings (API key presence only, not actual values).

---

## Key Design Patterns

### 1. Port-Adapter (Hexagonal Architecture)

**Location:** `backend/services/`

**Pattern:**
- **Ports** (`ports.py`): Abstract protocols (LLMPort, EmbeddingsPort, VectorStorePort, PersistencePort)
- **Adapters** (`adapters.py`): Concrete implementations binding to `backend.core.*`
- **Services** (`*_service.py`): Business logic depending on ports (DI via constructor)

**Benefits:**
- Framework-agnostic business logic
- Easy mocking for tests
- Swap implementations without changing services

**Example:**
```python
# Port
class LLMPort(Protocol):
    def evaluate(self, text: str, criteria: List[str]) -> List[Dict]: ...

# Adapter
class DefaultLLMAdapter:
    def evaluate(self, text: str, criteria: List[str]) -> List[Dict]:
        return llm_evaluate(text, criteria)

# Service
class EvaluationService:
    def __init__(self, llm: LLMPort):
        self.llm = llm
```

### 2. Society of Mind (Multi-Agent System)

**Location:** `arch_team/agents/`

**Pattern:**
- **7 Specialized Agents**: Orchestrator, ChunkMiner, KG, Validator, RAG, QA, UserClarification
- **RoundRobinGroupChat**: Sequential agent turns until termination condition
- **TextMentionTermination**: Workflow ends when agent outputs "WORKFLOW_COMPLETE"
- **Tools per Agent**: FunctionTools registered per agent role

**Benefits:**
- Separation of concerns (each agent has one job)
- Transparency (Chain-of-Thought output)
- Extensibility (add agents without changing others)
- Human-in-the-Loop (UserClarification agent)

**Example:**
```python
termination = TextMentionTermination("WORKFLOW_COMPLETE")
team = RoundRobinGroupChat(
    participants=[orchestrator, chunk_miner, kg_agent, validator, rag_agent, qa, user_clarification],
    termination_condition=termination,
    max_turns=100
)
master = SocietyOfMindAgent(team=team, model_client=model_client)
```

### 3. Chain-of-Thought (CoT) Processing

**Location:** `arch_team/runtime/cot_postprocessor.py`

**Pattern:**
- Agents produce structured blocks: `THOUGHTS`, `EVIDENCE`, `FINAL_ANSWER`, `DECISION`
- `extract_blocks()` parses output into structured dict
- `ui_payload()` filters safe content for frontend (no internal thoughts/tool results)

**Benefits:**
- Transparency (see agent reasoning)
- Privacy (tool results stay internal)
- Observability (structured logs)

**Example:**
```
THOUGHTS:
I need to extract requirements from 3 documents using chunk-based mining.

EVIDENCE:
- document1.md: 5 chunks
- document2.md: 8 chunks

FINAL_ANSWER:
Extracted 12 requirements across 3 documents.
```

### 4. SSE Streaming (Server-Sent Events)

**Location:** `arch_team/service.py`

**Pattern:**
- Frontend connects to SSE endpoint: `GET /api/workflow/stream?session_id=<correlation_id>`
- Backend maintains `Queue` per session in `workflow_streams` dict
- Agents call `_send_to_workflow_stream(correlation_id, message_type, **kwargs)` to push events
- Frontend receives events via `EventSource` and updates UI

**Benefits:**
- Real-time agent messages without polling
- Lightweight (HTTP, no WebSocket complexity)
- Auto-reconnect built into browser `EventSource`

**Example:**
```python
# Backend
workflow_streams[session_id] = Queue()

def event_stream():
    while True:
        msg = q.get()  # blocks
        yield f"data: {json.dumps(msg)}\n\n"

# Frontend
const eventSource = new EventSource(`/api/workflow/stream?session_id=${sessionId}`);
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Update UI
};
```

### 5. Evidence Tracking (Provenance)

**Location:** `arch_team/agents/chunk_miner.py`

**Pattern:**
- Each requirement DTO includes `evidence_refs: [{sourceFile, sha1, chunkIndex}]`
- Chunk hash computed with `hashlib.sha256(chunk_text.encode()).hexdigest()`
- Neighbor evidence: include ±1 chunks from same document when `neighbor_refs=True`
- Evidence preserved through KG construction

**Benefits:**
- Traceability (know where requirements came from)
- Verification (check if requirement still valid against source)
- Auditing (compliance with source documents)

**Example:**
```json
{
  "req_id": "REQ-001",
  "title": "System must authenticate users",
  "tag": "security",
  "evidence_refs": [
    {
      "sourceFile": "requirements.md",
      "sha1": "a1b2c3...",
      "chunkIndex": 5,
      "chunkText": "The system shall provide secure authentication..."
    },
    {
      "sourceFile": "requirements.md",
      "sha1": "d4e5f6...",
      "chunkIndex": 6,
      "chunkText": "Multi-factor authentication is required..."
    }
  ]
}
```

---

## Testing Strategy

### Test Organization

```
tests/
├── backend/                 # Backend unit tests
│   ├── test_lx_extract_v2.py
│   ├── test_rag_models.py
│   └── ...
├── services/                # Service layer tests
│   ├── test_evaluation_service.py
│   └── ...
├── parity/                  # v1 vs v2 compatibility tests
│   ├── conftest.py
│   └── test_parity_core.py
├── arch_team/               # Agent tests
│   ├── test_autogen_rac_smoke.py
│   ├── test_e2e_pipeline.py
│   ├── test_chunk_miner_cli.py
│   └── test_autogen_rag_tool.py
└── e2e/                     # End-to-end Playwright tests
    └── ...
```

### Running Tests

```bash
# All tests
pytest

# Backend tests only
pytest tests/backend/

# Service layer tests
pytest tests/services/

# Parity tests (MOCK_MODE=true)
pytest tests/parity/test_parity_core.py

# Agent tests
pytest tests/arch_team/

# Single test
pytest tests/backend/test_rag_models.py::test_specific_function -v

# E2E UI tests (Playwright)
npx playwright test
```

### Mock Mode Testing

**Purpose:** Test without OpenAI API (heuristic evaluation)

**Setup:**
```bash
export MOCK_MODE=true
# or leave OPENAI_API_KEY empty
pytest
```

**Behavior:**
- `llm_evaluate()` → `_heuristic_mock_evaluation()` (keyword-based scoring)
- `llm_suggest()` → returns empty list or predefined suggestions
- `llm_rewrite()` → returns original text with minor formatting

**Key Function:** [llm.py:18](backend/core/llm.py#L18) - `_heuristic_mock_evaluation()`

---

## Observability & Monitoring

### Structured Logging

**Format:** JSON logs with request IDs

**Example:**
```json
{
  "event": "request_start",
  "requestId": "123e4567-e89b-12d3-a456-426614174000",
  "method": "POST",
  "path": "/api/v1/validate/batch",
  "query": "",
  "client": "192.168.1.100",
  "userAgent": "Mozilla/5.0...",
  "variant": "v2",
  "variantReason": "flag",
  "canaryPercent": 0
}
```

**Key Functions:**
- [logging_ext.py:248](backend/core/logging_ext.py#L248) - `log_runtime_config_once()`
- [main.py:74](backend/main.py#L74) - Request-ID middleware

### Health Checks

```bash
# Backend
GET http://localhost:8087/health         # Basic health
GET http://localhost:8087/ready          # Readiness probe
GET http://localhost:8087/livez          # Liveness probe

# Arch Team
GET http://localhost:8000/health         # Basic health

# Qdrant
GET http://localhost:8087/api/v1/vector/health
```

### Request Tracing

- **X-Request-Id**: UUID assigned per request
- **X-Variant**: v1 or v2
- **X-Variant-Reason**: flag/canary/default

**Middleware:** [main.py:47](backend/main.py#L47) - `add_request_id_header()`

---

## Security Considerations

### 1. API Key Management
- **Storage:** Environment variables only (never commit to git)
- **Validation:** Check `OPENAI_API_KEY` presence at startup
- **Logging:** Log presence only ("SET" or "MISSING"), never actual key

### 2. Input Validation
- **File Uploads:** Validate MIME types, file size limits
- **SQL Injection:** Use parameterized queries (SQLite `?` placeholders)
- **XSS Prevention:** Sanitize user input in frontend before rendering

### 3. CORS Policy
- **Backend:** `allow_origins=["*"]` (restrictive in production)
- **Arch Team:** Flask-CORS with wildcard (fine for internal tools)

### 4. LLM Prompt Injection
- **Mitigation:** Use system messages with clear role boundaries
- **Validation:** Validate agent outputs against expected schema
- **Sandboxing:** Tool execution in isolated environment (workbench.py)

### 5. Privacy & Data Handling
- **PII Filtering:** Do not log sensitive requirement content
- **Tool Results:** Keep internal (EVIDENCE block), never expose to user
- **Trace Persistence:** Store only agent metadata, not full conversation

---

## Deployment

### Local Development

```bash
# Backend (FastAPI+Flask)
python -m uvicorn backend.main:fastapi_app --host 0.0.0.0 --port 8087 --reload

# Arch Team (Flask)
python -m arch_team.service

# Frontend (React)
npm run dev

# Qdrant (Docker)
docker-compose -f docker-compose.qdrant.yml up
```

### Docker Compose

```bash
docker-compose up --build

# Services:
# - Flask backend: http://localhost:8083
# - Agent worker: http://localhost:8090
# - Nginx frontend: http://localhost:8081
```

### Production Considerations

1. **Backend:** Use `gunicorn` or `uvicorn` with multiple workers
2. **Frontend:** Build static assets (`npm run build`) and serve via Nginx
3. **Qdrant:** Run as persistent Docker container with volume mounts
4. **Environment:** Use `.env.production` with secrets from vault
5. **Logging:** Ship structured logs to centralized logging (ELK, Splunk)
6. **Monitoring:** Set up health check endpoints with alerting
7. **CORS:** Restrict `allow_origins` to known domains

---

## Future Enhancements

### 1. Distributed Processing (gRPC)
- **Status:** Stubs exist (`arch_team/distributed/`)
- **Goal:** Scale requirement processing across workers
- **Pattern:** Host broadcasts tasks, workers execute and report back

### 2. Advanced RAG Strategies
- **Hybrid Search:** Combine vector similarity + keyword matching
- **Re-ranking:** Use cross-encoder for top-k re-ranking
- **Query Expansion:** LLM-based query augmentation

### 3. Knowledge Graph Reasoning
- **Graph Queries:** Cypher-like query language for KG
- **Inference Rules:** Deduce implicit relationships
- **Conflict Detection:** Identify contradictory requirements

### 4. Continuous Learning
- **Feedback Loop:** Capture user corrections as training data
- **Fine-tuning:** Periodically fine-tune LLMs on domain data
- **Active Learning:** Prioritize uncertain requirements for human review

### 5. Compliance & Standards
- **EARS Templates:** Enforce IEEE 29148 patterns
- **ISO 26262 Support:** Automotive safety requirements
- **Traceability Matrix:** Automated generation from KG

---

## Glossary

- **DTO**: Data Transfer Object (structured requirement representation)
- **KG**: Knowledge Graph
- **RAG**: Retrieval-Augmented Generation
- **SSE**: Server-Sent Events
- **CoT**: Chain-of-Thought
- **LX**: LangExtract (requirements mining)
- **Port-Adapter**: Hexagonal architecture pattern
- **Society of Mind**: Multi-agent coordination pattern
- **Evidence Refs**: Source provenance tracking
- **Auto-Refine**: Iterative improvement loop with quality gate
- **Canary**: Gradual rollout of new code (sticky by request ID)
- **Mock Mode**: Testing without OpenAI API (heuristic evaluation)

---

## References

- **CLAUDE.md**: High-level project instructions
- **backend/README.md**: Backend v2 details (LangExtract fixes)
- **docs/architecture/SYSTEM_OVERVIEW.md**: Legacy system overview
- **docs/architecture/FEATURES_AND_STACKS.md**: Technology stack details
- **docs/backend/ROUTES.md**: Detailed API route reference
- **README_FASTAPI.md**: FastAPI migration notes

---

**Document Maintainer:** Architecture Team
**Review Cycle:** Monthly or after major changes
**Last Reviewed:** 2025-11-10
