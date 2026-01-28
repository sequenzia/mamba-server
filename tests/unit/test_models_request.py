"""Tests for chat request data models."""

import pytest
from pydantic import ValidationError

from mamba.models.request import (
    ChatCompletionRequest,
    MessagePart,
    TextPart,
    ToolCallPart,
    ToolInvocationPart,
    ToolResultPart,
    UIMessage,
)


class TestTextPart:
    """Tests for TextPart model."""

    def test_valid_text_part(self):
        """Test valid text part creation."""
        part = TextPart(text="Hello, world!")
        assert part.type == "text"
        assert part.text == "Hello, world!"

    def test_empty_text_is_valid(self):
        """Test empty text is valid."""
        part = TextPart(text="")
        assert part.text == ""

    def test_serialization(self):
        """Test JSON serialization."""
        part = TextPart(text="Hello")
        data = part.model_dump()
        assert data == {"type": "text", "text": "Hello"}


class TestToolInvocationPart:
    """Tests for ToolInvocationPart model."""

    def test_valid_tool_invocation(self):
        """Test valid tool invocation creation."""
        part = ToolInvocationPart(
            toolCallId="tc_abc123",
            toolName="generateForm",
            args={"title": "Contact Us"},
        )
        assert part.type == "tool-invocation"
        assert part.toolCallId == "tc_abc123"
        assert part.toolName == "generateForm"
        assert part.args == {"title": "Contact Us"}
        assert part.result is None

    def test_tool_invocation_with_result(self):
        """Test tool invocation with result."""
        part = ToolInvocationPart(
            toolCallId="tc_abc123",
            toolName="generateForm",
            args={"title": "Form"},
            result={"status": "success"},
        )
        assert part.result == {"status": "success"}

    def test_empty_args_is_valid(self):
        """Test empty args dict is valid."""
        part = ToolInvocationPart(
            toolCallId="tc_123",
            toolName="tool",
            args={},
        )
        assert part.args == {}

    def test_serialization(self):
        """Test JSON serialization."""
        part = ToolInvocationPart(
            toolCallId="tc_123",
            toolName="generateForm",
            args={"title": "Test"},
        )
        data = part.model_dump()
        assert data == {
            "type": "tool-invocation",
            "toolCallId": "tc_123",
            "toolName": "generateForm",
            "args": {"title": "Test"},
            "result": None,
        }


class TestToolCallPart:
    """Tests for ToolCallPart model (AI SDK format)."""

    def test_valid_tool_call(self):
        """Test valid tool call creation."""
        part = ToolCallPart(
            toolCallId="tc_abc123",
            toolName="generateForm",
            args={"title": "Contact Us"},
        )
        assert part.type == "tool-call"
        assert part.toolCallId == "tc_abc123"
        assert part.toolName == "generateForm"
        assert part.args == {"title": "Contact Us"}

    def test_tool_call_without_args(self):
        """Test tool call with optional args."""
        part = ToolCallPart(
            toolCallId="tc_123",
            toolName="noArgs",
        )
        assert part.args is None

    def test_serialization(self):
        """Test JSON serialization."""
        part = ToolCallPart(
            toolCallId="tc_123",
            toolName="generateForm",
            args={"title": "Test"},
        )
        data = part.model_dump()
        assert data == {
            "type": "tool-call",
            "toolCallId": "tc_123",
            "toolName": "generateForm",
            "args": {"title": "Test"},
        }


class TestToolResultPart:
    """Tests for ToolResultPart model (AI SDK format)."""

    def test_valid_tool_result(self):
        """Test valid tool result creation."""
        part = ToolResultPart(
            toolCallId="tc_abc123",
            result={"status": "success"},
        )
        assert part.type == "tool-result"
        assert part.toolCallId == "tc_abc123"
        assert part.result == {"status": "success"}

    def test_tool_result_with_string(self):
        """Test tool result with string value."""
        part = ToolResultPart(
            toolCallId="tc_123",
            result="Operation completed",
        )
        assert part.result == "Operation completed"

    def test_tool_result_with_list(self):
        """Test tool result with list value."""
        part = ToolResultPart(
            toolCallId="tc_123",
            result=[1, 2, 3],
        )
        assert part.result == [1, 2, 3]

    def test_serialization(self):
        """Test JSON serialization."""
        part = ToolResultPart(
            toolCallId="tc_123",
            result={"data": "value"},
        )
        data = part.model_dump()
        assert data == {
            "type": "tool-result",
            "toolCallId": "tc_123",
            "result": {"data": "value"},
        }


