"""Domain models shared across PHREAK v5 subsystems."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence


class DeviceStatus(str, Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    FASTBOOT = "fastboot"
    RECOVERY = "recovery"


@dataclass(slots=True)
class Device:
    device_id: str
    connection_uri: str
    status: DeviceStatus = DeviceStatus.UNKNOWN
    tags: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def with_status(self, status: DeviceStatus) -> "Device":
        return Device(
            device_id=self.device_id,
            connection_uri=self.connection_uri,
            status=status,
            tags=self.tags,
            metadata=self.metadata,
        )


@dataclass(slots=True)
class DeviceBatch:
    """Represents a logical grouping of devices using tags or ids."""

    device_ids: Sequence[str] = field(default_factory=tuple)
    tags: Sequence[str] = field(default_factory=tuple)


class CommandPriority(Enum):
    LOW = 10
    NORMAL = 20
    HIGH = 30
    CRITICAL = 40


@dataclass(slots=True)
class CommandRequest:
    action: str
    device_ids: Sequence[str]
    arguments: Mapping[str, str] = field(default_factory=dict)
    requested_by: str = "system"
    priority: CommandPriority = CommandPriority.NORMAL
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def with_devices(self, devices: Sequence[str]) -> "CommandRequest":
        return CommandRequest(
            action=self.action,
            device_ids=tuple(devices),
            arguments=self.arguments,
            requested_by=self.requested_by,
            priority=self.priority,
            request_id=self.request_id,
            created_at=self.created_at,
        )

    def to_json(self) -> str:
        payload = {
            "action": self.action,
            "device_ids": list(self.device_ids),
            "arguments": dict(self.arguments),
            "requested_by": self.requested_by,
            "priority": self.priority.name,
            "request_id": self.request_id,
            "created_at": self.created_at.isoformat(),
        }
        return json.dumps(payload, sort_keys=True)


class CommandStatus(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass(slots=True)
class CommandResult:
    request_id: str
    device_id: str
    status: CommandStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def mark_running(self) -> None:
        self.status = CommandStatus.RUNNING
        self.started_at = datetime.utcnow()

    def mark_complete(self, status: CommandStatus, *, stdout: str = "", stderr: str = "", exit_code: Optional[int] = None) -> None:
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.completed_at = datetime.utcnow()


@dataclass(slots=True)
class PolicyContext:
    device_ids: Sequence[str]
    action: str
    requested_by: str
    arguments: Mapping[str, str]

    @classmethod
    def from_request(cls, request: CommandRequest) -> "PolicyContext":
        return cls(
            device_ids=request.device_ids,
            action=request.action,
            requested_by=request.requested_by,
            arguments=request.arguments,
        )


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reasons: Sequence[str] = field(default_factory=tuple)

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(True, ())

    @classmethod
    def deny(cls, reasons: Iterable[str]) -> "PolicyDecision":
        return cls(False, tuple(reasons))


@dataclass(slots=True)
class PolicyRule:
    name: str
    description: str
    condition: str
    effect: str = "allow"
    tags: Sequence[str] = field(default_factory=tuple)


@dataclass(slots=True)
class TelemetryEvent:
    topic: str
    payload: MutableMapping[str, object]
    timestamp: datetime = field(default_factory=datetime.utcnow)


__all__ = [
    "Device",
    "DeviceStatus",
    "DeviceBatch",
    "CommandRequest",
    "CommandPriority",
    "CommandResult",
    "CommandStatus",
    "PolicyContext",
    "PolicyDecision",
    "PolicyRule",
    "TelemetryEvent",
]
