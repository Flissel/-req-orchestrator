# arch_team Usage Analysis Report

**Generated:** 2025-11-06
**Updated:** 2025-11-06 (added backend_app_fastapi analysis)
**Purpose:** Identify unused files in arch_team directory, analyze external dependencies, and audit root directory usage

---

## Executive Summary

- **Total files analyzed:** 58 Python files in arch_team/
- **Unused files identified:** 14 files (24% of codebase)
- **Potentially unused (dev/experimental):** 4 files
- **External root directory dependencies:** 2 (backend_app, backend_app_v2)
- **Abandoned root directory:** backend_app_fastapi/ (early prototype, superseded)
- **arch_team tools connect to:** backend_app_v2:8087 (validation) + arch_team/service:8000 (mining/RAG/KG)

---

## 1. Unused Files (Not Referenced by Any Code)

These files are not imported by any other Python file in the codebase:

### Core Unused Files (10 files)

1. **arch_team/agents/prompts/master_qa_validator_prompt.py**
   - Orphaned prompt file
   - Not imported by any agent

2. **arch_team/agents/prompts/requirements_operator_prompt.py**
   - Orphaned prompt file
   - Not imported by any agent

3. **arch_team/model/chat_client.py**
   - Unused model abstraction layer
   - Replaced by direct OpenAI adapter usage

4. **arch_team/pipeline/store_requirements.py**
   - Legacy pipeline component
   - Imports backend_app but not used

5. **arch_team/pipeline/upload_ingest.py**
   - Legacy ingest pipeline
   - Imports backend_app but not used

6. **arch_team/runtime/agent_base.py**
   - Base class for agents (legacy)
   - Not used by any agent implementation

7. **arch_team/test_imports.py**
   - Test/debug script
   - Has imports but never executed

8. **arch_team/workbench/tools/base.py**
   - Tool base class (unused)
   - Not imported by any tool implementation

9. **arch_team/workbench/tools/python_code_execution.py**
   - Individual tool module (unused)
   - Functionality likely moved to workbench.py

10. **arch_team/workbench/tools/qdrant_search.py**
    - Individual tool module (unused)
    - Functionality likely moved to workbench.py or memory/retrieval.py

### Dev/Experimental Files (4 files)

Located in `arch_team/dev_folder_/` and `arch_team/distributed/`:

11. **arch_team/dev_folder_/github_operator_prompt.py**
    - Experimental GitHub integration
    - Not used in production

12. **arch_team/dev_folder_/qa_validator_prompt.py**
    - Duplicate/experimental QA prompt
    - Production version exists elsewhere

13. **arch_team/dev_folder_/user_clarification_prompt.py**
    - Duplicate/experimental clarification prompt
    - Production version exists elsewhere

14. **arch_team/distributed/host_stub.py**
    - Distributed processing stub (not implemented)
    - worker_stub.py exists but host not connected

---

## 2. Files Used Only by Tests

These files are only referenced in test code, not production:

1. **arch_team/autogen_tools/requirements_rag.py**
   - Used by: tests/arch_team/test_autogen_rag_tool.py
   - Also exported in __init__.py (may be intended for future use)

---

## 3. Entry Points (Executable Scripts)

Files with `__main__` blocks that can be executed directly:

| File | Purpose | Status |
|------|---------|--------|
| arch_team/main.py | Legacy EventBus-based workflow | ✓ Active |
| arch_team/service.py | Flask web service | ✓ Active |
| arch_team/autogen_rac.py | AutoGen RAC workflow | ✓ Active |
| arch_team/test_validation_e2e.py | E2E test script | ✓ Active |
| arch_team/dev_folder_/agent.py | Experimental agent | ? Dev only |
| arch_team/dev_folder_/test_github_agent.py | GitHub agent test | ? Dev only |
| arch_team/distributed/worker_stub.py | Worker stub | ? Not connected |

---

## 4. External Root Directory Dependencies

arch_team imports from these root directories:

### backend_app/ (7 files depend on it)

| arch_team File | What It Imports |
|----------------|-----------------|
| agents/chunk_miner.py | backend_app.embeddings, backend_app.llm |
| agents/solver.py | backend_app.vector_store |
| memory/qdrant_kg.py | backend_app.vector_store |
| memory/retrieval.py | backend_app.vector_store, backend_app.embeddings |
| pipeline/store_requirements.py | backend_app.db (unused file) |
| pipeline/upload_ingest.py | backend_app.ingest (unused file) |
| service.py | backend_app.db, backend_app.llm, backend_app.vector_store |

### backend_app_v2/ (1 file depends on it)

