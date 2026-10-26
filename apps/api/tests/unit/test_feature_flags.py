"""
Unit Tests for Platform Feature Flag Service.
"""

import uuid

from apps.api.app.platform.feature_flags.service import FeatureFlagService


def test_feature_flags_hierarchy():
    """Verify default values and per-tenant override priority."""
    svc = FeatureFlagService()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    # Core 1.0 module is enabled by default
    assert svc.is_enabled("module_content_services") is True
    # 1.1 capture feature is disabled by default
    assert svc.is_enabled("module_capture_idp") is False

    # Enable capture for tenant A only (canary / gradual rollout)
    svc.set_tenant_override(tenant_a, "module_capture_idp", True)

    assert svc.is_enabled("module_capture_idp", tenant_id=tenant_a) is True
    assert svc.is_enabled("module_capture_idp", tenant_id=tenant_b) is False
    assert svc.is_enabled("module_capture_idp") is False

    # Clear override
    svc.clear_tenant_override(tenant_a, "module_capture_idp")
    assert svc.is_enabled("module_capture_idp", tenant_id=tenant_a) is False
