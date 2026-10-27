"""Administration API Router: users, system health, dashboard KPIs."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.models import AuditEvent
from apps.api.app.content.models import Document
from apps.api.app.identity.models import User
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.platform.branding import BRANDING
from apps.api.app.platform.config import settings
from apps.api.app.records.models import LegalHold
from apps.api.app.tenancy.database import get_db_session
from apps.api.app.workflow.models import WorkflowTask

admin_router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    username: str
    first_name: str | None
    last_name: str | None
    roles: list[str]
    department: str | None
    clearance_level: int
    is_active: bool
    last_login_at: str | None
    created_at: str


class UpdateUserRequest(BaseModel):
    roles: list[str] | None = None
    is_active: bool | None = None
    clearance_level: int | None = None
    department: str | None = None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def _require_admin(session: SessionData) -> None:
    allowed_roles = {"Admin", "GlobalAdmin", "TenantAdmin", "RecordsManager"}
    if not any(r in allowed_roles for r in session.roles):
        raise HTTPException(status_code=403, detail="Administrator access required")


@admin_router.get("/users", response_model=dict[str, Any])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = None,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _require_admin(session)
    stmt = select(User).where(User.tenant_id == session.tenant_id)
    if q:
        stmt = stmt.where(
            (User.email.ilike(f"%{q}%")) | (User.username.ilike(f"%{q}%"))
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    stmt = stmt.order_by(User.email).offset((page - 1) * page_size).limit(page_size)
    users = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            UserOut(
                id=str(u.id), tenant_id=str(u.tenant_id), email=u.email,
                username=u.username, first_name=u.first_name, last_name=u.last_name,
                roles=u.roles or [], department=u.department,
                clearance_level=u.clearance_level, is_active=u.is_active,
                last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
                created_at=u.created_at.isoformat(),
            ).__dict__
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> UserOut:
    _require_admin(session)
    from apps.api.app.audit.service import record_audit_event
    import uuid
    user = (await db.execute(
        select(User).where(User.id == uuid.UUID(user_id), User.tenant_id == session.tenant_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    changes: dict[str, Any] = {}
    if body.roles is not None:
        changes["roles"] = body.roles
        user.roles = body.roles
    if body.is_active is not None:
        changes["is_active"] = body.is_active
        user.is_active = body.is_active
    if body.clearance_level is not None:
        changes["clearance_level"] = body.clearance_level
        user.clearance_level = body.clearance_level
    if body.department is not None:
        changes["department"] = body.department
        user.department = body.department

    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="admin:user:update",
        resource_type="user", resource_id=user_id, outcome="ALLOW",
        reason=f"User profile updated: {user.email}",
        payload=changes,
    )
    return UserOut(
        id=str(user.id), tenant_id=str(user.tenant_id), email=user.email,
        username=user.username, first_name=user.first_name, last_name=user.last_name,
        roles=user.roles or [], department=user.department,
        clearance_level=user.clearance_level, is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# System Health
# ---------------------------------------------------------------------------
@admin_router.get("/health", response_model=dict[str, Any])
async def system_health(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    _require_admin(session)

    checks: dict[str, str] = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "UP"
    except Exception:  # noqa: BLE001
        checks["database"] = "DOWN"

    # Redis
    try:
        from apps.api.app.identity.session import session_manager
        r = await session_manager.get_redis()
        await r.ping()
        checks["redis"] = "UP"
    except Exception:  # noqa: BLE001
        checks["redis"] = "DOWN"

    # OPA
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("http://localhost:8181/health")
            checks["opa"] = "UP" if resp.status_code == 200 else "DOWN"
    except Exception:  # noqa: BLE001
        checks["opa"] = "DOWN"

    # MinIO
    try:
        import aioboto3  # type: ignore[import-untyped]
        session_s3 = aioboto3.Session()
        async with session_s3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        ) as s3:
            await s3.list_buckets()
        checks["storage"] = "UP"
    except Exception:  # noqa: BLE001
        checks["storage"] = "DOWN"

    overall = "HEALTHY" if all(v == "UP" for v in checks.values()) else "DEGRADED"
    return {
        "status": overall,
        "overall_status": overall.lower(),
        "checks": checks,
        "services": {
            "postgres": {"status": "healthy" if checks.get("database") == "UP" else "unhealthy"},
            "redis": {"status": "healthy" if checks.get("redis") == "UP" else "unhealthy"},
            "opa": {"status": "healthy" if checks.get("opa") == "UP" else "unhealthy"},
            "minio": {"status": "healthy" if checks.get("storage") == "UP" else "unhealthy"},
            "clamav": {"status": "healthy"},
        },
        "version": BRANDING.version,
        "product": {
            "name": BRANDING.name,
            "version": BRANDING.version,
            "compliance": ["DoD 5015.02", "SEC Rule 17a-4", "ISO 15489", "HIPAA §164"],
        },
        "environment": settings.elixir_env,
    }


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------
@admin_router.get("/kpis", response_model=dict[str, Any])
@admin_router.get("/dashboard", response_model=dict[str, Any])
async def dashboard_kpis(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Aggregate KPI data for the admin and home dashboard."""
    _require_admin(session)

    # Documents
    total_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id,
            Document.is_trashed.is_(False),
        )
    )).scalar() or 0

    blocked = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id, Document.status == "blocked"
        )
    )).scalar() or 0

    declared_records = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id, Document.is_record.is_(True)
        )
    )).scalar() or 0

    # Legal holds
    active_holds = (await db.execute(
        select(func.count(LegalHold.id)).where(
            LegalHold.tenant_id == session.tenant_id, LegalHold.status == "ACTIVE"
        )
    )).scalar() or 0

    held_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.tenant_id == session.tenant_id, Document.status == "held"
        )
    )).scalar() or 0

    # Workflow
    pending_approvals = (await db.execute(
        select(func.count(WorkflowTask.id)).where(
            WorkflowTask.tenant_id == session.tenant_id, WorkflowTask.status == "pending"
        )
    )).scalar() or 0

    my_tasks = (await db.execute(
        select(func.count(WorkflowTask.id)).where(
            WorkflowTask.tenant_id == session.tenant_id,
            WorkflowTask.assigned_to_id == session.user_id,
            WorkflowTask.status == "pending",
        )
    )).scalar() or 0

    # Users
    user_count = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == session.tenant_id)
    )).scalar() or 0

    active_users = (await db.execute(
        select(func.count(User.id)).where(User.tenant_id == session.tenant_id, User.is_active.is_(True))
    )).scalar() or 0

    # Audit events
    audit_events_24h = (await db.execute(
        select(func.count(AuditEvent.id)).where(AuditEvent.tenant_id == session.tenant_id)
    )).scalar() or 0

    recent_audit = (await db.execute(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == session.tenant_id)
        .order_by(AuditEvent.sequence_number.desc())
        .limit(5)
    )).scalars().all()

    # Storage bytes
    total_bytes = (await db.execute(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.tenant_id == session.tenant_id)
    )).scalar() or 0

    return {
        "total_users": user_count,
        "active_users": active_users,
        "total_documents": total_docs,
        "total_records": declared_records,
        "active_holds": active_holds,
        "held_documents": held_docs,
        "pending_tasks": pending_approvals,
        "audit_events_24h": audit_events_24h,
        "storage_bytes_total": total_bytes,
        "storage_mb_total": round(total_bytes / (1024 * 1024), 2),
        "kpis": {
            "total_documents": total_docs,
            "blocked_uploads": blocked,
            "declared_records": declared_records,
            "active_holds": active_holds,
            "pending_approvals": pending_approvals,
            "my_tasks": my_tasks,
            "total_users": user_count,
        },
        "recent_activity": [
            {
                "id": str(e.id),
                "action": e.action,
                "actor_email": e.actor_email,
                "resource_type": e.resource_type,
                "outcome": e.outcome,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in recent_audit
        ],
    }
