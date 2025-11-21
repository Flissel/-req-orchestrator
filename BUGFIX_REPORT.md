# Bugfix Report - Requirements Engineering System
**Datum:** 2025-11-07
**Test Phase:** Smoke Tests (E2E with Playwright)

---

## TEST RESULTS SUMMARY

| Category | Passed | Failed | Total |
|----------|--------|--------|-------|
| Smoke Tests | 2 | 4 | 6 |

**Pass Rate:** 33% (2/6 tests)

---

## FAILURES DETAILED

### 1. Frontend `networkidle` Timeout (4 tests)
**Affected Tests:**
- `tests/e2e/01-smoke-test.spec.ts:9:3` - Frontend loads successfully
- `tests/e2e/01-smoke-test.spec.ts:64:3` - All major UI components render
- `tests/e2e/01-smoke-test.spec.ts:85:3` - File upload component is present
- (Test 6 passed eventually after 1.2m)

**Error:**
```
Test timeout of 90000ms exceeded.
Error: page.waitForLoadState: Test timeout of 90000ms exceeded.
```

**Root Cause:**
`page.waitForLoadState('networkidle')` expects no network activity for 500ms. The React app at `http://localhost:3000` likely has:
- Long-polling SSE connections (`/api/workflow/stream`, `/api/clarification/stream`)
- Vite HMR websocket connection
- Pending API calls that don't complete

**Impact:** HIGH - Blocks all frontend E2E tests

**Fix Strategy:**
1. **Option A (Quick)**: Change wait strategy from `networkidle` to `domcontentloaded` + explicit element visibility checks
2. **Option B (Better)**: Mock SSE endpoints during tests or close SSE connections after initial load
3. **Option C (Best)**: Add test-specific flag to disable auto-connecting SSE streams in test mode

**Recommended Fix:** Option A (Quick win)

**Code Change:**
```diff
- await page.waitForLoadState('networkidle');
+ await page.waitForLoadState('domcontentloaded');
+ await page.waitForSelector('#root', { state: 'visible', timeout: 10000 });
```

---

### 2. Backend Health Endpoint 404
**Affected Test:**
- `tests/e2e/01-smoke-test.spec.ts:44:3` - Backend health endpoint responds

**Error:**
```
Expected: 200
Received: 404
```

**Root Cause:**
`arch_team/service.py` did not have a `/health` endpoint defined.

**Status:** ✅ **FIXED**
**Fix Applied:** Added `/health` endpoint at [service.py:74](arch_team/service.py#L74-L77)
```python
@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint for monitoring and testing."""
    return jsonify({"status": "ok", "service": "arch_team"}), 200
```

**Verification:**
```bash
$ curl http://localhost:8000/health
{"service":"arch_team","status":"ok"}
```

**Impact:** MEDIUM - Health checks critical for monitoring
**Re-test Required:** Yes (pending service restart)

---

## PASSING TESTS

### 3. Qdrant Vector DB Accessibility ✅
**Tests:**
- `tests/e2e/01-smoke-test.spec.ts:53:3` - Qdrant vector DB is accessible (68ms)
- `tests/e2e/01-smoke-test.spec.ts:94:3` - Start Mining button is present (1.2m)

**Status:** PASSING
**Qdrant Status:**
```bash
$ curl http://localhost:6401/collections
{"result":{"collections":[]},"status":"ok","time":0.000022212}
```

**Analysis:** Qdrant Docker container running perfectly on port 6401.

---

## ADDITIONAL ISSUES DISCOVERED (from service logs)

### 4. OPENAI_API_KEY not set Error
**Location:** `arch_team/agents/requirements_agent.py:69`
**Error:**
```python
RuntimeError: OPENAI_API_KEY not set
```

**Trigger:** POST `/api/validation/run` (validation endpoint)
**Impact:** HIGH - Validation workflow completely broken

**Root Cause:**
The `.env` file exists and contains `OPENAI_API_KEY`, but it's not being loaded properly in some execution contexts (likely when agents are initialized).

**Status:** ⚠️ NEEDS FIX

**Fix Strategy:**
1. Verify `.env` is loaded in `arch_team/agents/requirements_agent.py`
2. Add fallback to check `os.environ` explicitly
3. Add better error message with instructions

**Recommended Code Fix:**
```python
# arch_team/agents/requirements_agent.py:69
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    # Try loading .env explicitly
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY not set. "
        "Add it to .env file in project root or export as environment variable."
    )
```

---

## CONFIGURATION REVIEW

### Model Provider Selection ✓
**User Request:** "reduce to only use openai provider default selection gp models"

**Status:** ✅ **ALREADY COMPLIANT**

**Location:** [src/components/Configuration.jsx:77-82](src/components/Configuration.jsx#L77-L82)
```jsx
<select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
  <option value="gpt-4o-mini">gpt-4o-mini (schnell & günstig)</option>
  <option value="gpt-4o">gpt-4o (präzise)</option>
  <option value="gpt-4">gpt-4</option>
</select>
```

**Analysis:**
- Default model: `gpt-4o-mini` (line 5)
- Only OpenAI GPT models available
- No anthropic/gemini/ollama options present
- Provider locked to OpenAI

**No changes needed.**

---

## RECOMMENDED FIX PRIORITY

### Priority 1 (BLOCKING - must fix for E2E tests to pass)
1. **Fix Frontend `networkidle` Timeout** → Change wait strategy to `domcontentloaded`
2. **Verify /health endpoint fix** → Re-run smoke tests after service restart

### Priority 2 (CRITICAL - breaks core workflows)
3. **Fix OPENAI_API_KEY loading** → Add explicit `.env` loading in requirements_agent.py

### Priority 3 (ENHANCEMENT)
4. Create test data directory structure: `tests/data/test/test_requirements.md`
5. Add test mode flag to disable SSE auto-connect in React app

---

## NEXT STEPS

### Immediate Actions:
1. ✅ Health endpoint added - restart service
2. ⏳ Fix `networkidle` timeout in all smoke tests
3. ⏳ Fix OPENAI_API_KEY loading issue
4. ⏳ Re-run smoke tests
5. ⏳ Document remaining failures

### Testing Strategy:
```bash
# 1. Restart arch_team service (already done)
# 2. Fix smoke tests
# 3. Re-run
npx playwright test tests/e2e/01-smoke-test.spec.ts --reporter=list

# 4. Run mining workflow test
npx playwright test tests/e2e/02-mining-workflow.spec.ts --reporter=list

# 5. Full test suite
npx playwright test tests/e2e/ --reporter=list
```

---

## FILES MODIFIED

| File | Change | Status |
|------|--------|--------|
| `arch_team/service.py` | Added `/health` endpoint (line 74-77) | ✅ Done |
| `playwright.config.ts` | Changed `testDir` from `tests/ui` to `tests/e2e` | ✅ Done |
| `playwright.config.ts` | Changed `baseURL` from `4173` to `3000` | ✅ Done |
| `tests/e2e/*.spec.ts` | Will fix `networkidle` → `domcontentloaded` | ⏳ Next |
| `arch_team/agents/requirements_agent.py` | Will add explicit `.env` loading | ⏳ Next |

---

**Test Execution Time:** 6 minutes
**Report Generated:** 2025-11-07 22:10 UTC
