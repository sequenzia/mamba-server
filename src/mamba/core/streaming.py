"""Server-Sent Events encoder for streaming responses.

Compatible with Vercel AI SDK UIMessageChunk format.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

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

logger = logging.getLogger(__name__)

# Default stream timeout in seconds (5 minutes)
DEFAULT_STREAM_TIMEOUT = 300

# AI SDK stream terminator
SSE_DONE_MARKER = "data: [DONE]\n\n"


def encode_sse_event(data: dict[str, Any] | str) -> str:
    """Encode data as a Server-Sent Event.

    Args:
        data: Dictionary to encode as JSON, or pre-encoded JSON string.

    Returns:
        SSE-formatted string with data: prefix and double newline.
    """
    if isinstance(data, str):
        json_data = data
    else:
        json_data = json.dumps(data, ensure_ascii=False)

    return f"data: {json_data}\n\n"


def encode_stream_event(event: StreamEvent) -> str:
    """Encode a StreamEvent model as an SSE event.

    Args:
        event: The stream event model to encode.

    Returns:
        SSE-formatted string.
    """
    return encode_sse_event(event.model_dump())


async def stream_events(
    events: AsyncIterator[StreamEvent],
) -> AsyncIterator[str]:
    """Transform an async iterator of events into SSE-encoded strings.

    Args:
        events: Async iterator of StreamEvent models.

    Yields:
        SSE-formatted strings for each event, ending with [DONE] marker.
    """
    try:
        async for event in events:
            yield encode_stream_event(event)
        # Always end with [DONE] marker for AI SDK compatibility
        yield SSE_DONE_MARKER
    except Exception as e:
        logger.exception("Error during event streaming")
        # Yield error event if encoding fails
        error_event = ErrorEvent(errorText="An unexpected error occurred")
        yield encode_stream_event(error_event)
        yield SSE_DONE_MARKER


async def stream_with_timeout(
    events: AsyncIterator[str],
    timeout: float = DEFAULT_STREAM_TIMEOUT,
    request: Request | None = None,
) -> AsyncIterator[str]:
    """Wrap an event stream with timeout and disconnect handling.

    Monitors for client disconnect and enforces maximum stream duration.
    Sends finish events before closing on timeout.

    Args:
        events: Async iterator yielding SSE-encoded strings.
        timeout: Maximum stream duration in seconds (default: 5 minutes).
        request: Optional FastAPI request for disconnect detection.

    Yields:
        SSE-formatted strings from the wrapped iterator.
    """
    start_time = asyncio.get_event_loop().time()
    finish_sent = False
    done_sent = False

    try:
        async for event in events:
            # Check for client disconnect
            if request and await request.is_disconnected():
                logger.info("Client disconnected, terminating stream")
                break

            # Check for timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Stream timeout after {elapsed:.1f}s, sending finish")
                if not finish_sent:
                    yield encode_stream_event(FinishStepEvent())
                    yield encode_stream_event(FinishEvent(finishReason="stop"))
                    finish_sent = True
                if not done_sent:
                    yield SSE_DONE_MARKER
                    done_sent = True
                break

            # Track if we've seen a finish event or done marker
            if '"type":"finish"' in event or '"type": "finish"' in event:
                finish_sent = True
            if "[DONE]" in event:
                done_sent = True

            yield event

    except asyncio.CancelledError:
        logger.info("Stream cancelled, cleaning up")
        if not finish_sent:
            yield encode_stream_event(FinishStepEvent())
            yield encode_stream_event(FinishEvent(finishReason="stop"))
        if not done_sent:
            yield SSE_DONE_MARKER
        raise
    except Exception as e:
        logger.exception("Error during stream with timeout")
        if not finish_sent:
            yield encode_stream_event(
                ErrorEvent(errorText="Stream error: connection interrupted")
            )
        if not done_sent:
            yield SSE_DONE_MARKER
    finally:
        logger.debug("Stream cleanup completed")


def create_streaming_response(
    event_generator: AsyncIterator[str],
    request: Request | None = None,
) -> StreamingResponse:
    """Create a FastAPI StreamingResponse for SSE.

    Args:
        event_generator: Async iterator yielding SSE-encoded strings.
        request: Optional request to extract request ID for headers.

    Returns:
        Configured StreamingResponse with proper headers for AI SDK.
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "x-vercel-ai-ui-message-stream": "v1",  # Required for AI SDK
        "x-accel-buffering": "no",  # Disable nginx buffering
    }

    # Add request ID to response headers if available
    if request and hasattr(request.state, "request_id"):
        headers["X-Request-ID"] = request.state.request_id

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers=headers,
    )


class SSEStream:
    """Helper class for building SSE event streams.

    Supports AI SDK UIMessageChunk format with proper lifecycle events.

    Example usage:
        stream = SSEStream()
        stream.send_start()
        text_id = stream.send_text_start()
        stream.send_text_delta("Hello", text_id)
        stream.send_text_delta(", world!", text_id)
        stream.send_text_end(text_id)
        stream.send_finish()
        return create_streaming_response(stream.events())
    """

    def __init__(self):
        self._events: list[StreamEvent] = []
        self._text_id_counter = 0
        self._current_text_id: str | None = None

    def add_event(self, event: StreamEvent) -> None:
        """Add an event to the stream."""
        self._events.append(event)

    def _generate_text_id(self) -> str:
        """Generate unique text block ID."""
        self._text_id_counter += 1
        return f"text-{self._text_id_counter}"

    def send_start(self, message_id: str | None = None) -> None:
        """Add start lifecycle events."""
        self.add_event(StartEvent(messageId=message_id))
        self.add_event(StartStepEvent())

    def send_text_start(self, text_id: str | None = None) -> str:
        """Start a new text block, returns the text ID."""
        tid = text_id or self._generate_text_id()
        self._current_text_id = tid
        self.add_event(TextStartEvent(id=tid))
        return tid

    def send_text_delta(self, delta: str, text_id: str | None = None) -> None:
        """Add a text-delta event."""
        tid = text_id or self._current_text_id
        if tid is None:
            tid = self.send_text_start()
        self.add_event(TextDeltaEvent(id=tid, delta=delta))

    def send_text_end(self, text_id: str | None = None) -> None:
        """End a text block."""
        tid = text_id or self._current_text_id
        if tid:
            self.add_event(TextEndEvent(id=tid))
            self._current_text_id = None

    def send_tool_input(
        self, tool_call_id: str, tool_name: str, input_data: dict[str, Any]
    ) -> None:
        """Add a tool-input-available event."""
        self.add_event(
            ToolInputAvailableEvent(
                toolCallId=tool_call_id,
                toolName=tool_name,
                input=input_data,
            )
        )

    def send_tool_output(self, tool_call_id: str, output_data: Any) -> None:
        """Add a tool-output-available event."""
        self.add_event(
            ToolOutputAvailableEvent(
                toolCallId=tool_call_id,
                output=output_data,
            )
        )

    def send_finish(self, reason: str = "stop") -> None:
        """Add finish lifecycle events."""
        self.add_event(FinishStepEvent())
        self.add_event(FinishEvent(finishReason=reason))

    def send_error(self, error_text: str) -> None:
        """Add an error event."""
        self.add_event(ErrorEvent(errorText=error_text))

    async def events(self) -> AsyncIterator[str]:
        """Yield all events as SSE-encoded strings, ending with [DONE]."""
        for event in self._events:
            yield encode_stream_event(event)
        yield SSE_DONE_MARKER
