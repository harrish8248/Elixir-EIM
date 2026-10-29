"""Audit Domain Service: Concurrency-Safe Linear SHA-256 Hash Chain Ledger.

Implements immutable audit logging with per-tenant cryptographic continuity.
Enforces strict secret redaction (no passwords, tokens, cookies, or raw document content).
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.models import AuditEvent
from apps.api.app.platform.logging import logger

GENESIS_HASH = "0" * 64

# Sensitive keywords strictly forbidden from audit payloads
SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "authorization",
    "cookie",
    "access_token",
    "id_token",
    "refresh_token",
    "csrf_token",
    "private_key",
    "content",
    "raw_data",
}


def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively scrub secrets, tokens, credentials, and bulky file contents from audit payloads."""
    if not payload:
        return {}

    sanitized: dict[str, Any] = {}
    for k, v in payload.items():
        k_lower = str(k).lower()
        if any(s in k_lower for s in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED_SECURITY_DATA]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_payload(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_payload(item) if isinstance(item, dict) else item
                for item in v
            ]
        elif isinstance(v, (str, int, float, bool)) or v is None:
            sanitized[k] = v
        else:
            sanitized[k] = str(v)
    return sanitized


def canonical_event_json(
    tenant_id: UUID | str,
    sequence_number: int,
    prev_hash: str,
    timestamp_iso: str,
    actor_id: str,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    reason: str | None,
    correlation_id: str,
    payload: dict[str, Any],
) -> str:
    """
    Produce a deterministic, canonical JSON representation of an audit event for hashing.
    Keys are sorted, separators are compact (no spaces), ensuring cross-platform repeatability.
    """
    canonical_dict = {
        "action": action,
        "actor_email": actor_email,
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "payload": payload,
        "prev_hash": prev_hash,
        "reason": reason or "",
        "resource_id": resource_id,
        "resource_type": resource_type,
        "sequence_number": sequence_number,
        "tenant_id": str(tenant_id),
        "timestamp": timestamp_iso,
    }
    return json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))


def compute_event_hash(
    tenant_id: UUID | str,
    sequence_number: int,
    prev_hash: str,
    timestamp_iso: str,
    actor_id: str,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    reason: str | None,
    correlation_id: str,
    payload: dict[str, Any],
) -> str:
    """Compute cryptographic SHA-256 digest of an audit event over its canonical representation."""
    canonical_str = canonical_event_json(
        tenant_id=tenant_id,
        sequence_number=sequence_number,
        prev_hash=prev_hash,
        timestamp_iso=timestamp_iso,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        correlation_id=correlation_id,
        payload=payload,
    )
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


async def record_audit_event(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    actor_id: str,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
    payload: dict[str, Any] | None = None,
    policy_version: str = "1.0",
) -> AuditEvent:
    """
    Record an immutable audit event with per-tenant SHA-256 linear hash chaining.
    Concurrency-Safe: Acquires an exclusive row-level lock on the target tenant during hash generation
    to guarantee strictly monotonic sequence numbers and unbroken cryptographic chains.
    """
    clean_payload = sanitize_payload(payload)
    clean_payload["policy_version"] = policy_version

    corr_id = correlation_id or str(uuid.uuid4())
    now = datetime.now(UTC)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # Set PostgreSQL tenant context for RLS enforcement
    await db.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
        {"tenant_id": str(tenant_id)},
    )

    # 1. Acquire exclusive lock on target tenant to prevent concurrent sequence races
    await db.execute(
        text("SELECT id FROM tenants WHERE id = :tenant_id FOR UPDATE"),
        {"tenant_id": str(tenant_id)},
    )

    # 2. Fetch the latest sequence record for this tenant
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.sequence_number.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    last_event = res.scalar_one_or_none()

    if last_event is None:
        sequence_number = 1
        prev_hash = GENESIS_HASH
    else:
        sequence_number = last_event.sequence_number + 1
        prev_hash = last_event.current_hash

    # 3. Calculate current SHA-256 seal
    current_hash = compute_event_hash(
        tenant_id=tenant_id,
        sequence_number=sequence_number,
        prev_hash=prev_hash,
        timestamp_iso=now_iso,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        correlation_id=corr_id,
        payload=clean_payload,
    )

    # 4. Insert immutable audit event
    event = AuditEvent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sequence_number=sequence_number,
        prev_hash=prev_hash,
        current_hash=current_hash,
        timestamp=now,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=corr_id,
        payload=clean_payload,
    )
    db.add(event)
    await db.flush()

    logger.info(
        f"Audit [{outcome}]: {action} on {resource_type}:{resource_id} by {actor_email} "
        f"(Tenant: {tenant_id}, Seq: {sequence_number}, Hash: {current_hash[:12]}...)"
    )
    return event


