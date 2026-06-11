import json
import subprocess
import zipfile

from services import diag_collector


def _result(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)


def _read_bundle(path):
    with zipfile.ZipFile(path) as bundle:
        return {
            name: bundle.read(name).decode("utf-8")
            for name in bundle.namelist()
        }


def test_collects_authorized_adb_device_even_when_screen_is_locked(tmp_path, monkeypatch):
    def fake_run(cmd, timeout=120):
        if cmd == ["adb", "devices", "-l"]:
            return _result(cmd, stdout="List of devices attached\nserial-1 device product:test\n")
        if cmd == ["fastboot", "devices"]:
            return _result(cmd)
        if "window" in cmd:
            return _result(cmd, stdout="isStatusBarKeyguard=true")
        return _result(cmd, stdout="probe output")

    monkeypatch.setattr(diag_collector, "_run", fake_run)
    output = diag_collector.collect_diagnostics(tmp_path / "bundle.zip", include_bugreport=False)
    files = _read_bundle(output)
    manifest = json.loads(files["manifest.json"])

    assert manifest["collection_mode"] == "adb_authorized"
    assert "isStatusBarKeyguard=true" in files["screen_lock_state.txt"]
    assert "$ adb -s serial-1 shell dumpsys telephony.registry" in files["telephony.txt"]
    assert "$ adb -s serial-1 shell dumpsys device_policy" in files["device_policy.txt"]
    assert "development_settings_enabled" in files["developer_settings.txt"]
    assert "motorola|thinkshield|oemconfig" in files["motorola_enterprise_packages.txt"]


def test_unauthorized_adb_device_still_creates_access_report(tmp_path, monkeypatch):
    def fake_run(cmd, timeout=120):
        if cmd == ["adb", "devices", "-l"]:
            return _result(cmd, stdout="List of devices attached\nserial-1 unauthorized\n")
        return _result(cmd)

    monkeypatch.setattr(diag_collector, "_run", fake_run)
    output = diag_collector.collect_diagnostics(tmp_path / "bundle.zip")
    files = _read_bundle(output)
    manifest = json.loads(files["manifest.json"])

    assert manifest["collection_mode"] == "adb_restricted"
    assert "unauthorized" in manifest["limitations"][0]
    assert "telephony.txt" not in files


def test_fastboot_device_collects_bootloader_diagnostics(tmp_path, monkeypatch):
    def fake_run(cmd, timeout=120):
        if cmd == ["adb", "devices", "-l"]:
            return _result(cmd, returncode=127, stderr="adb missing")
        if cmd == ["fastboot", "devices"]:
            return _result(cmd, stdout="boot-serial\tfastboot\n")
        if cmd == ["fastboot", "-s", "boot-serial", "getvar", "all"]:
            return _result(cmd, stdout="(bootloader) product:test")
        return _result(cmd)

    monkeypatch.setattr(diag_collector, "_run", fake_run)
    output = diag_collector.collect_diagnostics(tmp_path / "bundle.zip")
    files = _read_bundle(output)
    manifest = json.loads(files["manifest.json"])

    assert manifest["collection_mode"] == "fastboot"
    assert "(bootloader) product:test" in files["fastboot_getvar_all.txt"]
