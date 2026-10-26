"""
Platform Module Registry and Manifests.
"""

from apps.api.app.platform.registry.manifest import DependencySpec, ModuleManifest
from apps.api.app.platform.registry.registry import ModuleRegistry, module_registry

__all__ = ["DependencySpec", "ModuleManifest", "ModuleRegistry", "module_registry"]
