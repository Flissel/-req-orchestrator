# arch_team - Detaillierte Flow-Diagramme

Visualisierung aller wichtigen Workflows im arch_team System.

---

## 📄 Dokument-Mining Flow (ChunkMiner)

### Schritt-für-Schritt Ablauf

```
┌───────────────────────────────────────────────────────────────┐
│ PHASE 1: UPLOAD & PARSING                                     │
└───────────────────────────────────────────────────────────────┘

User uploads: requirements.docx (150 KB)
                    │
                    ▼
┌──────────────────────────────────────┐
│ extract_texts()                      │
│ - DOCX → python-docx library         │
│ - PDF → PyPDF2                       │
│ - MD → direct read                   │
└──────────────┬───────────────────────┘
               │
               ▼
Raw Text (45,000 characters)
"# Project Requirements
1.1 Authentication System
The system shall provide...
..."

┌───────────────────────────────────────────────────────────────┐
│ PHASE 2: CHUNKING                                             │
└───────────────────────────────────────────────────────────────┘

chunk_payloads(
  text=raw_text,
  max_tokens=800,        # User configured
  overlap_tokens=200     # User configured
)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Tokenization (tiktoken)                                     │
│ "The system shall..." → [464, 1887, 4985, ...]             │
│ Total: ~11,250 tokens                                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Sliding Window Chunking                                     │
│                                                             │
│ [0 ────── 800]                    Chunk 1                  │
│           [600 ────── 1400]       Chunk 2 (overlap 200)    │
│                     [1200 ─── 2000] Chunk 3               │
│                               ...                           │
│                                                             │
│ Result: 15 Chunks                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
Chunks Array:
[
  {text: "# Project Requirements...", payload: {sha1: "a3b2c1", chunkIndex: 0}},
  {text: "...Authentication System...", payload: {sha1: "a3b2c1", chunkIndex: 1}},
  ...
]

┌───────────────────────────────────────────────────────────────┐
│ PHASE 3: LLM MINING (per Chunk)                              │
└───────────────────────────────────────────────────────────────┘

For each chunk (parallel possible):

┌──────────────────────────────────────┐
│ Chunk 1 (chunkIndex: 0)             │
│ Text: "# Project Requirements..."   │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ Build LLM Prompt:                                            │
│                                                              │
│ SYSTEM:                                                      │
│ "Du bist Requirements-Mining-Agent.                          │
│  Extrahiere 0..n Requirements als JSON."                     │
│                                                              │
│ USER:                                                        │
│ "Suggested REQ-ID: REQ-a3b2c1-000                           │
│  Text-Chunk:                                                 │
│  ----                                                        │
│  # Project Requirements                                      │
│  1.1 Authentication System                                   │
│  The system shall provide secure...                          │
│  ----                                                        │
│  Gib nur JSON zurück."                                       │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ OpenAI API Call                      │
│ Model: gpt-4o-mini                   │
│ Temperature: 0.2                     │
└──────────────┬───────────────────────┘
               │
               ▼
LLM Response:
```json
{
  "items": [
    {
      "req_id": "REQ-a3b2c1-000-a",
      "title": "System shall provide secure user authentication",
      "tag": "security",
      "evidence_refs": [
        {"sourceFile": "requirements.docx", "sha1": "a3b2c1", "chunkIndex": 0}
      ]
    },
    {
      "req_id": "REQ-a3b2c1-000-b",
      "title": "System shall support OAuth2 and SAML protocols",
      "tag": "functional",
      "evidence_refs": [
        {"sourceFile": "requirements.docx", "sha1": "a3b2c1", "chunkIndex": 0}
      ]
    }
  ]
}
```

┌──────────────────────────────────────┐
│ Parse JSON → validate                │
│ Add to results array                 │
└──────────────┬───────────────────────┘
               │
               ▼
    [Repeat for Chunk 2, 3, ...]

┌───────────────────────────────────────────────────────────────┐
│ PHASE 4: NEIGHBOR EVIDENCE (if enabled)                      │
└───────────────────────────────────────────────────────────────┘

For each extracted requirement:

REQ-a3b2c1-003 (from Chunk 3)
     │
     ├─ Original evidence: Chunk 3
     │
     ├─ Add Chunk 2 (neighbor -1)
     │   {"sourceFile": "...", "sha1": "a3b2c1", "chunkIndex": 2}
     │
     └─ Add Chunk 4 (neighbor +1)
         {"sourceFile": "...", "sha1": "a3b2c1", "chunkIndex": 4}

Result:
{
  "req_id": "REQ-a3b2c1-003",
  "title": "...",
  "evidence_refs": [
    {"chunkIndex": 2},  // Previous
    {"chunkIndex": 3},  // Current
    {"chunkIndex": 4}   // Next
  ]
}

┌───────────────────────────────────────────────────────────────┐
│ PHASE 5: AGGREGATION & RETURN                                │
└───────────────────────────────────────────────────────────────┘

All chunks processed:
  Chunk 1 → 2 REQs
  Chunk 2 → 3 REQs
  Chunk 3 → 2 REQs
  ...
  Chunk 15 → 1 REQ

Total: 42 Requirements

┌──────────────────────────────────────┐
│ Return to Frontend                   │
│ {                                    │
│   "success": true,                   │
│   "count": 42,                       │
│   "items": [...]                     │
│ }                                    │
└──────────────────────────────────────┘
```

