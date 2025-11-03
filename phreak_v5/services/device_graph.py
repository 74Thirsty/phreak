"""Device graph orchestrator for PHREAK v5."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..models import Device, DeviceBatch, DeviceStatus
from ..telemetry import TelemetryBus


@dataclass(slots=True)
class DeviceNode:
    device: Device
    tags: Set[str] = field(default_factory=set)
    status: DeviceStatus = DeviceStatus.UNKNOWN
    last_seen: datetime = field(default_factory=datetime.utcnow)

    def update(self, *, tags: Optional[Iterable[str]] = None, status: Optional[DeviceStatus] = None) -> None:
        if tags is not None:
            self.tags = set(tags)
        if status is not None:
            self.status = status
        self.last_seen = datetime.utcnow()


@dataclass(slots=True)
class DeviceBatchResolution:
    device_ids: Tuple[str, ...]
    missing: Tuple[str, ...]
    tags: Tuple[str, ...]


class DeviceGraphOrchestrator:
    """Maintains a live view of connected devices and groupings."""

    def __init__(self, *, telemetry: TelemetryBus, audit_log=None) -> None:
        self.telemetry = telemetry
        self.audit_log = audit_log
        self._nodes: Dict[str, DeviceNode] = {}

    def register_device(self, device: Device) -> None:
        node = DeviceNode(device=device, tags=set(device.tags), status=device.status)
        self._nodes[device.device_id] = node
        self.telemetry.emit(
            "device_graph.registered",
            {
                "device_id": device.device_id,
                "tags": list(node.tags),
                "status": node.status.value,
            },
        )

    def remove_device(self, device_id: str) -> None:
        if self._nodes.pop(device_id, None):
            self.telemetry.emit("device_graph.removed", {"device_id": device_id})

    def update_status(self, device_id: str, status: DeviceStatus) -> None:
        node = self._nodes.get(device_id)
        if not node:
            return
        node.update(status=status)
        self.telemetry.emit(
            "device_graph.status_updated",
            {"device_id": device_id, "status": status.value},
        )

    def add_tags(self, device_id: str, tags: Iterable[str]) -> None:
        node = self._nodes.get(device_id)
        if not node:
            return
        node.tags.update(tags)
        node.last_seen = datetime.utcnow()
        self.telemetry.emit(
            "device_graph.tags_added",
            {"device_id": device_id, "tags": list(tags)},
        )

    def remove_tags(self, device_id: str, tags: Iterable[str]) -> None:
        node = self._nodes.get(device_id)
        if not node:
            return
        for tag in tags:
            node.tags.discard(tag)
        node.last_seen = datetime.utcnow()
        self.telemetry.emit(
            "device_graph.tags_removed",
            {"device_id": device_id, "tags": list(tags)},
        )

    def list_devices(self) -> List[Device]:
        return [node.device for node in self._nodes.values()]

    def resolve_batch(self, batch: DeviceBatch) -> DeviceBatchResolution:
        resolved: Set[str] = set(batch.device_ids)
        missing: Set[str] = set()
        if batch.tags:
            for node in self._nodes.values():
                if set(batch.tags).issubset(node.tags):
                    resolved.add(node.device.device_id)
        for device_id in list(resolved):
            if device_id not in self._nodes:
                resolved.discard(device_id)
                missing.add(device_id)
        return DeviceBatchResolution(
            device_ids=tuple(sorted(resolved)),
            missing=tuple(sorted(missing)),
            tags=tuple(batch.tags),
        )

    def find_by_tag(self, tag: str) -> List[Device]:
        return [node.device for node in self._nodes.values() if tag in node.tags]

    def describe(self) -> List[dict]:
        return [
            {
                "device_id": node.device.device_id,
                "status": node.status.value,
                "tags": sorted(node.tags),
                "last_seen": node.last_seen.isoformat(),
            }
            for node in self._nodes.values()
        ]


__all__ = ["DeviceGraphOrchestrator", "DeviceBatchResolution"]
