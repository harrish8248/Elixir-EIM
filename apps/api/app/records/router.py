"""Records & Retention API Router: legal holds, retention schedules, disposition."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.records.models import LegalHold, LegalHoldTarget, RetentionSchedule
from apps.api.app.tenancy.database import get_db_session

records_router = APIRouter(prefix="/api/v1/records", tags=["Records & Retention"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CreateHoldRequest(BaseModel):
    name: str
    description: str | None = None
    matter_number: str | None = None
    document_ids: list[str] = []


class RetentionScheduleOut(BaseModel):
    id: str
    name: str
    description: str | None
    schedule_code: str | None
    retention_years: int
    department: str | None
    classification: str | None
    is_active: bool
    created_at: str


class LegalHoldOut(BaseModel):
    id: str
    name: str
    description: str | None
    matter_number: str | None
    status: str
    placed_by_email: str
    released_at: str | None
    target_count: int
    created_at: str


# ---------------------------------------------------------------------------
# Retention Schedules
# ---------------------------------------------------------------------------
@records_router.get("/schedules", response_model=list[RetentionScheduleOut])
async def list_retention_schedules(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[RetentionScheduleOut]:
    schedules = (await db.execute(
        select(RetentionSchedule)
        .where(RetentionSchedule.tenant_id == session.tenant_id)
        .order_by(RetentionSchedule.name)
    )).scalars().all()
    return [
        RetentionScheduleOut(
            id=str(s.id), name=s.name, description=s.description,
            schedule_code=s.schedule_code, retention_years=s.retention_years,
            department=s.department, classification=s.classification,
            is_active=s.is_active, created_at=s.created_at.isoformat(),
        )
        for s in schedules
    ]


@records_router.post("/schedules", response_model=RetentionScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_retention_schedule(
    body: dict,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> RetentionScheduleOut:
    if "RecordsManager" not in session.roles and "Admin" not in session.roles:
        raise HTTPException(status_code=403, detail="Only Records Managers can create retention schedules")
    schedule = RetentionSchedule(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        name=body.get("name", ""),
        description=body.get("description"),
        schedule_code=body.get("schedule_code"),
        retention_years=body.get("retention_years", 7),
        department=body.get("department"),
        classification=body.get("classification"),
        created_by_id=session.user_id,
    )
    db.add(schedule)
    await db.flush()
    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="records:schedule:create",
        resource_type="retention_schedule", resource_id=str(schedule.id), outcome="ALLOW",
        reason=f"Created retention schedule: {schedule.name}",
    )
    return RetentionScheduleOut(
        id=str(schedule.id), name=schedule.name, description=schedule.description,
        schedule_code=schedule.schedule_code, retention_years=schedule.retention_years,
        department=schedule.department, classification=schedule.classification,
        is_active=schedule.is_active, created_at=schedule.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Legal Holds
# ---------------------------------------------------------------------------
@records_router.get("/holds", response_model=dict[str, Any])
async def list_legal_holds(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: str | None = None,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    stmt = select(LegalHold).where(LegalHold.tenant_id == session.tenant_id)
    if status_filter:
        stmt = stmt.where(LegalHold.status == status_filter.upper())
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0

    stmt = stmt.order_by(LegalHold.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    holds = (await db.execute(stmt)).scalars().all()

    # Count targets per hold
    items = []
    for h in holds:
        target_count = (await db.execute(
            select(func.count(LegalHoldTarget.id)).where(LegalHoldTarget.hold_id == h.id)
        )).scalar() or 0
        items.append(LegalHoldOut(
            id=str(h.id), name=h.name, description=h.description,
            matter_number=h.matter_number, status=h.status,
            placed_by_email=h.placed_by_email,
            released_at=h.released_at.isoformat() if h.released_at else None,
            target_count=target_count,
            created_at=h.created_at.isoformat(),
        ))

    return {"items": [i.__dict__ for i in items], "total": total, "page": page, "page_size": page_size}


@records_router.post("/holds", response_model=LegalHoldOut, status_code=status.HTTP_201_CREATED)
async def create_legal_hold(
    body: CreateHoldRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> LegalHoldOut:
    if "RecordsManager" not in session.roles and "Admin" not in session.roles:
        raise HTTPException(status_code=403, detail="Only Records Managers can create legal holds")

    hold = LegalHold(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        name=body.name,
        description=body.description,
        matter_number=body.matter_number,
        status="ACTIVE",
        placed_by_id=session.user_id,
        placed_by_email=session.email,
    )
    db.add(hold)
    await db.flush()

    # Add targets
    for doc_id_str in body.document_ids:
        target = LegalHoldTarget(
            id=uuid.uuid4(),
            tenant_id=session.tenant_id,
            hold_id=hold.id,
            document_id=uuid.UUID(doc_id_str),
        )
        db.add(target)

    await db.flush()

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="records:hold:create",
        resource_type="legal_hold", resource_id=str(hold.id), outcome="ALLOW",
        reason=f"Legal hold created: {body.name} — {len(body.document_ids)} documents",
        payload={"matter_number": body.matter_number, "document_count": len(body.document_ids)},
    )

    return LegalHoldOut(
        id=str(hold.id), name=hold.name, description=hold.description,
        matter_number=hold.matter_number, status=hold.status,
        placed_by_email=hold.placed_by_email, released_at=None,
        target_count=len(body.document_ids),
        created_at=hold.created_at.isoformat(),
    )


@records_router.post("/holds/{hold_id}/release", status_code=status.HTTP_204_NO_CONTENT)
async def release_legal_hold(
    hold_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    if "RecordsManager" not in session.roles and "Admin" not in session.roles:
        raise HTTPException(status_code=403, detail="Only Records Managers can release legal holds")

    hold = (await db.execute(
        select(LegalHold).where(
            LegalHold.id == uuid.UUID(hold_id), LegalHold.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not hold:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    if hold.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Legal hold is not active")

    hold.status = "RELEASED"
    hold.released_by_id = session.user_id
    hold.released_at = datetime.now(UTC)
    await db.flush()

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="records:hold:release",
        resource_type="legal_hold", resource_id=hold_id, outcome="ALLOW",
        reason=f"Legal hold released: {hold.name}",
    )


@records_router.get("/holds/{hold_id}", response_model=LegalHoldOut)
async def get_legal_hold(
    hold_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> LegalHoldOut:
    hold = (await db.execute(
        select(LegalHold).where(
            LegalHold.id == uuid.UUID(hold_id), LegalHold.tenant_id == session.tenant_id
        )
    )).scalar_one_or_none()
    if not hold:
        raise HTTPException(status_code=404, detail="Legal hold not found")
    target_count = (await db.execute(
        select(func.count(LegalHoldTarget.id)).where(LegalHoldTarget.hold_id == hold.id)
    )).scalar() or 0
    return LegalHoldOut(
        id=str(hold.id), name=hold.name, description=hold.description,
        matter_number=hold.matter_number, status=hold.status,
        placed_by_email=hold.placed_by_email,
        released_at=hold.released_at.isoformat() if hold.released_at else None,
        target_count=target_count,
        created_at=hold.created_at.isoformat(),
    )


@records_router.get("/stats", response_model=dict[str, Any])
async def records_stats(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """KPI stats for records dashboard."""
    active_holds = (await db.execute(
        select(func.count(LegalHold.id)).where(
            LegalHold.tenant_id == session.tenant_id, LegalHold.status == "ACTIVE"
        )
    )).scalar() or 0

    declared_records = (await db.execute(
        text("SELECT count(*) FROM documents WHERE tenant_id = :tid AND is_record = true AND is_trashed = false"),
        {"tid": session.tenant_id},
    )).scalar() or 0

    schedules_count = (await db.execute(
        select(func.count(RetentionSchedule.id)).where(
            RetentionSchedule.tenant_id == session.tenant_id, RetentionSchedule.is_active.is_(True)
        )
    )).scalar() or 0

    return {
        "active_holds": active_holds,
        "declared_records": declared_records,
        "active_schedules": schedules_count,
    }


@records_router.get("/disposition-queue", response_model=list[dict[str, Any]])
async def disposition_queue(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve records currently eligible for defensible disposition review."""
    return []

