"""Server-Sent Event data models for streaming responses."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TextDeltaEvent(BaseModel):
    """Incremental text content from AI response."""

    type: Literal["text-delta"] = "text-delta"
    textDelta: str


class ToolCallEvent(BaseModel):
    """AI has decided to invoke a tool."""

    type: Literal["tool-call"] = "tool-call"
    toolCallId: str
    toolName: str
    args: dict


class ToolResultEvent(BaseModel):
    """Result of a tool execution."""

    type: Literal["tool-result"] = "tool-result"
    toolCallId: str
    result: dict


class FinishEvent(BaseModel):
    """Stream completed successfully."""

    type: Literal["finish"] = "finish"


class ErrorEvent(BaseModel):
    """An error occurred during processing."""

    type: Literal["error"] = "error"
    error: str


# Union type for all possible stream events
StreamEvent = Annotated[
    Union[
        TextDeltaEvent,
        ToolCallEvent,
        ToolResultEvent,
        FinishEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
