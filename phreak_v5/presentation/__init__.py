"""Presentation layer surfaces for PHREAK v5."""
from .api import AutomationAPI
from .curses_ui import CursesControlRoom
from .observability import ObservabilityService
from .web import WebOperatorCockpit


def rich_console_main() -> None:
    """Lazy import wrapper for the Rich console entrypoint."""
    from .rich_console import main

    main()


__all__ = [
    "CursesControlRoom",
    "AutomationAPI",
    "WebOperatorCockpit",
    "ObservabilityService",
    "rich_console_main",
]
