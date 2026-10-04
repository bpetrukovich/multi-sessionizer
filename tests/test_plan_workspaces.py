"""Workspace planning tests (US1/US3, FR-010..FR-014/FR-017, research R5/R12).

Pure domain tests: ``plan`` is exercised with hand-built DTOs — marker-based
reuse, foreign-session safety, disambiguation, restart statelessness, and the
single-plan/single-post-step shape for mixed selections. No external tools, no
real execution.
"""

from __future__ import annotations

from multi_sessionizer.domain.models import Command, CommandPlan, RuntimeSnapshot, Selection
from multi_sessionizer.domain.plan import plan
from multi_sessionizer.domain.workspace import fingerprint, picker_labels

NAMED_ONE = "session_name: myws\nwindows:\n  - shell_command: vim\n"
NAMED_TWO = "session_name: myws\nwindows:\n  - shell_command: ls\n"
ANON = "windows:\n  - shell_command: vim\n"


def cmd(program, *args, input=None):
    return Command(program, args, input=input)


def snapshot(*, in_tmux=False, tmux_server_running=False, existing=None, markers=None):
    return RuntimeSnapshot(
        in_tmux=in_tmux,
        tmux_server_running=tmux_server_running,
        existing=existing if existing is not None else {},
        markers=markers if markers is not None else {},
    )


def ws_commands(name, definition):
    fp = fingerprint(definition)
    return [
        cmd("tmuxp", "load", "-d", "--no-progress", "-s", name, input=definition),
        cmd("tmux", "set-option", "-t", name, "@multi-sessionizer-marker", fp),
    ]


def test_single_new_workspace_provisions_and_attaches():
    fp = fingerprint(NAMED_ONE)
    selection = Selection((), (NAMED_ONE,))
    snap = snapshot(tmux_server_running=False)
    assert plan(selection, snap) == CommandPlan(
        [
            *ws_commands("myws", NAMED_ONE),
            cmd("tmux", "attach", "-t", "myws"),
        ]
    )
    assert fp


def test_single_workspace_reuse_emits_no_tmuxp_no_set_option():
    fp = fingerprint(NAMED_ONE)
    selection = Selection((), (NAMED_ONE,))
    snap = snapshot(tmux_server_running=True, existing={"whatever": "/x"}, markers={"whatever": fp})
    assert plan(selection, snap) == CommandPlan(
        [
            cmd("tmux", "attach", "-t", "whatever"),
        ]
    )


def test_reuse_switches_under_whatever_name_marker_says():
    fp = fingerprint(NAMED_ONE)
    selection = Selection((), (NAMED_ONE,))
    snap = snapshot(
        in_tmux=True, tmux_server_running=True, existing={"renamed": "/x"}, markers={"renamed": fp}
    )
    assert plan(selection, snap) == CommandPlan(
        [
            cmd("tmux", "switch-client", "-t", "renamed"),
            cmd("tmux", "refresh-client", "-S"),
        ]
    )


def test_taken_desired_name_gets_numeric_suffix():
    selection = Selection((), (NAMED_ONE,))
    snap = snapshot(tmux_server_running=False, existing={"myws": "/foreign"})
    assert plan(selection, snap) == CommandPlan(
        [
            *ws_commands("myws-2", NAMED_ONE),
            cmd("tmux", "attach", "-t", "myws-2"),
        ]
    )


def test_anonymous_workspace_uses_msz_fallback_name():
    selection = Selection((), (ANON,))
    snap = snapshot(tmux_server_running=False)
    name = f"msz-{fingerprint(ANON)[:12]}"
    assert plan(selection, snap) == CommandPlan(
        [
            *ws_commands(name, ANON),
            cmd("tmux", "attach", "-t", name),
        ]
    )


def test_mixed_dirs_then_workspaces_single_post_step():
    selection = Selection(("/a/one",), (NAMED_ONE,))
    snap = snapshot(tmux_server_running=False)
    assert plan(selection, snap) == CommandPlan(
        [
            cmd("zoxide", "add", "/a/one"),
            cmd("tmux", "new-session", "-ds", "one", "-c", "/a/one"),
            *ws_commands("myws", NAMED_ONE),
            cmd("tmux", "attach", "-t", "one"),
        ]
    )


