# Master Society of Mind - arch_team Complete Workflow

## Architecture Overview

Integration aller arch_team Agents in eine zentrale Society of Mind Struktur für kohärenten, orchestrierten Requirements Engineering Workflow.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ SocietyOfMindAgent ("arch_team_master")                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  RoundRobinGroupChat (max_turns=100)                              │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │ 1️⃣ OrchestratorAgent (no tools, coordinates workflow)       │  │  │
│  │  │ 2️⃣ ChunkMinerAgent (mining_tools: upload, chunk, extract)  │  │  │
│  │  │ 3️⃣ KGAgent (kg_tools: build_kg, query_kg, export)          │  │  │
│  │  │ 4️⃣ ValidationAgent (eval_tools: evaluate, rewrite)         │  │  │
│  │  │ 5️⃣ RAGAgent (rag_tools: semantic_search, find_duplicates)  │  │  │
│  │  │ 6️⃣ QAValidator (no tools, reviews with RAG context)        │  │  │
│  │  │ 7️⃣ UserClarificationAgent (ask_user tool, final step)      │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │  Termination: TextMentionTermination("WORKFLOW_COMPLETE")          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Agent Roles & Responsibilities

### 1. OrchestratorAgent (Coordinator)
**Role:** Workflow coordination and task delegation
**Tools:** None (pure coordination)
**Responsibilities:**
- Receives user request and breaks down into phases
- Delegates tasks to specialized agents
- Monitors progress and ensures workflow completion
- Signals "WORKFLOW_COMPLETE" when done

**Workflow Phases:**
```
Phase 1: Mining     → @ChunkMiner extract requirements from documents
Phase 2: KG Build   → @KG build knowledge graph from requirements
Phase 3: Validation → @Validator evaluate and improve requirements
Phase 4: RAG        → @RAG find duplicates and semantic similarities
Phase 5: QA         → @QA review final quality with RAG context
Phase 6: Clarify    → @UserClarification ask user if needed
Phase 7: Complete   → WORKFLOW_COMPLETE
```

### 2. ChunkMinerAgent (Document Processing)
**Role:** Extract requirements from uploaded documents
**Tools:**
- `upload_documents(files: List[File]) -> UploadResult`
- `chunk_documents(files: List[str], chunk_size: int, overlap: int) -> List[Chunk]`
- `extract_requirements(chunks: List[Chunk]) -> List[Requirement]`

**Workflow:**
```python
1. upload_documents() → Store files
2. chunk_documents() → Split into chunks (default: 800 tokens, 200 overlap)
3. extract_requirements() → LLM extraction per chunk
4. Return: List[Requirement] with metadata
```

**Output Format:**
```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "text": "Die App muss eine Login-Funktion bieten",
      "source": "dokument.md",
      "chunk_id": "chunk-1",
      "confidence": 0.95
    }
  ]
}
```

### 3. KGAgent (Knowledge Graph)
**Role:** Build and manage Knowledge Graph from requirements
**Tools:**
- `build_knowledge_graph(requirements: List[Requirement], use_llm: bool) -> KGResult`
- `query_kg(query: str, limit: int) -> List[Node]`
- `export_kg(format: str) -> str`

**Workflow:**
```python
1. build_knowledge_graph(requirements) → Create nodes/edges
   - LLM-based entity/relation extraction (if use_llm=True)
   - Rule-based fallback
   - Store in Qdrant
2. Return: {"nodes": [...], "edges": [...]}
```

**KG Structure:**
```
Nodes:
  - Type: Requirement, Feature, Actor, System, Constraint
  - Properties: id, label, type, metadata

Edges:
  - Type: DEPENDS_ON, CONFLICTS_WITH, IMPLEMENTS, RELATES_TO
  - Properties: source, target, type, weight
```

### 4. ValidationAgent (Quality Evaluation)
**Role:** Evaluate and improve requirements quality
**Tools:**
- `evaluate_requirement(text: str, criteria_keys: List[str]) -> EvalResult`
- `rewrite_requirement(text: str, issues: List[str]) -> str`
- `suggest_improvements(text: str) -> List[Suggestion]`

**Workflow:**
```python
1. evaluate_requirement() → Score on clarity, testability, measurability
2. If score < 0.7:
   a. suggest_improvements() → Get atomic fixes
   b. rewrite_requirement() → Generate improved version
3. Return: {"original": "...", "improved": "...", "score": 0.85}
```

**Evaluation Criteria:**
- **clarity:** Eindeutig und verständlich? (0-1)
- **testability:** Testbar und verifizierbar? (0-1)
- **measurability:** Messbare Akzeptanzkriterien? (0-1)

