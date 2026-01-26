"""Health check endpoint handler."""

import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Response

from mamba import __version__
from mamba.api.deps import SettingsDep
from mamba.models.health import ComponentHealth, HealthResponse, HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# Thresholds for health status determination
LATENCY_DEGRADED_MS = 2000  # Above this is considered degraded
HEALTH_CHECK_TIMEOUT_SECONDS = 5  # Maximum time for health check


async def check_openai_health(settings) -> ComponentHealth:
    """Check OpenAI API connectivity.

    Args:
        settings: Application settings.

    Returns:
        ComponentHealth indicating OpenAI status.
    """
    if not settings.health.openai_check_enabled:
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Check disabled",
        )

    if not settings.openai.api_key:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error="OpenAI API key not configured",
        )

    try:
        import httpx

        start_time = time.perf_counter()

        async with httpx.AsyncClient(timeout=settings.health.timeout_seconds) as client:
            # Use the models endpoint as a lightweight connectivity check
            response = await client.get(
                f"{settings.openai.base_url}/models",
                headers={"Authorization": f"Bearer {settings.openai.api_key}"},
            )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if response.status_code == 200:
            if latency_ms > LATENCY_DEGRADED_MS:
                return ComponentHealth(
                    status=HealthStatus.DEGRADED,
                    latency_ms=latency_ms,
                    message="High latency detected",
                )
            return ComponentHealth(
                status=HealthStatus.HEALTHY,
                latency_ms=latency_ms,
            )
        elif response.status_code == 401:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error="Invalid API key",
            )
        else:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error=f"Unexpected status code: {response.status_code}",
            )

    except httpx.TimeoutException:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error="Connection timeout",
        )
    except httpx.ConnectError as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error=f"Connection failed: {str(e)}",
        )
    except Exception as e:
        logger.exception("Unexpected error during OpenAI health check")
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error=f"Unexpected error: {type(e).__name__}",
        )


def determine_overall_status(checks: dict[str, ComponentHealth]) -> HealthStatus:
    """Determine overall health status from component checks.

    Args:
        checks: Dictionary of component health results.

    Returns:
        Overall health status.
    """
    if not checks:
        return HealthStatus.HEALTHY

    statuses = [check.status for check in checks.values()]

    if any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.UNHEALTHY
    elif any(s == HealthStatus.DEGRADED for s in statuses):
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


@router.get("/health", response_model=HealthResponse)
async def health_check(settings: SettingsDep, response: Response) -> HealthResponse:
    """Health check endpoint for Kubernetes probes.

    Returns service health status including component checks.
    - HTTP 200: Service is healthy or degraded
    - HTTP 503: Service is unhealthy
    """
    try:
        # Run health checks with timeout
        openai_check = await asyncio.wait_for(
            check_openai_health(settings),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        openai_check = ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error="Health check timeout",
        )

    checks = {"openai": openai_check}
    overall_status = determine_overall_status(checks)

    # Set HTTP status code based on health
    if overall_status == HealthStatus.UNHEALTHY:
        response.status_code = 503

    return HealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        checks=checks,
    )


@router.get("/health/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe - checks if process is running.

    Returns 200 if the application is alive (can accept requests).
    This should be a very fast check with no dependencies.
    """
    return {"status": "alive"}


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(settings: SettingsDep, response: Response) -> HealthResponse:
    """Kubernetes readiness probe - checks if service can handle traffic.

    Same as main health check - returns unhealthy if dependencies are down.
    """
    return await health_check(settings, response)
