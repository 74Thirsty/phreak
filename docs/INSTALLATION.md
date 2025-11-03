# Installation Guide

PHREAK v5 ships as a standalone Python application. The toolkit targets Linux, macOS, and Windows hosts with the Android SDK platform tools installed.

## 1. System Requirements

- **Operating system:** Linux, macOS, or Windows 10+
- **Python:** 3.10, 3.11, or 3.12
- **Android platform tools:** `adb` and `fastboot` must be available on your `PATH`
- **Optional tooling:**
  - [`avbtool`](https://android.googlesource.com/platform/external/avb/) for vbmeta patching
  - [`mtkclient`](https://github.com/bkerler/mtkclient) for MediaTek BootROM work
  - `sqlite3` for secure settings manipulation on locked devices

## 2. Clone the Repository

```bash
git clone https://github.com/74Thirsty/phreak.git
cd phreak
```

## 3. Create a Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

## 4. Install Python Dependencies

PHREAK v5 relies solely on the standard library plus [`rich`](https://github.com/Textualize/rich) for its text-based UI. Install the requirement from `pyproject.toml`.

```bash
pip install -r requirements.txt  # if you maintain a pinned list
# or install manually
pip install rich
```

## 5. Verify Platform Tools

```bash
adb version
fastboot --version
```

Both commands should report valid versions. If either fails, install the Android SDK Platform Tools from Google and add the extracted directory to your `PATH`.

## 6. Configure Optional Hotkeys

The hidden operations menu listens for `Ctrl+H` via the `keyboard` module when available. To enable hotkey support:

```bash
pip install keyboard
```

Hotkeys are optional; the menu remains reachable by typing `hidden` at the prompt.

## 7. Launch the Toolkit

```bash
python -m phreak_v5
```

Use a USB cable with proper drivers for your platform, authorize the host for USB debugging, and you are ready to work.
