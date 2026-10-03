"""Pure planning of the tmux/zoxide command sequence.

``plan`` turns a selection into an ordered list of :class:`Command` objects,
mirroring the branching logic of the original bash script:

- a single selection attaches/switches straight into that session;
- multiple selections create/reuse a session per path and then run one
  post-step: attach to the first session (outside tmux, no server),
  ``choose-session`` (inside tmux) or a plain ``attach``.

Directories are processed before files. Session creation decisions are made
from a snapshot of already-existing sessions plus the sessions created earlier
in the same plan (so duplicate basenames reuse one session).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .naming import session_name


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]

    def argv(self) -> list[str]:
        return [self.program, *self.args]


def _ensure_session(
    cmds: list[Command],
    existing: set[str],
    created: set[str],
    name: str,
    cwd: str,
) -> None:
    cmds.append(Command("zoxide", ("add", cwd)))
    if name not in existing and name not in created:
        cmds.append(Command("tmux", ("new-session", "-ds", name, "-c", cwd)))
        created.add(name)


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


def _first_name(dirs: Sequence[str], files: Sequence[str]) -> str:
    if dirs:
        return session_name(dirs[0])
    return session_name(os.path.dirname(files[0]))


def plan(
    dirs: Iterable[str],
    files: Iterable[str],
    *,
    in_tmux: bool,
    tmux_server_running: bool,
    existing: Iterable[str] = (),
) -> list[Command]:
    dirs = list(dirs)
    files = list(files)
    existing = set(existing)
    created: set[str] = set()
    cmds: list[Command] = []

    if len(dirs) == 1 and not files:
        name = session_name(dirs[0])
        _ensure_session(cmds, existing, created, name, dirs[0])
        _attach_single(cmds, in_tmux, name)
        return cmds

    if len(files) == 1 and not dirs:
        filepath = files[0]
        dir_ = os.path.dirname(filepath)
        name = session_name(dir_)
        _ensure_session(cmds, existing, created, name, dir_)
        cmds.append(Command("tmux", ("send-keys", "-t", name, f"nvim '{filepath}'", "Enter")))
        _attach_single(cmds, in_tmux, name)
        return cmds

    for dir_ in dirs:
        _ensure_session(cmds, existing, created, session_name(dir_), dir_)

    for filepath in files:
        dir_ = os.path.dirname(filepath)
        name = session_name(dir_)
        _ensure_session(cmds, existing, created, name, dir_)
        cmds.append(Command("tmux", ("send-keys", "-t", name, f"nvim '{filepath}'", "Enter")))

    if cmds:
        _post_step(cmds, in_tmux, tmux_server_running, _first_name(dirs, files))

    return cmds
