"""Tests for SSE streaming encoder (AI SDK UIMessageChunk format)."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from mamba.core.streaming import (
    DEFAULT_STREAM_TIMEOUT,
    SSE_DONE_MARKER,
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
    FinishStepEvent,
    StartEvent,
    StartStepEvent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
)


class TestEncodeSseEvent:
    """Tests for encode_sse_event function."""

    def test_encodes_dict_to_sse(self):
        """Test dictionary is encoded as SSE event."""
        result = encode_sse_event({"type": "text-delta", "id": "text-1", "delta": "Hello"})
        assert result == 'data: {"type": "text-delta", "id": "text-1", "delta": "Hello"}\n\n'

    def test_encodes_string_to_sse(self):
        """Test pre-encoded string is wrapped as SSE."""
        result = encode_sse_event('{"type": "finish", "finishReason": "stop"}')
        assert result == 'data: {"type": "finish", "finishReason": "stop"}\n\n'

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
        event = TextDeltaEvent(id="text-1", delta="Hello")
        result = encode_stream_event(event)
        # Verify format and content (JSON may have spaces)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "text-delta"
        assert data["id"] == "text-1"
        assert data["delta"] == "Hello"

    def test_encodes_tool_input_available(self):
        """Test tool-input-available event encoding."""
        event = ToolInputAvailableEvent(
            toolCallId="tc_123",
            toolName="generateForm",
            input={"title": "Test"},
        )
        result = encode_stream_event(event)
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "tool-input-available"
        assert data["toolCallId"] == "tc_123"
        assert data["toolName"] == "generateForm"
        assert data["input"]["title"] == "Test"

    def test_encodes_tool_output_available(self):
        """Test tool-output-available event encoding."""
        event = ToolOutputAvailableEvent(
            toolCallId="tc_123",
            output={"status": "success"},
        )
        result = encode_stream_event(event)
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "tool-output-available"
        assert data["toolCallId"] == "tc_123"
        assert data["output"]["status"] == "success"

    def test_encodes_finish(self):
        """Test finish event encoding."""
        event = FinishEvent(finishReason="stop")
        result = encode_stream_event(event)
        # Verify format and content (JSON may have spaces)
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "finish"
        assert data["finishReason"] == "stop"

    def test_encodes_error(self):
        """Test error event encoding."""
        event = ErrorEvent(errorText="Something went wrong")
        result = encode_stream_event(event)
        data = json.loads(result.replace("data: ", "").strip())
        assert data["type"] == "error"
        assert data["errorText"] == "Something went wrong"


class TestStreamEvents:
    """Tests for stream_events async generator."""

    @pytest.mark.asyncio
    async def test_streams_multiple_events(self):
        """Test streaming multiple events."""

        async def event_generator():
            yield TextDeltaEvent(id="text-1", delta="Hello")
            yield TextDeltaEvent(id="text-1", delta=" world")
            yield FinishEvent(finishReason="stop")

        results = []
        async for sse in stream_events(event_generator()):
            results.append(sse)

        # 3 events + [DONE] marker
        assert len(results) == 4
        assert "Hello" in results[0]
        assert "world" in results[1]
        assert "finish" in results[2]
        assert "[DONE]" in results[3]

    @pytest.mark.asyncio
    async def test_handles_empty_delta(self):
        """Test empty delta is encoded correctly."""

        async def event_generator():
            yield TextDeltaEvent(id="text-1", delta="")

        results = []
        async for sse in stream_events(event_generator()):
            results.append(sse)

        # 1 event + [DONE] marker
        assert len(results) == 2
        assert '""' in results[0]  # Empty string in JSON

    @pytest.mark.asyncio
    async def test_ends_with_done_marker(self):
        """Test stream ends with [DONE] marker."""

        async def event_generator():
            yield FinishEvent(finishReason="stop")

        results = []
        async for sse in stream_events(event_generator()):
            results.append(sse)

        assert results[-1] == SSE_DONE_MARKER


class TestCreateStreamingResponse:
    """Tests for create_streaming_response function."""

    @pytest.mark.asyncio
    async def test_creates_response_with_correct_content_type(self):
        """Test response has text/event-stream content type."""

        async def generator():
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'

        response = create_streaming_response(generator())
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_includes_cache_headers(self):
        """Test response includes cache control headers."""

        async def generator():
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'

        response = create_streaming_response(generator())
        assert response.headers.get("Cache-Control") == "no-cache"
        assert response.headers.get("Connection") == "keep-alive"

    @pytest.mark.asyncio
    async def test_includes_ai_sdk_header(self):
        """Test response includes AI SDK version header."""

        async def generator():
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'

        response = create_streaming_response(generator())
        assert response.headers.get("x-vercel-ai-ui-message-stream") == "v1"

    @pytest.mark.asyncio
    async def test_includes_request_id_header(self):
        """Test response includes request ID from request state."""
        from unittest.mock import MagicMock

        async def generator():
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'

        mock_request = MagicMock()
        mock_request.state.request_id = "test-request-123"

        response = create_streaming_response(generator(), request=mock_request)
        assert response.headers.get("X-Request-ID") == "test-request-123"


class TestSSEStream:
    """Tests for SSEStream helper class."""

    def test_send_start(self):
        """Test sending start lifecycle events."""
        stream = SSEStream()
        stream.send_start(message_id="msg-123")

        assert len(stream._events) == 2
        assert isinstance(stream._events[0], StartEvent)
        assert isinstance(stream._events[1], StartStepEvent)
        assert stream._events[0].messageId == "msg-123"

    def test_send_text_start(self):
        """Test sending text-start event."""
        stream = SSEStream()
        text_id = stream.send_text_start("text-1")

        assert text_id == "text-1"
        assert len(stream._events) == 1
        assert isinstance(stream._events[0], TextStartEvent)
        assert stream._events[0].id == "text-1"

    def test_send_text_start_auto_generates_id(self):
        """Test send_text_start auto-generates ID if not provided."""
        stream = SSEStream()
        text_id = stream.send_text_start()

        assert text_id == "text-1"
        assert stream._events[0].id == "text-1"

    def test_send_text_delta(self):
        """Test sending text delta events."""
        stream = SSEStream()
        stream.send_text_start("text-1")
        stream.send_text_delta("Hello")
        stream.send_text_delta(" world")

        assert len(stream._events) == 3
        assert isinstance(stream._events[1], TextDeltaEvent)
        assert stream._events[1].delta == "Hello"
        assert stream._events[1].id == "text-1"

    def test_send_text_delta_auto_starts_text_block(self):
        """Test send_text_delta auto-starts text block if needed."""
        stream = SSEStream()
        stream.send_text_delta("Hello")

        # Should have created text-start + text-delta
        assert len(stream._events) == 2
        assert isinstance(stream._events[0], TextStartEvent)
        assert isinstance(stream._events[1], TextDeltaEvent)

    def test_send_text_end(self):
        """Test sending text-end event."""
        stream = SSEStream()
        stream.send_text_start("text-1")
        stream.send_text_delta("Hello")
        stream.send_text_end("text-1")

        assert len(stream._events) == 3
        assert isinstance(stream._events[2], TextEndEvent)
        assert stream._events[2].id == "text-1"

    def test_send_tool_input(self):
        """Test sending tool-input-available events."""
        stream = SSEStream()
        stream.send_tool_input("tc_123", "generateForm", {"title": "Test"})

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ToolInputAvailableEvent)
        assert event.toolCallId == "tc_123"
        assert event.toolName == "generateForm"
        assert event.input["title"] == "Test"

    def test_send_tool_output(self):
        """Test sending tool-output-available events."""
        stream = SSEStream()
        stream.send_tool_output("tc_123", {"status": "success"})

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ToolOutputAvailableEvent)
        assert event.toolCallId == "tc_123"
        assert event.output["status"] == "success"

    def test_send_finish(self):
        """Test sending finish lifecycle events."""
        stream = SSEStream()
        stream.send_finish("stop")

        assert len(stream._events) == 2
        assert isinstance(stream._events[0], FinishStepEvent)
        assert isinstance(stream._events[1], FinishEvent)
        assert stream._events[1].finishReason == "stop"

    def test_send_error(self):
        """Test sending error event."""
        stream = SSEStream()
        stream.send_error("Something went wrong")

        assert len(stream._events) == 1
        event = stream._events[0]
        assert isinstance(event, ErrorEvent)
        assert event.errorText == "Something went wrong"

    @pytest.mark.asyncio
    async def test_events_yields_sse_strings(self):
        """Test events() yields SSE-encoded strings."""
        stream = SSEStream()
        stream.send_text_start("text-1")
        stream.send_text_delta("Hello", "text-1")
        stream.send_text_end("text-1")
        stream.send_finish()

        results = []
        async for sse in stream.events():
            results.append(sse)

        # 5 events (text-start, text-delta, text-end, finish-step, finish) + [DONE] marker
        assert len(results) == 6
        assert "text-start" in results[0]
        assert "Hello" in results[1]
        assert "text-end" in results[2]
        assert "finish-step" in results[3]
        assert "finish" in results[4]
        assert "[DONE]" in results[-1]


class TestStreamWithTimeout:
    """Tests for stream_with_timeout function."""

    @pytest.mark.asyncio
    async def test_streams_events_normally(self):
        """Test that events are streamed without modification when no timeout."""

        async def event_generator():
            yield 'data: {"type": "text-delta", "id": "text-1", "delta": "Hello"}\n\n'
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'

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
                yield f'data: {{"type": "text-delta", "id": "text-1", "delta": "chunk{call_count}"}}\n\n'
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
                yield f'data: {{"type": "text-delta", "id": "text-1", "delta": "chunk{i}"}}\n\n'
                await asyncio.sleep(0.1)  # Slow down to trigger timeout

        results = []
        async for event in stream_with_timeout(slow_generator(), timeout=0.15):
            results.append(event)

        # Should have stopped due to timeout and sent finish
        assert len(results) >= 1
        # Last event should be [DONE] marker
        assert "[DONE]" in results[-1]

    @pytest.mark.asyncio
    async def test_handles_cancellation(self):
        """Test that cancellation is handled gracefully."""

        async def infinite_generator():
            count = 0
            while True:
                count += 1
                yield f'data: {{"type": "text-delta", "id": "text-1", "delta": "chunk{count}"}}\n\n'
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
            yield 'data: {"type": "text-delta", "id": "text-1", "delta": "Hello"}\n\n'
            yield 'data: {"type": "finish", "finishReason": "stop"}\n\n'
            yield 'data: [DONE]\n\n'

        results = []
        async for event in stream_with_timeout(event_generator(), timeout=60):
            results.append(event)

        # Should have exactly 3 events (no duplicate finish)
        assert len(results) == 3
        finish_count = sum(1 for r in results if '"type":"finish"' in r or '"type": "finish"' in r)
        assert finish_count == 1

    @pytest.mark.asyncio
    async def test_default_timeout_value(self):
        """Test that default timeout is 5 minutes (300 seconds)."""
        assert DEFAULT_STREAM_TIMEOUT == 300

    def test_done_marker_constant(self):
        """Test SSE_DONE_MARKER constant."""
        assert SSE_DONE_MARKER == "data: [DONE]\n\n"
