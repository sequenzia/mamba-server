"""Tests for chat request data models."""

import pytest
from pydantic import ValidationError

from mamba.models.request import (
    ChatCompletionRequest,
    MessagePart,
    TextPart,
    ToolInvocationPart,
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
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-4-turbo",
            "openai/o1-preview",
            "openai/o1-mini",
        ]
        for model in valid_models:
            request = ChatCompletionRequest(messages=[], model=model)
            assert request.model == model

    def test_invalid_model_format_rejected(self):
        """Test invalid model format raises error."""
        invalid_models = [
            "gpt-4o",  # Missing prefix
            "anthropic/claude-3",  # Wrong provider
            "openai/",  # Missing model name
            "openai",  # No slash
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

    def test_invalid_part_type_rejected(self):
        """Test invalid part type raises error."""
        data = {"type": "invalid", "content": "test"}
        with pytest.raises(ValidationError):
            UIMessage(id="1", role="user", parts=[data])  # type: ignore
