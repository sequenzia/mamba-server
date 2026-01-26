"""Health check data models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class HealthStatus(str, Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status for a single component/dependency."""

    model_config = ConfigDict(use_enum_values=True)

    status: HealthStatus
    latency_ms: int | None = None
    error: str | None = None
    message: str | None = None


class HealthResponse(BaseModel):
    """Health check response model."""

    model_config = ConfigDict(use_enum_values=True)

    status: HealthStatus
    version: str
    timestamp: datetime
    checks: dict[str, ComponentHealth]
