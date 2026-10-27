"""Route-Coverage Integration Tests: Introspects all FastAPI endpoints for Policy Enforcement.

FAILS if any endpoint is neither marked protected by PDP nor in the documented public allowlist.
Verifies that adding an unprotected endpoint fails the coverage test.
"""

import pytest
from fastapi.routing import APIRoute

from apps.api.app.main import app
from apps.api.app.pep.policy import PUBLIC_ALLOWLIST


def is_route_protected(route: APIRoute) -> bool:
    """Check if a route has PEP policy enforcement via dependencies or decorator."""
    # 1. Check endpoint function attributes
    endpoint = route.endpoint
    if getattr(endpoint, "__pep_protected__", False):
        return True

    # 2. Check route-level dependencies
    for dep in route.dependencies:
        call = getattr(dep, "dependency", dep)
        if getattr(call, "__pep_protected__", False):
            return True

    # 3. Check endpoint parameter dependencies
    if hasattr(route, "dependant"):
        for sub_dep in route.dependant.dependencies:
            call = getattr(sub_dep, "call", None)
            if getattr(call, "__pep_protected__", False):
                return True

    return False


def get_unprotected_routes(app_instance) -> list[str]:
    """Return all routes that are neither protected nor on the public allowlist."""
    violations = []
    for route in app_instance.routes:
        if isinstance(route, APIRoute):
            path = route.path
            # Normalize path for allowlist check
            if path in PUBLIC_ALLOWLIST or path.rstrip("/") in PUBLIC_ALLOWLIST:
                continue

            # Skip swagger and internal openapi paths
            if path in ["/docs", "/redoc", "/api/v1/openapi.json", "/"]:
                continue

            if not is_route_protected(route):
                violations.append(f"{list(route.methods)} {path}")

    return violations


def test_all_routes_have_policy_enforcement_or_documented_allowlist():
    """Verify that every route in the production application is protected or allowlisted."""
    violations = get_unprotected_routes(app)
    assert not violations, (
        f"CRITICAL SECURITY VIOLATION: {len(violations)} route(s) lack PEP protection "
        f"and are not on the public allowlist:\n" + "\n".join(violations)
    )


def test_coverage_fails_when_unprotected_route_is_added():
    """Verify that adding an unprotected route strictly causes the coverage test to fail."""
    from fastapi import FastAPI
    test_app = FastAPI()

    # Add a mock unprotected route
    @test_app.get("/api/v1/confidential/backdoor")
    def backdoor():
        return {"leaked": True}

    violations = get_unprotected_routes(test_app)
    assert len(violations) == 1
    assert "/api/v1/confidential/backdoor" in violations[0]


# ------------------------------------------------------------------------------
# PEP Runtime Enforcement & Audit Trail Integration Tests
# ------------------------------------------------------------------------------
import uuid

from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from apps.api.app.audit.models import AuditEvent
from apps.api.app.identity.session import SESSION_COOKIE_NAME, session_manager
from apps.api.app.pep.policy import require_permission
from apps.api.app.tenancy.database import AsyncSessionFactory

# Test router to exercise all branches of require_permission dependency
pep_test_router = APIRouter(prefix="/api/v1/pep-test")


@pep_test_router.get(
    "/documents/{id}",
    dependencies=[Depends(require_permission("content:read", resource_type="document"))],
)
async def pep_test_read_doc(id: str):
    return {"status": "ok", "id": id}


@pep_test_router.post(
    "/records/{id}/lift-hold",
    dependencies=[Depends(require_permission("records:hold:lift", resource_type="record"))],
)
async def pep_test_lift_hold(id: str):
    return {"status": "lifted", "id": id}


app.include_router(pep_test_router)


