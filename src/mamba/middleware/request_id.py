"""Request ID middleware for request tracing."""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID.

    Args:
        value: String to validate.

    Returns:
        True if valid UUID, False otherwise.
    """
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def generate_request_id() -> str:
    """Generate a new request ID.

    Returns:
        A new UUID4 string.
    """
    return str(uuid.uuid4())


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle X-Request-ID header for request tracing.

    This middleware:
    - Extracts X-Request-ID from incoming request headers
    - Generates a new UUID if the header is missing or invalid
    - Stores the request ID in request.state for handler access
    - Adds X-Request-ID to response headers
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process the request with request ID handling.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response with X-Request-ID header added.
        """
        # Extract or generate request ID
        request_id = request.headers.get(REQUEST_ID_HEADER, "")

        # Validate the request ID - empty or invalid gets replaced
        if not request_id or not is_valid_uuid(request_id):
            request_id = generate_request_id()

        # Store in request state for access in handlers
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[REQUEST_ID_HEADER] = request_id

        return response
