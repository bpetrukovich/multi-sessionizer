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

from .labels import parse_tags
from .models import SessionEntry
from .session_entries import classify_sessions
from .workspace import desired_name

_INVALID_ENTRY = (
    "Invalid 'external add' entry: expected a directory path, a workspace, or a named group."
)
_TAGS_TWICE = "Tags are specified both in the entry and via '--tags'."


def _strip_tags(data: dict) -> str:
    """Re-dump a workspace mapping without the ``tags`` key (deterministic)."""
    rest = {k: v for k, v in data.items() if k != "tags"}
    return yaml.safe_dump(rest, sort_keys=False, allow_unicode=True, width=1000)


def classify_external_input(
    arg: str, tags: Sequence[str] = ()
) -> tuple[SessionEntry | None, list[str]]:
    """Classify a single ``add`` argument (domain-contracts §classify_external_input).

    The argument is ``yaml.safe_load``-ed once:
    - a mapping with a non-empty ``windows`` list → **workspace** (verbatim,
      minus an optional top-level ``tags`` key, which tmuxp never sees);
    - a mapping with a string ``name`` + non-empty ``sessions`` → **group**
      (members validated like config — no nesting);
    - any other mapping → invalid (specific message);
    - a scalar string, or a value that fails to parse → **directory** (path).

    ``tags`` carries ``--tags`` CLI values. They apply to directory entries;
    for a YAML document they are rejected when the document also declares
    ``tags`` (ambiguous), otherwise they merge in.

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
            doc_tags, problem = parse_tags(data.get("tags"))
            if problem is not None:
                return None, [problem]
            if doc_tags and tags:
                return None, [_TAGS_TWICE]
            definition = arg if "tags" not in data else _strip_tags(data)
            return (
                SessionEntry(kind="workspace", definition=definition, tags=doc_tags or tuple(tags)),
                [],
            )
        name = data.get("name")
        sessions = data.get("sessions")
        if isinstance(name, str) and isinstance(sessions, list) and sessions:
            entries, problems = classify_sessions([data])
            if problems:
                return None, problems
            if len(entries) != 1 or entries[0].kind != "group":
                return None, [_INVALID_ENTRY]
            group = entries[0]
            if group.tags and tags:
                return None, [_TAGS_TWICE]
            return (
                SessionEntry(
                    kind="group",
                    name=group.name,
                    tags=group.tags or tuple(tags),
                    members=group.members,
                ),
                [],
            )
        return None, [_INVALID_ENTRY]

    if isinstance(data, str):
        return SessionEntry(kind="directory", path=data, tags=tuple(tags)), []

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
