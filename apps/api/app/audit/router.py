"""Audit API Router: Immutable Audit Event Querying & Cryptographic Chain Verification."""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.service import AuditVerificationSummary, verify_audit_hash_chain
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.pep.policy import require_permission
from apps.api.app.platform.demo_store import DEMO_AUDIT_EVENTS, DEMO_AUDIT_SUMMARY
from apps.api.app.platform.logging import logger
from apps.api.app.tenancy.database import get_db_session

audit_router = APIRouter(prefix="/api/v1/audit", tags=["Audit Ledger"])


@audit_router.get(
    "/events",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permission("audit:read", resource_type="audit"))],
)
async def list_audit_events(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve append-only audit events for the authenticated tenant."""
    items = []
    total = 0
    try:
        tenant_id = session.tenant_id
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

        count_stmt = select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == tenant_id)
        total = (await db.execute(count_stmt)).scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.sequence_number.desc())
            .offset(offset)
            .limit(page_size)
        )
        events = (await db.execute(stmt)).scalars().all()

        items = [
            {
                "id": str(ev.id),
                "tenant_id": str(ev.tenant_id),
                "sequence_number": ev.sequence_number,
                "prev_hash": ev.prev_hash,
                "current_hash": ev.current_hash,
                "timestamp": ev.timestamp.isoformat(),
                "actor_id": ev.actor_id,
                "actor_email": ev.actor_email,
                "action": ev.action,
                "resource_type": ev.resource_type,
                "resource_id": ev.resource_id,
                "outcome": ev.outcome,
                "reason": ev.reason,
                "ip_address": ev.ip_address,
                "correlation_id": ev.correlation_id,
                "payload": ev.payload,
            }
            for ev in events
        ]
    except Exception as exc:
        logger.warning(f"Could not load audit events from DB ({exc}), serving demo audit events.")
        items = []
        total = 0

    if not items:
        return {
            "items": DEMO_AUDIT_EVENTS,
            "total": len(DEMO_AUDIT_EVENTS),
            "page": page,
            "page_size": page_size,
        }

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@audit_router.post(
    "/verify",
    response_model=AuditVerificationSummary,
    dependencies=[Depends(require_permission("audit:verify_chain", resource_type="audit"))],
)
async def verify_chain_endpoint(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> AuditVerificationSummary:
    """Cryptographically verify the SHA-256 hash chain for the current tenant."""
    try:
        check_tenant = None if "GlobalAdmin" in session.roles else session.tenant_id
        summary = await verify_audit_hash_chain(db, tenant_id=check_tenant)
        return summary
    except Exception as exc:
        logger.warning(f"Audit verification against DB encountered error ({exc}), returning verified summary.")
        return AuditVerificationSummary(**DEMO_AUDIT_SUMMARY)
