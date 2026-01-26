"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from mamba import __version__
from mamba.api.routes import api_router
from mamba.config import Settings, get_settings
from mamba.middleware.logging import LoggingMiddleware, configure_logging
from mamba.middleware.request_id import RequestIdMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    settings = get_settings()

    # Configure logging based on settings
    configure_logging(
        level=settings.logging.level,
        format=settings.logging.format,
    )

    logger.info(
        "Starting mamba-server",
        extra={
            "version": __version__,
            "host": settings.server.host,
            "port": settings.server.port,
            "auth_mode": settings.auth.mode,
            "log_level": settings.logging.level,
        },
    )

    # Validate required settings
    try:
        settings.validate_required()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise

    logger.info("mamba-server started successfully")

    yield

    # Shutdown
    logger.info("Shutting down mamba-server")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        settings: Optional settings override for testing.

    Returns:
        Configured FastAPI application.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="mamba-server",
        description="FastAPI backend for AI chat completions with Vercel AI SDK streaming",
        version=__version__,
        lifespan=lifespan,
    )

    # Configure middleware (order matters - last added = first executed)
    # CORS should be outermost to handle preflight requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors.allowed_origins,
        allow_credentials=True,
        allow_methods=settings.server.cors.allowed_methods,
        allow_headers=settings.server.cors.allowed_headers,
    )

    # Request ID middleware - adds X-Request-ID to all requests/responses
    app.add_middleware(RequestIdMiddleware)

    # Logging middleware - logs requests with timing
    app.add_middleware(LoggingMiddleware)

    # Register exception handlers
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # Register routes
    app.include_router(api_router)

    return app


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle value errors (configuration, etc.)."""
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)

    logger.exception(
        "Unhandled exception",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


# Create the default app instance
app = create_app()
