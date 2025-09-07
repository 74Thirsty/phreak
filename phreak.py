#!/usr/bin/env python3
# PHREAK v4 — full Android Operator Console with Hack Arsenal

import os, sys, shlex, subprocess, time, json, glob, re
from datetime import datetime
from pathlib import Path

ADB = "adb"
FASTBOOT = "fastboot"
MTK = "python3 mtk"                    # mtkclient entry (adjust path if needed)
LOG_FILE = Path.home() / "phreak_tool.log.jsonl"
LAST = ""  # persists on-screen

# ---------- Logging ----------
def log_event(action, cmd, out, err, code):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "action": action, "cmd": cmd, "stdout": out, "stderr": err, "exit": code
    }
    with open(LOG_FILE, "a") as f: f.write(json.dumps(entry) + "\n")

def run(cmd, action="exec", shell=False, timeout=None, show_spinner=False, spinner_text=None):
    global LAST
    sp = None
    try:
        if show_spinner:
            sp = Spinner(spinner_text or f"{action}…")
            sp.start()

        if shell:
            proc = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=timeout)
        else:
            proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=timeout)

        out, err, code = proc.stdout.strip(), proc.stderr.strip(), proc.returncode
        log_event(action, cmd, out, err, code)
        FIRST = (out.splitlines()[0] if out else "") or (err.splitlines()[0] if err else "")
        LAST = f"[{action}] exit={code} :: {FIRST}"
        return out, err, code

    except subprocess.TimeoutExpired:
        LAST = f"[{action}] timeout"
        log_event(action, cmd, "", "timeout", 124)
        return "", "timeout", 124

    except FileNotFoundError:
        LAST = f"[{action}] missing binary: {cmd.split()[0]}"
        log_event(action, cmd, "", LAST, 127)
        return "", LAST, 127

    finally:
        if sp: sp.stop()


# ---------- UI ----------
def clear(): os.system("clear" if os.name == "posix" else "cls")
def banner():
    art = r"""           █████                                   █████      ███
          ░░███                                   ░░███      ░███
 ████████  ░███ █████ ████████   ██████   ██████   ░███ █████░███
░░███░░███ ░███░░███ ░░███░░███ ███░░███ ░░░░░███  ░███░░███ ░███
 ░███ ░███ ░██████░   ░███ ░░░ ░███████   ███████  ░██████░  ░███
 ░███ ░███ ░███░░███  ░███     ░███░░░   ███░░███  ░███░░███ ░░░ 
 ░███████  ████ █████ █████    ░░██████ ░░████████ ████ █████ ███
 ░███░░░  ░░░░ ░░░░░ ░░░░░      ░░░░░░   ░░░░░░░░ ░░░░ ░░░░░ ░░░ 
 ░███                                                            
 █████                                                           
░░░░░                                                            """
    print("\033[95m" + art + "\033[0m")
    print("       \033[97mAndroid Operator Console v4 (Hack Arsenal)\033[0m\n")

# change draw signature
def draw(title, options, info=None, show_last=True):
    clear(); banner()
    print(f"\033[96m=== {title} ===\033[0m   (h=help, b=back, q=quit)\n")
    if info:
        print("\033[93m--- Device Info ---\033[0m")
        for k,v in info.items(): print(f"{k:14}: {v}")
        print("")
    for i,(label,desc) in enumerate(options,1):
        print(f"{i}) {label}\n    \033[90m{desc}\033[0m")
    if show_last:
        print("\n\033[90mLast: " + (LAST or "No actions yet") + "\033[0m")


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

def menu_hack():
    while True:
        opts=[
            "Patch + Flash VBMETA (disable verity)",
            "BROM Bypass (mtkclient)",
            "Magisk Auto-Root",
            "Firmware Hunter",
            "Back"
        ]
        draw("HACK ARSENAL", opts)
        c=input("Select: ").strip()
        if   c=="1": hack_vbmeta()
        elif c=="2": hack_brom_bypass()
        elif c=="3": hack_magisk_root()
        elif c=="4": hack_firmware_hunter()
        elif c=="5": break

# ---------- Menus ----------
def menu_adb():
    while True:
        info=adb_props()
        opts=[
            "Device profiler (JSON)",
            "Shell",
            "Reboot",
            "Reboot to bootloader",
            "Push file (smart default)",
            "Batch push directory",
            "Install APK (manual path)",
            "Logcat (live)",
            "Debloat (profile)",
            "OTA sideload",
            "Firmware Hunter (links)",
            "Back"
        ]
        draw("ADB MENU", opts, info)
        c=input("Select: ").strip()
        if   c=="1": print(json.dumps(info,indent=2)); input("Enter to continue…")
        elif c=="2": os.system(f"{ADB} shell")
        elif c=="3": run(f"{ADB} reboot","adb_reboot")
        elif c=="4": run(f"{ADB} reboot bootloader","adb_reboot_bl"); return
        elif c=="5": adb_push_smart()
        elif c=="6": adb_batch_push()
        elif c=="7": apk=input("APK path: ").strip(); run(f"{ADB} install -r {shlex.quote(apk)}","adb_install")
        elif c=="8": logcat()
        elif c=="9": debloat()
        elif c=="10": sideload()
        elif c=="11": firmware_hunter()
        elif c=="12": break

def menu_fastboot():
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
        draw("FASTBOOT MENU", opts, info)
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
    while True:
        opts = [
            ("Preflight (drivers/checks)", "Check adb/fastboot/avbtool/mtk and USB state."),
            ("Probe BROM (mtkclient print)", "Confirm BootROM handshake (bypass .auth)."),
            ("Write single partition (mtk wl)", "Bypass write boot/recovery/super/vbmeta."),
            ("Back", "Return to main menu."),
        ]
        draw("MTK BROM MENU", opts, {"hint": "Phone OFF → hold Vol+ and Vol- → plug USB"})
        c = input("Select: ").strip().lower()
        if   c == "1": mtk_probe()
        elif c == "2": mtk_write_single()
        elif c == "3": break
        elif c == "4": break

def main():
    while True:
        m=mode()
        opts=["ADB operations","Fastboot operations","MTK BROM","Hack Arsenal","Quit"]
        info=None
        if m=="adb": info=adb_props()
        elif m=="fastboot": info=fb_info()
        draw("MAIN MENU", opts, info)
        c=input("Select: ").strip()
        if   c=="1": menu_adb()
        elif c=="2": menu_fastboot()
        elif c=="3": menu_mtk()
        elif c=="4": menu_hack()
        elif c=="5": print("Later."); sys.exit(0)

if __name__=="__main__":
    main()
