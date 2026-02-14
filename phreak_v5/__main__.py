"""Command-line entrypoint for the PHREAK v5 console."""
from __future__ import annotations

import argparse

from . import PhreakControlTower
from .presentation.web import launch_web_cockpit


def run() -> None:
    """Launch the Rich console or optional web cockpit."""
    parser = argparse.ArgumentParser(prog="python -m phreak_v5")
    parser.add_argument("--web", action="store_true", help="Launch the web cockpit instead of the Rich console.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for web mode.")
    parser.add_argument("--port", type=int, default=8765, help="Port for web mode.")
    args = parser.parse_args()

    if args.web:
        tower = PhreakControlTower()
        tower.bootstrap()
        launch_web_cockpit(tower, host=args.host, port=args.port)
        return

    from .presentation.rich_console import main

    main()


if __name__ == "__main__":
    run()
