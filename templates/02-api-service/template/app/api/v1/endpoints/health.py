"""
Health check endpoint for {{PROJECT_NAME}}.

Provides readiness and liveness probes for container orchestration.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    database: str
    version: str


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.

    Checks:
    - API is responding
    - Database connection is working
    """
    db_status = "healthy"

    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    return HealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        database=db_status,
        version="0.1.0",
    )


@router.get("/live")
async def liveness_probe() -> dict:
    """
    Liveness probe for Kubernetes.

    Returns 200 if the service is alive.
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)) -> dict:
    """
    Readiness probe for Kubernetes.

    Returns 200 if the service is ready to accept traffic.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}