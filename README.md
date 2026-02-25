# req-orchestrator

AI-powered requirements engineering system with multi-agent orchestration, automated validation, and knowledge graph generation.

## Features

- **Requirements Mining** - Extract structured requirements from PDF, DOCX, and Markdown documents using LLM-powered agents
- **IEEE 29148 Validation** - Automated quality evaluation against 9 IEEE 29148 criteria with scoring and improvement suggestions
- **Knowledge Graph** - Build and visualize semantic relationships between requirements, actors, entities, and actions
- **Multi-Agent Orchestration** - 15+ specialized AutoGen agents (Planner, Solver, Verifier, ChunkMiner, KG Agent, etc.)
- **RAG Search** - Semantic search over requirements using Qdrant vector database
- **Auto-Refine Loop** - Iterative improvement: validate → suggest → apply → re-validate until quality gates pass
- **MCP Integration** - 20+ tools for Claude CLI orchestration
- **Real-time Updates** - WebSocket-based live processing status

## Quickstart

### Prerequisites

- Python 3.10+
- Node.js 20+
- [OpenRouter API key](https://openrouter.ai) (required for LLM calls)
- Qdrant (optional, for vector search / RAG)

### Setup

```bash
# Clone and enter the project
git clone https://github.com/YOUR_ORG/req-orchestrator.git
cd req-orchestrator

# Python environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -e .

# Frontend
npm ci

# Configure
cp .env.example .env
# Edit .env: set OPENROUTER_API_KEY
```

### Run

```bash
# Backend (port 8087)
uvicorn backend.main:fastapi_app --reload --port 8087

# Frontend (port 3000)
npm run dev

# Agent service (port 8000, optional)
python -m arch_team.service
```

Open http://localhost:3000 in your browser.

### Docker

```bash
docker-compose up --build
# App: http://localhost:8087
# Qdrant: http://localhost:6401
```

## Architecture

```
backend/          FastAPI REST API (13 routers, 14 services)
arch_team/        Multi-agent system (AutoGen 0.4+)
mcp_server/       MCP server for Claude CLI (20+ tools)
src/              React + Vite frontend
config/           Prompts & evaluation criteria
tests/            Pytest + Playwright E2E tests
```

See [docs/architecture/](docs/architecture/) for detailed documentation.

## API

The backend exposes a full REST API with interactive documentation at `/docs` when running.

Key endpoints:

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/validate/batch` | Validate requirements against IEEE 29148 |
| `POST /api/v1/lx/extract` | Mine requirements from documents |
| `GET /api/v1/rag/search` | Semantic search via RAG |
| `POST /api/kg/build` | Build knowledge graph |
| `WS /ws/enhancement` | Real-time processing updates |

## MCP Server (Claude CLI)

```bash
# Register as MCP tool provider
claude mcp add req-orchestrator -- python -m mcp_server.server

# Or run standalone
python -m mcp_server.server
```

Provides tools for mining, validation, knowledge graph operations, RAG search, and end-to-end workflow automation.

## Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Description | Default |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | OpenRouter API key (required) | - |
| `OPENAI_MODEL` | LLM model via OpenRouter | `google/gemini-2.5-flash:nitro` |
| `BACKEND_PORT` | FastAPI backend port | `8087` |
| `MOCK_MODE` | Use heuristics instead of LLM | `false` |
| `VERDICT_THRESHOLD` | Min score for validation pass | `0.7` |
| `QDRANT_URL` | Qdrant vector DB URL | `http://localhost` |
| `QDRANT_PORT` | Qdrant HTTP port | `6333` |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# E2E tests (requires running backend + frontend)
npx playwright test

# Code formatting
black .
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

## License

[MIT](LICENSE)
