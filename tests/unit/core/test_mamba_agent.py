"""Tests for Mamba Agents framework integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mamba.core.mamba_agent import (
    _AGENT_REGISTRY,
    _extract_text,
    convert_ui_messages_to_dicts,
    get_agent,
    get_available_agents,
    register_agent,
    run_mamba_agent,
    stream_mamba_agent_events,
)
from mamba.models.events import ErrorEvent, TextDeltaEvent
from mamba.models.request import TextPart, ToolInvocationPart, UIMessage


class TestAgentRegistry:
    """Tests for agent registration and retrieval."""

    def test_get_available_agents_returns_registered(self):
        """Test that registered agents are returned."""
        agents = get_available_agents()
        assert "research" in agents
        assert "code_review" in agents

    def test_get_available_agents_returns_list(self):
        """Test that get_available_agents returns a list."""
        agents = get_available_agents()
        assert isinstance(agents, list)

    def test_register_agent_decorator(self):
        """Test registering a custom agent."""
        # Store original registry state
        original_keys = set(_AGENT_REGISTRY.keys())

        @register_agent("test_agent")
        def create_test_agent(settings, model_name):
            return MagicMock()

        try:
            assert "test_agent" in _AGENT_REGISTRY
            assert "test_agent" in get_available_agents()
        finally:
            # Clean up: remove test agent from registry
            if "test_agent" in _AGENT_REGISTRY:
                del _AGENT_REGISTRY["test_agent"]

    def test_get_agent_raises_for_unknown(self):
        """Test that unknown agent raises ValueError."""
        mock_settings = MagicMock()

        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent("nonexistent_agent", mock_settings, "gpt-4o")

    def test_get_agent_error_message_lists_available(self):
        """Test that error message includes available agents."""
        mock_settings = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            get_agent("nonexistent", mock_settings, "gpt-4o")

        error_message = str(exc_info.value)
        assert "research" in error_message
        assert "code_review" in error_message

    def test_get_agent_returns_agent(self):
        """Test that get_agent creates and returns a configured agent.

        This test verifies the integration works with real mamba_agents imports.
        """
        mock_settings = MagicMock()
        mock_settings.openai.base_url = "https://api.openai.com/v1"
        mock_settings.openai.api_key = "sk-test"
        mock_settings.openai.timeout_seconds = 60
        mock_settings.openai.max_retries = 3

        # Patch at a higher level - the mamba_agents imports inside factory functions
        with patch("mamba_agents.Agent") as mock_agent_cls, \
             patch("mamba_agents.AgentConfig"):
            mock_agent = MagicMock()
            mock_agent_cls.return_value = mock_agent

            result = get_agent("research", mock_settings, "gpt-4o")

            # Verify agent was created
            assert result is mock_agent
            mock_agent_cls.assert_called_once()


class TestMessageConversion:
    """Tests for UIMessage to dict conversion."""

    def test_converts_user_message(self):
        """Test user message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="user",
                parts=[TextPart(text="Hello")],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_converts_system_message(self):
        """Test system message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="system",
                parts=[TextPart(text="You are helpful")],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are helpful"

    def test_converts_assistant_message(self):
        """Test assistant message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[TextPart(text="Hello there!")],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hello there!"

    def test_converts_assistant_with_tool_call(self):
        """Test assistant message with tool call."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[
                    TextPart(text="Let me search"),
                    ToolInvocationPart(
                        toolCallId="call_1",
                        toolName="search",
                        args={"query": "test"},
                        result=None,
                    ),
                ],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Let me search"
        assert "tool_calls" in result[0]
        assert len(result[0]["tool_calls"]) == 1
        assert result[0]["tool_calls"][0]["function"]["name"] == "search"
        assert result[0]["tool_calls"][0]["id"] == "call_1"

    def test_converts_tool_result_to_separate_message(self):
        """Test that tool results become separate messages."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[
                    TextPart(text="Here is the result"),
                    ToolInvocationPart(
                        toolCallId="call_1",
                        toolName="search",
                        args={"query": "test"},
                        result={"results": ["item1", "item2"]},
                    ),
                ],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        # Should have assistant message + tool result message
        assert len(result) == 2
        assert result[0]["role"] == "assistant"
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "call_1"
        assert result[1]["name"] == "search"

    def test_converts_multiple_messages(self):
        """Test conversion of multiple messages."""
        messages = [
            UIMessage(
                id="msg_1",
                role="system",
                parts=[TextPart(text="You are helpful")],
            ),
            UIMessage(
                id="msg_2",
                role="user",
                parts=[TextPart(text="Hello")],
            ),
            UIMessage(
                id="msg_3",
                role="assistant",
                parts=[TextPart(text="Hi there!")],
            ),
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert len(result) == 3
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"

    def test_empty_messages_returns_empty_list(self):
        """Test empty input returns empty list."""
        result = convert_ui_messages_to_dicts([])
        assert result == []

    def test_multiple_text_parts_joined(self):
        """Test multiple text parts are joined with space."""
        messages = [
            UIMessage(
                id="msg_1",
                role="user",
                parts=[
                    TextPart(text="Hello"),
                    TextPart(text="World"),
                ],
            )
        ]

        result = convert_ui_messages_to_dicts(messages)

        assert result[0]["content"] == "Hello World"


class TestExtractText:
    """Tests for _extract_text helper."""

    def test_extracts_single_text_part(self):
        """Test extracting from single text part."""
        parts = [TextPart(text="Hello")]
        result = _extract_text(parts)
        assert result == "Hello"

    def test_extracts_multiple_text_parts(self):
        """Test extracting from multiple text parts."""
        parts = [TextPart(text="Hello"), TextPart(text="World")]
        result = _extract_text(parts)
        assert result == "Hello World"

    def test_ignores_tool_invocation_parts(self):
        """Test that tool invocation parts are ignored."""
        parts = [
            TextPart(text="Hello"),
            ToolInvocationPart(
                toolCallId="tc_1",
                toolName="test",
                args={},
            ),
        ]
        result = _extract_text(parts)
        assert result == "Hello"

    def test_empty_parts_returns_empty_string(self):
        """Test empty parts returns empty string."""
        result = _extract_text([])
        assert result == ""


class TestStreamingAdapter:
    """Tests for streaming event conversion."""

    @pytest.mark.asyncio
    async def test_yields_text_delta_events(self):
        """Test that PartDeltaEvent with TextPartDelta becomes TextDeltaEvent."""
        from mamba_agents import PartDeltaEvent, TextPartDelta

        # Create mock PartDeltaEvent objects with TextPartDelta
        mock_events = [
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=" world")),
        ]

        async def mock_run_stream_events(prompt, message_history=None):
            for event in mock_events:
                yield event

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test prompt"):
            events.append(event)

        # Should have 2 text delta events
        assert len(events) == 2
        assert all(isinstance(e, TextDeltaEvent) for e in events)
        assert events[0].id == "text-1"
        assert events[0].delta == "Hello"
        assert events[1].delta == " world"

    @pytest.mark.asyncio
    async def test_skips_empty_text_chunks(self):
        """Test that empty text chunks are not emitted."""
        from mamba_agents import PartDeltaEvent, TextPartDelta

        # Create mock events with one empty delta
        mock_events = [
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Hello")),
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="")),  # Empty
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="World")),
        ]

        async def mock_run_stream_events(prompt, message_history=None):
            for event in mock_events:
                yield event

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test"):
            events.append(event)

        # Should have only 2 events (empty skipped)
        assert len(events) == 2
        assert events[0].delta == "Hello"
        assert events[1].delta == "World"

    @pytest.mark.asyncio
    async def test_yields_error_event_on_exception(self):
        """Test that exceptions become ErrorEvent with sanitized message."""

        async def mock_run_stream_events(prompt, message_history=None):
            raise RuntimeError("Test error")
            yield  # Make it an async generator

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        # Error message is sanitized to user-friendly text, not raw exception
        assert events[0].errorText  # Just verify there's an error message

    @pytest.mark.asyncio
    async def test_passes_message_history(self):
        """Test that message history is converted and passed."""
        from mamba_agents import PartDeltaEvent, TextPartDelta

        received_history = None

        async def mock_run_stream_events(prompt, message_history=None):
            nonlocal received_history
            received_history = message_history
            yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Response"))

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        history = [{"role": "user", "content": "Previous message"}]

        # Mock the dicts_to_model_messages function at the mamba_agents module level
        with patch("mamba_agents.agent.message_utils.dicts_to_model_messages") as mock_convert:
            mock_convert.return_value = [MagicMock()]

            events = []
            async for event in stream_mamba_agent_events(mock_agent, "test", history):
                events.append(event)

            mock_convert.assert_called_once_with(history)

    @pytest.mark.asyncio
    async def test_yields_tool_input_event_on_function_call(self):
        """Test that FunctionToolCallEvent becomes ToolInputAvailableEvent."""
        from mamba_agents import FunctionToolCallEvent
        from mamba.models.events import ToolInputAvailableEvent
        from pydantic_ai.messages import ToolCallPart

        # Create a mock FunctionToolCallEvent
        mock_tool_call = ToolCallPart(
            tool_name="search_notes",
            args={"query": "test query"},
            tool_call_id="call_123",
        )
        mock_event = FunctionToolCallEvent(part=mock_tool_call)

        async def mock_run_stream_events(prompt, message_history=None):
            yield mock_event

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ToolInputAvailableEvent)
        assert events[0].toolCallId == "call_123"
        assert events[0].toolName == "search_notes"
        assert events[0].input == {"query": "test query"}

    @pytest.mark.asyncio
    async def test_yields_tool_output_event_on_function_result(self):
        """Test that FunctionToolResultEvent becomes ToolOutputAvailableEvent."""
        from mamba_agents import FunctionToolResultEvent
        from mamba.models.events import ToolOutputAvailableEvent
        from pydantic_ai.messages import ToolReturnPart

        # Create a mock FunctionToolResultEvent
        # tool_call_id is extracted from the result's ToolReturnPart
        mock_result = ToolReturnPart(
            tool_name="search_notes",
            content={"notes": ["note1", "note2"]},
            tool_call_id="call_123",
        )
        mock_event = FunctionToolResultEvent(result=mock_result)

        async def mock_run_stream_events(prompt, message_history=None):
            yield mock_event

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ToolOutputAvailableEvent)
        assert events[0].toolCallId == "call_123"
        assert events[0].output == {"notes": ["note1", "note2"]}

    @pytest.mark.asyncio
    async def test_interleaves_text_and_tool_events(self):
        """Test proper interleaving: text -> tool_input -> tool_output -> text."""
        from mamba_agents import (
            FunctionToolCallEvent,
            FunctionToolResultEvent,
            PartDeltaEvent,
            TextPartDelta,
        )
        from mamba.models.events import ToolInputAvailableEvent, ToolOutputAvailableEvent
        from pydantic_ai.messages import ToolCallPart, ToolReturnPart

        mock_tool_call = ToolCallPart(
            tool_name="calculator",
            args={"expression": "2+2"},
            tool_call_id="call_456",
        )
        mock_tool_result = ToolReturnPart(
            tool_name="calculator",
            content="The result is 4",  # Non-JSON string gets wrapped in {"result": ...}
            tool_call_id="call_456",
        )

        mock_events = [
            PartDeltaEvent(index=0, delta=TextPartDelta(content_delta="Let me calculate...")),
            FunctionToolCallEvent(part=mock_tool_call),
            FunctionToolResultEvent(result=mock_tool_result),
            PartDeltaEvent(index=1, delta=TextPartDelta(content_delta="The answer is 4.")),
        ]

        async def mock_run_stream_events(prompt, message_history=None):
            for event in mock_events:
                yield event

        mock_agent = MagicMock()
        mock_agent.run_stream_events = mock_run_stream_events

        events = []
        async for event in stream_mamba_agent_events(mock_agent, "test"):
            events.append(event)

        assert len(events) == 4
        assert isinstance(events[0], TextDeltaEvent)
        assert events[0].delta == "Let me calculate..."
        assert isinstance(events[1], ToolInputAvailableEvent)
        assert events[1].toolName == "calculator"
        assert isinstance(events[2], ToolOutputAvailableEvent)
        assert events[2].output == {"result": "The result is 4"}
        assert isinstance(events[3], TextDeltaEvent)
        assert events[3].delta == "The answer is 4."


