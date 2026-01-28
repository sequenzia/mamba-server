"""Tests for SSE event data models (AI SDK UIMessageChunk format)."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from mamba.models.events import (
    ErrorEvent,
    FinishEvent,
    FinishStepEvent,
    StartEvent,
    StartStepEvent,
    StreamEvent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
)


class TestStartEvent:
    """Tests for StartEvent model."""

    def test_valid_event(self):
        """Test valid start event."""
        event = StartEvent(messageId="msg-123")
        assert event.type == "start"
        assert event.messageId == "msg-123"

    def test_optional_message_id(self):
        """Test messageId is optional."""
        event = StartEvent()
        assert event.type == "start"
        assert event.messageId is None

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = StartEvent(messageId="msg-123")
        data = event.model_dump()
        assert data == {"type": "start", "messageId": "msg-123"}


class TestStartStepEvent:
    """Tests for StartStepEvent model."""

    def test_valid_event(self):
        """Test valid start-step event."""
        event = StartStepEvent()
        assert event.type == "start-step"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = StartStepEvent()
        data = event.model_dump()
        assert data == {"type": "start-step"}


class TestTextStartEvent:
    """Tests for TextStartEvent model."""

    def test_valid_event(self):
        """Test valid text-start event."""
        event = TextStartEvent(id="text-1")
        assert event.type == "text-start"
        assert event.id == "text-1"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = TextStartEvent(id="text-1")
        data = event.model_dump()
        assert data == {"type": "text-start", "id": "text-1"}


class TestTextDeltaEvent:
    """Tests for TextDeltaEvent model."""

    def test_valid_event(self):
        """Test valid text delta event."""
        event = TextDeltaEvent(id="text-1", delta="Hello")
        assert event.type == "text-delta"
        assert event.id == "text-1"
        assert event.delta == "Hello"

    def test_empty_delta_is_valid(self):
        """Test empty delta is valid."""
        event = TextDeltaEvent(id="text-1", delta="")
        assert event.delta == ""

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = TextDeltaEvent(id="text-1", delta="Hello")
        data = event.model_dump()
        assert data == {"type": "text-delta", "id": "text-1", "delta": "Hello"}

    def test_json_serialization(self):
        """Test JSON string serialization."""
        event = TextDeltaEvent(id="text-1", delta="Hello")
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed == {"type": "text-delta", "id": "text-1", "delta": "Hello"}


class TestTextEndEvent:
    """Tests for TextEndEvent model."""

    def test_valid_event(self):
        """Test valid text-end event."""
        event = TextEndEvent(id="text-1")
        assert event.type == "text-end"
        assert event.id == "text-1"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = TextEndEvent(id="text-1")
        data = event.model_dump()
        assert data == {"type": "text-end", "id": "text-1"}


class TestToolInputAvailableEvent:
    """Tests for ToolInputAvailableEvent model."""

    def test_valid_event(self):
        """Test valid tool-input-available event."""
        event = ToolInputAvailableEvent(
            toolCallId="tc_abc123xyz",
            toolName="generateForm",
            input={"title": "Contact Us", "fields": []},
        )
        assert event.type == "tool-input-available"
        assert event.toolCallId == "tc_abc123xyz"
        assert event.toolName == "generateForm"
        assert event.input["title"] == "Contact Us"

    def test_empty_input_is_valid(self):
        """Test empty input dict is valid."""
        event = ToolInputAvailableEvent(
            toolCallId="tc_123",
            toolName="testTool",
            input={},
        )
        assert event.input == {}

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = ToolInputAvailableEvent(
            toolCallId="tc_123",
            toolName="generateForm",
            input={"type": "form", "title": "Test"},
        )
        data = event.model_dump()
        assert data == {
            "type": "tool-input-available",
            "toolCallId": "tc_123",
            "toolName": "generateForm",
            "input": {"type": "form", "title": "Test"},
        }


class TestToolOutputAvailableEvent:
    """Tests for ToolOutputAvailableEvent model."""

    def test_valid_event(self):
        """Test valid tool-output-available event."""
        event = ToolOutputAvailableEvent(
            toolCallId="tc_abc123xyz",
            output={"type": "form", "title": "Contact Us"},
        )
        assert event.type == "tool-output-available"
        assert event.toolCallId == "tc_abc123xyz"
        assert event.output["type"] == "form"

    def test_empty_output_is_valid(self):
        """Test empty output dict is valid."""
        event = ToolOutputAvailableEvent(
            toolCallId="tc_123",
            output={},
        )
        assert event.output == {}

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = ToolOutputAvailableEvent(
            toolCallId="tc_123",
            output={"status": "success"},
        )
        data = event.model_dump()
        assert data == {
            "type": "tool-output-available",
            "toolCallId": "tc_123",
            "output": {"status": "success"},
        }


class TestFinishStepEvent:
    """Tests for FinishStepEvent model."""

    def test_valid_event(self):
        """Test valid finish-step event."""
        event = FinishStepEvent()
        assert event.type == "finish-step"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = FinishStepEvent()
        data = event.model_dump()
        assert data == {"type": "finish-step"}


class TestFinishEvent:
    """Tests for FinishEvent model."""

    def test_valid_event(self):
        """Test valid finish event."""
        event = FinishEvent()
        assert event.type == "finish"
        assert event.finishReason is None

    def test_finish_with_reason(self):
        """Test finish event with reason."""
        event = FinishEvent(finishReason="stop")
        assert event.finishReason == "stop"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = FinishEvent(finishReason="stop")
        data = event.model_dump()
        assert data == {"type": "finish", "finishReason": "stop"}


class TestErrorEvent:
    """Tests for ErrorEvent model."""

    def test_valid_event(self):
        """Test valid error event."""
        event = ErrorEvent(errorText="Model rate limit exceeded")
        assert event.type == "error"
        assert event.errorText == "Model rate limit exceeded"

    def test_serialization_matches_spec(self):
        """Test JSON serialization matches AI SDK spec."""
        event = ErrorEvent(errorText="Service temporarily unavailable")
        data = event.model_dump()
        assert data == {
            "type": "error",
            "errorText": "Service temporarily unavailable",
        }


class TestStreamEventUnion:
    """Tests for StreamEvent union type."""

    def test_parse_start(self):
        """Test parsing start event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "start", "messageId": "msg-123"}
        event = adapter.validate_python(data)
        assert isinstance(event, StartEvent)

    def test_parse_start_step(self):
        """Test parsing start-step event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "start-step"}
        event = adapter.validate_python(data)
        assert isinstance(event, StartStepEvent)

    def test_parse_text_start(self):
        """Test parsing text-start event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "text-start", "id": "text-1"}
        event = adapter.validate_python(data)
        assert isinstance(event, TextStartEvent)

    def test_parse_text_delta(self):
        """Test parsing text-delta event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "text-delta", "id": "text-1", "delta": "Hello"}
        event = adapter.validate_python(data)
        assert isinstance(event, TextDeltaEvent)

    def test_parse_text_end(self):
        """Test parsing text-end event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "text-end", "id": "text-1"}
        event = adapter.validate_python(data)
        assert isinstance(event, TextEndEvent)

    def test_parse_tool_input_available(self):
        """Test parsing tool-input-available event."""
        adapter = TypeAdapter(StreamEvent)
        data = {
            "type": "tool-input-available",
            "toolCallId": "tc_123",
            "toolName": "test",
            "input": {},
        }
        event = adapter.validate_python(data)
        assert isinstance(event, ToolInputAvailableEvent)

    def test_parse_tool_output_available(self):
        """Test parsing tool-output-available event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "tool-output-available", "toolCallId": "tc_123", "output": {}}
        event = adapter.validate_python(data)
        assert isinstance(event, ToolOutputAvailableEvent)

    def test_parse_finish_step(self):
        """Test parsing finish-step event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "finish-step"}
        event = adapter.validate_python(data)
        assert isinstance(event, FinishStepEvent)

    def test_parse_finish(self):
        """Test parsing finish event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "finish", "finishReason": "stop"}
        event = adapter.validate_python(data)
        assert isinstance(event, FinishEvent)

    def test_parse_error(self):
        """Test parsing error event."""
        adapter = TypeAdapter(StreamEvent)
        data = {"type": "error", "errorText": "Test error"}
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
        # Missing id and delta for text-delta event
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "text-delta"})


class TestEventCreationValidation:
    """Tests for event creation validation."""

    def test_text_delta_requires_id_and_delta(self):
        """Test TextDeltaEvent requires id and delta fields."""
        with pytest.raises(ValidationError):
            TextDeltaEvent()  # type: ignore

    def test_tool_input_available_requires_all_fields(self):
        """Test ToolInputAvailableEvent requires all fields."""
        with pytest.raises(ValidationError):
            ToolInputAvailableEvent(toolCallId="tc_123")  # type: ignore

    def test_error_event_requires_error_text(self):
        """Test ErrorEvent requires errorText field."""
        with pytest.raises(ValidationError):
            ErrorEvent()  # type: ignore

    def test_text_start_requires_id(self):
        """Test TextStartEvent requires id field."""
        with pytest.raises(ValidationError):
            TextStartEvent()  # type: ignore

    def test_text_end_requires_id(self):
        """Test TextEndEvent requires id field."""
        with pytest.raises(ValidationError):
            TextEndEvent()  # type: ignore
