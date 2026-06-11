"""Diagnostic bundle collector for PHREAK v5.

This module runs a curated list of safe ADB commands, redacts personally
identifiable information, and packages the output into a ZIP archive.
It mirrors the reference script shared with the team but is written as a
callable function so the interactive console can drive it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence

ADB = os.environ.get("ADB", "adb")
FASTBOOT = os.environ.get("FASTBOOT", "fastboot")

PII_PATTERNS = [
    re.compile(r"\bIMSI[:= ]?(\d{5,15})\b", re.IGNORECASE),
    re.compile(r"\bICCID[:= ]?(\d{10,20})\b", re.IGNORECASE),
    re.compile(r"\bMSISDN[:= ]?(\+?\d{6,15})\b", re.IGNORECASE),
    re.compile(r"\bphoneNumber[:= ]?(\+?\d{6,15})\b", re.IGNORECASE),
    re.compile(r"(\b\d{15}\b)")  # IMEI style numbers
]


def _run(cmd: Iterable[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command and always return a result suitable for a support bundle."""
    argv = list(cmd)
    try:
        return subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]} is not installed")
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
        return subprocess.CompletedProcess(
            argv,
            124,
            stdout or "",
            (stderr or "") + f"\ncommand timed out after {timeout} seconds",
        )


def _redact(text: str) -> str:
    if not text:
        return text
    scrubbed = text
    for pattern in PII_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    scrubbed = re.sub(r"\+?\b\d{7,15}\b", lambda m: "[REDACTED]", scrubbed)
    return scrubbed


