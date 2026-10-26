"""
Feature Flag Service supporting default fallbacks and per-tenant evaluation.
"""

from typing import Dict, Optional
import uuid


class FeatureFlagService:
    """
    Evaluates feature flags using a 3-tier hierarchy:
    1. Tenant-specific override (if tenant_id provided)
    2. System default
    3. Safe default fallback (False)
    """

    def __init__(self) -> None:
        # Default registered platform flags
        self._defaults: Dict[str, bool] = {
            "module_content_services": True,
            "module_records_management": True,
            "module_workflow_automation": True,
            "module_search_engine": True,
            "module_capture_idp": False,       # 1.1 feature
            "module_case_management": False,   # 1.2 feature
            "module_guardrailed_ai": False,    # 1.4 feature
            "module_analytics_bi": False,      # 1.5 feature
            "strict_magic_bytes_check": True,
            "quarantine_virus_scan": True,
        }
        # In-memory per-tenant overrides: (tenant_id_str, flag_key) -> bool
        self._tenant_overrides: Dict[tuple[str, str], bool] = {}

    def register_default(self, key: str, enabled: bool) -> None:
        """Register a default flag state."""
        self._defaults[key] = enabled

    def set_tenant_override(self, tenant_id: uuid.UUID | str, key: str, enabled: bool) -> None:
        """Set or update an override for a specific tenant."""
        self._tenant_overrides[(str(tenant_id), key)] = enabled

    def clear_tenant_override(self, tenant_id: uuid.UUID | str, key: str) -> None:
        """Remove a tenant override."""
        self._tenant_overrides.pop((str(tenant_id), key), None)

    def is_enabled(self, key: str, tenant_id: Optional[uuid.UUID | str] = None) -> bool:
        """
        Evaluate if a flag is active for the given tenant or globally.
        """
        if tenant_id is not None:
            override = self._tenant_overrides.get((str(tenant_id), key))
            if override is not None:
                return override

        return self._defaults.get(key, False)


# Global platform feature flag service singleton
feature_flags: FeatureFlagService = FeatureFlagService()
