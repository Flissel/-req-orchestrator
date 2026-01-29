# MCP Server for Requirements Orchestrator

Model Context Protocol (MCP) server that exposes all high-end requirements engineering functions to Claude CLI for interactive workflow orchestration.

## Features

- **20+ MCP Tools** for requirements engineering
- **5 Resources** for data access
- **6 Workflow Prompts** for guided operations
- **Hybrid Architecture**: Direct Python imports for speed + REST/SSE for streaming
- **Interactive CLI** for testing and debugging

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .
# Or install from requirements
pip install mcp httpx pydantic rich
```

### 2. Configure Claude CLI

```bash
claude mcp add req-orchestrator -- python -m mcp_server.server
```

### 3. Verify Installation

```bash
claude "List all available tools from req-orchestrator"
```

## Architecture

```
mcp_server/
├── server.py              # MCP Server Entry Point
├── config.py              # Configuration
├── tools/                 # 20+ MCP Tools
│   ├── mining_tools.py    # Document → Requirements
│   ├── validation_tools.py # IEEE 29148 validation
│   ├── kg_tools.py        # Knowledge Graph
│   ├── rag_tools.py       # RAG & duplicates
│   ├── workflow_tools.py  # End-to-end orchestration
│   └── template_tools.py  # Tech stack & templates
├── resources/             # Data Resources
│   └── requirements.py    # Requirements, Projects, Templates
├── prompts/               # Workflow Prompts
│   └── workflow_prompts.py
└── cli/                   # Interactive CLI
    └── interactive.py
```

## Available Tools

### Mining (2 tools)
| Tool | Description |
|------|-------------|
| `mine_documents` | Extract requirements from files (PDF, DOCX, MD) |
| `mine_text` | Extract requirements from raw text |

### Validation (3 tools)
| Tool | Description |
|------|-------------|
| `validate_requirements` | Batch validation against 9 IEEE 29148 criteria |
| `enhance_requirement` | Improve a requirement based on failing criteria |
| `evaluate_single` | Detailed evaluation of a single requirement |

### Knowledge Graph (4 tools)
| Tool | Description |
|------|-------------|
| `build_knowledge_graph` | Build semantic KG from requirements |
| `search_kg_nodes` | Semantic search for nodes |
| `get_kg_neighbors` | Get 1-hop neighbors of a node |
| `export_knowledge_graph` | Export entire graph |

### RAG & Semantic Search (4 tools)
| Tool | Description |
|------|-------------|
| `find_duplicates` | Detect semantic duplicate requirements |
| `search_requirements` | Semantic search in knowledge base |
| `find_related` | Find related requirements |
| `analyze_coverage` | Analyze coverage across categories |

### Workflow Orchestration (5 tools)
| Tool | Description |
|------|-------------|
| `run_full_workflow` | Complete pipeline: Mining → KG → Validation → RAG |
| `get_clarification_questions` | Generate questions for failing requirements |
| `apply_answers` | Apply user answers and re-validate |
| `get_project_status` | Get workflow statistics |
| `export_requirements` | Export to markdown/json/csv |

### Templates (4 tools)
| Tool | Description |
|------|-------------|
| `recommend_techstack` | Recommend project template from 15 options |
| `get_template_info` | Get template metadata |
| `list_templates` | List all 15 templates |
| `get_template_questions` | Get customization questions |

## Available Resources

| URI | Description |
|-----|-------------|
| `requirements://current` | Current requirements with validation status |
| `projects://list` | All available projects |
| `templates://all` | All 15 project templates |
| `criteria://ieee29148` | IEEE 29148 quality criteria definitions |
| `config://runtime` | Runtime configuration and service status |

## Available Prompts

| Prompt | Description |
|--------|-------------|
| `quick-validation` | Fast requirement validation |
| `deep-analysis` | Complete analysis pipeline |
| `interactive-enhancement` | Guided requirement improvement |
| `techstack-recommendation` | Template recommendation |
| `duplicate-detection` | Find semantic duplicates |
| `coverage-analysis` | Coverage gap analysis |

## Usage Examples

### Basic Validation

