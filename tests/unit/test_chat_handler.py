"""Tests for chat completions endpoint handler."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mamba.api.handlers.chat import router, _extract_model_name
from mamba.config import Settings


def create_test_app(settings: Settings) -> FastAPI:
    """Create test app with chat router."""
    from mamba.api.deps import get_settings_dependency
    from mamba.middleware.request_id import RequestIdMiddleware

    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.include_router(router)

    # Override settings dependency
    app.dependency_overrides[get_settings_dependency] = lambda: settings

    return app


class TestExtractModelName:
    """Tests for _extract_model_name helper function."""

    def test_extracts_model_from_openai_format(self):
        """Test extracting model name from 'openai/model-name' format."""
        assert _extract_model_name("openai/gpt-4o") == "gpt-4o"
        assert _extract_model_name("openai/gpt-4o-mini") == "gpt-4o-mini"

    def test_handles_model_without_prefix(self):
        """Test handling model name without provider prefix."""
        assert _extract_model_name("gpt-4o") == "gpt-4o"

    def test_handles_complex_model_names(self):
        """Test handling model names with multiple slashes."""
        assert _extract_model_name("openai/gpt-4/turbo") == "gpt-4/turbo"


class TestChatCompletionsValidation:
    """Tests for request validation."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    def test_rejects_empty_messages(self, settings):
        """Test that empty messages array returns 400 error."""
        app = create_test_app(settings)
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "messages": [],
                "model": "openai/gpt-4o",
            },
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_rejects_invalid_model_format(self, settings):
        """Test that invalid model format returns validation error."""
        app = create_test_app(settings)
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "user",
                        "parts": [{"type": "text", "text": "Hello"}],
                    }
                ],
                "model": "invalid-model",  # Missing openai/ prefix
            },
        )

        assert response.status_code == 422

    def test_rejects_missing_messages(self, settings):
        """Test that missing messages field returns validation error."""
        app = create_test_app(settings)
        client = TestClient(app)

        response = client.post(
            "/chat",
            json={
                "model": "openai/gpt-4o",
            },
        )

        assert response.status_code == 422


class TestChatCompletionsStreaming:
    """Tests for streaming response functionality."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent that yields text chunks."""

        async def mock_stream_text(prompt, message_history=None):
            yield "Hello"
            yield ", "
            yield "world!"

        mock = AsyncMock()
        mock.stream_text = mock_stream_text
        return mock

    def test_returns_streaming_response(self, settings, mock_agent):
        """Test that endpoint returns a streaming response."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_includes_request_id_header(self, settings, mock_agent):
        """Test that response includes X-Request-ID header."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        assert "x-request-id" in response.headers

    def test_streams_text_delta_events(self, settings, mock_agent):
        """Test that text-delta events are emitted for text chunks."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        # Parse SSE events from response
        events = parse_sse_events(response.text)

        # Should have text-delta events
        text_deltas = [e for e in events if e.get("type") == "text-delta"]
        assert len(text_deltas) == 3
        assert text_deltas[0]["textDelta"] == "Hello"
        assert text_deltas[1]["textDelta"] == ", "
        assert text_deltas[2]["textDelta"] == "world!"

    def test_sends_finish_event(self, settings, mock_agent):
        """Test that finish event is sent on completion."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        # Parse SSE events from response
        events = parse_sse_events(response.text)

        # Last event should be finish
        finish_events = [e for e in events if e.get("type") == "finish"]
        assert len(finish_events) == 1

    def test_includes_cache_headers(self, settings, mock_agent):
        """Test that response includes proper cache headers."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        assert response.headers.get("cache-control") == "no-cache"


class TestChatCompletionsErrorHandling:
    """Tests for error handling in streaming."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    def test_streams_error_event_on_agent_failure(self, settings):
        """Test that error event is streamed when agent fails."""

        async def failing_stream_text(prompt, message_history=None):
            raise RuntimeError("OpenAI API error")
            yield  # Make it a generator

        mock_agent = AsyncMock()
        mock_agent.stream_text = failing_stream_text

        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        # Should still return 200 since streaming starts before error
        assert response.status_code == 200

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Should have error event
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "error" in error_events[0]["error"].lower() or "OpenAI" in error_events[0]["error"]


