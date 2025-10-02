# Requirements Validation - Society of Mind Design

**Status**: Design Phase
**Pattern**: AutoGen Society of Mind + Tool Calling
**Reference Implementation**: `arch_team/dev_folder_/agent.py` (GitHub MCP Agent)

---

## 🎯 **Zielsetzung**

Automatisierte Requirements-Qualitätssicherung mit:
- ✅ Multi-Kriterien Evaluation (Clarity, Testability, Measurability)
- ✅ Automatische Verbesserungsvorschläge (Atomic Suggestions)
- ✅ LLM-basiertes Rewriting (User Story Format, Acceptance Criteria)
- ✅ Duplikats-Erkennung (Semantic Search via Embeddings)
- ✅ User-Interaktion für fehlende Informationen

---

## 🏗️ **Architektur: Society of Mind Pattern**

### **Übersicht**

```
┌─────────────────────────────────────────────────────────────────┐
│ SocietyOfMindAgent ("requirements_society_of_mind")             │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  RoundRobinGroupChat (Inner Team, max_turns=20)           │  │
│  │                                                             │  │
│  │  ┌───────────────────────────────────────────────┐        │  │
│  │  │ 1️⃣ RequirementsOperator                       │        │  │
│  │  │   Role: Validate & improve requirements       │        │  │
│  │  │   Tools:                                       │        │  │
│  │  │   - evaluate_requirement()                     │        │  │
│  │  │   - rewrite_requirement()                      │        │  │
│  │  │   - suggest_improvements()                     │        │  │
│  │  │   - detect_duplicates()                        │        │  │
│  │  │   Signal: "READY_FOR_VALIDATION"              │        │  │
│  │  └───────────────────────────────────────────────┘        │  │
│  │                        ↕                                    │  │
│  │  ┌───────────────────────────────────────────────┐        │  │
│  │  │ 2️⃣ UserClarificationAgent                     │        │  │
│  │  │   Role: Get missing info from user            │        │  │
│  │  │   Tool: ask_user(question, suggestions)        │        │  │
│  │  │   Trigger: "NEED_USER_CLARIFICATION: xyz"     │        │  │
│  │  └───────────────────────────────────────────────┘        │  │
│  │                        ↕                                    │  │
│  │  ┌───────────────────────────────────────────────┐        │  │
│  │  │ 3️⃣ QAValidator                                 │        │  │
│  │  │   Role: Verify completeness & quality          │        │  │
│  │  │   Tools: None (validation only)                │        │  │
│  │  │   Termination: "APPROVE"                       │        │  │
│  │  └───────────────────────────────────────────────┘        │  │
│  │                                                             │  │
│  │  Termination: TextMentionTermination("APPROVE")           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  Model: OpenAIChatCompletionClient (via OpenAIAdapter)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ **Tool-Spezifikation**

### **1. evaluate_requirement**

**API Endpoint**: `POST /api/v2/evaluate/single`
**Service**: `backend_app_v2/services/evaluation_service.py`

**Input**:
```python
{
    "text": "Die Plattform muss schnell sein",
    "criteria_keys": ["clarity", "testability", "measurability"]
}
```

**Output**:
```python
{
    "score": 0.42,
    "verdict": "fail",
    "evaluation": [
        {
            "criterion": "clarity",
            "score": 0.3,
            "passed": false,
            "feedback": "Schwammige Formulierung: 'schnell' ist nicht messbar"
        },
        {
            "criterion": "testability",
            "score": 0.5,
            "passed": false,
            "feedback": "Keine Akzeptanzkriterien definiert"
        },
        {
            "criterion": "measurability",
            "score": 0.45,
            "passed": false,
            "feedback": "Fehlende Metriken (z.B. Latenz <2s)"
        }
    ]
}
```

**Tool Signature**:
```python
async def evaluate_requirement(
    requirement_text: Annotated[str, "The requirement to evaluate"],
    criteria_keys: Annotated[List[str], "Quality criteria"] = None
) -> Dict[str, Any]
```

---

### **2. rewrite_requirement**

**API Endpoint**: `POST /api/v1/validate/batch`
**Service**: `backend_app_v2/routers/validate_router.py`

**Input**:
```python
{
    "items": ["Die Plattform muss schnell sein"]
}
```

**Output**:
```python
[{
    "id": 1,
    "originalText": "Die Plattform muss schnell sein",
    "correctedText": "Als Nutzer möchte ich Seitenladezeiten <2s (P95), damit ich effizient arbeiten kann",
    "status": "accepted",
    "score": 0.88,
    "verdict": "pass",
    "evaluation": [...]
}]
```

**Tool Signature**:
```python
async def rewrite_requirement(
    requirement_text: Annotated[str, "The requirement to improve"]
) -> Dict[str, Any]
```

---

### **3. suggest_improvements**

**API Endpoint**: `POST /api/v1/validate/suggest`
**Service**: `backend_app/llm.py:llm_suggest`

**Input**:
```python
{
    "items": ["Die Plattform muss schnell sein"]
}
```

**Output**:
```python
{
    "items": {
        "REQ_1": {
            "suggestions": [
                {
                    "type": "add_actor",
                    "suggestion": "Füge User Story Format hinzu: 'Als [Rolle] möchte ich...'",
                    "priority": "high"
                },
                {
                    "type": "add_metric",
                    "suggestion": "Spezifiziere Performance-Metrik: 'Latenz <2000ms (P95)'",
                    "priority": "high"
                },
                {
                    "type": "add_criteria",
                    "suggestion": "Ergänze Akzeptanzkriterien: 'Given...When...Then...'",
                    "priority": "medium"
                }
            ]
        }
    }
}
```

**Tool Signature**:
```python
async def suggest_improvements(
    requirement_text: Annotated[str, "The requirement to analyze"]
) -> List[Dict[str, Any]]
```

---

### **4. detect_duplicates**

**API Endpoint**: `POST /api/kg/search/nodes` (semantic search in Qdrant)
**Service**: `arch_team/memory/qdrant_kg.py`

**Input**:
```python
{
    "requirements": [
        "Video-Wasserzeichen für Urheberrecht",
        "Wasserzeichen in Videos einfügen"
    ]
}
```

**Output**:
```python
[
    {
        "req1_idx": 0,
        "req2_idx": 1,
        "similarity": 0.94,
        "reason": "Beide beschreiben Video-Wasserzeichen für Urheberrecht"
    }
]
```

**Tool Signature**:
```python
async def detect_duplicates(
    requirements: Annotated[List[str], "Requirements to check"]
) -> List[Dict[str, Any]]
```

**Implementation Status**: TODO (Qdrant semantic search)

---

## 📜 **Agent Prompts**

### **RequirementsOperator Prompt**

**Datei**: `arch_team/agents/prompts/requirements_operator_prompt.py`

**Inhalt**:
```
ROLE: Requirements Operator
GOAL: Validate and improve software requirements

