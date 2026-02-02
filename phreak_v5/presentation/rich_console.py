#!/usr/bin/env python3
# PHREAK v5 — Android Operator Console with integrated workflow arsenal
# Author: Chris Hirschauer
import os, sys, shlex, subprocess, time, json, glob, re, shutil
import importlib
import importlib.util
from datetime import datetime
from pathlib import Path

keyboard_spec = importlib.util.find_spec("keyboard")
keyboard = importlib.import_module("keyboard") if keyboard_spec else None

ADB = "adb"
FASTBOOT = "fastboot"
MTK = "python3 " + str(Path.home() / "Apps/mtkclient/mtk")
LOG_FILE = Path.home() / "phreak_console.log.jsonl"
LAST = ""  # persists on-screen
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT_DIR / "docs"
KNOWLEDGE_BASE = [
    ("Hidden commands cheat sheet", "Dialer codes and safe ADB/Fastboot probes.", DOCS_DIR / "hidden_commands.md"),
    ("Carrier ticket template", "Copy/paste provisioning escalation body.", DOCS_DIR / "carrier_ticket_template.md"),
    ("Android SDK telemetry sample", "Kotlin collector skeleton for apps.", DOCS_DIR / "android_sdk_sample.md"),
    ("Installation guide", "Host setup requirements and dependency list.", DOCS_DIR / "INSTALLATION.md"),
    ("Usage guide", "Menu walkthroughs and feature overview.", DOCS_DIR / "USAGE.md"),
]

# ---------- Logging ----------
def log_event(action, cmd, out, err, code):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "action": action, "cmd": cmd, "stdout": out, "stderr": err, "exit": code
    }
    with open(LOG_FILE, "a") as f: f.write(json.dumps(entry) + "\n")

from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
import threading, time, sys

from services.diag_collector import collect_diagnostics

console = Console()

