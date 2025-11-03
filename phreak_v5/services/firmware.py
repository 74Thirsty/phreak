"""Firmware ingestion and management for PHREAK v5."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

from ..core.logging import AuditLoggingKernel
from ..telemetry import TelemetryBus


@dataclass(slots=True)
class FirmwareRecord:
    identifier: str
    filename: str
    sha256: str
    metadata: Dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class FirmwareSuite:
    """Handles firmware ingestion, verification, and lookup."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        audit_log: AuditLoggingKernel,
        storage_path: Path,
    ) -> None:
        self.telemetry = telemetry
        self.audit_log = audit_log
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._index_path = self.storage_path / "index.json"
        self._records: Dict[str, FirmwareRecord] = {}
        self._load_index()

    def ingest_firmware(self, source: Path, *, metadata: Optional[dict] = None) -> str:
        if not source.exists():
            raise FileNotFoundError(source)
        sha256 = self._hash_file(source)
        identifier = sha256[:16]
        target_name = f"{identifier}_{source.name}"
        target_path = self.storage_path / target_name
        shutil.copy2(source, target_path)
        record = FirmwareRecord(
            identifier=identifier,
            filename=target_name,
            sha256=sha256,
            metadata=metadata or {},
        )
        self._records[identifier] = record
        self._write_index()
        self.audit_log.append_custom(
            "firmware.ingested",
            {
                "identifier": identifier,
                "filename": target_name,
                "sha256": sha256,
            },
        )
        self.telemetry.emit(
            "firmware.ingested",
            {"identifier": identifier, "sha256": sha256, "metadata": record.metadata},
        )
        return identifier

    def get_record(self, identifier: str) -> Optional[FirmwareRecord]:
        return self._records.get(identifier)

    def verify(self, identifier: str) -> bool:
        record = self._records.get(identifier)
        if not record:
            return False
        path = self.storage_path / record.filename
        if not path.exists():
            return False
        return self._hash_file(path) == record.sha256

    def list_records(self) -> Iterable[FirmwareRecord]:
        return list(self._records.values())

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_index(self) -> None:
        if not self._index_path.exists():
            return
        data = json.loads(self._index_path.read_text())
        for identifier, entry in data.items():
            self._records[identifier] = FirmwareRecord(
                identifier=identifier,
                filename=entry["filename"],
                sha256=entry["sha256"],
                metadata=entry.get("metadata", {}),
                created_at=entry.get("created_at", datetime.utcnow().isoformat()),
            )

    def _write_index(self) -> None:
        data = {
            identifier: {
                "filename": record.filename,
                "sha256": record.sha256,
                "metadata": record.metadata,
                "created_at": record.created_at,
            }
            for identifier, record in self._records.items()
        }
        self._index_path.write_text(json.dumps(data, indent=2, sort_keys=True))


__all__ = ["FirmwareSuite", "FirmwareRecord"]
