# Test Analysis & Debugging Strategy Report

**Datum:** 2025-11-07
**Status:** System läuft - Bereit für systematisches Testing

---

## 1. AKTUELLE SYSTEM-STATUS

### Running Services ✓
- **Qdrant Vector DB**: Port 6401 (Docker)
- **arch_team Service**: Port 8000 (Flask + AutoGen 0.7.5)
- **React Frontend**: Port 3000 (Vite Dev Server)

### Behobene Probleme
1. ✓ Backend konsolidiert (3 →  1 unified `backend/`)
2. ✓ Lazy DB initialization
3. ✓ AutoGen 0.7.5 + tiktoken installiert
4. ✓ Import fixes (`autogen_ext.models.openai`)
5. ✓ .env path resolution (PROJECT_DIR)
6. ✓ validation_tools export alias

---

## 2. VORHANDENE TESTS

### Pytest Tests (`tests/`)
```
tests/
├── arch_team/          # AutoGen agent tests
│   ├── test_autogen_rac_smoke.py
│   ├── test_autogen_rag_tool.py
│   ├── test_chunk_miner_cli.py
│   ├── test_e2e_pipeline.py
│   └── test_qdrant_trace_sink.py
├── backend/           # Backend logic tests
│   ├── test_rag_models.py
│   ├── test_vector_payload_alias.py
│   └── test_lx_extract_v2.py
├── parity/            # v1/v2 compatibility tests
│   └── test_parity_core.py
└── services/          # Service layer tests
    └── test_evaluation_service.py
```

### Playwright UI Tests (`tests/ui/`)
```
tests/ui/
├── auto-refine.spec.ts           # Auto-refine loop test
├── apply-suggestion.spec.ts      # Suggestion application
├── compare-layout.spec.ts        # Layout verification
├── e2e-frontend-batch.spec.ts    # Batch processing E2E
├── modified-filter.spec.ts       # Filter functionality
└── optimizedui_*.spec.ts         # Optimized UI test
```

**Playwright Config:**
- Base URL: `http://localhost:4173` (static server)
- Test timeout: 60s
- Parallel execution enabled

---

## 3. KRITISCHE USER JOURNEYS (zu testen)

