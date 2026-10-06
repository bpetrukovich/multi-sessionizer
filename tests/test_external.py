"""Unit tests for the pure external domain rules (FR-005/FR-008/FR-009/FR-015).

Covers ``classify_external_input``, ``deletion_key``, and ``resolve_delete`` in
``multi_sessionizer/domain/external.py`` — pure (stdlib + PyYAML), so no
subprocess/filesystem/environment side effects and no realpath normalization.
"""

from __future__ import annotations

from multi_sessionizer.domain.external import (
    classify_external_input,
    deletion_key,
    resolve_delete,
)
from multi_sessionizer.domain.models import SessionEntry
from multi_sessionizer.domain.workspace import desired_name

DIR = "/home/u/tmp/msz-proj-a"
WS = 'session_name: "ext-ws"\nwindows:\n  - shell_command: "echo hi"\n'
GRP_WS = 'session_name: "ext-svc"\nwindows:\n  - shell_command: "echo svc"'
GRP = (
    "name: ext-stack\n"
    "sessions:\n"
    "  - /home/u/tmp/msz-proj-b\n"
    "  - |-\n"
    '    session_name: "ext-svc"\n'
    "    windows:\n"
    '      - shell_command: "echo svc"\n'
)


def dir_entry(path):
    return SessionEntry(kind="directory", path=path)


def ws_entry(definition=WS):
    return SessionEntry(kind="workspace", definition=definition)


def group_entry(name, members):
    return SessionEntry(kind="group", name=name, members=tuple(members))


# --- classify_external_input -------------------------------------------------


def test_classify_workspace_from_nonempty_windows_mapping():
    entry, problems = classify_external_input(WS)
    assert problems == []
    assert entry == ws_entry(WS)


def test_classify_group_from_string_name_and_nonempty_sessions():
    entry, problems = classify_external_input(GRP)
    assert problems == []
    assert entry == group_entry(
        "ext-stack",
        [dir_entry("/home/u/tmp/msz-proj-b"), ws_entry(GRP_WS)],
    )


def test_classify_any_other_mapping_is_invalid():
    entry, problems = classify_external_input("foo: bar\nbaz: 1\n")
    assert entry is None
    assert len(problems) == 1


def test_classify_scalar_string_is_directory():
    entry, problems = classify_external_input(DIR)
    assert problems == []
    assert entry == dir_entry(DIR)


def test_classify_yaml_parse_failure_is_directory():
    entry, problems = classify_external_input('"unterminated')
    assert problems == []
    assert entry == dir_entry('"unterminated')


def test_classify_invalid_group_member_is_rejected():
    entry, problems = classify_external_input(
        "name: g\nsessions:\n  - name: inner\n    sessions:\n      - /a\n"
    )
    assert entry is None
    assert problems


def test_classify_group_with_tags():
    entry, problems = classify_external_input(
        "name: ext-stack\ntags:\n  - pp-000000\nsessions:\n  - /home/u/tmp/msz-proj-b\n"
    )
    assert problems == []
    assert entry == SessionEntry(
        kind="group",
        name="ext-stack",
        tags=("pp-000000",),
        members=(dir_entry("/home/u/tmp/msz-proj-b"),),
    )


def test_classify_workspace_with_tags_strips_tags_from_definition():
    doc = 'session_name: "ext-ws"\ntags: [pp-1]\nwindows:\n  - shell_command: "echo hi"\n'
    entry, problems = classify_external_input(doc)
    assert problems == []
    assert entry.kind == "workspace"
    assert entry.tags == ("pp-1",)
    assert "tags" not in entry.definition
    assert "session_name: ext-ws" in entry.definition


def test_classify_workspace_without_tags_keeps_definition_verbatim():
    entry, problems = classify_external_input(WS)
    assert problems == []
    assert entry.kind == "workspace"
    assert entry.definition == WS
    assert entry.tags == ()


def test_classify_directory_with_cli_tags():
    entry, problems = classify_external_input(DIR, tags=("pp-000000",))
    assert problems == []
    assert entry == SessionEntry(kind="directory", path=DIR, tags=("pp-000000",))


def test_classify_document_and_cli_tags_conflict():
    doc = 'name: g\ntags: [pp-1]\nsessions:\n  - /a\n'
    entry, problems = classify_external_input(doc, tags=("pp-2",))
    assert entry is None
    assert problems == ["Tags are specified both in the entry and via '--tags'."]


def test_classify_workspace_invalid_tags_rejected():
    doc = 'session_name: "ext-ws"\ntags: [pp 1]\nwindows:\n  - shell_command: "echo hi"\n'
    entry, problems = classify_external_input(doc)
    assert entry is None
    assert problems
    assert "Invalid tag" in problems[0]


# --- deletion_key -------------------------------------------------------------


def test_deletion_key_directory_is_realpath_normalized_path():
    assert deletion_key(dir_entry("/x/y")) == "/x/y"


def test_deletion_key_workspace_is_desired_name():
    assert deletion_key(ws_entry(WS)) == desired_name(WS)


def test_deletion_key_group_is_name():
    assert deletion_key(group_entry("ext-stack", [])) == "ext-stack"


# --- resolve_delete -----------------------------------------------------------


def test_resolve_delete_zero_matches():
    matches, problems = resolve_delete([dir_entry("/a")], "nope")
    assert matches == []
    assert problems == ["No external entry with deletion key 'nope'."]


def test_resolve_delete_single_match():
    entry = ws_entry()
    matches, problems = resolve_delete([dir_entry("/a"), entry], deletion_key(entry))
    assert matches == [entry]
    assert problems == []


def test_resolve_delete_ambiguous_two_workspaces_share_session_name():
    ws1 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: one\n')
    ws2 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: two\n')
    matches, problems = resolve_delete([ws1, ws2], "shared")
    assert matches == [ws1, ws2]
    assert len(problems) == 1
    assert "matches multiple entries" in problems[0]
