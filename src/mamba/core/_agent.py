from pathlib import Path
from typing import Any
from pydantic import SecretStr
from mamba.config import Settings
from mamba_agents import Agent, AgentSettings
from mamba_agents.prompts import PromptManager, PromptConfig
from mamba_agents.mcp import MCPClientManager
from mamba_agents.config.model_backend import ModelBackendSettings


def _create_agent_settings(settings: Settings, model_name: str) -> Any:
    """Create Mamba Agents settings from Mamba Server settings.

    Reuses OpenAI configuration from the server settings.

    Args:
        settings: Mamba Server settings.
        model_name: Model name to use.

    Returns:
        Configured AgentSettings for Mamba Agents.
    """

    return AgentSettings(
        model_backend=ModelBackendSettings(
            base_url=settings.openai.base_url,
            api_key=SecretStr(settings.openai.api_key) if settings.openai.api_key else None,
            model=model_name,
            timeout=float(settings.openai.timeout_seconds),
            max_retries=settings.openai.max_retries,
        ),
    )


def get_agent(settings: Settings, model_name: str) -> Agent:

    home_dir = Path.home()

    agent_settings = _create_agent_settings(settings, model_name)

    promt_manager = PromptManager(config=PromptConfig(prompts_dir=f"{home_dir}/prompts"))
    mcp_manager = MCPClientManager.from_mcp_json(f"{home_dir}/.mcp.json")

    return Agent(
        model_name,
        settings=agent_settings,
        system_prompt=promt_manager.render("system/talent-ops", tone="professional"),
        toolsets=mcp_manager.as_toolsets()
    )
