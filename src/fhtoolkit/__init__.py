"""
Utilities for querying Flathub AppStream metadata and downloading related
`.flatpakref` descriptors.
"""

from importlib import metadata


try:
    __version__ = metadata.version("fhtoolkit")
except metadata.PackageNotFoundError:  # pragma: no cover - during local development
    __version__ = "0.0.0"


__all__ = ["__version__"]
