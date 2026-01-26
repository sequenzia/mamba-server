"""Tests for SSE streaming encoder."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mamba.core.streaming import (
    DEFAULT_STREAM_TIMEOUT,
    SSEStream,
    create_streaming_response,
    encode_sse_event,
    encode_stream_event,
    stream_events,
    stream_with_timeout,
)
from mamba.models.events import (
    ErrorEvent,
    FinishEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)


class TestEncodeSseEvent:
    """Tests for encode_sse_event function."""

    def test_encodes_dict_to_sse(self):
        """Test dictionary is encoded as SSE event."""
        result = encode_sse_event({"type": "text-delta", "textDelta": "Hello"})
        assert result == 'data: {"type": "text-delta", "textDelta": "Hello"}\n\n'

    def test_encodes_string_to_sse(self):
        """Test pre-encoded string is wrapped as SSE."""
        result = encode_sse_event('{"type": "finish"}')
        assert result == 'data: {"type": "finish"}\n\n'

    def test_handles_unicode(self):
        """Test unicode characters are handled correctly."""
        result = encode_sse_event({"text": "Hello 世界 🌍"})
        assert "Hello 世界 🌍" in result

    def test_handles_special_characters(self):
        """Test special characters are properly escaped in JSON."""
        result = encode_sse_event({"text": 'Line 1\nLine 2\t"quoted"'})
        # Parse back to verify it's valid JSON
        json_part = result.replace("data: ", "").strip()
        parsed = json.loads(json_part)
        assert parsed["text"] == 'Line 1\nLine 2\t"quoted"'

    def test_format_ends_with_double_newline(self):
        """Test SSE format ends with double newline."""
        result = encode_sse_event({"type": "test"})
        assert result.endswith("\n\n")


class TestEncodeStreamEvent:
    """Tests for encode_stream_event function."""

    def test_encodes_text_delta(self):
        """Test text-delta event encoding."""
        event = TextDeltaEvent(textDelta="Hello")
        result = encode_stream_event(event)
        # Verify format and content (JSON may have spaces)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "text-delta"
        assert data["textDelta"] == "Hello"

    def test_encodes_tool_call(self):
        """Test tool-call event encoding."""
        event = ToolCallEvent(
            toolCallId="tc_123",
            toolName="generateForm",
            args={"title": "Test"},
        )
        result = encode_stream_event(event)
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "tool-call"
        assert data["toolCallId"] == "tc_123"
        assert data["toolName"] == "generateForm"

    def test_encodes_finish(self):
        """Test finish event encoding."""
        event = FinishEvent()
        result = encode_stream_event(event)
        # Verify format and content (JSON may have spaces)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "finish"

    def test_encodes_error(self):
        """Test error event encoding."""
        event = ErrorEvent(error="Something went wrong")
        result = encode_stream_event(event)
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "error"
        assert data["error"] == "Something went wrong"


class TestStreamEvents:
    """Tests for stream_events async generator."""

    @pytest.mark.asyncio
    async def test_streams_multiple_events(self):
        """Test streaming multiple events."""

        async def event_generator():
            yield TextDeltaEvent(textDelta="Hello")
            yield TextDeltaEvent(textDelta=" world")
            yield FinishEvent()

        results = []
        async for sse in stream_events(event_generator()):
            results.append(sse)

        assert len(results) == 3
        assert "Hello" in results[0]
        assert "world" in results[1]
        assert "finish" in results[2]

    @pytest.mark.asyncio
    async def test_handles_empty_text_delta(self):
        """Test empty text delta is encoded correctly."""

        async def event_generator():
            yield TextDeltaEvent(textDelta="")

        results = []
        async for sse in stream_events(event_generator()):
            results.append(sse)

        assert len(results) == 1
        assert '""' in results[0]  # Empty string in JSON


class TestCreateStreamingResponse:
    """Tests for create_streaming_response function."""

    @pytest.mark.asyncio
    async def test_creates_response_with_correct_content_type(self):
        """Test response has text/event-stream content type."""

        async def generator():
            yield 'data: {"type": "finish"}\n\n'

        response = create_streaming_response(generator())
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_includes_cache_headers(self):
        """Test response includes cache control headers."""

        async def generator():
            yield 'data: {"type": "finish"}\n\n'

        response = create_streaming_response(generator())
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"

    @pytest.mark.asyncio
    async def test_includes_request_id_header(self):
        """Test response includes request ID from request state."""
        from unittest.mock import MagicMock

        async def generator():
            yield 'data: {"type": "finish"}\n\n'

        mock_request = MagicMock()
        mock_request.state.request_id = "test-request-123"

        response = create_streaming_response(generator(), request=mock_request)
        assert response.headers.get("X-Request-ID") == "test-request-123"


class TestSSEStream:
    """Tests for SSEStream helper class."""

    def test_send_text_delta(self):
        """Test sending text delta events."""
        stream = SSEStream()
        stream.send_text_delta("Hello")
        stream.send_text_delta(" world")

        assert len(stream._events) == 2
        assert isinstance(stream._events[0], TextDeltaEvent)

    def test_send_tool_call(self):
        """Test sending tool call events."""
        stream = SSEStream()
        stream.send_tool_call("tc_123", "generateForm", {"title": "Test"})

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ToolCallEvent)
        assert event.toolCallId == "tc_123"

    def test_send_tool_result(self):
        """Test sending tool result events."""
        stream = SSEStream()
        stream.send_tool_result("tc_123", {"status": "success"})

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ToolResultEvent)

    def test_send_finish(self):
        """Test sending finish event."""
        stream = SSEStream()
        stream.send_finish()

        assert len(stream._events) == 1
        assert isinstance(stream._events[0], FinishEvent)

    def test_send_error(self):
        """Test sending error event."""
        stream = SSEStream()
        stream.send_error("Something went wrong")

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ErrorEvent)
        assert event.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_events_yields_sse_strings(self):
        """Test events() yields SSE-encoded strings."""
        stream = SSEStream()
        stream.send_text_delta("Hello")
        stream.send_finish()

        results = []
        async for sse in stream.events():
            results.append(sse)

        assert len(results) == 2
        assert "Hello" in results[0]
        assert "finish" in results[1]


class TestStreamWithTimeout:
    """Tests for stream_with_timeout function."""

    @pytest.mark.asyncio
    async def test_streams_events_normally(self):
        """Test that events are streamed without modification when no timeout."""

        async def event_generator():
            yield 'data: {"type": "text-delta", "textDelta": "Hello"}\n\n'
            yield 'data: {"type": "finish"}\n\n'

        results = []
        async for event in stream_with_timeout(event_generator(), timeout=60):
            results.append(event)

        assert len(results) == 2
        assert "Hello" in results[0]
        assert "finish" in results[1]

    @pytest.mark.asyncio
    async def test_stops_on_client_disconnect(self):
        """Test that streaming stops when client disconnects."""
        call_count = 0

        async def event_generator():
            nonlocal call_count
            while True:
                call_count += 1
                yield f'data: {{"type": "text-delta", "textDelta": "chunk{call_count}"}}\n\n'
                if call_count >= 5:
                    break

        # Mock request that reports disconnected after 2 events
        mock_request = MagicMock()
        disconnect_after = 2
        check_count = 0

        async def is_disconnected():
            nonlocal check_count
            check_count += 1
            return check_count > disconnect_after

        mock_request.is_disconnected = is_disconnected

        results = []
        async for event in stream_with_timeout(
            event_generator(), timeout=60, request=mock_request
        ):
            results.append(event)

        # Should have stopped after disconnect
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_sends_finish_on_timeout(self):
        """Test that finish event is sent when stream times out."""

        async def slow_generator():
            for i in range(10):
                yield f'data: {{"type": "text-delta", "textDelta": "chunk{i}"}}\n\n'
                await asyncio.sleep(0.1)  # Slow down to trigger timeout

        results = []
        async for event in stream_with_timeout(slow_generator(), timeout=0.15):
            results.append(event)

        # Should have stopped due to timeout and sent finish
        assert len(results) >= 1
        # Last event should be finish (either from timeout or original stream)
        assert "finish" in results[-1]

    @pytest.mark.asyncio
    async def test_handles_cancellation(self):
        """Test that cancellation is handled gracefully."""

        async def infinite_generator():
            count = 0
            while True:
                count += 1
                yield f'data: {{"type": "text-delta", "textDelta": "chunk{count}"}}\n\n'
                await asyncio.sleep(0.01)

        results = []

        async def consume_and_cancel():
            async for event in stream_with_timeout(infinite_generator(), timeout=60):
                results.append(event)
                if len(results) >= 3:
                    raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            await consume_and_cancel()

        # Should have collected some events before cancellation
        assert len(results) >= 3

    @pytest.mark.asyncio
    async def test_tracks_finish_event_seen(self):
        """Test that finish event is not duplicated if already in stream."""

        async def event_generator():
            yield 'data: {"type": "text-delta", "textDelta": "Hello"}\n\n'
            yield 'data: {"type": "finish"}\n\n'

        results = []
        async for event in stream_with_timeout(event_generator(), timeout=60):
            results.append(event)

        # Should have exactly 2 events (no duplicate finish)
        assert len(results) == 2
        finish_count = sum(1 for r in results if "finish" in r)
        assert finish_count == 1

    @pytest.mark.asyncio
    async def test_default_timeout_value(self):
        """Test that default timeout is 5 minutes (300 seconds)."""
        assert DEFAULT_STREAM_TIMEOUT == 300
