"""High-level orchestration for the PHREAK v5 control tower."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .config import ControlTowerConfig
from .core.connection import ConnectionMatrix
from .core.logging import AuditLoggingKernel
from .core.policy import PolicyEngine, PolicyRule
from .core.router import CommandRouter
from .core.vault import SecurityVault
from .models import CommandRequest, Device, DeviceBatch, PolicyContext
from .services.backup import BackupSyncEngine
from .services.device_graph import DeviceGraphOrchestrator
from .services.firmware import FirmwareSuite
from .services.forensics import ForensicsHub
from .services.ml import MLDiagnostics
from .services.plugins import PluginRuntime
from .telemetry import TelemetryBus


@dataclass(slots=True)
class ControlTowerComponents:
    """Aggregated component references used by the orchestrator."""

    connection_matrix: ConnectionMatrix
    policy_engine: PolicyEngine
    command_router: CommandRouter
    audit_log: AuditLoggingKernel
    vault: SecurityVault
    device_graph: DeviceGraphOrchestrator
    forensics_hub: ForensicsHub
    firmware_suite: FirmwareSuite
    backup_engine: BackupSyncEngine
    ml_diagnostics: MLDiagnostics
    plugin_runtime: PluginRuntime
    telemetry: TelemetryBus


class PhreakControlTower:
    """Top-level facade wiring together the PHREAK v5 subsystems."""

    def __init__(
        self,
        config: Optional[ControlTowerConfig] = None,
        *,
        policy_rules: Optional[Sequence[PolicyRule]] = None,
    ) -> None:
        self.config = config or ControlTowerConfig.default()
        self.telemetry = TelemetryBus()

        self.audit_log = AuditLoggingKernel(
            storage_path=self.config.paths.audit_log,
            telemetry=self.telemetry,
        )
        self.vault = SecurityVault(
            storage_path=self.config.paths.vault,
            master_key=self.config.security.master_key,
            telemetry=self.telemetry,
        )

        self.connection_matrix = ConnectionMatrix(
            telemetry=self.telemetry, audit_log=self.audit_log
        )
        self.policy_engine = PolicyEngine(
            policy_rules=policy_rules or [],
            telemetry=self.telemetry,
        )
        self.command_router = CommandRouter(
            connection_matrix=self.connection_matrix,
            policy_engine=self.policy_engine,
            audit_log=self.audit_log,
            telemetry=self.telemetry,
        )

        self.device_graph = DeviceGraphOrchestrator(
            telemetry=self.telemetry, audit_log=self.audit_log
        )
        self.forensics_hub = ForensicsHub(
            audit_log=self.audit_log,
            telemetry=self.telemetry,
        )
        self.firmware_suite = FirmwareSuite(
            telemetry=self.telemetry,
            audit_log=self.audit_log,
            storage_path=self.config.paths.firmware_store,
        )
        self.backup_engine = BackupSyncEngine(
            telemetry=self.telemetry,
            storage_path=self.config.paths.backup_store,
        )
        self.ml_diagnostics = MLDiagnostics(telemetry=self.telemetry)
        self.plugin_runtime = PluginRuntime(
            search_paths=list(self.config.paths.plugin_roots),
            telemetry=self.telemetry,
            audit_log=self.audit_log,
        )

    @property
    def components(self) -> ControlTowerComponents:
        return ControlTowerComponents(
            connection_matrix=self.connection_matrix,
            policy_engine=self.policy_engine,
            command_router=self.command_router,
            audit_log=self.audit_log,
            vault=self.vault,
            device_graph=self.device_graph,
            forensics_hub=self.forensics_hub,
            firmware_suite=self.firmware_suite,
            backup_engine=self.backup_engine,
            ml_diagnostics=self.ml_diagnostics,
            plugin_runtime=self.plugin_runtime,
            telemetry=self.telemetry,
        )

    # -- Device lifecycle -------------------------------------------------
    def register_devices(self, devices: Iterable[Device]) -> None:
        """Register devices in the graph and connection matrix."""
        for device in devices:
            self.connection_matrix.register_device(device)
            self.device_graph.register_device(device)

    def remove_device(self, device_id: str) -> None:
        self.connection_matrix.unregister_device(device_id)
        self.device_graph.remove_device(device_id)

    # -- Command dispatch -------------------------------------------------
    async def dispatch(self, request: CommandRequest) -> None:
        """Submit a command request and record results in services."""
        context = PolicyContext.from_request(request)
        self.audit_log.record_command_request(request)
        await self.command_router.dispatch(request, context)

    async def dispatch_batch(self, batch: DeviceBatch, request: CommandRequest) -> None:
        resolved = self.device_graph.resolve_batch(batch)
        request = request.with_devices(resolved.device_ids)
        await self.dispatch(request)

    # -- Maintenance ------------------------------------------------------
    def bootstrap(self) -> None:
        """Ensure storage paths exist and perform first-run setup."""
        for path in self.config.paths.all_paths():
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                path.mkdir(parents=True, exist_ok=True)
        self.audit_log.bootstrap()
        self.vault.bootstrap()
        self.telemetry.emit("control_tower.bootstrap", {})

    # -- Secrets ----------------------------------------------------------
    def store_secret(self, name: str, value: str, *, tags: Optional[Sequence[str]] = None) -> None:
        self.vault.store_secret(name, value, tags=tags)

    def load_secret(self, name: str) -> Optional[str]:
        return self.vault.retrieve_secret(name)

    # -- Firmware/Backups -------------------------------------------------
    def ingest_firmware(self, path: Path, *, metadata: Optional[dict] = None) -> str:
        return self.firmware_suite.ingest_firmware(path, metadata=metadata)

    def schedule_backup(self, device_id: str) -> Path:
        return self.backup_engine.schedule_backup(device_id)

    # -- Forensics --------------------------------------------------------
    async def collect_forensics(self, device_id: str) -> Path:
        return await self.forensics_hub.collect_snapshot(device_id, self.command_router)

    # -- Plugins ----------------------------------------------------------
    def load_plugins(self) -> None:
        self.plugin_runtime.scan()
        for plugin in self.plugin_runtime.plugins:
            self.telemetry.emit(
                "plugin.loaded",
                {"name": plugin.metadata.name, "version": plugin.metadata.version},
            )


__all__ = ["PhreakControlTower", "ControlTowerComponents"]
