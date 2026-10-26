"""
Unit Tests for Central Branding Configuration.
"""

import pytest
from pydantic import ValidationError
from apps.api.app.platform.branding import BRANDING, ProductBrandingConfig


def test_branding_single_source_of_truth():
    """Verify default product branding constants."""
    assert BRANDING.name == "Elixir Enterprise Information Management"
    assert BRANDING.short_name == "Elixir EIM"
    assert BRANDING.product_code == "ELIXIR_EIM"
    assert BRANDING.version == "1.0.0"
    assert "Elixir Enterprise Software" in BRANDING.copyright_statement
    assert "Elixir Trust Layer" in BRANDING.trust_layer_label


def test_branding_immutability():
    """Ensure branding constant cannot be altered at runtime (frozen)."""
    with pytest.raises(ValidationError):
        # Attempting mutation must fail
        BRANDING.name = "Hacked Brand"  # type: ignore[misc]