```
User: Validate these requirements against IEEE 29148:
- The system shall be fast
- The system shall respond within 100ms

Claude: [Calls validate_requirements tool]
→ 1 passed, 1 failed
→ "The system shall be fast" fails: measurability, testability
→ "The system shall respond within 100ms" passes all criteria
```

### Complete Workflow

```
User: Analyze the requirements in docs/specs.md

Claude: [Calls run_full_workflow]
→ Mining: 42 requirements extracted
→ KG: 156 nodes, 234 edges
→ Validation: 35 passed, 7 failed
→ Duplicates: 2 groups found
→ Coverage: Missing security requirements
```

### Interactive Enhancement

```
User: Help me improve "The system shall be user-friendly"

Claude: [Calls evaluate_single]
→ Fails: measurability (0.3), testability (0.4), clarity (0.5)

Claude: What specific aspects of usability are important?
- Response time?
- Error recovery?
- Accessibility?

User: Response time and error messages

Claude: [Calls enhance_requirement]
→ Enhanced: "The system shall display feedback within 200ms and
   show descriptive error messages with recovery suggestions."
→ New score: 0.89 ✓
```

### Tech Stack Recommendation

```
User: What template fits these requirements?
- Web application
- User authentication
- REST API
- PostgreSQL database

Claude: [Calls recommend_techstack]
→ Top match: 02-api-service (95% match)
→ FastAPI + SQLAlchemy + Alembic
→ Includes auth, CRUD, and API documentation
```

## Configuration

Environment variables (in `.env`):

```bash
# Backend URLs
BACKEND_URL=http://localhost:8087
ARCH_TEAM_URL=http://localhost:8000

# Timeouts
MCP_DEFAULT_TIMEOUT=30000
MCP_STREAM_TIMEOUT=300000

# LLM
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Interactive CLI

For testing and debugging:

```bash
# Start interactive CLI
python -m mcp_server.cli.interactive

# Available commands
mcp> tools          # List all tools
mcp> resources      # List all resources
mcp> prompts        # List all prompts
mcp> call <tool>    # Call a tool interactively
mcp> read <uri>     # Read a resource
mcp> status         # Show system status
```

## IEEE 29148 Criteria

The validation tools check requirements against these 9 criteria:

| Criterion | Description | Threshold |
|-----------|-------------|-----------|
| **Atomic** | One requirement per statement | 0.7 |
| **Clarity** | Clear, precise language | 0.7 |
| **Testability** | Can be verified through testing | 0.7 |
| **Measurability** | Contains quantifiable metrics | 0.7 |
| **Concise** | No unnecessary words | 0.7 |
| **Unambiguous** | Single interpretation | 0.7 |
| **Consistent Language** | Consistent terminology | 0.7 |
| **Design Independent** | WHAT not HOW | 0.7 |
| **Purpose Independent** | No business justification | 0.7 |

**Verdict Rules:**
- **PASS**: Overall score ≥ 0.7 AND no criterion below 0.7
- **FAIL**: Overall score < 0.7 OR any criterion below 0.7

## Development

### Running Tests

```bash
pytest tests/mcp_server/
```

### Starting Services

```bash
# Backend (required)
python -m uvicorn backend.main:fastapi_app --port 8087

# Arch Team Service (optional, for mining)
python -m arch_team.service

# MCP Server (standalone)
python -m mcp_server.server
```

### Project Structure

The MCP server integrates with:

- **Backend** (`backend/`): FastAPI service on port 8087
- **Arch Team** (`arch_team/`): Multi-agent system on port 8000
- **Templates** (`templates/`): 15 project templates
- **Projects** (`projects/`): User projects

## Troubleshooting

### "Connection refused" errors

Ensure backend services are running:
```bash
python -m uvicorn backend.main:fastapi_app --port 8087
```

### Tool execution fails

Check service health:
```bash
curl http://localhost:8087/health
curl http://localhost:8000/health
```

### MCP not recognized by Claude

Re-add the MCP server:
```bash
claude mcp remove req-orchestrator
claude mcp add req-orchestrator -- python -m mcp_server.server
```

## License

MIT License
