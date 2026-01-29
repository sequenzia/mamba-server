"""Mamba Agents framework integration adapter.

Provides pre-configured agents and streaming adapter to convert
Mamba Agents responses to Mamba Server's StreamEvent format.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from mamba.config import Settings
from mamba.models.events import (
    ErrorEvent,
    TextDeltaEvent,
    ToolInputAvailableEvent,
    ToolOutputAvailableEvent,
)
from mamba.models.request import TextPart, ToolInvocationPart, UIMessage
from mamba.utils.errors import classify_exception, create_stream_error_event, log_error

if TYPE_CHECKING:
    from mamba_agents import Agent

logger = logging.getLogger(__name__)


# Type alias for agent factory functions
AgentFactory = Callable[[Settings, str], "Agent"]

# Registry of available agents
_AGENT_REGISTRY: dict[str, AgentFactory] = {}


def register_agent(name: str) -> Callable[[AgentFactory], AgentFactory]:
    """Decorator to register an agent factory.

    Args:
        name: Unique identifier for the agent.

    Returns:
        Decorator function that registers the factory.
    """

    def decorator(factory: AgentFactory) -> AgentFactory:
        _AGENT_REGISTRY[name] = factory
        logger.debug(f"Registered agent: {name}")
        return factory

    return decorator


def get_available_agents() -> list[str]:
    """Get list of registered agent names.

    Returns:
        List of available agent identifiers.
    """
    return list(_AGENT_REGISTRY.keys())


def get_agent(name: str, settings: Settings, model_name: str) -> Agent:
    """Get a configured agent instance by name.

    Args:
        name: Agent identifier.
        settings: Mamba Server settings (for OpenAI config).
        model_name: Model to use (e.g., 'gpt-4o').

    Returns:
        Configured Agent instance.

    Raises:
        ValueError: If agent name is not registered.
    """
    if name not in _AGENT_REGISTRY:
        available = ", ".join(get_available_agents()) or "none"
        raise ValueError(f"Unknown agent: '{name}'. Available agents: {available}")
    return _AGENT_REGISTRY[name](settings, model_name)


def _create_agent_settings(settings: Settings, model_name: str) -> Any:
    """Create Mamba Agents settings from Mamba Server settings.

    Reuses OpenAI configuration from the server settings.

    Args:
        settings: Mamba Server settings.
        model_name: Model name to use.

    Returns:
        Configured AgentSettings for Mamba Agents.
    """
    from mamba_agents import AgentSettings
    from mamba_agents.config.model_backend import ModelBackendSettings

    return AgentSettings(
        model_backend=ModelBackendSettings(
            base_url=settings.openai.base_url,
            api_key=SecretStr(settings.openai.api_key) if settings.openai.api_key else None,
            model=model_name,
            timeout=float(settings.openai.timeout_seconds),
            max_retries=settings.openai.max_retries,
        ),
    )


# ============================================================================
# Agent Definitions
# ============================================================================

RESEARCH_SYSTEM_PROMPT = """You are a research assistant that helps users find and synthesize information.

Your capabilities:
- Searching for relevant information
- Summarizing findings clearly
- Citing sources when available
- Asking clarifying questions when needed

Always provide accurate, well-organized responses. If you're unsure about something, say so."""


@register_agent("research")
def create_research_agent(settings: Settings, model_name: str) -> Agent:
    """Create a research assistant agent.

    This agent is designed for information gathering and synthesis tasks.
    It has a focused system prompt for research activities.

    Args:
        settings: Mamba Server settings.
        model_name: Model to use.

    Returns:
        Configured research Agent.
    """
    from mamba_agents import Agent, AgentConfig

    agent_settings = _create_agent_settings(settings, model_name)

    config = AgentConfig(
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        track_context=False,  # Stateless - client manages history
        auto_compact=False,
        graceful_tool_errors=True,
    )

    agent = Agent(
        model_name,
        settings=agent_settings,
        config=config,
    )

    # Register research-specific tools
    @agent.tool_plain
    async def search_notes(query: str) -> dict[str, Any]:
        """Search through notes and documents.

        Args:
            query: Search query string.

        Returns:
            Search results with matching content.
        """
        # Placeholder - would integrate with actual search service
        return {
            "query": query,
            "results": [],
            "message": "Search functionality not yet connected",
        }

    return agent


CODE_REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Your role is to:

1. Analyze code for bugs, security issues, and performance problems
2. Suggest improvements following best practices
3. Explain your reasoning clearly
4. Be constructive and educational in feedback

