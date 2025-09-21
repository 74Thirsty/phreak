"""Forensics and analytics hub for PHREAK v5."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ..core.logging import AuditLoggingKernel
from ..core.router import CommandRouter
from ..models import CommandRequest, PolicyContext
from ..telemetry import TelemetryBus


DEFAULT_COLLECTION_COMMANDS = [
    {"action": "shell", "arguments": {"command": "getprop"}},
    {"action": "pull", "arguments": {"path": "/system/build.prop"}},
]


@dataclass(slots=True)
class ForensicArtifact:
    name: str
    description: str
    path: Path


class ForensicsHub:
    """Coordinates snapshot collection and reporting."""

    def __init__(
        self,
        *,
        audit_log: AuditLoggingKernel,
        telemetry: TelemetryBus,
        storage_path: Optional[Path] = None,
    ) -> None:
        self.audit_log = audit_log
        self.telemetry = telemetry
        self.storage_path = storage_path or Path("~/.phreak/forensics").expanduser()
        self.storage_path.mkdir(parents=True, exist_ok=True)

    async def collect_snapshot(
        self,
        device_id: str,
        router: CommandRouter,
        *,
        commands: Optional[list[dict]] = None,
    ) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = self.storage_path / device_id / timestamp
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        metadata: Dict[str, object] = {
            "device_id": device_id,
            "collected_at": datetime.utcnow().isoformat(),
            "artifacts": [],
        }

        cmds = commands or DEFAULT_COLLECTION_COMMANDS
        executed_commands = []
        for spec in cmds:
            request = CommandRequest(
                action=spec["action"],
                device_ids=(device_id,),
                arguments=spec.get("arguments", {}),
                requested_by="forensics",
            )
            context = PolicyContext.from_request(request)
            try:
                await router.dispatch(request, context)
                status = "submitted"
            except Exception as exc:  # pragma: no cover - defensive
                status = f"error: {exc}"
            executed_commands.append(
                {
                    "action": spec["action"],
                    "arguments": spec.get("arguments", {}),
                    "status": status,
                }
            )

        metadata["commands"] = executed_commands
        metadata_path = snapshot_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True))
        self.audit_log.append_custom(
            "forensics.snapshot",
            {"device_id": device_id, "path": str(snapshot_dir)},
        )
        self.telemetry.emit(
            "forensics.snapshot_created",
            {"device_id": device_id, "path": str(snapshot_dir)},
        )
        return snapshot_dir


__all__ = ["ForensicsHub", "ForensicArtifact"]
