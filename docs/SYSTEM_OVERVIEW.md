# Requirements Engineering Platform - System Overview

A multi-agent requirements engineering platform combining document mining, LLM-based validation, knowledge graph construction, and interactive enhancement.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python 3.11) |
| Frontend | React + Vite |
| LLM | OpenRouter (google/gemini-2.5-flash:nitro) |
| Vector Store | Qdrant |
| Database | SQLite |
| Multi-Agent | AutoGen 0.4+ |
| Container | Docker + docker-compose |

---

## Backend Services

### Service Layer (`backend/services/`)

| Service | Purpose | Input | Output |
|---------|---------|-------|--------|
| **EvaluationService** | Validates requirements against IEEE 29148 criteria | Requirement text | Score, verdict, per-criterion details |
| **ManifestService** | CRUD for requirement manifests | Requirement data | Stored manifest with evidence refs |
| **ClarificationService** | Handles user Q&A during validation | Identified gaps | User answers |
| **VectorService** | Manages embeddings and Qdrant | Text | Embeddings, search results |
| **CorrectionsService** | Applies merged corrections | Suggestions | Enhanced requirement text |

### Core Modules (`backend/core/`)

| Module | Purpose |
|--------|---------|
| `llm.py` | LLM calls: evaluate, suggest, rewrite, apply |
| `llm_async.py` | Async LLM service for parallel processing |
| `db.py` | SQLite schema, migrations, CRUD helpers |
| `vector_store.py` | Qdrant client and search operations |
| `embeddings.py` | Text embedding generation |
| `settings.py` | Configuration from environment |

---

## API Endpoints

### Master Workflow

```
POST /api/arch_team/process
```
Complete pipeline: mining → validation → KG → RAG

**Input:**
```json
{
  "files": ["base64_encoded_content"],
  "filenames": ["requirements.md"],
  "model": "google/gemini-2.5-flash:nitro",
  "kg_model": "same",
  "auto_validate": true
}
```

**Output:**
```json
{
  "requirements": [...],
  "validation_results": {...},
  "kg_nodes": [...],
  "kg_edges": [...],
  "stats": {...}
}
```

### Validation Endpoints (`/api/v1/validate/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/batch` | POST | Batch validate multiple requirements |
| `/suggest` | POST | Generate improvement suggestions |

### Manifest Endpoints (`/api/v1/manifest/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | List stored requirements (with filters) |
| `/sources` | GET | List unique source files/projects |
| `/{id}` | GET | Get single manifest with full details |

### Knowledge Graph (`/api/kg/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/build` | POST | Build KG from requirements |
| `/export` | GET | Export current KG nodes/edges |
| `/search/nodes` | GET | Semantic search nodes |
| `/neighbors` | GET | Find KG neighbors |

### TechStack (`/api/v1/techstack/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/detect` | POST | Detect tech stack from requirements |
| `/templates` | GET | List available project templates |

---

## Multi-Agent System (`arch_team/agents/`)

### Core Agents

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **MasterAgent** | Orchestrates entire workflow | Files, config | Requirements, KG, validation |
| **ChunkMinerAgent** | Extracts requirements from documents | md, txt, pdf, docx | DTOs: `{req_id, title, tag, evidence_refs}` |
| **KGAbstractionAgent** | Builds knowledge graph | Requirement DTOs | Nodes, Edges (persisted to Qdrant) |
| **ValidationDelegatorAgent** | Distributes validation across workers | Requirements list | Validation results per requirement |
| **ValidationWorkerAgent** | Evaluates single requirement | Requirement text | Score, evaluation, suggestions |
| **RewriteDelegatorAgent** | Distributes rewrite tasks | Failing requirements | Rewrite jobs |
| **RewriteWorkerAgent** | Rewrites requirement | Poor-scoring text | Enhanced text + new score |
| **ClarificationAgent** | Asks users for missing info | Identified gaps | User answers |
| **DecisionMakerAgent** | Routes requirements | Validation results | pass/fail/rewrite/clarify |
| **SocietyOfMindEnhancement** | Iterative improvement | Original text | Enhanced text, splits |

### Criterion Specialists (`criterion_specialists.py`)

Nine specialized agents evaluate individual IEEE 29148 criteria:

