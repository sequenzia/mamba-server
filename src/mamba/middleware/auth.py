"""Authentication middleware for request validation."""

import json
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from mamba.config import Settings

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle authentication based on configured mode.

    Supports three authentication modes:
    - none: No authentication required (development only)
    - api_key: API key validation via X-API-Key header or Authorization Bearer
    - jwt: JWT token validation via Authorization Bearer header
    """

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.auth_mode = settings.auth.mode

        if self.auth_mode == "none":
            logger.warning(
                "Authentication is DISABLED. This should only be used in development.",
                extra={"auth_mode": self.auth_mode},
            )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with authentication check.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            Response from the handler or 401/500 error response.
        """
        # Skip auth for health endpoints (liveness/readiness probes)
        if self._is_health_endpoint(request.url.path):
            return await call_next(request)

        # Authenticate based on mode
        if self.auth_mode == "none":
            return await call_next(request)

        elif self.auth_mode == "api_key":
            if not self._validate_api_key(request):
                return self._auth_error_response()
            return await call_next(request)

        elif self.auth_mode == "jwt":
            if not self._validate_jwt(request):
                return self._auth_error_response()
            return await call_next(request)

        else:
            # This shouldn't happen if config validation works correctly
            logger.error(f"Unknown auth mode: {self.auth_mode}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Server configuration error"},
            )

    def _auth_error_response(self) -> JSONResponse:
        """Create a 401 authentication error response."""
        return JSONResponse(
            status_code=401,
            content={
                "detail": "Invalid authentication credentials",
                "code": "AUTH_INVALID",
            },
        )

    def _is_health_endpoint(self, path: str) -> bool:
        """Check if path is a health check endpoint."""
        health_paths = ["/health", "/health/live", "/health/ready"]
        return path in health_paths

    def _validate_api_key(self, request: Request) -> bool:
        """Validate API key from request headers.

        Accepts API key from:
        - X-API-Key header
        - Authorization: Bearer <key> header

        Args:
            request: The incoming request.

        Returns:
            True if API key is valid, False otherwise.
        """
        # Try X-API-Key header first
        api_key = request.headers.get("X-API-Key")

        # Fall back to Authorization Bearer
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # Remove "Bearer " prefix

        if not api_key:
            logger.debug("No API key provided in request")
            return False

        # Check against configured API keys
        for key_config in self.settings.auth.api_keys:
            if key_config.key == api_key:
                logger.debug(
                    "API key validated",
                    extra={"key_name": key_config.name},
                )
                return True

        logger.warning("Invalid API key provided")
        return False

    def _validate_jwt(self, request: Request) -> bool:
        """Validate JWT token from Authorization header.

        Args:
            request: The incoming request.

        Returns:
            True if JWT is valid, False otherwise.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.debug("No Bearer token provided in request")
            return False

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            import jwt

            # Get JWT settings
            jwt_settings = self.settings.auth.jwt
            if not jwt_settings.secret:
                logger.error("JWT secret not configured")
                return False

            # Decode and validate token
            payload = jwt.decode(
                token,
                jwt_settings.secret,
                algorithms=[jwt_settings.algorithm],
                issuer=jwt_settings.issuer,
                audience=jwt_settings.audience,
            )

            logger.debug(
                "JWT validated",
                extra={"user_id": payload.get("sub")},
            )
            return True

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return False
        except ImportError:
            logger.error("PyJWT package not installed for JWT auth mode")
            return False
