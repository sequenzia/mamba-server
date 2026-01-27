"""Title generation endpoint handler."""

import asyncio
import logging

from fastapi import APIRouter

from mamba.api.deps import SettingsDep
from mamba.core.agent import create_agent
from mamba.core.title_utils import clean_title
from mamba.models.title import TitleGenerationRequest, TitleGenerationResponse

logger = logging.getLogger(__name__)

router = APIRouter()

TITLE_PROMPT = """Generate a concise title (max {max_length} characters) for this conversation based on the user's first message.
The title should:
- Capture the main topic or intent
- Be descriptive but brief
- Not include quotes or special characters
- Be in sentence case

User message: {user_message}

Respond with ONLY the title, nothing else."""


@router.post("/title/generate", response_model=TitleGenerationResponse)
async def generate_title(
    request: TitleGenerationRequest,
    settings: SettingsDep,
) -> TitleGenerationResponse:
    """Generate a title for a conversation.

    Uses an LLM to generate a concise, descriptive title based on the
    user's first message. Falls back gracefully on any error.

    Args:
        request: The title generation request with userMessage and conversationId.
        settings: Application settings dependency.

    Returns:
        TitleGenerationResponse with the generated title and fallback status.
    """
    try:
        # Create agent with title-specific model (no tools needed)
        agent = create_agent(
            settings,
            model_name=settings.title.model,
            enable_tools=False,
        )

        # Format the prompt
        prompt = TITLE_PROMPT.format(
            max_length=settings.title.max_length,
            user_message=request.userMessage,
        )

        # Calculate timeout in seconds
        timeout_seconds = settings.title.timeout_ms / 1000

        logger.debug(
            f"Generating title for conversation {request.conversationId} "
            f"(timeout={timeout_seconds}s, model={settings.title.model})"
        )

        # Run agent with timeout
        raw_title = await asyncio.wait_for(
            agent.run(prompt),
            timeout=timeout_seconds,
        )

        # Clean and truncate the title
        title = clean_title(raw_title, settings.title.max_length)

        logger.info(f"Generated title for conversation {request.conversationId}: {title!r}")

        return TitleGenerationResponse(title=title, useFallback=False)

    except TimeoutError:
        logger.warning(
            f"Title generation timed out for conversation {request.conversationId}"
        )
        return TitleGenerationResponse(title="", useFallback=True)

    except Exception as e:
        logger.warning(
            f"Title generation failed for conversation {request.conversationId}: {e}"
        )
        return TitleGenerationResponse(title="", useFallback=True)
