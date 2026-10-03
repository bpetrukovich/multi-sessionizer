"""Pure planning of the tmux/zoxide command sequence.

``plan`` turns a selection into an ordered list of :class:`Command` objects,
mirroring the branching logic of the original bash script:

- a single selection attaches/switches straight into that session;
- multiple selections create/reuse a session per path and then run one
  post-step: attach to the first session (outside tmux, no server),
  ``choose-session`` (inside tmux) or a plain ``attach``.

Directories are processed before files. Session creation decisions are made
from a snapshot of already-existing sessions (a ``name -> path`` mapping) plus
the sessions created earlier in the same plan. An existing session is reused
only when it belongs to the same directory; otherwise the name is
disambiguated with a numeric suffix (``dup``, ``dup-2``, ``dup-3``).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .naming import session_name


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]

    def argv(self) -> list[str]:
        return [self.program, *self.args]


def _same_path(a: str, b: str) -> bool:
    return os.path.realpath(a) == os.path.realpath(b)


def _resolve_name(
    base: str,
    cwd: str,
    existing: Mapping[str, str],
    created: dict[str, str],
) -> str:
    name = base
    index = 2
    while name in existing or name in created:
        if _same_path(existing.get(name, ""), cwd) or _same_path(created.get(name, ""), cwd):
            return name
        name = f"{base}-{index}"
        index += 1
    return name


def _ensure_session(
    cmds: list[Command],
    existing: Mapping[str, str],
    created: dict[str, str],
    base_name: str,
    cwd: str,
) -> str:
    name = _resolve_name(base_name, cwd, existing, created)
    cmds.append(Command("zoxide", ("add", cwd)))
    if name not in existing and name not in created:
        cmds.append(Command("tmux", ("new-session", "-ds", name, "-c", cwd)))
        created[name] = cwd
    return name


def _attach_single(cmds: list[Command], in_tmux: bool, name: str) -> None:
    if in_tmux:
        cmds.append(Command("tmux", ("switch-client", "-t", name)))
        cmds.append(Command("tmux", ("refresh-client", "-S")))
    else:
        cmds.append(Command("tmux", ("attach", "-t", name)))


def _post_step(
    cmds: list[Command],
    in_tmux: bool,
    tmux_server_running: bool,
    first_name: str,
) -> None:
    if not in_tmux and not tmux_server_running:
        cmds.append(Command("tmux", ("attach", "-t", first_name)))
    elif in_tmux:
        cmds.append(Command("tmux", ("choose-session",)))
        cmds.append(Command("tmux", ("refresh-client", "-S")))
    else:
        cmds.append(Command("tmux", ("attach",)))


def plan(
    dirs: Iterable[str],
    files: Iterable[str],
    *,
    in_tmux: bool,
    tmux_server_running: bool,
    existing: Mapping[str, str] | None = None,
) -> list[Command]:
    dirs = list(dirs)
    files = list(files)
    existing = existing if existing is not None else {}
    created: dict[str, str] = {}
    cmds: list[Command] = []

    if len(dirs) == 1 and not files:
        name = _ensure_session(cmds, existing, created, session_name(dirs[0]), dirs[0])
        _attach_single(cmds, in_tmux, name)
        return cmds

    if len(files) == 1 and not dirs:
        filepath = files[0]
        dir_ = os.path.dirname(filepath)
        name = _ensure_session(cmds, existing, created, session_name(dir_), dir_)
        cmds.append(Command("tmux", ("send-keys", "-t", name, f"nvim '{filepath}'", "Enter")))
        _attach_single(cmds, in_tmux, name)
        return cmds

    first_name: str | None = None
    for dir_ in dirs:
        name = _ensure_session(cmds, existing, created, session_name(dir_), dir_)
        if first_name is None:
            first_name = name

    for filepath in files:
        dir_ = os.path.dirname(filepath)
        name = _ensure_session(cmds, existing, created, session_name(dir_), dir_)
        cmds.append(Command("tmux", ("send-keys", "-t", name, f"nvim '{filepath}'", "Enter")))
        if first_name is None:
            first_name = name

    if cmds:
        assert first_name is not None
        _post_step(cmds, in_tmux, tmux_server_running, first_name)

    return cmds
