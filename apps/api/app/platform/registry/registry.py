"""
Module Registry and Dependency Graph Resolver.
"""

from pathlib import Path

import yaml

from apps.api.app.platform.errors import ValidationError
from apps.api.app.platform.logging import logger
from apps.api.app.platform.registry.manifest import ModuleManifest


class ModuleRegistry:
    """
    Central registry responsible for discovering, validating,
    and ordering modules according to their topological dependencies.
    """

    def __init__(self) -> None:
        self._manifests: dict[str, ModuleManifest] = {}
        self._ordered_modules: list[str] = []

    def register_manifest(self, manifest: ModuleManifest) -> None:
        """Register a pre-parsed module manifest."""
        self._manifests[manifest.name] = manifest
        self._recompute_order()

    def load_from_file(self, file_path: Path) -> ModuleManifest:
        """Load, validate, and register a module.yaml file."""
        if not file_path.exists():
            raise ValidationError(f"Manifest file does not exist at {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        manifest = ModuleManifest.model_validate(data)
        self.register_manifest(manifest)
        return manifest

    def discover_modules(self, root_dir: Path) -> list[ModuleManifest]:
        """Recursively discover all module.yaml manifests in a directory."""
        discovered: list[ModuleManifest] = []
        for manifest_path in root_dir.glob("**/module.yaml"):
            try:
                manifest = self.load_from_file(manifest_path)
                discovered.append(manifest)
                logger.info(f"Registered module: {manifest.name} (v{manifest.version})")
            except Exception as exc:
                logger.error(f"Failed to load manifest at {manifest_path}: {exc}")
                raise

        return discovered

    def get(self, name: str) -> ModuleManifest:
        """Retrieve a registered module manifest by name."""
        if name not in self._manifests:
            raise ValidationError(f"Module '{name}' is not registered.")
        return self._manifests[name]

    def all_modules(self) -> dict[str, ModuleManifest]:
        """Return all registered manifests."""
        return dict(self._manifests)

    def startup_order(self) -> list[str]:
        """Return modules ordered by dependency topology."""
        return list(self._ordered_modules)

    def _recompute_order(self) -> None:
        """Topological sort using Kahn's algorithm; raises on cyclic dependencies."""
        graph: dict[str, set[str]] = {name: set() for name in self._manifests}
        in_degree: dict[str, int] = {name: 0 for name in self._manifests}

        for name, manifest in self._manifests.items():
            for dep in manifest.dependencies:
                dep_name = dep.module
                # Only check dependencies among known modules
                if dep_name in self._manifests:
                    graph[dep_name].add(name)

        for neighbors in graph.values():
            for neighbor in neighbors:
                in_degree[neighbor] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._manifests):
            raise ValidationError("Cyclic dependency detected among registered modules.")

        self._ordered_modules = order


# Global platform module registry singleton
module_registry: ModuleRegistry = ModuleRegistry()