@pytest.mark.asyncio
async def test_pep_runtime_allow_and_audit_trail():
    """Verify that an authorized request succeeds (200) and automatically writes an ALLOW audit event."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Create tenant row in postgres
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "PEP Allow Corp", "slug": f"pep-allow-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    # 2. Establish valid session in Redis
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        email="kw@pepcorp.com",
        username="kw",
        roles=["KnowledgeWorker"],
        department="Operations",
        clearance_level=2,
        acr="1",
        amr=["pwd"],
    )

    # 3. Call protected endpoint with permitted department & classification
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/pep-test/documents/doc-ops-101",
            cookies={SESSION_COOKIE_NAME: session.session_id},
            headers={
                "X-Resource-Department": "Operations",
                "X-Resource-Classification": "INTERNAL",
            },
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "id": "doc-ops-101"}

    # 4. Verify that PEP automatically recorded an ALLOW audit entry
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "content:read",
                AuditEvent.outcome == "ALLOW",
            )
        )
        res = await db.execute(stmt)
        audit_row = res.scalar_one_or_none()
        assert audit_row is not None
        assert audit_row.actor_email == "kw@pepcorp.com"
        assert audit_row.resource_id == "doc-ops-101"


@pytest.mark.asyncio
async def test_pep_runtime_deny_on_clearance_and_audit_trail():
    """Verify that insufficient clearance is rejected (403 ACCESS_DENIED) and writes a DENY audit event."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Create tenant row
    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "PEP Deny Corp", "slug": f"pep-deny-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    # 2. Session with clearance 1 (CONFIDENTIAL requires clearance 2)
    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        email="intern@pepcorp.com",
        username="intern",
        roles=["KnowledgeWorker"],
        department="Operations",
        clearance_level=1,
        acr="1",
        amr=["pwd"],
    )

    # 3. Call endpoint requesting CONFIDENTIAL document
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/pep-test/documents/doc-confidential-99",
            cookies={SESSION_COOKIE_NAME: session.session_id},
            headers={
                "X-Resource-Department": "Operations",
                "X-Resource-Classification": "CONFIDENTIAL",
            },
        )
        assert res.status_code == 403
        data = res.json()["detail"]
        assert data["error"] == "ACCESS_DENIED"
        assert "clearance" in data["message"].lower()

    # 4. Verify DENY audit event in DB
    async with AsyncSessionFactory() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.action == "content:read",
                AuditEvent.outcome == "DENY",
            )
        )
        res = await db.execute(stmt)
        audit_row = res.scalar_one_or_none()
        assert audit_row is not None
        assert audit_row.actor_email == "intern@pepcorp.com"


@pytest.mark.asyncio
async def test_pep_runtime_step_up_dual_control():
    """Verify dual authorization requirement: 403 STEP_UP_REQUIRED without approval, 200 with X-Approval-Token."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with AsyncSessionFactory() as db:
        await db.execute(
            text(
                "INSERT INTO tenants (id, name, slug, status, settings) "
                "VALUES (:id, :name, :slug, 'ACTIVE', '{}') ON CONFLICT DO NOTHING"
            ),
            {"id": str(tenant_id), "name": "PEP StepUp Corp", "slug": f"pep-stepup-{uuid.uuid4().hex[:6]}"},
        )
        await db.commit()

    session = await session_manager.create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        email="rm@pepcorp.com",
        username="rm",
        roles=["RecordsManager"],
        department="Governance",
        clearance_level=3,
        acr="2",
        amr=["pwd", "mfa"],
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # A. Without X-Approval-Token -> 403 STEP_UP_REQUIRED
        res_unapproved = await client.post(
            "/api/v1/pep-test/records/rec-hold-77/lift-hold",
            cookies={SESSION_COOKIE_NAME: session.session_id},
        )
        assert res_unapproved.status_code == 403
        data = res_unapproved.json()["detail"]
        assert data["error"] == "STEP_UP_REQUIRED"

        # B. With X-Approval-Token -> 200 OK
        res_approved = await client.post(
            "/api/v1/pep-test/records/rec-hold-77/lift-hold",
            cookies={SESSION_COOKIE_NAME: session.session_id},
            headers={"X-Approval-Token": "dual-custody-valid-sig-token"},
        )
        assert res_approved.status_code == 200
        assert res_approved.json() == {"status": "lifted", "id": "rec-hold-77"}


@pytest.mark.asyncio
async def test_pep_protect_decorator_and_decision_dependency():
    """Verify @protect decorator attributes and direct PdpDecision injection."""
    from unittest.mock import patch

    from apps.api.app.pep.policy import protect

    # 1. Test @protect decorator
    @protect("records:destroy", resource_type="record", default_classification="STRICT")
    async def sample_endpoint():
        return {"ok": True}

    assert sample_endpoint.__pep_protected__ is True
    assert sample_endpoint.__pep_action__ == "records:destroy"
    assert sample_endpoint.__pep_resource_type__ == "record"

    # 2. Test audit exception fallback in require_permission
    tenant_id = uuid.uuid4()
    session = await session_manager.create_session(
        user_id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="audit-fail@pepcorp.com",
        username="auditfail",
        roles=["KnowledgeWorker"],
        department="Operations",
        clearance_level=2,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("apps.api.app.pep.policy.record_audit_event", side_effect=RuntimeError("Simulated DB Disk Full")):
            res = await client.get(
                "/api/v1/pep-test/documents/doc-ops-101",
                cookies={SESSION_COOKIE_NAME: session.session_id},
                headers={
                    "X-Resource-Department": "Operations",
                    "X-Resource-Classification": "INTERNAL",
                },
            )
            # Should still return 200 despite audit failure
            assert res.status_code == 200


