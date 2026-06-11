from phreak_v5.presentation import rich_console


def test_adb_access_state_selects_authorized_device(monkeypatch):
    monkeypatch.setattr(
        rich_console,
        "run",
        lambda *args, **kwargs: (
            "List of devices attached\nblocked unauthorized\nready device product:test\n",
            "",
            0,
        ),
    )

    serial, devices, error = rich_console.adb_access_state()

    assert serial == "ready"
    assert devices == [("blocked", "unauthorized"), ("ready", "device")]
    assert error == ""


def test_open_terminal_refuses_unauthorized_device(monkeypatch):
    monkeypatch.setattr(
        rich_console,
        "adb_access_state",
        lambda: (None, [("blocked", "unauthorized")], ""),
    )
    monkeypatch.setattr(rich_console, "show_usb_debugging_status", lambda: False)
    called = []
    monkeypatch.setattr(rich_console.subprocess, "call", lambda cmd: called.append(cmd))

    assert rich_console.open_adb_terminal() is False
    assert called == []


def test_open_terminal_uses_selected_serial(monkeypatch):
    monkeypatch.setattr(
        rich_console,
        "adb_access_state",
        lambda: ("ready", [("ready", "device")], ""),
    )
    called = []
    monkeypatch.setattr(rich_console.subprocess, "call", lambda cmd: called.append(cmd) or 0)

    assert rich_console.open_adb_terminal() is True
    assert called == [["adb", "-s", "ready", "shell"]]
