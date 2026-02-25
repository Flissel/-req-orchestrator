# Architecture Overview

req-orchestrator is composed of four main subsystems that work together to provide AI-powered requirements engineering.

```
                    ┌─────────────────────┐
                    │   React Frontend    │
                    │  (Vite, port 3000)  │
                    └────────┬────────────┘
                             │ HTTP / WebSocket
                    ┌────────▼────────────┐
                    │   FastAPI Backend   │
                    │   (port 8087)       │
                    │  13 routers         │
                    │  14 services        │
                    └──┬──────────┬───────┘
                       │          │
          ┌────────────▼──┐  ┌───▼──────────────┐
          │  Arch Team    │  │   Qdrant          │
          │  Agent Service│  │   Vector DB       │
          │  (port 8000)  │  │   (port 6333)     │
          │  15+ agents   │  │   RAG + KG store  │
          └───────────────┘  └───────────────────┘
```

## Subsystems

### 1. FastAPI Backend (`backend/`)

The REST API layer with 13 route modules and 14 service classes.

**Key routers:** validation, LangExtract (mining), RAG search, corrections, batch processing, WebSocket real-time updates.

**Data flow:** HTTP request → Router → Service → Core logic (LLM / DB / Vector) → Response

### 2. Multi-Agent System (`arch_team/`)

AutoGen 0.4+-based agent orchestration for intelligent requirements analysis.

**Agent types:** Planner, Solver, Verifier, ChunkMiner, KG Agent, Master Agent, Clarification Agent, Validation Workers, Criterion Specialists.

**Execution modes:**
- **AutoGen RAC** (`autogen_rac.py`) - Round-robin group chat with Planner → Solver → Verifier
- **EventBus** (`main.py`) - Custom pub/sub with topic-based routing
- **Web Service** (`service.py`) - Flask REST API for document mining

See [agents.md](agents.md) for the full Society of Mind design.

### 3. React Frontend (`src/`)

Single-page application with tabs for Mining, Validation, Knowledge Graph visualization, and Tech Stack analysis.

**Stack:** React 18, Vite, Cytoscape.js (graph visualization), React-Window (virtualized lists).

### 4. MCP Server (`mcp_server/`)

Model Context Protocol integration for Claude CLI orchestration. Provides 20+ tools for mining, validation, knowledge graph operations, RAG search, and workflow automation.

**Install:** `claude mcp add req-orchestrator -- python -m mcp_server.server`

## Data Storage

| Store | Purpose |
|-------|---------|
| SQLite | Evaluations, suggestions, requirement manifests, criteria |
| Qdrant | Embeddings (RAG search), knowledge graph nodes/edges, agent traces |

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/validate/batch` | Batch requirement validation |
| `POST /api/v1/lx/extract` | Mine requirements from documents |
| `GET /api/v1/rag/search` | Semantic search via RAG |
| `POST /api/kg/build` | Build knowledge graph |
| `WS /ws/enhancement` | Real-time processing updates |
| `GET /docs` | OpenAPI documentation |

## Detailed Documentation

- [agents.md](agents.md) - Multi-agent Society of Mind architecture
- [flows.md](flows.md) - Workflow diagrams and data flows
- [validation.md](validation.md) - Parallel validation system design
- [requirements-validation.md](requirements-validation.md) - Requirements validation design