def test_same_plan_two_identical_definitions_share_one_session():
    selection = Selection((), (NAMED_ONE, NAMED_ONE))
    snap = snapshot(tmux_server_running=False)
    plan_ = plan(selection, snap)
    tmuxp_cmds = [c for c in plan_ if c.program == "tmuxp"]
    setopt_cmds = [c for c in plan_ if c.program == "tmux" and c.args and c.args[0] == "set-option"]
    assert len(tmuxp_cmds) == 1
    assert len(setopt_cmds) == 1
    assert plan_[-1] == cmd("tmux", "attach", "-t", "myws")


def test_same_plan_two_different_definitions_two_sessions():
    selection = Selection((), (NAMED_ONE, NAMED_TWO))
    snap = snapshot(tmux_server_running=False)
    plan_ = plan(selection, snap)
    names = [c.args[2] for c in plan_ if c.program == "tmux" and c.args[:2] == ("set-option", "-t")]
    assert names == ["myws", "myws-2"]


def test_foreign_session_with_colliding_name_never_switched_into():
    selection = Selection((), (NAMED_ONE,))
    snap = snapshot(tmux_server_running=False, existing={"myws": "/foreign"})
    plan_ = plan(selection, snap)
    assert not any(
        c.program == "tmux" and c.args[0] == "attach" and c.args[1] == "myws" for c in plan_
    )
    assert cmd("tmux", "attach", "-t", "myws-2") in plan_
    assert cmd("tmuxp", "load", "-d", "--no-progress", "-s", "myws-2", input=NAMED_ONE) in plan_


def test_decision_derived_purely_from_snapshot_markers():
    fp = fingerprint(NAMED_ONE)
    selection = Selection((), (NAMED_ONE,))
    reused = plan(selection, snapshot(existing={"s1": "/x"}, markers={"s1": fp}))
    created = plan(selection, snapshot(existing={"s1": "/x"}))
    assert reused == CommandPlan([cmd("tmux", "attach", "-t", "s1")])
    assert any(c.program == "tmuxp" for c in created)


def test_reuse_survives_name_drift_after_disambiguated_creation():
    # First run collides with a foreign "myws" -> created under "myws-2" with
    # the marker; a later run must switch to that session by marker alone (R3).
    fp = fingerprint(NAMED_ONE)
    selection = Selection((), (NAMED_ONE,))
    first = plan(selection, snapshot(existing={"myws": "/foreign"}))
    assert cmd("tmuxp", "load", "-d", "--no-progress", "-s", "myws-2", input=NAMED_ONE) in first
    later = plan(
        selection,
        snapshot(existing={"myws": "/foreign", "myws-2": "/x"}, markers={"myws-2": fp}),
    )
    assert later == CommandPlan([cmd("tmux", "attach", "-t", "myws-2")])


def test_edited_definition_produces_new_session_never_silent_reuse():
    selection_old = Selection((), (NAMED_ONE,))
    selection_new = Selection((), (NAMED_TWO,))
    snap = snapshot(
        tmux_server_running=True, existing={"old": "/x"}, markers={"old": fingerprint(NAMED_ONE)}
    )
    assert plan(selection_new, snap) != plan(selection_old, snap)
    assert any(c.program == "tmuxp" for c in plan(selection_new, snap))


def test_picker_labels_disambiguate_duplicate_display_names():
    labels = picker_labels([NAMED_ONE, NAMED_ONE, ANON])
    assert labels == ["[tmuxp] myws", "[tmuxp] myws-2", f"[tmuxp] msz-{fingerprint(ANON)[:12]}"]
    assert len(set(labels)) == len(labels)


def test_array_readiness_expanding_input_before_plan_needs_no_plan_change():
    specs = (NAMED_ONE, NAMED_ONE, NAMED_TWO)
    selection = Selection((), specs)
    snap = snapshot(tmux_server_running=False)
    plan_ = plan(selection, snap)
    created = [c for c in plan_ if c.program == "tmuxp"]
    assert len(created) == 2
    assert [c.args[-1] for c in created] == ["myws", "myws-2"]
