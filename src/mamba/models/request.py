"""Chat request data models."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, BeforeValidator, Field


# Part types that contain actual conversation content
CONTENT_PART_TYPES = frozenset({"text", "tool-call", "tool-result", "tool-invocation"})


def filter_message_parts(parts: list[Any]) -> list[Any]:
    """Filter message parts to only include content types.

    The AI SDK may include lifecycle/metadata parts like 'step-start',
    'reasoning', 'source-url', etc. that are meaningful for UI rendering
    but not for conversation context. These are filtered out.

    Args:
        parts: Raw list of message parts from the request.

    Returns:
        Filtered list containing only processable content parts.
    """
    if not isinstance(parts, list):
        return parts

    filtered = []
    for part in parts:
        # Dict from JSON - filter by type field
        if isinstance(part, dict):
            if part.get("type") in CONTENT_PART_TYPES:
                filtered.append(part)
        # Already a Pydantic model - pass through (already validated)
        elif isinstance(part, BaseModel):
            filtered.append(part)

    return filtered


class TextPart(BaseModel):
    """Text content part of a message."""

    type: Literal["text"] = "text"
    text: str


class ToolCallPart(BaseModel):
    """Tool call part of a message (AI SDK format)."""

    type: Literal["tool-call"] = "tool-call"
    toolCallId: str
    toolName: str
    args: dict | None = None


class ToolResultPart(BaseModel):
    """Tool result part of a message (AI SDK format)."""

    type: Literal["tool-result"] = "tool-result"
    toolCallId: str
    result: Any


class ToolInvocationPart(BaseModel):
    """Tool invocation part of a message (legacy format)."""

    type: Literal["tool-invocation"] = "tool-invocation"
    toolCallId: str
    toolName: str
    args: dict
    result: dict | None = None


# Discriminated union for message parts - supports both AI SDK and legacy formats
MessagePart = Annotated[
    Union[TextPart, ToolCallPart, ToolResultPart, ToolInvocationPart],
    Field(discriminator="type"),
]


class UIMessage(BaseModel):
    """Message in UI format with parts array."""

    id: str
    role: Literal["user", "assistant", "system"]
    # Filter parts before validation to remove lifecycle/metadata parts
    parts: Annotated[list[MessagePart], BeforeValidator(filter_message_parts)]


class ChatCompletionRequest(BaseModel):
    """Request body for chat completions endpoint."""

    messages: list[UIMessage]
    model: str = Field(
        ...,
        min_length=1,
        description="Model identifier (e.g., 'gpt-4o' or 'openai/gpt-4o')",
    )
    tools: list[str] | None = Field(
        default=None,
        description="Optional list of tool names to enable (e.g., ['generateForm', 'generateChart'])",
    )
    agent: str | None = Field(
        default=None,
        description="Optional agent name (e.g., 'research', 'code_review'). "
        "Routes to Mamba Agents framework when specified.",
    )