1. **ClarityAgent** - Is the requirement clear and understandable?
2. **TestabilityAgent** - Can it be verified/tested?
3. **MeasurabilityAgent** - Are measurable criteria defined?
4. **AtomicityAgent** - Is it a single, atomic requirement?
5. **ConcisenessAgent** - Is it concise without unnecessary words?
6. **UnambiguousAgent** - Is there only one interpretation?
7. **ConsistentLanguageAgent** - Does it use consistent terminology?
8. **DesignIndependentAgent** - Is it free of implementation details?
9. **PurposeIndependentAgent** - Does it focus on what, not why?

---

## Frontend Tabs

### Tab 1: Mining (Start Mining)

**Purpose:** Upload documents and extract requirements

**Actions:**
- Upload documents (md, txt, pdf, docx, xlsx)
- Configure mining parameters
- Select LLM model
- Enable auto-validation
- Start Master Workflow

**Components:** `Configuration.jsx`, `FilePreview`, `Shuttle.jsx`

### Tab 2: Requirements

**Purpose:** View and manage extracted requirements

**Features:**
- Display all requirements in table
- Color-coded validation scores (green ≥0.7, red <0.7)
- Click to view requirement details
- Load from: Mining output, JSON file, Database, KG

**Components:** `RequirementsTable.jsx`, `RequirementDetailModal.jsx`

### Tab 3: Validation

**Purpose:** Validate and improve failing requirements

**Features:**
- List failing requirements (score < 0.7)
- Inline validation panel
- Real-time SSE streaming progress
- Batch validation button
- Suggestion application
- Q&A flow for clarification

**Workflow:**
1. Select requirement → ValidationDetailPanel opens
2. Click "Start Validation"
3. LLM evaluates against 10 criteria
4. If score < threshold: suggest → rewrite → re-evaluate
5. Loop until threshold met or max iterations

**Components:** `ValidationTab.jsx`, `ValidationDetailPanel.jsx`, `BatchValidationModal.jsx`

### Tab 4: Knowledge Graph

**Purpose:** Visualize requirement relationships

**Features:**
- Interactive graph visualization (vis.js)
- Node types: Requirements, Tags, Actors, Entities, Actions
- Edge types: HAS_TAG, HAS_ACTOR, HAS_ACTION, ON_ENTITY
- Split view: requirement list + graph
- Click nodes to inspect
- Semantic search

**Components:** `KnowledgeGraph.jsx`

### Tab 5: TechStack

**Purpose:** Detect stack and generate project scaffold

**Sub-tabs:**
- **Templates**: Browse and apply project templates
- **Detect**: Auto-detect tech stack from requirements
- **Pipeline**: Run full TechStack pipeline
- **KG Status**: View KG statistics

**Components:** `TechStackTab.jsx`

---

## Complete Pipeline Flow

```
┌────────────────────────────────────────────────────────┐
│ 1. DOCUMENT UPLOAD                                      │
│    User uploads: md, txt, pdf, docx, xlsx              │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 2. CHUNK MINING (ChunkMinerAgent)                       │
│    - Extract text from documents                        │
│    - Create overlap chunks (800 tokens, 200 overlap)    │
│    - LLM mines requirements per chunk                   │
│    → Output: DTOs {req_id, title, tag, evidence_refs}  │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 3. MANIFEST PERSISTENCE (Phase 1.5)                     │
│    - Store requirements in SQLite                       │
│    - Record source file, chunk index, sha1              │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 4. KNOWLEDGE GRAPH (KGAbstractionAgent)                 │
│    - Extract entities/relationships                     │
│    - Build heuristic KG (optionally LLM-enhanced)       │
│    - Persist to Qdrant collections                      │
│    → Output: Nodes [], Edges []                        │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 5. VALIDATION (ValidationDelegatorAgent)                │
│    - Evaluate each requirement (10 criteria)            │
│    - Parallel processing (max 10 concurrent)            │
│    → Output: scores, evaluations, pass/fail counts     │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 6. REWRITE (RewriteDelegatorAgent)                      │
│    - Process failing requirements (score < 0.7)         │
│    - Generate improved text                             │
│    - Re-evaluate after rewrite                          │
│    → Output: enhanced text, new_score, new_evaluation  │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 7. SCORE PERSISTENCE (Phase 3c)                         │
│    - Update validation_score in manifest table          │
│    - Store validation_verdict (pass/fail)               │
└──────────────────────┬─────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────────┐
│ 8. RETURN RESULTS                                       │
│    - requirements: all mined requirements               │
│    - validation_results: scores and evaluations         │
│    - rewrite_results: enhanced texts                    │
│    - kg: nodes and edges for visualization              │
└────────────────────────────────────────────────────────┘
```