### 5. RAGAgent (Semantic Search & Retrieval)
**Role:** Find similar requirements, detect duplicates, provide context
**Tools:**
- `semantic_search(query: str, top_k: int, threshold: float) -> List[Match]`
- `find_duplicates(requirements: List[str], threshold: float) -> List[DuplicateGroup]`
- `get_related_requirements(req_id: str, relation_type: str) -> List[Requirement]`

**Workflow:**
```python
1. semantic_search(query) → Qdrant vector search
2. find_duplicates(requirements, threshold=0.90) → Group similar requirements
3. get_related_requirements(req_id) → Find dependencies/conflicts via KG
```

**Output Example:**
```json
{
  "duplicates": [
    {
      "group_id": "DUP-001",
      "requirements": [
        {"id": "REQ-005", "text": "App muss schnell sein", "similarity": 0.95},
        {"id": "REQ-012", "text": "System soll performant sein", "similarity": 0.92}
      ]
    }
  ]
}
```

### 6. QAValidator (Quality Assurance)
**Role:** Final quality review with context from RAG
**Tools:** None (reviews outputs from other agents)

**Responsibilities:**
- Review all requirements from Validation phase
- Check for duplicates using RAG results
- Verify semantic consistency
- Signal "READY_FOR_CLARIFICATION" or "NEEDS_IMPROVEMENT"

**Review Checklist:**
```
✓ All requirements scored > 0.7
✓ No unresolved duplicates
✓ Semantic consistency across requirements
✓ User Story format where applicable
✓ Acceptance criteria present
✓ Dependencies mapped in KG
```

### 7. UserClarificationAgent (Human-in-the-Loop)
**Role:** Ask user for clarification when needed (FINAL STEP)
**Tools:**
- `ask_user(question: str, suggested_answers: List[str]) -> str`

**Triggers:**
- Low-confidence requirements (score < 0.5)
- Conflicting requirements detected
- Missing context for critical features
- Ambiguous acceptance criteria

**Workflow:**
```python
1. Identify issues requiring user input
2. ask_user(question, suggestions) → SSE broadcast to frontend
3. Wait for user response (file-based polling)
4. Process answer and update requirements
5. Signal "WORKFLOW_COMPLETE"
```

## Data Exchange Between Agents

### 1. ChunkMiner → KG Agent
**Data Type:** `List[RequirementDTO]`
```python
[
  {
    "id": "REQ-001",
    "text": "Die App muss eine Login-Funktion bieten",
    "source": "feature_requirements.md",
    "chunk_id": "chunk-1",
    "confidence": 0.95,
    "metadata": {
      "page": 1,
      "line": 42,
      "extraction_method": "llm"
    }
  }
]
```

### 2. KG Agent → Validator
**Data Type:** `KnowledgeGraphDTO + List[RequirementDTO]`
```python
{
  "requirements": [...],  # Original requirements from ChunkMiner
  "knowledge_graph": {
    "nodes": [
      {
        "id": "node-1",
        "label": "Login System",
        "type": "Feature",
        "properties": {"priority": "high"}
      }
    ],
    "edges": [
      {
        "source": "node-1",
        "target": "node-5",
        "type": "DEPENDS_ON",
        "weight": 0.8
      }
    ]
  }
}
```

### 3. Validator → RAG
**Data Type:** `ValidationResultDTO`
```python
{
  "original_requirements": [...],
  "evaluated_requirements": [
    {
      "id": "REQ-001",
      "original_text": "App muss schnell sein",
      "improved_text": "Das System muss Suchanfragen innerhalb von 200ms verarbeiten",
      "scores": {
        "clarity": 0.85,
        "testability": 0.90,
        "measurability": 0.95,
        "overall": 0.90
      },
      "suggestions": [
        "Spezifische Metrik hinzugefügt",
        "Messbare Akzeptanzkriterium definiert"
      ]
    }
  ],
  "needs_improvement": ["REQ-003", "REQ-007"]
}
```

### 4. RAG → QA
**Data Type:** `RAGAnalysisDTO`
```python
{
  "requirements": [...],  # From Validator
  "duplicate_groups": [
    {
      "group_id": "DUP-001",
      "requirements": [
        {"id": "REQ-005", "similarity": 0.95},
        {"id": "REQ-012", "similarity": 0.92}
      ],
      "suggested_merge": "Das System muss skalierbar und performant sein"
    }
  ],
  "semantic_clusters": [
    {
      "cluster_id": "CLUSTER-001",
      "theme": "Authentication & Security",
      "requirements": ["REQ-001", "REQ-002", "REQ-009"]
    }
  ],
  "related_requirements": {
    "REQ-001": [
      {
        "id": "REQ-004",
        "relation": "DEPENDS_ON",
        "explanation": "Login depends on User Database"
      }
    ]
  }
}
```

