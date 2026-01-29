# API Service Template - Follow Guide

> Step-by-step instructions to use this template

## Prerequisites

Before starting, ensure you have:

- [ ] Docker Desktop installed and running
- [ ] Python 3.11+ installed (optional for local development)
- [ ] Git installed

## Quick Start (5 minutes)

### Step 1: Import Template

```bash
# From the project root
python templates/tools/import_template.py 02-api-service my-api

# Or with custom output path
python templates/tools/import_template.py 02-api-service my-api --output ./projects/
```

### Step 2: Navigate to Project

```bash
cd my-api
```

### Step 3: Start Docker Services

```bash
# Start PostgreSQL database
docker-compose up -d

# Wait for database to be ready (~10 seconds)
```

### Step 4: Create Virtual Environment

```bash
# Create venv
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Setup Database

```bash
# Run migrations
alembic upgrade head
```

### Step 7: Start Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 8: Open API Docs

Navigate to: **http://localhost:8000/docs**

---

## Project Structure After Import

```
my-api/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI application
│   ├── core/
│   │   ├── config.py         # Settings
│   │   ├── database.py       # Database connection
│   │   └── security.py       # Auth utilities
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── users.py
│   │   │   │   ├── items.py
│   │   │   │   └── health.py
│   │   │   └── router.py
│   │   └── deps.py           # Dependencies
│   ├── models/               # SQLAlchemy models
│   │   ├── user.py
│   │   └── item.py
│   ├── schemas/              # Pydantic schemas
│   │   ├── user.py
│   │   └── item.py
│   └── services/             # Business logic
│       └── user_service.py
├── alembic/                  # Database migrations
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py
│   └── test_api/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Common Tasks

### Adding a New Endpoint

1. Create schema in `app/schemas/`:
   ```python
   # app/schemas/product.py
   from pydantic import BaseModel

   class ProductCreate(BaseModel):
       name: str
       price: float

   class ProductOut(ProductCreate):
       id: int
       model_config = ConfigDict(from_attributes=True)
   ```

2. Create model in `app/models/`:
   ```python
   # app/models/product.py
   from sqlalchemy import Column, Integer, String, Float
   from app.core.database import Base

   class Product(Base):
       __tablename__ = "products"
       id = Column(Integer, primary_key=True)
       name = Column(String, nullable=False)
       price = Column(Float, nullable=False)
   ```

3. Create endpoint in `app/api/v1/endpoints/`:
   ```python
   # app/api/v1/endpoints/products.py
   from fastapi import APIRouter, Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.api.deps import get_db
   from app.schemas.product import ProductCreate, ProductOut
   from app.models.product import Product

   router = APIRouter()

   @router.post("/", response_model=ProductOut)
   async def create_product(
       product: ProductCreate,
       db: AsyncSession = Depends(get_db)
   ):
       db_product = Product(**product.model_dump())
       db.add(db_product)
       await db.commit()
       await db.refresh(db_product)
       return db_product
   ```

4. Register in router:
   ```python
   # app/api/v1/router.py
   from app.api.v1.endpoints import products
   router.include_router(products.router, prefix="/products", tags=["products"])
   ```

### Creating a Database Migration

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add products table"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test
pytest tests/test_api/test_users.py -v
```

---

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/db` |
| `SECRET_KEY` | JWT secret key | `your-secret-key` |
| `ENVIRONMENT` | Environment name | `development` |
| `DEBUG` | Debug mode | `true` |

---

## Deployment

### Option 1: Docker

```bash
# Build image
docker build -t my-api .

# Run container
docker run -p 8000:8000 --env-file .env my-api
```

### Option 2: Docker Compose (Production)

```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## API Documentation

FastAPI automatically generates documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Next Steps

1. [ ] Review `CODING_RULES.md` for implementation guidelines
2. [ ] Check `docs/requirements/` for project requirements
3. [ ] Add your domain models in `app/models/`
4. [ ] Implement business logic in `app/services/`
5. [ ] Write tests in `tests/`
6. [ ] Deploy to production

---

*Template Version: 1.0.0*
*Last Updated: 2024*