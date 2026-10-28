"""Workflow & Approvals API Router."""

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
from apps.api.app.tenancy.database import get_db_session
from apps.api.app.workflow.models import WorkflowTask

workflow_router = APIRouter(prefix="/api/v1/workflow", tags=["Workflow & Approvals"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class SubmitApprovalRequest(BaseModel):
    document_id: str
    title: str
    description: str | None = None
    assigned_to_id: str | None = None
    assigned_to_email: str | None = None
    priority: str = "normal"


class DecisionRequest(BaseModel):
    decision: str  # approved | rejected
    reason: str  # mandatory


class TaskOut(BaseModel):
    id: str
    document_id: str
    document_name: str | None
    title: str
    description: str | None
    task_type: str
    status: str
    priority: str
    submitted_by_email: str
    assigned_to_email: str | None
    decision_by_email: str | None
    decision_at: str | None
    decision_reason: str | None
    due_date: str | None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@workflow_router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def submit_approval(
    body: SubmitApprovalRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> TaskOut:
    """Submit a document for approval. Self-approval is blocked."""
    # Validate document exists and user can access it
    doc_res = (await db.execute(
        text("SELECT id, name FROM documents WHERE id = :doc_id AND tenant_id = :tid"),
        {"doc_id": body.document_id, "tid": session.tenant_id},
    )).mappings().one_or_none()
    if not doc_res:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_name = str(doc_res["name"])

    # Block self-approval: if assigned to same user as submitter
    if body.assigned_to_id and body.assigned_to_id == str(session.user_id):
        await record_audit_event(
            db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
            actor_email=session.email, action="workflow:approval:self_approval_blocked",
            resource_type="workflow_task", resource_id="new", outcome="DENY",
            reason="Self-approval attempt blocked",
        )
        raise HTTPException(
            status_code=403,
            detail="Self-approval is not permitted. Please assign the task to a different approver.",
        )

    task = WorkflowTask(
        id=uuid.uuid4(),
        tenant_id=session.tenant_id,
        document_id=uuid.UUID(body.document_id),
        title=body.title,
        description=body.description,
        task_type="approval",
        status="pending",
        priority=body.priority,
        submitted_by_id=session.user_id,
        submitted_by_email=session.email,
        assigned_to_id=uuid.UUID(body.assigned_to_id) if body.assigned_to_id else None,
        assigned_to_email=body.assigned_to_email,
    )
    db.add(task)
    await db.flush()

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action="workflow:approval:submitted",
        resource_type="workflow_task", resource_id=str(task.id), outcome="ALLOW",
        reason=f"Approval submitted for: {doc_name}",
        payload={"document_id": str(task.document_id), "document_name": doc_name, "priority": body.priority},
    )

    return TaskOut(
        id=str(task.id), document_id=str(task.document_id), document_name=doc_name,
        title=task.title, description=task.description, task_type=task.task_type,
        status=task.status, priority=task.priority,
        submitted_by_email=task.submitted_by_email,
        assigned_to_email=task.assigned_to_email,
        decision_by_email=None, decision_at=None, decision_reason=None, due_date=None,
        created_at=task.created_at.isoformat(), updated_at=task.updated_at.isoformat(),
    )


@workflow_router.get("/tasks", response_model=dict[str, Any])
async def list_tasks(
    mine_only: bool = True,
    task_status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List workflow tasks. mine_only=true shows tasks assigned to the current user."""
    stmt = select(WorkflowTask).where(WorkflowTask.tenant_id == session.tenant_id)

    if mine_only:
        stmt = stmt.where(WorkflowTask.assigned_to_id == session.user_id)
    if task_status:
        stmt = stmt.where(WorkflowTask.status == task_status)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    stmt = stmt.order_by(WorkflowTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    tasks = (await db.execute(stmt)).scalars().all()

    # Lookup document names
    items = []
    for t in tasks:
        doc_name = None
        doc = (await db.execute(
            text("SELECT name FROM documents WHERE id = :doc_id"),
            {"doc_id": t.document_id},
        )).scalar_one_or_none()
        doc_name = doc
        items.append({
            "id": str(t.id),
            "document_id": str(t.document_id),
            "document_name": doc_name,
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "status": t.status,
            "priority": t.priority,
            "submitted_by_email": t.submitted_by_email,
            "assigned_to_email": t.assigned_to_email,
            "decision_by_email": t.decision_by_email,
            "decision_at": t.decision_at.isoformat() if t.decision_at else None,
            "decision_reason": t.decision_reason,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@workflow_router.post("/tasks/{task_id}/decide", response_model=dict[str, Any])
async def decide_task(
    task_id: str,
    body: DecisionRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Approve or reject a task. Reason is mandatory. Self-approval blocked."""
    task = (await db.execute(
        select(WorkflowTask).where(
            WorkflowTask.id == uuid.UUID(task_id),
            WorkflowTask.tenant_id == session.tenant_id,
        )
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task is already {task.status}")

    # Block self-approval
    if task.submitted_by_id == session.user_id:
        await record_audit_event(
            db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
            actor_email=session.email, action="workflow:approval:self_approval_blocked",
            resource_type="workflow_task", resource_id=task_id, outcome="DENY",
            reason="Self-approval attempt blocked at decision",
        )
        raise HTTPException(
            status_code=403,
            detail="Self-approval is not permitted. The task must be decided by a different user.",
        )

    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="Decision must be 'approved' or 'rejected'")
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=422, detail="A decision reason is required")

    task.status = body.decision
    task.decision_by_id = session.user_id
    task.decision_by_email = session.email
    task.decision_at = datetime.now(UTC)
    task.decision_reason = body.reason
    task.updated_at = datetime.now(UTC)
    await db.flush()

    await record_audit_event(
        db, tenant_id=session.tenant_id, actor_id=str(session.user_id),
        actor_email=session.email, action=f"workflow:approval:{body.decision}",
        resource_type="workflow_task", resource_id=task_id, outcome="ALLOW",
        reason=f"Task {body.decision}: {body.reason}",
        payload={"decision": body.decision, "task_id": task_id},
    )

    return {
        "id": str(task.id),
        "status": task.status,
        "decision_by_email": task.decision_by_email,
        "decision_at": task.decision_at.isoformat() if task.decision_at else None,
        "decision_reason": task.decision_reason,
    }


@workflow_router.get("/stats", response_model=dict[str, Any])
async def workflow_stats(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    my_pending = (await db.execute(
        select(func.count(WorkflowTask.id)).where(
            WorkflowTask.tenant_id == session.tenant_id,
            WorkflowTask.assigned_to_id == session.user_id,
            WorkflowTask.status == "pending",
        )
    )).scalar() or 0

    total_pending = (await db.execute(
        select(func.count(WorkflowTask.id)).where(
            WorkflowTask.tenant_id == session.tenant_id,
            WorkflowTask.status == "pending",
        )
    )).scalar() or 0

    return {"my_pending_tasks": my_pending, "total_pending": total_pending}