---

## 🕸️ Knowledge Graph Build Flow

### Schritt-für-Schritt Ablauf

```
┌───────────────────────────────────────────────────────────────┐
│ INPUT: 42 Requirements DTOs                                   │
└───────────────────────────────────────────────────────────────┘

DTOs = [
  {req_id: "REQ-001", title: "User can reset password", tag: "functional"},
  {req_id: "REQ-002", title: "System validates password strength", tag: "security"},
  ...
]

┌───────────────────────────────────────────────────────────────┐
│ PHASE 1: HEURISTIC EXTRACTION (per DTO)                      │
└───────────────────────────────────────────────────────────────┘

For DTO: "User can reset password"

Step 1: Create Requirement Node
┌──────────────────────────────────────┐
│ Node: REQ-001                        │
│ type: "Requirement"                  │
│ name: "User can reset password"      │
│ payload: {tag: "functional", ...}    │
└──────────────────────────────────────┘

Step 2: Create Tag Node
┌──────────────────────────────────────┐
│ Node: Tag:functional                 │
│ type: "Tag"                          │
│ name: "functional"                   │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Edge: REQ-001 --HAS_TAG--> functional│
└──────────────────────────────────────┘

Step 3: Heuristic Actor Detection
title.lower() = "user can reset password"
                 ^^^^
Match: "user" → Create Actor Node

┌──────────────────────────────────────┐
│ Node: Actor:user                     │
│ type: "Actor"                        │
│ name: "User"                         │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Edge: REQ-001 --HAS_ACTOR--> User    │
└──────────────────────────────────────┘

Step 4: Heuristic Action Detection
Tokens: ["user", "can", "reset", "password"]
                         ^^^^^
Match: ends with "en" → verb (German)
But "reset" is English verb → Accept

┌──────────────────────────────────────┐
│ Node: Action:reset                   │
│ type: "Action"                       │
│ name: "reset"                        │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Edge: REQ-001 --HAS_ACTION--> reset  │
└──────────────────────────────────────┘

Step 5: Heuristic Entity Detection
title.lower() = "user can reset password"
                                ^^^^^^^^
Match: "password" in entity_keywords

┌──────────────────────────────────────┐
│ Node: Entity:password                │
│ type: "Entity"                       │
│ name: "Password"                     │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│ Edge: reset --ON_ENTITY--> Password  │
└──────────────────────────────────────┘

Result for REQ-001:
  Nodes: 5 (Requirement, Tag, Actor, Action, Entity)
  Edges: 4

┌───────────────────────────────────────────────────────────────┐
│ PHASE 2: LLM FALLBACK (optional, if heuristic found < 2 nodes)│
└───────────────────────────────────────────────────────────────┘

If llm_fallback=true AND heuristic found only REQ + Tag:

┌──────────────────────────────────────────────────────────────┐
│ LLM Prompt:                                                  │
│                                                              │
│ SYSTEM: "Extrahiere KG-Ansicht. Nur JSON."                 │
│                                                              │
│ USER:                                                        │
│ "Titel: 'System encrypts data at rest'                      │
│  ReqId: REQ-002                                              │
│  Tag: security                                               │
│                                                              │
│  Gib zurück:                                                 │
│  {                                                           │
│    'nodes': [{'id': '...', 'type': '...', 'name': '...'}],  │
│    'edges': [{'from': '...', 'to': '...', 'rel': '...'}]    │
│  }"                                                          │
└──────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────┐
│ OpenAI Response:                     │
│ {                                    │
│   "nodes": [                         │
│     {"id": "encrypt", "type": "Action"},│
│     {"id": "data", "type": "Entity"} │
│   ],                                 │
│   "edges": [                         │
│     {"from": "REQ-002", "to": "encrypt", "rel": "HAS_ACTION"},│
│     {"from": "encrypt", "to": "data", "rel": "ON_ENTITY"}│
│   ]                                  │
│ }                                    │
└──────────────────────────────────────┘
                      │
                      ▼
        Merge with heuristic results

┌───────────────────────────────────────────────────────────────┐
│ PHASE 3: AGGREGATION (all DTOs)                              │
└───────────────────────────────────────────────────────────────┘

Process all 42 DTOs:
  DTO 1 → 5 nodes, 4 edges
  DTO 2 → 4 nodes, 3 edges
  ...
  DTO 42 → 3 nodes, 2 edges

Raw totals:
  Nodes: ~180 (with duplicates)
  Edges: ~150 (with duplicates)

┌───────────────────────────────────────────────────────────────┐
│ PHASE 4: DEDUPLICATION                                       │
└───────────────────────────────────────────────────────────────┘

Dedupe Nodes by canonical_key:
  "Actor:user" appears 12x → Keep 1
  "Entity:password" appears 8x → Keep 1
  "Tag:security" appears 15x → Keep 1
  ...

Dedupe Edges by (from, rel, to):
  "REQ-001 --HAS_TAG--> security" (unique)
  "REQ-003 --HAS_TAG--> security" (unique)
  "REQ-005 --HAS_ACTOR--> User" (unique)
  ...

Final counts:
  Nodes: 87 (removed 93 duplicates)
  Edges: 143 (removed 7 duplicates)

┌───────────────────────────────────────────────────────────────┐
│ PHASE 5: PERSISTENCE (Qdrant)                                │
└───────────────────────────────────────────────────────────────┘

If persist="qdrant":

┌──────────────────────────────────────┐
│ QdrantKGClient.ensure_collections()  │
│ - Create kg_nodes_v1 (if not exists)│
│ - Create kg_edges_v1 (if not exists)│
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ Embed Nodes (text-embedding-3-small)│
│                                      │
│ "User can reset password"            │
│ → [0.123, -0.456, 0.789, ...]       │
│    (1536 dimensions)                 │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ QdrantClient.upsert(                 │
│   collection="kg_nodes_v1",          │
│   points=[                           │
│     {id: "REQ-001", vector: [...],   │
│      payload: {type: "Requirement"}} │
│   ]                                  │
│ )                                    │
└──────────────┬───────────────────────┘
               │
               ▼
Nodes persisted: 87 ✓

┌──────────────────────────────────────┐
│ Embed Edges                          │
│ "User HAS_ACTION reset"              │
│ → [0.234, -0.567, ...]              │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│ QdrantClient.upsert(                 │
│   collection="kg_edges_v1",          │
│   points=[{id: "edge-001", ...}]     │
│ )                                    │
└──────────────────────────────────────┘

Edges persisted: 143 ✓

┌───────────────────────────────────────────────────────────────┐
│ PHASE 6: RETURN RESULT                                       │
└───────────────────────────────────────────────────────────────┘

{
  "success": true,
  "nodes": [...], // 87 nodes
  "edges": [...], // 143 edges
  "stats": {
    "nodes": 87,
    "edges": 143,
    "deduped": 100,
    "persisted_nodes": 87,
    "persisted_edges": 143
  }
}

Frontend → Cytoscape.js → Interactive Visualization
```

