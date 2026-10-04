"""Direct DTO-driven domain tests (FR-018, US1).

These tests construct ``Selection``/``RuntimeSnapshot`` by hand and exercise the
pure core: they must pass with zero external tools, no ``TMUX`` env var, and no
real subprocess execution.
"""

from __future__ import annotations

from multi_sessionizer.domain.models import Command, CommandPlan, RuntimeSnapshot, Selection
from multi_sessionizer.domain.plan import plan, plan_legacy
from multi_sessionizer.domain.run import run


def cmd(program, *args):
    return Command(program, args)


def snapshot(*, in_tmux=False, tmux_server_running=False, existing=None):
    return RuntimeSnapshot(
        in_tmux=in_tmux,
        tmux_server_running=tmux_server_running,
        existing=existing if existing is not None else {},
    )


def test_plan_is_deterministic():
    selection = Selection(("/a/one", "/b/two"), ("/a/x.py",))
    snap = snapshot(tmux_server_running=False)
    assert plan(selection, snap) == plan(selection, snap)


def test_existing_session_reused_when_same_path():
    selection = Selection(("/a/dup",), ())
    snap = snapshot(tmux_server_running=True, existing={"dup": "/a/dup"})
    assert plan(selection, snap) == CommandPlan(
        [
            cmd("zoxide", "add", "/a/dup"),
            cmd("tmux", "attach", "-t", "dup"),
        ]
    )


def test_numeric_suffix_disambiguation():
    selection = Selection(("/d/dup",), ())
    snap = snapshot(
        tmux_server_running=False,
        existing={"dup": "/a/dup", "dup-2": "/c/dup"},
    )
    assert plan(selection, snap) == CommandPlan(
        [
            cmd("zoxide", "add", "/d/dup"),
            cmd("tmux", "new-session", "-ds", "dup-3", "-c", "/d/dup"),
            cmd("tmux", "attach", "-t", "dup-3"),
        ]
    )


def test_core_plan_matches_legacy_wrapper_single_dir():
    selection = Selection(("/a/my.project",), ())
    snap = snapshot(in_tmux=False, tmux_server_running=False)
    assert plan(selection, snap) == plan_legacy(
        ["/a/my.project"],
        [],
        in_tmux=False,
        tmux_server_running=False,
    )


def test_core_plan_matches_legacy_wrapper_single_file():
    selection = Selection((), ("/a/b/file.py",))
    snap = snapshot(in_tmux=False, tmux_server_running=False)
    assert plan(selection, snap) == plan_legacy(
        [],
        ["/a/b/file.py"],
        in_tmux=False,
        tmux_server_running=False,
    )


def test_core_plan_matches_legacy_wrapper_multi():
    selection = Selection(("/a/one", "/b/two"), ())
    snap = snapshot(in_tmux=False, tmux_server_running=False)
    assert plan(selection, snap) == plan_legacy(
        ["/a/one", "/b/two"],
        [],
        in_tmux=False,
        tmux_server_running=False,
    )


def test_core_plan_matches_legacy_wrapper_empty():
    selection = Selection((), ())
    snap = snapshot(in_tmux=False, tmux_server_running=False)
    assert plan(selection, snap) == plan_legacy(
        [],
        [],
        in_tmux=False,
        tmux_server_running=False,
    )
    assert plan(selection, snap) == CommandPlan([])


class FakeExecutor:
    def __init__(self):
        self.executed: list[CommandPlan] = []

    def execute(self, cmds: CommandPlan) -> None:
        self.executed.append(cmds)


def test_run_hands_plan_to_executor_and_nothing_else():
    selection = Selection(("/a/one",), ())
    snap = snapshot(in_tmux=False, tmux_server_running=False)
    fake = FakeExecutor()
    run(selection, snap, fake)
    assert len(fake.executed) == 1
    assert fake.executed[0] == plan(selection, snap)
