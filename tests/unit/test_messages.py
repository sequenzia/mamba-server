"""Tests for message format conversion."""

import json

import pytest

from mamba.core.messages import (
    convert_messages,
    convert_text_part,
    convert_tool_invocation_part,
    convert_tool_result_to_message,
    convert_ui_message,
    extract_text_content,
    extract_tool_calls,
    extract_tool_results,
)
from mamba.models.request import TextPart, ToolInvocationPart, UIMessage


class TestConvertTextPart:
    """Tests for convert_text_part function."""

    def test_converts_text(self):
        """Test text part conversion."""
        part = TextPart(type="text", text="Hello, world!")
        result = convert_text_part(part)
        assert result == "Hello, world!"

    def test_empty_text(self):
        """Test empty text part conversion."""
        part = TextPart(type="text", text="")
        result = convert_text_part(part)
        assert result == ""


class TestConvertToolInvocationPart:
    """Tests for convert_tool_invocation_part function."""

    def test_converts_tool_call(self):
        """Test tool invocation conversion."""
        part = ToolInvocationPart(
            type="tool-invocation",
            toolCallId="call_123",
            toolName="generateForm",
            args={"title": "Contact"},
        )
        result = convert_tool_invocation_part(part)

        assert result["id"] == "call_123"
        assert result["type"] == "function"
        assert result["function"]["name"] == "generateForm"
        # Arguments should be JSON string
        assert json.loads(result["function"]["arguments"]) == {"title": "Contact"}


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_single_text_part(self):
        """Test extraction from single text part."""
        parts = [TextPart(type="text", text="Hello")]
        result = extract_text_content(parts)
        assert result == "Hello"

    def test_multiple_text_parts(self):
        """Test extraction from multiple text parts."""
        parts = [
            TextPart(type="text", text="Hello"),
            TextPart(type="text", text="world"),
        ]
        result = extract_text_content(parts)
        assert result == "Hello world"

    def test_empty_parts_list(self):
        """Test extraction from empty parts list."""
        parts = []
        result = extract_text_content(parts)
        assert result == ""

    def test_mixed_parts(self):
        """Test extraction ignores non-text parts."""
        parts = [
            TextPart(type="text", text="Hello"),
            ToolInvocationPart(
                type="tool-invocation",
                toolCallId="call_1",
                toolName="test",
                args={},
            ),
            TextPart(type="text", text="world"),
        ]
        result = extract_text_content(parts)
        assert result == "Hello world"


class TestExtractToolCalls:
    """Tests for extract_tool_calls function."""

    def test_extracts_tool_calls(self):
        """Test extraction of tool calls without results."""
        parts = [
            ToolInvocationPart(
                type="tool-invocation",
                toolCallId="call_1",
                toolName="generateForm",
                args={"title": "Test"},
            ),
        ]
        result = extract_tool_calls(parts)
        assert len(result) == 1
        assert result[0]["id"] == "call_1"

    def test_ignores_tool_calls_with_results(self):
        """Test that tool calls with results are ignored."""
        parts = [
            ToolInvocationPart(
                type="tool-invocation",
                toolCallId="call_1",
                toolName="generateForm",
                args={"title": "Test"},
                result={"status": "completed"},
            ),
        ]
        result = extract_tool_calls(parts)
        assert len(result) == 0


class TestExtractToolResults:
    """Tests for extract_tool_results function."""

    def test_extracts_tool_results(self):
        """Test extraction of tool results."""
        parts = [
            ToolInvocationPart(
                type="tool-invocation",
                toolCallId="call_1",
                toolName="generateForm",
                args={"title": "Test"},
                result={"status": "Form generated"},
            ),
        ]
        result = extract_tool_results(parts)
        assert len(result) == 1
        assert result[0]["tool_call_id"] == "call_1"
        # Result should be JSON string
        assert json.loads(result[0]["result"]) == {"status": "Form generated"}

    def test_ignores_tool_calls_without_results(self):
        """Test that tool calls without results are ignored."""
        parts = [
            ToolInvocationPart(
                type="tool-invocation",
                toolCallId="call_1",
                toolName="generateForm",
                args={"title": "Test"},
            ),
        ]
        result = extract_tool_results(parts)
        assert len(result) == 0


