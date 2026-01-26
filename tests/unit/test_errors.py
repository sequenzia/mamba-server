"""Tests for error handling utilities."""

import pytest
from pydantic import ValidationError

from mamba.models.events import ErrorEvent
from mamba.utils.errors import (
    DEFAULT_USER_MESSAGE,
    ErrorCode,
    ErrorResponse,
    classify_exception,
    create_error_response,
    create_stream_error_event,
    get_user_message,
    truncate_error,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_all_codes_defined(self):
        """Test all expected error codes are defined."""
        assert ErrorCode.AUTH_REQUIRED
        assert ErrorCode.AUTH_INVALID
        assert ErrorCode.AUTH_EXPIRED
        assert ErrorCode.INVALID_REQUEST
        assert ErrorCode.VALIDATION_ERROR
        assert ErrorCode.RATE_LIMITED
        assert ErrorCode.MODEL_UNAVAILABLE
        assert ErrorCode.INTERNAL_ERROR

    def test_codes_are_strings(self):
        """Test error codes serialize to strings."""
        assert ErrorCode.AUTH_REQUIRED.value == "AUTH_REQUIRED"
        assert ErrorCode.RATE_LIMITED.value == "RATE_LIMITED"


class TestGetUserMessage:
    """Tests for get_user_message function."""

    def test_returns_message_for_known_code(self):
        """Test returns user message for known code."""
        message = get_user_message(ErrorCode.RATE_LIMITED)
        assert "high demand" in message

    def test_returns_default_for_none(self):
        """Test returns default for None code."""
        message = get_user_message(None)
        assert message == DEFAULT_USER_MESSAGE

    def test_returns_custom_default(self):
        """Test returns custom default when provided."""
        message = get_user_message(None, default="Custom error")
        assert message == "Custom error"


class TestTruncateError:
    """Tests for truncate_error function."""

    def test_short_message_unchanged(self):
        """Test short messages are unchanged."""
        message = "Short error"
        assert truncate_error(message) == message

    def test_long_message_truncated(self):
        """Test long messages are truncated."""
        message = "A" * 1000
        result = truncate_error(message, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_custom_max_length(self):
        """Test custom max length is respected."""
        message = "A" * 100
        result = truncate_error(message, max_length=50)
        assert len(result) == 50


class TestCreateErrorResponse:
    """Tests for create_error_response function."""

    def test_creates_response_with_code(self):
        """Test creates response with error code."""
        response = create_error_response(ErrorCode.AUTH_REQUIRED)
        assert response.code == ErrorCode.AUTH_REQUIRED
        assert response.detail == "Authentication required"

    def test_creates_response_with_custom_detail(self):
        """Test creates response with custom detail."""
        response = create_error_response(
            ErrorCode.INTERNAL_ERROR,
            detail="Something specific went wrong",
        )
        assert response.detail == "Something specific went wrong"
        assert response.code == ErrorCode.INTERNAL_ERROR

    def test_includes_request_id(self):
        """Test includes request ID when provided."""
        response = create_error_response(
            ErrorCode.RATE_LIMITED,
            request_id="req-123",
        )
        assert response.request_id == "req-123"


class TestCreateStreamErrorEvent:
    """Tests for create_stream_error_event function."""

    def test_creates_event_with_code(self):
        """Test creates error event from code."""
        event = create_stream_error_event(code=ErrorCode.RATE_LIMITED)
        assert isinstance(event, ErrorEvent)
        assert "high demand" in event.error

    def test_creates_event_with_custom_message(self):
        """Test creates error event with custom message."""
        event = create_stream_error_event(message="Custom error message")
        assert event.error == "Custom error message"

    def test_message_takes_precedence(self):
        """Test custom message takes precedence over code."""
        event = create_stream_error_event(
            code=ErrorCode.RATE_LIMITED,
            message="Override message",
        )
        assert event.error == "Override message"

    def test_truncates_long_message(self):
        """Test truncates very long messages."""
        long_message = "A" * 1000
        event = create_stream_error_event(message=long_message)
        assert len(event.error) <= 500


class TestClassifyException:
    """Tests for classify_exception function."""

    def test_classifies_validation_error(self):
        """Test classifies ValidationError correctly."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            field: int

        try:
            TestModel(field="not-an-int")  # type: ignore
        except ValidationError as e:
            code = classify_exception(e)
            assert code == ErrorCode.VALIDATION_ERROR

    def test_classifies_timeout(self):
        """Test classifies timeout errors."""
        import httpx

        exc = httpx.TimeoutException("Timeout")
        code = classify_exception(exc)
        assert code == ErrorCode.TIMEOUT

    def test_classifies_connection_error(self):
        """Test classifies connection errors."""
        exc = ConnectionError("Connection refused")
        code = classify_exception(exc)
        assert code == ErrorCode.SERVICE_UNAVAILABLE

    def test_classifies_unknown_as_internal(self):
        """Test classifies unknown exceptions as internal error."""
        exc = RuntimeError("Something unexpected")
        code = classify_exception(exc)
        assert code == ErrorCode.INTERNAL_ERROR


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_serialization(self):
        """Test error response serializes correctly."""
        response = ErrorResponse(
            detail="Test error",
            code=ErrorCode.AUTH_INVALID,
            request_id="req-456",
        )
        data = response.model_dump()
        assert data["detail"] == "Test error"
        assert data["code"] == "AUTH_INVALID"
        assert data["request_id"] == "req-456"

    def test_optional_fields(self):
        """Test optional fields can be None."""
        response = ErrorResponse(detail="Test error")
        assert response.code is None
        assert response.request_id is None
