"""
Single Source of Truth for Product Identity, Naming, and Corporate Branding.
Never hardcode the product name or short name in application logic or UI components.
"""

from pydantic import BaseModel, ConfigDict


class ProductBrandingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = "Elixir Enterprise Information Management"
    short_name: str = "Elixir EIM"
    product_code: str = "ELIXIR_EIM"
    version: str = "1.0.0"
    build_version: str = "1.0.0-build.20261026"
    api_version: str = "v1"
    vendor: str = "Elixir Enterprise Software Inc."
    copyright_statement: str = "© 2026 Elixir Enterprise Software Inc. All rights reserved."
    support_url: str = "https://support.elixireim.internal"
    docs_url: str = "https://docs.elixireim.internal"
    default_theme: str = "enterprise_navy"
    trust_layer_label: str = "Elixir Trust Layer (Governance, Guardrails, & Audit)"


# Single immutable global branding constant
BRANDING: ProductBrandingConfig = ProductBrandingConfig()
