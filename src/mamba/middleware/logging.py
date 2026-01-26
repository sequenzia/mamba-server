"""Structured logging middleware with JSON format support."""

import json
import logging
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable for request ID
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add request ID from context if available
        request_id = request_id_var.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add extra fields from record
        if hasattr(record, "request_id") and record.request_id:
            log_entry["request_id"] = record.request_id

        # Include any extra data passed to the logger
        for key in ["method", "path", "status_code", "duration_ms", "error_type"]:
            if hasattr(record, key):
                value = getattr(record, key)
                if value is not None:
                    log_entry[key] = value

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Text log formatter for development."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with request ID prefix."""
        # Add request ID prefix if available
        request_id = request_id_var.get()
        if request_id:
            record.msg = f"[{request_id[:8]}] {record.msg}"
        return super().format(record)


def configure_logging(
    level: str = "INFO",
    format: str = "json",
) -> None:
    """Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        format: Output format (json or text).
    """
    # Remove existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Set formatter based on format
    if format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())

    # Configure root logger
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging with timing."""

    def __init__(self, app, logger: logging.Logger | None = None):
        super().__init__(app)
        self.logger = logger or logging.getLogger("mamba.access")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Log request start/end with timing information."""
        # Get request ID from state (set by RequestIdMiddleware)
        request_id = getattr(request.state, "request_id", None)

        # Set context variable for use in other log calls
        token = request_id_var.set(request_id)

        try:
            # Log request start
            self.logger.info(
                "Request started",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )

            # Process request and measure time
            start_time = time.perf_counter()
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Log request completion
            self.logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

            return response

        except Exception as e:
            # Log error
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.logger.exception(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error_type": type(e).__name__,
                },
            )
            raise
        finally:
            # Reset context variable
            request_id_var.reset(token)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name, typically __name__.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
