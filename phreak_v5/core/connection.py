"""Connection management for PHREAK v5."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Protocol

from ..models import CommandRequest, CommandResult, CommandStatus, Device
from ..telemetry import TelemetryBus

if True:  # typing imports
    from .logging import AuditLoggingKernel


class DeviceConnector(Protocol):
    """Protocol implemented by device transport adapters."""

    async def execute(self, request: CommandRequest) -> CommandResult:
        ...


@dataclass(slots=True)
class ConnectionState:
    device: Device
    connector: Optional[DeviceConnector] = None
    last_seen: datetime = field(default_factory=datetime.utcnow)
    healthy: bool = True
    transport: str = "unknown"


class NullConnector:
    """Fallback connector used when no transport is registered."""

    async def execute(self, request: CommandRequest) -> CommandResult:
        result = CommandResult(
            request_id=request.request_id,
            device_id=request.device_ids[0] if request.device_ids else "unknown",
            status=CommandStatus.REJECTED,
        )
        result.mark_complete(
            CommandStatus.REJECTED,
            stderr="No connector registered for device",
            exit_code=1,
        )
        return result


class LoopbackConnector:
    """Connector that echoes commands for testing purposes."""

    async def execute(self, request: CommandRequest) -> CommandResult:
        device_id = request.device_ids[0] if request.device_ids else "unknown"
        result = CommandResult(
            request_id=request.request_id,
            device_id=device_id,
            status=CommandStatus.SUCCESS,
        )
        result.mark_running()
        result.mark_complete(
            CommandStatus.SUCCESS,
            stdout=f"loopback:{device_id}:{request.action}",
            exit_code=0,
        )
        return result


class ConnectionMatrix:
    """Maintains registered devices and their transport connectors."""

    def __init__(self, *, telemetry: TelemetryBus, audit_log: "AuditLoggingKernel") -> None:
        self.telemetry = telemetry
        self.audit_log = audit_log
        self._states: Dict[str, ConnectionState] = {}
        self._default_connector = NullConnector()
        self._lock = asyncio.Lock()

    def register_device(self, device: Device, *, connector: Optional[DeviceConnector] = None) -> None:
        self._states[device.device_id] = ConnectionState(
            device=device,
            connector=connector,
            transport=device.connection_uri.split(":", 1)[0],
        )
        self.audit_log.append_custom(
            "connection.register", {"device_id": device.device_id, "transport": device.connection_uri}
        )
        self.telemetry.emit(
            "connection.device_registered",
            {"device_id": device.device_id, "transport": device.connection_uri},
        )

    def unregister_device(self, device_id: str) -> None:
        if device_id in self._states:
            del self._states[device_id]
            self.audit_log.append_custom(
                "connection.unregister", {"device_id": device_id}
            )
            self.telemetry.emit(
                "connection.device_unregistered", {"device_id": device_id}
            )

    def bind_connector(self, device_id: str, connector: DeviceConnector) -> None:
        state = self._states.get(device_id)
        if not state:
            raise KeyError(f"Unknown device: {device_id}")
        state.connector = connector
        state.last_seen = datetime.utcnow()
        self.telemetry.emit(
            "connection.connector_bound",
            {"device_id": device_id, "transport": state.transport},
        )

    def get_state(self, device_id: str) -> Optional[ConnectionState]:
        return self._states.get(device_id)

    async def execute(self, device_id: str, request: CommandRequest) -> CommandResult:
        async with self._lock:
            state = self._states.get(device_id)
            if not state:
                result = CommandResult(
                    request_id=request.request_id,
                    device_id=device_id,
                    status=CommandStatus.REJECTED,
                )
                result.mark_complete(
                    CommandStatus.REJECTED,
                    stderr="Device not registered",
                    exit_code=1,
                )
                return result

            connector = state.connector or self._default_connector
            state.last_seen = datetime.utcnow()

        result = await connector.execute(request)
        state.healthy = result.status not in {CommandStatus.FAILED, CommandStatus.REJECTED}
        self.telemetry.emit(
            "connection.command_completed",
            {
                "device_id": device_id,
                "request_id": request.request_id,
                "status": result.status.value,
                "exit_code": result.exit_code,
            },
        )
        return result

    def list_devices(self) -> Dict[str, ConnectionState]:
        return dict(self._states)


__all__ = [
    "ConnectionMatrix",
    "DeviceConnector",
    "ConnectionState",
    "LoopbackConnector",
]
