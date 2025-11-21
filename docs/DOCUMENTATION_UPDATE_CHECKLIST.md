# Documentation Update Checklist

**Status:** 3/9 files completed
**Last Updated:** 2025-11-10

## ✅ Completed

1. **docs/ARCHITECTURE_OVERVIEW.md** (NEW)
   - Comprehensive English architecture reference
   - All workflows documented
   - Current file paths
   - Arch team fully documented

2. **docs/architecture/SYSTEM_OVERVIEW.md**
   - Updated all file paths (backend_app/ → backend/core/, backend/services/, etc.)
   - Added arch_team sections
   - Added Society of Mind workflow diagrams
   - Updated all code references

3. **docs/architecture/FEATURES_AND_STACKS.md**
   - Updated all file paths
   - Added arch_team stack section
   - Added 12 showcases (including Requirements Mining, KG Construction)
   - Updated all diagrams

## 🔄 Remaining Updates

### Priority 1: Architecture Docs

#### 4. **docs/architecture/C4.md**

**Changes needed:**
- Update Container Diagram (Level 2):
  ```
  - Add: FastAPI+Flask :8087
  - Add: Arch Team :8000
  - Update: Qdrant ports (6333/6401)
  ```

- Update Component Diagram (Level 3):
  ```
  - backend/core/ (shared business logic)
  - backend/services/ (port-adapter pattern)
  - backend/routers/ (FastAPI routers)
  - backend/legacy/ (Flask compatibility)
  ```

- Add Arch Team Components:
  ```
  - Master Agent (Society of Mind)
  - Specialized Agents (ChunkMiner, KG, Validator, RAG, QA, UserClarification)
  - Memory layer (Qdrant KG)
  - SSE streaming
  ```

**File path replacements:**
- `backend_app/` → `backend/core/` (throughout)

#### 5. **docs/architecture/README.md**

**Changes needed:**
- Add link to ARCHITECTURE_OVERVIEW.md as primary reference
- Update "Abweichungen" section
- Add arch_team references
- Update all links to other docs

### Priority 2: Backend Docs

#### 6. **docs/backend/README.md**

**Changes needed:**
- Document consolidated backend structure:
  - FastAPI + Flask hybrid architecture
  - Service layer (ports/adapters pattern)
  - Core business logic
  - Routers organization

- Update file paths throughout:
  - `backend_app/api.py` → `backend/core/api.py` (Flask legacy) or `backend/routers/*_router.py` (FastAPI)
  - `backend_app/llm.py` → `backend/core/llm.py`
  - etc.

- Add sections:
  - Port-Adapter Pattern
  - Service Layer
  - Router Organization

#### 7. **docs/backend/ROUTES.md**

**Changes needed:**
- Add arch_team endpoints:
  ```
  ## Arch Team (Port 8000)

  ### Requirements Mining
  - POST /api/mining/upload
  - POST /api/mining/report

  ### Knowledge Graph
  - POST /api/kg/build
  - GET /api/kg/search/nodes
  - GET /api/kg/search/edges
  - GET /api/kg/neighbors

  ### Society of Mind
  - POST /api/arch_team/process
  - GET /api/workflow/stream
  - GET /api/clarification/stream

  ### Validation & RAG
  - POST /api/v2/evaluate/single
  - POST /api/v2/evaluate/batch
  - POST /api/rag/duplicates
  - POST /api/rag/search
  - POST /api/rag/related
  - POST /api/rag/coverage
  ```

- Update backend router paths:
  - `/api/v1/validate/*` → [backend.routers.validate_router](../../backend/routers/validate_router.py)
  - `/api/v1/lx/*` → [backend.routers.lx_router](../../backend/routers/lx_router.py)
  - etc.

#### 8. **docs/backend/{CONFIG,TESTS,DEPLOYMENT,etc.}.md**

**Changes needed for each:**
- Search for `backend_app/` and replace with appropriate path:
  - `backend/core/` for shared logic
  - `backend/services/` for services
  - `backend/routers/` for FastAPI routers
- Update line numbers (may have shifted)
- Add cross-references to ARCHITECTURE_OVERVIEW.md

