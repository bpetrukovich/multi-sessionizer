"""Domain DTOs shared by every layer.

Frozen dataclasses (research R3): ``Selection``, ``SessionSpec``,
``RuntimeSnapshot``, and ``Command`` are immutable value objects; ``CommandPlan``
is a ``list`` subclass so equality, indexing, and slicing behave like a plain
``list``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Selection:
    dirs: tuple[str, ...]
    workspaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionEntry:
    """A single element of the unified ``sessions`` config list (FR-001).

    A discriminated union over three forms: a directory (``kind ==
    "directory"``), an inline tmuxp workspace (``kind == "workspace"``), or a
    named group (``kind == "group"``). Group members are directory/workspace
    entries only — nesting is rejected (FR-007).
    """

    kind: str  # "directory" | "workspace" | "group"
    path: str = ""  # directory path (kind == "directory")
    definition: str = ""  # authored YAML (kind == "workspace")
    name: str = ""  # group label (kind == "group")
    members: tuple[SessionEntry, ...] = ()  # group members (dir/workspace only)
    tags: tuple[str, ...] = ()  # user-supplied picker tags (display only)


@dataclass(frozen=True)
class SessionSpec:
    """The provisioning unit the plan iterates over (FR-022, research R5)."""

    kind: str  # "directory" | "workspace"
    path: str = ""  # directory path (kind == "directory")
    definition: str = ""  # authored YAML (kind == "workspace")
    fingerprint: str = ""  # sha256(definition).hexdigest() (kind == "workspace")
    desired_name: str = ""  # declared session_name or `msz-<fp[:12]>` fallback


@dataclass(frozen=True)
class RuntimeSnapshot:
    in_tmux: bool
    tmux_server_running: bool
    existing: Mapping[str, str]
    markers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]
    input: str | None = None  # executor materializes to a temp file whose path
    #                           is appended as the final argument (research R12)

    def argv(self) -> list[str]:
        return [self.program, *self.args]


class CommandPlan(list[Command]):
    """An ordered list of commands with list-compatible behavior."""
