"""Chat request data models."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    """Text content part of a message."""

    type: Literal["text"] = "text"
    text: str


class ToolInvocationPart(BaseModel):
    """Tool invocation part of a message."""

    type: Literal["tool-invocation"] = "tool-invocation"
    toolCallId: str
    toolName: str
    args: dict
    result: dict | None = None


# Discriminated union for message parts
MessagePart = Annotated[
    Union[TextPart, ToolInvocationPart],
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
        pattern=r"^openai/[\w-]+$",
        description="Model identifier in format 'openai/model-name'",
    )
    tools: list[str] | None = Field(
        default=None,
        description="Optional list of tool names to enable (e.g., ['generateForm', 'generateChart'])",
    )