class ChainViolation(BaseModel):
    sequence_number: int
    tenant_id: UUID
    event_id: UUID
    violation_type: str
    details: str


class AuditVerificationSummary(BaseModel):
    is_valid: bool
    total_events: int
    tenants_checked: int
    violations: list[ChainViolation] = Field(default_factory=list)


async def verify_audit_hash_chain(
    db: AsyncSession,
    tenant_id: UUID | None = None,
) -> AuditVerificationSummary:
    """
    Cryptographically verify the integrity of the audit ledger.
    Recalculates every SHA-256 seal and validates sequence monotonicity and hash linkage.
    Detects any unauthorized modification, deletion, reordering, or insertion.
    """
    query = select(AuditEvent).order_by(AuditEvent.tenant_id, AuditEvent.sequence_number.asc())
    if tenant_id:
        query = query.where(AuditEvent.tenant_id == tenant_id)

    res = await db.execute(query)
    events = res.scalars().all()

    violations: list[ChainViolation] = []
    tenants_seen: set[UUID] = set()

    current_tenant: UUID | None = None
    expected_sequence = 1
    expected_prev_hash = GENESIS_HASH

    for ev in events:
        tenants_seen.add(ev.tenant_id)
        if current_tenant != ev.tenant_id:
            current_tenant = ev.tenant_id
            expected_sequence = 1
            expected_prev_hash = GENESIS_HASH

        # 1. Check sequence number monotonicity
        if ev.sequence_number != expected_sequence:
            violations.append(
                ChainViolation(
                    sequence_number=ev.sequence_number,
                    tenant_id=ev.tenant_id,
                    event_id=ev.id,
                    violation_type="SEQUENCE_GAP_OR_REORDER",
                    details=f"Expected sequence {expected_sequence}, found {ev.sequence_number}",
                )
            )

        # 2. Check previous hash continuity
        if ev.prev_hash != expected_prev_hash:
            violations.append(
                ChainViolation(
                    sequence_number=ev.sequence_number,
                    tenant_id=ev.tenant_id,
                    event_id=ev.id,
                    violation_type="PREV_HASH_MISMATCH",
                    details=f"Previous hash broken: expected {expected_prev_hash[:12]}..., got {ev.prev_hash[:12]}...",
                )
            )

        # 3. Recalculate canonical hash
        now_iso = ev.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        recomputed_hash = compute_event_hash(
            tenant_id=ev.tenant_id,
            sequence_number=ev.sequence_number,
            prev_hash=ev.prev_hash,
            timestamp_iso=now_iso,
            actor_id=ev.actor_id,
            actor_email=ev.actor_email,
            action=ev.action,
            resource_type=ev.resource_type,
            resource_id=ev.resource_id,
            outcome=ev.outcome,
            reason=ev.reason,
            correlation_id=ev.correlation_id,
            payload=ev.payload,
        )

        if ev.current_hash != recomputed_hash:
            violations.append(
                ChainViolation(
                    sequence_number=ev.sequence_number,
                    tenant_id=ev.tenant_id,
                    event_id=ev.id,
                    violation_type="RECORD_TAMPERED_HASH_MISMATCH",
                    details=(
                        f"Stored hash '{ev.current_hash}' does not match recomputed seal '{recomputed_hash}'. "
                        f"Row content was altered!"
                    ),
                )
            )

        # Advance state
        expected_sequence = ev.sequence_number + 1
        expected_prev_hash = ev.current_hash

    is_valid = len(violations) == 0
    return AuditVerificationSummary(
        is_valid=is_valid,
        total_events=len(events),
        tenants_checked=len(tenants_seen),
        violations=violations,
    )
