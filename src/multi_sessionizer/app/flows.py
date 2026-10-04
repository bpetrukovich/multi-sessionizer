"""App flows: pure composition of adapters and domain capabilities (FR-013/FR-014).

Each flow threads values between the injected ``FlowDeps`` adapters and the
domain. No business rules and no raw subprocess/filesystem/environment/terminal
calls live here (US3). The interactive flow validates every configured
workspace before the picker (FR-018), builds a ``label -> definition`` map
(R10), and splits selected ``[tmuxp]`` labels from directory paths before
classifying the remaining lines.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..domain.models import Selection
from ..domain.rank import parse_zoxide_scores, rank_dirs
from ..domain.run import ProvisioningError, run
from ..domain.workspace import picker_labels, validate_workspace
from .configuration import ConfigNotFoundError
from .ports import FlowDeps


def run_selection(selection: Selection, deps: FlowDeps) -> int:
    snapshot = deps.probe.snapshot()
    try:
        run(selection, snapshot, deps.executor)
    except ProvisioningError as exc:
        deps.messages.error(str(exc))
        return 1
    return 0


def interactive_flow(deps: FlowDeps) -> int:
    try:
        cfg = deps.config_loader.load()
    except ConfigNotFoundError as exc:
        deps.messages.config_not_found(exc)
        return 1

    problems: list[str] = []
    for definition in cfg.tmuxp_workspaces:
        problems.extend(validate_workspace(definition))
    if problems:
        deps.messages.workspace_problems(problems)
        return 1

    missing_dirs = deps.config_loader.missing_dirs(cfg)
    if missing_dirs:
        deps.messages.missing_dirs(missing_dirs)
        return 1

    dirs = deps.discovery.collect_dirs(cfg)
    scores = parse_zoxide_scores(deps.scorer.scores())
    labels = picker_labels(cfg.tmuxp_workspaces)
    label_map = dict(zip(labels, cfg.tmuxp_workspaces))
    items = [*rank_dirs(dirs, scores), *labels]
    selected = deps.picker.pick(items)
    if not selected:
        return 0

    workspace_defs: list[str] = []
    dir_lines: list[str] = []
    for line in selected:
        if line in label_map:
            workspace_defs.append(label_map[line])
        else:
            dir_lines.append(line)

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
