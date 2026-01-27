"""Tests for configuration module."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from mamba.config import (
    ApiKeyConfig,
    AuthSettings,
    CorsSettings,
    HealthSettings,
    JwtSettings,
    LoggingSettings,
    ModelConfig,
    OpenAISettings,
    ServerSettings,
    Settings,
    TitleSettings,
    _deep_merge,
    _load_yaml_config,
)


class TestServerSettings:
    """Tests for ServerSettings."""

    def test_default_values(self):
        """Test default values are set correctly."""
        settings = ServerSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.workers == 4
        assert settings.timeout_seconds == 300
        assert isinstance(settings.cors, CorsSettings)

    def test_custom_values(self):
        """Test custom values are accepted."""
        settings = ServerSettings(
            host="127.0.0.1",
            port=9000,
            workers=8,
            timeout_seconds=600,
        )
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.workers == 8
        assert settings.timeout_seconds == 600


class TestCorsSettings:
    """Tests for CorsSettings."""

    def test_default_values(self):
        """Test default values."""
        settings = CorsSettings()
        assert "http://localhost:5173" in settings.allowed_origins
        assert "GET" in settings.allowed_methods
        assert "Content-Type" in settings.allowed_headers

    def test_custom_origins(self):
        """Test custom origins."""
        settings = CorsSettings(allowed_origins=["https://example.com"])
        assert settings.allowed_origins == ["https://example.com"]


class TestAuthSettings:
    """Tests for AuthSettings."""

    def test_default_mode_is_none(self):
        """Test default auth mode is none."""
        settings = AuthSettings()
        assert settings.mode == "none"
        assert settings.api_keys == []
        assert isinstance(settings.jwt, JwtSettings)

    def test_api_key_mode(self):
        """Test API key authentication settings."""
        settings = AuthSettings(
            mode="api_key",
            api_keys=[ApiKeyConfig(key="test_key", name="test")],
        )
        assert settings.mode == "api_key"
        assert len(settings.api_keys) == 1
        assert settings.api_keys[0].key == "test_key"

    def test_jwt_mode(self):
        """Test JWT authentication settings."""
        settings = AuthSettings(
            mode="jwt",
            jwt=JwtSettings(
                secret="my-secret",
                algorithm="HS512",
                issuer="test-issuer",
                audience="test-audience",
            ),
        )
        assert settings.mode == "jwt"
        assert settings.jwt.secret == "my-secret"
        assert settings.jwt.algorithm == "HS512"

    def test_invalid_mode_rejected(self):
        """Test invalid auth mode is rejected."""
        with pytest.raises(ValueError):
            AuthSettings(mode="invalid")


class TestOpenAISettings:
    """Tests for OpenAISettings."""

    def test_default_values(self):
        """Test default values."""
        settings = OpenAISettings()
        assert settings.base_url == "https://api.openai.com/v1"
        assert settings.timeout_seconds == 60
        assert settings.max_retries == 3
        assert settings.default_model == "gpt-4o"
        assert settings.api_key == ""

    def test_custom_values(self):
        """Test custom values."""
        settings = OpenAISettings(
            api_key="sk-test",
            organization="org-123",
            timeout_seconds=120,
        )
        assert settings.api_key == "sk-test"
        assert settings.organization == "org-123"
        assert settings.timeout_seconds == 120


class TestLoggingSettings:
    """Tests for LoggingSettings."""

    def test_default_values(self):
        """Test default values."""
        settings = LoggingSettings()
        assert settings.level == "INFO"
        assert settings.format == "json"
        assert settings.include_request_body is False
        assert settings.include_response_body is False

    def test_debug_level(self):
        """Test debug log level."""
        settings = LoggingSettings(level="DEBUG")
        assert settings.level == "DEBUG"

    def test_text_format(self):
        """Test text format."""
        settings = LoggingSettings(format="text")
        assert settings.format == "text"

    def test_invalid_level_rejected(self):
        """Test invalid log level is rejected."""
        with pytest.raises(ValueError):
            LoggingSettings(level="TRACE")


class TestHealthSettings:
    """Tests for HealthSettings."""

    def test_default_values(self):
        """Test default values."""
        settings = HealthSettings()
        assert settings.openai_check_enabled is True
        assert settings.check_interval_seconds == 30
        assert settings.timeout_seconds == 5


class TestTitleSettings:
    """Tests for TitleSettings."""

    def test_default_values(self):
        """Test default values."""
        settings = TitleSettings()
        assert settings.max_length == 50
        assert settings.timeout_ms == 10000
        assert settings.model == "gpt-4o-mini"

    def test_custom_values(self):
        """Test custom values are accepted."""
        settings = TitleSettings(
            max_length=100,
            timeout_ms=5000,
            model="gpt-4o",
        )
        assert settings.max_length == 100
        assert settings.timeout_ms == 5000
        assert settings.model == "gpt-4o"

    def test_max_length_minimum_constraint(self):
        """Test max_length minimum constraint (ge=10)."""
        with pytest.raises(ValueError):
            TitleSettings(max_length=9)

    def test_max_length_maximum_constraint(self):
        """Test max_length maximum constraint (le=200)."""
        with pytest.raises(ValueError):
            TitleSettings(max_length=201)

    def test_max_length_at_boundaries(self):
        """Test max_length at boundary values."""
        settings_min = TitleSettings(max_length=10)
        assert settings_min.max_length == 10

        settings_max = TitleSettings(max_length=200)
        assert settings_max.max_length == 200

    def test_timeout_ms_minimum_constraint(self):
        """Test timeout_ms minimum constraint (ge=1000)."""
        with pytest.raises(ValueError):
            TitleSettings(timeout_ms=999)

    def test_timeout_ms_maximum_constraint(self):
        """Test timeout_ms maximum constraint (le=30000)."""
        with pytest.raises(ValueError):
            TitleSettings(timeout_ms=30001)

    def test_timeout_ms_at_boundaries(self):
        """Test timeout_ms at boundary values."""
        settings_min = TitleSettings(timeout_ms=1000)
        assert settings_min.timeout_ms == 1000

        settings_max = TitleSettings(timeout_ms=30000)
        assert settings_max.timeout_ms == 30000


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_required_fields(self):
        """Test required fields."""
        model = ModelConfig(
            id="openai/gpt-4o",
            name="GPT-4o",
            provider="openai",
            openai_model="gpt-4o",
        )
        assert model.id == "openai/gpt-4o"
        assert model.supports_tools is True

    def test_optional_fields(self):
        """Test optional fields."""
        model = ModelConfig(
            id="openai/gpt-4o",
            name="GPT-4o",
            provider="openai",
            openai_model="gpt-4o",
            description="Test model",
            context_window=128000,
            supports_tools=False,
        )
        assert model.description == "Test model"
        assert model.context_window == 128000
        assert model.supports_tools is False


class TestDeepMerge:
    """Tests for _deep_merge function."""

    def test_shallow_merge(self):
        """Test shallow dictionary merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge(self):
        """Test deep dictionary merge."""
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"y": 3, "z": 4}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}}

    def test_override_non_dict(self):
        """Test override replaces non-dict values."""
        base = {"a": {"x": 1}}
        override = {"a": "replaced"}
        result = _deep_merge(base, override)
        assert result == {"a": "replaced"}


