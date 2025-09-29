# 🚀 FastAPI Requirements Engineering System

**Modern Requirements Processing with AutoGen Agents & gRPC Workers**

## 🌟 Features

- ✨ **Modern FastAPI Backend** - Async/await, automatic OpenAPI docs
- 🤖 **AutoGen Multi-Agent System** - Distributed requirements processing
- 🔄 **gRPC Worker Runtime** - Scalable agent orchestration
- 📊 **Real-time WebSocket Updates** - Live processing status
- 🐳 **Docker & Docker Compose** - Production-ready deployment
- 🧪 **Comprehensive Testing** - Pytest with async support
- 📈 **Monitoring & Metrics** - Prometheus + Grafana
- 🌐 **Modern Frontend** - Interactive web interface
- 🔒 **Production Security** - Nginx reverse proxy, rate limiting

## 🚀 Quick Start

### **Option 1: Docker Compose (Empfohlen)**

```bash
# 1. Repository Setup
cd ~/Desktop/test

# 2. Environment konfigurieren
cp .env.example .env
# Bearbeiten Sie .env und setzen Sie OPENAI_API_KEY

# 3. System starten
docker-compose -f docker-compose.fastapi.yml up --build

# 4. Frontend öffnen
open http://localhost
```

### **Option 2: Local Development**

```bash
# 1. Dependencies installieren
pip install -r requirements_fastapi.txt

# 2. Environment konfigurieren
cp .env.example .env

# 3. System starten
python start_fastapi.py

# 4. Frontend öffnen
open fastapi_frontend.html
```

## v2 Quickstart (FastAPI Wrapper + Flask WSGI-Mount)

- Start (lokal)
  - Backend v2 (Port 8087 empfohlen):
    ```
    python -m uvicorn backend_app_v2.main:fastapi_app --host 0.0.0.0 --port 8087 --reload
    ```
    Siehe App-Setup in [backend_app_v2/main.py](backend_app_v2/main.py:25)
  - Frontend (statisch):
    - Direkt im Browser öffnen: [frontend/index.html](frontend/index.html), [frontend/mining_demo.html](frontend/mining_demo.html), [frontend/reports.html](frontend/reports.html), [frontend/kg_view.html](frontend/kg_view.html)
    - window.API_BASE ist vereinheitlicht auf http://localhost:8087

- Observability/Health:
  - Health: GET http://localhost:8087/health → implementiert in [backend_app_v2/main.py](backend_app_v2/main.py:53)
  - Readiness: GET http://localhost:8087/ready → [backend_app_v2/main.py](backend_app_v2/main.py:58)
  - Liveness: GET http://localhost:8087/livez → [backend_app_v2/main.py](backend_app_v2/main.py:61)
  - Request-ID Header: Middleware setzt X-Request-Id automatisch, siehe [backend_app_v2/main.py](backend_app_v2/main.py:31)

- CORS:
  - Globale CORS-Policy (allow_origins="*"): [backend_app_v2/main.py](backend_app_v2/main.py:31)

- Wichtige Endpunkte (v2 Router):
  - RAG/Vector Verwaltung + Suche: [backend_app_v2/routers/vector_router.py](backend_app_v2/routers/vector_router.py:20)
    - GET /api/v1/vector/collections
    - GET /api/v1/vector/health
    - POST/DELETE /api/v1/vector/reset
    - GET /api/v1/vector/source/full
    - GET /api/v1/rag/search?query=...&top_k=5
  - Validate/Batch/Streams: [backend_app_v2/routers/validate_router.py](backend_app_v2/routers/validate_router.py:11)
  - LX/Gold/Structure: [backend_app_v2/routers/lx_router.py](backend_app_v2/routers/lx_router.py:18), [backend_app_v2/routers/gold_router.py](backend_app_v2/routers/gold_router.py:11), [backend_app_v2/routers/structure_router.py](backend_app_v2/routers/structure_router.py:7)

## Konfiguration (ENV)

- Siehe Laufzeit-Konfiguration in [backend_app/settings.py](backend_app/settings.py:108)
- Relevante Keys:
  - OPENAI_API_KEY, OPENAI_MODEL
  - EMBEDDINGS_MODEL
  - QDRANT_URL, QDRANT_PORT, QDRANT_COLLECTION
  - SQLITE_PATH
- Frontend API-Basis:
  - window.API_BASE in Frontends ist auf http://localhost:8087 gesetzt:
    - [frontend/index.html](frontend/index.html:9)
    - [frontend/mining_demo.html](frontend/mining_demo.html:72)
    - [frontend/reports.html](frontend/reports.html:22)
    - [frontend/kg_view.html](frontend/kg_view.html:37)
    - [ui.html](ui.html:9)

## Routen- und Migrationsübersicht

- Konsolidierte Routenübersicht (Legacy Flask vs. FastAPI v2): [docs/backend/ROUTES.md](docs/backend/ROUTES.md:1)
- Abhängigkeits-Inventar (Module/Seiteneffekte/ENV): [docs/backend/MIGRATION_DEP_MAP.md](docs/backend/MIGRATION_DEP_MAP.md:1)

## Tests

- Paritätstests (MOCK_MODE=true): [tests/parity/test_parity_core.py](tests/parity/test_parity_core.py:1) → Validate/Suggest/Corrections/Vector/RAG sind grün
- UI-Tests (Playwright): [playwright.config.ts](playwright.config.ts:1), Beispiele in [tests/ui](tests/ui)

## 📡 API Endpoints

### **Core Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/system/status` | System status |
| `GET` | `/docs` | OpenAPI documentation |

### **New Health/Ready/Livez Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness probe (secondary health check) |
| `GET` | `/livez` | Liveness probe (primary health check) |

### **Requirements Processing**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/requirements/evaluate` | Single requirement evaluation |
| `POST` | `/api/v1/requirements/batch` | Batch requirements processing |
| `GET` | `/api/v1/processing/status/{id}` | Get processing status |

## 🧪 Testing

```bash
# Unit & Integration Tests
pytest test_fastapi_system.py -v

# Performance Tests
pytest test_fastapi_system.py::TestPerformance -v
```

## 🔧 Development

### **Adding New Agent Types**

1. Define agent in `backend_app/agents.py`
2. Register in `worker_startup.py`
3. Add tests in `test_fastapi_system.py`
4. Update Docker configuration

## 🆘 Support

- **Issues**: GitHub Issues
- **Documentation**: `/docs` endpoint
- **API Reference**: `/docs` (OpenAPI)
- **Health Status**: `/health` endpoint
