"""Motorola Android Enterprise enrollment and diagnostic access workflows."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

EMM_PROVIDERS: List[Dict[str, str]] = [
    {
        "name": "Motorola Moto Device Manager",
        "url": "https://www.motorola.com/business/moto-device-manager",
        "notes": "Motorola's own device management for enterprise fleets.",
    },
    {
        "name": "Microsoft Intune",
        "url": "https://learn.microsoft.com/mem/intune",
        "notes": "Supports Android Enterprise fully managed + OEMConfig.",
    },
    {
        "name": "VMware Workspace ONE",
        "url": "https://www.vmware.com/products/workspace-one.html",
        "notes": "Android Enterprise fully managed + OEMConfig deployment.",
    },
    {
        "name": "Other AE-compatible EMM",
        "url": "",
        "notes": "Any EMM supporting Android Enterprise device-owner mode.",
    },
]

ENTERPRISE_PROBE_COMMANDS: Dict[str, str] = {
    "device_owner": (
        "shell dumpsys device_policy "
        "| grep -E 'Device Owner|admin='"
    ),
    "managed_profile": "shell pm list users | grep -i managed",
    "developer_settings": "shell settings get global development_settings_enabled",
    "adb_enabled": "shell settings get global adb_enabled",
    "oemconfig_packages": (
        "shell pm list packages "
        "| grep -iE 'motorola|thinkshield|oemconfig'"
    ),
    "enterprise_packages": (
        "shell pm list packages "
        "| grep -iE 'enterprise|device_policy'"
    ),
    "screen_lock_state": (
        "shell dumpsys window policy "
        "| grep -E 'isStatusBarKeyguard|showLockscreen'"
    ),
}


@dataclass
class EnrollmentPayload:
    """Android Enterprise QR enrollment payload template."""

    dm_id: str = ""
    dm_package: str = ""
    dm_checksum: str = ""
    dm_signature: str = ""
    dm_download_url: str = ""
    android_policy: Dict[str, object] = field(default_factory=dict)

    def to_qr_json(self) -> str:
        payload: Dict[str, object] = {
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": (
                self.dm_id
            ),
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": (
                self.dm_checksum
            ),
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM": (
                self.dm_signature
            ),
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION": (
                self.dm_download_url
            ),
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_NAME": (
                self.dm_package
            ),
        }
        if self.android_policy:
            payload[
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_EXTRAS"
            ] = self.android_policy
        return json.dumps(payload, indent=2)

    @staticmethod
    def template_placeholder() -> str:
        """Return a filled-in template with placeholder values as a reference."""
        return json.dumps(
            {
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": (
                    "com.example.emm/.DeviceAdminReceiver"
                ),
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_CHECKSUM": (
                    "Base64-encoded SHA-256 of the EMM APK"
                ),
                (
                    "android.app.extra"
                    ".PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM"
                ): (
                    "Base64-encoded SHA-256 of the EMM signing cert"
                ),
                (
                    "android.app.extra"
                    ".PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION"
                ): (
                    "https://example.com/emm.apk"
                ),
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_PACKAGE_NAME": (
                    "com.example.emm"
                ),
            },
            indent=2,
        )

    @classmethod
    def from_android_device_policy_token(cls, enrollment_token: str) -> str:
        """Build Google's standard Android Device Policy QR payload."""
        token = enrollment_token.strip()
        if not token:
            raise ValueError("Enrollment token is required")
        return json.dumps(
            {
                "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME": (
                    "com.google.android.apps.work.clouddpc/"
                    ".receivers.CloudDeviceAdminReceiver"
                ),
                (
                    "android.app.extra."
                    "PROVISIONING_DEVICE_ADMIN_SIGNATURE_CHECKSUM"
                ): "I5YvS0O5hXY46mb01BlRjq4oJJGs2kuUcHvVkAPEXlg",
                (
                    "android.app.extra."
                    "PROVISIONING_DEVICE_ADMIN_PACKAGE_DOWNLOAD_LOCATION"
                ): "https://play.google.com/managed/downloadManagingApp?identifier=setup",
                "android.app.extra.PROVISIONING_ADMIN_EXTRAS_BUNDLE": {
                    "com.google.android.apps.work.clouddpc.EXTRA_ENROLLMENT_TOKEN": token
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def validate_qr_json(payload_json: str) -> str:
        """Validate an EMM-provided QR payload and return compact JSON."""
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise ValueError("Enrollment QR payload must be a JSON object")
        if not payload.get(
            "android.app.extra.PROVISIONING_DEVICE_ADMIN_COMPONENT_NAME"
        ):
            raise ValueError("Enrollment QR payload is missing the device-admin component")
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class MotorolaEnterpriseManager:
    """Guides Motorola enterprise enrollment and diagnostic access configuration."""

    @staticmethod
    def list_emm_providers() -> List[Dict[str, str]]:
        return [dict(p) for p in EMM_PROVIDERS]

    @staticmethod
    def enrollment_steps() -> List[Tuple[str, str]]:
        return [
            (
                "Own & control devices",
                "Company-owned or explicitly enrolled with owner consent. "
                "Existing retail devices require a factory reset for "
                "device-owner mode.",
            ),
            (
                "Choose an EMM/MDM",
                "Select from: Motorola Moto Device Manager, Microsoft Intune, "
                "VMware Workspace ONE, or another Android Enterprise-compatible "
                "EMM.",
            ),
            (
                "Android Enterprise enrollment",
                "Configure fully managed / device-owner mode via zero-touch, "
                "QR, or NFC during initial setup. Device-owner cannot be added "
                "after setup without a factory reset.",
            ),
            (
                "Deploy Moto OEMConfig",
                "Connect EMM to Managed Google Play, approve and deploy Moto "
                "OEMConfig, configure supported ThinkShield policies.",
            ),
            (
                "Configure diagnostics",
                "Permit developer settings through enterprise policy. Install "
                "authorized diagnostic companion app. Authorize PHREAK "
                "service-station ADB keys during provisioning.",
            ),
            (
                "Contact Motorola Business",
                "Request access to Moto Device Manager, Moto Remote Control, "
                "OEMConfig docs, and enterprise support at "
                "https://www.motorola.com/business/moto-oem-config",
            ),
        ]

    @staticmethod
    def write_enrollment_artifacts(
        payload_json: str,
        output_dir: Path,
    ) -> Tuple[Path, Optional[Path]]:
        """Write the QR payload and render a PNG when qrencode is installed."""
        compact = EnrollmentPayload.validate_qr_json(payload_json)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        payload_path = output_dir / f"motorola_enrollment_{timestamp}.json"
        payload_path.write_text(compact, encoding="utf-8")

        qr_path = None
        qrencode = shutil.which("qrencode")
        if qrencode:
            candidate = output_dir / f"motorola_enrollment_{timestamp}.png"
            proc = subprocess.run(
                [qrencode, "-o", str(candidate), compact],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                qr_path = candidate
        return payload_path, qr_path

    VERIFICATION_DISPLAY: Dict[str, str] = {
        "device_owner": "Device Owner",
        "developer_settings": "Developer Settings",
        "adb_enabled": "ADB Enabled",
        "oemconfig_packages": "Moto Enterprise Packages",
    }

    @classmethod
    def build_verification_plan(cls) -> List[Tuple[str, str, str]]:
        return [
            (
                "device_owner",
                ENTERPRISE_PROBE_COMMANDS["device_owner"],
                "device owner",
            ),
            (
                "developer_settings",
                ENTERPRISE_PROBE_COMMANDS["developer_settings"],
                "1",
            ),
            (
                "adb_enabled",
                ENTERPRISE_PROBE_COMMANDS["adb_enabled"],
                "1",
            ),
            (
                "oemconfig_packages",
                ENTERPRISE_PROBE_COMMANDS["oemconfig_packages"],
                "motorola",
            ),
        ]

    @classmethod
    def parse_verification_results(
        cls,
        results: Dict[str, Tuple[str, str, int]],
    ) -> Dict[str, bool]:
        plan = cls.build_verification_plan()
        status: Dict[str, bool] = {}
        for check_name, _, expected in plan:
            out, _err, _code = results.get(check_name, ("", "", -1))
            if expected == "device owner":
                status[check_name] = bool(
                    re.search(r"(device\s*owner|admin=)", out, re.IGNORECASE)
                )
            elif expected == "1":
                status[check_name] = out.strip() == "1"
            else:
                status[check_name] = expected.lower() in out.lower()
        return status

    @staticmethod
    def verification_commands_for_adb(
        adb_binary: str = "adb",
    ) -> Dict[str, str]:
        return {
            name: f"{adb_binary} {cmd}"
            for name, cmd in ENTERPRISE_PROBE_COMMANDS.items()
        }


__all__ = [
    "EnrollmentPayload",
    "MotorolaEnterpriseManager",
    "ENTERPRISE_PROBE_COMMANDS",
    "EMM_PROVIDERS",
]