### 5. QA → UserClarification
**Data Type:** `QAReportDTO`
```python
{
  "validation_status": "needs_clarification",
  "summary": {
    "total_requirements": 25,
    "avg_quality_score": 0.82,
    "duplicates_found": 2,
    "conflicts_found": 1,
    "low_confidence": 3
  },
  "issues": [
    {
      "issue_id": "ISSUE-001",
      "type": "duplicate",
      "severity": "medium",
      "description": "REQ-005 and REQ-012 are semantically identical",
      "affected_requirements": ["REQ-005", "REQ-012"],
      "suggested_resolution": "Merge into single requirement"
    },
    {
      "issue_id": "ISSUE-002",
      "type": "low_confidence",
      "severity": "high",
      "description": "REQ-007 has unclear acceptance criteria",
      "affected_requirements": ["REQ-007"],
      "context": "Original text: 'System soll benutzerfreundlich sein'"
    }
  ]
}
```

### 6. UserClarification → Orchestrator (Final)
**Data Type:** `WorkflowResultDTO`
```python
{
  "status": "completed",
  "final_requirements": [
    {
      "id": "REQ-001",
      "text": "Das System muss Suchanfragen innerhalb von 200ms verarbeiten",
      "quality_score": 0.90,
      "user_approved": true,
      "metadata": {...}
    }
  ],
  "knowledge_graph": {...},
  "quality_metrics": {
    "avg_clarity": 0.88,
    "avg_testability": 0.85,
    "avg_measurability": 0.87,
    "total_requirements": 24,  # After merging duplicates
    "user_interactions": 3
  },
  "user_clarifications": [
    {
      "question": "REQ-5 and REQ-12 are duplicates. Merge or keep separate?",
      "answer": "Merge",
      "timestamp": "2025-01-15T14:32:00Z"
    }
  ]
}
```

## Data Flow Diagram

```
┌─────────────┐
│   User      │ uploads files
└──────┬──────┘
       │
       v
┌─────────────────────────────────────────────────────────────┐
│ ChunkMiner                                                  │
│  Input:  files (List[File])                                │
│  Output: requirements (List[RequirementDTO])               │
└──────┬──────────────────────────────────────────────────────┘
       │ List[RequirementDTO]
       v
┌─────────────────────────────────────────────────────────────┐
│ KG Agent                                                    │
│  Input:  requirements (List[RequirementDTO])               │
│  Output: kg_data (KnowledgeGraphDTO)                       │
└──────┬──────────────────────────────────────────────────────┘
       │ KnowledgeGraphDTO + requirements
       v
┌─────────────────────────────────────────────────────────────┐
│ Validator                                                   │
│  Input:  requirements + kg                                 │
│  Output: evaluated_requirements (ValidationResultDTO)      │
└──────┬──────────────────────────────────────────────────────┘
       │ ValidationResultDTO
       v
┌─────────────────────────────────────────────────────────────┐
│ RAG Agent                                                   │
│  Input:  evaluated_requirements                            │
│  Output: rag_analysis (RAGAnalysisDTO)                     │
└──────┬──────────────────────────────────────────────────────┘
       │ RAGAnalysisDTO
       v
┌─────────────────────────────────────────────────────────────┐
│ QA Validator                                                │
│  Input:  rag_analysis                                      │
│  Output: qa_report (QAReportDTO)                           │
└──────┬──────────────────────────────────────────────────────┘
       │ QAReportDTO (if issues found)
       v
┌─────────────────────────────────────────────────────────────┐
│ UserClarification                                           │
│  Input:  qa_report.issues                                  │
│  Output: workflow_result (WorkflowResultDTO)               │
└──────┬──────────────────────────────────────────────────────┘
       │ WorkflowResultDTO
       v
┌─────────────┐
│  Frontend   │ displays results
└─────────────┘
```

## Complete Workflow Example

### Input:
```
User uploads: "feature_requirements.md"
Request: "Extract and validate all requirements"
```

### Execution:

