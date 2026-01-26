"""Error handling utilities for consistent error responses."""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel

from mamba.models.events import ErrorEvent

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standard error codes for API responses."""

    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"

    # Request errors
    INVALID_REQUEST = "INVALID_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"

    # Provider errors
    RATE_LIMITED = "RATE_LIMITED"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


class ErrorResponse(BaseModel):
    """HTTP error response model."""

    detail: str
    code: ErrorCode | None = None
    request_id: str | None = None


# User-friendly error messages by error code
USER_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.AUTH_REQUIRED: "Authentication required",
    ErrorCode.AUTH_INVALID: "Invalid authentication credentials",
    ErrorCode.AUTH_EXPIRED: "Token has expired",
    ErrorCode.INVALID_REQUEST: "Invalid request format",
    ErrorCode.VALIDATION_ERROR: "Request validation failed",
    ErrorCode.MODEL_NOT_FOUND: "The requested model was not found",
    ErrorCode.RATE_LIMITED: (
        "The service is experiencing high demand. Please try again in a moment."
    ),
    ErrorCode.MODEL_UNAVAILABLE: (
        "The requested model is temporarily unavailable. Please try a different model."
    ),
    ErrorCode.PROVIDER_ERROR: "The AI provider returned an error. Please try again.",
    ErrorCode.INTERNAL_ERROR: "An unexpected error occurred. Our team has been notified.",
    ErrorCode.SERVICE_UNAVAILABLE: (
        "The service is temporarily unavailable. Please try again later."
    ),
    ErrorCode.TIMEOUT: "The request timed out. Please try again.",
}

# Default message for unknown errors
DEFAULT_USER_MESSAGE = "An unexpected error occurred"

# Maximum length for error details
MAX_ERROR_LENGTH = 500


def get_user_message(code: ErrorCode | None, default: str | None = None) -> str:
    """Get user-appropriate error message for an error code.

    Args:
        code: The error code.
        default: Default message if code not found.

    Returns:
        User-friendly error message.
    """
    if code is None:
        return default or DEFAULT_USER_MESSAGE

    return USER_MESSAGES.get(code, default or DEFAULT_USER_MESSAGE)


def truncate_error(error: str, max_length: int = MAX_ERROR_LENGTH) -> str:
    """Truncate error message if too long.

    Args:
        error: The error message.
        max_length: Maximum allowed length.

    Returns:
        Truncated error message.
    """
    if len(error) <= max_length:
        return error

    return error[: max_length - 3] + "..."


def create_error_response(
    code: ErrorCode,
    detail: str | None = None,
    request_id: str | None = None,
) -> ErrorResponse:
    """Create a standardized error response.

    Args:
        code: The error code.
        detail: Optional custom detail message.
        request_id: Optional request ID.

    Returns:
        ErrorResponse model.
    """
    message = detail if detail else get_user_message(code)
    return ErrorResponse(
        detail=truncate_error(message),
        code=code,
        request_id=request_id,
    )


def create_stream_error_event(
    code: ErrorCode | None = None,
    message: str | None = None,
) -> ErrorEvent:
    """Create an error event for streaming responses.

    Args:
        code: Optional error code.
        message: Optional custom message (takes precedence over code).

    Returns:
        ErrorEvent model for SSE streaming.
    """
    if message:
        error_message = truncate_error(message)
    else:
        error_message = get_user_message(code)

    return ErrorEvent(error=error_message)


def classify_exception(exc: Exception) -> ErrorCode:
    """Classify an exception to an error code.

    Args:
        exc: The exception to classify.

    Returns:
        Appropriate error code.
    """
    # Import here to avoid circular imports
    import httpx
    from pydantic import ValidationError

    exc_type = type(exc).__name__

    # Validation errors
    if isinstance(exc, ValidationError):
        return ErrorCode.VALIDATION_ERROR

    # HTTP errors from upstream
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 401:
            return ErrorCode.AUTH_INVALID
        elif status_code == 429:
            return ErrorCode.RATE_LIMITED
        elif status_code == 404:
            return ErrorCode.MODEL_NOT_FOUND
        elif status_code >= 500:
            return ErrorCode.SERVICE_UNAVAILABLE
        else:
            return ErrorCode.PROVIDER_ERROR

    # Timeout errors
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return ErrorCode.TIMEOUT

    # Connection errors
    if isinstance(exc, (httpx.ConnectError, ConnectionError)):
        return ErrorCode.SERVICE_UNAVAILABLE

    # Default to internal error
    return ErrorCode.INTERNAL_ERROR


def log_error(
    exc: Exception,
    code: ErrorCode | None = None,
    request_id: str | None = None,
    **context: Any,
) -> None:
    """Log an error with context.

    Logs the full exception for debugging while creating
    user-appropriate error messages.

    Args:
        exc: The exception that occurred.
        code: Optional pre-classified error code.
        request_id: Optional request ID.
        **context: Additional context to include in log.
    """
    if code is None:
        code = classify_exception(exc)

    log_extra = {
        "error_code": code.value,
        "error_type": type(exc).__name__,
        "request_id": request_id,
        **context,
    }

    # Error level for user-facing errors, exception level for internal errors
    if code == ErrorCode.INTERNAL_ERROR:
        logger.exception("Internal error occurred", extra=log_extra)
    else:
        logger.error(f"Request error: {exc}", extra=log_extra)
