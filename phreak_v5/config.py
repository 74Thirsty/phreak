"""Configuration helpers for the PHREAK v5 control tower."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Tuple


@dataclass(slots=True)
class PathConfig:
    root: Path = Path("~/.phreak").expanduser()
    audit_log_name: str = "audit.log.jsonl"
    vault_name: str = "vault.json"
    firmware_store_name: str = "firmware"
    backup_store_name: str = "backups"
    plugin_dirs: Tuple[str, ...] = ("plugins",)

    @property
    def audit_log(self) -> Path:
        return self.root / self.audit_log_name

    @property
    def vault(self) -> Path:
        return self.root / self.vault_name

    @property
    def firmware_store(self) -> Path:
        return self.root / self.firmware_store_name

    @property
    def backup_store(self) -> Path:
        return self.root / self.backup_store_name

    @property
    def plugin_roots(self) -> Tuple[Path, ...]:
        return tuple(self.root / name for name in self.plugin_dirs)

    def all_paths(self) -> Iterable[Path]:
        yield self.audit_log
        yield self.vault
        yield self.firmware_store
        yield self.backup_store
        for plugin_root in self.plugin_roots:
            yield plugin_root


@dataclass(slots=True)
class SecurityConfig:
    master_key: str = "phreak-default-master-key"


@dataclass(slots=True)
class ControlTowerConfig:
    paths: PathConfig = field(default_factory=PathConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @classmethod
    def default(cls) -> "ControlTowerConfig":
        return cls()