| arch_team File | What It Imports |
|----------------|-----------------|
| service.py | backend_app_v2.routers.lx_router |

### Root Directories NOT Used by arch_team

These exist but are never imported:
- agent_worker/
- backend_app_fastapi/
- config/
- dev/
- frontend/
- src/
- tests/ (tests import arch_team, not vice versa)

---

## 5. Key Production Files and Their Usage

### Master Agent Workflow

**arch_team/agents/master_agent.py** (Society of Mind coordinator)
- Used by: arch_team/service.py
- Integrates 7 specialized agents:
  1. Orchestrator (coordination)
  2. ChunkMiner (document processing)
  3. KG (Knowledge Graph)
  4. Validator (quality evaluation)
  5. RAG (semantic search)
  6. QA (final review)
  7. UserClarification (human-in-loop)

### Agent Tools

All tool modules are used exclusively by master_agent.py:

| Tool Module | Used By |
|-------------|---------|
| tools/mining_tools.py | master_agent.py |
| tools/kg_tools.py | master_agent.py |
| tools/validation_tools.py | master_agent.py |
| tools/rag_tools.py | master_agent.py |

### Core Services

| File | Purpose | Used By |
|------|---------|---------|
| service.py | Flask API | External HTTP clients |
| main.py | EventBus workflow | CLI execution |
| autogen_rac.py | AutoGen RAC | CLI execution |

---

## 6. Recommendations

### Immediate Actions

1. **Delete unused files** (10 core unused files)
   - Safe to remove with no impact on production
   - Consider archiving pipeline/ files if future migration needed

