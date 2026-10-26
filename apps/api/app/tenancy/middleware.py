"""
Tenancy Context Middleware.
Extracts and validates tenant context from headers or JWT tokens.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from apps.api.app.platform.errors import ValidationError
from apps.api.app.tenancy.context import set_current_tenant_id, tenant_id_ctx

TENANT_HEADER = "X-Tenant-ID"

# Public paths that do not require tenant scoping
UNSCOPED_PATHS = {
    "/",
    "/api/v1/system/info",
    "/api/v1/system/health",
    "/api/v1/system/health/live",
    "/api/v1/system/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class TenancyMiddleware(BaseHTTPMiddleware):
    """
    Middleware establishing active tenant context for each HTTP request.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in UNSCOPED_PATHS or path.startswith("/static"):
            return await call_next(request)

        tenant_header_val = request.headers.get(TENANT_HEADER)
        if tenant_header_val:
            try:
                tenant_id = uuid.UUID(tenant_header_val)
                token = tenant_id_ctx.set(tenant_id)
            except ValueError:
                err = ValidationError(f"Invalid UUID in '{TENANT_HEADER}' header: '{tenant_header_val}'")
                from apps.api.app.platform.errors import elixir_error_handler
                return elixir_error_handler(request, err)
        else:
            token = tenant_id_ctx.set(None)

        try:
            response = await call_next(request)
            if tenant_id_ctx.get():
                response.headers[TENANT_HEADER] = str(tenant_id_ctx.get())
            return response
        finally:
            tenant_id_ctx.reset(token)
