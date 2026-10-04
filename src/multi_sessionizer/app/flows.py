"""App flows: pure composition of adapters and domain capabilities (FR-013/FR-014).

Each flow threads values between the injected ``FlowDeps`` adapters and the
domain. No business rules and no raw subprocess/filesystem/environment/terminal
calls live here (US3).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..domain.models import Selection
from ..domain.rank import build_picker_list, parse_zoxide_scores
from ..domain.run import run
from .configuration import ConfigNotFoundError
from .ports import FlowDeps


def run_selection(selection: Selection, deps: FlowDeps) -> int:
    snapshot = deps.probe.snapshot()
    run(selection, snapshot, deps.executor)
    return 0


def interactive_flow(deps: FlowDeps) -> int:
    try:
        cfg = deps.config_loader.load()
    except ConfigNotFoundError as exc:
        deps.messages.config_not_found(exc)
        return 1

    missing_files = deps.config_loader.missing_files(cfg)
    missing_dirs = deps.config_loader.missing_dirs(cfg)
    if missing_files or missing_dirs:
        deps.messages.missing_paths(missing_files, missing_dirs)
        return 1

    dirs = deps.discovery.collect_dirs(cfg)
    files = deps.discovery.collect_files(cfg)
    scores = parse_zoxide_scores(deps.scorer.scores())
    items = build_picker_list(dirs, scores, files)
    selected = deps.picker.pick(items)
    if not selected:
        return 0

    selection = deps.classifier.classify_selection(selected)
    return run_selection(selection, deps)


def switch_flow(paths: Sequence[str], deps: FlowDeps) -> int:
    dirs, files = deps.classifier.classify_args(paths)
    return run_selection(Selection(tuple(dirs), tuple(files)), deps)
