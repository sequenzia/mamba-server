"""Tests for retry utilities with exponential backoff."""

import asyncio

import httpx
import pytest

from mamba.utils.retry import (
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_RETRIES,
    RetryError,
    calculate_backoff_delay,
    is_retryable_error,
    retry_with_backoff,
    with_retry,
)


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_rate_limit_is_retryable(self):
        """Test that 429 rate limit error is retryable."""
        response = httpx.Response(429)
        error = httpx.HTTPStatusError("Rate limited", request=None, response=response)
        assert is_retryable_error(error) is True

    def test_server_errors_are_retryable(self):
        """Test that 5xx server errors are retryable."""
        for status_code in [500, 502, 503, 504]:
            response = httpx.Response(status_code)
            error = httpx.HTTPStatusError(
                f"Server error {status_code}", request=None, response=response
            )
            assert is_retryable_error(error) is True

    def test_client_errors_not_retryable(self):
        """Test that 4xx client errors are not retryable."""
        for status_code in [400, 401, 403, 404, 422]:
            response = httpx.Response(status_code)
            error = httpx.HTTPStatusError(
                f"Client error {status_code}", request=None, response=response
            )
            assert is_retryable_error(error) is False

    def test_connection_errors_are_retryable(self):
        """Test that connection errors are retryable."""
        assert is_retryable_error(httpx.ConnectError("Failed to connect")) is True
        assert is_retryable_error(httpx.ConnectTimeout("Timeout")) is True
        assert is_retryable_error(httpx.ReadTimeout("Read timeout")) is True
        assert is_retryable_error(ConnectionError("Connection reset")) is True
        assert is_retryable_error(TimeoutError("Timeout")) is True

    def test_generic_error_not_retryable(self):
        """Test that generic errors are not retryable."""
        assert is_retryable_error(ValueError("Invalid value")) is False
        assert is_retryable_error(KeyError("Key not found")) is False

    def test_error_message_patterns_are_retryable(self):
        """Test that certain error message patterns are retryable."""
        assert is_retryable_error(Exception("Rate limit exceeded")) is True
        assert is_retryable_error(Exception("Connection reset by peer")) is True
        assert is_retryable_error(Exception("Request timeout")) is True
        assert is_retryable_error(Exception("Service unavailable")) is True


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    def test_first_attempt_uses_base_delay(self):
        """Test that first attempt (0) uses base delay."""
        delay = calculate_backoff_delay(0, base_delay=1.0)
        assert delay == 1.0

    def test_exponential_growth(self):
        """Test that delays grow exponentially."""
        assert calculate_backoff_delay(0, base_delay=1.0) == 1.0
        assert calculate_backoff_delay(1, base_delay=1.0) == 2.0
        assert calculate_backoff_delay(2, base_delay=1.0) == 4.0
        assert calculate_backoff_delay(3, base_delay=1.0) == 8.0

    def test_respects_max_delay(self):
        """Test that delay is capped at max_delay."""
        delay = calculate_backoff_delay(10, base_delay=1.0, max_delay=10.0)
        assert delay == 10.0

    def test_custom_base_delay(self):
        """Test custom base delay."""
        assert calculate_backoff_delay(0, base_delay=0.5) == 0.5
        assert calculate_backoff_delay(1, base_delay=0.5) == 1.0
        assert calculate_backoff_delay(2, base_delay=0.5) == 2.0


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        """Test that function succeeds on first try without retry."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self):
        """Test that function retries on retryable error."""
        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection failed")
            return "success"

        result = await retry_with_backoff(
            failing_then_success, max_retries=3, base_delay=0.01
        )

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_retry_error_after_max_retries(self):
        """Test that RetryError is raised after max retries exhausted."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("Connection failed")

        with pytest.raises(RetryError) as exc_info:
            await retry_with_backoff(always_fails, max_retries=3, base_delay=0.01)

        assert call_count == 3
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.original_error, httpx.ConnectError)

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self):
        """Test that non-retryable errors fail immediately without retry."""
        call_count = 0

        async def bad_request():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(400)
            raise httpx.HTTPStatusError("Bad request", request=None, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await retry_with_backoff(bad_request, max_retries=3, base_delay=0.01)

        # Should only be called once (no retries)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_preserves_original_error(self):
        """Test that original error is preserved in RetryError."""
        async def always_fails():
            raise httpx.ConnectError("Original error message")

        with pytest.raises(RetryError) as exc_info:
            await retry_with_backoff(always_fails, max_retries=2, base_delay=0.01)

        assert "Original error message" in str(exc_info.value.original_error)

    @pytest.mark.asyncio
    async def test_cancellation_not_retried(self):
        """Test that CancelledError is not retried."""
        call_count = 0

        async def cancelling_func():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await retry_with_backoff(cancelling_func, max_retries=3, base_delay=0.01)

        # Should only be called once
        assert call_count == 1


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        """Test that decorator correctly wraps the function."""

        @with_retry(max_retries=2, base_delay=0.01)
        async def my_func():
            return "decorated"

        result = await my_func()
        assert result == "decorated"

    @pytest.mark.asyncio
    async def test_decorator_retries_on_error(self):
        """Test that decorated function retries on error."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection failed")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_signature(self):
        """Test that decorator preserves function arguments."""

        @with_retry(max_retries=2, base_delay=0.01)
        async def func_with_args(a: int, b: str, c: bool = True) -> str:
            return f"{a}-{b}-{c}"

        result = await func_with_args(1, "test", c=False)
        assert result == "1-test-False"


class TestRetryError:
    """Tests for RetryError exception."""

    def test_error_message_includes_attempts(self):
        """Test that error message includes attempt count."""
        original = ValueError("Original error")
        error = RetryError(original, attempts=3)

        assert "3" in str(error)
        assert "retry" in str(error).lower()

    def test_error_preserves_original(self):
        """Test that original error is preserved."""
        original = ValueError("Original error")
        error = RetryError(original, attempts=3)

        assert error.original_error is original
        assert error.attempts == 3