```
[Orchestrator]
  ├─> @ChunkMiner extract requirements from feature_requirements.md
  │
[ChunkMiner]
  ├─> upload_documents([feature_requirements.md])
  ├─> chunk_documents(files, chunk_size=800, overlap=200)
  ├─> extract_requirements(chunks)
  └─> ✓ Extracted 25 requirements
  │
[Orchestrator]
  ├─> @KG build knowledge graph from requirements
  │
[KG]
  ├─> build_knowledge_graph(requirements, use_llm=True)
  └─> ✓ Created 25 nodes, 18 edges
  │
[Orchestrator]
  ├─> @Validator evaluate and improve requirements
  │
[Validator]
  ├─> evaluate_requirement(req_1) → score: 0.65
  ├─> suggest_improvements(req_1) → ["Add acceptance criteria", "Specify performance metric"]
  ├─> rewrite_requirement(req_1) → improved version
  └─> ✓ Improved 8 requirements, avg score: 0.82
  │
[Orchestrator]
  ├─> @RAG find duplicates and similarities
  │
[RAG]
  ├─> find_duplicates(requirements, threshold=0.90)
  ├─> semantic_search(req_5, top_k=5)
  └─> ✓ Found 2 duplicate groups
  │
[Orchestrator]
  ├─> @QA review final quality
  │
[QA]
  ├─> Reviews: All requirements score > 0.7 ✓
  ├─> Reviews: 2 duplicates need merging ✗
  └─> NEEDS_IMPROVEMENT
  │
[Orchestrator]
  ├─> @UserClarification ask about duplicates
  │
[UserClarification]
  ├─> ask_user("REQ-5 and REQ-12 are duplicates. Merge or keep separate?", ["Merge", "Keep both"])
  ├─> User answers: "Merge"
  └─> ✓ Merged requirements
  │
[Orchestrator]
  └─> WORKFLOW_COMPLETE
```

## Detailed Data Flow: Input → Process → Output

This section shows EXACTLY what data enters each agent, what processing happens, and what data comes out.

### STEP 1: User → Orchestrator

**INPUT (from User):**
```json
{
  "files": ["requirements.docx", "features.md"],
  "config": {
    "model": "gpt-4o-mini",
    "chunk_size": 800,
    "chunk_overlap": 200,
    "validation_threshold": 0.7,
    "use_llm_kg": true
  }
}
```

**PROCESS (Orchestrator):**
- Parse files list: 2 files found
- Determine workflow: mining → kg → validation → rag → qa
- Generate delegation message for ChunkMiner

**OUTPUT (to ChunkMiner):**
```
"@ChunkMiner, please process these 2 files (requirements.docx, features.md) using chunk_size=800 and model=gpt-4o-mini"
```

---

### STEP 2: Orchestrator → ChunkMiner → Orchestrator

**INPUT (ChunkMiner receives):**
- files: ["requirements.docx", "features.md"]
- model: "gpt-4o-mini"
- chunk_size: 800
- chunk_overlap: 200

**PROCESS (ChunkMiner tool calls):**
```python
# Tool call 1: upload_and_mine_documents()
result = upload_and_mine_documents(
    files=["requirements.docx", "features.md"],
    model="gpt-4o-mini",
    chunk_size=800,
    chunk_overlap=200,
    neighbor_refs=True
)
```

**Backend Processing:**
1. Load requirements.docx → 2500 words
2. Load features.md → 1200 words
3. Chunk documents:
   - requirements.docx → 5 chunks (chunk_0 to chunk_4)
   - features.md → 3 chunks (chunk_5 to chunk_7)
4. For each chunk, call LLM to extract requirements
5. Deduplicate and assign IDs

**OUTPUT (ChunkMiner returns):**
```json
{
  "success": true,
  "items": [
    {
      "req_id": "REQ-001",
      "text": "System must authenticate users using OAuth 2.0",
      "source": "requirements.docx",
      "chunk_id": "chunk_0",
      "confidence": 0.95,
      "metadata": {
        "page": 1,
        "extraction_method": "llm",
        "neighbors": ["chunk_1"]
      }
    },
    {
      "req_id": "REQ-002",
      "text": "API response time must be under 200ms for 95% of requests",
      "source": "requirements.docx",
      "chunk_id": "chunk_2",
      "confidence": 0.92,
      "metadata": {
        "page": 2,
        "extraction_method": "llm",
        "neighbors": ["chunk_1", "chunk_3"]
      }
    },
    {
      "req_id": "REQ-003",
      "text": "System should support dark mode",
      "source": "features.md",
      "chunk_id": "chunk_5",
      "confidence": 0.88,
      "metadata": {
        "extraction_method": "llm",
        "neighbors": ["chunk_6"]
      }
    }
    // ... 22 more requirements (total 25)
  ],
  "count": 25,
  "chunks_processed": 8
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"MINING_COMPLETE - Successfully extracted 25 requirements from 8 chunks across 2 documents (requirements.docx, features.md). Average confidence: 0.91"
```

---

### STEP 3: Orchestrator → KGAgent → Orchestrator

**INPUT (KGAgent receives):**
```json
{
  "items": [
    {"req_id": "REQ-001", "text": "System must authenticate users using OAuth 2.0", ...},
    {"req_id": "REQ-002", "text": "API response time must be under 200ms for 95% of requests", ...},
    // ... 23 more
  ],
  "use_llm": true,
  "persist": "qdrant"
}
```