TOOLS:
- evaluate_requirement: Assess quality (score 0-1)
- rewrite_requirement: Improve structure
- suggest_improvements: Generate atomic fixes
- detect_duplicates: Find semantic overlaps

WORKFLOW:
1. Evaluate quality with evaluate_requirement()
2. If score < 0.7:
   a. Call suggest_improvements() for specific fixes
   b. Call rewrite_requirement() for improved version
3. For multiple requirements: Call detect_duplicates()
4. Signal completion: "READY_FOR_VALIDATION"

CLARIFICATION:
If info missing (e.g., criteria selection):
"NEED_USER_CLARIFICATION: <what is missing>"

OUTPUT:
- Quality scores
- Improvement suggestions
- Rewritten requirements
- Duplicate warnings
- "READY_FOR_VALIDATION"
```

---

### **UserClarificationAgent Prompt**

**Datei**: `arch_team/agents/prompts/user_clarification_prompt.py`

**Inhalt**:
```
ROLE: User Clarification Agent

TOOL: ask_user(question, suggested_answers=[])

WORKFLOW:
1. Detect: "NEED_USER_CLARIFICATION: xyz"
2. Call: ask_user("German question", ["option1", "option2"])
3. Wait for user response (via conversation)
4. Relay: "The user provided: <answer>. RequirementsOperator, continue..."

RULES:
- Questions in GERMAN
- ONE question at a time
- NEVER assume answers
```

---

### **QAValidator Prompt**

**Datei**: `arch_team/agents/prompts/qa_validator_prompt.py`

**Inhalt**:
```
ROLE: QA Validator

CHECKLIST:
- ✓ evaluate_requirement called?
- ✓ Quality scores documented?
- ✓ If score < 0.7: Improvements applied?
- ✓ Duplicates checked?
- ✓ Output clear and actionable?

RESPONSE:
✓ "APPROVE: <summary>"
✗ "NOT APPROVED: <issues>"
```

---

## 🔄 **Beispiel-Ablauf**

### **Scenario 1: Low-Quality Requirement**

**Input**:
```
Requirement: "Die App muss schnell sein"
```

**Execution Flow**:

```
1. [RequirementsOperator]
   → Tool: evaluate_requirement(text="Die App muss schnell sein")
   → Result: {"score": 0.35, "verdict": "fail"}

   → Tool: suggest_improvements(text="...")
   → Result: [
       {"type": "add_actor", "suggestion": "Als Nutzer möchte ich..."},
       {"type": "add_metric", "suggestion": "Latenz <2s (P95)"}
     ]

   → Tool: rewrite_requirement(text="...")
   → Result: {
       "correctedText": "Als Nutzer möchte ich Seitenladezeiten <2s (P95), damit ich effizient arbeite"
     }

   → "READY_FOR_VALIDATION"

2. [QAValidator]
   → Checks:
     - evaluate_requirement ✓
     - score documented (0.35) ✓
     - improvements suggested ✓
     - rewrite applied ✓

   → "APPROVE: Requirement validated (score: 0.35→0.88 after rewrite)"

