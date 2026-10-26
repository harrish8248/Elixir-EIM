"""
Tenant Context Management using async ContextVars.
"""

import uuid
from contextvars import ContextVar

# Context variable preserving active tenant UUID across async execution contexts
tenant_id_ctx: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant_id() -> uuid.UUID | None:
    """Retrieve the current active tenant UUID."""
    return tenant_id_ctx.get()


def set_current_tenant_id(tenant_id: uuid.UUID) -> None:
    """Set the current active tenant UUID."""
    tenant_id_ctx.set(tenant_id)


def clear_current_tenant_id() -> None:
    """Reset the tenant context."""
    tenant_id_ctx.set(None)
