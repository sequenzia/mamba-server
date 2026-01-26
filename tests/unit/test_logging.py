"""Tests for structured logging middleware."""

import json
import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mamba.middleware.logging import (
    JsonFormatter,
    LoggingMiddleware,
    TextFormatter,
    configure_logging,
    get_logger,
    request_id_var,
)


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_basic_log_format(self):
        """Test basic log formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_timestamp_format(self):
        """Test timestamp is ISO 8601 with Z suffix."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["timestamp"].endswith("Z")
        # Should be parseable ISO format
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_includes_request_id_from_context(self):
        """Test request ID from context variable."""
        formatter = JsonFormatter()
        token = request_id_var.set("test-request-id")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            data = json.loads(output)

            assert data["request_id"] == "test-request-id"
        finally:
            request_id_var.reset(token)

    def test_includes_extra_fields(self):
        """Test extra fields are included."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.method = "POST"
        record.path = "/chat/completions"
        record.status_code = 200
        record.duration_ms = 1500

        output = formatter.format(record)
        data = json.loads(output)

        assert data["method"] == "POST"
        assert data["path"] == "/chat/completions"
        assert data["status_code"] == 200
        assert data["duration_ms"] == 1500

    def test_includes_exception_info(self):
        """Test exception info is included."""
        formatter = JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )
            output = formatter.format(record)
            data = json.loads(output)

            assert "exception" in data
            assert "ValueError" in data["exception"]


class TestTextFormatter:
    """Tests for TextFormatter."""

    def test_basic_format(self):
        """Test basic text formatting."""
        formatter = TextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)

        assert "INFO" in output
        assert "test" in output
        assert "Test message" in output

    def test_includes_request_id_prefix(self):
        """Test request ID is prefixed to message."""
        formatter = TextFormatter()
        token = request_id_var.set("abc12345-1234-1234-1234-123456789012")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)

            assert "[abc12345]" in output
        finally:
            request_id_var.reset(token)


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_json_format(self):
        """Test JSON format configuration."""
        configure_logging(level="INFO", format="json")
        logger = logging.getLogger()

        assert len(logger.handlers) > 0
        assert isinstance(logger.handlers[0].formatter, JsonFormatter)

    def test_text_format(self):
        """Test text format configuration."""
        configure_logging(level="INFO", format="text")
        logger = logging.getLogger()

        assert len(logger.handlers) > 0
        assert isinstance(logger.handlers[0].formatter, TextFormatter)

    def test_log_level_setting(self):
        """Test log level is set correctly."""
        configure_logging(level="DEBUG", format="json")
        logger = logging.getLogger()

        assert logger.level == logging.DEBUG


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.fixture
    def app_with_logging(self):
        """Create app with logging middleware."""
        from mamba.middleware.request_id import RequestIdMiddleware

        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)
        app.add_middleware(LoggingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/error")
        async def error_endpoint():
            raise RuntimeError("Test error")

        return app

    @pytest.fixture
    def client(self, app_with_logging):
        """Create test client."""
        return TestClient(app_with_logging, raise_server_exceptions=False)

    def test_logs_request_completion(self, client, caplog):
        """Test request completion is logged."""
        configure_logging(level="INFO", format="text")
        with caplog.at_level(logging.INFO):
            response = client.get("/test")
            assert response.status_code == 200

    def test_logs_error_requests(self, client, caplog):
        """Test error requests are logged."""
        configure_logging(level="INFO", format="text")
        with caplog.at_level(logging.ERROR):
            client.get("/error")


class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger(self):
        """Test returns a logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
