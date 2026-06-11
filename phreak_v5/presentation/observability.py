"""Observability surface for PHREAK v5."""
from __future__ import annotations

from collections import deque
from typing import Deque, Dict

from ..core.logging import AuditLoggingKernel
from ..telemetry import TelemetryBus


class ObservabilityService:
    """Collects telemetry metrics and exposes recent events."""

    def __init__(self, *, telemetry: TelemetryBus, audit_log: AuditLoggingKernel) -> None:
        self.telemetry = telemetry
        self.audit_log = audit_log
        self._events: Deque[dict] = deque(maxlen=128)
        self._metrics: Dict[str, int] = {}
        self.telemetry.subscribe("*", self._on_event)

    async def _on_event(self, event) -> None:  # type: ignore[override]
        self._events.append(
            {
                "topic": event.topic,
                "payload": dict(event.payload),
                "timestamp": event.timestamp.isoformat(),
            }
        )
        self._metrics[event.topic] = self._metrics.get(event.topic, 0) + 1

    def recent_events(self) -> list[dict]:
        return list(self._events)

    def metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    def audit_tail(self, limit: int = 20) -> list[dict]:
        return [
            {
                "timestamp": record.timestamp,
                "kind": record.kind,
                "hash": record.hash,
            }
            for record in self.audit_log.tail(limit)
        ]


__all__ = ["ObservabilityService"]
