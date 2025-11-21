# Port Configuration Migration Guide

## Overview

This guide documents the migration from hardcoded port numbers to a centralized port configuration system using `backend/core/ports.py` as the single source of truth.

## Completed Migrations

The following critical files have been updated to use the centralized port configuration:

### Phase 1: Foundation
1. ✅ **backend/core/ports.py** (NEW) - Central configuration module
2. ✅ **.env.example** - Standardized port variable documentation
3. ✅ **vite.config.js** - Dynamic frontend proxy configuration
4. ✅ **backend/core/settings.py** - Backend settings integration
5. ✅ **backend/main.py** - FastAPI application port configuration
6. ✅ **arch_team/service.py** - Flask service port configuration
7. ✅ **backend/core/vector_store.py** - Qdrant client configuration with fallback

## Standardized Port Variables

### New Variable Names (Use These)
```bash
FRONTEND_PORT=3000          # Vite dev server
BACKEND_PORT=8087           # FastAPI main backend
ARCH_TEAM_PORT=8000         # Arch team Flask service
AGENT_WORKER_PORT=8090      # Distributed agent worker
QDRANT_PORT=6333            # Qdrant vector database (primary)
QDRANT_PORT_FALLBACK=6401   # Qdrant fallback port (docker-compose)
```

### Vite-Specific Variables
```bash
VITE_BACKEND_PORT=8087      # For Vite proxy (browser-accessible)
VITE_ARCH_TEAM_PORT=8000    # For Vite proxy (browser-accessible)
```

### Deprecated Variables (Legacy Support)
```bash
API_PORT → BACKEND_PORT     # Will show deprecation warning
APP_PORT → ARCH_TEAM_PORT   # Will show deprecation warning
PORT → AGENT_WORKER_PORT    # Will show deprecation warning
```

## Migration Pattern for Python Files

### Step 1: Add Import at Top of File
```python
# Import centralized port configuration
try:
    from backend.core.ports import get_ports
    _ports = get_ports()
except ImportError:
    _ports = None
```

### Step 2: Replace Hardcoded Ports
```python
# BEFORE (hardcoded):
port = int(os.environ.get("APP_PORT", "8000"))

# AFTER (centralized with legacy fallback):
port = _ports.ARCH_TEAM_PORT if _ports else int(os.environ.get("ARCH_TEAM_PORT", os.environ.get("APP_PORT", "8000")))
```

### Step 3: Use Service URLs (Docker/Production)
```python
# Access pre-built service URLs from ports module:
backend_url = _ports.BACKEND_URL if _ports else f"http://localhost:8087"
arch_team_url = _ports.ARCH_TEAM_URL if _ports else f"http://localhost:8000"
qdrant_url = _ports.QDRANT_FULL_URL if _ports else "http://localhost:6333"
```

## Remaining Files to Migrate

The following files still have hardcoded port numbers and should be migrated incrementally:

### High Priority (Active Services) - ✅ COMPLETED

#### agent_worker/app.py - ✅ DONE
- Migrated to use `_ports.AGENT_WORKER_PORT` with `PORT` as legacy fallback
- Impact: Distributed agent worker service

### Medium Priority (Memory/Pipeline Files) - ✅ COMPLETED

#### arch_team/memory/ - ✅ DONE (5 files)
- ✅ `qdrant_kg.py` - Line 53: Uses `_ports.QDRANT_FULL_URL`
- ✅ `qdrant_trace_sink.py` - Line 28: Uses `_ports.QDRANT_FULL_URL`
- ✅ `retrieval.py` - Line 54: Uses `_ports.QDRANT_FULL_URL`

#### arch_team/pipeline/ - ✅ DONE (2 files)
- ✅ `upload_ingest.py` - Line 83: Uses `_ports.QDRANT_FULL_URL`
- ✅ `store_requirements.py` - Line 98: Uses `_ports.QDRANT_FULL_URL`

### Low Priority (Test Files)

#### tests/ (20+ files)
- Files: `tests/backend/`, `tests/services/`, `tests/parity/`, `tests/e2e/`
- Current: Many use hardcoded localhost URLs with ports
- Action: Update test fixtures to read from `get_ports()` or environment
- Impact: Test reliability across environments

#### Test Fixtures Example:
```python
# conftest.py or test fixtures
import pytest
from backend.core.ports import get_ports

@pytest.fixture
def api_base_url():
    ports = get_ports()
    return ports.BACKEND_URL

@pytest.fixture
def arch_team_url():
    ports = get_ports()
    return ports.ARCH_TEAM_URL
```

### Docker Configuration

#### docker-compose.yml
- Current: Hardcoded port mappings
- Action: Use environment variable expansion
```yaml
services:
  backend:
    ports:
      - "${BACKEND_PORT:-8087}:${BACKEND_PORT:-8087}"
    environment:
      - BACKEND_PORT=${BACKEND_PORT:-8087}
      - CONFIG_ENV=docker-compose
```

#### Dockerfile / startup scripts
- Review for hardcoded ports in EXPOSE, CMD, or ENTRYPOINT
- Replace with environment variable expansion: `${BACKEND_PORT}`

### Frontend HTML Files (Legacy)

