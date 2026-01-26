"""Tests for SSE event data models."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from mamba.models.events import (
    ErrorEvent,
    FinishEvent,
    StreamEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)


class TestTextDeltaEvent:
    """Tests for TextDeltaEvent model."""

    def test_valid_event(self):
        """Test valid text delta event."""
        event = TextDeltaEvent(textDelta="Hello")
        assert event.type == "text-delta"
        assert event.textDelta == "Hello"

    def test_empty_text_delta_is_valid(self):
        """Test empty textDelta is valid."""
        event = TextDeltaEvent(textDelta="")
        assert event.textDelta == ""

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches protocol spec."""
        event = TextDeltaEvent(textDelta="Hello")
        data = event.model_dump()
        assert data == {"type": "text-delta", "textDelta": "Hello"}

    def test_json_serialization(self):
        """Test JSON string serialization."""
        event = TextDeltaEvent(textDelta="Hello")
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed == {"type": "text-delta", "textDelta": "Hello"}


class TestToolCallEvent:
    """Tests for ToolCallEvent model."""

    def test_valid_event(self):
        """Test valid tool call event."""
        event = ToolCallEvent(
            toolCallId="tc_abc123xyz",
            toolName="generateForm",
            args={"title": "Contact Us", "fields": []},
        )
        assert event.type == "tool-call"
        assert event.toolCallId == "tc_abc123xyz"
        assert event.toolName == "generateForm"
        assert event.args["title"] == "Contact Us"

    def test_empty_args_is_valid(self):
        """Test empty args dict is valid."""
        event = ToolCallEvent(
            toolCallId="tc_123",
            toolName="testTool",
            args={},
        )
        assert event.args == {}

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches protocol spec."""
        event = ToolCallEvent(
            toolCallId="tc_123",
            toolName="generateForm",
            args={"type": "form", "title": "Test"},
        )
        data = event.model_dump()
        assert data == {
            "type": "tool-call",
            "toolCallId": "tc_123",
            "toolName": "generateForm",
            "args": {"type": "form", "title": "Test"},
        }


class TestToolResultEvent:
    """Tests for ToolResultEvent model."""

    def test_valid_event(self):
        """Test valid tool result event."""
        event = ToolResultEvent(
            toolCallId="tc_abc123xyz",
            result={"type": "form", "title": "Contact Us"},
        )
        assert event.type == "tool-result"
        assert event.toolCallId == "tc_abc123xyz"
        assert event.result["type"] == "form"

    def test_empty_result_is_valid(self):
        """Test empty result dict is valid."""
        event = ToolResultEvent(
            toolCallId="tc_123",
            result={},
        )
        assert event.result == {}

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches protocol spec."""
        event = ToolResultEvent(
            toolCallId="tc_123",
            result={"status": "success"},
        )
        data = event.model_dump()
        assert data == {
            "type": "tool-result",
            "toolCallId": "tc_123",
            "result": {"status": "success"},
        }


class TestFinishEvent:
    """Tests for FinishEvent model."""

    def test_valid_event(self):
        """Test valid finish event."""
        event = FinishEvent()
        assert event.type == "finish"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches protocol spec."""
        event = FinishEvent()
        data = event.model_dump()
        assert data == {"type": "finish"}


class TestErrorEvent:
    """Tests for ErrorEvent model."""

    def test_valid_event(self):
        """Test valid error event."""
        event = ErrorEvent(error="Model rate limit exceeded")
        assert event.type == "error"
        assert event.error == "Model rate limit exceeded"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches protocol spec."""
        event = ErrorEvent(error="Service temporarily unavailable")
        data = event.model_dump()
        assert data == {
            "type": "error",
            "error": "Service temporarily unavailable",
        }


class TestStreamEventUnion:
    """Tests for StreamEvent union type."""

    def test_parse_text_delta(self):
        """Test parsing text-delta event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "text-delta", "textDelta": "Hello"}
        event = adapter.validate_python(data)
        assert isinstance(event, TextDeltaEvent)

    def test_parse_tool_call(self):
        """Test parsing tool-call event."""
        adapter = TypeAdapter(StreamEvent)
        data = {
            "type": "tool-call",
            "toolCallId": "tc_123",
            "toolName": "test",
            "args": {},
        }
        event = adapter.validate_python(data)
        assert isinstance(event, ToolCallEvent)

    def test_parse_tool_result(self):
        """Test parsing tool-result event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "tool-result", "toolCallId": "tc_123", "result": {}}
        event = adapter.validate_python(data)
        assert isinstance(event, ToolResultEvent)

    def test_parse_finish(self):
        """Test parsing finish event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "finish"}
        event = adapter.validate_python(data)
        assert isinstance(event, FinishEvent)

    def test_parse_error(self):
        """Test parsing error event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "error", "error": "Test error"}
        event = adapter.validate_python(data)
        assert isinstance(event, ErrorEvent)

    def test_invalid_type_rejected(self):
        """Test invalid event type raises error."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "invalid", "data": "test"}
        with pytest.raises(ValidationError):
            adapter.validate_python(data)

    def test_missing_required_fields_rejected(self):
        """Test missing required fields raises error."""
        adapter = TypeAdapter(StreamEvent)
        # Missing textDelta for text-delta event
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "text-delta"})


class TestEventCreationValidation:
    """Tests for event creation validation."""

    def test_text_delta_requires_text_delta(self):
        """Test TextDeltaEvent requires textDelta field."""
        with pytest.raises(ValidationError):
            TextDeltaEvent()  # type: ignore

    def test_tool_call_requires_all_fields(self):
        """Test ToolCallEvent requires all fields."""
        with pytest.raises(ValidationError):
            ToolCallEvent(toolCallId="tc_123")  # type: ignore

    def test_error_event_requires_error(self):
        """Test ErrorEvent requires error field."""
        with pytest.raises(ValidationError):
            ErrorEvent()  # type: ignore
