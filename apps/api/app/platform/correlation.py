"""
Correlation ID context management and ASGI middleware for end-to-end request tracing.
"""

import uuid
from contextvars import ContextVar
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable preserving correlation ID across async execution contexts
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

HEADER_NAME = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Get the current correlation ID or generate a new fallback."""
    cid = correlation_id_ctx.get()
    if not cid:
        cid = str(uuid.uuid4())
        correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Explicitly set the correlation ID for the active context."""
    correlation_id_ctx.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware extracting or injecting X-Correlation-ID into request and response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get(HEADER_NAME)
        if not cid:
            cid = str(uuid.uuid4())

        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers[HEADER_NAME] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)
