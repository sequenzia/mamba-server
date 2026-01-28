"""Chat request data models."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


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
    parts: list[MessagePart]


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
