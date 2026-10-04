"""Domain DTOs shared by every layer.

Frozen dataclasses (research R3): ``Selection``, ``RuntimeSnapshot``, and
``Command`` are immutable value objects; ``CommandPlan`` is a ``list`` subclass
so equality, indexing, and slicing behave like a plain ``list``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    dirs: tuple[str, ...]
    files: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeSnapshot:
    in_tmux: bool
    tmux_server_running: bool
    existing: Mapping[str, str]


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]

    def argv(self) -> list[str]:
        return [self.program, *self.args]


class CommandPlan(list[Command]):
    """An ordered list of commands with list-compatible behavior."""