---

## 🔄 AutoGen RAC Conversation Flow

### Multi-Agent Dialog

```
┌───────────────────────────────────────────────────────────────┐
│ INITIALIZATION                                                │
└───────────────────────────────────────────────────────────────┘

User:
  ARCH_TASK="Analyze payment processing requirements"

System creates:
  ┌─────────────┐
  │  Planner    │ (AssistantAgent)
  └─────────────┘
  ┌─────────────┐
  │  Solver     │ (AssistantAgent + RAG Tool)
  └─────────────┘
  ┌─────────────┐
  │  Verifier   │ (AssistantAgent)
  └─────────────┘

RoundRobinGroupChat([Planner, Solver, Verifier])
Termination: TextMentionTermination("COVERAGE_OK") OR MaxMessageTermination(10)

┌───────────────────────────────────────────────────────────────┐
│ TURN 1: PLANNER                                               │
└───────────────────────────────────────────────────────────────┘

Input: "Analyze payment processing requirements"

Planner thinks:
  "I need to create a structured analysis plan..."

Planner outputs:
────────────────────────────────────────────
THOUGHTS:
The task requires comprehensive analysis of payment processing.
Need to cover: security, transactions, compliance, error handling.

PLAN:
1. Identify core payment transaction requirements
2. Analyze security and PCI-DSS compliance needs
3. Define error handling and rollback mechanisms
4. Specify audit and logging requirements
5. Document performance and scalability needs
────────────────────────────────────────────

┌───────────────────────────────────────────────────────────────┐
│ TURN 2: SOLVER                                                │
└───────────────────────────────────────────────────────────────┘

Solver receives: Planner's PLAN

Solver checks: RAG tool available?
  → Yes: Call search_requirements("payment processing")

┌──────────────────────────────────────┐
│ RAG Tool Execution:                  │
│                                      │
│ search_requirements(                 │
│   query="payment processing",        │
│   top_k=5                            │
│ )                                    │
│                                      │
│ → Qdrant search in requirements_v2  │
│ → Returns similar requirements       │
└──────────────┬───────────────────────┘
               │
               ▼
Context:
  - "System shall use HTTPS for all payment API calls"
  - "Payment data must be encrypted at rest"
  - "Transaction timeout: 30 seconds max"
  ...

Solver combines: PLAN + RAG Context + LLM reasoning

Solver outputs:
────────────────────────────────────────────
THOUGHTS:
Based on the plan and retrieved context, I identify
5 core requirement categories. PCI-DSS compliance is critical.

EVIDENCE:
- Found existing requirement about HTTPS enforcement
- Encryption at rest is documented
- Timeout constraints are specified

FINAL_ANSWER:
REQ-001: System shall process payment transactions via secure API gateway
  Tag: functional

REQ-002: System shall encrypt payment data using AES-256
  Tag: security

REQ-003: System shall validate PCI-DSS compliance for card data
  Tag: security

REQ-004: System shall implement transaction rollback on failure
  Tag: functional

REQ-005: System shall log all payment attempts with timestamp
  Tag: ops
────────────────────────────────────────────

┌───────────────────────────────────────────────────────────────┐
│ TURN 3: VERIFIER                                              │
└───────────────────────────────────────────────────────────────┘

Verifier receives: Solver's FINAL_ANSWER

Verifier checks:
  ✓ REQ count: 5 (acceptable, min 5)
  ✓ REQ-ID format: REQ-00X ✓
  ✓ Tags present: yes
  ✗ Tag distribution:
      functional: 2
      security: 2
      ops: 1
      performance: 0  ← Missing!
      ux: 0

Verifier outputs:
────────────────────────────────────────────
CRITIQUE:
Good start with 5 requirements covering security and functional aspects.
However, missing:
- Performance requirements (transaction throughput, latency)
- UX requirements (error messages, user feedback)

Please add 2-3 more requirements covering these areas.
────────────────────────────────────────────

┌───────────────────────────────────────────────────────────────┐
│ TURN 4: SOLVER (Refinement Round)                            │
└───────────────────────────────────────────────────────────────┘

Solver receives: Verifier's CRITIQUE + previous FINAL_ANSWER

Solver refines:

FINAL_ANSWER:
[... keeps REQ-001 to REQ-005 ...]

REQ-006: System shall process 1000 transactions per second
  Tag: performance

REQ-007: System shall respond within 200ms for payment validation
  Tag: performance

REQ-008: System shall display clear error messages for declined payments
  Tag: ux

┌───────────────────────────────────────────────────────────────┐
│ TURN 5: VERIFIER (Final Check)                               │
└───────────────────────────────────────────────────────────────┘

Verifier checks:
  ✓ REQ count: 8
  ✓ REQ-ID format: all valid
  ✓ Tag distribution:
      functional: 2
      security: 2
      ops: 1
      performance: 2 ✓
      ux: 1 ✓

Verifier outputs:
────────────────────────────────────────────
COVERAGE_OK

All requirement categories covered.
Total: 8 requirements with balanced distribution.
────────────────────────────────────────────

┌───────────────────────────────────────────────────────────────┐
│ TERMINATION                                                   │
└───────────────────────────────────────────────────────────────┘

TextMentionTermination detects "COVERAGE_OK"
→ Conversation ends
→ Return final requirements to user
```

