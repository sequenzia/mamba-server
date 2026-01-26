"""Models endpoint handler."""

import logging

from fastapi import APIRouter

from mamba.api.deps import SettingsDep
from mamba.models.response import ModelInfo, ModelsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models", response_model=ModelsResponse)
async def list_models(settings: SettingsDep) -> ModelsResponse:
    """List available AI models.

    Returns all models configured in the application settings.
    """
    models = []

    for model_config in settings.models:
        model_info = ModelInfo(
            id=model_config.id,
            name=model_config.name,
            provider=model_config.provider,
            description=model_config.description,
            context_window=model_config.context_window,
            supports_tools=model_config.supports_tools,
        )
        models.append(model_info)

    logger.debug(f"Returning {len(models)} models")

    return ModelsResponse(models=models)
