"""Simple pub/sub telemetry bus for PHREAK v5."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, MutableMapping

from .models import TelemetryEvent

TelemetryCallback = Callable[[TelemetryEvent], Awaitable[None]]


class TelemetryBus:
    """Asynchronous in-process pub/sub bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[TelemetryCallback]] = defaultdict(list)
        self._queue: "asyncio.Queue[TelemetryEvent]" = asyncio.Queue()
        self._dispatcher_task: asyncio.Task[None] | None = None

    def subscribe(self, topic: str, callback: TelemetryCallback) -> None:
        self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: TelemetryCallback) -> None:
        callbacks = self._subscribers.get(topic)
        if not callbacks:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            pass

    def emit(self, topic: str, payload: MutableMapping[str, Any]) -> None:
        event = TelemetryEvent(topic=topic, payload=payload)
        self._queue.put_nowait(event)
        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._dispatch_loop())

    async def iter_events(self, topic: str) -> AsyncIterator[TelemetryEvent]:
        queue: "asyncio.Queue[TelemetryEvent]" = asyncio.Queue()

        async def _forward(event: TelemetryEvent) -> None:
            await queue.put(event)

        self.subscribe(topic, _forward)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(topic, _forward)

    async def _dispatch_loop(self) -> None:
        while not self._queue.empty() or self._has_subscribers():
            event = await self._queue.get()
            await self._dispatch(event)
        self._dispatcher_task = None

    async def _dispatch(self, event: TelemetryEvent) -> None:
        callbacks = list(self._subscribers.get(event.topic, ()))
        callbacks += self._subscribers.get("*", [])
        if not callbacks:
            return
        await asyncio.gather(*(cb(event) for cb in callbacks))

    def _has_subscribers(self) -> bool:
        return any(self._subscribers.values())


__all__ = ["TelemetryBus"]
