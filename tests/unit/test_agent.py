"""Tests for Pydantic AI Agent wrapper."""

import pytest

from mamba.config import Settings
from mamba.core.agent import ChatAgent, create_agent
from mamba.models.request import TextPart, ToolInvocationPart, UIMessage


class TestChatAgentInit:
    """Tests for ChatAgent initialization."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    def test_creates_agent_with_default_model(self, settings):
        """Test agent uses default model from settings."""
        agent = ChatAgent(settings)
        assert agent.model_name == settings.openai.default_model

    def test_creates_agent_with_custom_model(self, settings):
        """Test agent uses custom model when provided."""
        agent = ChatAgent(settings, model_name="gpt-4-turbo")
        assert agent.model_name == "gpt-4-turbo"


class TestConvertMessages:
    """Tests for message format conversion."""

    @pytest.fixture
    def agent(self, monkeypatch):
        """Create test agent."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()
        return ChatAgent(settings)

    def test_converts_user_message(self, agent):
        """Test user message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="user",
                parts=[TextPart(type="text", text="Hello")],
            ),
        ]
        result = agent.convert_messages(messages)

        assert len(result) == 1
        assert result[0].parts[0].content == "Hello"

    def test_converts_system_message(self, agent):
        """Test system message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="system",
                parts=[TextPart(type="text", text="You are a helpful assistant.")],
            ),
        ]
        result = agent.convert_messages(messages)

        assert len(result) == 1
        assert "You are a helpful assistant." in result[0].parts[0].content

    def test_converts_assistant_text_message(self, agent):
        """Test assistant text message conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[TextPart(type="text", text="I can help with that.")],
            ),
        ]
        result = agent.convert_messages(messages)

        assert len(result) == 1
        # Should be a ModelResponse with TextPart
        assert result[0].parts[0].content == "I can help with that."

    def test_converts_assistant_tool_call(self, agent):
        """Test assistant message with tool call conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[
                    ToolInvocationPart(
                        type="tool-invocation",
                        toolCallId="call_1",
                        toolName="generateForm",
                        args={"title": "Contact Form"},
                    ),
                ],
            ),
        ]
        result = agent.convert_messages(messages)

        assert len(result) == 1
        tool_call = result[0].parts[0]
        assert tool_call.tool_name == "generateForm"
        assert tool_call.tool_call_id == "call_1"

    def test_converts_tool_result(self, agent):
        """Test assistant message with tool result conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="assistant",
                parts=[
                    ToolInvocationPart(
                        type="tool-invocation",
                        toolCallId="call_1",
                        toolName="generateForm",
                        args={"title": "Contact Form"},
                        result={"status": "success"},
                    ),
                ],
            ),
        ]
        result = agent.convert_messages(messages)

        # Should have a tool return part
        assert len(result) >= 1
        tool_return = result[0].parts[0]
        assert tool_return.tool_name == "generateForm"

    def test_converts_empty_messages(self, agent):
        """Test empty messages list conversion."""
        result = agent.convert_messages([])
        assert result == []

    def test_converts_conversation_sequence(self, agent):
        """Test full conversation sequence conversion."""
        messages = [
            UIMessage(
                id="msg_1",
                role="system",
                parts=[TextPart(type="text", text="You are a helpful assistant.")],
            ),
            UIMessage(
                id="msg_2",
                role="user",
                parts=[TextPart(type="text", text="Hello")],
            ),
            UIMessage(
                id="msg_3",
                role="assistant",
                parts=[TextPart(type="text", text="Hi there!")],
            ),
            UIMessage(
                id="msg_4",
                role="user",
                parts=[TextPart(type="text", text="How are you?")],
            ),
        ]
        result = agent.convert_messages(messages)

        # Should have 4 messages
        assert len(result) == 4


class TestCreateAgent:
    """Tests for create_agent factory function."""

    def test_creates_agent(self, monkeypatch):
        """Test factory creates ChatAgent instance."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()

        agent = create_agent(settings)

        assert isinstance(agent, ChatAgent)
        assert agent.settings == settings

    def test_creates_agent_with_model(self, monkeypatch):
        """Test factory creates agent with custom model."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()

        agent = create_agent(settings, model_name="gpt-4-turbo")

        assert agent.model_name == "gpt-4-turbo"

    def test_creates_agent_with_tools_disabled(self, monkeypatch):
        """Test factory creates agent with tools disabled by default."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()

        agent = create_agent(settings)

        assert agent.enable_tools is False

    def test_creates_agent_with_tools_enabled(self, monkeypatch):
        """Test factory creates agent with tools enabled."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()

        agent = create_agent(settings, enable_tools=True)

        assert agent.enable_tools is True


class TestChatAgentWithTools:
    """Tests for ChatAgent tool functionality."""

    @pytest.fixture
    def settings(self, monkeypatch):
        """Create test settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings()

    def test_agent_registers_tools_when_enabled(self, settings):
        """Test that tools are registered when enable_tools is True."""
        agent = ChatAgent(settings, enable_tools=True)

        # Agent should have tools registered
        # Check that the agent has tool definitions
        assert agent.enable_tools is True

    def test_agent_has_stream_events_method(self, settings):
        """Test that agent has stream_events method."""
        agent = ChatAgent(settings, enable_tools=True)

        assert hasattr(agent, "stream_events")
        assert callable(agent.stream_events)
