"""Server-Sent Event data models for streaming responses.

Event types are compatible with Vercel AI SDK UIMessageChunk format.
"""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


# =============================================================================
# Lifecycle Events
# =============================================================================


class StartEvent(BaseModel):
    """Stream start marker."""

    type: Literal["start"] = "start"
    messageId: str | None = None


class StartStepEvent(BaseModel):
    """Step start marker for multi-step flows."""

    type: Literal["start-step"] = "start-step"


class FinishStepEvent(BaseModel):
    """Step completion marker."""

    type: Literal["finish-step"] = "finish-step"


class FinishEvent(BaseModel):
    """Stream completed successfully."""

    type: Literal["finish"] = "finish"
    finishReason: Literal["stop", "length", "tool-calls", "error"] | None = None


# =============================================================================
# Text Events
# =============================================================================


class TextStartEvent(BaseModel):
    """Marks beginning of a text content block."""

    type: Literal["text-start"] = "text-start"
    id: str


class TextDeltaEvent(BaseModel):
    """Incremental text content from AI response."""

    type: Literal["text-delta"] = "text-delta"
    id: str
    delta: str


class TextEndEvent(BaseModel):
    """Marks end of a text content block."""

    type: Literal["text-end"] = "text-end"
    id: str


# =============================================================================
# Tool Events (AI SDK format)
# =============================================================================


class ToolInputAvailableEvent(BaseModel):
    """AI has decided to invoke a tool."""

    type: Literal["tool-input-available"] = "tool-input-available"
    toolCallId: str
    toolName: str
    input: dict


class ToolOutputAvailableEvent(BaseModel):
    """Result of a tool execution."""

    type: Literal["tool-output-available"] = "tool-output-available"
    toolCallId: str
    output: Any


# =============================================================================
# Error Event
# =============================================================================


class ErrorEvent(BaseModel):
    """An error occurred during processing."""

    type: Literal["error"] = "error"
    errorText: str


# =============================================================================
# Union type for all possible stream events
# =============================================================================

StreamEvent = Annotated[
    Union[
        StartEvent,
        StartStepEvent,
        TextStartEvent,
        TextDeltaEvent,
        TextEndEvent,
        ToolInputAvailableEvent,
        ToolOutputAvailableEvent,
        FinishStepEvent,
        FinishEvent,
        ErrorEvent,
    ],
    Field(discriminator="type"),
]
