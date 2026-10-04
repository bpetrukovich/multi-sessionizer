"""App-owned configuration DTO (FR-011).

The higher layer defines the boundary contracts; infrastructure loads and
raises ``ConfigNotFoundError``. Missing keys mean empty tuples — no built-in
defaults.
"""

from __future__ import annotations

from dataclasses import dataclass


class ConfigNotFoundError(FileNotFoundError):
    """Raised when the configuration file does not exist."""


@dataclass(frozen=True)
class Config:
    project_roots_depth_1: tuple[str, ...] = ()
    project_roots_depth_2: tuple[str, ...] = ()
    additional_dirs: tuple[str, ...] = ()
    tmuxp_workspaces: tuple[str, ...] = ()
