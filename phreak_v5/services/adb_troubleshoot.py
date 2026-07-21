"""ADB/Fastboot connection troubleshooter for PHREAK v5.

Runs a comprehensive diagnostic sweep across USB, kernel, udev, ADB server,
and Samsung-specific checks. Returns structured results that the rich console
can render into a visual report.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

ADB = os.environ.get("ADB", "adb")
FASTBOOT = os.environ.get("FASTBOOT", "fastboot")


@dataclass
class Check:
    name: str
    status: str  # "pass", "fail", "warn", "info"
    message: str
    details: List[str] = field(default_factory=list)
    fix: Optional[str] = None


def _run(cmd: str, timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd.split()[0]} not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def _parse_devices(output: str) -> list[tuple[str, str]]:
    devices = []
    for line in output.splitlines():
        if not line.strip() or line.startswith("List of devices"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            devices.append((fields[0], fields[1]))
    return devices


def run_diagnostics() -> dict:
    """Run all checks and return a structured report."""
    checks: List[Check] = []
    issues = 0

    # ── 1. Tools ──
    adb_path = shutil.which(ADB)
    fb_path = shutil.which(FASTBOOT)

    if adb_path:
        ver = _run(f"{ADB} version")
        ver_line = ver.stdout.splitlines()[0] if ver.stdout else "unknown"
        checks.append(Check("adb", "pass", f"found at {adb_path}", [ver_line]))
    else:
        checks.append(Check("adb", "fail", "NOT found in PATH",
                            ["sudo apt install android-tools-adb"]))
        issues += 1

    if fb_path:
        ver = _run(f"{FASTBOOT} --version")
        ver_line = ver.stdout.splitlines()[0] if ver.stdout else "unknown"
        checks.append(Check("fastboot", "pass", f"found at {fb_path}", [ver_line]))
    else:
        checks.append(Check("fastboot", "fail", "NOT found in PATH",
                            ["sudo apt install android-tools-fastboot"]))
        issues += 1

    # ── 2. ADB server ──
    _run(f"{ADB} kill-server", timeout=5)
    start = _run(f"{ADB} start-server", timeout=10)
    server_out = (start.stdout + start.stderr).strip()
    pid_check = _run("pgrep -f 'adb server'")
    if pid_check.stdout.strip():
        checks.append(Check("adb server", "pass", "running",
                            [f"PID: {pid_check.stdout.strip()}"]))
    else:
        checks.append(Check("adb server", "fail", "failed to start",
                            server_out.splitlines()[:3]))
        issues += 1

    # ── 3. USB / lsusb ──
    if shutil.which("lsusb"):
        lsusb_out = _run("lsusb").stdout
        samsung_lines = [l for l in lsusb_out.splitlines()
                         if re.search(r"samsung|04e8", l, re.I)]
        usb_devices = lsusb_out.splitlines()

        if samsung_lines:
            checks.append(Check("usb hardware", "pass", "Samsung device detected on USB bus",
                                samsung_lines))
        else:
            checks.append(Check("usb hardware", "fail", "No Samsung device in lsusb",
                                ["Bad cable (charge-only)", "Broken port",
                                 "Phone not connected or powered off"],
                                "Try a different USB cable and port"))
            issues += 1

        # Vendor ID check
        samsung_vid_count = sum(1 for l in usb_devices if "04e8" in l)
        if samsung_vid_count > 0:
            checks.append(Check("vendor id", "pass", "Samsung vendor ID (04e8) found"))
        else:
            checks.append(Check("vendor id", "fail",
                                "Samsung vendor ID (04e8) not found",
                                ["Phone may be in wrong mode",
                                 "Check for 'Allow USB debugging?' on screen"]))
            issues += 1
    else:
        checks.append(Check("usb hardware", "warn", "lsusb not available",
                            ["sudo apt install usbutils"]))

    # ── 4. ADB devices ──
    adb_devices_out = _run(f"{ADB} devices -l").stdout
    devices = _parse_devices(adb_devices_out)
    device_count = sum(1 for _, s in devices if s == "device")
    unauthorized = [sn for sn, s in devices if s == "unauthorized"]
    offline = [sn for sn, s in devices if s == "offline"]
    no_perms = [sn for sn, s in devices if s == "no permissions"]

    if device_count > 0:
        checks.append(Check("adb connection", "pass",
                            f"{device_count} device(s) connected",
                            [f"{sn}: {st}" for sn, st in devices]))
    else:
        detail_lines = []
        fix_lines = []

        if unauthorized:
            detail_lines.append(f"UNAUTHORIZED: {', '.join(unauthorized)}")
            fix_lines.extend([
                "Revoke USB debugging authorizations in Developer Options",
                "Re-plug USB and tap 'Allow' on the phone prompt",
            ])
        if offline:
            detail_lines.append(f"OFFLINE: {', '.join(offline)}")
            fix_lines.extend([
                "Toggle USB debugging OFF then ON",
                "Reboot phone if still offline",
            ])
        if no_perms:
            detail_lines.append(f"NO PERMISSIONS: {', '.join(no_perms)}")
            fix_lines.extend([
                "sudo udevadm control --reload-rules && sudo udevadm trigger",
                "sudo usermod -aG plugdev $USER → log out & back in",
            ])
        if not detail_lines:
            detail_lines.append("No devices in adb output")

        checks.append(Check("adb connection", "fail", "No ADB devices detected",
                            detail_lines, "\n".join(fix_lines) if fix_lines else None))
        issues += 1

    # ── 5. Udev rules ──
    udev_dir = Path("/etc/udev/rules.d")
    if udev_dir.is_dir():
        android_rules = list(udev_dir.glob("*android*")) + list(udev_dir.glob("*adb*"))
        samsung_rules = list(udev_dir.glob("*Samsung*")) + list(udev_dir.glob("*samsung*")) + list(udev_dir.glob("*04e8*"))
        if android_rules or samsung_rules:
            checks.append(Check("udev rules", "pass", "Android/Samsung udev rules found",
                                [str(p) for p in android_rules + samsung_rules]))
        else:
            rule = 'SUBSYSTEM=="usb", ATTR{idVendor}=="04e8", MODE="0666", GROUP="plugdev"'
            checks.append(Check("udev rules", "fail", "No Android udev rules found",
                                [f"Create /etc/udev/rules.d/51-android.rules",
                                 f"  {rule}",
                                 "sudo udevadm control --reload-rules",
                                 "sudo udevadm trigger"]))
            issues += 1

    # ── 6. User groups ──
    whoami = _run("whoami").stdout.strip()
    groups_out = _run(f"groups {whoami}").stdout
    if "plugdev" in groups_out:
        checks.append(Check("user groups", "pass", f"'{whoami}' is in plugdev group"))
    else:
        checks.append(Check("user groups", "fail", f"'{whoami}' NOT in plugdev",
                            [f"sudo usermod -aG plugdev {whoami}",
                             "Log out and log back in"]))
        issues += 1

    # ── 7. Samsung device details (if connected) ──
    device_info = {}
    if device_count > 0:
        props_to_check = {
            "model": "ro.product.model",
            "brand": "ro.product.brand",
            "android": "ro.build.version.release",
            "sdk": "ro.build.version.sdk",
            "serial": "ro.serialno",
            "usb_state": "sys.usb.state",
            "usb_config": "sys.usb.config",
        }
        for key, prop in props_to_check.items():
            val = _run(f"{ADB} shell getprop {prop}").stdout.strip()
            device_info[key] = val

        # Developer options
        dev_opts = _run(f"{ADB} shell settings get global development_settings_enabled").stdout.strip()
        usb_dbg = _run(f"{ADB} shell settings get global adb_enabled").stdout.strip()

        samsung_details = []
        samsung_details.append(f"Model: {device_info.get('brand', '?')} {device_info.get('model', '?')}")
        samsung_details.append(f"Android: {device_info.get('android', '?')} (SDK {device_info.get('sdk', '?')})")
        samsung_details.append(f"Serial: {device_info.get('serial', '?')}")
        samsung_details.append(f"USB state: {device_info.get('usb_state', '?')}")
        samsung_details.append(f"USB config: {device_info.get('usb_config', '?')}")

        if dev_opts == "1":
            samsung_details.append("Developer options: ENABLED")
        else:
            samsung_details.append("Developer options: DISABLED → Settings → About Phone → tap Build Number 7x")
            issues += 1

        if usb_dbg == "1":
            samsung_details.append("USB debugging: ENABLED")
        else:
            samsung_details.append("USB debugging: DISABLED → Settings → Developer Options → USB Debugging ON")
            issues += 1

        checks.append(Check("device info", "info", "Samsung device details", samsung_details))

    # ── 8. Kernel modules ──
    lsmod_out = _run("lsmod").stdout
    usb_modules = [l for l in lsmod_out.splitlines()
                   if re.search(r"usb|cdc|option|qcserial|f_samsung", l, re.I)]
    if usb_modules:
        checks.append(Check("kernel modules", "pass", "USB kernel modules loaded",
                            usb_modules[:8]))
    else:
        checks.append(Check("kernel modules", "warn", "No USB kernel modules visible",
                            ["May need sudo for full lsmod output"]))

    # ── 9. dmesg ──
    dmesg_out = _run("dmesg").stdout
    usb_dmesg = [l for l in dmesg_out.splitlines()
                 if re.search(r"usb|samsung|android|adb|gadget", l, re.I)]
    if usb_dmesg:
        checks.append(Check("dmesg", "info", "Recent USB-related kernel messages",
                            usb_dmesg[-10:]))
    else:
        checks.append(Check("dmesg", "warn", "No USB entries in dmesg",
                            ["May need sudo for full dmesg access"]))

    # ── 10. Fastboot ──
    if fb_path:
        fb_out = _run(f"{FASTBOOT} devices").stdout.strip()
        if fb_out:
            checks.append(Check("fastboot", "pass", "Fastboot device(s) found", fb_out.splitlines()))
        else:
            checks.append(Check("fastboot", "warn", "No fastboot devices",
                                ["Normal if phone isn't in bootloader mode",
                                 "Enter: adb reboot bootloader",
                                 "Or: hold Volume Down + Power while off"]))

    return {
        "checks": checks,
        "issues": issues,
        "device_info": device_info,
    }


def generate_fix_guide(result: dict) -> List[str]:
    """Return a prioritized fix list based on the diagnostics."""
    steps = []
    issues = result["issues"]

    if issues == 0:
        return ["Everything looks good — device should be working."]

    # Build fix steps from failed checks
    for check in result["checks"]:
        if check.status == "fail" and check.fix:
            steps.append(check.fix)

    # Always append the universal fallback steps
    steps.extend([
        "\n--- Universal fallback ---",
        "1. Unplug USB",
        "2. Phone: Settings → Developer Options → Revoke USB debugging authorizations",
        "3. Phone: Turn USB debugging OFF → wait 2s → ON",
        "4. Plug in → tap 'Allow USB debugging' on phone screen",
        "5. Run: adb kill-server && adb start-server",
        "6. If Samsung: enable 'USB debugging (Security settings)' in Developer Options",
        "7. Log out and log back in (for udev/group changes)",
        "8. Reboot phone and PC",
    ])

    return steps
