"""
API v1 Router for {{PROJECT_NAME}}.

All v1 endpoints are mounted here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, items

router = APIRouter()

# Include endpoint routers
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(items.router, prefix="/items", tags=["Items"])