class TestUIMessage:
    """Tests for UIMessage model."""

    def test_user_message(self):
        """Test user message creation."""
        msg = UIMessage(
            id="msg_123",
            role="user",
            parts=[TextPart(text="Hello")],
        )
        assert msg.id == "msg_123"
        assert msg.role == "user"
        assert len(msg.parts) == 1

    def test_assistant_message(self):
        """Test assistant message with multiple parts."""
        msg = UIMessage(
            id="msg_456",
            role="assistant",
            parts=[
                TextPart(text="I'll create a form."),
                ToolInvocationPart(
                    toolCallId="tc_789",
                    toolName="generateForm",
                    args={"title": "Contact"},
                ),
            ],
        )
        assert msg.role == "assistant"
        assert len(msg.parts) == 2

    def test_system_message(self):
        """Test system message."""
        msg = UIMessage(
            id="msg_sys",
            role="system",
            parts=[TextPart(text="You are a helpful assistant.")],
        )
        assert msg.role == "system"

    def test_empty_parts_is_valid(self):
        """Test empty parts list is valid."""
        msg = UIMessage(id="msg_empty", role="user", parts=[])
        assert msg.parts == []

    def test_invalid_role_rejected(self):
        """Test invalid role raises error."""
        with pytest.raises(ValidationError):
            UIMessage(
                id="msg_123",
                role="invalid",  # type: ignore
                parts=[],
            )

    def test_all_valid_roles(self):
        """Test all valid role values."""
        for role in ["user", "assistant", "system"]:
            msg = UIMessage(id="msg", role=role, parts=[])  # type: ignore
            assert msg.role == role