class TestLoadYamlConfig:
    """Tests for YAML config loading."""

    def test_load_config_yaml(self):
        """Test loading config.yaml."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            config_file.write_text(yaml.dump({"server": {"port": 9000}}))

            config = _load_yaml_config(config_dir)
            assert config["server"]["port"] == 9000

    def test_local_override(self):
        """Test config.local.yaml overrides config.yaml."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)

            config_file = config_dir / "config.yaml"
            config_file.write_text(yaml.dump({"server": {"port": 8000, "host": "0.0.0.0"}}))

            local_file = config_dir / "config.local.yaml"
            local_file.write_text(yaml.dump({"server": {"port": 9000}}))

            config = _load_yaml_config(config_dir)
            assert config["server"]["port"] == 9000
            assert config["server"]["host"] == "0.0.0.0"

    def test_missing_config_returns_empty(self):
        """Test missing config file returns empty dict."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config = _load_yaml_config(config_dir)
            assert config == {}


class TestSettings:
    """Tests for main Settings class."""

    def test_default_models(self):
        """Test default models are set when none provided."""
        settings = Settings()
        assert len(settings.models) == 2
        assert settings.models[0].id == "openai/gpt-4o"
        assert settings.models[1].id == "openai/gpt-4o-mini"

    def test_nested_settings_access(self):
        """Test nested settings are accessible."""
        settings = Settings()
        assert settings.server.port == 8000
        assert settings.auth.mode == "none"
        assert settings.logging.level == "INFO"

    def test_environment_variable_override(self, monkeypatch):
        """Test environment variables override defaults."""
        monkeypatch.setenv("MAMBA_SERVER__PORT", "9000")
        settings = Settings()
        assert settings.server.port == 9000

    def test_openai_api_key_from_env(self, monkeypatch):
        """Test OPENAI_API_KEY environment variable is applied."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        settings = Settings()
        assert settings.openai.api_key == "sk-test-key"

    def test_openai_base_url_from_env(self, monkeypatch):
        """Test OPENAI_API_BASE_URL environment variable is applied."""
        monkeypatch.setenv("OPENAI_API_BASE_URL", "https://custom.api.com/v1")
        settings = Settings()
        assert settings.openai.base_url == "https://custom.api.com/v1"

    def test_load_from_yaml(self):
        """Test loading from YAML config directory."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            config_file.write_text(
                yaml.dump(
                    {
                        "server": {"port": 9000},
                        "logging": {"level": "DEBUG"},
                    }
                )
            )

            settings = Settings(config_dir=config_dir)
            assert settings.server.port == 9000
            assert settings.logging.level == "DEBUG"

    def test_validate_required_missing_api_key(self, monkeypatch):
        """Test validation fails when OPENAI_API_KEY is missing."""
        # Ensure OPENAI_API_KEY is not set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = Settings()
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            settings.validate_required()

    def test_validate_required_with_api_key(self, monkeypatch):
        """Test validation passes with OPENAI_API_KEY set."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings()
        settings.validate_required()  # Should not raise

    def test_validate_required_jwt_missing_secret(self, monkeypatch):
        """Test validation fails when JWT mode but no secret."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(auth=AuthSettings(mode="jwt"))
        with pytest.raises(ValueError, match="JWT secret"):
            settings.validate_required()

    def test_validate_required_api_key_mode_no_keys(self, monkeypatch):
        """Test validation fails when api_key mode but no keys."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = Settings(auth=AuthSettings(mode="api_key"))
        with pytest.raises(ValueError, match="API key"):
            settings.validate_required()

    def test_empty_env_causes_validation_error(self, monkeypatch):
        """Test empty environment variables cause validation errors for typed fields."""
        monkeypatch.setenv("MAMBA_SERVER__PORT", "")
        # Empty string cannot be parsed as integer, so validation fails
        with pytest.raises(Exception):  # ValidationError
            Settings()


class TestSettingsIntegration:
    """Integration tests with actual config files."""

    def test_load_project_config(self):
        """Test loading the project's actual config.yaml."""
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config"

        if config_dir.exists():
            settings = Settings(config_dir=config_dir)
            assert settings.server.port == 8000
            assert len(settings.models) >= 2
