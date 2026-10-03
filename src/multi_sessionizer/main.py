"""Entry point: wires configuration, pure planning and the runner together."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

from . import config as config_mod
from . import decisions
from . import runner as runner_mod
from .cli import classify_args
from .discovery import collect_dirs, collect_files
from .rank import build_picker_list, parse_zoxide_scores

CONFIG_EXAMPLE = """\
project_roots_depth_1 = ["$HOME"]
project_roots_depth_2 = ["$HOME/work"]
additional_dirs = ["$HOME/Documents", "$HOME/Projects"]
additional_files = ["$HOME/.bashrc"]
"""


def _config_not_found(path: object) -> int:
    print(f"Configuration file not found: {path}", file=sys.stderr)
    print(file=sys.stderr)
    print("Create it with an example:", file=sys.stderr)
    print(CONFIG_EXAMPLE, file=sys.stderr, end="")
    print(
        "The path can be overridden with the MULTI_SESSIONIZER_CONFIG environment variable.",
        file=sys.stderr,
    )
    return 1


def _run(dirs: list[str], files: list[str]) -> int:
    runner = runner_mod.Runner()
    in_tmux = bool(os.environ.get("TMUX"))
    existing = runner.existing_sessions()
    cmds = decisions.plan(
        dirs,
        files,
        in_tmux=in_tmux,
        tmux_server_running=runner.tmux_running(),
        existing=existing,
    )
    runner.execute(cmds)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv:
        try:
            dirs, files = classify_args(argv)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return _run(dirs, files)

    try:
        cfg = config_mod.load_config()
    except config_mod.ConfigNotFoundError as exc:
        return _config_not_found(exc)

    missing_files = config_mod.missing_files(cfg)
    missing_dirs = config_mod.missing_dirs(cfg)
    if missing_files or missing_dirs:
        if missing_files:
            print("The following files do not exist:", file=sys.stderr)
            for path in missing_files:
                print(f"  {path}", file=sys.stderr)
        if missing_dirs:
            print("The following directories do not exist:", file=sys.stderr)
            for path in missing_dirs:
                print(f"  {path}", file=sys.stderr)
        return 1

    runner = runner_mod.Runner()
    scores = parse_zoxide_scores(runner.zoxide_scores())
    items = build_picker_list(collect_dirs(cfg), scores, collect_files(cfg))
    selected = runner.run_fzf(items)
    if not selected:
        return 0

    dirs: list[str] = []
    files: list[str] = []
    for path in selected:
        (files if os.path.isfile(path) else dirs).append(path)

    return _run(dirs, files)