---

## Data Storage

### SQLite Tables

```sql
-- requirement_manifest: Stored requirements
requirement_manifest(
  requirement_id TEXT PRIMARY KEY,
  original_text TEXT,
  current_text TEXT,
  source_file TEXT,
  source_type TEXT,
  current_stage TEXT,
  validation_score REAL,      -- Added in Phase 3c
  validation_verdict TEXT,    -- Added in Phase 3c
  metadata TEXT,
  created_at TEXT,
  updated_at TEXT
)

-- processing_stage: Lifecycle tracking
processing_stage(
  id INTEGER PRIMARY KEY,
  requirement_id TEXT,
  stage_name TEXT,
  status TEXT,
  score REAL,
  verdict TEXT,
  started_at TEXT,
  completed_at TEXT
)

-- evidence_reference: Source provenance
evidence_reference(
  requirement_id TEXT,
  source_file TEXT,
  sha1 TEXT,
  chunk_index INTEGER,
  is_neighbor BOOLEAN
)
```

### Qdrant Collections

| Collection | Purpose |
|------------|---------|
| `requirements_v1` | Embeddings for RAG/semantic search |
| `kg_nodes_v1` | Knowledge graph nodes |
| `kg_edges_v1` | Knowledge graph edges |
| `arch_trace` | Agent execution traces |

---

## Configuration

### Environment Variables

```bash
# LLM Provider (OpenRouter)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=google/gemini-2.5-flash:nitro

# Embeddings (OpenAI)
OPENAI_API_KEY=sk-...
EMBEDDINGS_MODEL=text-embedding-3-small

# Database
SQLITE_PATH=/app/data/app.db

# Vector Store
QDRANT_URL=http://localhost
QDRANT_PORT=6333

# Thresholds
VERDICT_THRESHOLD=0.7

# Parallelism
VALIDATION_MAX_CONCURRENT=10
REWRITE_MAX_CONCURRENT=10
```

### Docker Compose

```bash
# Start all services
docker-compose up --build

# Services:
# - app (FastAPI + React): localhost:8087
# - qdrant: localhost:6333
```

---

## Key Workflows

### Workflow A: Standard Mining + Validation

1. Upload document in Mining tab
2. Click "Start Mining"
3. Wait for extraction + KG building + validation
4. View results in Requirements tab
5. Auto-validation toast appears for failing reqs
6. Click "Start Auto-Validation" or manually validate

### Workflow B: Manual Validation

1. Go to Validation tab
2. Click on failing requirement
3. ValidationDetailPanel opens inline
4. Click "Start Validation"
5. Review suggestions, accept/reject
6. Requirement is rewritten and re-evaluated
7. Close panel when satisfied

### Workflow C: Load from Database

1. Click "From DB" button
2. Select project/source file
3. Requirements load with validation_score
4. View scores in Requirements tab
5. Continue validation if needed

---

## Important Files

| Purpose | File |
|---------|------|
| FastAPI entry | `backend/main.py` |
| Master workflow | `backend/routers/arch_team_router.py` |
| Master agent | `arch_team/agents/master_agent.py` |
| Mining agent | `arch_team/agents/chunk_miner.py` |
| Validation agent | `arch_team/agents/validation_delegator.py` |
| Rewrite agent | `arch_team/agents/rewrite_delegator.py` |
| KG agent | `arch_team/agents/kg_agent.py` |
| Main React app | `src/AppV2.jsx` |
| Validation UI | `src/components/ValidationTab.jsx` |
| Validation panel | `src/components/ValidationDetailPanel.jsx` |
| Requirements table | `src/components/RequirementsTable.jsx` |
| KG visualization | `src/components/KnowledgeGraph.jsx` |
| Database schema | `backend/core/db.py` |
| LLM integration | `backend/core/llm.py` |
