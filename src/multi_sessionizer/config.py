"""Legacy facade: re-exports config DTO + infrastructure loader (zero logic)."""

from __future__ import annotations

from .app.configuration import Config, ConfigNotFoundError
from .infrastructure.config_loader import load_config, missing_dirs, missing_files

__all__ = [
    "Config",
    "ConfigNotFoundError",
    "load_config",
    "missing_dirs",
    "missing_files",
]
