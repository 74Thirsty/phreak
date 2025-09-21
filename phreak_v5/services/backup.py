"""Backup and cloud sync engine for PHREAK v5."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

from ..telemetry import TelemetryBus


class BackupSyncEngine:
    """Manages encrypted backup manifests and scheduling."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        storage_path: Path,
    ) -> None:
        self.telemetry = telemetry
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self.storage_path / "backups.json"
        self._manifest: Dict[str, list[dict]] = {}
        self._load_manifest()

    def schedule_backup(self, device_id: str) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.storage_path / device_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"backup_{timestamp}.tar"
        backup_path.write_bytes(b"")  # placeholder archive
        entry = {"device_id": device_id, "path": str(backup_path), "created_at": datetime.utcnow().isoformat()}
        self._manifest.setdefault(device_id, []).append(entry)
        self._write_manifest()
        self.telemetry.emit(
            "backup.created",
            {"device_id": device_id, "path": str(backup_path)},
        )
        return backup_path

    def list_backups(self, device_id: Optional[str] = None) -> Iterable[dict]:
        if device_id:
            return list(self._manifest.get(device_id, ()))
        entries = []
        for records in self._manifest.values():
            entries.extend(records)
        return entries

    def _load_manifest(self) -> None:
        if not self._manifest_path.exists():
            return
        self._manifest = json.loads(self._manifest_path.read_text())

    def _write_manifest(self) -> None:
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2, sort_keys=True))


__all__ = ["BackupSyncEngine"]
