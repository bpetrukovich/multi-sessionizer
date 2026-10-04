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


def test_snapshot_builds_runtime_snapshot(monkeypatch, tmp_path):
    runner = Runner(tmux="tmux")
    session_out = f"blog\t{tmp_path}/blog\nwith space\t{tmp_path}/with space\n"

    def fake_run(args, **kw):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0, stdout="")
        if args[0] == "tmux":
            return subprocess.CompletedProcess(args, 0, stdout=session_out)
        raise AssertionError(f"unexpected argv: {args}")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.setenv("TMUX", "sock,12345,0")
    snap = runner.snapshot()
    assert snap.in_tmux is True
    assert snap.tmux_server_running is True
    assert snap.existing == {
        "blog": str(tmp_path / "blog"),
        "with space": str(tmp_path / "with space"),
    }


def test_snapshot_in_tmux_false_when_env_unset(monkeypatch):
    runner = Runner(tmux="tmux")

    def fake_run(args, **kw):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 1, stdout="")
        if args[0] == "tmux":
            return subprocess.CompletedProcess(args, 1, stdout="")
        raise AssertionError(f"unexpected argv: {args}")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.delenv("TMUX", raising=False)
    snap = runner.snapshot()
    assert snap.in_tmux is False
    assert snap.tmux_server_running is False
    assert snap.existing == {}


def test_snapshot_realpath_normalizes_existing_values(monkeypatch, tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    runner = Runner(tmux="tmux")
    session_out = f"blog\t{link}\n"

    def fake_run(args, **kw):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0, stdout="")
        if args[0] == "tmux":
            return subprocess.CompletedProcess(args, 0, stdout=session_out)
        raise AssertionError(f"unexpected argv: {args}")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.delenv("TMUX", raising=False)
    snap = runner.snapshot()
    assert snap.existing == {"blog": str(target)}
