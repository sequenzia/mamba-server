"""Tests for title generation endpoint handler."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mamba.api.handlers.title import router, generate_title, TITLE_PROMPT
from mamba.config import Settings, TitleSettings
from mamba.models.title import TitleGenerationRequest, TitleGenerationResponse


def create_test_app(settings: Settings) -> FastAPI:
    """Create test app with title router."""
    from mamba.api.deps import get_settings_dependency

    app = FastAPI()
    app.include_router(router)

    # Override settings dependency
    app.dependency_overrides[get_settings_dependency] = lambda: settings

    return app


@pytest.fixture
def mock_settings(monkeypatch):
    """Create test settings with title config."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = Settings()
    return settings


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    agent = MagicMock()
    agent.run = AsyncMock()
    return agent


class TestTitlePrompt:
    """Tests for title prompt template."""

    def test_prompt_includes_max_length(self):
        """Test that prompt template includes max_length placeholder."""
        assert "{max_length}" in TITLE_PROMPT

    def test_prompt_includes_user_message(self):
        """Test that prompt template includes user_message placeholder."""
        assert "{user_message}" in TITLE_PROMPT

    def test_prompt_formatting(self):
        """Test that prompt can be formatted correctly."""
        formatted = TITLE_PROMPT.format(
            max_length=50,
            user_message="Hello, how do I use Python?",
        )
        assert "50" in formatted
        assert "Hello, how do I use Python?" in formatted


