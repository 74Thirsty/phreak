"""Web operator cockpit stubs for PHREAK v5."""
from __future__ import annotations

import json
from typing import Dict

from ..services.device_graph import DeviceGraphOrchestrator
from ..telemetry import TelemetryBus


class WebOperatorCockpit:
    """Prepares state for a future web UI implementation."""

    def __init__(self, *, telemetry: TelemetryBus, device_graph: DeviceGraphOrchestrator) -> None:
        self.telemetry = telemetry
        self.device_graph = device_graph

    def snapshot_state(self) -> Dict[str, object]:
        devices = self.device_graph.describe()
        summary = {
            "total": len(devices),
            "online": sum(1 for d in devices if d["status"] == "online"),
            "fastboot": sum(1 for d in devices if d["status"] == "fastboot"),
        }
        return {"devices": devices, "summary": summary}

    def export_state_json(self) -> str:
        state = self.snapshot_state()
        payload = json.dumps(state, indent=2, sort_keys=True)
        self.telemetry.emit("web.snapshot", {"device_count": state["summary"]["total"]})
        return payload


__all__ = ["WebOperatorCockpit"]