When reviewing code:
- Check for common vulnerabilities (injection, XSS, etc.)
- Identify logic errors and edge cases
- Suggest cleaner, more readable alternatives
- Note any missing error handling"""


@register_agent("code_review")
def create_code_review_agent(settings: Settings, model_name: str) -> Agent:
    """Create a code review agent.

    This agent is specialized for code analysis and review tasks.

    Args:
        settings: Mamba Server settings.
        model_name: Model to use.

    Returns:
        Configured code review Agent.
    """
    from mamba_agents import Agent, AgentConfig

    agent_settings = _create_agent_settings(settings, model_name)

    config = AgentConfig(
        system_prompt=CODE_REVIEW_SYSTEM_PROMPT,
        track_context=False,
        auto_compact=False,
        graceful_tool_errors=True,
    )

    agent = Agent(
        model_name,
        settings=agent_settings,
        config=config,
    )

    # Register code-review-specific tools
    @agent.tool_plain
    async def analyze_complexity(code: str, language: str) -> dict[str, Any]:
        """Analyze code complexity metrics.

        Args:
            code: Source code to analyze.
            language: Programming language.

        Returns:
            Complexity analysis results.
        """
        # Placeholder - would integrate with actual analysis tools
        return {
            "language": language,
            "lines": len(code.splitlines()),
            "analysis": "Complexity analysis not yet connected",
        }

    return agent


MAIN_SYSTEM_PROMPT = """You are a helpful, harmless, and honest AI assistant.

Your capabilities:
- Engaging in natural, helpful conversations
- Answering questions clearly and accurately
- Helping with a wide variety of tasks
- Asking clarifying questions when needed

Always be helpful while being truthful. If you're unsure about something, say so."""


@register_agent("main")
def create_main_agent(settings: Settings, model_name: str) -> Agent:
    """Create the main general-purpose agent.

    This agent is designed for general conversation and assistance.

    Args:
        settings: Mamba Server settings.
        model_name: Model to use.

    Returns:
        Configured main Agent.
    """
    from ._agent import get_agent

    agent = get_agent(settings=settings,
                        model_name=model_name)

    # Register placeholder tool for future expansion
    @agent.tool_plain
    async def get_current_context(topic: str) -> dict[str, Any]:
        """Get additional context about a topic.

        Args:
            topic: Topic to get context for.

        Returns:
            Context information.
        """
        # Placeholder - would integrate with context service
        return {
            "topic": topic,
            "context": [],
            "message": "Context service not yet connected",
        }

    return agent


# ============================================================================
# Message Conversion
# ============================================================================


def convert_ui_messages_to_dicts(messages: list[UIMessage]) -> list[dict[str, Any]]:
    """Convert UIMessage format to dict format for Mamba Agents.

    Transforms Mamba Server's UIMessage format into the dict format
    expected by mamba_agents.agent.message_utils.dicts_to_model_messages().

    Args:
        messages: List of UIMessage objects from the request.

    Returns:
        List of message dictionaries compatible with Mamba Agents.
    """
    result: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            result.append({
                "role": "system",
                "content": _extract_text(msg.parts),
            })

        elif msg.role == "user":
            result.append({
                "role": "user",
                "content": _extract_text(msg.parts),
            })

        elif msg.role == "assistant":
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": _extract_text(msg.parts),
            }

            # Extract tool calls (without results)
            tool_calls = []
            for part in msg.parts:
                if isinstance(part, ToolInvocationPart) and part.result is None:
                    tool_calls.append({
                        "id": part.toolCallId,
                        "type": "function",
                        "function": {
                            "name": part.toolName,
                            "arguments": json.dumps(part.args),
                        },
                    })

            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls

            result.append(assistant_msg)

            # Add tool results as separate messages
            for part in msg.parts:
                if isinstance(part, ToolInvocationPart) and part.result is not None:
                    result.append({
                        "role": "tool",
                        "tool_call_id": part.toolCallId,
                        "name": part.toolName,
                        "content": (
                            json.dumps(part.result)
                            if isinstance(part.result, dict)
                            else str(part.result)
                        ),
                    })

    return result


def _extract_text(parts: list) -> str:
    """Extract text content from message parts.

    Args:
        parts: List of message parts.

    Returns:
        Concatenated text content.
    """
    texts = []
    for part in parts:
        if isinstance(part, TextPart):
            texts.append(part.text)
    return " ".join(texts) if texts else ""


# ============================================================================
# Streaming Adapter
# ============================================================================