**PROCESS (KGAgent tool calls):**
```python
# Tool call: build_knowledge_graph()
result = build_knowledge_graph(
    items=[...],  # 25 requirements
    use_llm=True,
    persist="qdrant"
)
```

**Backend Processing:**
1. For each requirement, extract entities via LLM:
   - REQ-001: Entities = ["System", "User", "OAuth 2.0"], Relations = ["authenticates_with"]
   - REQ-002: Entities = ["API", "Response"], Relations = ["has_metric"]
   - REQ-003: Entities = ["System", "Dark Mode"], Relations = ["supports"]
2. Build graph:
   - Deduplicate entities → Create nodes
   - Extract relations → Create edges
3. Generate embeddings for each node
4. Persist to Qdrant vector store

**OUTPUT (KGAgent returns):**
```json
{
  "success": true,
  "nodes": [
    {
      "id": "node_1",
      "label": "System",
      "type": "Actor",
      "properties": {
        "source_reqs": ["REQ-001", "REQ-003"],
        "mentions": 2
      }
    },
    {
      "id": "node_2",
      "label": "OAuth 2.0",
      "type": "Technology",
      "properties": {
        "source_reqs": ["REQ-001"],
        "category": "Authentication"
      }
    },
    {
      "id": "node_3",
      "label": "API",
      "type": "Component",
      "properties": {
        "source_reqs": ["REQ-002"],
        "performance_metric": "response_time"
      }
    }
    // ... 22 more nodes (total 25 nodes)
  ],
  "edges": [
    {
      "source": "node_1",
      "target": "node_2",
      "relation": "authenticates_with",
      "properties": {
        "source_req": "REQ-001"
      }
    },
    {
      "source": "node_3",
      "target": "node_4",
      "relation": "has_metric",
      "properties": {
        "source_req": "REQ-002",
        "threshold": "200ms"
      }
    }
    // ... 16 more edges (total 18 edges)
  ],
  "stats": {
    "node_count": 25,
    "edge_count": 18,
    "requirements_linked": 25,
    "entity_types": {
      "Actor": 3,
      "Component": 8,
      "Technology": 6,
      "Feature": 5,
      "Metric": 3
    }
  }
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"KG_COMPLETE - Built knowledge graph with 25 nodes and 18 edges from 25 requirements. Persisted to Qdrant. Entity types: 3 Actors, 8 Components, 6 Technologies, 5 Features, 3 Metrics."
```

---

### STEP 4: Orchestrator → ValidationAgent → Orchestrator

**INPUT (ValidationAgent receives):**
```json
{
  "requirements": [
    {"req_id": "REQ-001", "text": "System must authenticate users using OAuth 2.0"},
    {"req_id": "REQ-002", "text": "API response time must be under 200ms for 95% of requests"},
    {"req_id": "REQ-003", "text": "System should support dark mode"}
    // ... 22 more
  ],
  "criteria_keys": ["clarity", "testability", "measurability"],
  "threshold": 0.7
}
```

**PROCESS (ValidationAgent processes each requirement):**

**For REQ-001:**
```python
# Tool call 1: evaluate_requirement()
eval_result = evaluate_requirement(
    text="System must authenticate users using OAuth 2.0",
    criteria_keys=["clarity", "testability", "measurability"]
)
# Result:
{
  "scores": {
    "clarity": 0.85,
    "testability": 0.80,
    "measurability": 0.75
  },
  "overall": 0.80,
  "passed": True  # 0.80 >= 0.7
}
# → PASS, no action needed
```

**For REQ-003:**
```python
# Tool call 1: evaluate_requirement()
eval_result = evaluate_requirement(
    text="System should support dark mode",
    criteria_keys=["clarity", "testability", "measurability"]
)
# Result:
{
  "scores": {
    "clarity": 0.60,
    "testability": 0.45,
    "measurability": 0.30
  },
  "overall": 0.45,
  "passed": False  # 0.45 < 0.7
}

# Tool call 2: suggest_improvements()
suggestions = suggest_improvements(text="System should support dark mode")
# Result:
{
  "suggestions": [
    "Specify which UI components need dark mode",
    "Add acceptance criteria for color contrast ratios",
    "Define user preference persistence mechanism"
  ]
}

# Tool call 3: rewrite_requirement()
rewrite_result = rewrite_requirement(
    text="System should support dark mode",
    context="Need to specify UI components, contrast ratios, and persistence"
)
# Result:
{
  "improved_text": "System must provide dark mode theme for all UI components (dashboard, settings, reports) with WCAG AAA contrast ratio (7:1), persisted in user preferences database",
  "scores": {
    "clarity": 0.92,
    "testability": 0.88,
    "measurability": 0.85
  },
  "overall": 0.88,
  "passed": True
}
```

