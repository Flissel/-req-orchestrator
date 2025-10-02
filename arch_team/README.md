# arch_team - Multi-Agent Requirements Engineering System

Ein modulares Multi-Agent-Framework für automatisiertes Requirements Mining, Analyse und Knowledge Graph Generierung.

## 📚 Inhaltsverzeichnis

1. [Überblick](#überblick)
2. [Architektur-Varianten](#architektur-varianten)
3. [Agent-Typen](#agent-typen)
4. [Workflows](#workflows)
5. [API-Endpunkte](#api-endpunkte)
6. [Konfiguration](#konfiguration)
7. [Beispiele](#beispiele)

---

## Überblick

Das arch_team System bietet **3 Hauptmodi** für Requirements Engineering:

| Modus | Beschreibung | Use Case |
|-------|--------------|----------|
| **AutoGen RAC** | Konversationsbasierte Multi-Agent-Analyse | Komplexe Requirements-Analyse mit Reflexion |
| **EventBus** | Event-driven Agent-Orchestrierung | Flexible Workflows mit Custom Logic |
| **Web Service** | REST API für Dokument-Mining | Batch-Processing von Dokumenten |

---

## Architektur-Varianten

### 1️⃣ AutoGen RAC Team (Recommended)

**Datei:** `autogen_rac.py`

```
┌─────────────┐
│   Task      │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  Planner    │────▶│  Solver      │
│  Agent      │     │  Agent       │
└─────────────┘     └──────┬───────┘
                           │ (RAG Tool)
                           ▼
                    ┌──────────────┐
                    │  Verifier    │
                    │  Agent       │
                    └──────┬───────┘
                           │
                           ▼
                    COVERAGE_OK? ─┐
                           │       │
                           NO      YES
                           │       │
                           └───────▶ Output
```

**Features:**
- Round-robin Gruppenchat
- RAG-Tool für Kontext-Retrieval
- Termination: "COVERAGE_OK" oder Max 10 Messages
- Streaming Console Output

**Start:**
```bash
export ARCH_TASK="Extract functional requirements for authentication"
python -m arch_team.autogen_rac
```

---

### 2️⃣ Custom EventBus System (Legacy)

**Datei:** `main.py`

```
┌─────────────────┐
│  Task Input     │
└────────┬────────┘
         │
         ▼
    ╔════════════╗
    ║  EventBus  ║
    ╚════════════╝
         │
    ┌────┼────┬────────┐
    │    │    │        │
    ▼    ▼    ▼        ▼
 ┌─────┐┌─────┐┌──────┐┌──────┐
 │Plan ││Solve││Verify││ DTO  │
 │Topic││Topic││Topic ││Topic │
 └──┬──┘└──┬──┘└──┬───┘└──┬───┘
    │      │      │       │
    ▼      ▼      ▼       ▼
  Planner Solver Verifier Frontend
  Agent   Agent  Agent    Handler
```

**Topics:**
- `TOPIC_PLAN` - Planning Phase
- `TOPIC_SOLVE` - Requirement Extraction
- `TOPIC_VERIFY` - Quality Check
- `TOPIC_DTO` - Frontend Output
- `TOPIC_TRACE` - Logging

**Start:**
```bash
python -m arch_team.main --mode chunk_miner --path "data/*.md"
```

---

### 3️⃣ Web Service (Production)

**Datei:** `service.py`

```
┌──────────────┐
│ React Client │
└──────┬───────┘
       │ HTTP
       ▼
┌──────────────────┐
│  Flask Service   │
│  (Port 8000)     │
└────────┬─────────┘
         │
    ┌────┼─────┬──────────┐
    │         │          │
    ▼         ▼          ▼
┌────────┐┌────────┐┌────────┐
│ Chunk  ││   KG   ││  RAG   │
│ Miner  ││ Agent  ││ Search │
└────────┘└────────┘└────────┘
```

**Key Endpoints:**
- `POST /api/mining/upload` - Document Mining
- `POST /api/kg/build` - Knowledge Graph
- `GET /api/kg/search/nodes` - Graph Query

**Start:**
```bash
python -m arch_team.service
# Frontend: http://localhost:8000
```

---

## Agent-Typen

### PlannerAgent

**Zweck:** Erstellt Ausführungsplan für Requirements-Analyse

**Input:**
```python
{"task": "Analyze security requirements"}
```

**Output:**
```
THOUGHTS: [Internal reasoning]
PLAN:
- Analyze authentication mechanisms
- Identify data protection requirements
- Check authorization patterns
- Verify compliance requirements
```

**Datei:** `agents/planner.py`

---

### SolverAgent

**Zweck:** Extrahiert und normalisiert Requirements

**Features:**
- RAG-Retrieval für Kontext
- Workbench-Tools (qdrant_search, python_exec)
- Chain-of-Thought Reasoning

**Input:**
```python
{
  "task": "Extract auth requirements",
  "plan": "Analyze authentication...",
  "critique": "[Optional feedback from Verifier]"
}
```

**Output:**
```
THOUGHTS: [Analysis process]
EVIDENCE: [Gathered context]
FINAL_ANSWER:
  REQ-001: System shall enforce password complexity
  REQ-002: System shall support multi-factor authentication
```

**Datei:** `agents/solver.py`

---

### VerifierAgent

**Zweck:** Validiert Requirements-Vollständigkeit

**Checks:**
- Anzahl Requirements (5-20 empfohlen)
- REQ-ID Format (REQ-###)
- Tag-Verteilung (functional, security, performance, ux, ops)

**Output:**
```
COVERAGE_OK  // oder
CRITIQUE: Missing performance requirements, only 3 REQs found
```

**Datei:** `agents/verifier.py`

---

### ChunkMinerAgent

**Zweck:** Mining von Requirements aus Dokumenten

**Flow:**
```
Document (PDF/DOCX/MD)
    ↓
extract_texts()          # Text-Extraktion
    ↓
chunk_payloads()         # Chunking mit Overlap
    ↓  [Chunk 1] [Chunk 2] [Chunk 3] ...
    ↓
mine_chunk() per Chunk   # LLM-Call pro Chunk
    ↓
aggregate DTOs           # Sammeln & Normalisieren
    ↓
Return: List[DTO]
```

**DTO Format:**
```json
{
  "req_id": "REQ-5a8f23-001",
  "title": "System shall provide user authentication",
  "tag": "security",
  "evidence_refs": [
    {
      "sourceFile": "requirements.docx",
      "sha1": "5a8f23abc",
      "chunkIndex": 1
    }
  ]
}
```

**Chunking-Parameter:**
- `max_tokens`: 800 (Standard) - Chunk-Größe
- `overlap_tokens`: 200 (Standard) - Überlappung
- `neighbor_refs`: true - Inkludiert ±1 Chunks als Evidence

**Datei:** `agents/chunk_miner.py`

---

### KGAbstractionAgent

**Zweck:** Baut Knowledge Graph aus Requirements

**Node-Typen:**
- **Requirement**: Eigentliches Requirement
- **Tag**: Kategorie (functional, security, etc.)
- **Actor**: Akteur (User, System, etc.)
- **Entity**: Entität (Password, Profile, etc.)
- **Action**: Verb (authenticate, validate, etc.)

**Edge-Typen:**
- **HAS_TAG**: Requirement → Tag
- **HAS_ACTOR**: Requirement → Actor
- **HAS_ACTION**: Requirement → Action
- **ON_ENTITY**: Action → Entity

**Beispiel:**
```
Requirement: "User can reset password"

Nodes:
  REQ-001 (Requirement)
  User (Actor)
  reset (Action)
  Password (Entity)
  functional (Tag)

Edges:
  REQ-001 --HAS_ACTOR--> User
  REQ-001 --HAS_ACTION--> reset
  reset --ON_ENTITY--> Password
  REQ-001 --HAS_TAG--> functional
```

**Extraction-Modi:**
1. **Heuristic**: Regex-basierte Keyword-Extraktion (schnell)
2. **LLM**: Optional für komplexe Fälle (präzise)
3. **Hybrid**: Heuristik + LLM Fallback (empfohlen)

**Datei:** `agents/kg_agent.py`

---

## Workflows

### Workflow 1: Document Mining (Web Service)

```
┌─────────────────────────────────────────────────────┐
│ 1. User uploads document.docx via React Frontend   │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 2. POST /api/mining/upload                          │
│    FormData: {files, model, neighbor_refs,          │
│               chunk_size, chunk_overlap}            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 3. ChunkMinerAgent.mine_files_or_texts_collect()   │
│    ├─ extract_texts() → "Full document text..."    │
│    ├─ chunk_payloads(max=800, overlap=200)         │
│    │   → [Chunk1, Chunk2, Chunk3, ...]             │
│    ├─ For each chunk:                               │
│    │   └─ LLM Call → JSON extraction                │
│    └─ Aggregate → List[DTO]                         │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 4. Return {success: true, count: 42, items: [...]} │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 5. Frontend displays Requirements List              │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 6. POST /api/kg/build                               │
│    JSON: {items: [...], options: {...}}            │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 7. KGAbstractionAgent.run()                         │
│    ├─ For each DTO:                                 │
│    │   ├─ Heuristic extraction → Nodes/Edges       │
│    │   └─ Optional LLM expansion                    │
│    ├─ Deduplication                                 │
│    └─ Persist to Qdrant (kg_nodes_v1, kg_edges_v1) │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 8. Return {nodes: [...], edges: [...], stats}      │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 9. Frontend renders Interactive Knowledge Graph     │
│    (Cytoscape.js visualization)                     │
└─────────────────────────────────────────────────────┘
```

---

### Workflow 2: RAC Analysis (AutoGen)

```
┌─────────────────────────────────────────────────────┐
│ 1. User starts: python -m arch_team.autogen_rac    │
│    ARCH_TASK="Analyze payment system requirements" │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 2. RoundRobinGroupChat initializes                  │
│    Agents: [Planner, Solver, Verifier]             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 3. Planner turn:                                    │
│    Output: PLAN with 3-5 analysis steps             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 4. Solver turn:                                     │
│    ├─ Reads PLAN from Planner                       │
│    ├─ Optional: Calls RAG tool (search_requirements)│
│    │   → Retrieves context from Qdrant              │
│    ├─ LLM reasoning                                 │
│    └─ Output: FINAL_ANSWER with REQ-001, REQ-002... │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│ 5. Verifier turn:                                   │
│    ├─ Checks requirement count                      │
│    ├─ Validates REQ-ID format                       │
│    ├─ Checks tag distribution                       │
│    └─ Output: "COVERAGE_OK" or CRITIQUE             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
                ┌─────┴─────┐
                │           │
         COVERAGE_OK    CRITIQUE
                │           │
                │           ▼
                │    ┌─────────────────┐
                │    │ Back to Solver  │
                │    │ with feedback   │
                │    └─────────────────┘
                │           │
                │           ▼
                │    [Loop max 10x]
                │
                ▼
┌─────────────────────────────────────────────────────┐
│ 6. Termination: Output final requirements           │
└─────────────────────────────────────────────────────┘
```

---

## API-Endpunkte

### POST /api/mining/upload

**Dokument-Mining**

**Request:**
```bash
curl -X POST http://localhost:8000/api/mining/upload \
  -F "files=@document.docx" \
  -F "model=gpt-4o-mini" \
  -F "neighbor_refs=1" \
  -F "chunk_size=1200" \
  -F "chunk_overlap=300"
```

**Response:**
```json
{
  "success": true,
  "count": 15,
  "items": [
    {
      "req_id": "REQ-a3b2c1-001",
      "title": "System shall authenticate users via OAuth2",
      "tag": "security",
      "evidence_refs": [
        {"sourceFile": "document.docx", "sha1": "a3b2c1", "chunkIndex": 2}
      ]
    }
  ]
}
```

**Parameter:**
- `files`: Multipart files (PDF, DOCX, MD, TXT)
- `model`: Optional (default: gpt-4o-mini)
- `neighbor_refs`: "1"|"true" für ±1 Chunk Context
- `chunk_size`: Tokens pro Chunk (default: 800)
- `chunk_overlap`: Overlap-Tokens (default: 200)

---

### POST /api/kg/build

**Knowledge Graph Generierung**

**Request:**
```bash
curl -X POST http://localhost:8000/api/kg/build \
  -H "Content-Type: application/json" \
  -d '{
    "items": [...],
    "options": {
      "persist": "qdrant",
      "use_llm": false,
      "llm_fallback": true,
      "persist_async": true
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "nodes": [...],
  "edges": [...],
  "stats": {
    "nodes": 87,
    "edges": 143,
    "deduped": 12,
    "persisted_nodes": 87,
    "persisted_edges": 143
  }
}
```

**Options:**
- `persist`: "qdrant" | "none"
- `use_llm`: true für LLM-basierte Extraktion
- `llm_fallback`: true → LLM wenn Heuristik wenig findet
- `persist_async`: true für Background-Persistence

---

### GET /api/kg/search/nodes

**Semantic Node Search**

```bash
curl "http://localhost:8000/api/kg/search/nodes?query=authentication&top_k=5"
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "id": "REQ-001",
      "type": "Requirement",
      "name": "User authentication",
      "score": 0.89
    }
  ]
}
```

---

### GET /api/kg/neighbors

**Graph Traversal (1-hop)**

```bash
curl "http://localhost:8000/api/kg/neighbors?node_id=REQ-001&dir=both&rel=HAS_ACTION&limit=50"
```

**Parameter:**
- `node_id`: Start-Node
- `dir`: "in" | "out" | "both"
- `rel`: Filter by relation type (comma-separated)
- `limit`: Max results (default: 200)

---

## Konfiguration

### Environment Variables (.env)

```bash
# OpenAI
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
ARCH_TEMPERATURE=0.2

# AutoGen RAC
ARCH_TASK="Analyze requirements..."
RAC_RAG_ENABLED=1
RAC_MAX_MESSAGES=10

# EventBus Mode
ARCH_REFLECTION_ROUNDS=1
ARCH_MODEL_CONTEXT_MAX=12

# ChunkMiner
CHUNK_MINER_NEIGHBORS=1

# Qdrant
QDRANT_URL=http://localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=requirements_v2
# Collections auto-created: kg_nodes_v1, kg_edges_v1, arch_trace

# Service
APP_PORT=8000
```

---

## Beispiele

### Beispiel 1: CLI Mining

```bash
# Mit Neighbor Evidence
python -m arch_team.main \
  --mode chunk_miner \
  --path "specs/*.md" \
  --neighbor-evidence \
  --model gpt-4o-mini
```

### Beispiel 2: Python API

```python
from arch_team.agents.chunk_miner import ChunkMinerAgent

agent = ChunkMinerAgent(source="api", default_model="gpt-4o-mini")

# Mining from files
with open("requirements.md", "rb") as f:
    items = agent.mine_files_or_texts_collect(
        files_or_texts=[f.read()],
        neighbor_refs=True,
        chunk_options={"max_tokens": 1200, "overlap_tokens": 300}
    )

print(f"Extracted {len(items)} requirements")
```

### Beispiel 3: Knowledge Graph

```python
from arch_team.agents.kg_agent import KGAbstractionAgent

kg_agent = KGAbstractionAgent()

result = kg_agent.run(
    items=requirements_dtos,
    persist="qdrant",
    use_llm=False,
    llm_fallback=True
)

print(f"Created {result['stats']['nodes']} nodes, {result['stats']['edges']} edges")
```

---

## Performance-Tipps

### Chunking-Optimierung

| Dokument-Typ | chunk_size | overlap | neighbor_refs |
|--------------|------------|---------|---------------|
| Kurze Specs (< 10 Seiten) | 600 | 150 | false |
| Mittlere Docs (10-50 Seiten) | 800 | 200 | true |
| Lange Standards (> 50 Seiten) | 1200 | 300 | true |
| Sehr dichte Texte | 1600 | 400 | true |

### Model-Wahl

| Modell | Geschwindigkeit | Qualität | Kosten | Use Case |
|--------|-----------------|----------|--------|----------|
| gpt-4o-mini | ⚡⚡⚡ | ✓✓ | $ | Standard-Mining |
| gpt-4o | ⚡⚡ | ✓✓✓ | $$$ | Komplexe Dokumente |
| gpt-4 | ⚡ | ✓✓✓ | $$$$ | Höchste Qualität |

### Batch-Processing

Für große Mengen:
```bash
# Parallel processing mit xargs
find specs/ -name "*.md" | xargs -P 4 -I {} \
  python -m arch_team.main --mode chunk_miner --path {}
```

---

## Troubleshooting

### Problem: Zu wenige Requirements extrahiert

**Lösung:**
1. ✅ Erhöhe `chunk_size` (z.B. 1200)
2. ✅ Aktiviere `neighbor_refs=true`
3. ✅ Erhöhe `chunk_overlap` (z.B. 300)
4. ✅ Prüfe Dokument-Format (DOCX-Extraktion OK?)

### Problem: Knowledge Graph leer

**Lösung:**
1. ✅ Aktiviere `llm_fallback=true`
2. ✅ Prüfe DTO-Format (req_id, title, tag vorhanden?)
3. ✅ Logs prüfen: `arch_team/runtime/logging.py`

### Problem: Langsame Performance

**Lösung:**
1. ✅ Reduziere `chunk_size` (weniger Chunks)
2. ✅ Deaktiviere `neighbor_refs` (schneller)
3. ✅ Nutze `gpt-4o-mini` statt `gpt-4o`
4. ✅ Aktiviere `persist_async=true` für KG

---

## Weiterführende Dokumentation

- **Agent-Details:** Siehe `agents/` README
- **Runtime:** Siehe `runtime/` README
- **Tools:** Siehe `autogen_tools/` README
- **Memory:** Siehe `memory/` README

---

## Support

Bei Fragen siehe:
- GitHub Issues: [Link]
- CLAUDE.md (Root-Verzeichnis)
- Inline-Docstrings in Agent-Klassen
