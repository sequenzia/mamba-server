"""Pydantic AI Agent wrapper for OpenAI communication."""

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from pydantic_ai import Agent, FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mamba.config import Settings
from mamba.core.messages import extract_text_content
from mamba.core.tools import (
    SUPPORTED_TOOLS,
    TOOL_ARG_MODELS,
    GenerateCardArgs,
    GenerateChartArgs,
    GenerateCodeArgs,
    GenerateFormArgs,
)
from mamba.models.events import (
    FinishEvent,
    StreamEvent,
    TextDeltaEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from mamba.models.request import TextPart as UITextPart
from mamba.models.request import ToolInvocationPart, UIMessage

logger = logging.getLogger(__name__)


@dataclass
class ToolCallInfo:
    """Information about a tool call for tracking."""

    tool_call_id: str
    tool_name: str
    args: dict


class ChatAgent:
    """Wrapper around Pydantic AI Agent for chat completions.

    Provides:
    - OpenAI model configuration from settings
    - Message format conversion (UIMessage -> pydantic-ai format)
    - Streaming text responses
    - Tool call handling with streaming events
    """

    def __init__(
        self,
        settings: Settings,
        model_name: str | None = None,
        enable_tools: bool = False,
    ):
        """Initialize the chat agent.

        Args:
            settings: Application settings.
            model_name: Optional model name override (e.g., "gpt-4o").
                       If not provided, uses settings.openai.default_model.
            enable_tools: Whether to enable tool calling capabilities.
        """
        self.settings = settings
        self.model_name = model_name or settings.openai.default_model
        self.enable_tools = enable_tools

        # Configure OpenAI provider
        provider = OpenAIProvider(
            base_url=settings.openai.base_url,
            api_key=settings.openai.api_key,
        )

        # Create OpenAI model
        model = OpenAIChatModel(
            self.model_name,
            provider=provider,
        )

        # Create agent
        self.agent = Agent(model)

        # Register tools if enabled
        if enable_tools:
            self._register_tools()

    def convert_messages(self, messages: list[UIMessage]) -> list[ModelMessage]:
        """Convert UIMessages to pydantic-ai message format.

        Args:
            messages: List of UIMessages from the request.

        Returns:
            List of pydantic-ai ModelMessage objects.
        """
        result: list[ModelMessage] = []

        for msg in messages:
            if msg.role == "system":
                # System messages become part of a ModelRequest
                content = extract_text_content(msg.parts)
                result.append(
                    ModelRequest(
                        parts=[SystemPromptPart(content=content)],
                    )
                )

            elif msg.role == "user":
                # User messages become UserPromptPart
                content = extract_text_content(msg.parts)
                result.append(
                    ModelRequest(
                        parts=[UserPromptPart(content=content)],
                    )
                )

            elif msg.role == "assistant":
                # Assistant messages can have text and/or tool calls
                response_parts = []

                # Extract text content
                text_content = extract_text_content(msg.parts)
                if text_content:
                    response_parts.append(TextPart(content=text_content))

                # Extract tool calls (without results)
                for part in msg.parts:
                    if isinstance(part, ToolInvocationPart):
                        if part.result is None:
                            # This is a tool call
                            response_parts.append(
                                ToolCallPart(
                                    tool_name=part.toolName,
                                    args=part.args,
                                    tool_call_id=part.toolCallId,
                                )
                            )
                        else:
                            # This is a tool result - add as separate request
                            result.append(
                                ModelRequest(
                                    parts=[
                                        ToolReturnPart(
                                            tool_name=part.toolName,
                                            content=json.dumps(part.result),
                                            tool_call_id=part.toolCallId,
                                        )
                                    ],
                                )
                            )

                if response_parts:
                    result.append(ModelResponse(parts=response_parts))

        return result

    async def stream_text(
        self,
        prompt: str,
        message_history: list[UIMessage] | None = None,
    ) -> AsyncIterator[str]:
        """Stream text response from the agent.

        Args:
            prompt: The user's prompt/question.
            message_history: Optional previous conversation messages.

        Yields:
            Text delta strings as they are generated.
        """
        # Convert message history if provided
        history = None
        if message_history:
            history = self.convert_messages(message_history)

        try:
            async with self.agent.run_stream(
                prompt,
                message_history=history,
            ) as response:
                async for text in response.stream_text(delta=True):
                    yield text

        except Exception as e:
            logger.exception("Error during agent streaming")
            raise

    async def run(
        self,
        prompt: str,
        message_history: list[UIMessage] | None = None,
    ) -> str:
        """Run the agent and return complete response.

        Args:
            prompt: The user's prompt/question.
            message_history: Optional previous conversation messages.

        Returns:
            Complete text response from the agent.
        """
        # Convert message history if provided
        history = None
        if message_history:
            history = self.convert_messages(message_history)

        try:
            result = await self.agent.run(
                prompt,
                message_history=history,
            )
            return result.output

        except Exception as e:
            logger.exception("Error during agent run")
            raise

    def _register_tools(self) -> None:
        """Register display tools with the agent."""
        from pydantic_ai import RunContext

        @self.agent.tool_plain
        async def generateForm(
            title: str,
            fields: list[dict],
            description: str | None = None,
            submitLabel: str | None = None,
        ) -> dict:
            """Generate a form for user input.

            Args:
                title: Form title displayed to the user.
                fields: List of form fields with id, type, label, etc.
                description: Optional form description.
                submitLabel: Optional custom submit button label.

            Returns:
                The form arguments for client-side rendering.
            """
            return {
                "type": "form",
                "title": title,
                "description": description,
                "fields": fields,
                "submitLabel": submitLabel,
            }

        @self.agent.tool_plain
        async def generateChart(
            chartType: str,
            title: str,
            data: list[dict],
            description: str | None = None,
        ) -> dict:
            """Generate a chart visualization.

            Args:
                chartType: Type of chart (line, bar, pie, area).
                title: Chart title.
                data: List of data points with label and value.
                description: Optional chart description.

            Returns:
                The chart arguments for client-side rendering.
            """
            return {
                "type": "chart",
                "chartType": chartType,
                "title": title,
                "description": description,
                "data": data,
            }

        @self.agent.tool_plain
        async def generateCode(
            language: str,
            code: str,
            filename: str | None = None,
            editable: bool | None = None,
            showLineNumbers: bool | None = None,
        ) -> dict:
            """Generate a code block with syntax highlighting.

            Args:
                language: Programming language for syntax highlighting.
                code: The code content.
                filename: Optional filename to display.
                editable: Whether the code should be editable.
                showLineNumbers: Whether to show line numbers.

            Returns:
                The code arguments for client-side rendering.
            """
            return {
                "type": "code",
                "language": language,
                "code": code,
                "filename": filename,
                "editable": editable,
                "showLineNumbers": showLineNumbers,
            }

        @self.agent.tool_plain
        async def generateCard(
            title: str,
            description: str | None = None,
            content: str | None = None,
            media: dict | None = None,
            actions: list[dict] | None = None,
        ) -> dict:
            """Generate a card component.

            Args:
                title: Card title.
                description: Optional card description.
                content: Optional card body content.
                media: Optional media (image/video) with type, url, alt.
                actions: Optional list of action buttons.

            Returns:
                The card arguments for client-side rendering.
            """
            return {
                "type": "card",
                "title": title,
                "description": description,
                "content": content,
                "media": media,
                "actions": actions,
            }

    async def stream_events(
        self,
        prompt: str,
        message_history: list[UIMessage] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream events including text deltas, tool calls, and tool results.

        Args:
            prompt: The user's prompt/question.
            message_history: Optional previous conversation messages.

        Yields:
            StreamEvent objects (TextDeltaEvent, ToolCallEvent, ToolResultEvent).
        """
        from collections.abc import AsyncIterable

        from pydantic_ai import (
            AgentStreamEvent,
            PartDeltaEvent,
            PartStartEvent,
            TextPartDelta,
        )

        # Convert message history if provided
        history = None
        if message_history:
            history = self.convert_messages(message_history)

        # Track pending tool calls for emitting results
        pending_tool_calls: dict[str, ToolCallInfo] = {}

        async def event_handler(
            ctx,
            event_stream: AsyncIterable[AgentStreamEvent],
        ):
            """Handle agent events and track tool calls."""
            nonlocal pending_tool_calls

            async for event in event_stream:
                if isinstance(event, FunctionToolCallEvent):
                    # Track tool call for result handling
                    pending_tool_calls[event.part.tool_call_id] = ToolCallInfo(
                        tool_call_id=event.part.tool_call_id,
                        tool_name=event.part.tool_name,
                        args=event.part.args,
                    )
                elif isinstance(event, FunctionToolResultEvent):
                    # Tool result received
                    if event.tool_call_id in pending_tool_calls:
                        del pending_tool_calls[event.tool_call_id]

        try:
            async with self.agent.run_stream(
                prompt,
                message_history=history,
                event_stream_handler=event_handler,
            ) as response:
                # Stream text and emit tool events
                emitted_tool_calls: set[str] = set()

                async for text in response.stream_text(delta=True):
                    # Check for new tool calls
                    for tool_call_id, info in pending_tool_calls.items():
                        if tool_call_id not in emitted_tool_calls:
                            # Emit tool-call event
                            yield ToolCallEvent(
                                toolCallId=info.tool_call_id,
                                toolName=info.tool_name,
                                args=info.args,
                            )
                            emitted_tool_calls.add(tool_call_id)

                            # For display tools, emit tool-result immediately
                            # (the args ARE the result for rendering)
                            yield ToolResultEvent(
                                toolCallId=info.tool_call_id,
                                result=info.args,
                            )

                    # Emit text delta
                    if text:
                        yield TextDeltaEvent(textDelta=text)

        except Exception as e:
            logger.exception("Error during agent event streaming")
            raise


def create_agent(
    settings: Settings,
    model_name: str | None = None,
    enable_tools: bool = False,
) -> ChatAgent:
    """Create a new ChatAgent instance.

    Args:
        settings: Application settings.
        model_name: Optional model name override.
        enable_tools: Whether to enable tool calling capabilities.

    Returns:
        Configured ChatAgent instance.
    """
    return ChatAgent(settings, model_name, enable_tools)