**OUTPUT (ValidationAgent returns):**
```json
{
  "success": true,
  "validated_items": [
    {
      "req_id": "REQ-001",
      "original": "System must authenticate users using OAuth 2.0",
      "improved": null,
      "scores": {"clarity": 0.85, "testability": 0.80, "measurability": 0.75},
      "overall": 0.80,
      "status": "passed"
    },
    {
      "req_id": "REQ-002",
      "original": "API response time must be under 200ms for 95% of requests",
      "improved": null,
      "scores": {"clarity": 0.95, "testability": 0.98, "measurability": 0.96},
      "overall": 0.96,
      "status": "passed"
    },
    {
      "req_id": "REQ-003",
      "original": "System should support dark mode",
      "improved": "System must provide dark mode theme for all UI components (dashboard, settings, reports) with WCAG AAA contrast ratio (7:1), persisted in user preferences database",
      "scores": {"clarity": 0.92, "testability": 0.88, "measurability": 0.85},
      "overall": 0.88,
      "status": "improved"
    }
    // ... 22 more
  ],
  "stats": {
    "total": 25,
    "passed": 17,
    "improved": 7,
    "failed": 1,
    "avg_score_before": 0.68,
    "avg_score_after": 0.82
  }
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"VALIDATION_COMPLETE - Evaluated 25 requirements: 17 passed initially, 7 improved (avg score 0.68 → 0.82), 1 failed (below threshold even after rewrite)"
```

---

### STEP 5: Orchestrator → RAGAgent → Orchestrator

**INPUT (RAGAgent receives):**
```json
{
  "requirements": [
    {"req_id": "REQ-001", "text": "System must authenticate users using OAuth 2.0"},
    {"req_id": "REQ-005", "text": "User authentication shall use OAuth 2.0 protocol"},
    // ... 23 more
  ],
  "similarity_threshold": 0.90
}
```

**PROCESS (RAGAgent tool calls):**
```python
# Tool call 1: find_duplicates()
duplicates = find_duplicates(
    requirements=[...],
    similarity_threshold=0.90
)
```

**Backend Processing:**
1. Generate embeddings for all 25 requirements
2. Compare each requirement to all others using cosine similarity
3. Group requirements with similarity >= 0.90

**OUTPUT (RAGAgent returns):**
```json
{
  "success": true,
  "duplicate_groups": [
    {
      "group_id": "dup_1",
      "requirements": [
        {"req_id": "REQ-001", "text": "System must authenticate users using OAuth 2.0", "similarity": 1.0},
        {"req_id": "REQ-005", "text": "User authentication shall use OAuth 2.0 protocol", "similarity": 0.94}
      ],
      "avg_similarity": 0.94
    },
    {
      "group_id": "dup_2",
      "requirements": [
        {"req_id": "REQ-008", "text": "Dashboard must load within 2 seconds", "similarity": 1.0},
        {"req_id": "REQ-012", "text": "Dashboard page should render in under 2s", "similarity": 0.92}
      ],
      "avg_similarity": 0.92
    }
  ],
  "stats": {
    "total_requirements": 25,
    "unique_requirements": 23,
    "duplicate_groups": 2,
    "total_duplicates": 2
  }
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"RAG_COMPLETE - Found 2 duplicate groups out of 25 requirements. Duplicates: REQ-001≈REQ-005 (94% similar), REQ-008≈REQ-012 (92% similar). 23 unique requirements remain."
```

---

### STEP 6: Orchestrator → QAValidator → Orchestrator

**INPUT (QAValidator receives):**
```json
{
  "validated_requirements": [...],  // from ValidationAgent
  "duplicate_groups": [...]          // from RAGAgent
}
```

**PROCESS (QAValidator reviews):**
- Check all requirements passed validation: 24/25 ✓
- Check for duplicates: 2 groups found ✗
- Check avg quality score: 0.82 ✓
- Decision: NEEDS_USER_INPUT (duplicates need resolution)

**OUTPUT (QAValidator returns):**
```json
{
  "status": "NEEDS_USER_INPUT",
  "issues": [
    {
      "type": "duplicate",
      "severity": "medium",
      "description": "REQ-001 and REQ-005 are 94% similar - likely duplicates",
      "affected_reqs": ["REQ-001", "REQ-005"]
    },
    {
      "type": "duplicate",
      "severity": "medium",
      "description": "REQ-008 and REQ-012 are 92% similar - likely duplicates",
      "affected_reqs": ["REQ-008", "REQ-012"]
    }
  ],
  "summary": {
    "quality_passed": 24,
    "quality_failed": 1,
    "duplicates_found": 2,
    "recommendation": "User should decide whether to merge duplicates"
  }
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"QA_REVIEW_COMPLETE - Quality check: 24/25 requirements passed. Found 2 duplicate groups that need user decision. NEEDS_USER_INPUT"
```

