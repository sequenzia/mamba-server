"""Configuration management using Pydantic Settings.

Loads configuration from multiple sources with the following priority (highest first):
1. Environment variables (MAMBA_* prefix)
2. .env file
3. config.local.yaml (if exists)
4. config.yaml
5. Default values
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CorsSettings(BaseModel):
    """CORS configuration."""

    allowed_origins: list[str] = ["http://localhost:5173"]
    allowed_methods: list[str] = ["GET", "POST", "OPTIONS"]
    allowed_headers: list[str] = [
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Request-ID",
    ]


class ServerSettings(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    timeout_seconds: int = 300
    cors: CorsSettings = Field(default_factory=CorsSettings)


class ApiKeyConfig(BaseModel):
    """API key configuration."""

    key: str
    name: str


class JwtSettings(BaseModel):
    """JWT authentication settings."""

    secret: str | None = None
    algorithm: str = "HS256"
    issuer: str | None = None
    audience: str | None = None


class AuthSettings(BaseModel):
    """Authentication configuration."""

    mode: Literal["none", "api_key", "jwt"] = "none"
    api_keys: list[ApiKeyConfig] = Field(default_factory=list)
    jwt: JwtSettings = Field(default_factory=JwtSettings)


class OpenAISettings(BaseModel):
    """OpenAI provider configuration."""

    api_key: str = ""
    organization: str | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60
    max_retries: int = 3
    default_model: str = "gpt-4o"


class ModelConfig(BaseModel):
    """Model configuration."""

    id: str
    name: str
    provider: str
    openai_model: str
    description: str | None = None
    context_window: int | None = None
    supports_tools: bool = True


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "text"] = "json"
    include_request_body: bool = False
    include_response_body: bool = False


class HealthSettings(BaseModel):
    """Health check configuration."""

    openai_check_enabled: bool = True
    check_interval_seconds: int = 30
    timeout_seconds: int = 5


class TitleSettings(BaseModel):
    """Settings for title generation."""

    max_length: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Maximum title length in characters",
    )
    timeout_ms: int = Field(
        default=10000,
        ge=1000,
        le=30000,
        description="Timeout for title generation in milliseconds",
    )
    model: str = Field(
        default="gpt-4o-mini",
        description="Model to use for title generation",
    )


def _load_yaml_config(config_dir: Path) -> dict:
    """Load configuration from YAML files.

    Loads config.yaml and optionally overlays config.local.yaml.
    """
    config = {}

    config_file = config_dir / "config.yaml"
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.safe_load(f) or {}

    local_config_file = config_dir / "config.local.yaml"
    if local_config_file.exists():
        with open(local_config_file) as f:
            local_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, local_config)

    return config


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Settings(BaseSettings):
    """Application settings loaded from environment, .env, and config files."""

    model_config = SettingsConfigDict(
        env_prefix="MAMBA_",
        env_nested_delimiter="__",
        env_file=Path.home() / "mamba.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server: ServerSettings = Field(default_factory=ServerSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    title: TitleSettings = Field(default_factory=TitleSettings)
    models: list[ModelConfig] = Field(default_factory=list)

    # Direct environment variable mappings for common settings
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_API_BASE_URL")

    def __init__(self, config_dir: Path | None = None, **data):
        """Initialize settings, loading from YAML if config_dir provided."""
        if config_dir is not None:
            yaml_config = _load_yaml_config(config_dir)
            # Merge YAML config with any explicit data (explicit data wins)
            merged = _deep_merge(yaml_config, data)
            super().__init__(**merged)
        else:
            super().__init__(**data)

        # Apply OPENAI_API_KEY environment variable to openai.api_key if not set
        if self.openai_api_key and not self.openai.api_key:
            self.openai.api_key = self.openai_api_key

        # Apply OPENAI_API_BASE_URL environment variable to openai.base_url if set
        if self.openai_base_url:
            self.openai.base_url = self.openai_base_url

    @field_validator("models", mode="before")
    @classmethod
    def set_default_models(cls, v):
        """Set default models if none provided."""
        if not v:
            return [
                ModelConfig(
                    id="openai/gpt-4o",
                    name="GPT-4o",
                    provider="openai",
                    openai_model="gpt-4o",
                    description="Most capable GPT-4 model",
                    context_window=128000,
                    supports_tools=True,
                ),
                ModelConfig(
                    id="openai/gpt-4o-mini",
                    name="GPT-4o Mini",
                    provider="openai",
                    openai_model="gpt-4o-mini",
                    description="Fast and cost-effective",
                    context_window=128000,
                    supports_tools=True,
                ),
            ]
        return v

    def validate_required(self) -> None:
        """Validate that required settings are present.

        Raises:
            ValueError: If required settings are missing.
        """
        if not self.openai.api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable or openai.api_key config is required"
            )

        if self.auth.mode == "jwt" and not self.auth.jwt.secret:
            raise ValueError("JWT secret is required when auth mode is 'jwt'")

        if self.auth.mode == "api_key" and not self.auth.api_keys:
            raise ValueError("At least one API key is required when auth mode is 'api_key'")


@lru_cache
def get_settings(config_dir: Path | None = None) -> Settings:
    """Get cached settings instance.

    Args:
        config_dir: Optional path to config directory. If None, only environment
                   variables and .env file are used.

    Returns:
        Settings instance.
    """
    if config_dir is None:
        # Try to find config directory relative to project root
        project_root = Path(__file__).parent.parent.parent
        default_config_dir = project_root / "config"
        if default_config_dir.exists():
            config_dir = default_config_dir

    return Settings(config_dir=config_dir)