class TestGenerateTitleHandler:
    """Tests for generate_title handler function."""

    @pytest.mark.asyncio
    async def test_returns_title_on_success(self, mock_settings, mock_agent):
        """Returns generated title with useFallback=False."""
        mock_agent.run.return_value = "Python binary search trees"

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="How do I implement a BST?",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == "Python binary search trees"
        assert response.useFallback is False

    @pytest.mark.asyncio
    async def test_returns_fallback_on_timeout(self, mock_settings, mock_agent):
        """Returns useFallback=True on timeout."""
        mock_agent.run.side_effect = asyncio.TimeoutError()

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="Hello",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == ""
        assert response.useFallback is True

    @pytest.mark.asyncio
    async def test_returns_fallback_on_api_error(self, mock_settings, mock_agent):
        """Returns useFallback=True on API error."""
        mock_agent.run.side_effect = Exception("API Error")

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="Hello",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == ""
        assert response.useFallback is True

    @pytest.mark.asyncio
    async def test_cleans_title_with_quotes(self, mock_settings, mock_agent):
        """Test that quotes are removed from LLM response."""
        mock_agent.run.return_value = '"Python Tutorial Question"'

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="How do I learn Python?",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == "Python Tutorial Question"
        assert not response.title.startswith('"')
        assert not response.title.endswith('"')

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_title(self, mock_settings, mock_agent):
        """Test that whitespace is stripped from LLM response."""
        mock_agent.run.return_value = "  Python Help  "

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="Help with Python",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == "Python Help"

    @pytest.mark.asyncio
    async def test_truncates_long_title(self, mock_settings, mock_agent):
        """Test that long titles are truncated."""
        # Create a title that exceeds max_length (default 50)
        long_title = "This is a very long title that definitely exceeds the maximum allowed length for titles"
        mock_agent.run.return_value = long_title

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="Tell me everything",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        # Should be truncated to max_length (50) + "..." = 53 max
        assert len(response.title) <= 53
        assert response.title.endswith("...")

    @pytest.mark.asyncio
    async def test_uses_configured_model(self, mock_settings, mock_agent):
        """Test that the configured model is used."""
        mock_agent.run.return_value = "Test Title"

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ) as mock_create:
            await generate_title(
                TitleGenerationRequest(
                    userMessage="Test message",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        # Verify create_agent was called with correct model
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["model_name"] == mock_settings.title.model
        assert call_kwargs.kwargs["enable_tools"] is False

    @pytest.mark.asyncio
    async def test_handles_empty_title_from_llm(self, mock_settings, mock_agent):
        """Test handling when LLM returns empty string."""
        mock_agent.run.return_value = ""

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="Hello",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == ""
        assert response.useFallback is False  # Empty is still a valid response

    @pytest.mark.asyncio
    async def test_handles_unicode_in_response(self, mock_settings, mock_agent):
        """Test handling unicode characters in LLM response."""
        mock_agent.run.return_value = "日本語の質問 🎉"

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = await generate_title(
                TitleGenerationRequest(
                    userMessage="日本語で教えてください",
                    conversationId="conv_123",
                ),
                settings=mock_settings,
            )

        assert response.title == "日本語の質問 🎉"
        assert response.useFallback is False


class TestTitleEndpointValidation:
    """Tests for request validation at endpoint level."""

    def test_rejects_empty_user_message(self, mock_settings):
        """Test that empty userMessage is rejected with 422."""
        app = create_test_app(mock_settings)
        client = TestClient(app)

        response = client.post(
            "/title/generate",
            json={
                "userMessage": "",
                "conversationId": "conv_123",
            },
        )

        assert response.status_code == 422

    def test_rejects_empty_conversation_id(self, mock_settings):
        """Test that empty conversationId is rejected with 422."""
        app = create_test_app(mock_settings)
        client = TestClient(app)

        response = client.post(
            "/title/generate",
            json={
                "userMessage": "Hello",
                "conversationId": "",
            },
        )

        assert response.status_code == 422

    def test_rejects_missing_user_message(self, mock_settings):
        """Test that missing userMessage is rejected with 422."""
        app = create_test_app(mock_settings)
        client = TestClient(app)

        response = client.post(
            "/title/generate",
            json={
                "conversationId": "conv_123",
            },
        )

        assert response.status_code == 422

    def test_rejects_missing_conversation_id(self, mock_settings):
        """Test that missing conversationId is rejected with 422."""
        app = create_test_app(mock_settings)
        client = TestClient(app)

        response = client.post(
            "/title/generate",
            json={
                "userMessage": "Hello",
            },
        )

        assert response.status_code == 422

    def test_accepts_max_length_user_message(self, mock_settings, mock_agent):
        """Test that max length userMessage (10000 chars) is accepted."""
        mock_agent.run.return_value = "Test Title"

        app = create_test_app(mock_settings)
        client = TestClient(app)

        long_message = "a" * 10000

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/title/generate",
                json={
                    "userMessage": long_message,
                    "conversationId": "conv_123",
                },
            )

        assert response.status_code == 200

    def test_rejects_over_max_length_user_message(self, mock_settings):
        """Test that userMessage over 10000 chars is rejected."""
        app = create_test_app(mock_settings)
        client = TestClient(app)

        long_message = "a" * 10001

        response = client.post(
            "/title/generate",
            json={
                "userMessage": long_message,
                "conversationId": "conv_123",
            },
        )

        assert response.status_code == 422


class TestTitleEndpointIntegration:
    """Integration tests for the title endpoint."""

    def test_endpoint_returns_json_response(self, mock_settings, mock_agent):
        """Test that endpoint returns proper JSON response."""
        mock_agent.run.return_value = "Test Title"

        app = create_test_app(mock_settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/title/generate",
                json={
                    "userMessage": "Hello, world!",
                    "conversationId": "conv_123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "title" in data
        assert "useFallback" in data
        assert data["title"] == "Test Title"
        assert data["useFallback"] is False

    def test_endpoint_returns_fallback_on_error(self, mock_settings, mock_agent):
        """Test that endpoint returns fallback response on error."""
        mock_agent.run.side_effect = Exception("API Error")

        app = create_test_app(mock_settings)
        client = TestClient(app)

        with patch(
            "mamba.api.handlers.title.create_agent", return_value=mock_agent
        ):
            response = client.post(
                "/title/generate",
                json={
                    "userMessage": "Hello, world!",
                    "conversationId": "conv_123",
                },
            )

        # Should still return 200 with fallback (graceful degradation)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == ""
        assert data["useFallback"] is True

    def test_endpoint_never_returns_500(self, mock_settings, mock_agent):
        """Test that endpoint never returns 500 for operational errors."""
        # Various error types that shouldn't cause 500
        error_types = [
            Exception("Generic error"),
            asyncio.TimeoutError(),
            RuntimeError("Runtime error"),
            ConnectionError("Connection failed"),
        ]

        app = create_test_app(mock_settings)
        client = TestClient(app)

        for error in error_types:
            mock_agent.run.side_effect = error

            with patch(
                "mamba.api.handlers.title.create_agent", return_value=mock_agent
            ):
                response = client.post(
                    "/title/generate",
                    json={
                        "userMessage": "Hello",
                        "conversationId": "conv_123",
                    },
                )

            # Should always return 200 with fallback, never 500
            assert response.status_code == 200, f"Failed for error: {error}"
            data = response.json()
            assert data["useFallback"] is True
