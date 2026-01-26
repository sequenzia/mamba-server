"""Tests for health check endpoint handler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from mamba import __version__
from mamba.api.handlers.health import (
    LATENCY_DEGRADED_MS,
    check_openai_health,
    determine_overall_status,
    router,
)
from mamba.config import AuthSettings, HealthSettings, OpenAISettings, Settings
from mamba.main import create_app
from mamba.models.health import ComponentHealth, HealthStatus


class TestDetermineOverallStatus:
    """Tests for determine_overall_status function."""

    def test_all_healthy(self):
        """Test all healthy components result in healthy status."""
        checks = {
            "openai": ComponentHealth(status=HealthStatus.HEALTHY),
            "other": ComponentHealth(status=HealthStatus.HEALTHY),
        }
        assert determine_overall_status(checks) == HealthStatus.HEALTHY

    def test_any_degraded(self):
        """Test any degraded component results in degraded status."""
        checks = {
            "openai": ComponentHealth(status=HealthStatus.HEALTHY),
            "other": ComponentHealth(status=HealthStatus.DEGRADED),
        }
        assert determine_overall_status(checks) == HealthStatus.DEGRADED

    def test_any_unhealthy(self):
        """Test any unhealthy component results in unhealthy status."""
        checks = {
            "openai": ComponentHealth(status=HealthStatus.UNHEALTHY),
            "other": ComponentHealth(status=HealthStatus.HEALTHY),
        }
        assert determine_overall_status(checks) == HealthStatus.UNHEALTHY

    def test_unhealthy_takes_precedence(self):
        """Test unhealthy takes precedence over degraded."""
        checks = {
            "openai": ComponentHealth(status=HealthStatus.UNHEALTHY),
            "other": ComponentHealth(status=HealthStatus.DEGRADED),
        }
        assert determine_overall_status(checks) == HealthStatus.UNHEALTHY

    def test_empty_checks(self):
        """Test empty checks results in healthy."""
        assert determine_overall_status({}) == HealthStatus.HEALTHY


class TestCheckOpenaiHealth:
    """Tests for check_openai_health function."""

    @pytest.fixture
    def settings_with_api_key(self):
        """Settings with OpenAI API key configured."""
        return Settings(
            openai=OpenAISettings(api_key="sk-test-key"),
            health=HealthSettings(openai_check_enabled=True, timeout_seconds=5),
            auth=AuthSettings(mode="none"),
        )

    @pytest.fixture
    def settings_without_api_key(self, monkeypatch):
        """Settings without OpenAI API key."""
        # Clear OPENAI_API_KEY from environment
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        return Settings(
            openai=OpenAISettings(api_key=""),
            health=HealthSettings(openai_check_enabled=True),
            auth=AuthSettings(mode="none"),
        )

    @pytest.fixture
    def settings_check_disabled(self):
        """Settings with health check disabled."""
        return Settings(
            openai=OpenAISettings(api_key="sk-test"),
            health=HealthSettings(openai_check_enabled=False),
            auth=AuthSettings(mode="none"),
        )

    @pytest.mark.asyncio
    async def test_check_disabled(self, settings_check_disabled):
        """Test check returns healthy when disabled."""
        result = await check_openai_health(settings_check_disabled)
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Check disabled"

    @pytest.mark.asyncio
    async def test_missing_api_key(self, settings_without_api_key):
        """Test unhealthy when API key not configured."""
        result = await check_openai_health(settings_without_api_key)
        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_successful_check(self, settings_with_api_key):
        """Test healthy status on successful API call."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await check_openai_health(settings_with_api_key)
            assert result.status == HealthStatus.HEALTHY
            assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, settings_with_api_key):
        """Test unhealthy on 401 response."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await check_openai_health(settings_with_api_key)
            assert result.status == HealthStatus.UNHEALTHY
            assert "Invalid API key" in result.error

    @pytest.mark.asyncio
    async def test_connection_timeout(self, settings_with_api_key):
        """Test unhealthy on timeout."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            result = await check_openai_health(settings_with_api_key)
            assert result.status == HealthStatus.UNHEALTHY
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, settings_with_api_key):
        """Test unhealthy on connection error."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            result = await check_openai_health(settings_with_api_key)
            assert result.status == HealthStatus.UNHEALTHY
            assert "Connection failed" in result.error


class TestHealthEndpoint:
    """Integration tests for health endpoints."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Create test client with mocked health check."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        settings = Settings(
            health=HealthSettings(openai_check_enabled=False),
        )
        app = create_app(settings)
        return TestClient(app)

    def test_health_endpoint_returns_200(self, client):
        """Test health endpoint returns 200 when healthy."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        """Test health response has correct structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "checks" in data
        assert data["version"] == __version__

    def test_health_timestamp_format(self, client):
        """Test timestamp is ISO 8601 format."""
        response = client.get("/health")
        data = response.json()

        # Should be parseable as datetime
        timestamp = data["timestamp"]
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    def test_liveness_endpoint(self, client):
        """Test liveness probe endpoint."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_endpoint(self, client):
        """Test readiness probe endpoint."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestHealthEndpointUnhealthy:
    """Tests for unhealthy scenarios."""

    @pytest.fixture
    def unhealthy_client(self, monkeypatch):
        """Create client that simulates unhealthy state."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Patch the check function to return unhealthy
        async def mock_unhealthy_check(settings):
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                error="Mock failure",
            )

        with patch(
            "mamba.api.handlers.health.check_openai_health", mock_unhealthy_check
        ):
            settings = Settings(health=HealthSettings(openai_check_enabled=True))
            app = create_app(settings)
            yield TestClient(app)

    def test_unhealthy_returns_503(self, unhealthy_client):
        """Test unhealthy status returns 503."""
        response = unhealthy_client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
