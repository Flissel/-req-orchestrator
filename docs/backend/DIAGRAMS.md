# Backend Diagramme

Diese Datei bündelt Komponenten-, Dataflow- und ER-Diagramm für das Backend.

## Komponenten-Diagramm

```mermaid
graph LR
  U[User] --> FE[Frontend]
  FE --> GW[HTTP]
  GW --> API_BP[API Blueprint]
  GW --> BATCH_BP[Batch Blueprint]

  API_BP --> SVC[Evaluation Service]
  BATCH_BP --> BATCH[Batch Orchestrator]

  SVC --> LLM[OpenAI Adapter]
  BATCH --> LLM

  SVC --> DB[SQLite]
  BATCH --> DB

  CFG[Settings Env] --> API_BP
  CFG --> BATCH_BP
  UTILS[Utils] --> API_BP
  UTILS --> BATCH_BP

  subgraph Backend
    API_BP
    BATCH_BP
    SVC
    BATCH
    LLM
    DB
    UTILS
    CFG
  end
```

## Dataflow-Diagramm

```mermaid
sequenceDiagram
  autonumber
  actor Client
  participant BE as Backend
  participant FS as Markdown Docs
  participant LLM as OpenAI API
  participant DB as SQLite

  rect rgb(230,230,230)
    note over Client,BE: Evaluate Route
    Client ->> BE: POST /api/v1/batch/evaluate
    BE ->> FS: Read requirements.md
    loop per requirement
      BE ->> LLM: Evaluate criteria
      LLM -->> BE: Scores and feedback
      BE ->> DB: Store evaluation and details
    end
    BE -->> Client: JSON items and mergedMarkdown
  end

  rect rgb(230,230,230)
    note over Client,BE: Suggest Route
    Client ->> BE: POST /api/v1/batch/suggest
    BE ->> FS: Read requirements.md
    par parallel LLM calls
      BE ->> LLM: Suggestions for requirement
      LLM -->> BE: Suggestions list
    end
    BE ->> DB: Insert suggestions sequential
    BE -->> Client: JSON items and mergedMarkdown
  end

  rect rgb(230,230,230)
    note over Client,BE: Rewrite Route
    Client ->> BE: POST /api/v1/batch/rewrite
    BE ->> FS: Read requirements.md
    par parallel LLM calls
      BE ->> LLM: Rewrite requirement
      LLM -->> BE: Redefined requirement
    end
    BE ->> DB: Insert rewritten requirement sequential
    BE -->> Client: JSON items and mergedMarkdown
  end
```

## ER-Diagramm

```mermaid
erDiagram
  EVALUATION ||--o{ EVALUATION_DETAIL : has
  EVALUATION ||--o{ SUGGESTION : has
  EVALUATION ||--o{ REWRITTEN_REQUIREMENT : has
  CRITERION ||--o{ EVALUATION_DETAIL : defines

  EVALUATION {
    TEXT id
    TEXT requirement_checksum
    TEXT model
    INTEGER latency_ms
    REAL score
    TEXT verdict
    DATETIME created_at
  }

  EVALUATION_DETAIL {
    INTEGER id
    TEXT evaluation_id
    TEXT criterion_key
    REAL score
    BOOLEAN passed
    TEXT feedback
  }

  SUGGESTION {
    INTEGER id
    TEXT evaluation_id
    TEXT text
    TEXT priority
  }

  REWRITTEN_REQUIREMENT {
    INTEGER id
    TEXT evaluation_id
    TEXT text
  }

  CRITERION {
    TEXT key
    TEXT name
    TEXT description
    REAL weight
    BOOLEAN active
  }
```

Referenz: Details und DDL siehe [docs/backend/README.md](docs/backend/README.md).