---

## 🔍 Detailed Component Interactions

### ChunkMiner → KG Agent Data Flow

```
ChunkMiner Output (DTO):
┌──────────────────────────────────────────────────────────────┐
│ {                                                            │
│   "req_id": "REQ-abc123-005",                               │
│   "title": "System validates email format before saving",   │
│   "tag": "functional",                                       │
│   "evidence_refs": [                                         │
│     {                                                        │
│       "sourceFile": "spec.md",                              │
│       "sha1": "abc123",                                      │
│       "chunkIndex": 5                                        │
│     },                                                       │
│     {                                                        │
│       "sourceFile": "spec.md",  // Neighbor -1              │
│       "sha1": "abc123",                                      │
│       "chunkIndex": 4                                        │
│     },                                                       │
│     {                                                        │
│       "sourceFile": "spec.md",  // Neighbor +1              │
│       "sha1": "abc123",                                      │
│       "chunkIndex": 6                                        │
│     }                                                        │
│   ]                                                          │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
              KG Agent processes:
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ HEURISTIC EXTRACTION:                                        │
│                                                              │
│ title: "System validates email format before saving"        │
│         ^^^^^^ ^^^^^^^^^ ^^^^^ ^^^^^^        ^^^^^^         │
│                                                              │
│ Detected:                                                    │
│ - Actor: "System"                                            │
│ - Action: "validates" (ends with 's', verb form)            │
│ - Entity: "email" (keyword match)                            │
│ - Entity: "format" (keyword match)                           │
│                                                              │
│ Generated Nodes:                                             │
│ 1. Requirement(REQ-abc123-005)                              │
│ 2. Tag(functional)                                           │
│ 3. Actor(System)                                             │
│ 4. Action(validates)                                         │
│ 5. Entity(email)                                             │
│ 6. Entity(format)                                            │
│                                                              │
│ Generated Edges:                                             │
│ 1. REQ-abc123-005 --HAS_TAG--> functional                   │
│ 2. REQ-abc123-005 --HAS_ACTOR--> System                     │
│ 3. REQ-abc123-005 --HAS_ACTION--> validates                 │
│ 4. validates --ON_ENTITY--> email                            │
│ 5. validates --ON_ENTITY--> format                           │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
              Evidence preserved in edge payloads:
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ Edge payload example:                                        │
│ {                                                            │
│   "edge_id": "REQ-abc123-005#HAS_ACTION#validates",         │
│   "from_node_id": "REQ-abc123-005",                         │
│   "to_node_id": "Action:validates",                         │
│   "rel": "HAS_ACTION",                                       │
│   "evidence": [                                              │
│     {"sourceFile": "spec.md", "chunkIndex": 4},             │
│     {"sourceFile": "spec.md", "chunkIndex": 5},             │
│     {"sourceFile": "spec.md", "chunkIndex": 6}              │
│   ],                                                         │
│   "canonical_key": "from=REQ-abc123-005|rel=HAS_ACTION|..."  │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 📊 Performance Characteristics

### Timing Breakdown (typical 20KB document)

```
Model: gpt-4o-mini
Document: 20,000 characters
Settings: chunk_size=800, overlap=200, neighbor_refs=true

