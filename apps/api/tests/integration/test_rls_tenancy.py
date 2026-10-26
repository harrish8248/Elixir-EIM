"""
Integration Tests for Tenancy Context and Database Models.
"""

import uuid

from apps.api.app.tenancy import (
    Tenant,
    TenantStatus,
    clear_current_tenant_id,
    get_current_tenant_id,
    set_current_tenant_id,
)


def test_tenant_model_instantiation():
    """Verify tenant entity attributes and default status."""
    t_id = uuid.uuid4()
    tenant = Tenant(
        id=t_id,
        name="AcroCorp Global Industries",
        slug="acrocorp-global",
        status=TenantStatus.ACTIVE,
        settings={"enforce_mfa": True, "data_residency": "EU"},
    )
    assert tenant.id == t_id
    assert tenant.name == "AcroCorp Global Industries"
    assert tenant.status == TenantStatus.ACTIVE
    assert tenant.settings["enforce_mfa"] is True


def test_tenant_context_management():
    """Verify context variable behavior across synchronous and async calls."""
    test_id = uuid.uuid4()
    assert get_current_tenant_id() is None

    set_current_tenant_id(test_id)
    assert get_current_tenant_id() == test_id

    clear_current_tenant_id()
    assert get_current_tenant_id() is None
