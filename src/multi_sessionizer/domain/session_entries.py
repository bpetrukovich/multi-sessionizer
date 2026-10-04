"""Pure unified-session classification and structural validation (FR-001/FR-003).

Classifies each element of the ``sessions`` config list by its shape and
validates group structure. Purely functional: PyYAML ``yaml.safe_load`` is the
only non-stdlib/pure facility — no process spawning, no filesystem, no environment
access, no realpath normalization, so ``tests/test_layer_boundaries.py`` stays
green. Directory existence is a separate infrastructure concern
(``missing_dirs``).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import yaml

from .models import SessionEntry

_INVALID_MEMBER_DETAIL = "expected a directory or workspace"


def is_workspace_definition(value: str) -> bool:
    """True when ``value`` parses to a mapping with a non-empty ``windows`` list."""
    try:
        data = yaml.safe_load(value)
    except yaml.YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    windows = data.get("windows")
    return isinstance(windows, list) and bool(windows)


def _looks_like_group(data: dict) -> bool:
    name = data.get("name")
    sessions = data.get("sessions")
    return isinstance(name, str) and isinstance(sessions, list) and bool(sessions)


def _classify_member(member: object, group_name: str) -> tuple[SessionEntry | None, str | None]:
    """Classify a single group member; returns (entry, problem) with one None."""
    if isinstance(member, str):
        if is_workspace_definition(member):
            return SessionEntry(kind="workspace", definition=member), None
        return SessionEntry(kind="directory", path=member), None
    if isinstance(member, dict):
        if _looks_like_group(member):
            return None, f"Nested groups are not supported: group '{member.get('name')}'."
        return None, f"Group '{group_name}' has an invalid member: {_INVALID_MEMBER_DETAIL}."
    return None, f"Group '{group_name}' has an invalid member: {_INVALID_MEMBER_DETAIL}."


def _classify_item(item: object) -> tuple[SessionEntry | None, list[str]]:
    """Classify one top-level element; returns (entry, problems) with one empty."""
    if isinstance(item, str):
        if is_workspace_definition(item):
            return SessionEntry(kind="workspace", definition=item), []
        return SessionEntry(kind="directory", path=item), []

    if isinstance(item, dict):
        name = item.get("name")
        if not isinstance(name, str):
            return None, ["Group is missing a 'name'."]
        sessions = item.get("sessions")
        if not (isinstance(sessions, list) and sessions):
            return None, [f"Group '{name}' has an empty 'sessions' list."]

        members: list[SessionEntry] = []
        problems: list[str] = []
        for member in sessions:
            entry, problem = _classify_member(member, name)
            if problem is not None:
                problems.append(problem)
            elif entry is not None:
                members.append(entry)
        if problems:
            return None, problems
        return SessionEntry(kind="group", name=name, members=tuple(members)), []

    return None, [
        f"Invalid 'sessions' element: expected a string or table, got {type(item).__name__}."
    ]


def classify_sessions(raw: Iterable[Any]) -> tuple[list[SessionEntry], list[str]]:
    """Classify and structurally validate every ``sessions`` element.

    Returns ``(entries, problems)``. Fully-valid elements yield an entry;
    invalid elements yield problem messages and no entry. A non-empty
    ``problems`` result means the config must be rejected (no session created).
    """
    entries: list[SessionEntry] = []
    problems: list[str] = []
    for item in raw:
        entry, item_problems = _classify_item(item)
        entries.extend([entry] if entry is not None else [])
        problems.extend(item_problems)
    return entries, problems
