"""Tests for title generation request and response models."""

import pytest
from pydantic import ValidationError

from mamba.models.title import TitleGenerationRequest, TitleGenerationResponse


class TestTitleGenerationRequest:
    """Tests for TitleGenerationRequest model."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = TitleGenerationRequest(
            userMessage="Hello, can you help me with Python?",
            conversationId="conv_123",
        )
        assert request.userMessage == "Hello, can you help me with Python?"
        assert request.conversationId == "conv_123"

    def test_empty_user_message_rejected(self):
        """Test empty userMessage is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleGenerationRequest(userMessage="", conversationId="conv_123")
        assert "userMessage" in str(exc_info.value)

    def test_empty_conversation_id_rejected(self):
        """Test empty conversationId is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleGenerationRequest(userMessage="Hello", conversationId="")
        assert "conversationId" in str(exc_info.value)

    def test_missing_user_message_rejected(self):
        """Test missing userMessage is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleGenerationRequest(conversationId="conv_123")  # type: ignore
        assert "userMessage" in str(exc_info.value)

    def test_missing_conversation_id_rejected(self):
        """Test missing conversationId is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleGenerationRequest(userMessage="Hello")  # type: ignore
        assert "conversationId" in str(exc_info.value)

    def test_max_length_user_message_accepted(self):
        """Test userMessage at max length (10000) is accepted."""
        long_message = "a" * 10000
        request = TitleGenerationRequest(
            userMessage=long_message,
            conversationId="conv_123",
        )
        assert len(request.userMessage) == 10000

    def test_over_max_length_user_message_rejected(self):
        """Test userMessage over max length is rejected."""
        long_message = "a" * 10001
        with pytest.raises(ValidationError) as exc_info:
            TitleGenerationRequest(
                userMessage=long_message,
                conversationId="conv_123",
            )
        assert "userMessage" in str(exc_info.value)

    def test_single_char_user_message_accepted(self):
        """Test single character userMessage is accepted."""
        request = TitleGenerationRequest(
            userMessage="a",
            conversationId="conv_123",
        )
        assert request.userMessage == "a"

    def test_single_char_conversation_id_accepted(self):
        """Test single character conversationId is accepted."""
        request = TitleGenerationRequest(
            userMessage="Hello",
            conversationId="a",
        )
        assert request.conversationId == "a"

    def test_serialization(self):
        """Test JSON serialization."""
        request = TitleGenerationRequest(
            userMessage="Hello",
            conversationId="conv_123",
        )
        data = request.model_dump()
        assert data == {
            "userMessage": "Hello",
            "conversationId": "conv_123",
        }

    def test_unicode_content_accepted(self):
        """Test unicode content is accepted."""
        request = TitleGenerationRequest(
            userMessage="こんにちは 🎉 مرحبا",
            conversationId="conv_123",
        )
        assert "🎉" in request.userMessage


class TestTitleGenerationResponse:
    """Tests for TitleGenerationResponse model."""

    def test_valid_response(self):
        """Test valid response creation."""
        response = TitleGenerationResponse(
            title="Python Help Request",
            useFallback=False,
        )
        assert response.title == "Python Help Request"
        assert response.useFallback is False

    def test_fallback_response(self):
        """Test fallback response."""
        response = TitleGenerationResponse(
            title="New Conversation",
            useFallback=True,
        )
        assert response.title == "New Conversation"
        assert response.useFallback is True

    def test_empty_title_accepted(self):
        """Test empty title is accepted (validation happens elsewhere)."""
        response = TitleGenerationResponse(
            title="",
            useFallback=True,
        )
        assert response.title == ""

    def test_serialization(self):
        """Test JSON serialization."""
        response = TitleGenerationResponse(
            title="Test Title",
            useFallback=False,
        )
        data = response.model_dump()
        assert data == {
            "title": "Test Title",
            "useFallback": False,
        }

    def test_missing_title_rejected(self):
        """Test missing title is rejected."""
        with pytest.raises(ValidationError):
            TitleGenerationResponse(useFallback=False)  # type: ignore

    def test_missing_use_fallback_rejected(self):
        """Test missing useFallback is rejected."""
        with pytest.raises(ValidationError):
            TitleGenerationResponse(title="Test")  # type: ignore