async def stream_mamba_agent_events(
    agent: Agent,
    prompt: str,
    message_history: list[dict[str, Any]] | None = None,
    text_id: str = "text-1",
) -> AsyncIterator[TextDeltaEvent | ToolInputAvailableEvent | ToolOutputAvailableEvent | ErrorEvent]:
    """Stream events from a Mamba Agent, converting to StreamEvent format.

    Adapts the Mamba Agents streaming interface to emit events compatible
    with Mamba Server's SSE protocol (AI SDK UIMessageChunk format).

    Events are emitted in real-time as they occur:
    - TextDeltaEvent: As text is generated
    - ToolInputAvailableEvent: When a tool is called (with arguments)
    - ToolOutputAvailableEvent: When a tool returns (with result)

    Args:
        agent: Configured Mamba Agent instance.
        prompt: User prompt to process.
        message_history: Optional message history as dict list.
        text_id: ID to use for text block events.

    Yields:
        StreamEvent objects in real-time as the agent executes.
    """
    from mamba_agents import (
        AgentRunResultEvent,
        FunctionToolCallEvent,
        FunctionToolResultEvent,
        PartDeltaEvent,
        TextPartDelta,
    )
    from mamba_agents.agent.message_utils import dicts_to_model_messages
    from pydantic_ai.messages import ModelMessage

    # Convert dict history to ModelMessage format if provided
    history: list[ModelMessage] | None = None
    if message_history:
        history = dicts_to_model_messages(message_history)

    # Track emitted tool calls to avoid duplicates
    emitted_tool_calls: set[str] = set()

    try:
        async for event in agent.run_stream_events(prompt, message_history=history):
            # Handle text deltas
            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta):
                    content = event.delta.content_delta
                    if content:
                        yield TextDeltaEvent(id=text_id, delta=content)

            # Handle tool being called (with arguments)
            elif isinstance(event, FunctionToolCallEvent):
                tool_call_id = event.part.tool_call_id
                if not tool_call_id:
                    logger.warning(
                        f"FunctionToolCallEvent missing tool_call_id for tool "
                        f"'{event.part.tool_name}', skipping"
                    )
                    continue
                if tool_call_id in emitted_tool_calls:
                    logger.debug(f"Duplicate tool call {tool_call_id}, skipping")
                    continue
                emitted_tool_calls.add(tool_call_id)

                # Parse args - they may be string (JSON) or dict
                args = event.part.args
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                elif not isinstance(args, dict):
                    args = {}

                yield ToolInputAvailableEvent(
                    toolCallId=tool_call_id,
                    toolName=event.part.tool_name,
                    input=args,
                )

            # Handle tool result
            elif isinstance(event, FunctionToolResultEvent):
                tool_call_id = event.tool_call_id
                if not tool_call_id:
                    logger.warning(
                        "FunctionToolResultEvent missing tool_call_id, skipping"
                    )
                    continue

                # Convert result content to appropriate format
                result_content = event.result.content if event.result else None
                if result_content is None:
                    output = {"result": None}
                elif isinstance(result_content, dict):
                    output = result_content
                elif isinstance(result_content, str):
                    # Try to parse as JSON, otherwise wrap as string result
                    try:
                        output = json.loads(result_content)
                    except json.JSONDecodeError:
                        output = {"result": result_content}
                else:
                    output = {"result": str(result_content)}

                yield ToolOutputAvailableEvent(
                    toolCallId=tool_call_id,
                    output=output,
                )

            # Log completion (text was already streamed via PartDeltaEvent)
            elif isinstance(event, AgentRunResultEvent):
                output_preview = str(event.result.output)[:100] if event.result.output else "None"
                logger.debug(f"Agent run completed with output: {output_preview}...")

    except Exception as e:
        log_error(e, context={"component": "mamba_agent_streaming"})
        error_code = classify_exception(e)
        yield create_stream_error_event(code=error_code)


async def run_mamba_agent(
    agent: Agent,
    prompt: str,
    message_history: list[dict[str, Any]] | None = None,
) -> str:
    """Run Mamba Agent non-streaming and return the text output.

    This is the default execution mode for Mamba agents. It awaits the
    complete result before returning, which is simpler and more reliable
    than streaming for most use cases.

    Args:
        agent: Configured Mamba Agent instance.
        prompt: User prompt to process.
        message_history: Optional message history as dict list.

    Returns:
        The agent's text response.

    Raises:
        Exception: Propagates any errors from the agent.
    """
    from mamba_agents.agent.message_utils import dicts_to_model_messages
    from pydantic_ai.messages import ModelMessage

    # Convert dict history to ModelMessage format if provided
    history: list[ModelMessage] | None = None
    if message_history:
        history = dicts_to_model_messages(message_history)

    # Run agent (non-streaming)
    result = await agent.run(prompt, message_history=history)

    # Return just the text output
    return str(result.output) if result.output else ""