#### frontend/*.html
- Files: `index.html`, `mining_demo.html`, `reports.html`, `kg_view.html`, etc.
- Current: JavaScript has hardcoded port numbers (e.g., `const API_BASE = "http://localhost:8087"`)
- Action: Update to read from window.location or injected config
```javascript
// BEFORE:
const API_BASE = "http://localhost:8087"

// AFTER:
const API_PORT = new URLSearchParams(window.location.search).get('api_port') || '8087'
const API_BASE = `http://${window.location.hostname}:${API_PORT}`
```

## Environment-Specific Configuration

### Development (Local)
```bash
CONFIG_ENV=dev
# Uses localhost URLs
# backend/core/ports.py automatically builds: http://localhost:{port}
```

### Docker Compose
```bash
CONFIG_ENV=docker-compose
# Uses container DNS names
# backend/core/ports.py automatically builds: http://backend:{port}
```

### Production
```bash
CONFIG_ENV=production
# Uses environment-specific URLs
BACKEND_BASE_URL=https://api.example.com
ARCH_TEAM_BASE_URL=https://mining.example.com
QDRANT_FULL_URL=https://qdrant.example.com:6333
```

## Testing the Migration

### Step 1: Verify Environment Variables
```bash
# Check that your .env file uses new variable names
cat .env | grep -E "(BACKEND|ARCH_TEAM|AGENT_WORKER|QDRANT)_PORT"
```

### Step 2: Test Service Startup
```bash
# Backend should start on configured BACKEND_PORT
python -m uvicorn backend.main:fastapi_app --host 0.0.0.0 --port ${BACKEND_PORT:-8087}

# Arch team service should start on configured ARCH_TEAM_PORT
python -m arch_team.service
```

### Step 3: Verify Deprecation Warnings
```bash
# If you still have API_PORT in .env, you should see a warning:
# "Using deprecated environment variable API_PORT. Please migrate to BACKEND_PORT."
```

### Step 4: Test Service Discovery
```python
# In Python shell:
from backend.core.ports import get_ports
ports = get_ports()
print(f"Backend: {ports.BACKEND_URL}")
print(f"Arch Team: {ports.ARCH_TEAM_URL}")
print(f"Qdrant: {ports.QDRANT_FULL_URL}")
```

### Step 5: Test Frontend Proxy
```bash
# Start Vite dev server
npm run dev

# Verify proxy configuration in browser console
# Check that /api requests route to correct backend ports
```

## Rollback Plan

If issues arise, the migration supports gradual rollback:

1. **Keep legacy variable names** - They still work with deprecation warnings
2. **Selective rollback** - Each file can independently use old or new config
3. **Fallback logic** - All updates include `if _ports else` fallback to legacy behavior

Example rollback in any file:
```python
# Temporarily bypass centralized config
port = int(os.environ.get("API_PORT", "8087"))  # Old way still works
```

## Best Practices

### DO:
- ✅ Use `get_ports()` for service-to-service communication
- ✅ Use standardized variable names (`BACKEND_PORT`, not `API_PORT`)
- ✅ Include try/except when importing ports module for graceful fallback
- ✅ Check for deprecation warnings and update .env files
- ✅ Document any new services in backend/core/ports.py

### DON'T:
- ❌ Hardcode port numbers (use environment variables)
- ❌ Mix old and new variable names in the same file
- ❌ Remove legacy fallbacks until all files are migrated
- ❌ Assume ports module is available in all contexts (use try/except)

## Progress Tracking

| Category | Total Files | Migrated | Remaining |
|----------|------------|----------|-----------|
| Core Services | 7 | 7 | 0 |
| Agent Worker | 1 | 1 | 0 |
| Memory/Pipeline | 5 | 5 | 0 |
| Tests | 25+ | 0 | 25+ |
| Docker Config | 3 | 0 | 3 |
| Frontend HTML | 10+ | 1 (via vite) | 9 |
| **TOTAL** | **60+** | **14** | **46+** |

**Status**: Phase 2 Complete (All Production Code) - Services running with centralized ports

## Questions or Issues?

If you encounter problems during migration:
1. Check that `.env` file exists and has correct variable names
2. Verify `backend/core/ports.py` is accessible from your module
3. Check for typos in new variable names (they're case-sensitive)
4. Review deprecation warnings in console output
5. Test with `CONFIG_ENV=dev` before docker-compose or production

## Next Steps

1. ✅ ~~Test current phase 1 changes with all three services running~~
2. ✅ ~~Migrate agent_worker/app.py (high priority)~~
3. ✅ ~~Audit arch_team/memory/ and arch_team/pipeline/ files~~
4. Update test fixtures for consistent testing (25+ files)
5. Update Docker configuration (docker-compose.yml, Dockerfile)
6. Migrate legacy frontend HTML files (9 files)
7. Remove legacy variable support after full migration complete

## Phase 2 Summary (Completed)

**Files Migrated**: 6 files
- [agent_worker/app.py:51](agent_worker/app.py#L51)
- [arch_team/memory/qdrant_kg.py:53](arch_team/memory/qdrant_kg.py#L53)
- [arch_team/memory/qdrant_trace_sink.py:28](arch_team/memory/qdrant_trace_sink.py#L28)
- [arch_team/memory/retrieval.py:54](arch_team/memory/retrieval.py#L54)
- [arch_team/pipeline/upload_ingest.py:83](arch_team/pipeline/upload_ingest.py#L83)
- [arch_team/pipeline/store_requirements.py:98](arch_team/pipeline/store_requirements.py#L98)

**Verification**: All services restarted successfully with centralized port configuration. Deprecation warnings confirm the ports module is active.
