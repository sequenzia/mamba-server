"""Chat completions endpoint handler."""

import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request

from mamba.api.deps import SettingsDep
from mamba.core.agent import create_agent
from mamba.core.messages import extract_text_content
from mamba.core.streaming import (
    create_streaming_response,
    encode_stream_event,
    stream_with_timeout,
)
from mamba.models.events import ErrorEvent, FinishEvent, TextDeltaEvent
from mamba.models.request import ChatCompletionRequest

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


async def _stream_chat_response(
    request: ChatCompletionRequest,
    settings: SettingsDep,
    enable_tools: bool = False,
) -> AsyncIterator[str]:
    """Generate streaming SSE events from chat completion.

    Args:
        request: The chat completion request.
        settings: Application settings.
        enable_tools: Whether to enable tool calling.

    Yields:
        SSE-encoded event strings.
    """
    try:
        # Extract model name from model ID
        model_name = _extract_model_name(request.model)

        # Create agent with the specified model and tools if enabled
        agent = create_agent(
            settings,
            model_name=model_name,
            enable_tools=enable_tools,
        )

        # Extract the latest user message as the prompt
        # The rest become message history
        if not request.messages:
            yield encode_stream_event(ErrorEvent(error="No messages provided"))
            return

        # Get the last user message as the prompt
        last_message = request.messages[-1]
        if last_message.role != "user":
            # If last message isn't from user, use all messages as history
            # and extract text from the last message as prompt
            prompt = extract_text_content(last_message.parts)
            history = request.messages[:-1] if len(request.messages) > 1 else None
        else:
            prompt = extract_text_content(last_message.parts)
            history = request.messages[:-1] if len(request.messages) > 1 else None

        if enable_tools:
            # Use event streaming with tools
            async for event in agent.stream_events(prompt, message_history=history):
                yield encode_stream_event(event)
        else:
            # Stream text-only response
            async for text_chunk in agent.stream_text(prompt, message_history=history):
                yield encode_stream_event(TextDeltaEvent(textDelta=text_chunk))

        # Send finish event
        yield encode_stream_event(FinishEvent())

    except Exception as e:
        logger.exception("Error during chat completion streaming")
        yield encode_stream_event(ErrorEvent(error=str(e)))


@router.post("/chat/completions")
async def chat_completions(
    request_body: ChatCompletionRequest,
    request: Request,
    settings: SettingsDep,
):
    """Handle chat completion requests with streaming response.

    Accepts a chat completion request and returns a streaming response
    with Server-Sent Events containing text deltas and a finish event.

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

    # Determine if tools are enabled
    enable_tools = bool(request_body.tools)

    logger.info(
        f"Chat completion request: model={request_body.model}, "
        f"messages={len(request_body.messages)}, "
        f"tools={'enabled' if enable_tools else 'disabled'}"
    )

    # Create streaming response with timeout and disconnect handling
    event_generator = _stream_chat_response(request_body, settings, enable_tools)
    wrapped_generator = stream_with_timeout(event_generator, request=request)

    return create_streaming_response(wrapped_generator, request)