class Spinner:
    def __init__(self, text="working...", transient=True, fallback=True):
        self.text = text
        self.transient = transient
        self.fallback = fallback
        self.progress = None
        self.live = None
        self.task_id = None
        self._running = False
        self._thread = None

    def _build(self):
        self.progress = Progress(
            SpinnerColumn("dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=self.transient,
        )
        self.live = Live(self.progress, console=console, refresh_per_second=12)

    def start(self, text=None):
        if text:
            self.text = text
        try:
            self._build()
            self.live.__enter__()
            self.task_id = self.progress.add_task(self.text, total=None)
            self._running = True
            # Background refresher
            self._thread = threading.Thread(target=self._keepalive, daemon=True)
            self._thread.start()
        except Exception as e:
            if self.fallback:
                sys.stdout.write(f"[spinner] {self.text}...\n")
                sys.stdout.flush()

    def _keepalive(self):
        # Keep description fresh
        while self._running and self.progress and self.task_id is not None:
            self.progress.update(self.task_id, description=self.text)
            time.sleep(0.2)

    def update(self, text):
        """Update the message shown beside the spinner."""
        self.text = text

    def stop(self, final=None, success=True):
        """Stop spinner; optionally print final message."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        try:
            if self.progress and self.task_id is not None:
                if final:
                    style = "green" if success else "red"
                    self.progress.update(self.task_id, description=f"[{style}]{final}")
                self.live.__exit__(None, None, None)
        except Exception as e:
            if self.fallback:
                sys.stdout.write(f"[spinner stopped] {final or self.text}\n")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop(success=(exc_type is None))


# ---------- UI ----------
def clear(): os.system("clear" if os.name == "posix" else "cls")


def banner():
    art = r"""   ____ _ _   ____      ____            ____              _
  / ___(_) |_|  _ \  _ / ___| ___  _ __|  _ \  ___   ___| |__   ___ _ __
 | |  _| | __| | | |/ / \___ \ / _ \| '__| | | |/ _ \ / __| '_ \ / _ \ '__|
 | |_| | | |_| |_| / /__ ___) | (_) | |  | |_| | (_) | (__| | | |  __/ |
  \____|_|\__|____/_____|____/ \___/|_|  |____/ \___/ \___|_| |_|\___|_|
"""
    console.print(f"[magenta]{art}[/magenta]")
    console.print("[white]PHREAK v5 Android Control Center[/white]\n")

# change draw signature
def draw(title, options, info=None, show_last=True, *, first_render=False):
    if first_render:
        clear()
        banner()
        quick_tips = Text(
            "Navigate with the number keys • h for contextual help • b to go back • q to exit",
            style="cyan",
        )
        console.print(Panel.fit(quick_tips, border_style="bright_magenta"))
    else:
        console.rule(style="bright_magenta")

    console.print(f"[bold cyan]{title}[/bold cyan]", justify="left")
    console.print("[dim]Use the shortcuts shown below to take action.[/dim]\n")

    if info:
        info_table = Table.grid(padding=(0, 1))
        info_table.add_column("Property", style="yellow", justify="right")
        info_table.add_column("Value", style="white")
        for k, v in info.items():
            info_table.add_row(k, v)
        console.print(Panel(info_table, title="Device Snapshot", border_style="yellow"))

    option_table = Table(box=box.SIMPLE_HEAD, show_header=False, padding=(0, 1))
    option_table.add_column("Choice", style="bold green", justify="right", width=6)
    option_table.add_column("Action", style="white")
    option_table.add_column("Details", style="dim")

    for idx, (label, desc) in enumerate(options, 1):
        option_table.add_row(f"[{idx}]", label, desc or "")

    console.print(option_table)

    if show_last:
        status_text = LAST or "No actions yet"
        console.print(Panel.fit(f"Last action: {status_text}", border_style="dim", style="dim"))


# ---------- Detect ----------
def mode():
    out,_,_ = run(f"{ADB} get-state","detect_adb")
    if out.strip()=="device": return "adb"
    out,_,_ = run(f"{FASTBOOT} devices","detect_fastboot")
    if "fastboot" in out: return "fastboot"
    return None

def adb_props():
    out,_,_ = run(f"{ADB} shell getprop","getprop")
    props={}
    for line in out.splitlines():
        m=re.match(r"\[(.*?)\]: \[(.*)\]", line)
        if m: props[m.group(1)]=m.group(2)
    info={
        "brand": props.get("ro.product.brand","?"),
        "model": props.get("ro.product.model","?"),
        "device": props.get("ro.product.device","?"),
        "board": props.get("ro.product.board","?"),
        "android": props.get("ro.build.version.release","?"),
        "sdk": props.get("ro.build.version.sdk","?"),
        "fingerprint": props.get("ro.build.fingerprint","?"),
        "patch": props.get("ro.build.version.security_patch","?")
    }
    return info


def save_device_snapshot(output_path: Path | None = None) -> Path:
    """Save the current adb_props() snapshot to a JSON file."""
    global LAST
    info = adb_props()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if output_path is None:
        output_path = Path.cwd() / f"device_snapshot_{timestamp}.json"
    else:
        output_path = Path(output_path)
    output_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    LAST = f"snapshot saved: {output_path}"
    return output_path


def view_recent_activity(limit: int = 20) -> None:
    """Render recent command activity from the JSONL log file."""
    if not LOG_FILE.exists():
        console.print("[yellow]No log entries yet.[/yellow]")
        input("\nPress Enter…")
        return
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    if not lines:
        console.print("[yellow]No log entries yet.[/yellow]")
        input("\nPress Enter…")
        return
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Action", style="magenta")
    table.add_column("Exit", style="green", justify="right")
    table.add_column("Command", style="white")
    for line in lines[-limit:]:
        try:
            entry = json.loads(line)
            table.add_row(
                entry.get("ts", "?"),
                entry.get("action", "?"),
                str(entry.get("exit", "?")),
                entry.get("cmd", ""),
            )
        except json.JSONDecodeError:
            table.add_row("?", "invalid", "?", line[:120])
    console.print(Panel(table, title="Recent Activity", border_style="bright_magenta"))
    input("\nPress Enter…")

def detect_screen_state():
    """Detect if device is screen locked"""
    out, _, _ = run(f"{ADB} shell dumpsys window policy", "screen_check")
    return "isStatusBarKeyguard" in out and "true" in out

def enable_debug_locked():
    """Attempt to enable USB debugging on locked device"""
    if not detect_screen_state():
        print("Device is not locked")
        return False
    
    print("Device is screen locked. Attempting USB debugging enable...")
    
    # Method 1: Try settings.db modification
    try:
        print("Attempting Method 1: Settings database modification")
        run(f"{ADB} pull /data/data/com.android.providers.settings/databases/settings.db ~/settings.db", 
            "pull_settings_db")
        
        # Modify settings.db
        with Spinner("Modifying USB debug settings"):
            run("""sqlite3 ~/settings.db <<EOF
                UPDATE secure SET value=1 WHERE name='development_settings_enabled';
                UPDATE secure SET value=1 WHERE name='adb_enabled';
                EXIT;
                EOF""", "modify_settings_db", shell=True)
            
            run(f"{ADB} push ~/settings.db /data/data/com.android.providers.settings/databases/", 
                "push_settings_db")
            os.remove("~/settings.db")
            
        return True
    
    except Exception as e:
        print(f"Method 1 failed: {str(e)}")
        return False

def unlock_screen():
    """Attempt to bypass screen lock"""
    print("Attempting screen lock bypass...")
    
    # Try Google FindMyDevice method
    out, _, _ = run(f"{ADB} shell pm list packages com.google.android.gms", "check_gms")
    if "package:" in out:
        print("Google Play Services found. Using FindMyDevice method...")
        # This requires user interaction with Google account
        print("Please go to Google FindMyDevice website and:")
        print("1. Select this device")
        print("2. Click 'Lock'")
        print("3. Enter temporary password")
        input("Press Enter when done...")
        return True
        
    # Try MTK-specific method if MediaTek device
    out, _, _ = run(f"{ADB} shell getprop ro.mediatek.hardware", "check_mtk")
    if "mtk" in out.lower():
        print("MediaTek device detected. Using MTK method...")
        run(f"{MTK} auth", "mtk_auth", shell=True)
        return True
        
    return False

def enable_debug_anyway():
    """Main function to handle locked device USB debugging"""
    if detect_screen_state():
        print("\033[93mWarning: Device is screen locked!\033[0m")
        if unlock_screen():
            print("\033[92mScreen unlocked successfully! Enabling USB debugging...\033[0m")
            enable_debug_locked()
        else:
            print("\033[91mFailed to bypass screen lock.\033[0m")
    else:
        print("Device is not locked. Proceeding normally...")


def locate_by_phone_number():
    """Query contacts on the device for a matching phone number."""
    raw = input("Enter phone number or fragment: ").strip()
    if not raw:
        print("No number provided.")
        return

    digits = re.sub(r"[^0-9+]", "", raw)
    if not digits:
        print("Input did not contain any dialable characters.")
        return

    like = f"%{digits}%"
    where_clause = f"\"number LIKE '{like}'\""
    cmd = (
        f"{ADB} shell content query --uri content://contacts/phones "
        "--projection display_name:number --sort order ASC "
        f"--where {where_clause}"
    )

    out, err, code = run(cmd, "adb_locate_contact", shell=True)
    if code != 0:
        print("Unable to query contacts. Ensure the device is unlocked and USB debugging is allowed.")
        return

    matches = []
    for line in out.splitlines():
        if "display_name=" in line and "number=" in line:
            parts = dict(
                kv.split("=", 1) for kv in line.split() if "=" in kv
            )
            name = parts.get("display_name", "<unknown>")
            number = parts.get("number", "<unknown>")
            matches.append((name, number))

    if not matches:
        print("No contacts matched that number fragment.")
        return

    print("\nMatches:")
    for name, number in matches:
        print(f" • {name}: {number}")


def network_unlock_assistant():
    """Collect diagnostic info and walk through carrier unlock steps."""
    print("Gathering radio and SIM lock state…")
    probes = {
        "SIM status": "gsm.sim.state",
        "Carrier": "gsm.operator.alpha",
        "Network lock": "persist.radio.network_lock",
        "Service provider": "gsm.sim.operator.alpha",
        "Bootloader unlocked": "ro.boot.flash.locked",
    }

    results = {}
    for label, prop in probes.items():
        out, _, _ = run(f"{ADB} shell getprop {prop}", f"getprop_{prop}")
        results[label] = out.strip() or "<unknown>"

    print("\nCurrent device state:")
    for label, value in results.items():
        print(f" • {label}: {value}")

    locked_indicators = {"NETWORK_LOCKED", "PERM_DISABLED", "PERSO_LOCKED"}
    if any(value.upper() in locked_indicators for value in results.values()):
        print("\nThe device reports an active network lock.")
    else:
        print("\nNo explicit network lock detected from getprop output.")

    print("\nNext steps:")
    print(" 1. Request an unlock code from the original carrier (requires account verification).")
    print(" 2. Insert a non-accepted SIM and enter the unlock code when prompted.")
    print(" 3. If no prompt appears, reboot into fastboot and run 'fastboot oem unlock-go' if supported.")
    print(" 4. Some carriers require remote unlock – contact their support with the IMEI shown below.")

    imei_out, _, _ = run(f"{ADB} shell service call iphonesubinfo 1", "read_imei")
    if imei_out:
        print("\nIMEI response:")
        print(imei_out)
    else:
        print("\nCould not read IMEI via service call. Use *#06# on the device instead.")


def fb_info():
    # quick probe to see if anything is in fastboot
    out,_,_ = run(f"{FASTBOOT} devices", "fb_devices_probe", timeout=2)
    has = any(line.strip().endswith("fastboot") for line in (out or "").splitlines())
    if not has:
        # Try a short, animated wait loop (up to ~10s) before giving up
        deadline = time.time() + 10
        with Spinner("waiting for fastboot device"):
            while time.time() < deadline:
                out,_,_ = run(f"{FASTBOOT} devices", "fb_devices_probe", timeout=1)
                if any(line.strip().endswith("fastboot") for line in (out or "").splitlines()):
                    has = True
                    break
                time.sleep(0.3)
        if not has:
            return {"note": "no fastboot device detected (check cable/udev)"}

    # We have a device; fetch vars with short timeouts and a spinner
    info = {}
    keys = ["product","variant","version-baseband","version-bootloader","secure","unlocked"]
    with Spinner("querying bootloader vars"):
        for k in keys:
            o,_,_ = run(f"{FASTBOOT} getvar {k}", f"fb_{k}", timeout=2)
            if o:
                info[k] = o.replace("(bootloader) ","").strip()
    return info if info else {"note": "fastboot device present"}


# ---------- Smart push / batch / install ----------
def adb_push_smart():
    local=input("Local file path: ").strip()
    if not os.path.exists(local):
        print("❌ not found"); return
    remote = input("Remote (default /sdcard/Download/): ").strip() or "/sdcard/Download/"
    run(f"{ADB} push {shlex.quote(local)} {shlex.quote(remote)}","adb_push")
    base=os.path.basename(local)
    path_remote = remote.rstrip("/")+"/"+base
    if local.lower().endswith(".apk"):
        run(f"{ADB} shell pm install -r {shlex.quote(path_remote)}","adb_install")
    elif local.lower().endswith(".zip"):
        print("📦 OTA zip? Use: adb sideload <zip> from recovery.")

def adb_batch_push():
    folder=input("Local dir: ").strip()
    if not os.path.isdir(folder): print("❌ not a dir"); return
    remote = input("Remote base (default /sdcard/Download/): ").strip() or "/sdcard/Download/"
    for f in sorted(os.listdir(folder)):
        p=os.path.join(folder,f)
        if os.path.isfile(p):
            run(f"{ADB} push {shlex.quote(p)} {shlex.quote(remote)}","adb_batch_push")

# ---------- Logcat ----------
def logcat():
    print("Ctrl+C to stop…"); os.system(f"{ADB} logcat")

# ---------- Debloat ----------
DEBLOAT = [
    "com.facebook.katana","com.facebook.appmanager","com.facebook.services","com.facebook.system",
]
def debloat():
    for pkg in DEBLOAT:
        run(f"{ADB} shell pm uninstall -k --user 0 {pkg}", f"debloat_{pkg}")

# ---------- OTA sideload ----------
def sideload():
    zipf=input("Path to OTA zip: ").strip()
    run(f"{ADB} reboot recovery","reboot_recovery"); print("Booting recovery…")
    time.sleep(8)
    run(f"{ADB} sideload {shlex.quote(zipf)}","adb_sideload")

# ---------- Fastboot basics ----------
def fb_flash():
    part=input("Partition (boot, recovery, vbmeta, super, dtbo…): ").strip()
    img =input("Image path: ").strip()
    run(f"{FASTBOOT} flash {part} {shlex.quote(img)}", f"flash_{part}")

def fb_boot():
    img=input("Boot (RAM boot) image path: ").strip()
    run(f"{FASTBOOT} boot {shlex.quote(img)}","fastboot_boot")

def fb_backup():
    parts=["boot","recovery","vbmeta","dtbo"]
    outdir=f"backup_{int(time.time())}"; os.makedirs(outdir,exist_ok=True)
    for p in parts:
        run(f"{FASTBOOT} fetch {p} {outdir}/{p}.img", f"backup_{p}")
    print(f"✅ backup → {outdir}")

def fb_restore():
    indir=input("Backup dir: ").strip()
    for img in glob.glob(os.path.join(indir,"*.img")):
        part=os.path.splitext(os.path.basename(img))[0]
        run(f"{FASTBOOT} flash {part} {img}", f"restore_{part}")

# ---------- VBMETA patch ----------
def patch_vbmeta_menu():
    vb=input("Path to vbmeta.bin/img: ").strip()
    out="vbmeta_patched.img"
    cmd = ("avbtool make_vbmeta_image --disable_verity --disable_verification "
           f"--output {out}")
    print("🔧 Patching vbmeta…")
    _,_,code=run(cmd,"patch_vbmeta",shell=True)
    if code!=0:
        print("❌ avbtool missing. Install with: pip install avbtool"); return
    print(f"✅ wrote {out}")
    if input("Flash patched vbmeta now? (y/N): ").lower()=="y":
        run(f"{FASTBOOT} flash vbmeta {out}","flash_vbmeta")

# ---------- Auto-root ----------
def auto_root_magisk():
    boot=input("Path to stock boot.img (matching your build): ").strip()
    if not os.path.exists(boot): print("❌ need stock boot.img"); return
    dest="/sdcard/Download/boot-to-patch.img"
    run(f"{ADB} push {boot} {dest}","push_boot_for_patch")
    run(f"{ADB} shell am start -a android.intent.action.VIEW -d file://{dest} "
        " -n com.topjohnwu.magisk/.ui.MainActivity", "launch_magisk", shell=True)
    print("📲 Patch in Magisk, then return here.")
    input("Press Enter when magisk_patched-*.img is ready…")
    out,_,_=run(f"{ADB} shell ls -t /sdcard/Download/ | head -n 20","list_downloads",shell=True)
    cand=[x for x in out.splitlines() if x.startswith("magisk_patched") and x.endswith(".img")]
    if not cand: print("❌ couldn't see patched image"); return
    patched=cand[0]
    run(f"{ADB} pull /sdcard/Download/{patched} .","pull_patched")
    if input(f"Flash {patched} to boot via fastboot now? (y/N): ").lower()=="y":
        run(f"{ADB} reboot bootloader","reboot_bl")
        run(f"{FASTBOOT} flash boot {patched}","flash_patched_boot")
        print("✅ Rooted boot flashed")

# ---------- Firmware Hunter ----------
def build_search_urls(info):
    brand=info.get("brand","").lower(); device=info.get("device",""); fp=info.get("fingerprint","")
    urls=[
        "https://www.google.com/search?q="+f"{brand} {device} stock firmware".replace(" ","+"),
        "https://www.google.com/search?q="+f"XDA {brand} {device} firmware".replace(" ","+"),
        "https://www.google.com/search?q="+f"{brand} {device} MTK scatter download".replace(" ","+")
    ]
    return urls

def firmware_hunter():
    info=adb_props() if mode()=="adb" else fb_info()
    print("Device fingerprint:", info.get("fingerprint","?"))
    urls=build_search_urls(info)
    print("\nUse these to fetch the *matching* build:")
    for u in urls: print("  →", u)
    print("\n⚠️ boot.img + super/vendor/system + vbmeta must match the SAME build.")


def collect_support_bundle_interactive():
    """Interactive wrapper for the diagnostic bundle collector."""
    default_path = Path.cwd() / f"support_bundle_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    dest = input(f"Output zip path [{default_path}]: ").strip() or str(default_path)
    include_bugreport = input("Include full adb bugreport? [Y/n]: ").strip().lower() not in {"n", "no"}

    spinner = Spinner("Collecting diagnostics", transient=False)
    spinner.start()

    try:
        bundle_path = collect_diagnostics(
            dest,
            include_bugreport=include_bugreport,
            progress_cb=lambda msg: spinner.update(msg),
        )
        spinner.stop(final=f"Bundle saved → {bundle_path}")
        print(f"\n📦 Support bundle created: {bundle_path}\n")
    except Exception as exc:
        spinner.stop(final="Collection failed", success=False)
        print(f"\n❌ Diagnostic collection failed: {exc}\n")


def _render_document(path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        console.print(f"[red]Document not found:[/red] {path}")
        return
    console.print(Markdown(content), soft_wrap=True)
    input("\nPress Enter to return…")


def knowledge_base_menu():
    first_render = True
    while True:
        opts = [(title, desc) for title, desc, _ in KNOWLEDGE_BASE]
        opts.append(("Back", "Return to main menu."))
        draw("KNOWLEDGE BASE", opts, first_render=first_render, show_last=False)
        first_render = False
        choice = input("Select: ").strip().lower()
        if choice in {"b", str(len(opts))}:
            break
        if choice == "h":
            help_block("KB")
            continue
        if not choice.isdigit():
            continue
        idx = int(choice) - 1
        if idx < 0 or idx >= len(KNOWLEDGE_BASE):
            continue
        _, _, doc_path = KNOWLEDGE_BASE[idx]
        _render_document(doc_path)


def preflight():
    print("\n\033[96mPreflight checks\033[0m")

    tools = {
        "adb": (
            "adb",
            "sudo apt-get install -y adb"
        ),
        "fastboot": (
            "fastboot",
            "sudo apt-get install -y fastboot"
        ),
        "avbtool": (
            "avbtool",
            "python3 -m pip install --user avbtool"
        ),
        "mtk": (
            "mtk",
            "git clone https://github.com/bkerler/mtkclient.git ~/Apps/mtkclient && "
            "cd ~/Apps/mtkclient && python3 -m pip install --user -r requirements.txt"
        ),
    }

    for name, (binary, install_cmd) in tools.items():
        path = shutil.which(binary)
        if path:
            print(f" • {name}: {path}")
        else:
            print(f" • {name}: \033[91mMISSING\033[0m — attempting install…")
            out, err, code = run(install_cmd, action=f"install_{name}", shell=True, timeout=300)
            if code == 0:
                print(f"   ✅ {name} installed successfully")
            else:
                print(f"   ❌ {name} install failed (exit {code})")
                if err:
                    print(f"     stderr: {err.splitlines()[-1]}")

    # --- Post-checks ---
    out, _, _ = run("lsusb", "lsusb", shell=True)
    if "0e8d:" in out:
        print(" • MTK device present (0e8d).")

    out, _, _ = run(f"{ADB} devices", "adb_devices")
    if "device" in out.split():
        print(" • ADB device connected.")

    out, _, _ = run(f"{FASTBOOT} devices", "fb_devices")
    if "fastboot" in out:
        print(" • Fastboot device connected.")

    input("\nPress Enter…")

def run(cmd, action="exec", shell=False, timeout=None, show_spinner=False, spinner_text=None):
    global LAST
    sp = None
    try:
        # Start spinner if enabled
        if show_spinner:
            sp = Spinner(spinner_text or f"{action}…")
            sp.start()

        if shell:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=timeout,
            )
        else:
            proc = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        out, err, code = proc.stdout.strip(), proc.stderr.strip(), proc.returncode
        log_event(action, cmd, out, err, code)

        FIRST = (out.splitlines()[0] if out else "") or (err.splitlines()[0] if err else "")
        LAST = f"[{action}] exit={code} :: {FIRST}"

        # Report result through spinner
        if sp:
            if code == 0:
                sp.stop(final=f"{action} ok", success=True)
            else:
                sp.stop(final=f"{action} failed", success=False)

        if code != 0:
            if out:
                preview = "\n".join(out.splitlines()[:10])
                print(f"\n[{action}] output:\n{preview}\n")
            if err:
                preview_err = "\n".join(err.splitlines()[:10])
                print(f"[{action}] error:\n{preview_err}\n")
            print(f"[{action}] exited with status {code}")

        return out, err, code

    except subprocess.TimeoutExpired:
        LAST = f"[{action}] timeout"
        log_event(action, cmd, "", "timeout", 124)
        if sp: sp.stop(final=f"{action} timeout", success=False)
        return "", "timeout", 124

    except FileNotFoundError:
        LAST = f"[{action}] missing binary: {cmd.split()[0]}"
        log_event(action, cmd, "", LAST, 127)
        if sp: sp.stop(final=f"{action} missing", success=False)
        return "", LAST, 127

    finally:
        if sp and sp._running:  # just in case
            sp.stop()


# ---------- MTK bypass ----------
def mtk_probe():
    print("Attempting BROM handshake (mtkclient)…")
    run(f"{MTK} print","mtk_print",shell=True)

def mtk_write_single():
    part=input("Partition name: ").strip()
    img =input("Image path: ").strip()
    run(f"{MTK} wl {part} {shlex.quote(img)}","mtk_write",shell=True)

# ---------- Hack Arsenal ----------
def hack_vbmeta(): patch_vbmeta_menu()
def hack_brom_bypass(): mtk_probe()
def hack_magisk_root(): auto_root_magisk()
def hack_firmware_hunter(): firmware_hunter()


# ---------- Menus ----------
def help_block(topic):
    HELP = {
        "MAIN": """Select a mode based on how the phone is connected:
- ADB ops: phone is ON with USB debugging (adb devices shows 'device').
- Fastboot ops: phone in bootloader (fastboot devices shows a serial).
- MTK BROM: MediaTek BootROM bypass (mtkclient), used when SPFT asks for .auth.
- Hack Arsenal: guided flows (fix dm-verity, root, etc.).
- Knowledge base: renders cheat sheets, templates, and SDK snippets.
- Activity log: review recent command outcomes from the session log.""",
        "ADB": """Common paths:
- Remote path usually /sdcard/Download/  (writable without root)
- /data/local/tmp/ is a staging area (writable via adb)
- 'Push file (smart)' installs APKs automatically after push.
- 'OTA sideload' requires stock recovery + an update.zip.
- 'Save device snapshot' writes a JSON profile to the working directory.""",
        "FASTBOOT": """Flashing writes directly to partitions. Triple-check file/partition:
- vbmeta: Verified Boot metadata (patch to disable verity).
- super: dynamic partitions container (system/vendor/product).
- boot: kernel+ramdisk (can be Magisk-patched).
Type FLASH when prompted to execute risky writes.""",
        "MTK": """BROM steps:
1) Power OFF phone.
2) Hold Vol+ and Vol- (or testpoint) and plug USB.
3) Run 'Probe BROM' to verify handshake (requires mtkclient).
If SP Flash Tool asks for .auth, use BROM bypass instead.""",
        "HACK": """Guided flows:
