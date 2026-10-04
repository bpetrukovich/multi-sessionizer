"""App flows: pure composition of adapters and domain capabilities (FR-013/FR-014).

Each flow threads values between the injected ``FlowDeps`` adapters and the
domain. No business rules and no raw process/filesystem/environment/terminal
calls live here (US3). The interactive flow loads and classifies the unified
``sessions`` config (FR-001/FR-003), rejects removed keys and malformed groups
via ``ConfigError`` before any picker step (FR-002/FR-010), builds a unified
picker mixing directory paths, ``[tmuxp]`` workspace labels, and ``[group]``
group labels (FR-004), and expands a selected group into a flat domain
``Selection(dirs, workspaces)`` before the unchanged ``run_selection``
(FR-005/FR-006/FR-009, SC-001).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..domain.models import Selection, SessionEntry
from ..domain.rank import parse_zoxide_scores, rank_dirs
from ..domain.run import ProvisioningError, run
from ..domain.workspace import validate_workspace, workspace_label
from .configuration import ConfigError, ConfigNotFoundError
from .ports import FlowDeps


def run_selection(selection: Selection, deps: FlowDeps) -> int:
    snapshot = deps.probe.snapshot()
    try:
        run(selection, snapshot, deps.executor)
    except ProvisioningError as exc:
        deps.messages.error(str(exc))
        return 1
    return 0


def _disambiguated(
    candidates: Sequence[tuple[str, SessionEntry]],
) -> tuple[list[str], dict[str, SessionEntry]]:
    """Numeric-suffix duplicate display lines so every picker line is unique.

    Returns ``(items, line -> entry)``. A group name colliding with a directory
    path or a workspace label stays selectable (FR-009 edge case).
    """
    items: list[str] = []
    route: dict[str, SessionEntry] = {}
    counts: dict[str, int] = {}
    for display, entry in candidates:
        counts[display] = counts.get(display, 0) + 1
        line = display if counts[display] == 1 else f"{display}-{counts[display]}"
        items.append(line)
        route[line] = entry
    return items, route


def _group_display(entry: SessionEntry) -> str:
    return f"[group] {entry.name}"


def interactive_flow(deps: FlowDeps) -> int:
    try:
        cfg = deps.config_loader.load()
    except ConfigNotFoundError as exc:
        deps.messages.config_not_found(exc)
        return 1
    except ConfigError as exc:
        for msg in exc.messages:
            deps.messages.error(msg)
        return 1

    missing_dirs = deps.config_loader.missing_dirs(cfg)
    if missing_dirs:
        deps.messages.missing_dirs(missing_dirs)
        return 1

    discovered = deps.discovery.collect_dirs(cfg)
    scores = parse_zoxide_scores(deps.scorer.scores())
    top_level_dirs = [e.path for e in cfg.sessions if e.kind == "directory"]
    ranked = rank_dirs([*discovered, *top_level_dirs], scores)

    candidates: list[tuple[str, SessionEntry]] = []
    for path in ranked:
        candidates.append((path, SessionEntry(kind="directory", path=path)))
    for entry in cfg.sessions:
        if entry.kind == "workspace":
            candidates.append((workspace_label(entry.definition), entry))
        elif entry.kind == "group":
            candidates.append((_group_display(entry), entry))

    items, route = _disambiguated(candidates)
    selected = deps.picker.pick(items)
    if not selected:
        return 0

    dir_lines: list[str] = []
    workspace_defs: list[str] = []
    for line in selected:
        entry = route[line]
        if entry.kind == "directory":
            dir_lines.append(entry.path)
        elif entry.kind == "workspace":
            workspace_defs.append(entry.definition)
        else:  # group: expand members into a flat selection (FR-005/FR-006)
            for member in entry.members:
                if member.kind == "directory":
                    dir_lines.append(member.path)
                else:
                    workspace_defs.append(member.definition)

    classified = deps.classifier.classify_selection(dir_lines)
    selection = Selection(classified.dirs, tuple(workspace_defs))
    return run_selection(selection, deps)


def session_flow(paths: Sequence[str], deps: FlowDeps) -> int:
    problems: list[str] = []
    for definition in paths:
        problems.extend(validate_workspace(definition))
    if problems:
        deps.messages.workspace_problems(problems)
        return 1
    return run_selection(Selection((), tuple(paths)), deps)


def switch_flow(paths: Sequence[str], deps: FlowDeps) -> int:
    try:
        dirs, files = deps.classifier.classify_args(paths)
    except ValueError as exc:
        deps.messages.error(str(exc))
        return 1
    return run_selection(Selection(tuple(dirs), tuple(files)), deps)
