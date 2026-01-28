"""Tests for FastAPI application entry point."""

import pytest
from fastapi.testclient import TestClient

from mamba import __version__
from mamba.config import AuthSettings, CorsSettings, ServerSettings, Settings
from mamba.main import create_app


@pytest.fixture
def minimal_settings(monkeypatch):
    """Create minimal settings for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    return Settings()


@pytest.fixture
def test_client(minimal_settings):
    """Create test client with minimal settings."""
    app = create_app(minimal_settings)
    return TestClient(app, raise_server_exceptions=False)


class TestAppCreation:
    """Tests for application creation."""

    def test_app_title(self, minimal_settings):
        """Test app has correct title."""
        app = create_app(minimal_settings)
        assert app.title == "mamba-server"

    def test_app_version(self, minimal_settings):
        """Test app has correct version."""
        app = create_app(minimal_settings)
        assert app.version == __version__

    def test_app_description(self, minimal_settings):
        """Test app has description."""
        app = create_app(minimal_settings)
        assert "FastAPI" in app.description
        assert "AI chat" in app.description


class TestCorsConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_configured_origin(self, monkeypatch):
        """Test CORS allows configured origins."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        settings = Settings(
            server=ServerSettings(
                cors=CorsSettings(allowed_origins=["http://localhost:3000"])
            )
        )
        app = create_app(settings)
        client = TestClient(app)

        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_preflight_request(self, test_client):
        """Test CORS handles OPTIONS preflight requests."""
        response = test_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not return 405 Method Not Allowed
        assert response.status_code != 405


class TestRouteRegistration:
    """Tests for route registration."""

    def test_health_endpoint_exists(self, test_client):
        """Test health endpoint is registered."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_models_endpoint_exists(self, test_client):
        """Test models endpoint is registered."""
        response = test_client.get("/models")
        assert response.status_code == 200

    def test_chat_endpoint_exists(self, test_client):
        """Test chat endpoint is registered."""
        # Send empty messages to verify endpoint exists (returns 400 for empty messages)
        response = test_client.post(
            "/chat",
            json={
                "messages": [],
                "model": "openai/gpt-4o",
            },
        )
        # 400 indicates endpoint exists but request validation failed (empty messages)
        assert response.status_code == 400


class TestExceptionHandlers:
    """Tests for exception handlers."""

    def test_unhandled_exception_returns_json(self, minimal_settings):
        """Test unhandled exceptions return structured JSON."""
        app = create_app(minimal_settings)

        @app.get("/test-error")
        async def raise_error():
            raise RuntimeError("Test error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-error")

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "An unexpected error occurred"

    def test_value_error_returns_400(self, minimal_settings):
        """Test ValueError returns 400 status."""
        app = create_app(minimal_settings)

        @app.get("/test-value-error")
        async def raise_value_error():
            raise ValueError("Invalid value")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-value-error")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"] == "Invalid value"


class TestMinimalConfig:
    """Tests for app with minimal configuration."""

    def test_app_starts_with_minimal_config(self, monkeypatch):
        """Test app starts with only required settings."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        settings = Settings()
        app = create_app(settings)
        assert app is not None

    def test_app_with_auth_none(self, monkeypatch):
        """Test app starts with auth mode none."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        settings = Settings(auth=AuthSettings(mode="none"))
        app = create_app(settings)
        client = TestClient(app)

        # Should be accessible without auth
        response = client.get("/health")
        assert response.status_code == 200


class TestAppIntegration:
    """Integration tests for the application."""

    def test_server_runs(self, test_client):
        """Test server accepts requests."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_cors_headers_in_response(self, test_client):
        """Test CORS headers present in responses."""
        response = test_client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        # When origin matches, CORS headers should be present
        assert "access-control-allow-origin" in response.headers

    def test_json_response_content_type(self, test_client):
        """Test responses have JSON content type."""
        response = test_client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")
