# Usage Guide

`phreak_v5.presentation.rich_console` provides a terminal-first operator console powered by the Rich library. Launch it with `python -m phreak_v5` and follow the numbered prompts.

## Main Menu Overview

| Option | Description |
| ------ | ----------- |
| `1` | **ADB operations** — Manage devices that have booted Android with USB debugging enabled. |
| `2` | **Fastboot operations** — Work with devices in bootloader/fastboot mode. |
| `3` | **MTK BROM** — MediaTek-specific flows driven by `mtkclient`. |
| `4` | **Hack Arsenal** — Guided flows for rooting, vbmeta patching, and firmware discovery. |
| `5` | **Preflight Check** — Verifies host tooling, connected devices, and optional dependencies. |
| `6` | **Quit** — Exit the toolkit. |

Press `h` in any menu for contextual help. Type `hidden` or press `Ctrl+H` (when the `keyboard` package is installed) to open the hidden operations menu.

## ADB Operations

Key workflows available while a device is online in Android:

- Device profiler (JSON view of high-value `getprop` keys)
- Interactive shell and reboot controls
- Smart file push with APK auto-install and batch directory transfer
- Live logcat streaming and bloatware removal preset
- OTA sideload helper
- Firmware hunter: generate search links based on the connected device fingerprint
- USB debugging enablement helper for locked screens
- Contact search by phone number fragment
- **Diagnostic bundle collector:** run the new support-bundle generator to capture bug reports and dumpsys output with redaction

## Fastboot Operations

Available for devices in bootloader mode:

- Device inventory (`fastboot devices`, `getvar` snapshot)
- Bootloader lock/unlock helpers
- Partition flashing and temporary booting
- Backup/restore flows for common partitions
- VBMETA patching with optional flashing
- Magisk auto-root workflow that reboots, flashes, and reports status

## MTK BROM Operations

Designed for MediaTek devices that require BootROM access. The menu walks through driver checks, BootROM probing, and single-partition writes using `mtkclient`.

## Hack Arsenal

Provides wizard-like walk-throughs for high-risk operations:

- VBMETA patch and flash
- BootROM bypass and verification
- Magisk auto-root
- Firmware hunter helper
- Network unlock assistant

## Diagnostic Bundle Collector

The diagnostic bundle collector detects authorized ADB, restricted/unauthorized ADB, fastboot, and host-only states, then packages the best available evidence into a timestamped ZIP archive. An authorized ADB connection continues to work while the screen is locked. If Android has not authorized the host or USB debugging is disabled, the bundle records that restriction and gathers non-invasive host or fastboot diagnostics instead of failing. Trigger it from the ADB operations menu or run programmatically via `services.diag_collector.collect_diagnostics()`.

You will be prompted for the destination ZIP path and whether to include the full `adb bugreport` (which can be large). Progress is streamed inside the console.

The **USB debugging access check** reports whether the connected host is authorized. PHREAK can open an ADB terminal on an authorized device even while its screen is locked. Android does not permit an external tool to silently enable USB debugging or authorize a new host on a secured production device; carrier deployments should authorize access during device-owner, zero-touch, or other managed enrollment.

## Knowledge Base Docs

Supplemental documents live in the `docs/` directory:

- `hidden_commands.md` — Publish-ready cheat sheet of dialer codes and ADB/Fastboot probes
- `android_sdk_sample.md` — Kotlin telemetry collector skeleton
- `carrier_ticket_template.md` — Copy-and-paste provisioning ticket body
- `INSTALLATION.md` — Installation instructions

Use these documents for onboarding, training, or embedding in your own documentation portals.