3. ✅ TERMINATION
```

---

### **Scenario 2: Missing Information**

**Input**:
```
Requirement: "System soll skalierbar sein"
Context: User didn't specify criteria
```

**Execution Flow**:

```
1. [RequirementsOperator]
   → "NEED_USER_CLARIFICATION: Which criteria should be checked?"

2. [UserClarificationAgent]
   → Tool: ask_user(
       question="Welche Qualitätskriterien sollen geprüft werden?",
       suggested_answers=["clarity", "testability", "all"]
     )
   → (Waits for user via GUI/file polling)

3. [User via GUI]
   → Answer: "all"

4. [UserClarificationAgent]
   → "The user provided: all. RequirementsOperator, validate against all criteria."

5. [RequirementsOperator]
   → Tool: evaluate_requirement(text="...", criteria_keys=["clarity", "testability", "measurability"])
   → Continue workflow...
```

---

## 📂 **Dateistruktur**

```
arch_team/
├── tools/
│   ├── __init__.py
│   └── validation_tools.py          # FunctionTool definitions
│
├── agents/
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── requirements_operator_prompt.py
│   │   ├── qa_validator_prompt.py
│   │   └── user_clarification_prompt.py
│   │
│   ├── requirements_agent.py        # Main SocietyOfMindAgent wrapper
│   └── ...
│
├── REQUIREMENTS_VALIDATION_DESIGN.md  # This file
└── ...
```

---

## 🔌 **Integration Points**

### **Backend APIs (bereits vorhanden)**

| API Endpoint | Service | Status |
|-------------|---------|--------|
| `/api/v2/evaluate/single` | EvaluationService | ✅ Implemented |
| `/api/v1/validate/batch` | validate_router | ✅ Implemented |
| `/api/v1/validate/suggest` | validate_router | ✅ Implemented |
| `/api/kg/search/nodes` | QdrantKGClient | ✅ Implemented |

### **AutoGen Dependencies**

```python
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent, SocietyOfMindAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core.tools import FunctionTool
```

### **arch_team Dependencies**

```python
from arch_team.model.openai_adapter import OpenAIAdapter
from arch_team.memory.qdrant_kg import QdrantKGClient
```

---

## 🚀 **Nächste Schritte (Implementation)**

### **Phase 1: Tools** (2-3 Stunden)
- [x] Design: Tool-Spezifikation
- [ ] Code: `arch_team/tools/validation_tools.py`
  - [ ] evaluate_requirement (HTTP → backend_app_v2)
  - [ ] rewrite_requirement (HTTP → backend_app_v2)
  - [ ] suggest_improvements (HTTP → backend_app_v2)
  - [ ] detect_duplicates (Qdrant semantic search)
  - [ ] VALIDATION_TOOLS export

### **Phase 2: Prompts** (1-2 Stunden)
- [x] Design: Prompt-Spezifikation
- [ ] Code: `arch_team/agents/prompts/*.py`
  - [ ] requirements_operator_prompt.py
  - [ ] qa_validator_prompt.py
  - [ ] user_clarification_prompt.py

### **Phase 3: Agent** (3-4 Stunden)
- [x] Design: Society of Mind Architecture
- [ ] Code: `arch_team/agents/requirements_agent.py`
  - [ ] RequirementsValidationAgent class
  - [ ] initialize() method
  - [ ] validate_requirements() method
  - [ ] ask_user tool (file-based polling)
  - [ ] SocietyOfMindAgent setup
  - [ ] RoundRobinGroupChat mit Termination

### **Phase 4: Testing** (2-3 Stunden)
- [ ] Unit-Tests: Tool HTTP calls
- [ ] Integration-Test: End-to-End validation flow
- [ ] User-Interaction-Test: ask_user polling
- [ ] Performance-Test: Batch validation (10+ requirements)

### **Phase 5: Frontend Integration** (Optional)
- [ ] React Component: RequirementValidator.jsx
- [ ] Live updates via EventBus
- [ ] Quality scorecard visualization

---

## 📊 **Erfolgs-Kriterien**

- ✅ Requirements mit score < 0.7 werden automatisch verbessert
- ✅ User Story Format wird korrekt angewendet
- ✅ Acceptance Criteria werden vorgeschlagen
- ✅ Duplikate werden erkannt (Similarity > 0.9)
- ✅ User-Clarification funktioniert via GUI
- ✅ QAValidator prüft alle Schritte korrekt
- ✅ End-to-End Latenz < 30s für 5 Requirements

---

## 🔗 **Referenzen**

- **AutoGen Society of Mind**: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/society-of-mind.html
- **Referenz-Implementation**: `arch_team/dev_folder_/agent.py` (GitHub MCP Agent)
- **Backend Evaluation API**: `backend_app_v2/services/evaluation_service.py`
- **Requirements Engineering Best Practices**: IEEE 29148, IREB CPRE