### Journey 1: Requirements Mining Workflow
1. Nutzer öffnet Frontend (http://localhost:3000)
2. Wählt Datei aus (.md/.txt/.pdf)
3. Konfiguriert Model & Settings
4. Klickt "Start Mining"
5. Sieht Agent Status Updates (SSE streaming)
6. Requirements werden extrahiert
7. Knowledge Graph wird visualisiert

**API Endpoints:**
- `POST /api/arch_team/process` - Master Workflow
- `GET /api/workflow/stream?session_id=...` - SSE für Workflow Messages
- `GET /api/clarification/stream?session_id=...` - SSE für User Clarifications

### Journey 2: Requirements Validation
1. Requirements werden angezeigt
2. Nutzer klickt "Validate"
3. Evaluation läuft (Quality Score)
4. Suggestions werden generiert
5. User kann Suggestions anwenden
6. Re-validation nach Apply

**API Endpoints:**
- `POST /api/validation/run` - Validation Workflow
- `POST /api/v1/validate/batch` - Batch Validation
- `POST /api/v1/validate/suggest` - Generate Suggestions

### Journey 3: Knowledge Graph Visualization
1. Nach Mining: KG wird gebaut
2. Cytoscape.js rendert Nodes & Edges
3. User kann zoomen/pan
4. Click auf Node zeigt Details
5. Export als JSON/PNG

**API Endpoints:**
- `POST /api/kg/build` - Build KG from requirements
- `GET /api/kg/search/nodes?query=...` - Search nodes
- `GET /api/kg/neighbors?node_id=...` - Get neighbors

---

## 4. IDENTIFIZIERTE RISIKEN & FEHLERQUELLEN

### Backend Risiken
1. **AutoGen Tool Calls** - Können fehlschlagen wenn LLM kein valides JSON zurückgibt
2. **Qdrant Connection** - Port 6401 Fallback zu 6333 muss funktionieren
3. **OpenAI API Key** - Muss korrekt geladen werden (aktuell OK)
4. **SQLite DB** - Path `./data/app.db` muss schreibbar sein
5. **Import Cycles** - Lazy loading verhindert, aber noch zu testen

### Frontend Risiken
1. **SSE Streaming** - EventSource kann disconnecten
2. **File Upload** - Binary files (.pdf/.docx) müssen korrekt gehandhabt werden
3. **React State** - Session ID generation & persistence
4. **API Proxy** - Vite proxy zu port 8000 muss funktionieren
5. **Cytoscape Init** - KG rendering kann bei großen Graphs crashen

### Integration Risiken
1. **CORS** - Cross-origin zwischen port 3000 ↔ 8000
2. **Timeouts** - Long-running LLM calls (>60s)
3. **Concurrent Requests** - Multiple mining sessions gleichzeitig
4. **Memory Leaks** - SSE streams nicht geclosed

---

## 5. TEST-STRATEGIE

### Phase 1: Smoke Tests
**Ziel:** Verify alle Services erreichbar sind
- [ ] GET http://localhost:3000 → HTML
- [ ] GET http://localhost:8000/health → 200 OK
- [ ] GET http://localhost:6401/collections → Qdrant JSON
- [ ] Playwright: Open frontend, verify title

### Phase 2: API Integration Tests
**Ziel:** Backend Endpoints einzeln testen
- [ ] POST /api/mining/upload (multipart file)
- [ ] POST /api/arch_team/process (JSON payload)
- [ ] GET /api/workflow/stream (SSE test)
- [ ] POST /api/kg/build (KG construction)
- [ ] POST /api/validation/run (Validation workflow)

### Phase 3: E2E Playwright Tests
**Ziel:** Full user journeys automatisiert
- [ ] Test 1: Upload file → Start mining → Verify requirements list
- [ ] Test 2: Mining → KG visualization → Verify nodes visible
- [ ] Test 3: Validate requirements → Apply suggestion → Re-validate
- [ ] Test 4: SSE streaming → Verify agent messages appear
- [ ] Test 5: Error handling → Invalid file upload → Error message

### Phase 4: Performance & Load Tests
**Ziel:** System unter Last testen
- [ ] Upload 10 files parallel
- [ ] Large file (10MB PDF)
- [ ] 100+ requirements in one session
- [ ] KG mit 500+ nodes

---

## 6. NÄCHSTE SCHRITTE

### Sofort (Heute)
1. ✅ Analyse abgeschlossen
2. ⏳ Erstelle Playwright E2E Tests für Journey 1-3
3. ⏳ Erstelle `scripts/test_all.sh` Runner
4. ⏳ Führe Tests aus, dokumentiere Fehler

### Kurz

fristig
1. Alle gefundenen Fehler fixen
2. Regression Tests nach jedem Fix
3. Coverage Report generieren
4. CI/CD Pipeline vorbereiten

### Mittel bis langfristig
1. Performance Monitoring (Prometheus/Grafana)
2. Load Testing (Locust/K6)
3. Security Audit (OWASP)
4. Documentation Update

---

## 7. TEST EXECUTION PLAN

### Playwright Tests Location
```
tests/e2e/
├── 01-smoke-test.spec.ts       # Basic connectivity
├── 02-mining-workflow.spec.ts  # Full mining journey
├── 03-kg-visualization.spec.ts # KG rendering
├── 04-validation.spec.ts       # Validation & suggestions
├── 05-sse-streaming.spec.ts    # Real-time updates
└── 06-error-handling.spec.ts   # Error scenarios
```

### Test Runner Script
```bash
#!/bin/bash
# scripts/test_all.sh

echo "=== Requirements Engineering System - Complete Test Suite ==="

# 1. Smoke tests
echo "\n[1/4] Running smoke tests..."
pytest tests/ -k smoke -v

# 2. Backend unit tests
echo "\n[2/4] Running backend tests..."
pytest tests/backend/ tests/services/ -v

# 3. Integration tests
echo "\n[3/4] Running integration tests..."
pytest tests/arch_team/ tests/parity/ -v

# 4. E2E Playwright tests
echo "\n[4/4] Running E2E tests..."
npx playwright test tests/e2e/

echo "\n=== Test Suite Complete ==="
```

---

## 8. SUCCESS CRITERIA

### Minimum Viable Test Coverage
- ✅ All 3 services start without errors
- ⏳ Smoke tests: 100% pass
- ⏳ API tests: 80% pass
- ⏳ E2E tests: 75% pass
- ⏳ No critical bugs blocking main workflows

### Definition of Done
- All tests documented
- Bug fixes committed
- Test runner script working
- CLAUDE.md updated with test instructions
- README updated with testing section

---

**Status:** ✅ Analyse abgeschlossen - Ready für Test Implementation
