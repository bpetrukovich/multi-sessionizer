"""Legacy facade: re-exports config DTO + infrastructure loader (zero logic)."""

from __future__ import annotations

from .app.configuration import Config, ConfigError, ConfigNotFoundError
from .infrastructure.config_loader import load_config, missing_dirs

__all__ = [
    "Config",
    "ConfigError",
    "ConfigNotFoundError",
    "load_config",
    "missing_dirs",
]
