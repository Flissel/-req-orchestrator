# API Service Template - Coding Rules

> Implementation guidelines and best practices for FastAPI backend services

## Table of Contents

1. [Project Structure](#project-structure)
2. [API Design](#api-design)
3. [Data Validation](#data-validation)
4. [Database](#database)
5. [Authentication](#authentication)
6. [Error Handling](#error-handling)
7. [Testing](#testing)
8. [Logging](#logging)
9. [Security](#security)
10. [Performance](#performance)

---

## Project Structure

### Directory Organization

```
app/
├── api/                    # API layer
│   ├── v1/                 # API version
│   │   ├── endpoints/      # Route handlers
│   │   └── router.py       # Version router
│   └── deps.py             # Shared dependencies
├── core/                   # Core configuration
│   ├── config.py           # Settings
│   ├── database.py         # DB connection
│   └── security.py         # Auth utilities
├── models/                 # SQLAlchemy models
├── schemas/                # Pydantic schemas
├── services/               # Business logic
└── main.py                 # Application entry
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `user_service.py` |
| Classes | PascalCase | `UserService` |
| Functions | snake_case | `get_user_by_id` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES` |
| Variables | snake_case | `user_count` |
| Env vars | SCREAMING_SNAKE | `DATABASE_URL` |

---

## API Design

### RESTful Conventions

```python
# ✅ Correct: RESTful resource naming
@router.get("/users")           # List users
@router.post("/users")          # Create user
@router.get("/users/{id}")      # Get user
@router.put("/users/{id}")      # Update user (full)
@router.patch("/users/{id}")    # Update user (partial)
@router.delete("/users/{id}")   # Delete user

# ❌ Wrong: Verb-based naming
@router.get("/getUsers")
@router.post("/createUser")
```

### Response Models

```python
from fastapi import APIRouter, status
from pydantic import BaseModel

# ✅ Always define response models
class UserOut(BaseModel):
    id: int
    email: str
    name: str | None

    model_config = ConfigDict(from_attributes=True)

@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Get user by ID",
    description="Retrieve a user by their unique identifier"
)
async def get_user(user_id: int) -> UserOut:
    ...
```

### Pagination

```python
from fastapi import Query

@router.get("/users", response_model=list[UserOut])
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max records to return"),
    db: AsyncSession = Depends(get_db)
) -> list[UserOut]:
    users = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return users.scalars().all()
```

### API Versioning

```python
# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import users, items, health

router = APIRouter()
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(items.router, prefix="/items", tags=["Items"])
router.include_router(health.router, prefix="/health", tags=["Health"])

# app/main.py
app.include_router(router, prefix="/api/v1")
```

---

## Data Validation

### Pydantic Schemas

```python
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime

# ✅ Separate schemas for different operations
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(None, min_length=2, max_length=100)

class UserOut(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserInDB(UserOut):
    hashed_password: str
```

### Custom Validators

```python
from pydantic import field_validator, model_validator

class UserCreate(BaseModel):
    email: str
    password: str
    password_confirm: str

    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()

    @model_validator(mode='after')
    def passwords_match(self) -> 'UserCreate':
        if self.password != self.password_confirm:
            raise ValueError('Passwords do not match')
        return self
```

---

## Database

### SQLAlchemy Models

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    items: Mapped[list["Item"]] = relationship(back_populates="owner")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
```

### Async Database Operations

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# ✅ Use async sessions
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        name=user_data.name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

### Migrations

```python
# alembic/env.py - ensure async support
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base

# Auto-generate migrations
# alembic revision --autogenerate -m "description"

# Apply migrations
# alembic upgrade head
```

---

## Authentication

### JWT Authentication

```python
# app/core/security.py
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

### Dependency Injection for Auth

```python
# app/api/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    return user
```

---

## Error Handling

### Custom Exceptions

```python
# app/core/exceptions.py
from fastapi import HTTPException, status

class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
```

### Exception Handlers

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

---

## Testing

### Test Setup

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.main import app
from app.core.database import Base

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

@pytest.fixture
async def client(db_session):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

### API Tests

```python
# tests/test_api/test_users.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/users",
        json={"email": "test@example.com", "password": "password123", "name": "Test"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data

@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient):
    response = await client.get("/api/v1/users/999")
    assert response.status_code == 404
```

---

## Logging

### Structured Logging

```python
# app/core/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

# Usage
logger = logging.getLogger(__name__)
logger.info("User created", extra={"user_id": user.id, "email": user.email})
```

---

## Security

### Input Sanitization

```python
# Always use Pydantic for input validation
# Never construct SQL queries with string interpolation

# ✅ Correct
await db.execute(select(User).where(User.id == user_id))

# ❌ Wrong
await db.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, credentials: LoginRequest):
    ...
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Performance

### Async Operations

```python
# ✅ Use async for I/O operations
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# ✅ Run CPU-bound tasks in thread pool
from fastapi.concurrency import run_in_threadpool

@router.post("/process")
async def process_data(data: DataIn):
    result = await run_in_threadpool(cpu_intensive_task, data)
    return result
```

### Caching

```python
from functools import lru_cache
from aiocache import cached

# For settings (sync)
@lru_cache()
def get_settings():
    return Settings()

# For async operations
@cached(ttl=300)  # 5 minutes
async def get_cached_data(key: str):
    ...
```

### Connection Pooling

```python
# app/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)
```

---

*These rules ensure consistency, maintainability, and performance across the API service.*