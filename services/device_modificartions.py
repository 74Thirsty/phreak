"""Device modification playbooks, guidelines, and troubleshooting flows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

__all__ = [
    "CommandStep",
    "Playbook",
    "Guideline",
    "TroubleshootingStep",
    "TroubleshootingGuide",
    "DeviceModificationOrchestrator",
]


@dataclass(frozen=True, slots=True)
class CommandStep:
    """Single command that appears within a device modification playbook."""

    description: str
    command: str
    requires_root: bool = False

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("description is required")
        if not self.command:
            raise ValueError("command is required")


@dataclass(frozen=True, slots=True)
class Playbook:
    """Declarative playbook that contains one or more command steps."""

    name: str
    summary: str
    steps: Tuple[CommandStep, ...]
    verification: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name is required")
        if not self.summary:
            raise ValueError("summary is required")
        if not self.steps:
            raise ValueError("steps must not be empty")

    @property
    def commands(self) -> Tuple[str, ...]:
        """Return the command strings in the order they should execute."""

        return tuple(step.command for step in self.steps)


@dataclass(frozen=True, slots=True)
class Guideline:
    """Represents a group of recommendations for operators."""

    category: str
    recommendations: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.category:
            raise ValueError("category is required")
        if not self.recommendations:
            raise ValueError("at least one recommendation is required")


@dataclass(frozen=True, slots=True)
class TroubleshootingStep:
    """Actionable troubleshooting command."""

    description: str
    command: str

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("description is required")
        if not self.command:
            raise ValueError("command is required")


@dataclass(frozen=True, slots=True)
class TroubleshootingGuide:
    """Collection of troubleshooting commands and their intent."""

    title: str
    steps: Tuple[TroubleshootingStep, ...]

    def __post_init__(self) -> None:
        if not self.title:
            raise ValueError("title is required")
        if not self.steps:
            raise ValueError("steps must not be empty")

    @property
    def commands(self) -> Tuple[str, ...]:
        return tuple(step.command for step in self.steps)


class DeviceModificationOrchestrator:
    """Factory that builds device modification playbooks and guides."""

    def __init__(self, *, adb_binary: str = "adb") -> None:
        self.adb = adb_binary

    def _adb(self, subcommand: str) -> str:
        return f"{self.adb} {subcommand}".strip()

    def hidden_menu_access(self) -> Playbook:
        """Playbook for enabling and accessing engineering menus."""

        steps = (
            CommandStep(
                "Check for hidden menu key support",
                self._adb('shell dumpsys input | grep "menu_key"'),
            ),
            CommandStep(
                "Enable the hidden menu trigger (requires root)",
                self._adb("shell setprop persist.menu.key 1"),
                requires_root=True,
            ),
            CommandStep(
                "Launch the engineering menu activity",
                self._adb(
                    "shell am start -n com.android.engineeringmenu/.EngineeringMenu"
                ),
            ),
        )
        verification = (
            self._adb("shell getprop persist.menu.key"),
        )
        return Playbook(
            name="Hidden Menu Access",
            summary="Enable and open OEM engineering menus for diagnostics.",
            steps=steps,
            verification=verification,
        )

    def auto_root(self) -> Playbook:
        """Playbook covering the auto-root verification steps."""

        steps = (
            CommandStep(
                "Confirm the current root identity",
                self._adb('shell su -c "echo $EUID"'),
                requires_root=True,
            ),
            CommandStep(
                "Verify that the system partition is mounted",
                self._adb("shell mount | grep system"),
            ),
            CommandStep(
                "Backup the system partition prior to modification",
                self._adb(
                    "shell dd if=/dev/block/bootdevice/by-name/system "
                    "of=/sdcard/system_backup.img bs=4096"
                ),
                requires_root=True,
            ),
            CommandStep(
                "Check the current SELinux enforcement mode",
                self._adb("shell getenforce"),
            ),
        )
        verification = (
            self._adb("shell ls -lh /sdcard/system_backup.img"),
        )
        return Playbook(
            name="Auto Root Preflight",
            summary="Validate environment and backups before the auto-root flow.",
            steps=steps,
            verification=verification,
        )

    def side_loading(self) -> Playbook:
        """Playbook for side loading APKs via ADB with verifier bypass."""

        steps = (
            CommandStep(
                "Disable verifier checks for ADB installs",
                self._adb("shell settings put global verifier_verify_adb_installs 0"),
            ),
            CommandStep(
                "Allow debuggable package installs without verification",
                self._adb("shell settings put global verifier_verify_debuggable 0"),
            ),
            CommandStep(
                "Install the APK via side loading",
                f"{self.adb} install -r --no-verify-certs app.apk",
            ),
        )
        verification = (
            self._adb("shell pm list packages | grep app.package.name"),
        )
        return Playbook(
            name="Side Loading",
            summary="Install unsigned or debug builds via the ADB side-loading path.",
            steps=steps,
            verification=verification,
        )

    def setup_crash_handler(self) -> Playbook:
        """Playbook for enabling persistent crash handler hooks."""

        steps = (
            CommandStep(
                "Monitor logcat for crash or error patterns",
                f"{self.adb} shell logcat | grep -i \"crash\\|error\"",
            ),
            CommandStep(
                "Enable the persistent system crash handler",
                self._adb("shell setprop persist.sys.crash_handler 1"),
                requires_root=True,
            ),
        )
        verification = (
            self._adb("shell getprop | grep crash_handler"),
        )
        return Playbook(
            name="Crash Handler Setup",
            summary="Enable crash monitoring and verify handler state.",
            steps=steps,
            verification=verification,
        )

    def network_unlock(self) -> Playbook:
        """Playbook for preparing the device for a network unlock workflow."""

        steps = (
            CommandStep(
                "Inspect the current SIM/network lock state",
                self._adb('shell getprop | grep "gsm.sim.state"'),
            ),
            CommandStep(
                "Backup modem NV data before changes",
                self._adb(
                    "shell dd if=/dev/block/bootdevice/by-name/nv_data "
                    "of=/sdcard/nv_data_backup.img bs=4096"
                ),
                requires_root=True,
            ),
            CommandStep(
                "Review the current modem configuration",
                self._adb('shell getprop | grep "gsm.current.phone-type"'),
            ),
        )
        verification = (
            self._adb("shell ls -lh /sdcard/nv_data_backup.img"),
        )
        return Playbook(
            name="Network Unlock",
            summary="Safely stage the device for carrier/network unlock workflows.",
            steps=steps,
            verification=verification,
        )

    def security_considerations(self) -> Tuple[Guideline, ...]:
        """Return the security guidance associated with modification flows."""

        return (
            Guideline(
                category="Data Protection",
                recommendations=(
                    "Maintain backups of critical partitions before changes.",
                    "Use secure channels when transferring sensitive images.",
                    "Implement error handling to surface backup failures early.",
                ),
            ),
            Guideline(
                category="System Integrity",
                recommendations=(
                    "Verify checksums of any modified system files or images.",
                    "Capture system logs throughout risky operations.",
                    "Monitor for unexpected behaviour post-modification.",
                ),
            ),
            Guideline(
                category="Recovery Procedures",
                recommendations=(
                    "Retain original firmware images for full restoration.",
                    "Document all modifications with timestamps and operators.",
                    "Exercise recovery drills before production roll-outs.",
                ),
            ),
        )

    def troubleshooting_guide(self) -> TroubleshootingGuide:
        """Return the troubleshooting commands for common issues."""

        steps = (
            TroubleshootingStep(
                "Verify the device is connected over ADB",
                self._adb("devices"),
            ),
            TroubleshootingStep(
                "Inspect system services for error states",
                self._adb('shell dumpsys | grep -i "error\\|failed"'),
            ),
            TroubleshootingStep(
                "Stream logcat and filter for failures",
                f"{self.adb} logcat | grep -i \"error\\|failed\"",
            ),
            TroubleshootingStep(
                "Confirm partitions are mounted correctly",
                self._adb('shell mount | grep -i "no\\|failed"'),
            ),
        )
        return TroubleshootingGuide(
            title="Troubleshooting Guide",
            steps=steps,
        )

    def list_all_playbooks(self) -> Tuple[Playbook, ...]:
        """Convenience helper that returns every playbook in a tuple."""

        return (
            self.hidden_menu_access(),
            self.auto_root(),
            self.side_loading(),
            self.setup_crash_handler(),
            self.network_unlock(),
        )

    def iter_commands(self) -> Tuple[str, ...]:
        """Flatten every playbook command into a tuple for quick inspection."""

        commands: Tuple[str, ...] = ()
        for playbook in self.list_all_playbooks():
            commands += playbook.commands
            if playbook.verification:
                commands += playbook.verification
        return commands
