"""Pure workspace capability tests (US1, FR-018/FR-022, research R4/R6/R10/R11).

These tests exercise ``domain/workspace.py`` with no external tools, no
``TMUX`` env var, and no real execution (quickstart step 2).
"""

from __future__ import annotations

from multi_sessionizer.domain.workspace import (
    desired_name,
    fingerprint,
    parse_workspace,
    validate_workspace,
    workspace_label,
)

NAMED = "session_name: myws\nwindows:\n  - shell_command: vim\n"
ANON = "windows:\n  - shell_command: vim\n"
VALID_SINGLE_WINDOW = "session_name: single\nwindows:\n  - shell_command: ls\n"


def test_fingerprint_is_deterministic():
    assert fingerprint(NAMED) == fingerprint(NAMED)
    assert isinstance(fingerprint(NAMED), str)
    assert len(fingerprint(NAMED)) == 64


def test_fingerprint_is_name_independent():
    # The fingerprint hashes the authored definition only (R3): a session-name
    # collision forces a numeric suffix on the NAME, never a new fingerprint,
    # so the marker stays stable even after a disambiguated creation.
    fp = fingerprint(ANON)
    assert fp == fingerprint(ANON)
    assert desired_name(ANON) == f"msz-{fp[:12]}"


def test_fingerprint_differs_across_definitions():
    assert fingerprint(NAMED) != fingerprint(ANON)


def test_validate_accepts_valid_single_window_workspace():
    assert validate_workspace(VALID_SINGLE_WINDOW) == []


def test_validate_rejects_invalid_yaml():
    problems = validate_workspace("windows: [\n")
    assert problems


def test_validate_rejects_non_mapping_root():
    problems = validate_workspace("- a\n- list\n")
    assert any("mapping" in p for p in problems)
    assert validate_workspace("just a scalar\n")


def test_validate_rejects_missing_windows():
    problems = validate_workspace("session_name: x\n")
    assert any("windows" in p for p in problems)


def test_validate_rejects_non_list_windows():
    problems = validate_workspace("windows: 42\n")
    assert any("list" in p for p in problems)


def test_validate_rejects_empty_windows():
    problems = validate_workspace("windows: []\n")
    assert any("empty" in p or "windows" in p for p in problems)


def test_validate_rejects_non_string_session_name():
    problems = validate_workspace("session_name: 42\nwindows:\n  - shell_command: vim\n")
    assert any("session_name" in p for p in problems)


def test_desired_name_honors_declared_session_name():
    assert desired_name(NAMED) == "myws"


def test_desired_name_falls_back_to_msz_fingerprint():
    fallback = desired_name(ANON)
    assert fallback == f"msz-{fingerprint(ANON)[:12]}"
    assert fallback.startswith("msz-")


def test_workspace_label_declared_name():
    assert workspace_label(NAMED) == "[tmuxp] myws"


def test_workspace_label_fallback_name():
    assert workspace_label(ANON) == f"[tmuxp] msz-{fingerprint(ANON)[:12]}"


def test_parse_workspace_extracts_fields():
    ws = parse_workspace(NAMED)
    assert ws.session_name == "myws"
    assert ws.windows == [{"shell_command": "vim"}]
    assert ws.problems == ()
