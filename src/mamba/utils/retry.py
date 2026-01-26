"""Retry utilities with exponential backoff for handling transient failures."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx

logger = logging.getLogger(__name__)

# Type variables for generic retry decorator
P = ParamSpec("P")
T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 16.0  # seconds

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {
    429,  # Rate Limited
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# Non-retryable HTTP status codes (fail immediately)
NON_RETRYABLE_STATUS_CODES = {
    400,  # Bad Request
    401,  # Unauthorized
    403,  # Forbidden
    404,  # Not Found
    422,  # Unprocessable Entity
}


class RetryError(Exception):
    """Error raised after all retry attempts are exhausted.

    Attributes:
        original_error: The last error that occurred.
        attempts: Number of retry attempts made.
    """

    def __init__(self, original_error: Exception, attempts: int):
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(
            f"All {attempts} retry attempts exhausted. "
            f"Last error: {type(original_error).__name__}: {original_error}"
        )


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable.

    Args:
        error: The exception to check.

    Returns:
        True if the error is retryable, False otherwise.
    """
    # Check for HTTP errors with retryable status codes
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in RETRYABLE_STATUS_CODES

    # Check for connection-related errors (retryable)
    if isinstance(
        error,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return True

    # Check for OpenAI-specific errors (pydantic_ai wraps these)
    error_str = str(error).lower()
    if any(
        phrase in error_str
        for phrase in [
            "rate limit",
            "connection reset",
            "connection refused",
            "timeout",
            "temporary failure",
            "service unavailable",
        ]
    ):
        return True

    return False


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> float:
    """Calculate exponential backoff delay for a given attempt.

    Args:
        attempt: The current attempt number (0-indexed).
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.

    Returns:
        Delay in seconds for this attempt.
    """
    # Exponential backoff: base_delay * 2^attempt
    delay = base_delay * (2**attempt)
    return min(delay, max_delay)


async def retry_with_backoff(
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    **kwargs: P.kwargs,
) -> T:
    """Execute an async function with retry logic and exponential backoff.

    Args:
        func: The async function to execute.
        *args: Positional arguments to pass to the function.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay in seconds.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The result of the function call.

    Raises:
        RetryError: If all retry attempts are exhausted.
        Exception: If a non-retryable error occurs.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except asyncio.CancelledError:
            # Don't retry on cancellation
            raise
        except Exception as e:
            last_error = e

            # Check if error is retryable
            if not is_retryable_error(e):
                logger.warning(
                    f"Non-retryable error on attempt {attempt + 1}/{max_retries}: "
                    f"{type(e).__name__}: {e}"
                )
                raise

            # Log retry attempt
            if attempt < max_retries - 1:
                delay = calculate_backoff_delay(attempt, base_delay, max_delay)
                logger.warning(
                    f"Retryable error on attempt {attempt + 1}/{max_retries}: "
                    f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Final attempt {attempt + 1}/{max_retries} failed: "
                    f"{type(e).__name__}: {e}"
                )

    # All retries exhausted
    assert last_error is not None
    raise RetryError(last_error, max_retries)


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to add retry logic with exponential backoff to an async function.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.
        max_delay: Maximum delay in seconds.

    Returns:
        A decorator function.

    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        async def call_api():
            ...
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                **kwargs,
            )

        return wrapper

    return decorator
