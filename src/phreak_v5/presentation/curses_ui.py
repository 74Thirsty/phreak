"""Text-based control room stub for PHREAK v5."""
from __future__ import annotations

import asyncio
from typing import Optional

from ..core.router import CommandRouter
from ..models import CommandRequest, PolicyContext
from ..services.device_graph import DeviceGraphOrchestrator
from ..telemetry import TelemetryBus


class CursesControlRoom:
    """Lightweight facade for a future curses-based UI."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        device_graph: DeviceGraphOrchestrator,
        router: CommandRouter,
    ) -> None:
        self.telemetry = telemetry
        self.device_graph = device_graph
        self.router = router
        self._updates = asyncio.Queue()
        self.telemetry.subscribe("device_graph.status_updated", self._on_event)
        self.telemetry.subscribe("command.completed", self._on_event)

    async def _on_event(self, event) -> None:  # type: ignore[override]
        await self._updates.put(event)

    def render_dashboard(self) -> str:
        lines = ["PHREAK v5 :: Control Room", "=========================="]
        for info in self.device_graph.describe():
            lines.append(
                f"{info['device_id']:<20} {info['status']:<10} tags={','.join(info['tags'])}"
            )
        return "\n".join(lines)

    async def run_command(
        self,
        *,
        device_id: str,
        action: str,
        arguments: Optional[dict] = None,
        requested_by: str = "operator",
    ) -> None:
        request = CommandRequest(
            action=action,
            device_ids=(device_id,),
            arguments=arguments or {},
            requested_by=requested_by,
        )
        context = PolicyContext.from_request(request)
        await self.router.dispatch(request, context)

    async def poll_updates(self):
        while True:
            event = await self._updates.get()
            yield event


__all__ = ["CursesControlRoom"]
