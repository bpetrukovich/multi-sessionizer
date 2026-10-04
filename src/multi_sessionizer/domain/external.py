"""Pure external-entry rules (FR-005/FR-008/FR-009/FR-015).

Classifies a single ``external add`` argument into a ``SessionEntry`` (or
specific problems), computes the user-facing deletion key, and resolves a
delete request with a precise-match rule. Purely functional: PyYAML
``yaml.safe_load`` is the only non-stdlib/pure facility — no process
spawning, filesystem, environment access, or realpath normalization, so
``tests/test_layer_boundaries.py`` stays green.
"""

from __future__ import annotations

from collections.abc import Sequence

import yaml

from .models import SessionEntry
from .session_entries import classify_sessions
from .workspace import desired_name

_INVALID_ENTRY = (
    "Invalid 'external add' entry: expected a directory path, a workspace, or a named group."
)


def classify_external_input(arg: str) -> tuple[SessionEntry | None, list[str]]:
    """Classify a single ``add`` argument (domain-contracts §classify_external_input).

    The argument is ``yaml.safe_load``-ed once:
    - a mapping with a non-empty ``windows`` list → **workspace** (verbatim);
    - a mapping with a string ``name`` + non-empty ``sessions`` → **group**
      (members validated like config — no nesting);
    - any other mapping → invalid (specific message);
    - a scalar string, or a value that fails to parse → **directory** (path).

    Returns ``(entry, problems)``; an invalid value returns ``(None, problems)``
    and must not be stored (FR-015).
    """
    try:
        data = yaml.safe_load(arg)
    except yaml.YAMLError:
        data = arg  # unparseable → treated as a directory path string

    if isinstance(data, dict):
        windows = data.get("windows")
        if isinstance(windows, list) and windows:
            return SessionEntry(kind="workspace", definition=arg), []
        name = data.get("name")
        sessions = data.get("sessions")
        if isinstance(name, str) and isinstance(sessions, list) and sessions:
            entries, problems = classify_sessions([data])
            if problems:
                return None, problems
            if len(entries) != 1 or entries[0].kind != "group":
                return None, [_INVALID_ENTRY]
            return entries[0], []
        return None, [_INVALID_ENTRY]

    if isinstance(data, str):
        return SessionEntry(kind="directory", path=data), []

    return None, [_INVALID_ENTRY]


def deletion_key(entry: SessionEntry) -> str:
    """User-facing key used to delete and listed per entry (FR-008/FR-009)."""
    if entry.kind == "workspace":
        return desired_name(entry.definition)
    if entry.kind == "directory":
        return entry.path
    return entry.name


def resolve_delete(
    entries: Sequence[SessionEntry], key: str
) -> tuple[list[SessionEntry], list[str]]:
    """Resolve a delete request (precise-match rule, FR-009/FR-010).

    Returns ``(matches, problems)``:
    - 0 matches → ``([], ["No external entry with deletion key '<key>'."])``;
    - exactly 1 match → ``([entry], [])``;
    - >1 matches → the matches plus an ambiguous message — none is removed.
    """
    matches = [entry for entry in entries if deletion_key(entry) == key]
    if not matches:
        return [], [f"No external entry with deletion key '{key}'."]
    if len(matches) == 1:
        return matches, []
    keys = ", ".join(deletion_key(e) for e in matches)
    return matches, [f"External delete key '{key}' matches multiple entries: {keys}."]
