"""Tests for models endpoint handler."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mamba.api.handlers.models import router
from mamba.config import ModelConfig, Settings


def create_test_app(settings: Settings) -> FastAPI:
    """Create test app with models router."""
    from mamba.api.deps import get_settings_dependency

    app = FastAPI()
    app.include_router(router)

    # Override settings dependency
    app.dependency_overrides[get_settings_dependency] = lambda: settings

    return app


class TestListModels:
    """Tests for GET /models endpoint."""

    @pytest.fixture
    def settings_with_models(self, monkeypatch):
        """Create settings with configured models."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        return Settings(
            models=[
                ModelConfig(
                    id="openai/gpt-4o",
                    name="GPT-4o",
                    provider="openai",
                    openai_model="gpt-4o",
                    description="Most capable model",
                    context_window=128000,
                    supports_tools=True,
                ),
                ModelConfig(
                    id="openai/gpt-4o-mini",
                    name="GPT-4o Mini",
                    provider="openai",
                    openai_model="gpt-4o-mini",
                    description="Fast and efficient",
                    context_window=128000,
                    supports_tools=True,
                ),
            ]
        )

    @pytest.fixture
    def settings_default_models(self, monkeypatch):
        """Create settings with default models (empty list triggers defaults)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        # Settings with empty models list will trigger default models
        return Settings(models=[])

    def test_returns_configured_models(self, settings_with_models):
        """Test returns all configured models."""
        app = create_test_app(settings_with_models)
        client = TestClient(app)

        response = client.get("/models")

        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 2

    def test_model_fields_present(self, settings_with_models):
        """Test all model fields are present in response."""
        app = create_test_app(settings_with_models)
        client = TestClient(app)

        response = client.get("/models")
        data = response.json()

        # Find the gpt-4o model in the response
        gpt4o_model = next((m for m in data["models"] if m["id"] == "openai/gpt-4o"), None)
        assert gpt4o_model is not None

        # Check all required fields are present with correct types
        assert gpt4o_model["id"] == "openai/gpt-4o"
        assert gpt4o_model["name"] == "GPT-4o"
        assert gpt4o_model["provider"] == "openai"
        assert isinstance(gpt4o_model["description"], str)
        assert gpt4o_model["context_window"] == 128000
        assert gpt4o_model["supports_tools"] is True

    def test_default_models_returned(self, settings_default_models):
        """Test returns default models when none explicitly configured."""
        app = create_test_app(settings_default_models)
        client = TestClient(app)

        response = client.get("/models")

        assert response.status_code == 200
        data = response.json()
        # Default models should be returned
        assert len(data["models"]) > 0

    def test_response_matches_spec_format(self, settings_with_models):
        """Test response format matches ModelsResponse schema."""
        app = create_test_app(settings_with_models)
        client = TestClient(app)

        response = client.get("/models")
        data = response.json()

        # Response should have 'models' key with list
        assert "models" in data
        assert isinstance(data["models"], list)


class TestModelInfoFields:
    """Tests for ModelInfo response fields."""

    def test_response_contains_required_fields(self, monkeypatch):
        """Test response models contain all required fields."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(
            models=[
                ModelConfig(
                    id="test/model",
                    name="Test Model",
                    provider="test",
                    openai_model="test-model",
                ),
            ]
        )
        app = create_test_app(settings)
        client = TestClient(app)

        response = client.get("/models")
        data = response.json()

        # Find our test model
        test_model = next((m for m in data["models"] if m["id"] == "test/model"), None)
        assert test_model is not None

        # Required fields should be present
        assert "id" in test_model
        assert "name" in test_model
        assert "provider" in test_model
        assert "supports_tools" in test_model

        # Optional fields should be present but may be null
        assert "description" in test_model
        assert "context_window" in test_model

    def test_supports_tools_defaults_true(self, monkeypatch):
        """Test supports_tools defaults to True."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(
            models=[
                ModelConfig(
                    id="test/model",
                    name="Test Model",
                    provider="test",
                    openai_model="test-model",
                ),
            ]
        )
        app = create_test_app(settings)
        client = TestClient(app)

        response = client.get("/models")
        data = response.json()

        # Find our test model
        test_model = next((m for m in data["models"] if m["id"] == "test/model"), None)
        assert test_model is not None
        assert test_model["supports_tools"] is True


class TestModelsEndpointIntegration:
    """Integration tests for models endpoint with full app."""

    @pytest.fixture
    def full_app_client(self, monkeypatch):
        """Create test client with full app."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from mamba.main import create_app

        settings = Settings(
            models=[
                ModelConfig(
                    id="openai/gpt-4o",
                    name="GPT-4o",
                    provider="openai",
                    openai_model="gpt-4o",
                ),
            ]
        )
        app = create_app(settings)
        return TestClient(app)

    def test_models_endpoint_accessible(self, full_app_client):
        """Test /models endpoint is accessible in full app."""
        response = full_app_client.get("/models")
        assert response.status_code == 200

    def test_returns_json_content_type(self, full_app_client):
        """Test response has JSON content type."""
        response = full_app_client.get("/models")
        assert "application/json" in response.headers["content-type"]
