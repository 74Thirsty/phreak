"""Tamper-evident audit logging for PHREAK v5."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from ..models import CommandRequest, CommandResult
from ..telemetry import TelemetryBus


@dataclass(slots=True)
class AuditRecord:
    timestamp: str
    kind: str
    payload: dict
    hash: str
    prev_hash: str


class AuditLoggingKernel:
    """Append-only audit log with SHA-256 hash chaining."""

    def __init__(self, *, storage_path: Path, telemetry: TelemetryBus) -> None:
        self.storage_path = storage_path
        self.telemetry = telemetry
        self._last_hash = "0" * 64
        if self.storage_path.exists():
            self._last_hash = self._read_last_hash()

    def bootstrap(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("")
            self._last_hash = "0" * 64

    def record_command_request(self, request: CommandRequest) -> None:
        payload = {
            "request_id": request.request_id,
            "action": request.action,
            "device_ids": list(request.device_ids),
            "arguments": dict(request.arguments),
            "requested_by": request.requested_by,
            "priority": request.priority.name,
            "created_at": request.created_at.isoformat(),
        }
        self._append("command_request", payload)

    def record_command_result(self, result: CommandResult) -> None:
        payload = {
            "request_id": result.request_id,
            "device_id": result.device_id,
            "status": result.status.value,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }
        self._append("command_result", payload)

    def append_custom(self, kind: str, payload: dict) -> None:
        self._append(kind, payload)

    def tail(self, limit: int = 20) -> List[AuditRecord]:
        if not self.storage_path.exists():
            return []
        lines = self.storage_path.read_text().strip().splitlines()
        records: List[AuditRecord] = []
        for line in lines[-limit:]:
            if not line:
                continue
            data = json.loads(line)
            records.append(AuditRecord(**data))
        return records

    def verify(self) -> bool:
        prev_hash = "0" * 64
        for record in self.tail(limit=10_000):
            payload = {
                "timestamp": record.timestamp,
                "kind": record.kind,
                "payload": record.payload,
            }
            expected = hashlib.sha256((prev_hash + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
            if expected != record.hash or record.prev_hash != prev_hash:
                return False
            prev_hash = record.hash
        return True

    def _append(self, kind: str, payload: dict) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        record_payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "kind": kind,
            "payload": payload,
        }
        digest = hashlib.sha256(
            (self._last_hash + json.dumps(record_payload, sort_keys=True)).encode()
        ).hexdigest()
        record = AuditRecord(
            timestamp=record_payload["timestamp"],
            kind=kind,
            payload=payload,
            hash=digest,
            prev_hash=self._last_hash,
        )
        with self.storage_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record)) + "\n")
        self._last_hash = digest
        self.telemetry.emit(
            "audit.record_appended",
            {"kind": kind, "hash": digest, "prev_hash": record.prev_hash},
        )

    def _read_last_hash(self) -> str:
        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                for line in reversed(handle.readlines()):
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    return data.get("hash", "0" * 64)
        except FileNotFoundError:
            return "0" * 64
        return "0" * 64


__all__ = ["AuditLoggingKernel", "AuditRecord"]