### Priority 3: Showcases

#### 9. **docs/showcases/ALL_SHOWCASES.md**

**Changes needed:**
- Update all 10 existing showcases with current file paths
- Fix code references (line numbers may have shifted)
- Add 2 new showcases:
  - Showcase 11: Requirements Mining with ChunkMiner
  - Showcase 12: Knowledge Graph Construction & Visualization

**Pattern for updates:**
```markdown
# Showcase X: Title

## Code References
- OLD: [backend_app.api.validate_batch_optimized()](../../backend_app/api.py:599)
- NEW: [backend.routers.validate_router.*](../../backend/routers/validate_router.py)
```

#### 10. **docs/showcases/README.md**

**Changes needed:**
- Update navigation links
- Add links to showcases 11 & 12

## 🔧 Pattern for File Path Replacements

### Backend Module Mapping

| Old Path | New Path | Purpose |
|----------|----------|---------|
| `backend_app/__init__.py` | `backend/core/__init__.py` | Flask app factory |
| `backend_app/api.py` | `backend/core/api.py` | Flask legacy APIs |
| `backend_app/llm.py` | `backend/core/llm.py` | LLM integration |
| `backend_app/db.py` | `backend/core/db.py` | Database operations |
| `backend_app/embeddings.py` | `backend/core/embeddings.py` | Embeddings |
| `backend_app/vector_store.py` | `backend/core/vector_store.py` | Vector store |
| `backend_app/ingest.py` | `backend/core/ingest.py` | Document ingestion |
| `backend_app/batch.py` | `backend/core/batch.py` or `backend/services/batch_service.py` | Batch processing |
| `backend_app/utils.py` | `backend/core/utils.py` | Utilities |
| `backend_app/settings.py` | `backend/core/settings.py` | Configuration |
| `backend_app/logging_ext.py` | `backend/core/logging_ext.py` | Logging |
| `backend_app/memory.py` | `backend/core/memory.py` | Memory store |
| `backend_app/rag.py` | `backend/core/rag.py` | RAG logic |
| N/A | `backend/main.py` | FastAPI entry point (NEW) |
| N/A | `backend/routers/*_router.py` | FastAPI routers (NEW) |
| N/A | `backend/services/*_service.py` | Service layer (NEW) |
| N/A | `backend/services/ports.py` | Protocol definitions (NEW) |
| N/A | `backend/services/adapters.py` | Adapter implementations (NEW) |

### New Arch Team Paths

| Path | Purpose |
|------|---------|
| `arch_team/service.py` | Flask service with SSE |
| `arch_team/agents/master_agent.py` | Society of Mind orchestration |
| `arch_team/agents/chunk_miner.py` | Requirements mining |
| `arch_team/agents/kg_agent.py` | Knowledge Graph construction |
| `arch_team/agents/requirements_agent.py` | Society of Mind validation |
| `arch_team/memory/qdrant_kg.py` | KG storage (Qdrant) |
| `arch_team/memory/retrieval.py` | RAG retrieval |
| `arch_team/memory/qdrant_trace_sink.py` | Agent traces |
| `arch_team/tools/mining_tools.py` | Mining FunctionTools |
| `arch_team/tools/kg_tools.py` | KG FunctionTools |
| `arch_team/tools/validation_tools.py` | Validation FunctionTools |
| `arch_team/tools/rag_tools.py` | RAG FunctionTools |

## 📝 Search & Replace Patterns

### For German docs (SYSTEM_OVERVIEW.md, FEATURES_AND_STACKS.md, C4.md)

```bash
# Find all references to old paths
grep -r "backend_app/" docs/

# Common replacements needed:
backend_app/__init__.create_app() → backend.core.__init__.create_app()
backend_app.api.validate_batch_optimized() → backend.routers.validate_router.*
backend_app.api.files_ingest() → backend.core.api.files_ingest() (Flask legacy)
backend_app.llm.llm_evaluate() → backend.core.llm.llm_evaluate()
backend_app.db.init_db() → backend.core.db.init_db()
backend_app.vector_store.* → backend.core.vector_store.*
backend_app.batch.ensure_evaluation_exists() → backend.services.batch_service.* or backend.core.batch.*
```

