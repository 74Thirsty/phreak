"""
MDM Integration Module
Encapsulated hmdm-server client and service bindings for Phreak.
Do not import outside this folder directly.
"""

from __future__ import annotations

__all__ = ["run_cli"]


def run_cli() -> None:
    """Launch the interactive CLI for ad-hoc investigations."""

    from .cli import run_cli as _run_cli

    _run_cli()