class TestChatCompletionRequest:
    """Tests for ChatCompletionRequest model."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = ChatCompletionRequest(
            messages=[
                UIMessage(
                    id="msg_1",
                    role="user",
                    parts=[TextPart(text="Hello")],
                )
            ],
            model="openai/gpt-4o",
        )
        assert len(request.messages) == 1
        assert request.model == "openai/gpt-4o"

    def test_valid_model_formats(self):
        """Test valid model format patterns."""
        valid_models = [
            # With openai/ prefix (legacy format)
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/o1-preview",
            "openai/o1-mini",
            # Without prefix (AI SDK format)
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-5",
            "o1-preview",
        ]
        for model in valid_models:
            request = ChatCompletionRequest(messages=[], model=model)
            assert request.model == model

    def test_invalid_model_format_rejected(self):
        """Test invalid model format raises error."""
        invalid_models = [
            "",  # Empty string
        ]
        for model in invalid_models:
            with pytest.raises(ValidationError, match="model"):
                ChatCompletionRequest(messages=[], model=model)

    def test_empty_messages_is_valid(self):
        """Test empty messages list is valid (server may reject later)."""
        request = ChatCompletionRequest(messages=[], model="openai/gpt-4o")
        assert request.messages == []

    def test_serialization(self):
        """Test JSON serialization."""
        request = ChatCompletionRequest(
            messages=[
                UIMessage(
                    id="msg_1",
                    role="user",
                    parts=[TextPart(text="Hi")],
                )
            ],
            model="openai/gpt-4o",
        )
        data = request.model_dump()
        assert data["model"] == "openai/gpt-4o"
        assert data["messages"][0]["role"] == "user"


class TestMessagePartDiscrimination:
    """Tests for MessagePart discriminated union."""

    def test_parse_text_part(self):
        """Test parsing text part from dict."""
        data = {"type": "text", "text": "Hello"}
        msg = UIMessage(id="1", role="user", parts=[data])  # type: ignore
        assert isinstance(msg.parts[0], TextPart)

    def test_parse_tool_invocation_part(self):
        """Test parsing tool invocation part from dict."""
        data = {
            "type": "tool-invocation",
            "toolCallId": "tc_1",
            "toolName": "test",
            "args": {},
        }
        msg = UIMessage(id="1", role="assistant", parts=[data])  # type: ignore
        assert isinstance(msg.parts[0], ToolInvocationPart)

    def test_invalid_part_type_filtered(self):
        """Test invalid part types are filtered (not rejected)."""
        data = {"type": "invalid", "content": "test"}
        msg = UIMessage(id="1", role="user", parts=[data])  # type: ignore
        assert msg.parts == []  # Filtered out, not error

    def test_parse_tool_call_part(self):
        """Test parsing tool-call part from dict (AI SDK format)."""
        data = {
            "type": "tool-call",
            "toolCallId": "tc_1",
            "toolName": "test",
            "args": {"key": "value"},
        }
        msg = UIMessage(id="1", role="assistant", parts=[data])  # type: ignore
        assert isinstance(msg.parts[0], ToolCallPart)

    def test_parse_tool_result_part(self):
        """Test parsing tool-result part from dict (AI SDK format)."""
        data = {
            "type": "tool-result",
            "toolCallId": "tc_1",
            "result": {"data": "value"},
        }
        msg = UIMessage(id="1", role="assistant", parts=[data])  # type: ignore
        assert isinstance(msg.parts[0], ToolResultPart)

    def test_mixed_ai_sdk_and_legacy_parts(self):
        """Test message with mixed part types (AI SDK and legacy)."""
        parts = [
            {"type": "text", "text": "Here's the form"},
            {"type": "tool-call", "toolCallId": "tc_1", "toolName": "generateForm", "args": {}},
            {"type": "tool-result", "toolCallId": "tc_1", "result": {"rendered": True}},
            {"type": "tool-invocation", "toolCallId": "tc_2", "toolName": "legacyTool", "args": {}},
        ]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert isinstance(msg.parts[0], TextPart)
        assert isinstance(msg.parts[1], ToolCallPart)
        assert isinstance(msg.parts[2], ToolResultPart)
        assert isinstance(msg.parts[3], ToolInvocationPart)


class TestMessagePartFiltering:
    """Tests for message part filtering (lifecycle parts removed)."""

    def test_step_start_filtered(self):
        """Test step-start lifecycle part is filtered out."""
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "Hello"},
        ]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert len(msg.parts) == 1
        assert isinstance(msg.parts[0], TextPart)

    def test_unknown_parts_filtered(self):
        """Test unknown part types are filtered out."""
        parts = [
            {"type": "reasoning", "text": "thinking..."},
            {"type": "source-url", "url": "http://example.com"},
            {"type": "text", "text": "Response"},
        ]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert len(msg.parts) == 1
        assert msg.parts[0].text == "Response"

    def test_all_content_types_preserved(self):
        """Test all valid content types are preserved."""
        parts = [
            {"type": "text", "text": "Hello"},
            {"type": "tool-call", "toolCallId": "tc_1", "toolName": "test", "args": {}},
            {"type": "tool-result", "toolCallId": "tc_1", "result": "done"},
            {"type": "tool-invocation", "toolCallId": "tc_2", "toolName": "legacy", "args": {}},
        ]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert len(msg.parts) == 4

    def test_empty_after_filtering(self):
        """Test message with only lifecycle parts results in empty parts."""
        parts = [{"type": "step-start"}, {"type": "finish"}]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert msg.parts == []

    def test_mixed_parts_in_real_scenario(self):
        """Test realistic AI SDK message with mixed parts."""
        parts = [
            {"type": "step-start"},
            {"type": "text", "text": "I'll help you with that."},
            {"type": "tool-call", "toolCallId": "tc_1", "toolName": "generateForm", "args": {"title": "Form"}},
            {"type": "tool-result", "toolCallId": "tc_1", "result": {"rendered": True}},
        ]
        msg = UIMessage(id="1", role="assistant", parts=parts)  # type: ignore
        assert len(msg.parts) == 3
        assert isinstance(msg.parts[0], TextPart)
        assert isinstance(msg.parts[1], ToolCallPart)
        assert isinstance(msg.parts[2], ToolResultPart)
