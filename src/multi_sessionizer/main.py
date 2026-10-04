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
from .app.flows import (
    add_external_flow,
    delete_external_flow,
    interactive_flow,
    list_external_flow,
    session_flow,
    switch_flow,
)
from .app.ports import FlowDeps
from .infrastructure.classifier import PathSelectionClassifier
from .infrastructure.config_loader import FileConfigLoader
from .infrastructure.discovery import FileCandidateDiscovery
from .infrastructure.external_store import SqliteExternalStore
from .infrastructure.messages import (
    CONFIG_EXAMPLE,  # noqa: F401  (public re-export)
    ConsoleMessageOutput,
)
from .infrastructure.runner import Runner

USAGE = """\
usage: multi-sessionizer [-h] [--version]
                         [switch PATH ...] [session YAML ...]
                         [external add ENTRY | external list | external delete KEY]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]       open the given directories non-interactively
  session YAML [YAML ...]      provision the given inline tmuxp workspaces
  external add ENTRY           permanently add a directory / workspace / group
  external list                list externally added entries
  external delete KEY          delete an external entry by its key

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
    if first == "external":
        return "external", list(argv[1:])
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
        external_store=SqliteExternalStore(),
    )


def _external_dispatch(args: list[str], deps: FlowDeps | None = None) -> int:
    deps = deps or default_deps()
    if not args:
        print("multi-sessionizer: error: external requires a verb", file=sys.stderr)
        print("Try 'multi-sessionizer --help' for more information.", file=sys.stderr)
        return 2
    verb, rest = args[0], args[1:]
    if verb == "add":
        if not rest:
            print("multi-sessionizer: error: external add requires an ENTRY", file=sys.stderr)
            return 2
        return add_external_flow(rest[0], deps)
    if verb == "list":
        return list_external_flow(deps)
    if verb == "delete":
        if not rest:
            print("multi-sessionizer: error: external delete requires a KEY", file=sys.stderr)
            return 2
        return delete_external_flow(rest[0], deps)
    print(f"multi-sessionizer: error: unknown external command: {verb}", file=sys.stderr)
    print("Try 'multi-sessionizer --help' for more information.", file=sys.stderr)
    return 2


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

    if cmd == "external":
        return _external_dispatch(paths)

    return interactive_flow(default_deps())
