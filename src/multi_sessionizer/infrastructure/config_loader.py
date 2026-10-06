"""ConfigLoader adapter: reads the TOML config file (constitution III).

The config file lives at ``~/.config/multi-sessionizer/config.toml`` (override
with the ``MULTI_SESSIONIZER_CONFIG`` environment variable). The file is
required: there are no built-in defaults. Every key is optional; missing keys
mean "empty tuple". Environment variables (``$HOME``, ...) and ``~`` are
expanded in every directory path. The unified ``sessions`` list is classified
by the pure domain classifier; directory entries (top-level and group members)
are realpath-normalized here while workspace definitions stay verbatim
(FR-003/FR-016). Removed keys (``additional_dirs`` / ``tmuxp_workspaces``) and
structurally invalid ``sessions`` raise the app-owned ``ConfigError`` with all
problems collected (FR-002/FR-010).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from ..app.configuration import Config, ConfigError, ConfigNotFoundError
from ..domain.models import SessionEntry
from ..domain.session_entries import classify_sessions

DEFAULT_CONFIG_PATH = Path("~/.config/multi-sessionizer/config.toml").expanduser()
ENV_CONFIG_PATH = "MULTI_SESSIONIZER_CONFIG"

_REMOVED_KEYS = ("additional_dirs", "tmuxp_workspaces")

_STRING_FIELDS = ("project_roots_depth_1", "project_roots_depth_2")


def _expand(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def _as_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _normalize_entry(entry: SessionEntry) -> SessionEntry:
    """Realpath directory paths; keep workspace definitions verbatim (R8)."""
    if entry.kind == "directory":
        return SessionEntry(kind="directory", path=os.path.realpath(_expand(entry.path)))
    if entry.kind == "group":
        return SessionEntry(
            kind="group",
            name=entry.name,
            members=tuple(_normalize_entry(m) for m in entry.members),
            tags=entry.tags,
        )
    return entry


def _load_sessions(raw: object) -> tuple[SessionEntry, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raw = [raw]
    entries, problems = classify_sessions(raw)
    if problems:
        raise ConfigError(problems)
    return tuple(_normalize_entry(e) for e in entries)


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        path = Path(os.environ.get(ENV_CONFIG_PATH, DEFAULT_CONFIG_PATH))
    path = Path(path)

    if not path.is_file():
        raise ConfigNotFoundError(path)

    with path.open("rb") as fh:
        data = tomllib.load(fh)

    removed = [
        f"Configuration error: the '{key}' key is no longer supported; use 'sessions' instead."
        for key in _REMOVED_KEYS
        if key in data
    ]
    if removed:
        raise ConfigError(removed)

    values: dict[str, tuple[str, ...]] = {}
    for field in _STRING_FIELDS:
        values[field] = tuple(_expand(v) for v in _as_tuple(data.get(field)))
    return Config(
        project_roots_depth_1=values["project_roots_depth_1"],
        project_roots_depth_2=values["project_roots_depth_2"],
        sessions=_load_sessions(data.get("sessions")),
    )


def _directory_paths(entries: tuple[SessionEntry, ...]) -> list[str]:
    paths: list[str] = []
    for entry in entries:
        if entry.kind == "directory":
            paths.append(entry.path)
        elif entry.kind == "group":
            paths.extend(_directory_paths(entry.members))
    return paths


def missing_dirs(cfg: Config) -> list[str]:
    roots = (*cfg.project_roots_depth_1, *cfg.project_roots_depth_2)
    return [p for p in (*roots, *_directory_paths(cfg.sessions)) if not os.path.isdir(p)]


class FileConfigLoader:
    """Object adapter satisfying the app ``ConfigLoader`` port."""

    def load(self) -> Config:
        return load_config()

    def missing_dirs(self, cfg: Config) -> list[str]:
        return missing_dirs(cfg)