---

### STEP 7: Orchestrator → UserClarificationAgent → User → UserClarificationAgent → Orchestrator

**INPUT (UserClarificationAgent receives):**
```json
{
  "issues": [
    {
      "type": "duplicate",
      "description": "REQ-001 and REQ-005 are 94% similar",
      "affected_reqs": ["REQ-001", "REQ-005"]
    }
  ]
}
```

**PROCESS (UserClarificationAgent tool calls):**
```python
# Tool call: ask_user()
answer = ask_user(
    question="REQ-001 ('System must authenticate users using OAuth 2.0') and REQ-005 ('User authentication shall use OAuth 2.0 protocol') are 94% similar. Should we merge them or keep both?",
    suggested_answers=["Merge into REQ-001", "Merge into REQ-005", "Keep both separate"]
)
```

**SSE Broadcast (to Frontend):**
```json
{
  "type": "question",
  "question_id": "q_1234",
  "question": "REQ-001 ('System must authenticate users using OAuth 2.0') and REQ-005 ('User authentication shall use OAuth 2.0 protocol') are 94% similar. Should we merge them or keep both?",
  "suggested_answers": ["Merge into REQ-001", "Merge into REQ-005", "Keep both separate"],
  "context": {
    "req_001": "System must authenticate users using OAuth 2.0",
    "req_005": "User authentication shall use OAuth 2.0 protocol",
    "similarity": 0.94
  }
}
```

**User Response (via REST API):**
```json
{
  "correlation_id": "session_xyz",
  "answer": "Merge into REQ-001"
}
```

**OUTPUT (UserClarificationAgent returns):**
```json
{
  "success": true,
  "resolutions": [
    {
      "issue_type": "duplicate",
      "affected_reqs": ["REQ-001", "REQ-005"],
      "user_decision": "Merge into REQ-001",
      "action_taken": "Deleted REQ-005, kept REQ-001"
    },
    {
      "issue_type": "duplicate",
      "affected_reqs": ["REQ-008", "REQ-012"],
      "user_decision": "Merge into REQ-008",
      "action_taken": "Deleted REQ-012, kept REQ-008"
    }
  ],
  "final_requirement_count": 23
}
```

**AGENT MESSAGE (to Orchestrator):**
```
"CLARIFICATION_COMPLETE - User resolved 2 duplicate groups: merged REQ-005 → REQ-001, merged REQ-012 → REQ-008. Final count: 23 unique requirements."
```

---

### STEP 8: Orchestrator → Final Output

**PROCESS (Orchestrator aggregates):**
- Mining: 25 requirements extracted
- Validation: 24 passed/improved, 1 failed
- Duplicates: 2 merged
- Final: 23 unique, high-quality requirements

**OUTPUT (to User):**
```json
{
  "workflow": "complete",
  "success": true,
  "steps_executed": [
    {
      "step": "mining",
      "status": "completed",
      "files_processed": 2,
      "chunks_created": 8,
      "requirements_extracted": 25
    },
    {
      "step": "knowledge_graph",
      "status": "completed",
      "nodes_created": 25,
      "edges_created": 18,
      "persist_location": "qdrant://arch_team_kg"
    },
    {
      "step": "validation",
      "status": "completed",
      "requirements_passed": 17,
      "requirements_improved": 7,
      "requirements_failed": 1,
      "avg_score": 0.82
    },
    {
      "step": "rag_analysis",
      "status": "completed",
      "duplicate_groups": 2,
      "unique_requirements": 23
    },
    {
      "step": "qa_review",
      "status": "completed",
      "issues_found": 2
    },
    {
      "step": "user_clarification",
      "status": "completed",
      "duplicates_resolved": 2
    }
  ],
  "final_results": {
    "requirements_count": 23,
    "avg_quality_score": 0.84,
    "knowledge_graph": {
      "nodes": 25,
      "edges": 18
    },
    "requirements": [
      {
        "req_id": "REQ-001",
        "text": "System must authenticate users using OAuth 2.0",
        "quality_score": 0.80,
        "source": "requirements.docx",
        "kg_nodes": ["node_1", "node_2"]
      }
      // ... 22 more
    ]
  }
}
```

**ORCHESTRATOR MESSAGE:**
```
"WORKFLOW_COMPLETE - Successfully processed 2 documents, extracted and validated 25 requirements, merged 2 duplicates, resulting in 23 high-quality requirements (avg score: 0.84) with knowledge graph (25 nodes, 18 edges) persisted to Qdrant."
```

---

## Summary: Data Transformation Chain