### For showcases

```bash
# Find all code snippets and update paths
# Pattern: Look for ](../../backend_app/
# Replace with appropriate new path based on mapping above
```

## 🎯 Key Content to Add

### Arch Team Sections (where missing)

```markdown
### Arch Team (Society of Mind Multi-Agent System, Port 8000)

**Purpose:** Requirements mining, Knowledge Graph construction, validation with AutoGen 0.4+

**Main Components:**
- Master Agent: Society of Mind orchestration with 7 specialized agents
- ChunkMiner: Chunk-based requirements extraction from documents
- KG Agent: Knowledge graph construction (heuristic + LLM)
- Validator: Requirements quality evaluation
- RAG Agent: Semantic search, duplicate detection, clustering
- QA Agent: Final quality review
- UserClarification: Human-in-the-loop questions via SSE

**Key Features:**
- SSE Streaming: Real-time agent messages to frontend
- Evidence Tracking: Source provenance with sha1 + chunkIndex
- Knowledge Graph: Qdrant persistence (kg_nodes_v1, kg_edges_v1)
- Chain-of-Thought: Structured agent output (THOUGHTS, EVIDENCE, FINAL_ANSWER)

**Endpoints:**
- POST /api/mining/upload - Requirements mining from documents
- POST /api/kg/build - Knowledge graph construction
- POST /api/arch_team/process - Master workflow execution
- GET /api/workflow/stream - SSE stream for agent messages
- GET /api/clarification/stream - SSE stream for user questions
```

### Service Layer Section (where missing)

```markdown
### Service Layer (Port-Adapter Pattern)

**Purpose:** Clean architecture with framework-agnostic business logic

**Components:**
- **Ports** (`backend/services/ports.py`): Protocol definitions (LLMPort, EmbeddingsPort, VectorStorePort, PersistencePort)
- **Adapters** (`backend/services/adapters.py`): Concrete implementations binding to backend.core.*
- **Services**: Business logic orchestration
  - EvaluationService: Single/batch requirement evaluation
  - BatchService: Batch processing
  - CorrectionsService: Suggestion application
  - VectorService: Vector store management
  - RAGService: RAG queries

**Benefits:**
- Framework independence
- Easy mocking for tests
- Swappable implementations
```

## 🚀 Quick Start for Remaining Updates

1. **For C4.md:**
   ```bash
   # Open file
   code docs/architecture/C4.md

   # Find all "backend_app" and replace with appropriate path
   # Add arch_team container to Level 2 diagram
   # Add service layer to Level 3 diagram
   ```

2. **For README.md (architecture):**
   ```bash
   code docs/architecture/README.md

   # Add link to ../ARCHITECTURE_OVERVIEW.md
   # Update all navigation links
   ```

3. **For backend/README.md:**
   ```bash
   code docs/backend/README.md

   # Add consolidated backend structure section
   # Update all file paths
   # Add service layer documentation
   ```

4. **For backend/ROUTES.md:**
   ```bash
   code docs/backend/ROUTES.md

   # Add arch_team endpoints section (copy from FEATURES_AND_STACKS.md section 4)
   # Update backend router paths
   ```

5. **For showcases/ALL_SHOWCASES.md:**
   ```bash
   code docs/showcases/ALL_SHOWCASES.md

   # Use search & replace for file paths
   # Add showcases 11 & 12 (copy from FEATURES_AND_STACKS.md)
   ```

## 📚 Cross-References

All updated docs should cross-reference:
- **Primary:** [docs/ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md) (English, comprehensive)
- **Secondary:** [docs/architecture/SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) (German, compact)
- **Features:** [docs/architecture/FEATURES_AND_STACKS.md](./FEATURES_AND_STACKS.md) (German, features + stacks)

---

**Completion Status:** 3/9 files updated (33%)
**Estimated Time Remaining:** 2-3 hours for remaining files
**Next Priority:** C4.md, then backend/ROUTES.md
