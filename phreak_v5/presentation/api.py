"""Automation API facade for PHREAK v5."""
from __future__ import annotations

from typing import Any, Dict

from ..core.router import CommandRouter
from ..models import CommandRequest, PolicyContext
from ..services.device_graph import DeviceGraphOrchestrator
from ..telemetry import TelemetryBus


class AutomationAPI:
    """Simple async facade mimicking a REST/gRPC handler."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        router: CommandRouter,
        device_graph: DeviceGraphOrchestrator,
    ) -> None:
        self.telemetry = telemetry
        self.router = router
        self.device_graph = device_graph

    async def submit_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = CommandRequest(
            action=payload["action"],
            device_ids=tuple(payload.get("device_ids", ())),
            arguments=payload.get("arguments", {}),
            requested_by=payload.get("requested_by", "api"),
        )
        context = PolicyContext.from_request(request)
        await self.router.dispatch(request, context)
        response = {"request_id": request.request_id, "status": "accepted"}
        self.telemetry.emit("api.command_submitted", response)
        return response

    def list_devices(self) -> Dict[str, Any]:
        devices = self.device_graph.describe()
        payload = {"devices": devices}
        self.telemetry.emit("api.list_devices", {"count": len(devices)})
        return payload


__all__ = ["AutomationAPI"]