class TestRunMambaAgent:
    """Tests for non-streaming run_mamba_agent function."""

    @pytest.mark.asyncio
    async def test_returns_text_output(self):
        """Test that run_mamba_agent returns the agent output text."""
        # Create a mock result with output property
        mock_result = MagicMock()
        mock_result.output = "Hello, I am the agent response."

        # Create a mock agent with async run method
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await run_mamba_agent(mock_agent, "test prompt")

        assert result == "Hello, I am the agent response."
        mock_agent.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_string_for_none_output(self):
        """Test that None output returns empty string."""
        mock_result = MagicMock()
        mock_result.output = None

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await run_mamba_agent(mock_agent, "test prompt")

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_string_for_empty_output(self):
        """Test that empty output returns empty string."""
        mock_result = MagicMock()
        mock_result.output = ""

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await run_mamba_agent(mock_agent, "test prompt")

        assert result == ""

    @pytest.mark.asyncio
    async def test_passes_message_history(self):
        """Test that message history is converted and passed."""
        mock_result = MagicMock()
        mock_result.output = "Response"

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        history = [{"role": "user", "content": "Previous message"}]

        with patch("mamba_agents.agent.message_utils.dicts_to_model_messages") as mock_convert:
            mock_converted = [MagicMock()]
            mock_convert.return_value = mock_converted

            result = await run_mamba_agent(mock_agent, "test", history)

            mock_convert.assert_called_once_with(history)
            mock_agent.run.assert_called_once()
            # Verify converted history was passed
            call_kwargs = mock_agent.run.call_args
            assert call_kwargs.kwargs["message_history"] == mock_converted

    @pytest.mark.asyncio
    async def test_no_history_conversion_when_none(self):
        """Test that no conversion happens when history is None."""
        mock_result = MagicMock()
        mock_result.output = "Response"

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch("mamba_agents.agent.message_utils.dicts_to_model_messages") as mock_convert:
            result = await run_mamba_agent(mock_agent, "test", None)

            mock_convert.assert_not_called()
            # Verify None was passed for history
            call_kwargs = mock_agent.run.call_args
            assert call_kwargs.kwargs["message_history"] is None

    @pytest.mark.asyncio
    async def test_propagates_agent_errors(self):
        """Test that errors from agent.run are propagated."""
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("Agent failed"))

        with pytest.raises(RuntimeError, match="Agent failed"):
            await run_mamba_agent(mock_agent, "test prompt")

    @pytest.mark.asyncio
    async def test_converts_non_string_output_to_string(self):
        """Test that non-string output is converted to string."""
        mock_result = MagicMock()
        mock_result.output = 12345  # Non-string output

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        result = await run_mamba_agent(mock_agent, "test prompt")

        assert result == "12345"
        assert isinstance(result, str)
