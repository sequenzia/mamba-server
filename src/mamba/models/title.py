"""Title generation request and response models."""

from pydantic import BaseModel, Field


class TitleGenerationRequest(BaseModel):
    """Request body for title generation endpoint."""

    userMessage: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user message to generate a title from",
    )
    conversationId: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the conversation",
    )


class TitleGenerationResponse(BaseModel):
    """Response body for title generation endpoint."""

    title: str = Field(
        ...,
        description="Generated conversation title",
    )
    useFallback: bool = Field(
        ...,
        description="Whether a fallback title was used due to generation failure",
    )