2. **Archive dev_folder_/** (4 experimental files)
   - Move to separate branch or docs/archive/
   - Not part of production codebase

3. **Document distributed/** stub
   - Either implement distributed processing or remove
   - Currently host_stub.py is not connected

4. **Review autogen_tools/requirements_rag.py**
   - Only used in tests
   - If intended for future use, document in CLAUDE.md
   - Otherwise, move to tests/ directory

### Code Organization

1. **Consolidate workbench tools**
   - Individual tool files (base.py, python_code_execution.py, qdrant_search.py) are unused
   - All functionality in workbench/workbench.py
   - Clean up tools/ directory structure

2. **Consolidate prompts**
   - Remove orphaned prompt files
   - Keep only prompts actively used by agents

3. **Document backend_app dependency**
   - arch_team heavily depends on backend_app
   - Consider creating formal interface/API layer
   - Current direct imports create tight coupling

### Testing

1. **Add tests for master_agent.py**
   - Critical production code
   - Only used by service.py (no test coverage found)

2. **Add tests for tools/**
   - Mining tools, KG tools, validation tools
   - All have __main__ blocks but no formal tests

---

## 7. Architecture Insights

### Current State

```
arch_team/
├── agents/          (7 specialized agents)
│   ├── master_agent.py  ← CENTRAL COORDINATOR
│   ├── chunk_miner.py   ← Used by service.py
│   ├── kg_agent.py      ← Used by service.py
│   ├── planner.py       ← Used by main.py (EventBus)
│   ├── solver.py        ← Used by main.py (EventBus)
│   └── verifier.py      ← Used by main.py (EventBus)
│
├── tools/           (Master agent tools)
│   ├── mining_tools.py      ← master_agent only
│   ├── kg_tools.py          ← master_agent only
│   ├── validation_tools.py  ← master_agent only
│   └── rag_tools.py         ← master_agent only
│
├── memory/          (Vector store, RAG, KG)
│   ├── qdrant_kg.py         ← Used by service.py
│   ├── retrieval.py         ← Used by main.py
│   └── qdrant_trace_sink.py ← Used by main.py
│
├── runtime/         (EventBus infrastructure)
│   └── (all used by main.py)
│
└── Entry Points
    ├── service.py       ← Flask API (master_agent + direct agents)
    ├── main.py          ← EventBus workflow (planner/solver/verifier)
    └── autogen_rac.py   ← AutoGen RAC workflow
```

### Two Parallel Workflows

1. **Master Agent Workflow** (service.py)
   - Society of Mind pattern
   - 7 coordinated agents
   - Newer implementation

2. **EventBus Workflow** (main.py)
   - Legacy event-driven pattern
   - 3 agents: Planner, Solver, Verifier
   - Sequencer with reflection rounds

**Note:** These workflows are independent and don't share agent implementations.

---

## 8. Dependency Graph Summary

```
External Dependencies:
  backend_app/
    ├─ embeddings (chunk_miner, retrieval)
    ├─ llm (chunk_miner, service)
    ├─ vector_store (solver, qdrant_kg, retrieval, service)
    ├─ db (service, store_requirements*)
    └─ ingest (upload_ingest*)

  backend_app_v2/
    └─ routers.lx_router (service)

  * = unused file
```

---

## 9. backend_app_fastapi/ Directory Analysis

### Contents

**Single file:** `backend_app_fastapi/api_fast.py` (191 lines)

**Intended Purpose:** FastAPI port/backup of Flask endpoints from `backend_app/api.py`

**Intended Port:** 8084
```bash
uvicorn backend_app_fastapi.api_fast:app --host 0.0.0.0 --port 8084
```

**Endpoints provided:**
- `GET /health` - Health check
- `GET /api/runtime-config` - Runtime configuration
- `GET /api/v1/criteria` - List evaluation criteria
- `POST /api/v1/evaluations` - Evaluate single requirement (with LLM)

### Status: UNUSED ❌

**Evidence:**
1. ❌ Not referenced anywhere in the codebase
2. ❌ Not documented in CLAUDE.md or README files
3. ❌ No Docker/startup scripts for port 8084
4. ❌ No arch_team tools use these endpoints
5. ✓ Superseded by backend_app_v2/ (port 8087)

### Why arch_team Doesn't Use It

**arch_team tools connect to different services:**

| Tool Module | API Base | Port | Endpoints Used |
|-------------|----------|------|----------------|
| validation_tools.py | backend_app_v2 | 8087 | `/api/v2/evaluate/single`<br>`/api/v1/validate/batch`<br>`/api/v1/validate/suggest` |
| mining_tools.py | arch_team/service | 8000 | `/api/mining/upload` |
| rag_tools.py | arch_team/service | 8000 | `/api/rag/duplicates`<br>`/api/rag/search`<br>`/api/rag/cluster` |
| kg_tools.py | arch_team/service | 8000 | `/api/kg/build`<br>`/api/kg/search/nodes`<br>`/api/kg/neighbors` |

**backend_app_fastapi provides:**
- Only `/api/v1/evaluations` (NOT `/api/v2/evaluate/single` that validation_tools needs)
- No batch validation
- No suggestions API
- No mining/RAG/KG endpoints

### Comparison to Active Services

| Feature | backend_app_fastapi (8084) | backend_app_v2 (8087) | arch_team/service (8000) |
|---------|---------------------------|----------------------|-------------------------|
| Status | ❌ Unused | ✓ Active | ✓ Active |
| Documentation | None | Full in CLAUDE.md | Full in CLAUDE.md |
| Validation | Single only | Batch + streaming | N/A |
| LangExtract | No | Yes | N/A |
| RAG | No | Yes | Yes (via tools) |
| Mining | No | No | Yes |
| KG | No | No | Yes |
| Used by arch_team | No | Yes | Yes |

### Recommendation

**backend_app_fastapi/** appears to be an **early/abandoned FastAPI prototype** that was replaced by the more comprehensive **backend_app_v2/** implementation.

**Action:** Safe to delete
- Zero references in codebase
- Zero documentation
- All functionality superseded
- No production usage

---

## Files to Keep

**Production (26 files):**
- All agents/ (except unused prompts)
- All tools/ (mining, kg, validation, rag)
- All memory/ (qdrant_kg, retrieval, trace_sink)
- All runtime/ (event_bus, sequencer, etc.)
- All model/ (except chat_client.py)
- service.py, main.py, autogen_rac.py

**Tests (1 file):**
- test_validation_e2e.py

**Entry points can execute standalone (7 files):**
- See section 3 above

---

## Analysis Scripts Created

Three analysis scripts were created for this report:

1. **analyze_arch_team_usage.py** - Initial static analysis
2. **analyze_comprehensive.py** - Includes test usage and dynamic imports
3. **analyze_external_deps.py** - External root directory dependencies

These scripts can be run again to verify cleanup progress.

---

## Conclusion

### arch_team Cleanup

The arch_team module has **24% unused code** that can be safely removed:
- 10 core unused files
- 4 dev/experimental files

The module depends on 2 root directories (backend_app, backend_app_v2) and maintains two parallel workflow systems (Master Agent + EventBus).

### backend_app_fastapi/ Removal

The **backend_app_fastapi/** directory (1 file, 191 lines) is an abandoned prototype that can be safely deleted:
- Zero references in codebase
- Not used by arch_team agents
- All functionality superseded by backend_app_v2/
- No documentation or startup scripts

### Summary

**Total cleanup opportunity:**
- 14 files in arch_team/ (24% of module)
- 1 directory (backend_app_fastapi/) at root level
- Cleanup will improve maintainability without affecting production functionality
