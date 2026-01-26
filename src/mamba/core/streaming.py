"""Server-Sent Events encoder for streaming responses."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from mamba.models.events import ErrorEvent, FinishEvent, StreamEvent

logger = logging.getLogger(__name__)

# Default stream timeout in seconds (5 minutes)
DEFAULT_STREAM_TIMEOUT = 300


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
        SSE-formatted strings for each event.
    """
    try:
        async for event in events:
            yield encode_stream_event(event)
    except Exception as e:
        logger.exception("Error during event streaming")
        # Yield error event if encoding fails
        error_event = ErrorEvent(error="An unexpected error occurred")
        yield encode_stream_event(error_event)


async def stream_with_timeout(
    events: AsyncIterator[str],
    timeout: float = DEFAULT_STREAM_TIMEOUT,
    request: Request | None = None,
) -> AsyncIterator[str]:
    """Wrap an event stream with timeout and disconnect handling.

    Monitors for client disconnect and enforces maximum stream duration.
    Sends a finish event before closing on timeout.

    Args:
        events: Async iterator yielding SSE-encoded strings.
        timeout: Maximum stream duration in seconds (default: 5 minutes).
        request: Optional FastAPI request for disconnect detection.

    Yields:
        SSE-formatted strings from the wrapped iterator.
    """
    start_time = asyncio.get_event_loop().time()
    finish_sent = False

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
                    yield encode_stream_event(FinishEvent())
                    finish_sent = True
                break

            # Track if we've seen a finish event
            if '"type": "finish"' in event or '"type":"finish"' in event:
                finish_sent = True

            yield event

    except asyncio.CancelledError:
        logger.info("Stream cancelled, cleaning up")
        if not finish_sent:
            yield encode_stream_event(FinishEvent())
        raise
    except Exception as e:
        logger.exception("Error during stream with timeout")
        if not finish_sent:
            yield encode_stream_event(
                ErrorEvent(error="Stream error: connection interrupted")
            )
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
        Configured StreamingResponse with proper headers.
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
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

    Example usage:
        stream = SSEStream()

        async def generate():
            stream.send_text_delta("Hello")
            stream.send_text_delta(", world!")
            stream.send_finish()
            return stream.events()

        return create_streaming_response(generate())
    """

    def __init__(self):
        self._events: list[StreamEvent] = []

    def add_event(self, event: StreamEvent) -> None:
        """Add an event to the stream."""
        self._events.append(event)

    def send_text_delta(self, text: str) -> None:
        """Add a text-delta event."""
        from mamba.models.events import TextDeltaEvent

        self.add_event(TextDeltaEvent(textDelta=text))

    def send_tool_call(
        self, tool_call_id: str, tool_name: str, args: dict[str, Any]
    ) -> None:
        """Add a tool-call event."""
        from mamba.models.events import ToolCallEvent

        self.add_event(
            ToolCallEvent(
                toolCallId=tool_call_id,
                toolName=tool_name,
                args=args,
            )
        )

    def send_tool_result(self, tool_call_id: str, result: dict[str, Any]) -> None:
        """Add a tool-result event."""
        from mamba.models.events import ToolResultEvent

        self.add_event(ToolResultEvent(toolCallId=tool_call_id, result=result))

    def send_finish(self) -> None:
        """Add a finish event."""
        from mamba.models.events import FinishEvent

        self.add_event(FinishEvent())

    def send_error(self, error: str) -> None:
        """Add an error event."""
        from mamba.models.events import ErrorEvent

        self.add_event(ErrorEvent(error=error))

    async def events(self) -> AsyncIterator[str]:
        """Yield all events as SSE-encoded strings."""
        for event in self._events:
            yield encode_stream_event(event)
