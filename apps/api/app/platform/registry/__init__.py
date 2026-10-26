"""
Platform Module Registry and Manifests.
"""

from apps.api.app.platform.registry.manifest import ModuleManifest, DependencySpec
from apps.api.app.platform.registry.registry import ModuleRegistry, module_registry

__all__ = ["ModuleManifest", "DependencySpec", "ModuleRegistry", "module_registry"]
