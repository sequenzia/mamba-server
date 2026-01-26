"""Tests for health check data models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mamba.models.health import ComponentHealth, HealthResponse, HealthStatus


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_healthy_value(self):
        """Test healthy status value."""
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_degraded_value(self):
        """Test degraded status value."""
        assert HealthStatus.DEGRADED.value == "degraded"

    def test_unhealthy_value(self):
        """Test unhealthy status value."""
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_all_statuses_serialize_correctly(self):
        """Test all status values serialize to lowercase strings."""
        for status in HealthStatus:
            component = ComponentHealth(status=status)
            data = component.model_dump()
            assert data["status"] == status.value


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_minimal_component(self):
        """Test component with only required field."""
        component = ComponentHealth(status=HealthStatus.HEALTHY)
        assert component.status == HealthStatus.HEALTHY
        assert component.latency_ms is None
        assert component.error is None
        assert component.message is None

    def test_full_component(self):
        """Test component with all fields."""
        component = ComponentHealth(
            status=HealthStatus.DEGRADED,
            latency_ms=250,
            error=None,
            message="High latency detected",
        )
        assert component.status == HealthStatus.DEGRADED
        assert component.latency_ms == 250
        assert component.message == "High latency detected"

    def test_unhealthy_component_with_error(self):
        """Test unhealthy component with error message."""
        component = ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            error="Connection refused",
        )
        assert component.status == HealthStatus.UNHEALTHY
        assert component.error == "Connection refused"

    def test_serialization(self):
        """Test JSON serialization matches spec."""
        component = ComponentHealth(
            status=HealthStatus.HEALTHY,
            latency_ms=45,
        )
        data = component.model_dump()
        assert data == {
            "status": "healthy",
            "latency_ms": 45,
            "error": None,
            "message": None,
        }

    def test_serialization_excludes_none(self):
        """Test serialization can exclude None values."""
        component = ComponentHealth(status=HealthStatus.HEALTHY)
        data = component.model_dump(exclude_none=True)
        assert data == {"status": "healthy"}

    def test_invalid_status_rejected(self):
        """Test invalid status value raises error."""
        with pytest.raises(ValidationError):
            ComponentHealth(status="invalid")  # type: ignore


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy response structure."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc),
            checks={
                "openai": ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=45,
                )
            },
        )
        assert response.status == HealthStatus.HEALTHY
        assert response.version == "1.0.0"
        assert "openai" in response.checks

    def test_empty_checks_is_valid(self):
        """Test empty checks dict is valid."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime.now(timezone.utc),
            checks={},
        )
        assert response.checks == {}

    def test_timestamp_serializes_to_iso8601(self):
        """Test timestamp serializes to ISO 8601 format."""
        ts = datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc)
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=ts,
            checks={},
        )
        data = response.model_dump(mode="json")
        assert data["timestamp"] == "2026-01-26T10:30:00Z"

    def test_serialization_matches_api_spec(self):
        """Test full serialization matches API spec."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            version="1.0.0",
            timestamp=datetime(2026, 1, 26, 10, 30, 0, tzinfo=timezone.utc),
            checks={
                "openai": ComponentHealth(
                    status=HealthStatus.HEALTHY,
                    latency_ms=45,
                )
            },
        )
        data = response.model_dump(mode="json", exclude_none=True)
        assert data == {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2026-01-26T10:30:00Z",
            "checks": {
                "openai": {
                    "status": "healthy",
                    "latency_ms": 45,
                }
            },
        }

    def test_degraded_response(self):
        """Test degraded response with warning."""
        response = HealthResponse(
            status=HealthStatus.DEGRADED,
            version="1.0.0",
            timestamp=datetime.now(timezone.utc),
            checks={
                "openai": ComponentHealth(
                    status=HealthStatus.DEGRADED,
                    latency_ms=2500,
                    message="High latency detected",
                )
            },
        )
        assert response.status == HealthStatus.DEGRADED

    def test_unhealthy_response(self):
        """Test unhealthy response with error."""
        response = HealthResponse(
            status=HealthStatus.UNHEALTHY,
            version="1.0.0",
            timestamp=datetime.now(timezone.utc),
            checks={
                "openai": ComponentHealth(
                    status=HealthStatus.UNHEALTHY,
                    error="Connection refused",
                )
            },
        )
        assert response.status == HealthStatus.UNHEALTHY
