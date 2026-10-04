"""Pure planning of the tmux/zoxide/tmuxp command sequence.

``plan`` turns a selection into an ordered list of :class:`Command` objects,
mirroring the branching logic of the original bash script:

- a single selection attaches/switches straight into that session;
- multiple selections create/reuse a session per spec and then run one
  post-step: attach to the first session (outside tmux, no server),
  ``choose-session`` (inside tmux) or a plain ``attach``.

The selection is expanded into a flat ordered collection of ``SessionSpec``\\ s
— directories first, then workspaces (FR-022). Directories keep today's
path-based decision byte-for-byte (SC-001): an existing session is reused only
when it belongs to the same directory, otherwise the name is disambiguated
with a numeric suffix (``dup``, ``dup-2``, ``dup-3``). Workspaces are decided
**by marker match only — never by session name** (FR-011/FR-013): a session
whose snapshot ``markers`` value equals the spec's fingerprint is switched to
under whatever name it has; otherwise a free name is resolved starting at the
desired name and the plan emits ``tmuxp load`` (with the authored definition as
``Command.input``) plus the marker ``set-option``.

Paths are compared **literally** (research R2): every path entering the domain
is already realpath-normalized at the infrastructure boundary, so literal
equality reproduces today's ``realpath(a) == realpath(b)`` comparison without
any filesystem access. ``os.path.dirname`` is a pure string helper.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import Command, CommandPlan, RuntimeSnapshot, Selection, SessionSpec
from .naming import session_name
from .workspace import desired_name, fingerprint


def _same_path(a: str, b: str) -> bool:
    return a == b


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


def _free_name(base: str, taken: set[str]) -> str:
    name = base
    index = 2
    while name in taken:
        name = f"{base}-{index}"
        index += 1
    return name


def _plan_workspace(
    cmds: list[Command],
    spec: SessionSpec,
    existing: Mapping[str, str],
    markers: Mapping[str, str],
    ws_by_fp: dict[str, str],
    created_dirs: dict[str, str],
) -> str:
    """Provision-or-reuse one workspace spec; returns the session to switch to."""
    # Marker check runs BEFORE name resolution (FR-011/FR-013): a session whose
    # marker matches is ours, whatever its name; a foreign session with a
    # colliding name is never adopted.
    for name, fp in markers.items():
        if fp == spec.fingerprint:
            return name
    if spec.fingerprint in ws_by_fp:
        return ws_by_fp[spec.fingerprint]

    taken = set(existing) | set(ws_by_fp.values()) | set(created_dirs)
    name = _free_name(spec.desired_name, taken)
    cmds.append(
        Command("tmuxp", ("load", "-d", "--no-progress", "-s", name), input=spec.definition)
    )
    cmds.append(
        Command("tmux", ("set-option", "-t", name, "@multi-sessionizer-marker", spec.fingerprint))
    )
    ws_by_fp[spec.fingerprint] = name
    return name


def _expand_specs(selection: Selection) -> list[SessionSpec]:
    specs: list[SessionSpec] = []
    for d in selection.dirs:
        specs.append(SessionSpec(kind="directory", path=d))
    for definition in selection.workspaces:
        specs.append(
            SessionSpec(
                kind="workspace",
                definition=definition,
                fingerprint=fingerprint(definition),
                desired_name=desired_name(definition),
            )
        )
    return specs


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


def plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan:
    specs = _expand_specs(selection)
    existing = snapshot.existing
    markers = snapshot.markers
    created_dirs: dict[str, str] = {}
    ws_by_fp: dict[str, str] = {}
    cmds: list[Command] = []

    if len(specs) == 1:
        spec = specs[0]
        if spec.kind == "directory":
            name = _ensure_session(cmds, existing, created_dirs, session_name(spec.path), spec.path)
            _attach_single(cmds, snapshot.in_tmux, name)
            return CommandPlan(cmds)
        name = _plan_workspace(cmds, spec, existing, markers, ws_by_fp, created_dirs)
        _attach_single(cmds, snapshot.in_tmux, name)
        return CommandPlan(cmds)

    first_name: str | None = None
    for spec in specs:
        if spec.kind == "directory":
            name = _ensure_session(cmds, existing, created_dirs, session_name(spec.path), spec.path)
        else:
            name = _plan_workspace(cmds, spec, existing, markers, ws_by_fp, created_dirs)
        if first_name is None:
            first_name = name

    if cmds:
        assert first_name is not None
        _post_step(cmds, snapshot.in_tmux, snapshot.tmux_server_running, first_name)

    return CommandPlan(cmds)


def plan_legacy(
    dirs: Iterable[str],
    files: Iterable[str],
    *,
    in_tmux: bool,
    tmux_server_running: bool,
    existing: Mapping[str, str] | None = None,
) -> CommandPlan:
    """Pure compatibility wrapper: positions arguments into DTOs and delegates.

    Kept so the existing directory-related test calls stay byte-identical
    (SC-001). The file feature is removed: a non-empty ``files`` argument is a
    program error.
    """
    files = tuple(files)
    if files:
        raise ValueError("File paths are not supported.")
    selection = Selection(tuple(dirs), files)
    snapshot = RuntimeSnapshot(
        in_tmux=in_tmux,
        tmux_server_running=tmux_server_running,
        existing=existing if existing is not None else {},
    )
    return plan(selection, snapshot)