- Patch+Flash VBMETA: disables dm-verity/verification.
- BROM Bypass: talks to BootROM to skip .auth.
- Magisk Auto-Root: push stock boot.img -> patch in Magisk -> pull/flash.
- Firmware Hunter: builds search links for the exact fingerprint/codename."""
        ,
        "KB": """Knowledge base documents render in the console. Use arrow keys or PgUp/PgDn in your terminal to scroll, then press Enter to return."""
    }
    print("\n\033[96m[HELP]\033[0m " + HELP.get(topic, "No help for this section.") + "\n")
    input("Press Enter…")

def menu_hack():
    first_render = True
    while True:
        opts = [
            ("Patch + Flash VBMETA", "Disable verity/verification (fix dm-verity)"),
            ("BROM Bypass", "Confirm BootROM handshake (bypass .auth)"),
            ("Magisk Auto-Root", "Patch boot with Magisk then flash"),
            ("Firmware Hunter", "Find matching firmware builds"),
            ("Network Unlock Assistant", "Check SIM lock state and guided steps"),
            ("Back", "Return to main menu")
        ]
        draw("HACK ARSENAL", opts, first_render=first_render)
        first_render = False
        c = input("Select: ").strip()
        if c == "1": hack_vbmeta()
        elif c == "2": hack_brom_bypass()
        elif c == "3": hack_magisk_root()
        elif c == "4": hack_firmware_hunter()
        elif c == "5": network_unlock_assistant()
        elif c == "6": break

def menu_adb():
    first_render = True
    while True:
        info = adb_props()
        opts = [
            ("Device profiler (JSON)", "Show brand/model/codename/build/patch."),
            ("Shell", "Open interactive adb shell on the phone."),
            ("Reboot", "Reboot Android normally."),
            ("Reboot to bootloader", "Switch to fastboot mode."),
            ("Push file (smart default)", "Push to /sdcard/Download/. APKs auto-install."),
            ("Batch push directory", "Push all files from a local folder."),
            ("Install APK (manual path)", "Install APK from local path via adb."),
            ("Logcat (live)", "Live logs; Ctrl+C to stop."),
            ("Debloat (profile)", "Uninstall common bloat for user 0."),
            ("OTA sideload", "Stream update.zip to recovery."),
            ("Firmware Hunter (links)", "Build search URLs for exact firmware."),
            ("Enable USB Debugging (locked)", "Try various methods to enable debugging"),
            ("Locate contact by phone number", "Search device contacts for a number fragment."),
            ("Collect diagnostic bundle", "Generate redacted support ZIP for carriers."),
            ("Save device snapshot", "Write device profile JSON to the local folder."),
            ("Back", "Return to main menu."),
        ]
        draw("ADB MENU", opts, info, first_render=first_render)
        first_render = False
        c = input("Select: ").strip().lower()
        if   c == "h": help_block("ADB")
        elif c == "b": break
        elif c == "q": sys.exit(0)
        elif c == "1": print(json.dumps(info, indent=2)); input("Enter…")
        elif c == "2": os.system(f"{ADB} shell")
        elif c == "3": run(f"{ADB} reboot", "adb_reboot")
        elif c == "4": run(f"{ADB} reboot bootloader", "adb_reboot_bl"); return
        elif c == "5": adb_push_smart()
        elif c == "6": adb_batch_push()
        elif c == "7": apk = input("APK path: ").strip(); run(f"{ADB} install -r {shlex.quote(apk)}", "adb_install")
        elif c == "8": print("Ctrl+C to stop…"); os.system(f"{ADB} logcat")
        elif c == "9": debloat()
        elif c == "10": sideload()
        elif c == "11": firmware_hunter()
        elif c == "12": enable_debug_anyway()
        elif c == "13": locate_by_phone_number()
        elif c == "14": collect_support_bundle_interactive()
        elif c == "15":
            snapshot = save_device_snapshot()
            print(f"\nSaved snapshot: {snapshot}")
            input("Enter…")
        elif c == "16": break

def menu_fastboot():
    first_render = True
    while True:
        # fetch info with an animated spinner
        info = fb_info()
        opts = [
            ("List devices", "Verify fastboot connection."),
            ("OEM unlock", "Request unlock (varies by OEM)."),
            ("OEM lock", "Re-lock bootloader (danger: wipes on many devices)."),
            ("Flash partition", "Write an image to a named partition."),
            ("Boot image (RAM)", "Temp-boot an image without flashing."),
            ("Reboot", "Leave fastboot and boot system."),
            ("Backup critical partitions", "fastboot fetch boot/recovery/vbmeta/dtbo."),
            ("Restore backup dir", "Flash all .img files from a directory."),
            ("Patch + Flash VBMETA", "Disable verity/verification (fix dm-verity)."),
            ("Auto-Root (Magisk flow)", "Patch boot with Magisk then flash."),
            ("Back", "Return to main menu."),
        ]
        draw("FASTBOOT MENU", opts, info, first_render=first_render)
        first_render = False
        c = input("Select: ").strip().lower()
        if   c=="1": run(f"{FASTBOOT} devices","fb_devices")
        elif c=="2": run(f"{FASTBOOT} oem unlock","fb_unlock")
        elif c=="3": run(f"{FASTBOOT} oem lock","fb_lock")
        elif c=="4": fb_flash()
        elif c=="5": fb_boot()
        elif c=="6": run(f"{FASTBOOT} reboot","fb_reboot")
        elif c=="7": fb_backup()
        elif c=="8": fb_restore()
        elif c=="9": patch_vbmeta_menu()
        elif c=="10": auto_root_magisk()
        elif c=="11": break

def menu_mtk():
    first_render = True
    while True:
        opts = [
            ("Preflight (drivers/checks)", "Check adb/fastboot/avbtool/mtk and USB state."),
            ("Probe BROM (mtkclient print)", "Confirm BootROM handshake (bypass .auth)."),
            ("Write single partition (mtk wl)", "Bypass write boot/recovery/super/vbmeta."),
            ("Back", "Return to main menu."),
        ]
        draw(
            "MTK BROM MENU",
            opts,
            {"hint": "Phone OFF → hold Vol+ and Vol- → plug USB"},
            first_render=first_render,
        )
        first_render = False
        c = input("Select: ").strip().lower()
        if   c == "1": preflight()
        elif c == "2": mtk_probe()
        elif c == "3": mtk_write_single()
        elif c == "4": break

class HiddenMenu:
    def __init__(self, hotkey_module=None):
        self._pending = False
        self._lock = threading.Lock()
        self._hotkey_registered = False
        if hotkey_module is not None:
            try:
                hotkey_module.on_press_key("ctrl+h", lambda _: self._schedule_show())
                self._hotkey_registered = True
            except Exception:
                self._hotkey_registered = False

    def _schedule_show(self):
        with self._lock:
            if self._pending:
                return
            self._pending = True
        print("\n[hidden] Hidden menu requested. Complete the current selection to view it.")

    def maybe_show(self):
        with self._lock:
            if not self._pending:
                return
            self._pending = False
        self._show_menu()

    def open_menu(self):
        self._show_menu()

    def _show_menu(self):
        opts = [
            ("Advanced shell (root)", "Launch an interactive adb shell with su."),
            ("System backup (fastboot)", "Fetch boot/recovery/system/vendor/super via fastboot."),
            ("Back", "Return to the previous menu."),
        ]
        first_render = True
        while True:
            draw("HIDDEN OPS", opts, first_render=first_render)
            first_render = False
            choice = input("Select: ").strip().lower()
            if choice in {"3", "b", "q"}:
                break
            if choice == "1":
                self.advanced_shell()
            elif choice == "2":
                self.system_backup()

    def advanced_shell(self):
        """Interactive shell with root access"""
        with Spinner("Starting advanced shell"):
            run(f"{ADB} shell su", "advanced_shell", shell=True)

    def system_backup(self):
        """Backup system partitions"""
        parts = ['boot', 'recovery', 'system', 'vendor', 'super']
        outdir = f"backup_{int(time.time())}"
        os.makedirs(outdir, exist_ok=True)

        with Spinner("Backing up system partitions"):
            for part in parts:
                run(
                    f"{FASTBOOT} fetch {part} {outdir}/{part}.img",
                    f"backup_{part}",
                    timeout=300,
                )
        print(f"Backups saved to {outdir}")


def main():
    hidden_menu = HiddenMenu(keyboard)

    first_render = True
    while True:
        hidden_menu.maybe_show()
        m = mode()
        info = None
        if m == "adb":
            info = adb_props()
        elif m == "fastboot":
            info = fb_info()

        opts = [
            ("ADB operations", "Phone ON + USB debugging. File ops, sideload, logs."),
            ("Fastboot operations", "Bootloader mode. Flash/backup/boot images."),
            ("MTK BROM", "MediaTek BootROM bypass via mtkclient."),
            ("Hack Arsenal (Guided)", "Wizards: fix dm-verity, unbrick MTK, root, firmware."),
            ("Preflight Check", "Check tools/drivers/devices before you start."),
            ("Knowledge base library", "Cheat sheets, templates, SDK samples."),
            ("Activity log", "Review recent console command history."),
            ("Quit", "Exit the console.")
        ]

        draw("MAIN MENU", opts, info, first_render=first_render)
        first_render = False
        c = input("Select: ").strip().lower()
        if   c == "h": help_block("MAIN")
        elif c == "q" or c == "8": sys.exit(0)
        elif c == "b": continue
        elif c == "1": menu_adb()
        elif c == "2": menu_fastboot()
        elif c == "3": menu_mtk()
        elif c == "4": menu_hack()
        elif c == "5": preflight()
        elif c == "6": knowledge_base_menu()
        elif c == "7": view_recent_activity()
        elif c == "hidden": hidden_menu.open_menu()


if __name__=="__main__":
    main()
