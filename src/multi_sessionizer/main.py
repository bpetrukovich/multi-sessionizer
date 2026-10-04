"""Entry point: infrastructure CLI dispatch + composition root.

``main`` handles help/version/unknown output and dispatches to the app flows
(``switch_flow``, ``session_flow``, ``interactive_flow``) with a real
``FlowDeps`` built by ``default_deps``. ``_split_argv`` keeps its signature so
``test_main.py`` monkeypatching works unchanged.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from importlib import metadata

from . import __version__
from .app.flows import interactive_flow, session_flow, switch_flow
from .app.ports import FlowDeps
from .infrastructure.classifier import PathSelectionClassifier
from .infrastructure.config_loader import FileConfigLoader
from .infrastructure.discovery import FileCandidateDiscovery
from .infrastructure.messages import (
    CONFIG_EXAMPLE,  # noqa: F401  (public re-export)
    ConsoleMessageOutput,
)
from .infrastructure.runner import Runner

USAGE = """\
usage: multi-sessionizer [-h] [--version] [switch PATH ...] [session YAML ...]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]   open the given directories non-interactively
  session YAML [YAML ...]  provision the given inline tmuxp workspaces

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
    if first == "session":
        return "session", list(argv[1:])
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
        return switch_flow(paths, default_deps())

    if cmd == "session":
        return session_flow(paths, default_deps())

    return interactive_flow(default_deps())
