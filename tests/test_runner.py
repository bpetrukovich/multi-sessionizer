import subprocess

from multi_sessionizer import runner as runner_mod
from multi_sessionizer.runner import Runner


def test_existing_sessions_parses_name_and_path(monkeypatch):
    runner = Runner(tmux="tmux")
    proc = subprocess.CompletedProcess(
        [],
        0,
        stdout="blog\t/home/me/blog\nwith space\t/home/me/with space\n",
    )
    monkeypatch.setattr(runner_mod.subprocess, "run", lambda *a, **k: proc)
    assert runner.existing_sessions() == {
        "blog": "/home/me/blog",
        "with space": "/home/me/with space",
    }


def test_existing_sessions_ignores_lines_without_path(monkeypatch):
    runner = Runner(tmux="tmux")
    proc = subprocess.CompletedProcess([], 0, stdout="empty_only\n")
    monkeypatch.setattr(runner_mod.subprocess, "run", lambda *a, **k: proc)
    assert runner.existing_sessions() == {}


def test_existing_sessions_empty_on_error(monkeypatch):
    runner = Runner(tmux="tmux")
    proc = subprocess.CompletedProcess([], 1, stdout="")
    monkeypatch.setattr(runner_mod.subprocess, "run", lambda *a, **k: proc)
    assert runner.existing_sessions() == {}


def test_existing_sessions_empty_on_oserror(monkeypatch):
    runner = Runner(tmux="tmux")

    def boom(*a, **k):
        raise OSError

    monkeypatch.setattr(runner_mod.subprocess, "run", boom)
    assert runner.existing_sessions() == {}
