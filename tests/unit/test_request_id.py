"""Tests for request ID middleware."""

import uuid

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mamba.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    generate_request_id,
    is_valid_uuid,
)


class TestIsValidUuid:
    """Tests for UUID validation."""

    def test_valid_uuid4(self):
        """Test valid UUID4 is accepted."""
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000")

    def test_valid_uuid_uppercase(self):
        """Test uppercase UUID is accepted."""
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000")

    def test_invalid_uuid_short(self):
        """Test short string is rejected."""
        assert not is_valid_uuid("not-a-uuid")

    def test_invalid_uuid_empty(self):
        """Test empty string is rejected."""
        assert not is_valid_uuid("")

    def test_invalid_uuid_none(self):
        """Test None is rejected."""
        assert not is_valid_uuid(None)  # type: ignore

    def test_valid_uuid_without_dashes(self):
        """Test UUID without dashes is also accepted (Python uuid supports both)."""
        assert is_valid_uuid("550e8400e29b41d4a716446655440000")


class TestGenerateRequestId:
    """Tests for request ID generation."""

    def test_generates_valid_uuid(self):
        """Test generated ID is valid UUID."""
        request_id = generate_request_id()
        assert is_valid_uuid(request_id)

    def test_generates_unique_ids(self):
        """Test each call generates unique ID."""
        ids = [generate_request_id() for _ in range(100)]
        assert len(set(ids)) == 100


@pytest.fixture
def app_with_middleware():
    """Create test app with request ID middleware."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"request_id": request.state.request_id}

    return app


@pytest.fixture
def client(app_with_middleware):
    """Create test client."""
    return TestClient(app_with_middleware)


class TestRequestIdMiddleware:
    """Tests for RequestIdMiddleware."""

    def test_preserves_valid_request_id(self, client):
        """Test incoming valid X-Request-ID is preserved."""
        request_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get("/test", headers={REQUEST_ID_HEADER: request_id})

        assert response.status_code == 200
        assert response.headers[REQUEST_ID_HEADER] == request_id

    def test_generates_id_when_missing(self, client):
        """Test generates new ID when header missing."""
        response = client.get("/test")

        assert response.status_code == 200
        assert REQUEST_ID_HEADER in response.headers
        assert is_valid_uuid(response.headers[REQUEST_ID_HEADER])

    def test_replaces_invalid_request_id(self, client):
        """Test invalid X-Request-ID is replaced."""
        response = client.get("/test", headers={REQUEST_ID_HEADER: "invalid-id"})

        assert response.status_code == 200
        assert REQUEST_ID_HEADER in response.headers
        assert response.headers[REQUEST_ID_HEADER] != "invalid-id"
        assert is_valid_uuid(response.headers[REQUEST_ID_HEADER])

    def test_replaces_empty_request_id(self, client):
        """Test empty X-Request-ID is replaced."""
        response = client.get("/test", headers={REQUEST_ID_HEADER: ""})

        assert response.status_code == 200
        assert is_valid_uuid(response.headers[REQUEST_ID_HEADER])

    def test_request_id_in_state(self, client):
        """Test request ID accessible via request.state."""
        request_id = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get("/test", headers={REQUEST_ID_HEADER: request_id})

        data = response.json()
        assert data["request_id"] == request_id

    def test_generated_id_in_state(self, client):
        """Test generated request ID accessible via request.state."""
        response = client.get("/test")

        data = response.json()
        assert is_valid_uuid(data["request_id"])
        assert data["request_id"] == response.headers[REQUEST_ID_HEADER]


class TestMiddlewareNeverFails:
    """Tests to ensure middleware never fails request processing."""

    def test_handles_various_headers_gracefully(self, client):
        """Test middleware handles various header values gracefully."""
        test_values = [
            "",
            " ",
            "null",
            "undefined",
            "0",
            "-1",
            "true",
            "false",
            "a" * 1000,  # Very long string
        ]

        for value in test_values:
            response = client.get("/test", headers={REQUEST_ID_HEADER: value})
            assert response.status_code == 200
            assert REQUEST_ID_HEADER in response.headers
