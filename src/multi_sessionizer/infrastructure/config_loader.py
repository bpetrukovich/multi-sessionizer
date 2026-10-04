"""ConfigLoader adapter: reads the TOML config file (constitution III).

The config file lives at ``~/.config/multi-sessionizer/config.toml`` (override
with the ``MULTI_SESSIONIZER_CONFIG`` environment variable). The file is
required: there are no built-in defaults. Every key is optional; missing keys
mean "empty tuple". Environment variables (``$HOME``, ...) and ``~`` are
expanded in every path. Raises the app-owned ``ConfigNotFoundError`` when the
file is absent (FR-006).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from ..app.configuration import Config, ConfigNotFoundError

DEFAULT_CONFIG_PATH = Path("~/.config/multi-sessionizer/config.toml").expanduser()
ENV_CONFIG_PATH = "MULTI_SESSIONIZER_CONFIG"

_FIELDS = (
    "project_roots_depth_1",
    "project_roots_depth_2",
    "additional_dirs",
    "additional_files",
)


def _expand(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def _expand_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_expand(v) for v in values)


def _as_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        path = Path(os.environ.get(ENV_CONFIG_PATH, DEFAULT_CONFIG_PATH))
    path = Path(path)

    if not path.is_file():
        raise ConfigNotFoundError(path)

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    values: dict[str, tuple[str, ...]] = {}
    for field in _FIELDS:
        raw = data.get(field)
        values[field] = _expand_tuple(_as_tuple(raw))
    return Config(**values)


def missing_files(cfg: Config) -> list[str]:
    return [p for p in cfg.additional_files if not os.path.exists(p)]


def missing_dirs(cfg: Config) -> list[str]:
    roots = (*cfg.project_roots_depth_1, *cfg.project_roots_depth_2)
    return [p for p in (*roots, *cfg.additional_dirs) if not os.path.isdir(p)]


class FileConfigLoader:
    """Object adapter satisfying the app ``ConfigLoader`` port."""

    def load(self) -> Config:
        return load_config()

    def missing_files(self, cfg: Config) -> list[str]:
        return missing_files(cfg)

    def missing_dirs(self, cfg: Config) -> list[str]:
        return missing_dirs(cfg)
