"""API route registration."""

from fastapi import APIRouter

from mamba.api.handlers.chat import router as chat_router
from mamba.api.handlers.health import router as health_router
from mamba.api.handlers.models import router as models_router

# Main API router that aggregates all endpoint routers
api_router = APIRouter()

# Include health check routes
api_router.include_router(health_router, tags=["health"])

# Include models routes
api_router.include_router(models_router, tags=["models"])

# Include chat routes
api_router.include_router(chat_router, tags=["chat"])
