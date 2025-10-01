"""Plugin runtime for PHREAK v5."""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from ..core.logging import AuditLoggingKernel
from ..telemetry import TelemetryBus


@dataclass(slots=True)
class PluginMetadata:
    name: str
    version: str
    description: str = ""
    capabilities: List[str] = field(default_factory=list)


@dataclass(slots=True)
class Plugin:
    metadata: PluginMetadata
    module: object
    path: Path

    def has_hook(self, name: str) -> bool:
        return hasattr(self.module, name)

    def call_hook(self, name: str, *args, **kwargs):
        if not self.has_hook(name):
            raise AttributeError(f"Plugin {self.metadata.name} lacks hook {name}")
        return getattr(self.module, name)(*args, **kwargs)


class PluginRuntime:
    """Loads plugin bundles described by a JSON manifest."""

    def __init__(
        self,
        *,
        search_paths: Iterable[Path],
        telemetry: TelemetryBus,
        audit_log: AuditLoggingKernel,
    ) -> None:
        self.search_paths = [Path(path) for path in search_paths]
        self.telemetry = telemetry
        self.audit_log = audit_log
        self.plugins: List[Plugin] = []

    def scan(self) -> None:
        self.plugins.clear()
        for root in self.search_paths:
            if not root.exists():
                continue
            for manifest_path in root.glob("*/plugin.json"):
                plugin = self._load_plugin(manifest_path)
                if plugin:
                    self.plugins.append(plugin)

    def get_plugin(self, name: str) -> Optional[Plugin]:
        for plugin in self.plugins:
            if plugin.metadata.name == name:
                return plugin
        return None

    def _load_plugin(self, manifest_path: Path) -> Optional[Plugin]:
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            self.telemetry.emit(
                "plugin.error",
                {"path": str(manifest_path), "error": "invalid manifest"},
            )
            return None

        metadata = PluginMetadata(
            name=manifest.get("name", manifest_path.parent.name),
            version=str(manifest.get("version", "0.0.0")),
            description=manifest.get("description", ""),
            capabilities=list(manifest.get("capabilities", [])),
        )

        entrypoint = manifest.get("entry", "main.py")
        module_path = manifest_path.parent / entrypoint
        if not module_path.exists():
            self.telemetry.emit(
                "plugin.error",
                {"path": str(module_path), "error": "missing entrypoint"},
            )
            return None

        spec = importlib.util.spec_from_file_location(metadata.name, module_path)
        if not spec or not spec.loader:
            self.telemetry.emit(
                "plugin.error",
                {"path": str(module_path), "error": "unable to load"},
            )
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[assignment]

        plugin = Plugin(metadata=metadata, module=module, path=manifest_path.parent)
        self.audit_log.append_custom(
            "plugin.loaded",
            {
                "name": metadata.name,
                "version": metadata.version,
                "path": str(plugin.path),
            },
        )
        self.telemetry.emit(
            "plugin.loaded",
            {
                "name": metadata.name,
                "version": metadata.version,
                "capabilities": metadata.capabilities,
            },
        )
        return plugin

    def call_hook(self, plugin_name: str, hook_name: str, *args, **kwargs):
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise KeyError(plugin_name)
        self.telemetry.emit(
            "plugin.hook_invoked",
            {"name": plugin_name, "hook": hook_name},
        )
        return plugin.call_hook(hook_name, *args, **kwargs)


__all__ = ["PluginRuntime", "Plugin", "PluginMetadata"]