def _parse_devices(output: str) -> list[tuple[str, str]]:
    devices = []
    for line in output.splitlines():
        if not line.strip() or line.startswith("List of devices"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            devices.append((fields[0], fields[1]))
    return devices


def _write_result(path: Path, cmd: Sequence[str], proc: subprocess.CompletedProcess) -> None:
    content = "\n".join(
        [
            f"$ {' '.join(cmd)}",
            f"exit_code={proc.returncode}",
            "",
            "STDOUT:",
            proc.stdout or "",
            "",
            "STDERR:",
            proc.stderr or "",
        ]
    )
    path.write_text(_redact(content), encoding="utf-8")


def collect_diagnostics(
    output_path: Optional[os.PathLike[str] | str] = None,
    *,
    include_bugreport: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """Collect the best available diagnostics from ADB, fastboot, and the host.

    Args:
        output_path: Destination zip file. Defaults to cwd/support_bundle_<ts>.zip
        include_bugreport: Whether to run ``adb bugreport`` (can take several minutes).
        progress_cb: Optional callback invoked with textual status updates.

    Returns:
        Path to the generated ZIP archive.

    A locked screen does not prevent collection when this host already has an
    authorized ADB connection. Android intentionally blocks device-level data
    when USB debugging is disabled or the host is unauthorized; in that case
    the bundle records the access state and gathers non-invasive host or
    fastboot diagnostics instead.
    """

    def report(message: str) -> None:
        if progress_cb:
            progress_cb(message)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if output_path is None:
        output_path = Path.cwd() / f"support_bundle_{timestamp}.zip"
    else:
        output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="phreak_diag_"))
    try:
        report("Detecting Android transports")
        adb_devices_cmd = [ADB, "devices", "-l"]
        adb_devices = _run(adb_devices_cmd, timeout=15)
        _write_result(tmpdir / "adb_devices.txt", adb_devices_cmd, adb_devices)
        detected_adb = _parse_devices(adb_devices.stdout)
        authorized = [serial for serial, state in detected_adb if state == "device"]

        fastboot_devices_cmd = [FASTBOOT, "devices"]
        fastboot_devices = _run(fastboot_devices_cmd, timeout=15)
        _write_result(tmpdir / "fastboot_devices.txt", fastboot_devices_cmd, fastboot_devices)
        detected_fastboot = _parse_devices(fastboot_devices.stdout)

        host_probes: Dict[str, Sequence[str]] = {
            "adb_version.txt": [ADB, "version"],
            "fastboot_version.txt": [FASTBOOT, "--version"],
        }
        for name, cmd in host_probes.items():
            report(f"Running {' '.join(cmd)}")
            _write_result(tmpdir / name, cmd, _run(cmd, timeout=15))

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adb_devices": [{"serial": serial, "state": state} for serial, state in detected_adb],
            "fastboot_devices": [
                {"serial": serial, "state": state} for serial, state in detected_fastboot
            ],
            "collection_mode": "host_only",
            "limitations": [],
        }

        if authorized:
            serial = authorized[0]
            adb = [ADB, "-s", serial]
            manifest["collection_mode"] = "adb_authorized"
            if len(authorized) > 1:
                manifest["limitations"].append(
                    f"Multiple authorized ADB devices detected; collected device {serial}"
                )

            probes: Dict[str, Sequence[str]] = {
                "screen_lock_state.txt": adb + ["shell", "dumpsys", "window", "policy"],
                "device_policy.txt": adb + ["shell", "dumpsys", "device_policy"],
                "developer_settings.txt": adb
                + [
                    "shell",
                    "sh",
                    "-c",
                    "settings get global development_settings_enabled; "
                    "settings get global adb_enabled",
                ],
                "motorola_enterprise_packages.txt": adb
                + [
                    "shell",
                    "sh",
                    "-c",
                    "pm list packages | grep -iE 'motorola|thinkshield|oemconfig'",
                ],
                "logcat.txt": adb + ["logcat", "-d"],
                "telephony.txt": adb + ["shell", "dumpsys", "telephony.registry"],
                "ims.txt": adb + ["shell", "dumpsys", "ims"],
                "connectivity.txt": adb + ["shell", "dumpsys", "connectivity"],
                "carrier_config.txt": adb + ["shell", "dumpsys", "carrier_config"],
                "getprops.txt": adb + ["shell", "getprop"],
                "device_info.txt": adb
                + [
                    "shell",
                    "sh",
                    "-c",
                    "getprop ro.product.model; "
                    "getprop ro.build.version.release; "
                    "getprop gsm.operator.numeric",
                ],
            }
            if include_bugreport:
                probes["bugreport.txt"] = adb + ["bugreport"]

            for name, cmd in probes.items():
                report(f"Running {' '.join(cmd)}")
                timeout = 600 if name == "bugreport.txt" else 120
                _write_result(tmpdir / name, cmd, _run(cmd, timeout=timeout))
        elif detected_fastboot:
            serial = detected_fastboot[0][0]
            manifest["collection_mode"] = "fastboot"
            cmd = [FASTBOOT, "-s", serial, "getvar", "all"]
            report(f"Running {' '.join(cmd)}")
            _write_result(tmpdir / "fastboot_getvar_all.txt", cmd, _run(cmd, timeout=60))
        elif detected_adb:
            states = sorted({state for _, state in detected_adb})
            manifest["collection_mode"] = "adb_restricted"
            manifest["limitations"].append(
                "Device-level diagnostics unavailable because ADB state is: " + ", ".join(states)
            )
        else:
            manifest["limitations"].append(
                "No ADB or fastboot device detected; bundle contains host diagnostics only"
            )

        (tmpdir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        report("Packaging support bundle")
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            for item in tmpdir.iterdir():
                bundle.write(item, arcname=item.name)

        return output_path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv: Optional[Iterable[str]] = None) -> Path:
    parser = argparse.ArgumentParser(description="Collect Android diagnostics via ADB")
    parser.add_argument("--out", default=None, help="Output zip path")
    parser.add_argument(
        "--skip-bugreport",
        action="store_true",
        help="Skip adb bugreport to speed up collection",
    )
    args = parser.parse_args(argv)

    dest = collect_diagnostics(
        args.out,
        include_bugreport=not args.skip_bugreport,
        progress_cb=lambda msg: print(msg),
    )
    print(f"Support bundle created: {dest}")
    return dest


if __name__ == "__main__":
    main()
