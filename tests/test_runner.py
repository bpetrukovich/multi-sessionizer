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


import os
import shutil
import tempfile

import pytest

from multi_sessionizer.domain.models import Command
from multi_sessionizer.domain.run import ProvisioningError


def test_snapshot_populates_markers_from_marker_column(monkeypatch, tmp_path):
    runner = Runner(tmux="tmux")
    two_col = f"blog\t{tmp_path}/blog\nplain\t{tmp_path}/plain\n"
    three_col = f"blog\t{tmp_path}/blog\tfp123\nplain\t{tmp_path}/plain\t\n"

    def fake_run(args, **kw):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0, stdout="")
        if args[0] == "tmux":
            fmt = args[args.index("-F") + 1]
            if "@multi-sessionizer-marker" in fmt:
                return subprocess.CompletedProcess(args, 0, stdout=three_col)
            return subprocess.CompletedProcess(args, 0, stdout=two_col)
        raise AssertionError(f"unexpected argv: {args}")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.delenv("TMUX", raising=False)
    snap = runner.snapshot()
    assert snap.markers == {"blog": "fp123"}
    assert snap.existing == {"blog": str(tmp_path / "blog"), "plain": str(tmp_path / "plain")}


def test_snapshot_markers_empty_when_sessions_lack_option(monkeypatch, tmp_path):
    runner = Runner(tmux="tmux")
    three_col = f"blog\t{tmp_path}/blog\t\nplain\t{tmp_path}/plain\t\n"

    def fake_run(args, **kw):
        if args[0] == "pgrep":
            return subprocess.CompletedProcess(args, 0, stdout="")
        if args[0] == "tmux":
            return subprocess.CompletedProcess(args, 0, stdout=three_col)
        raise AssertionError(f"unexpected argv: {args}")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.delenv("TMUX", raising=False)
    snap = runner.snapshot()
    assert snap.markers == {}


def test_execute_materializes_input_to_temp_file_under_cwd(monkeypatch, tmp_path):
    runner = Runner(tmuxp="tmuxp")
    captured = {}

    def fake_run(args, **kw):
        with open(args[-1], encoding="utf-8") as fh:
            captured["content"] = fh.read()
        captured["args"] = args
        return subprocess.CompletedProcess(args, 0, stdout="")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    real_mkdtemp = tempfile.mkdtemp

    def fake_mkdtemp(**kw):
        captured["mkdtemp_kw"] = kw
        created = real_mkdtemp(**kw)
        captured["tmpdir"] = created
        return created

    monkeypatch.setattr(tempfile, "mkdtemp", fake_mkdtemp)
    runner.execute(
        [Command("tmuxp", ("load", "-d", "--no-progress", "-s", "myws"), input="windows: []")]
    )
    assert captured["mkdtemp_kw"]["dir"] == str(tmp_path)
    assert captured["args"][0] == "tmuxp"
    assert captured["args"][1:5] == ["load", "-d", "--no-progress", "-s"]
    assert captured["content"] == "windows: []"
    assert captured["args"][-1] == os.path.join(captured["tmpdir"], "workspace.yaml")
    assert not os.path.exists(captured["tmpdir"])


def test_execute_raises_provisioning_error_on_tmuxp_failure(monkeypatch, tmp_path):
    runner = Runner(tmuxp="tmuxp")

    def fake_run(args, **kw):
        return subprocess.CompletedProcess(args, 1, stdout="")

    monkeypatch.setattr(runner_mod.subprocess, "run", fake_run)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProvisioningError):
        runner.execute(
            [Command("tmuxp", ("load", "-d", "--no-progress", "-s", "myws"), input="windows: []")]
        )


def test_execute_raises_when_tmuxp_missing_on_path(monkeypatch, tmp_path):
    runner = Runner(tmuxp="tmuxp")
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProvisioningError, match="tmuxp is required"):
        runner.execute(
            [Command("tmuxp", ("load", "-d", "--no-progress", "-s", "myws"), input="windows: []")]
        )