┌─────────────────────────────────────────────────────┐
│ PHASE                    │ TIME      │ % OF TOTAL   │
├─────────────────────────────────────────────────────┤
│ Text Extraction          │ 0.2s      │ 2%          │
│ Chunking                 │ 0.1s      │ 1%          │
│ LLM Calls (12 chunks)    │ 8.5s      │ 85%         │
│ JSON Parsing             │ 0.1s      │ 1%          │
│ Neighbor Evidence        │ 0.3s      │ 3%          │
│ DTO Assembly             │ 0.1s      │ 1%          │
│ KG Build (Heuristic)     │ 0.4s      │ 4%          │
│ KG Persistence (Qdrant)  │ 0.3s      │ 3%          │
├─────────────────────────────────────────────────────┤
│ TOTAL                    │ ~10s      │ 100%        │
└─────────────────────────────────────────────────────┘

Bottleneck: LLM API calls (sequential)
Optimization: Parallel chunk processing (future)
```

### Scaling Characteristics

```
Document Size vs Processing Time (gpt-4o-mini):

10 KB  (5 chunks)   →  ~5 seconds
20 KB  (12 chunks)  →  ~10 seconds
50 KB  (30 chunks)  →  ~25 seconds
100 KB (60 chunks)  →  ~50 seconds

