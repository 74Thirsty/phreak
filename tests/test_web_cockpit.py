from phreak_v5 import PhreakControlTower
from phreak_v5.models import Device, DeviceStatus
from phreak_v5.presentation.web import WebOperatorCockpit, launch_web_cockpit


def test_snapshot_state_counts_statuses():
    tower = PhreakControlTower()
    tower.register_devices(
        [
            Device("a", "adb://a", status=DeviceStatus.ONLINE),
            Device("b", "fastboot://b", status=DeviceStatus.FASTBOOT),
        ]
    )
    cockpit = WebOperatorCockpit(telemetry=tower.telemetry, device_graph=tower.device_graph)

    snapshot = cockpit.snapshot_state()

    assert snapshot["summary"] == {"total": 2, "online": 1, "fastboot": 1}


def test_rendered_html_contains_react_shell():
    tower = PhreakControlTower()
    cockpit = WebOperatorCockpit(telemetry=tower.telemetry, device_graph=tower.device_graph)

    html = cockpit._render_html()

    assert "react.production.min.js" in html
    assert "/api/command" in html


def test_launch_web_cockpit_bootstraps_demo_device_without_server(monkeypatch):
    tower = PhreakControlTower()

    def fake_serve(self, host="127.0.0.1", port=8765):
        return None

    monkeypatch.setattr("phreak_v5.presentation.web.WebOperatorCockpit.serve", fake_serve)
    launch_web_cockpit(tower)

    state = tower.device_graph.describe()
    assert len(state) == 1
    assert state[0]["device_id"] == "demo-device-01"
