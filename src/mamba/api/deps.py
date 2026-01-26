"""Dependency injection for API handlers."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from mamba.config import Settings, get_settings


def get_settings_dependency() -> Settings:
    """Get application settings.

    This is a thin wrapper around get_settings() to allow for
    easier testing via dependency override.
    """
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]


def get_request_id(request: Request) -> str | None:
    """Extract request ID from request state or headers.

    The request ID is set by the request ID middleware.
    """
    return getattr(request.state, "request_id", None)


RequestIdDep = Annotated[str | None, Depends(get_request_id)]