class TestConvertUiMessage:
    """Tests for convert_ui_message function."""

    def test_user_message(self):
        """Test user message conversion."""
        message = UIMessage(
            id="msg_1",
            role="user",
            parts=[TextPart(type="text", text="Hello")],
        )
        result = convert_ui_message(message)

        assert result["role"] == "user"
        assert result["content"] == "Hello"

    def test_system_message(self):
        """Test system message conversion."""
        message = UIMessage(
            id="msg_1",
            role="system",
            parts=[TextPart(type="text", text="You are a helpful assistant.")],
        )
        result = convert_ui_message(message)

        assert result["role"] == "system"
        assert result["content"] == "You are a helpful assistant."

    def test_assistant_message_with_text(self):
        """Test assistant message with text content."""
        message = UIMessage(
            id="msg_1",
            role="assistant",
            parts=[TextPart(type="text", text="I can help with that.")],
        )
        result = convert_ui_message(message)

        assert result["role"] == "assistant"
        assert result["content"] == "I can help with that."

    def test_assistant_message_with_tool_call(self):
        """Test assistant message with tool call."""
        message = UIMessage(
            id="msg_1",
            role="assistant",
            parts=[
                ToolInvocationPart(
                    type="tool-invocation",
                    toolCallId="call_1",
                    toolName="generateForm",
                    args={"title": "Test"},
                ),
            ],
        )
        result = convert_ui_message(message)

        assert result["role"] == "assistant"
        assert "tool_calls" in result
        assert len(result["tool_calls"]) == 1

    def test_assistant_message_empty_parts(self):
        """Test assistant message with empty parts."""
        message = UIMessage(
            id="msg_1",
            role="assistant",
            parts=[],
        )
        result = convert_ui_message(message)

        assert result["role"] == "assistant"
        assert result["content"] == ""

    def test_invalid_role_raises(self):
        """Test invalid role raises ValueError."""
        # Create a message with an invalid role by bypassing validation
        message = UIMessage.model_construct(
            id="msg_1",
            role="invalid",
            parts=[],
        )

        with pytest.raises(ValueError, match="Invalid message role"):
            convert_ui_message(message)


class TestConvertToolResultToMessage:
    """Tests for convert_tool_result_to_message function."""

    def test_creates_tool_message(self):
        """Test tool result message creation."""
        result = convert_tool_result_to_message("call_123", "Form submitted successfully")

        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_123"
        assert result["content"] == "Form submitted successfully"


class TestConvertMessages:
    """Tests for convert_messages function."""

    def test_simple_conversation(self):
        """Test simple user-assistant conversation."""
        messages = [
            UIMessage(
                id="msg_1",
                role="user",
                parts=[TextPart(type="text", text="Hello")],
            ),
            UIMessage(
                id="msg_2",
                role="assistant",
                parts=[TextPart(type="text", text="Hi there!")],
            ),
        ]
        result = convert_messages(messages)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_conversation_with_system_message(self):
        """Test conversation with system message."""
        messages = [
            UIMessage(
                id="msg_1",
                role="system",
                parts=[TextPart(type="text", text="Be helpful")],
            ),
            UIMessage(
                id="msg_2",
                role="user",
                parts=[TextPart(type="text", text="Hello")],
            ),
        ]
        result = convert_messages(messages)

        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"

    def test_empty_messages_list(self):
        """Test empty messages list."""
        result = convert_messages([])
        assert result == []

    def test_tool_results_in_conversation(self):
        """Test tool results are added as separate messages."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[
                    ToolInvocationPart(
                        type="tool-invocation",
                        toolCallId="call_1",
                        toolName="generateForm",
                        args={"title": "Test"},
                        result={"status": "Form generated"},
                    ),
                ],
            ),
        ]
        result = convert_messages(messages)

        # Should have assistant message + tool result message
        assert len(result) == 2
        assert result[0]["role"] == "assistant"
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "call_1"
