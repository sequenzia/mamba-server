"""Tests for authentication middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mamba.config import ApiKeyConfig, AuthSettings, JwtSettings, Settings
from mamba.middleware.auth import AuthenticationMiddleware


def create_test_app(settings: Settings) -> FastAPI:
    """Create test app with auth middleware."""
    app = FastAPI()
    app.add_middleware(AuthenticationMiddleware, settings=settings)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    return app


class TestAuthModeNone:
    """Tests for auth mode 'none'."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Create test client with auth disabled."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(auth=AuthSettings(mode="none"))
        app = create_test_app(settings)
        return TestClient(app)

    def test_allows_requests_without_auth(self, client):
        """Test requests are allowed without authentication."""
        response = client.get("/test")
        assert response.status_code == 200

    def test_ignores_auth_headers(self, client):
        """Test auth headers are ignored in none mode."""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 200

    def test_ignores_api_key_header(self, client):
        """Test X-API-Key header is ignored in none mode."""
        response = client.get(
            "/test",
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 200


class TestAuthModeApiKey:
    """Tests for auth mode 'api_key'."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Create test client with API key auth."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(
            auth=AuthSettings(
                mode="api_key",
                api_keys=[
                    ApiKeyConfig(key="valid-api-key-1", name="test-key-1"),
                    ApiKeyConfig(key="valid-api-key-2", name="test-key-2"),
                ],
            )
        )
        app = create_test_app(settings)
        return TestClient(app)

    def test_valid_api_key_in_header(self, client):
        """Test valid API key in X-API-Key header."""
        response = client.get(
            "/test",
            headers={"X-API-Key": "valid-api-key-1"},
        )
        assert response.status_code == 200

    def test_valid_api_key_in_bearer(self, client):
        """Test valid API key in Authorization Bearer header."""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer valid-api-key-2"},
        )
        assert response.status_code == 200

    def test_invalid_api_key_rejected(self, client):
        """Test invalid API key is rejected."""
        response = client.get(
            "/test",
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 401

    def test_missing_api_key_rejected(self, client):
        """Test missing API key is rejected."""
        response = client.get("/test")
        assert response.status_code == 401

    def test_health_endpoint_bypasses_auth(self, client):
        """Test health endpoint doesn't require auth."""
        response = client.get("/health")
        assert response.status_code == 200


class TestAuthModeJwt:
    """Tests for auth mode 'jwt'."""

    @pytest.fixture
    def jwt_secret(self):
        """JWT secret for testing."""
        return "test-secret-key-for-jwt"

    @pytest.fixture
    def client(self, jwt_secret, monkeypatch):
        """Create test client with JWT auth."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(
            auth=AuthSettings(
                mode="jwt",
                jwt=JwtSettings(
                    secret=jwt_secret,
                    algorithm="HS256",
                    issuer="test-issuer",
                    audience="test-audience",
                ),
            )
        )
        app = create_test_app(settings)
        return TestClient(app)

    def test_valid_jwt_accepted(self, client, jwt_secret):
        """Test valid JWT is accepted."""
        import jwt
        from datetime import datetime, timedelta, timezone

        token = jwt.encode(
            {
                "sub": "user123",
                "iss": "test-issuer",
                "aud": "test-audience",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            jwt_secret,
            algorithm="HS256",
        )

        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_expired_jwt_rejected(self, client, jwt_secret):
        """Test expired JWT is rejected."""
        import jwt
        from datetime import datetime, timedelta, timezone

        token = jwt.encode(
            {
                "sub": "user123",
                "iss": "test-issuer",
                "aud": "test-audience",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            jwt_secret,
            algorithm="HS256",
        )

        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_invalid_jwt_rejected(self, client):
        """Test invalid JWT is rejected."""
        response = client.get(
            "/test",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert response.status_code == 401

    def test_missing_bearer_prefix_rejected(self, client, jwt_secret):
        """Test missing Bearer prefix is rejected."""
        import jwt
        from datetime import datetime, timedelta, timezone

        token = jwt.encode(
            {
                "sub": "user123",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            jwt_secret,
            algorithm="HS256",
        )

        response = client.get(
            "/test",
            headers={"Authorization": token},  # Missing "Bearer " prefix
        )
        assert response.status_code == 401


class TestHealthEndpointBypass:
    """Tests for health endpoint auth bypass."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Create test client with strict auth."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(
            auth=AuthSettings(
                mode="api_key",
                api_keys=[ApiKeyConfig(key="secret-key", name="test")],
            )
        )
        app = create_test_app(settings)

        @app.get("/health/live")
        async def liveness():
            return {"status": "alive"}

        @app.get("/health/ready")
        async def readiness():
            return {"status": "ready"}

        return TestClient(app)

    def test_health_bypasses_auth(self, client):
        """Test /health bypasses auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_live_bypasses_auth(self, client):
        """Test /health/live bypasses auth."""
        response = client.get("/health/live")
        assert response.status_code == 200

    def test_health_ready_bypasses_auth(self, client):
        """Test /health/ready bypasses auth."""
        response = client.get("/health/ready")
        assert response.status_code == 200
