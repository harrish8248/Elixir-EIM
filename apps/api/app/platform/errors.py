"""
Standardized Enterprise Error Hierarchy and HTTP Exception Handlers.
Errors never leak raw stack traces or internal implementation details to clients.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from apps.api.app.platform.correlation import get_correlation_id


class ElixirError(Exception):
    """Base class for all application-level errors in Elixir EIM."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class EntityNotFoundError(ElixirError):
    def __init__(self, entity_name: str, entity_id: str):
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class PermissionDeniedError(ElixirError):
    def __init__(self, message: str = "Access denied by enterprise policy.", details: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class TenantNotFoundError(ElixirError):
    def __init__(self, tenant_id: str):
        super().__init__(
            message=f"Tenant '{tenant_id}' is inactive or does not exist.",
            code="TENANT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AuditIntegrityError(ElixirError):
    def __init__(self, message: str):
        super().__init__(
            message=f"Cryptographic audit chain failure: {message}",
            code="AUDIT_INTEGRITY_VIOLATION",
            status_code=status.HTTP_409_CONFLICT,
        )


class ValidationError(ElixirError):
    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_FAILED",
            status_code=422,
            details=details,
        )


def elixir_error_handler(request: Request, exc: ElixirError) -> JSONResponse:
    """Serializes ElixirError into standard enterprise JSON error response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "requestId": get_correlation_id(),
                "timestamp": datetime.now(UTC).isoformat(),
                "details": exc.details,
            }
        },
    )


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler masking unexpected exceptions behind safe enterprise envelope."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please contact your system administrator.",
                "requestId": get_correlation_id(),
                "timestamp": datetime.now(UTC).isoformat(),
                "details": [],
            }
        },
    )
