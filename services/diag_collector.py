"""Diagnostic bundle collector for PHREAK v5.

This module runs a curated list of safe ADB commands, redacts personally
identifiable information, and packages the output into a ZIP archive.
It mirrors the reference script shared with the team but is written as a
callable function so the interactive console can drive it.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

ADB = os.environ.get("ADB", "adb")

PII_PATTERNS = [
    re.compile(r"\bIMSI[:= ]?(\d{5,15})\b", re.IGNORECASE),
    re.compile(r"\bICCID[:= ]?(\d{10,20})\b", re.IGNORECASE),
    re.compile(r"\bMSISDN[:= ]?(\+?\d{6,15})\b", re.IGNORECASE),
    re.compile(r"\bphoneNumber[:= ]?(\+?\d{6,15})\b", re.IGNORECASE),
    re.compile(r"(\b\d{15}\b)")  # IMEI style numbers
]


def _run(cmd: Iterable[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command and capture stdout/stderr."""
    return subprocess.run(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        text=True,
        check=False,
    )


def _redact(text: str) -> str:
    if not text:
        return text
    scrubbed = text
    for pattern in PII_PATTERNS:
        scrubbed = pattern.sub("[REDACTED]", scrubbed)
    scrubbed = re.sub(r"\+?\b\d{7,15}\b", lambda m: "[REDACTED]", scrubbed)
    return scrubbed


def collect_diagnostics(
    output_path: Optional[os.PathLike[str] | str] = None,
    *,
    include_bugreport: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Path:
    """Collect diagnostics from the connected device.

    Args:
        output_path: Destination zip file. Defaults to cwd/support_bundle_<ts>.zip
        include_bugreport: Whether to run ``adb bugreport`` (can take several minutes).
        progress_cb: Optional callback invoked with textual status updates.

    Returns:
        Path to the generated ZIP archive.

    Raises:
        RuntimeError: if ``adb`` is missing or the device is not connected.
    """

    def report(message: str) -> None:
        if progress_cb:
            progress_cb(message)

    state = _run([ADB, "get-state"], timeout=10)
    if state.returncode != 0 or not state.stdout.strip():
        raise RuntimeError("ADB not available or device not connected")

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if output_path is None:
        output_path = Path.cwd() / f"support_bundle_{timestamp}.zip"
    else:
        output_path = Path(output_path)

    probes: Dict[str, Iterable[str]] = {
        "devices.txt": [ADB, "devices", "-l"],
        "logcat.txt": [ADB, "logcat", "-d"],
        "telephony.txt": [ADB, "shell", "dumpsys", "telephony.registry"],
        "ims.txt": [ADB, "shell", "dumpsys", "ims"],
        "connectivity.txt": [ADB, "shell", "dumpsys", "connectivity"],
        "carrier_config.txt": [ADB, "shell", "dumpsys", "carrier_config"],
        "getprops.txt": [ADB, "shell", "getprop"],
    }

    if include_bugreport:
        probes["bugreport.txt"] = [ADB, "bugreport"]

    tmpdir = Path(tempfile.mkdtemp(prefix="phreak_diag_"))
    try:
        for name, cmd in probes.items():
            report(f"Running {' '.join(cmd)}")
            proc = _run(cmd, timeout=600 if "bugreport" in cmd else 120)
            content = proc.stdout or proc.stderr
            path = tmpdir / name
            path.write_text(_redact(content), encoding="utf-8")

        report("Gathering device identifiers")
        device_info = _run(
            [
                ADB,
                "shell",
                "sh",
                "-c",
                " && ".join(
                    [
                        "getprop ro.product.model",
                        "getprop ro.build.version.release",
                        "getprop gsm.operator.numeric",
                    ]
                ),
            ]
        )
        (tmpdir / "device_info.txt").write_text(
            _redact(device_info.stdout + device_info.stderr),
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
