"""Web operator cockpit for PHREAK v5."""
from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

from ..core.connection import LoopbackConnector
from ..models import Device, DeviceStatus
from ..services.device_graph import DeviceGraphOrchestrator
from ..telemetry import TelemetryBus
from .api import AutomationAPI

if True:  # typing imports
    from .. import PhreakControlTower


class WebOperatorCockpit:
    """Serves a lightweight React cockpit to drive command dispatch."""

    def __init__(
        self,
        *,
        telemetry: TelemetryBus,
        device_graph: DeviceGraphOrchestrator,
        automation_api: Optional[AutomationAPI] = None,
    ) -> None:
        self.telemetry = telemetry
        self.device_graph = device_graph
        self.automation_api = automation_api

    def snapshot_state(self) -> Dict[str, object]:
        devices = self.device_graph.describe()
        summary = {
            "total": len(devices),
            "online": sum(1 for d in devices if d["status"] == "online"),
            "fastboot": sum(1 for d in devices if d["status"] == "fastboot"),
        }
        return {"devices": devices, "summary": summary}

    def export_state_json(self) -> str:
        state = self.snapshot_state()
        payload = json.dumps(state, indent=2, sort_keys=True)
        self.telemetry.emit("web.snapshot", {"device_count": state["summary"]["total"]})
        return payload

    def serve(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Launch a simple HTTP server exposing a React dashboard and JSON APIs."""
        cockpit = self

        class CockpitHandler(BaseHTTPRequestHandler):
            def _write_json(self, payload: Dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/api/state":
                    self._write_json(cockpit.snapshot_state())
                    return
                if self.path == "/":
                    page = cockpit._render_html().encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(page)))
                    self.end_headers()
                    self.wfile.write(page)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/api/command":
                    self.send_error(HTTPStatus.NOT_FOUND, "Unknown route")
                    return
                if cockpit.automation_api is None:
                    self._write_json(
                        {"status": "error", "message": "Automation API not configured"},
                        status=HTTPStatus.SERVICE_UNAVAILABLE,
                    )
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(content_length) or b"{}")
                response = asyncio.run(cockpit.automation_api.submit_command(payload))
                self._write_json(response)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer((host, port), CockpitHandler)
        self.telemetry.emit("web.server_started", {"host": host, "port": port})
        print(f"PHREAK web cockpit live at http://{host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            self.telemetry.emit("web.server_stopped", {"host": host, "port": port})

    def _render_html(self) -> str:
        return """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>PHREAK v5 Web Cockpit</title>
    <style>
      body { font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; }
      .wrap { max-width: 960px; margin: 0 auto; padding: 24px; }
      .card { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 8px; border-bottom: 1px solid #334155; }
      input, button { background: #1e293b; color: #e2e8f0; border: 1px solid #475569; border-radius: 8px; padding: 8px 10px; margin-right: 8px; }
      button { cursor: pointer; }
      .pill { display: inline-block; background: #1d4ed8; color: #dbeafe; border-radius: 999px; padding: 2px 10px; margin-right: 6px; font-size: 12px; }
      .ok { color: #4ade80; }
    </style>
  </head>
  <body>
    <div id=\"app\"></div>
    <script crossorigin src=\"https://unpkg.com/react@18/umd/react.production.min.js\"></script>
    <script crossorigin src=\"https://unpkg.com/react-dom@18/umd/react-dom.production.min.js\"></script>
    <script>
      const e = React.createElement;
      function App() {
        const [state, setState] = React.useState({devices: [], summary: {total: 0, online: 0, fastboot: 0}});
        const [deviceId, setDeviceId] = React.useState('demo-device-01');
        const [action, setAction] = React.useState('health.check');
        const [message, setMessage] = React.useState('');

        const refresh = () => fetch('/api/state').then(r => r.json()).then(setState);

        React.useEffect(() => {
          refresh();
          const timer = setInterval(refresh, 2500);
          return () => clearInterval(timer);
        }, []);

        const submit = async () => {
          const response = await fetch('/api/command', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action, device_ids: [deviceId], requested_by: 'web-cockpit'})
          });
          const payload = await response.json();
          setMessage(`Queued request ${payload.request_id || 'n/a'}`);
        };

        return e('div', {className: 'wrap'},
          e('h1', null, 'PHREAK v5 Web Cockpit'),
          e('div', {className: 'card'},
            e('span', {className: 'pill'}, `Devices: ${state.summary.total}`),
            e('span', {className: 'pill'}, `Online: ${state.summary.online}`),
            e('span', {className: 'pill'}, `Fastboot: ${state.summary.fastboot}`),
          ),
          e('div', {className: 'card'},
            e('h3', null, 'Dispatch command'),
            e('input', {value: deviceId, onChange: (evt) => setDeviceId(evt.target.value), placeholder: 'device id'}),
            e('input', {value: action, onChange: (evt) => setAction(evt.target.value), placeholder: 'action'}),
            e('button', {onClick: submit}, 'Send'),
            message ? e('p', {className: 'ok'}, message) : null,
          ),
          e('div', {className: 'card'},
            e('h3', null, 'Device table'),
            e('table', null,
              e('thead', null, e('tr', null,
                e('th', null, 'Device'), e('th', null, 'Status'), e('th', null, 'Tags'), e('th', null, 'Last seen')
              )),
              e('tbody', null, state.devices.map((d) => e('tr', {key: d.device_id},
                e('td', null, d.device_id),
                e('td', null, d.status),
                e('td', null, d.tags.join(', ')),
                e('td', null, d.last_seen)
              )))
            )
          )
        );
      }
      ReactDOM.createRoot(document.getElementById('app')).render(e(App));
    </script>
  </body>
</html>"""


def launch_web_cockpit(
    tower: "PhreakControlTower",
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    bootstrap_demo_device: bool = True,
) -> WebOperatorCockpit:
    """Create and start the web cockpit bound to a configured control tower."""
    if bootstrap_demo_device and not tower.device_graph.describe():
        demo = Device(
            device_id="demo-device-01",
            connection_uri="loopback://demo",
            status=DeviceStatus.ONLINE,
            tags=("demo", "web"),
        )
        tower.register_devices([demo])
        tower.connection_matrix.bind_connector(demo.device_id, LoopbackConnector())

    api = AutomationAPI(
        telemetry=tower.telemetry,
        router=tower.command_router,
        device_graph=tower.device_graph,
    )
    cockpit = WebOperatorCockpit(
        telemetry=tower.telemetry,
        device_graph=tower.device_graph,
        automation_api=api,
    )
    cockpit.serve(host=host, port=port)
    return cockpit


__all__ = ["WebOperatorCockpit", "launch_web_cockpit"]
