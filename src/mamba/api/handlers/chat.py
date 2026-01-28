"""Chat completions endpoint handler."""

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request

from mamba.api.deps import SettingsDep
from mamba.config import Settings
from mamba.core.agent import create_agent
from mamba.core.mamba_agent import (
    convert_ui_messages_to_dicts,
    get_agent,
    stream_mamba_agent_events,
)
from mamba.core.messages import extract_text_content
from mamba.core.streaming import (
    SSE_DONE_MARKER,
    create_streaming_response,
    encode_stream_event,
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
)
from mamba.models.request import ChatCompletionRequest
from mamba.utils.errors import (
    ErrorCode,
    classify_exception,
    create_stream_error_event,
    log_error,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_model_name(model_id: str) -> str:
    """Extract OpenAI model name from model ID.

    Args:
        model_id: Model identifier in format 'openai/model-name'.

    Returns:
        The model name portion (e.g., 'gpt-4o').
    """
    # Model ID format is 'openai/model-name'
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


async def _stream_agent_response(
    request: ChatCompletionRequest,
    settings: Settings,
    model_name: str,
    message_id: str,
) -> AsyncIterator[str]:
    """Stream response from a Mamba Agent.

    Args:
        request: The chat completion request.
        settings: Application settings.
        model_name: Model name to use.
        message_id: Unique message ID for this response.

    Yields:
        SSE-encoded event strings in AI SDK format.
    """
    text_id = "text-1"
    text_started = False

    try:
        # Emit start lifecycle events
        yield encode_stream_event(StartEvent(messageId=message_id))
        yield encode_stream_event(StartStepEvent())

        # Get the configured agent
        agent = get_agent(request.agent, settings, model_name)

        # Convert message history (all but last message)
        history = None
        if len(request.messages) > 1:
            history = convert_ui_messages_to_dicts(request.messages[:-1])

        # Extract prompt from last message
        last_message = request.messages[-1]
        prompt = extract_text_content(last_message.parts)

        # Stream events from agent
        async for event in stream_mamba_agent_events(agent, prompt, history):
            # Convert events to proper format with text block lifecycle
            if isinstance(event, TextDeltaEvent):
                if not text_started:
                    yield encode_stream_event(TextStartEvent(id=text_id))
                    text_started = True
                yield encode_stream_event(event)
            else:
                # For non-text events, close text block first
                if text_started:
                    yield encode_stream_event(TextEndEvent(id=text_id))
                    text_started = False
                yield encode_stream_event(event)

        # Close text block if still open
        if text_started:
            yield encode_stream_event(TextEndEvent(id=text_id))

        # Emit finish lifecycle events
        yield encode_stream_event(FinishStepEvent())
        yield encode_stream_event(FinishEvent(finishReason="stop"))
        yield SSE_DONE_MARKER

    except ValueError as e:
        # Unknown agent name - this is a user error, provide the message directly
        logger.error(f"Agent error: {e}")
        yield encode_stream_event(create_stream_error_event(
            code=ErrorCode.INVALID_REQUEST,
            message=str(e),
        ))
        yield SSE_DONE_MARKER
    except Exception as e:
        log_error(e, context={"component": "agent_streaming", "agent": request.agent})
        error_code = classify_exception(e)
        yield encode_stream_event(create_stream_error_event(code=error_code))
        yield SSE_DONE_MARKER


async def _stream_chat_response(
    request: ChatCompletionRequest,
    settings: Settings,
    enable_tools: bool = False,
) -> AsyncIterator[str]:
    """Generate streaming SSE events from chat completion.

    Emits events in AI SDK UIMessageChunk format with proper lifecycle events.

    Args:
        request: The chat completion request.
        settings: Application settings.
        enable_tools: Whether to enable tool calling.

    Yields:
        SSE-encoded event strings.
    """
    # Generate unique IDs for this response
    message_id = str(uuid.uuid4())
    text_id = "text-1"

    try:
        # Extract model name from model ID
        model_name = _extract_model_name(request.model)

        # Check if agent-based routing is requested
        if request.agent:
            async for event_str in _stream_agent_response(
                request, settings, model_name, message_id
            ):
                yield event_str
            return

        # Existing ChatAgent flow
        agent = create_agent(
            settings,
            model_name=model_name,
            enable_tools=enable_tools,
        )

        # Extract the latest user message as the prompt
        if not request.messages:
            yield encode_stream_event(ErrorEvent(errorText="No messages provided"))
            yield SSE_DONE_MARKER
            return

        # Get the last user message as the prompt
        last_message = request.messages[-1]
        prompt = extract_text_content(last_message.parts)
        history = request.messages[:-1] if len(request.messages) > 1 else None

        # Emit start lifecycle events
        yield encode_stream_event(StartEvent(messageId=message_id))
        yield encode_stream_event(StartStepEvent())

        if enable_tools:
            # Use event streaming with tools - events come from agent
            text_started = False
            async for event in agent.stream_events(prompt, message_history=history):
                # Events are already in the new format from agent.py
                if isinstance(event, TextDeltaEvent):
                    if not text_started:
                        yield encode_stream_event(TextStartEvent(id=text_id))
                        text_started = True
                yield encode_stream_event(event)

            # Close text block if still open
            if text_started:
                yield encode_stream_event(TextEndEvent(id=text_id))
        else:
            # Stream text-only response with lifecycle events
            yield encode_stream_event(TextStartEvent(id=text_id))

            async for text_chunk in agent.stream_text(prompt, message_history=history):
                yield encode_stream_event(TextDeltaEvent(id=text_id, delta=text_chunk))

            yield encode_stream_event(TextEndEvent(id=text_id))

        # Emit finish lifecycle events
        yield encode_stream_event(FinishStepEvent())
        yield encode_stream_event(FinishEvent(finishReason="stop"))
        yield SSE_DONE_MARKER

    except Exception as e:
        logger.exception("Error during chat completion streaming")
        yield encode_stream_event(ErrorEvent(errorText=str(e)))
        yield SSE_DONE_MARKER


@router.post("/chat")
async def chat(
    request_body: ChatCompletionRequest,
    request: Request,
    settings: SettingsDep,
):
    """Handle chat completion requests with streaming response.

    Accepts a chat completion request and returns a streaming response
    with Server-Sent Events in AI SDK UIMessageChunk format.

    Args:
        request_body: The chat completion request containing messages and model.
        request: The FastAPI request object for headers.
        settings: Application settings dependency.

    Returns:
        StreamingResponse with SSE events.

    Raises:
        HTTPException: If the request is invalid (empty messages).
    """
    # Validate that messages are not empty
    if not request_body.messages:
        raise HTTPException(
            status_code=400,
            detail="Messages array cannot be empty",
        )

    # Determine if tools are enabled (only for standard chat, not agent mode)
    enable_tools = bool(request_body.tools) and not request_body.agent

    logger.info(
        f"Chat completion request: model={request_body.model}, "
        f"messages={len(request_body.messages)}, "
        f"tools={'enabled' if enable_tools else 'disabled'}, "
        f"agent={request_body.agent or 'none'}"
    )

    # Create streaming response with timeout and disconnect handling
    event_generator = _stream_chat_response(request_body, settings, enable_tools)
    wrapped_generator = stream_with_timeout(event_generator, request=request)

    return create_streaming_response(wrapped_generator, request)
