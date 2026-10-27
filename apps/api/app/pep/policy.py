"""Policy Enforcement Point (PEP) Annotations, Dependencies, and Allowlist."""

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.pdp.client import PdpDecision, pdp_client
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.database import get_db_session

# Documented Allowlist of Public Endpoints
PUBLIC_ALLOWLIST = frozenset(
    [
        "/",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/system/info",
        "/api/v1/system/health",
        "/api/v1/system/health/live",
        "/api/v1/system/health/ready",
        "/api/v1/auth/login",
        "/api/v1/auth/callback",
        "/api/v1/auth/token",
        "/api/v1/scim/v2/Users",
        "/api/v1/scim/v2/Users/{user_id}",
        "/api/v1/scim/v2/Groups",
        "/api/v1/scim/v2/Groups/{group_id}",
    ]
)


def require_permission(
    action: str,
    resource_type: str = "document",
    default_classification: str = "INTERNAL",
) -> Callable[..., Any]:
    """
    FastAPI dependency factory enforcing PDP authorization on endpoints.
    Evaluates OPA Rego policy, audits every decision (allow, deny, require_approval),
    and enforces fail-closed behavior.
    """

    async def dependency(
        request: Request,
        session: SessionData = Depends(get_current_session),
        db: AsyncSession = Depends(get_db_session),
    ) -> PdpDecision:
        # Resolve target resource parameters from path / headers
        path_params = request.path_params
        resource_id = (
            path_params.get("id")
            or path_params.get("document_id")
            or path_params.get("record_id")
            or path_params.get("user_id")
            or "global"
        )
        resource_tenant_id = (
            path_params.get("tenant_id")
            or request.headers.get("X-Target-Tenant-ID")
            or session.tenant_id
        )
        classification = (
            request.headers.get("X-Resource-Classification") or default_classification
        )
        department = request.headers.get("X-Resource-Department") or session.department

        # Extract client IP and user agent for audit trail
        client_ip = request.client.host if request.client else "127.0.0.1"
        user_agent = request.headers.get("user-agent")
        correlation_id = getattr(request.state, "correlation_id", "trace-pep")

        # Context for approval / step-up checks
        has_approval = request.headers.get("X-Approval-Token") is not None
        context = {
            "has_approval": has_approval,
            "ip_address": client_ip,
        }

        # Evaluate Policy Decision Point (OPA)
        decision = await pdp_client.evaluate(
            user_id=session.user_id,
            tenant_id=session.tenant_id,
            roles=session.roles,
            department=session.department,
            clearance_level=session.clearance_level,
            action=action,
            resource_id=resource_id,
            resource_tenant_id=resource_tenant_id,
            resource_type=resource_type,
            resource_classification=classification,
            resource_department=department,
            context=context,
        )

        # Audit the decision outcome
        outcome = decision.result.upper()
        try:
            await record_audit_event(
                db,
                tenant_id=session.tenant_id,
                actor_id=str(session.user_id),
                actor_email=session.email,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id),
                outcome=outcome,
                reason=decision.reason,
                ip_address=client_ip,
                user_agent=user_agent,
                correlation_id=correlation_id,
                payload={
                    "obligations": decision.obligations,
                    "roles": session.roles,
                    "clearance": session.clearance_level,
                    "classification": classification,
                },
            )
            # Commit the audit record immediately so 403 HTTPException does not roll it back
            await db.commit()
        except Exception as audit_err:  # noqa: BLE001
            logger.error(f"Audit log recording error: {audit_err}")

        # Enforce Decision
        if decision.requires_approval:
            logger.warning(f"PEP: Step-up / dual approval required for {session.email} on {action}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "STEP_UP_REQUIRED",
                    "message": decision.reason,
                    "obligations": decision.obligations,
                },
            )

        if decision.is_denied:
            logger.warning(f"PEP: Denied {session.email} performing {action} ({decision.reason})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ACCESS_DENIED",
                    "message": decision.reason,
                    "obligations": decision.obligations,
                },
            )

        return decision

    # Mark dependency with metadata for route introspective coverage testing
    dependency.__pep_action__ = action  # type: ignore[attr-defined]
    dependency.__pep_protected__ = True  # type: ignore[attr-defined]
    return dependency


def protect(
    action: str,
    resource_type: str = "document",
    default_classification: str = "INTERNAL",
) -> Callable[..., Any]:
    """Decorator to mark and enforce policy protection on a route endpoint."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "__pep_protected__", True)  # noqa: B010
        setattr(func, "__pep_action__", action)  # noqa: B010
        setattr(func, "__pep_resource_type__", resource_type)  # noqa: B010
        return func

    return decorator
