"""
Unit Tests for Module Manifests and Registry.
"""

import pytest

from apps.api.app.platform.errors import ValidationError
from apps.api.app.platform.registry.manifest import DependencySpec, ModuleManifest
from apps.api.app.platform.registry.registry import ModuleRegistry


def test_manifest_validation():
    """Verify that a valid module manifest parses correctly."""
    manifest_data = {
        "schema_version": "1.0.0",
        "name": "audit",
        "version": "1.0.0",
        "title": "Tamper-Evident Audit Ledger",
        "description": "Cryptographically verifiable SHA-256 hash chained audit log.",
        "dependencies": [{"module": "platform", "min_version": "1.0.0"}],
        "required_permissions": ["audit:view", "audit:export"],
        "events_published": ["audit.record_created"],
    }
    manifest = ModuleManifest.model_validate(manifest_data)
    assert manifest.name == "audit"
    assert len(manifest.dependencies) == 1
    assert manifest.dependencies[0].module == "platform"


def test_registry_topological_sort():
    """Verify that modules are sorted in strict dependency order."""
    registry = ModuleRegistry()

    m_platform = ModuleManifest(
        name="platform", version="1.0.0", title="Platform", description="Core"
    )
    m_tenancy = ModuleManifest(
        name="tenancy",
        version="1.0.0",
        title="Tenancy",
        description="Tenant Context",
        dependencies=[DependencySpec(module="platform")],
    )
    m_content = ModuleManifest(
        name="content",
        version="1.0.0",
        title="Content",
        description="Documents",
        dependencies=[DependencySpec(module="tenancy")],
    )

    # Register in reverse order
    registry.register_manifest(m_content)
    registry.register_manifest(m_tenancy)
    registry.register_manifest(m_platform)

    order = registry.startup_order()
    assert order == ["platform", "tenancy", "content"]


def test_registry_detects_cycles():
    """Verify that cyclic dependencies fail immediately."""
    registry = ModuleRegistry()

    m_a = ModuleManifest(
        name="module_a",
        version="1.0.0",
        title="A",
        description="A",
        dependencies=[DependencySpec(module="module_b")],
    )
    m_b = ModuleManifest(
        name="module_b",
        version="1.0.0",
        title="B",
        description="B",
        dependencies=[DependencySpec(module="module_a")],
    )

    registry.register_manifest(m_a)
    with pytest.raises(ValidationError, match="Cyclic dependency detected"):
        registry.register_manifest(m_b)
