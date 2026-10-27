"""Integration Tests for Policy Decision Point (PDP) against real OPA container (openpolicyagent/opa:0.68.0).

Verifies RBAC, ABAC, clearance vs classification, department isolation,
dual-control require_approval, and fail-closed behavior on timeout or unreachability.
"""

import uuid

import pytest

from apps.api.app.pdp.client import PdpClient, pdp_client


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_pdp_global_admin_override():
    """GlobalAdmin must be allowed unconditionally across tenants with notify_security obligation."""
    decision = await pdp_client.evaluate(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        roles=["GlobalAdmin"],
        clearance_level=5,
        action="system:backup",
        resource_id="backup-1",
        resource_tenant_id=uuid.uuid4(),
        resource_classification="TOP_SECRET",
    )
    assert decision.is_allowed is True
    assert decision.result == "allow"
    assert "notify_security" in decision.obligations


@pytest.mark.asyncio
async def test_pdp_cross_tenant_denial():
    """Actor attempting to access another tenant's resource must be strictly denied."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    decision = await pdp_client.evaluate(
        user_id=uuid.uuid4(),
        tenant_id=tenant_a,
        roles=["KnowledgeWorker"],
        clearance_level=3,
        action="content:read",
        resource_id="doc-123",
        resource_tenant_id=tenant_b,
        resource_classification="INTERNAL",
    )
    assert decision.is_denied is True
    assert decision.result == "deny"
    assert "Cross-tenant access violation" in decision.reason
    assert "raise_security_alert" in decision.obligations


@pytest.mark.asyncio
async def test_pdp_clearance_vs_classification():
    """User clearance must equal or exceed resource classification level (ABAC)."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Clearance 2 (INTERNAL) accessing CONFIDENTIAL (level 3): must be DENIED
    denied_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["KnowledgeWorker"],
        clearance_level=2,
        department="Engineering",
        action="content:read",
        resource_id="doc-confidential",
        resource_tenant_id=tenant_id,
        resource_classification="CONFIDENTIAL",
        resource_department="Engineering",
    )
    assert denied_decision.is_denied is True
    assert "Insufficient security clearance" in denied_decision.reason

    # Clearance 3 (CONFIDENTIAL) accessing CONFIDENTIAL: must be ALLOWED
    allowed_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["KnowledgeWorker"],
        clearance_level=3,
        department="Engineering",
        action="content:read",
        resource_id="doc-confidential",
        resource_tenant_id=tenant_id,
        resource_classification="CONFIDENTIAL",
        resource_department="Engineering",
    )
    assert allowed_decision.is_allowed is True


@pytest.mark.asyncio
async def test_pdp_department_segregation():
    """Non-governance users from a different department must be denied access."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Marketing user accessing Finance document: must be DENIED
    mismatch_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["KnowledgeWorker"],
        clearance_level=2,
        department="Marketing",
        action="content:read",
        resource_id="payroll-2026",
        resource_tenant_id=tenant_id,
        resource_classification="INTERNAL",
        resource_department="Finance",
    )
    assert mismatch_decision.is_denied is True
    assert "Department isolation" in mismatch_decision.reason

    # Finance user accessing Finance document: must be ALLOWED
    matched_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["KnowledgeWorker"],
        clearance_level=2,
        department="Finance",
        action="content:read",
        resource_id="payroll-2026",
        resource_tenant_id=tenant_id,
        resource_classification="INTERNAL",
        resource_department="Finance",
    )
    assert matched_decision.is_allowed is True


@pytest.mark.asyncio
async def test_pdp_dual_control_step_up_approval():
    """Sensitive governance actions (lifting legal hold) require dual authorization."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Unapproved action: must return require_approval
    require_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["RecordsManager"],
        clearance_level=3,
        action="records:hold:lift",
        resource_id="hold-992",
        resource_tenant_id=tenant_id,
        resource_classification="CONFIDENTIAL",
        context={"has_approval": False},
    )
    assert require_decision.requires_approval is True
    assert require_decision.result == "require_approval"
    assert "step_up_mfa" in require_decision.obligations
    assert "dual_authorization" in require_decision.obligations

    # 2. Approved action: must return allow
    approved_decision = await pdp_client.evaluate(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["RecordsManager"],
        clearance_level=3,
        action="records:hold:lift",
        resource_id="hold-992",
        resource_tenant_id=tenant_id,
        resource_classification="CONFIDENTIAL",
        context={"has_approval": True},
    )
    assert approved_decision.is_allowed is True


@pytest.mark.asyncio
async def test_pdp_fail_closed_on_unreachable_opa():
    """When OPA is unreachable, PDP MUST fail closed with strict denial."""
    # Point client to a port with no listener
    broken_pdp = PdpClient(opa_url="http://127.0.0.1:59999/decision", timeout_seconds=1.0)
    decision = await broken_pdp.evaluate(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        roles=["GlobalAdmin"],
        action="content:read",
    )
    assert decision.is_denied is True
    assert decision.result == "deny"
    assert "fail closed" in decision.reason.lower()


@pytest.mark.asyncio
async def test_pdp_fail_closed_on_timeout():
    """When OPA request times out, PDP MUST fail closed with strict denial."""
    timeout_pdp = PdpClient(timeout_seconds=0.000001)
    decision = await timeout_pdp.evaluate(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        roles=["GlobalAdmin"],
        action="content:read",
    )
    assert decision.is_denied is True
    assert decision.result == "deny"
    assert "fail closed" in decision.reason.lower()
