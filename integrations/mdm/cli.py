"""Interactive CLI for the MDM integration.

This module exposes a Rich-powered command loop that lets operators audit
and manage devices without wiring the integration into the primary console.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text
from requests import HTTPError
from requests.exceptions import RequestException

from .models import Device, Policy
from .server import MDMService
from .utils import timestamp

console = Console()


def _render_devices(devices: Iterable[Device]) -> None:
    table = Table(
        title="Enrolled Devices",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
        show_lines=False,
        show_edge=False,
    )
    table.add_column("ID", style="bold white")
    table.add_column("IMEI", style="green")
    table.add_column("Model", style="magenta")
    table.add_column("Policy", style="yellow")
    table.add_column("Last Seen", style="blue")

    for device in devices:
        table.add_row(
            str(device.id),
            device.imei or "—",
            device.model or "—",
            str(device.policy_id) if device.policy_id is not None else "—",
            device.last_seen or "—",
        )

    console.print(table)


def _render_policies(policies: Iterable[Policy]) -> None:
    table = Table(
        title="Policies",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
        show_lines=False,
        show_edge=False,
    )
    table.add_column("ID", style="bold white")
    table.add_column("Name", style="magenta")
    table.add_column("Apps", style="green")
    table.add_column("Restrictions", style="yellow")

    for policy in policies:
        table.add_row(
            str(policy.id),
            policy.name,
            ", ".join(policy.apps) if policy.apps else "—",
            ", ".join(sorted(policy.restrictions)) if policy.restrictions else "—",
        )

    console.print(table)


def _export_snapshot(service: MDMService) -> Path:
    snapshot = {
        "generated_at": timestamp(),
        "devices": [asdict(d) for d in service.list_devices()],
        "policies": [asdict(p) for p in service.list_policies()],
    }
    output_dir = Path("mdm_forensics")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stamp = snapshot["generated_at"].replace(":", "-").replace(".", "_")
    export_path = output_dir / f"mdm_snapshot_{safe_stamp}.json"
    with export_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2)
    return export_path


def _handle_error(error: RequestException) -> None:
    message = Text("MDM API error", style="bold red")
    body = Text(str(error), style="red")
    console.print(Panel(body, title=message, border_style="red", expand=False))


def _apply_policy(service: MDMService) -> None:
    device_id = IntPrompt.ask("Enter the device ID to target")
    policy_id = IntPrompt.ask("Enter the policy ID to apply")
    if not Confirm.ask(
        f"Apply policy [bold]{policy_id}[/] to device [bold]{device_id}[/]?",
        default=True,
    ):
        console.print("[yellow]Operation cancelled.[/]")
        return
    try:
        response = service.apply_policy(device_id=device_id, policy_id=policy_id)
    except HTTPError as error:
        _handle_error(error)
        return
    except RequestException as error:
        _handle_error(error)
        return

    console.print(Panel.fit(str(response), title="Policy push response", border_style="green"))


def run_cli() -> None:
    service = MDMService()
    hero = Panel(
        Align.center(
            Text(
                "Mobile Device Management Interactive Shell", style="bold white"
            ),
        ),
        subtitle="Press Ctrl+C to exit at any time",
        border_style="cyan",
    )
    console.print(hero)

    options = {
        "1": "List devices",
        "2": "List policies",
        "3": "Apply policy to device",
        "4": "Export forensic snapshot",
        "5": "Refresh audit (devices & policies)",
        "q": "Quit",
    }

    while True:
        console.print()
        menu = Table(box=None, show_header=False)
        menu.add_column("Option", style="bold green")
        menu.add_column("Description", style="white")
        for key, description in options.items():
            menu.add_row(key, description)
        console.print(menu)

        choice = Prompt.ask("Select an action", choices=list(options.keys()), default="5")

        try:
            if choice == "1":
                _render_devices(service.list_devices())
            elif choice == "2":
                _render_policies(service.list_policies())
            elif choice == "3":
                _apply_policy(service)
            elif choice == "4":
                export_path = _export_snapshot(service)
                console.print(
                    Panel.fit(
                        f"Snapshot saved to [bold]{export_path}[/]",
                        title="Export complete",
                        border_style="green",
                    )
                )
            elif choice == "5":
                devices = service.list_devices()
                policies = service.list_policies()
                console.rule("Device Overview")
                _render_devices(devices)
                console.rule("Policy Overview")
                _render_policies(policies)
            elif choice == "q":
                console.print("[bold cyan]Bye![/]")
                return
        except HTTPError as error:
            _handle_error(error)
        except RequestException as error:
            _handle_error(error)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user.[/]")
            return


if __name__ == "__main__":
    run_cli()
