"""Unit tests for the pure unified-session classifier (FR-003/FR-007/FR-008/FR-011).

Exercises ``classify_sessions`` and ``is_workspace_definition`` with hand-built
values — no filesystem, no subprocess, no environment.
"""

from __future__ import annotations

from multi_sessionizer.domain.models import SessionEntry
from multi_sessionizer.domain.session_entries import (
    classify_sessions,
    is_workspace_definition,
)

WS_DEF = "session_name: myws\nwindows:\n  - shell_command: vim\n"


def _entry(**kw):
    return SessionEntry(**kw)


# --- is_workspace_definition (T004) ---


def test_is_workspace_definition_mapping_with_windows():
    assert is_workspace_definition("session_name: x\nwindows:\n  - shell_command: vim\n")


def test_is_workspace_definition_directory_like_string_is_false():
    assert not is_workspace_definition("/home/u/proj")


def test_is_workspace_definition_non_mapping_yaml_is_false():
    assert not is_workspace_definition("just a plain string")
    assert not is_workspace_definition("[1, 2, 3]")
    assert not is_workspace_definition("42")


def test_is_workspace_definition_empty_windows_is_false():
    assert not is_workspace_definition("session_name: x\nwindows: []\n")


def test_is_workspace_definition_invalid_yaml_is_false():
    assert not is_workspace_definition(": : : not yaml")


def test_is_workspace_definition_missing_windows_key_is_false():
    assert not is_workspace_definition("session_name: x\n")


# --- classify_sessions (T003) ---


def test_classify_directory_string():
    entries, problems = classify_sessions(["/home/u/proj"])
    assert problems == []
    assert entries == [_entry(kind="directory", path="/home/u/proj")]


def test_classify_workspace_string():
    entries, problems = classify_sessions([WS_DEF])
    assert problems == []
    assert entries == [_entry(kind="workspace", definition=WS_DEF)]


def test_classify_group_table():
    entries, problems = classify_sessions([{"name": "stack", "sessions": ["/tmp/a", WS_DEF]}])
    assert problems == []
    assert len(entries) == 1
    group = entries[0]
    assert group.kind == "group"
    assert group.name == "stack"
    assert group.members == (
        _entry(kind="directory", path="/tmp/a"),
        _entry(kind="workspace", definition=WS_DEF),
    )


def test_classify_mixed_top_level():
    entries, problems = classify_sessions(["/tmp/a", WS_DEF, {"name": "g", "sessions": ["/tmp/b"]}])
    assert problems == []
    assert [e.kind for e in entries] == ["directory", "workspace", "group"]


def test_classify_group_missing_name_is_problem():
    entries, problems = classify_sessions([{"sessions": ["/tmp/a"]}])
    assert entries == []
    assert problems == ["Group is missing a 'name'."]


def test_classify_group_name_not_string_is_problem():
    entries, problems = classify_sessions([{"name": 7, "sessions": ["/tmp/a"]}])
    assert entries == []
    assert problems == ["Group is missing a 'name'."]


def test_classify_group_empty_sessions_is_problem():
    entries, problems = classify_sessions([{"name": "g", "sessions": []}])
    assert entries == []
    assert problems == ["Group 'g' has an empty 'sessions' list."]


def test_classify_group_missing_sessions_is_problem():
    entries, problems = classify_sessions([{"name": "g"}])
    assert entries == []
    assert problems == ["Group 'g' has an empty 'sessions' list."]


def test_classify_nested_group_member_is_problem():
    entries, problems = classify_sessions(
        [{"name": "outer", "sessions": ["/tmp/a", {"name": "inner", "sessions": ["/tmp/b"]}]}]
    )
    assert entries == []
    assert problems == ["Nested groups are not supported: group 'inner'."]


def test_classify_group_invalid_member_table_is_problem():
    entries, problems = classify_sessions([{"name": "g", "sessions": [{"foo": 1}]}])
    assert entries == []
    assert problems == ["Group 'g' has an invalid member: expected a directory or workspace."]


def test_classify_group_invalid_member_scalar_is_problem():
    entries, problems = classify_sessions([{"name": "g", "sessions": [42]}])
    assert entries == []
    assert problems == ["Group 'g' has an invalid member: expected a directory or workspace."]


def test_classify_non_string_non_table_element_is_problem():
    entries, problems = classify_sessions([42])
    assert entries == []
    assert problems == ["Invalid 'sessions' element: expected a string or table, got int."]


def test_classify_multiple_problems_collected():
    entries, problems = classify_sessions(
        [
            {"sessions": ["/tmp/a"]},
            {"name": "g", "sessions": []},
            {"name": "o", "sessions": [{"name": "i", "sessions": ["/tmp/x"]}]},
        ]
    )
    assert entries == []
    assert problems == [
        "Group is missing a 'name'.",
        "Group 'g' has an empty 'sessions' list.",
        "Nested groups are not supported: group 'i'.",
    ]


def test_classify_empty_input():
    entries, problems = classify_sessions([])
    assert entries == []
    assert problems == []