class TestChatCompletionsWithHistory:
    """Tests for handling message history."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""

        async def mock_stream_text(prompt, message_history=None):
            yield "Response"

        mock = AsyncMock()
        mock.stream_text = mock_stream_text
        return mock

    def test_handles_conversation_with_history(self, settings, mock_agent):
        """Test handling conversation with multiple messages."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "system",
                            "parts": [{"type": "text", "text": "You are helpful."}],
                        },
                        {
                            "id": "msg_2",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        },
                        {
                            "id": "msg_3",
                            "role": "assistant",
                            "parts": [{"type": "text", "text": "Hi there!"}],
                        },
                        {
                            "id": "msg_4",
                            "role": "user",
                            "parts": [{"type": "text", "text": "How are you?"}],
                        },
                    ],
                    "model": "openai/gpt-4o",
                },
            )

        assert response.status_code == 200

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Should have text-delta and finish events
        text_deltas = [e for e in events if e.get("type") == "text-delta"]
        finish_events = [e for e in events if e.get("type") == "finish"]
        assert len(text_deltas) >= 1
        assert len(finish_events) == 1


class TestChatCompletionsWithTools:
    """Tests for tool call streaming."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    @pytest.fixture
    def mock_agent_with_tools(self):
        """Create a mock agent that yields tool events and text."""
        from mamba.models.events import TextDeltaEvent, ToolCallEvent, ToolResultEvent

        async def mock_stream_events(prompt, message_history=None):
            # Yield a tool call event
            yield ToolCallEvent(
                toolCallId="call_123",
                toolName="generateForm",
                args={"title": "Contact Form", "fields": []},
            )
            # Yield a tool result event
            yield ToolResultEvent(
                toolCallId="call_123",
                result={"title": "Contact Form", "fields": []},
            )
            # Yield some text
            yield TextDeltaEvent(textDelta="Here is your form.")

        mock = AsyncMock()
        mock.stream_events = mock_stream_events
        return mock

    def test_tool_call_events_emitted(self, settings, mock_agent_with_tools):
        """Test that tool-call events are emitted in response."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent_with_tools
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Create a contact form"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                    "tools": ["generateForm"],
                },
            )

        assert response.status_code == 200

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Should have tool-call event
        tool_calls = [e for e in events if e.get("type") == "tool-call"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["toolCallId"] == "call_123"
        assert tool_calls[0]["toolName"] == "generateForm"
        assert tool_calls[0]["args"]["title"] == "Contact Form"

    def test_tool_result_events_emitted(self, settings, mock_agent_with_tools):
        """Test that tool-result events are emitted in response."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent_with_tools
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Create a contact form"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                    "tools": ["generateForm"],
                },
            )

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Should have tool-result event
        tool_results = [e for e in events if e.get("type") == "tool-result"]
        assert len(tool_results) == 1
        assert tool_results[0]["toolCallId"] == "call_123"
        assert "title" in tool_results[0]["result"]

    def test_tool_call_followed_by_text(self, settings, mock_agent_with_tools):
        """Test that tool calls can be followed by text responses."""
        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent_with_tools
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Create a contact form"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                    "tools": ["generateForm"],
                },
            )

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Check event sequence: tool-call, tool-result, text-delta, finish
        event_types = [e.get("type") for e in events]
        assert "tool-call" in event_types
        assert "tool-result" in event_types
        assert "text-delta" in event_types
        assert "finish" in event_types

    def test_no_tools_when_not_requested(self, settings):
        """Test that tools are not used when not requested."""

        async def mock_stream_text(prompt, message_history=None):
            yield "Hello"

        mock_agent = AsyncMock()
        mock_agent.stream_text = mock_stream_text

        app = create_test_app(settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.chat.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/chat",
                json={
                    "messages": [
                        {
                            "id": "msg_1",
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "model": "openai/gpt-4o",
                    # No tools field
                },
            )

        # Parse SSE events
        events = parse_sse_events(response.text)

        # Should have only text-delta and finish (no tool events)
        event_types = [e.get("type") for e in events]
        assert "tool-call" not in event_types
        assert "tool-result" not in event_types
        assert "text-delta" in event_types


def parse_sse_events(sse_text: str) -> list[dict]:
    """Parse SSE text into list of event dictionaries.

    Args:
        sse_text: Raw SSE text with 'data: {...}' lines.

    Returns:
        List of parsed JSON event dictionaries.
    """
    events = []
    for line in sse_text.split("\n"):
        if line.startswith("data: "):
            json_str = line[6:]  # Remove 'data: ' prefix
            if json_str.strip():
                events.append(json.loads(json_str))
    return events
