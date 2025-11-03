"""Presentation layer surfaces for PHREAK v5."""
from .curses_ui import CursesControlRoom
from .api import AutomationAPI
from .web import WebOperatorCockpit
from .observability import ObservabilityService
from .rich_console import main as rich_console_main

__all__ = [
    "CursesControlRoom",
    "AutomationAPI",
    "WebOperatorCockpit",
    "ObservabilityService",
    "rich_console_main",
]
