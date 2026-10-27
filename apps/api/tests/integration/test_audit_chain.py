"""Integration Tests for Append-Only Audit Ledger and Cryptographic Hash Chain.

Tests:
1. Immutability: PostgreSQL triggers and role permissions strictly block UPDATE and DELETE.
2. Concurrency Safety: Parallel concurrent writes produce strictly contiguous sequences and valid chains.
3. Tamper Detection: Modifying a row directly in the database is detected by verify_audit_hash_chain.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from apps.api.app.audit.service import (
    record_audit_event,
    verify_audit_hash_chain,
)
from apps.api.app.tenancy.database import AsyncSessionFactory


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_audit_ledger_immutability_triggers_block_mutation():
    """Runtime application connection MUST NOT be able to UPDATE or DELETE audit events."""
    test_tenant_id = uuid.uuid4()

    # 1. Insert an audit event
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(test_tenant_id)},
        )
        # Create tenant row for FK / locking
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(test_tenant_id), "name": "Audit Test Corp", "slug": f"audit-test-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(test_tenant_id)},
        )
        event = await record_audit_event(
            db,
            tenant_id=test_tenant_id,
            actor_id="admin-1",
            actor_email="admin@audittest.com",
            action="policy:update",
            resource_type="policy",
            resource_id="pol-1",
            outcome="ALLOW",
            reason="Initial configuration",
        )
        await db.commit()
        event_id = event.id

    # 2. Attempt UPDATE on the audit event: MUST be rejected by trigger / role permissions
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(test_tenant_id)},
        )
        with pytest.raises(DBAPIError) as exc_info:
            await db.execute(
                text("UPDATE audit_events SET reason = 'tampered' WHERE id = :id"),
                {"id": str(event_id)},
            )
            await db.commit()
        assert "CRITICAL SECURITY VIOLATION" in str(exc_info.value) or "permission denied" in str(exc_info.value).lower()

    # 3. Attempt DELETE on the audit event: MUST be rejected
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(test_tenant_id)},
        )
        with pytest.raises(DBAPIError) as exc_info:
            await db.execute(
                text("DELETE FROM audit_events WHERE id = :id"),
                {"id": str(event_id)},
            )
            await db.commit()
        assert "CRITICAL SECURITY VIOLATION" in str(exc_info.value) or "permission denied" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_audit_concurrency_safe_parallel_writes():
    """Writing 10 audit events concurrently for the same tenant must preserve contiguous sequence and valid hashes."""
    tenant_id = uuid.uuid4()

    # Create tenant row
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "Parallel Test Corp", "slug": f"par-test-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    async def _write_one(idx: int):
        async with AsyncSessionFactory() as db:
            await db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await record_audit_event(
                db,
                tenant_id=tenant_id,
                actor_id=f"worker-{idx}",
                actor_email=f"worker{idx}@test.com",
                action="document:view",
                resource_type="document",
                resource_id=f"doc-{idx}",
                outcome="ALLOW",
                reason=f"Parallel access task {idx}",
            )
            await db.commit()

    # Launch 10 concurrent writes
    await asyncio.gather(*[_write_one(i) for i in range(10)])

    # Verify audit chain integrity
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        summary = await verify_audit_hash_chain(db, tenant_id=tenant_id)
        assert summary.is_valid is True
        assert summary.total_events == 10
        assert len(summary.violations) == 0


@pytest.mark.asyncio
async def test_audit_chain_tamper_detection_on_altered_row():
    """Tampering with an audit row directly in PostgreSQL must be detected by verify_audit_hash_chain."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from apps.api.app.platform.config import settings

    tenant_id = uuid.uuid4()

    # 1. Create tenant and 3 valid audit events
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "Tamper Test Corp", "slug": f"tamper-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    for i in range(1, 4):
        async with AsyncSessionFactory() as db:
            await db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await record_audit_event(
                db,
                tenant_id=tenant_id,
                actor_id=f"user-{i}",
                actor_email=f"user{i}@tamper.com",
                action="document:update",
                resource_type="document",
                resource_id=f"doc-{i}",
                outcome="ALLOW",
                reason=f"Legitimate update {i}",
            )
            await db.commit()

    # Verify intact before tampering
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        initial_summary = await verify_audit_hash_chain(db, tenant_id=tenant_id)
        assert initial_summary.is_valid is True

    # 2. Simulate direct database compromise (using owner role, disabling trigger to tamper row 2)
    owner_engine = create_async_engine(settings.migration_database_url)
    async with owner_engine.begin() as conn:
        # Disable trigger temporarily to alter the record
        await conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER trg_block_audit_events_update;"))
        await conn.execute(
            text(
                "UPDATE audit_events SET reason = 'FRAUDULENT_ALTERATION' "
                "WHERE tenant_id = :tenant_id AND sequence_number = 2"
            ),
            {"tenant_id": str(tenant_id)},
        )
        await conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_block_audit_events_update;"))
    await owner_engine.dispose()

    # 3. Verify audit chain: MUST detect violation on sequence 2 and 3!
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        tampered_summary = await verify_audit_hash_chain(db, tenant_id=tenant_id)
        assert tampered_summary.is_valid is False
        assert len(tampered_summary.violations) >= 1
        tampered_seqs = [v.sequence_number for v in tampered_summary.violations]
        assert 2 in tampered_seqs


@pytest.mark.asyncio
async def test_audit_events_api_query_and_pagination():
    """Verify GET /api/v1/audit/events returns paginated append-only records for Auditor."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.app.identity.session import SESSION_COOKIE_NAME, session_manager
    from apps.api.app.main import app

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Create tenant row
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "Audit Query Corp", "slug": f"aud-q-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    # 2. Insert 4 audit events
    for i in range(1, 5):
        async with AsyncSessionFactory() as db:
            await db.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
            await record_audit_event(
                db,
                tenant_id=tenant_id,
                actor_id="auditor-1",
                actor_email="auditor@test.com",
                action="document:access",
                resource_type="document",
                resource_id=f"doc-{i}",
                outcome="ALLOW",
                reason=f"Routine check {i}",
            )
            await db.commit()

    # 3. Create Auditor session
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        email="auditor@test.com",
        username="auditor1",
        roles=["Auditor"],
        clearance_level=3,
    )

    # 4. Query paginated audit events
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/audit/events?page=1&page_size=2",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 4
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert "current_hash" in data["items"][0]
        assert "prev_hash" in data["items"][0]


@pytest.mark.asyncio
async def test_audit_verify_api_endpoint():
    """Verify POST /api/v1/audit/verify endpoint and permission gating."""
    from httpx import ASGITransport, AsyncClient

    from apps.api.app.identity.session import SESSION_COOKIE_NAME, session_manager
    from apps.api.app.main import app

    tenant_id = uuid.uuid4()
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "Audit Verify Corp", "slug": f"aud-v-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    # A. Auditor can verify
    auditor_session = await session_manager.create_session(
        user_id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="auditor@test.com",
        username="auditor",
        roles=["Auditor"],
        clearance_level=3,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/audit/verify",
            cookies={SESSION_COOKIE_NAME: auditor_session.session_id},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_valid"] is True

    # B. Unauthorized user (KnowledgeWorker) is rejected with 403
    kw_session = await session_manager.create_session(
        user_id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="worker@test.com",
        username="worker",
        roles=["KnowledgeWorker"],
        clearance_level=1,
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/audit/verify",
            cookies={SESSION_COOKIE_NAME: kw_session.session_id},
        )
        assert res.status_code == 403

