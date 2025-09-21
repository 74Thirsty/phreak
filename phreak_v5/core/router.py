"""Command routing for PHREAK v5."""
from __future__ import annotations

import asyncio
from typing import Dict, Optional, Sequence

from ..models import CommandRequest, CommandResult, CommandStatus, PolicyContext
from ..telemetry import TelemetryBus

if True:  # typing imports
    from .connection import ConnectionMatrix
    from .logging import AuditLoggingKernel
    from .policy import PolicyEngine


class CommandRouter:
    """Routes normalized command requests to the correct connector."""

    def __init__(
        self,
        *,
        connection_matrix: "ConnectionMatrix",
        policy_engine: "PolicyEngine",
        audit_log: "AuditLoggingKernel",
        telemetry: TelemetryBus,
        concurrency: int = 8,
    ) -> None:
        self.connection_matrix = connection_matrix
        self.policy_engine = policy_engine
        self.audit_log = audit_log
        self.telemetry = telemetry
        self._semaphore = asyncio.Semaphore(concurrency)

    async def dispatch(
        self,
        request: CommandRequest,
        context: PolicyContext,
        *,
        extra: Optional[Dict[str, object]] = None,
    ) -> None:
        if not request.device_ids:
            raise ValueError("Command request must target at least one device")

        decision = self.policy_engine.evaluate(context, extra=extra)
        if not decision.allowed:
            await self._handle_denied(request, decision.reasons)
            return

        await asyncio.gather(
            *(
                self._dispatch_to_device(request, device_id)
                for device_id in request.device_ids
            )
        )

    async def _dispatch_to_device(self, request: CommandRequest, device_id: str) -> CommandResult:
        async with self._semaphore:
            single_request = request.with_devices([device_id])
            self.telemetry.emit(
                "command.dispatched",
                {"request_id": request.request_id, "device_id": device_id},
            )
            result = await self.connection_matrix.execute(device_id, single_request)
            self.audit_log.record_command_result(result)
            self.telemetry.emit(
                "command.completed",
                {
                    "request_id": request.request_id,
                    "device_id": device_id,
                    "status": result.status.value,
                    "exit_code": result.exit_code,
                },
            )
            return result

    async def _handle_denied(self, request: CommandRequest, reasons: Sequence[str]) -> None:
        for device_id in request.device_ids:
            result = CommandResult(
                request_id=request.request_id,
                device_id=device_id,
                status=CommandStatus.REJECTED,
            )
            result.mark_complete(
                CommandStatus.REJECTED,
                stderr="; ".join(reasons) if reasons else "Policy denied",
                exit_code=1,
            )
            self.audit_log.record_command_result(result)
            self.telemetry.emit(
                "command.rejected",
                {
                    "request_id": request.request_id,
                    "device_id": device_id,
                    "reasons": list(reasons),
                },
            )


__all__ = ["CommandRouter"]