Linear scaling: ~0.8s per chunk
```

---

## 🎯 Best Practices

### 1. Optimale Chunk-Konfiguration nach Dokument-Typ

```
┌────────────────────────────────────────────────────────────┐
│ DOKUMENT-TYP       │ chunk_size │ overlap │ neighbor_refs │
├────────────────────────────────────────────────────────────┤
│ Knappe Specs       │    600     │   150   │    false      │
│ Standard-Docs      │    800     │   200   │    true       │
│ Detaillierte Specs │   1200     │   300   │    true       │
│ Standards (ISO/IEC)│   1600     │   400   │    true       │
│ Code-Kommentare    │    400     │   100   │    false      │
└────────────────────────────────────────────────────────────┘
```

### 2. Model-Wahl nach Anforderung

```
┌────────────────────────────────────────────────────────────┐
│ USE CASE              │ MODEL        │ BEGRÜNDUNG         │
├────────────────────────────────────────────────────────────┤
│ Batch-Processing      │ gpt-4o-mini  │ Kosten/Speed       │
│ Kritische Specs       │ gpt-4o       │ Qualität           │
│ Prototyping           │ gpt-4o-mini  │ Schnelle Iteration │
│ Compliance-Docs       │ gpt-4        │ Höchste Genauigkeit│
└────────────────────────────────────────────────────────────┘
```

### 3. Error Handling Best Practices

```python
# Robust Mining
try:
    items = agent.mine_files_or_texts_collect(
        files,
        model="gpt-4o-mini",
        chunk_options={"max_tokens": 800}
    )
except Exception as e:
    # Log error
    logger.error(f"Mining failed: {e}")

    # Fallback: Smaller chunks
    items = agent.mine_files_or_texts_collect(
        files,
        chunk_options={"max_tokens": 400}  # Smaller, safer
    )
```

---

Diese Dokumentation zeigt dir genau, wie jeder Schritt im System abläuft!
