"""Policy & Ingestion Guardrails API Router.

Provides real, database-persisted tenant guardrail configuration,
administrative quarantine queue management, and explainable sensitivity classification overrides.
All changes are protected by PEP / OPA Rego rules and recorded in the append-only cryptographic audit ledger.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.service import record_audit_event
from apps.api.app.content.intake.classifier import CLEARANCE_MAP, SensitivityLabel
from apps.api.app.content.intake.policy import (
    get_tenant_guardrail_config,
)
from apps.api.app.identity.router import get_current_session
from apps.api.app.identity.session import SessionData
from apps.api.app.pep.policy import require_permission
from apps.api.app.tenancy.database import get_db_session

logger = logging.getLogger("elixir.guardrails.router")

guardrails_router = APIRouter(prefix="/api/v1/guardrails", tags=["Guardrails & Policy"])


async def get_guardrail_db(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_db_session),
) -> AsyncSession:
    """Ensure PostgreSQL session tenant_id is set for RLS on tenant_guardrails and quarantine_items."""
    try:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(session.tenant_id)},
        )
    except Exception as exc:
        logger.warning(f"RLS context deferred: {exc}")
    return db


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GuardrailPolicyResponse(BaseModel):
    tenant_id: str
    max_upload_bytes: int
    max_upload_mb: int
    allowed_types: list[str]
    blocked_types: list[str]
    quarantine_types: list[str]
    archive_max_depth: int
    archive_max_members: int
    archive_max_ratio: float
    clamav_enforce: bool  # Non-negotiable, always True
    strict_magic_bytes: bool
    min_clearance_restricted: int
    sec17a4_mode: bool
    updated_at: str | None
    updated_by: str | None
    is_persisted: bool = True


class UpdateGuardrailPolicyRequest(BaseModel):
    max_upload_mb: int = Field(ge=1, le=500, description="Max file upload size in MB (1-500)")
    allowed_types: list[str] | None = None
    blocked_types: list[str] | None = None
    quarantine_types: list[str] | None = None
    archive_max_depth: int = Field(ge=1, le=10, default=3)
    archive_max_members: int = Field(ge=10, le=5000, default=500)
    archive_max_ratio: float = Field(ge=5.0, le=500.0, default=100.0)
    strict_magic_bytes: bool = True
    min_clearance_restricted: int = Field(ge=2, le=5, default=3)
    sec17a4_mode: bool = False


class QuarantineItemResponse(BaseModel):
    id: str
    tenant_id: str
    filename: str
    detected_mime: str
    size_bytes: int
    content_hash: str
    reason: str
    status: str
    quarantined_by: str
    created_at: str
    metadata: dict[str, Any]


class ClassificationOverrideRequest(BaseModel):
    target_label: SensitivityLabel
    reason: str = Field(min_length=5, max_length=500)


# ---------------------------------------------------------------------------
# Guardrail Policy Endpoints
# ---------------------------------------------------------------------------

@guardrails_router.get(
    "/policy",
    response_model=GuardrailPolicyResponse,
    summary="Get active tenant guardrails and ingestion policies",
)
async def get_guardrail_policy(
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("guardrails:read", "policy")),
) -> GuardrailPolicyResponse:
    """Retrieve real persisted guardrail policy for the authenticated tenant."""
    config = await get_tenant_guardrail_config(session.tenant_id, db)

    res = await db.execute(
        text("SELECT updated_at, updated_by FROM tenant_guardrails WHERE tenant_id = :tenant_id"),
        {"tenant_id": str(session.tenant_id)},
    )
    row = res.fetchone()
    updated_at_str = row[0].isoformat() if row and row[0] else None
    updated_by_str = row[1] if row and row[1] else "system"

    return GuardrailPolicyResponse(
        tenant_id=str(session.tenant_id),
        max_upload_bytes=config.max_upload_bytes,
        max_upload_mb=int(config.max_upload_bytes // (1024 * 1024)),
        allowed_types=config.allowed_types,
        blocked_types=config.blocked_types,
        quarantine_types=config.quarantine_types,
        archive_max_depth=config.archive_max_depth,
        archive_max_members=config.archive_max_members,
        archive_max_ratio=config.archive_max_ratio,
        clamav_enforce=True,  # Non-negotiable server invariant
        strict_magic_bytes=config.strict_magic_bytes,
        min_clearance_restricted=config.min_clearance_restricted,
        sec17a4_mode=config.sec17a4_mode,
        updated_at=updated_at_str,
        updated_by=updated_by_str,
        is_persisted=True,
    )


@guardrails_router.put(
    "/policy",
    response_model=GuardrailPolicyResponse,
    summary="Update tenant guardrails and ingestion policies (Admin only)",
)
async def update_guardrail_policy(
    req: UpdateGuardrailPolicyRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("guardrails:admin", "policy")),
) -> GuardrailPolicyResponse:
    """Update tenant guardrail configuration in PostgreSQL with audit ledger diff recording."""
    old_config = await get_tenant_guardrail_config(session.tenant_id, db)
    max_bytes = req.max_upload_mb * 1024 * 1024

    # Ensure dangerous executables remain non-negotiably blocked
    blocked_set = set(req.blocked_types) if req.blocked_types is not None else set(old_config.blocked_types)
    for dangerous in ["exe", "dll", "msi", "bat", "cmd", "ps1", "sh", "js", "vbs", "jar", "apk"]:
        blocked_set.add(dangerous)

    allowed_list = req.allowed_types if req.allowed_types is not None else old_config.allowed_types
    quarantine_list = req.quarantine_types if req.quarantine_types is not None else old_config.quarantine_types

    # Persist to database
    await db.execute(
        text(
            """
            INSERT INTO tenant_guardrails (
                tenant_id, max_upload_bytes, allowed_types, blocked_types, quarantine_types,
                archive_max_depth, archive_max_members, archive_max_ratio,
                clamav_enforce, strict_magic_bytes, min_clearance_restricted, sec17a4_mode,
                updated_at, updated_by
            )
            VALUES (
                :tenant_id, :max_upload_bytes, :allowed_types, :blocked_types, :quarantine_types,
                :archive_max_depth, :archive_max_members, :archive_max_ratio,
                true, :strict_magic_bytes, :min_clearance_restricted, :sec17a4_mode,
                now(), :updated_by
            )
            ON CONFLICT (tenant_id) DO UPDATE SET
                max_upload_bytes = EXCLUDED.max_upload_bytes,
                allowed_types = EXCLUDED.allowed_types,
                blocked_types = EXCLUDED.blocked_types,
                quarantine_types = EXCLUDED.quarantine_types,
                archive_max_depth = EXCLUDED.archive_max_depth,
                archive_max_members = EXCLUDED.archive_max_members,
                archive_max_ratio = EXCLUDED.archive_max_ratio,
                clamav_enforce = true,
                strict_magic_bytes = EXCLUDED.strict_magic_bytes,
                min_clearance_restricted = EXCLUDED.min_clearance_restricted,
                sec17a4_mode = EXCLUDED.sec17a4_mode,
                updated_at = now(),
                updated_by = EXCLUDED.updated_by
            """
        ),
        {
            "tenant_id": str(session.tenant_id),
            "max_upload_bytes": max_bytes,
            "allowed_types": json.dumps(allowed_list),
            "blocked_types": json.dumps(sorted(list(blocked_set))),
            "quarantine_types": json.dumps(quarantine_list),
            "archive_max_depth": req.archive_max_depth,
            "archive_max_members": req.archive_max_members,
            "archive_max_ratio": req.archive_max_ratio,
            "strict_magic_bytes": req.strict_magic_bytes,
            "min_clearance_restricted": req.min_clearance_restricted,
            "sec17a4_mode": req.sec17a4_mode,
            "updated_by": session.email,
        },
    )
    await db.commit()

    # Record audited change in cryptographic chain
    await record_audit_event(
        db,
        tenant_id=session.tenant_id,
        actor_id=str(session.user_id),
        actor_email=session.email,
        action="guardrails:policy:update",
        resource_type="tenant_guardrails",
        resource_id=str(session.tenant_id),
        outcome="ALLOW",
        reason="Tenant guardrail policy updated by administrator",
        payload={
            "before": {
                "max_upload_mb": int(old_config.max_upload_bytes // (1024 * 1024)),
                "strict_magic_bytes": old_config.strict_magic_bytes,
                "sec17a4_mode": old_config.sec17a4_mode,
            },
            "after": {
                "max_upload_mb": req.max_upload_mb,
                "strict_magic_bytes": req.strict_magic_bytes,
                "sec17a4_mode": req.sec17a4_mode,
            },
        },
    )

    now_iso = datetime.now(UTC).isoformat()
    return GuardrailPolicyResponse(
        tenant_id=str(session.tenant_id),
        max_upload_bytes=max_bytes,
        max_upload_mb=req.max_upload_mb,
        allowed_types=allowed_list,
        blocked_types=sorted(list(blocked_set)),
        quarantine_types=quarantine_list,
        archive_max_depth=req.archive_max_depth,
        archive_max_members=req.archive_max_members,
        archive_max_ratio=req.archive_max_ratio,
        clamav_enforce=True,
        strict_magic_bytes=req.strict_magic_bytes,
        min_clearance_restricted=req.min_clearance_restricted,
        sec17a4_mode=req.sec17a4_mode,
        updated_at=now_iso,
        updated_by=session.email,
        is_persisted=True,
    )


# ---------------------------------------------------------------------------
# Quarantine Queue Endpoints
# ---------------------------------------------------------------------------

@guardrails_router.get(
    "/quarantine",
    response_model=list[QuarantineItemResponse],
    summary="List quarantined items awaiting admin review",
)
async def list_quarantine_items(
    status_filter: str | None = Query("QUARANTINED"),
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("guardrails:admin", "quarantine")),
) -> list[QuarantineItemResponse]:
    """Retrieve quarantine queue items for the tenant."""
    query = "SELECT id, tenant_id, filename, detected_mime, size_bytes, content_hash, reason, status, item_metadata, quarantined_by, created_at FROM quarantine_items WHERE tenant_id = :tenant_id"
    params: dict[str, Any] = {"tenant_id": str(session.tenant_id)}

    if status_filter:
        query += " AND status = :status"
        params["status"] = status_filter

    query += " ORDER BY created_at DESC LIMIT 100"

    res = await db.execute(text(query), params)
    rows = res.fetchall()

    return [
        QuarantineItemResponse(
            id=str(r[0]),
            tenant_id=str(r[1]),
            filename=r[2],
            detected_mime=r[3],
            size_bytes=r[4],
            content_hash=r[5],
            reason=r[6],
            status=r[7],
            metadata=r[8] if isinstance(r[8], dict) else {},
            quarantined_by=r[9],
            created_at=r[10].isoformat() if r[10] else "",
        )
        for r in rows
    ]


@guardrails_router.post(
    "/quarantine/{item_id}/release",
    summary="Release quarantined item (Admin only)",
)
async def release_quarantined_item(
    item_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("guardrails:admin", "quarantine")),
) -> dict[str, Any]:
    """Release a quarantined file after administrator approval."""
    res = await db.execute(
        text("SELECT id, filename, content_hash FROM quarantine_items WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": item_id, "tenant_id": str(session.tenant_id)},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Quarantined item not found")

    await db.execute(
        text(
            """
            UPDATE quarantine_items
            SET status = 'RELEASED', reviewed_at = now(), reviewed_by = :reviewed_by
            WHERE id = :id
            """
        ),
        {"id": item_id, "reviewed_by": session.email},
    )
    await db.commit()

    await record_audit_event(
        db,
        tenant_id=session.tenant_id,
        actor_id=str(session.user_id),
        actor_email=session.email,
        action="guardrails:quarantine:release",
        resource_type="quarantine_item",
        resource_id=item_id,
        outcome="ALLOW",
        reason=f"Administrator released quarantined file '{row[1]}'",
        payload={"filename": row[1], "content_hash": row[2]},
    )

    return {"status": "RELEASED", "id": item_id, "message": f"Item '{row[1]}' released from quarantine."}


@guardrails_router.delete(
    "/quarantine/{item_id}",
    summary="Delete quarantined item permanently (Admin only)",
)
async def delete_quarantined_item(
    item_id: str,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("guardrails:admin", "quarantine")),
) -> dict[str, Any]:
    """Permanently delete a quarantined item."""
    res = await db.execute(
        text("SELECT id, filename, content_hash FROM quarantine_items WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": item_id, "tenant_id": str(session.tenant_id)},
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Quarantined item not found")

    await db.execute(
        text("DELETE FROM quarantine_items WHERE id = :id"),
        {"id": item_id},
    )
    await db.commit()

    await record_audit_event(
        db,
        tenant_id=session.tenant_id,
        actor_id=str(session.user_id),
        actor_email=session.email,
        action="guardrails:quarantine:delete",
        resource_type="quarantine_item",
        resource_id=item_id,
        outcome="ALLOW",
        reason=f"Administrator permanently purged quarantined file '{row[1]}'",
        payload={"filename": row[1], "content_hash": row[2]},
    )

    return {"status": "DELETED", "id": item_id, "message": f"Quarantined item '{row[1]}' permanently deleted."}


# ---------------------------------------------------------------------------
# Classification Override Endpoint
# ---------------------------------------------------------------------------

@guardrails_router.post(
    "/documents/{document_id}/classify-override",
    summary="Override document sensitivity classification with audited reason",
)
async def override_document_classification(
    document_id: str,
    req: ClassificationOverrideRequest,
    session: SessionData = Depends(get_current_session),
    db: AsyncSession = Depends(get_guardrail_db),
    _authz=Depends(require_permission("content:update", "document")),
) -> dict[str, Any]:
    """Manually adjust document sensitivity label with verification."""
    res = await db.execute(
        text("SELECT id, classification, sensitivity_label, name FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": document_id, "tenant_id": str(session.tenant_id)},
    )
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    current_label = doc[2]
    target_clearance = CLEARANCE_MAP[req.target_label]

    # If lowering classification (e.g. from CRITICAL to SAFE), verify user holds clearance >= 3 (RESTRICTED)
    if current_label == "CRITICAL" and req.target_label != SensitivityLabel.CRITICAL:
        if session.clearance_level < 3 and "Admin" not in session.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lowering a CRITICAL classification requires Level 3 (Restricted) clearance or Admin role.",
            )

    override_record = {
        "previous_label": current_label,
        "new_label": req.target_label.value,
        "new_clearance": target_clearance,
        "reason": req.reason,
        "actor_email": session.email,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    await db.execute(
        text(
            """
            UPDATE documents
            SET sensitivity_label = :new_label,
                classification = :new_clearance,
                classification_override = :override_json,
                updated_at = now()
            WHERE id = :id
            """
        ),
        {
            "id": document_id,
            "new_label": req.target_label.value,
            "new_clearance": target_clearance,
            "override_json": json.dumps(override_record),
        },
    )
    await db.commit()

    await record_audit_event(
        db,
        tenant_id=session.tenant_id,
        actor_id=str(session.user_id),
        actor_email=session.email,
        action="content:classification:override",
        resource_type="document",
        resource_id=document_id,
        outcome="ALLOW",
        reason=f"Classification changed from {current_label} to {req.target_label.value}: {req.reason}",
        payload=override_record,
    )

    return {
        "status": "UPDATED",
        "document_id": document_id,
        "sensitivity_label": req.target_label.value,
        "classification": target_clearance,
        "reason": req.reason,
    }
