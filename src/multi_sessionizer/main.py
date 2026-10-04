"""Entry point: infrastructure CLI dispatch + composition root.

``main`` handles help/version/unknown output and the switch branch (classifying
via the classifier), then delegates to the app flows with a real ``FlowDeps``
built by ``default_deps``. ``_run`` and ``_split_argv`` keep their signatures so
``test_main.py`` monkeypatching works unchanged.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib import metadata

from . import __version__
from .app.flows import interactive_flow, run_selection
from .app.ports import FlowDeps
from .domain.models import Selection
from .infrastructure.classifier import PathSelectionClassifier
from .infrastructure.config_loader import FileConfigLoader
from .infrastructure.discovery import FileCandidateDiscovery
from .infrastructure.messages import (
    CONFIG_EXAMPLE,  # noqa: F401  (public re-export)
    ConsoleMessageOutput,
)
from .infrastructure.runner import Runner

USAGE = """\
usage: multi-sessionizer [-h] [--version] [switch PATH ...]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]   open the given directories/files non-interactively

options:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
"""


def _package_version() -> str:
    try:
        return metadata.version("multi-sessionizer")
    except metadata.PackageNotFoundError:
        return __version__


def _split_argv(argv: Sequence[str]) -> tuple[str | None, list[str]]:
    """Return (command, paths) based on the first token."""
    if not argv:
        return None, []
    first = argv[0]
    if first in ("-h", "--help"):
        return "help", []
    if first == "--version":
        return "version", []
    if first == "switch":
        return "switch", list(argv[1:])
    return "unknown", list(argv)


def default_deps() -> FlowDeps:
    """Composition root: one real ``Runner`` satisfies every subprocess port."""
    runner = Runner()
    return FlowDeps(
        config_loader=FileConfigLoader(),
        discovery=FileCandidateDiscovery(),
        scorer=runner,
        picker=runner,
        classifier=PathSelectionClassifier(),
        probe=runner,
        executor=runner,
        messages=ConsoleMessageOutput(),
    )


def _run(dirs: list[str], files: list[str]) -> int:
    selection = Selection(tuple(dirs), tuple(files))
    return run_selection(selection, default_deps())


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd, paths = _split_argv(argv)

    if cmd == "help":
        print(USAGE, end="")
        return 0

    if cmd == "version":
        print(f"multi-sessionizer {_package_version()}")
        return 0

    if cmd == "unknown":
        print(f"multi-sessionizer: error: unknown command: {paths[0]}", file=sys.stderr)
        print("Try 'multi-sessionizer --help' for more information.", file=sys.stderr)
        return 2

    if cmd == "switch":
        deps = default_deps()
        try:
            dirs, files = deps.classifier.classify_args(paths)
        except ValueError as exc:
            deps.messages.error(str(exc))
            return 1
        return _run(dirs, files)

    return interactive_flow(default_deps())
