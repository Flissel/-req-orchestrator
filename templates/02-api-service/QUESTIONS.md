# 📋 API Backend Service - Projekt-Fragebogen
## Template: 02-api-service (FastAPI + SQLAlchemy + PostgreSQL)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **API Name** | |
| **Zweck der API** | |
| **Konsumenten** | Frontend, Mobile App, Third-Party |

---

## A. API DESIGN

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | API-Stil? | REST (default), GraphQL | |
| A2 | Versionierung? | /api/v1/, Header-based | |
| A3 | Response-Format? | JSON (default), XML | |
| A4 | Pagination-Stil? | Offset (?page=2), Cursor-based | |
| A5 | Konsistente Error-Responses? | RFC 7807 Problem Details | |

---

## B. RESSOURCEN & ENDPUNKTE

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Haupt-Ressourcen? | users, products, orders, etc. | |
| B2 | CRUD pro Ressource? | GET, POST, PUT, DELETE | |
| B3 | Nested Resources? | /users/{id}/orders | |
| B4 | Bulk-Operationen? | POST /items/bulk | |
| B5 | Async Endpunkte? | Long-running tasks | |

---

## C. AUTHENTIFIZIERUNG & AUTORISIERUNG

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Auth-Methode? | [ ] JWT Bearer (default) [ ] API Keys [ ] OAuth2 [ ] Basic Auth | |
| C2 | Token-Ablauf? | 15min, 1h, 24h | |
| C3 | Refresh Tokens? | [ ] Ja [ ] Nein | |
| C4 | Rollen-basierte Zugriffe? | Admin, User, Service | |
| C5 | API Key Management? | Für Third-Party Zugriff | |

---

## D. DATENMODELL

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| D1 | Entitäten auflisten | Mit Feldern und Typen | |
| D2 | Beziehungen? | 1:n, n:m | |
| D3 | Validierungsregeln? | Required, min/max, regex | |
| D4 | Computed Fields? | total = sum(items) | |
| D5 | Soft-Delete? | deleted_at Timestamp | |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### API Framework (FastAPI)

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Dependency Injection? | [ ] FastAPI native (default) [ ] dependency-injector | |
| E2 | Serialization? | [ ] Pydantic v2 (default) [ ] Marshmallow | |
| E3 | Async/Sync? | [ ] Async (empfohlen) [ ] Sync | |
| E4 | Background Tasks? | [ ] FastAPI BackgroundTasks [ ] Celery [ ] ARQ | |

### Datenbank

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E5 | ORM? | [ ] SQLAlchemy 2.0 (default) [ ] SQLModel [ ] Tortoise | |
| E6 | Migrations? | [ ] Alembic (default) [ ] Manual | |
| E7 | Connection Pooling? | [ ] SQLAlchemy Pool [ ] PgBouncer | |
| E8 | Read Replicas? | [ ] Nein [ ] Ja | |

### Caching & Performance

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E9 | Caching? | [ ] Keins [ ] Redis [ ] Memcached | |
| E10 | Rate Limiting? | [ ] Nein [ ] slowapi [ ] Redis-based | |
| E11 | Response Compression? | [ ] Ja (gzip) [ ] Nein | |

---

## F. SICHERHEIT

| # | Frage | Antwort |
|---|-------|---------|
| F1 | CORS Origins? | *, specific domains | |
| F2 | HTTPS Only? | Ja/Nein | |
| F3 | Input Validation? | Pydantic, Custom | |
| F4 | SQL Injection Prevention? | ORM Queries | |
| F5 | Request Size Limits? | Max. Body Size | |

---

## G. OBSERVABILITY

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Logging Format? | [ ] JSON (empfohlen) [ ] Plain Text | |
| G2 | Log Level? | DEBUG, INFO, WARNING | |
| G3 | Tracing? | [ ] Nein [ ] OpenTelemetry [ ] Jaeger | |
| G4 | Metrics? | [ ] Nein [ ] Prometheus [ ] StatsD | |
| G5 | Health Checks? | /health, /ready, /live | |

---

## H. TESTING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Test Framework? | [ ] pytest (default) [ ] unittest | |
| H2 | Coverage Ziel? | 70%, 80%, 90% | |
| H3 | Integration Tests? | [ ] Ja [ ] Nein | |
| H4 | API Contract Tests? | [ ] Nein [ ] Schemathesis [ ] Dredd | |

---

## I. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | Container Runtime? | [ ] Docker (default) [ ] Podman | |
| I2 | ASGI Server? | [ ] Uvicorn (default) [ ] Hypercorn [ ] Gunicorn+Uvicorn | |
| I3 | Orchestrierung? | [ ] Docker Compose [ ] Kubernetes [ ] ECS | |
| I4 | Cloud Provider? | AWS, GCP, Azure, Hetzner | |
| I5 | CI/CD? | GitHub Actions, GitLab CI | |

---

## J. DOKUMENTATION

| # | Frage | Antwort |
|---|-------|---------|
| J1 | OpenAPI/Swagger UI? | Ja (default) | |
| J2 | ReDoc? | Ja/Nein | |
| J3 | Postman Collection? | Export generieren? | |
| J4 | SDK Generation? | Python, TypeScript, etc. | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] SQLAlchemy Models
- [ ] Pydantic Schemas
- [ ] API Routers
- [ ] Auth Middleware
- [ ] Alembic Migrations
- [ ] Docker Compose
- [ ] pytest Setup
- [ ] OpenAPI Schema

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "02-api-service",
  "backend": {
    "framework": "FastAPI",
    "language": "Python 3.11+",
    "async": true,
    "validation": "Pydantic v2"
  },
  "database": {
    "type": "PostgreSQL",
    "orm": "SQLAlchemy 2.0",
    "migrations": "Alembic"
  },
  "auth": {
    "method": "JWT Bearer",
    "library": "python-jose"
  },
  "deployment": {
    "container": "Docker",
    "server": "Uvicorn",
    "ci": "GitHub Actions"
  }
}
```
