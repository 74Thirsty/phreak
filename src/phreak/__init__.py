"""Top-level package that brings together the PHREAK toolchain."""

from importlib import metadata as _metadata

try:  # pragma: no cover - fallback when package metadata is missing
    __version__ = _metadata.version("phreak")
except _metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from phreak_v5 import (  # re-export for convenience
    ControlTowerComponents,
    PhreakControlTower,
)

__all__ = [
    "ControlTowerComponents",
    "PhreakControlTower",
    "__version__",
]