```
User Input (2 files)
  ↓
ChunkMiner: 2 files → 8 chunks → 25 requirements
  ↓
KGAgent: 25 requirements → 25 nodes + 18 edges
  ↓
ValidationAgent: 25 requirements → 17 passed + 7 improved + 1 failed
  ↓
RAGAgent: 25 requirements → 2 duplicate groups found
  ↓
QAValidator: 24 valid + 2 duplicates → NEEDS_USER_INPUT
  ↓
UserClarification: 2 duplicate groups → user resolves → 2 merged
  ↓
Final Output: 23 unique, validated requirements + KG
```

## Implementation Plan

### Phase 1: Tools Creation
```
arch_team/tools/
  ├── mining_tools.py       (upload, chunk, extract)
  ├── kg_tools.py           (build_kg, query_kg, export)
  ├── validation_tools.py   (evaluate, rewrite, suggest) [EXISTS]
  └── rag_tools.py          (semantic_search, find_duplicates, get_related)
```

### Phase 2: Agent Prompts
```
arch_team/agents/prompts/
  ├── orchestrator_prompt.py
  ├── chunk_miner_prompt.py
  ├── kg_agent_prompt.py
  ├── validation_agent_prompt.py
  ├── rag_agent_prompt.py
  ├── qa_validator_prompt.py
  └── user_clarification_prompt.py [EXISTS]
```

### Phase 3: Master Agent
```python
# arch_team/agents/master_agent.py

from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination

async def create_master_agent(correlation_id: Optional[str] = None):
    """Create master Society of Mind agent with all arch_team agents."""

    # 1. Create tool-based agents
    chunk_miner = AssistantAgent(
        "ChunkMiner",
        model_client=model_client,
        tools=mining_tools,
        system_message=chunk_miner_prompt
    )

    kg_agent = AssistantAgent(
        "KG",
        model_client=model_client,
        tools=kg_tools,
        system_message=kg_prompt
    )

    validator = AssistantAgent(
        "Validator",
        model_client=model_client,
        tools=validation_tools,
        system_message=validator_prompt
    )

    rag_agent = AssistantAgent(
        "RAG",
        model_client=model_client,
        tools=rag_tools,
        system_message=rag_prompt
    )

    # 2. Create review agents
    qa_validator = AssistantAgent(
        "QA",
        model_client=model_client,
        system_message=qa_prompt
    )

    clarification = AssistantAgent(
        "UserClarification",
        model_client=model_client,
        tools=[ask_user_tool],
        system_message=clarification_prompt
    )

    # 3. Create orchestrator
    orchestrator = AssistantAgent(
        "Orchestrator",
        model_client=model_client,
        system_message=orchestrator_prompt
    )

    # 4. Create inner team
    termination = TextMentionTermination("WORKFLOW_COMPLETE")
    inner_team = RoundRobinGroupChat(
        [orchestrator, chunk_miner, kg_agent, validator, rag_agent, qa_validator, clarification],
        termination_condition=termination,
        max_turns=100
    )

    # 5. Wrap in Society of Mind
    master_agent = SocietyOfMindAgent(
        "arch_team_master",
        team=inner_team,
        model_client=model_client
    )

    return master_agent
```

### Phase 4: Service Integration
```python
# arch_team/service.py

@app.route("/api/arch_team/process", methods=["POST"])
def arch_team_process():
    """Master endpoint for complete arch_team workflow."""

    files = request.files.getlist('files')
    correlation_id = request.form.get('correlation_id')

    # Create master agent
    master_agent = await create_master_agent(correlation_id)

    # Run workflow
    result = await master_agent.run(
        task=f"Process {len(files)} documents: extract, validate, and build knowledge graph"
    )

    return jsonify(result)
```

## API Endpoints

### Master Workflow
- `POST /api/arch_team/process` - Complete workflow (mining → KG → validation → RAG → QA → clarification)

### Individual Agents (fallback)
- `POST /api/mining/upload` - ChunkMiner only
- `POST /api/kg/build` - KG Agent only
- `POST /api/validation/run` - Validation Agent only
- `GET /api/clarification/stream` - SSE for clarification

## Benefits

1. **Unified Workflow:** All agents in one orchestrated space
2. **Context Sharing:** RAG provides context for QA validation
3. **Incremental Processing:** Each agent builds on previous results
4. **Human-in-the-Loop:** Clarification as final quality gate
5. **Scalable:** Easy to add new agents (e.g., PrioritizationAgent, DependencyAgent)
6. **Debuggable:** Clear agent handoffs and responsibilities

## Next Steps

1. Create missing tools (mining_tools.py, kg_tools.py, rag_tools.py)
2. Create agent prompts for all 7 agents
3. Implement master_agent.py with Society of Mind
4. Update service.py with /api/arch_team/process endpoint
5. Test complete workflow E2E
6. Update frontend to use master endpoint
