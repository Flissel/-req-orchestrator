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

## 📡 API Endpoints

### **Core Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/system/status` | System status |
| `GET` | `/docs` | OpenAPI documentation |

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
