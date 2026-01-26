"""Chat response data models."""

from pydantic import BaseModel


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str
    name: str
    provider: str
    description: str | None = None
    context_window: int | None = None
    supports_tools: bool = True


class ModelsResponse(BaseModel):
    """Response for models listing endpoint."""

    models: list[ModelInfo]
