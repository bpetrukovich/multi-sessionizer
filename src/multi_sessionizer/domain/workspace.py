"""Pure workspace capability (FR-005/FR-018/FR-022, research R4/R6/R10/R11).

Parses, validates, fingerprints, and labels authored tmuxp workspace
definitions. Purely functional: PyYAML ``yaml.safe_load`` and ``hashlib`` are
the only non-stdlib/pure facilities — no process spawning, no filesystem, no
environment access, no realpath normalization, so
``tests/test_layer_boundaries.py`` stays green. The authored definition string
is the identity (R3): env/``~`` expansion never happens here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

import yaml

from .labels import render_picker_line
from .naming import workspace_fallback_name


@dataclass(frozen=True)
class Workspace:
    """The pure parsed view of an authored definition (data-model §1.9)."""

    definition: str
    session_name: str | None
    start_directory: str | None
    windows: list[object]
    problems: tuple[str, ...] = ()


def parse_workspace(definition: str) -> Workspace:
    """Parse a definition, collecting validation problems instead of raising."""
    problems: list[str] = []
    try:
        data = yaml.safe_load(definition)
    except yaml.YAMLError as exc:
        return Workspace(definition, None, None, [], (str(exc),))

    if not isinstance(data, dict):
        problems.append("Workspace root must be a mapping (a YAML object).")
        return Workspace(definition, None, None, [], tuple(problems))

    windows = data.get("windows")
    if windows is None:
        problems.append("Workspace is missing the 'windows' key.")
    elif not isinstance(windows, list):
        problems.append("The 'windows' key must be a list.")
    elif not windows:
        problems.append("The 'windows' list must not be empty.")

    session_name = data.get("session_name")
    if session_name is not None and not isinstance(session_name, str):
        problems.append("The 'session_name' key must be a string.")

    start_directory = data.get("start_directory")
    if start_directory is not None and not isinstance(start_directory, str):
        problems.append("The 'start_directory' key must be a string.")

    return Workspace(
        definition=definition,
        session_name=session_name if isinstance(session_name, str) else None,
        start_directory=start_directory if isinstance(start_directory, str) else None,
        windows=windows if isinstance(windows, list) else [],
        problems=tuple(problems),
    )


def validate_workspace(definition: str) -> list[str]:
    """Report structural problems for a definition; empty list means valid."""
    return list(parse_workspace(definition).problems)


def fingerprint(definition: str) -> str:
    """Entry identity: sha256 over the authored bytes (R3)."""
    return hashlib.sha256(definition.encode()).hexdigest()


def desired_name(definition: str) -> str:
    """Declared ``session_name`` or the deterministic fallback (R11)."""
    workspace = parse_workspace(definition)
    if workspace.session_name:
        return workspace.session_name
    return workspace_fallback_name(fingerprint(definition))


def workspace_label(definition: str) -> str:
    """Picker line for a workspace entry: ``[tmuxp] <desired_name>`` (R10)."""
    return render_picker_line(("tmuxp",), desired_name(definition))


def picker_labels(definitions: Iterable[str]) -> list[str]:
    """Disambiguated display labels, one per definition, in input order (R10).

    Duplicate displayed names get a numeric suffix (``[tmuxp] foo``,
    ``[tmuxp] foo-2``, ...) so each picker line is unique; the flow zips these
    back with the definitions to recover the label -> definition map.
    """
    labels: list[str] = []
    counts: dict[str, int] = {}
    for definition in definitions:
        base = workspace_label(definition)
        counts[base] = counts.get(base, 0) + 1
        labels.append(base if counts[base] == 1 else f"{base}-{counts[base]}")
    return labels
