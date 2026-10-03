from multi_sessionizer import main


def test_split_empty():
    assert main._split_argv([]) == (None, [])


def test_split_help_flags():
    assert main._split_argv(["--help"]) == ("help", [])
    assert main._split_argv(["-h"]) == ("help", [])


def test_split_version():
    assert main._split_argv(["--version"]) == ("version", [])


def test_split_switch():
    assert main._split_argv(["switch", "/a", "/b"]) == ("switch", ["/a", "/b"])


def test_split_switch_leading_dash_path():
    assert main._split_argv(["switch", "--version"]) == ("switch", ["--version"])


def test_split_unknown():
    assert main._split_argv(["bogus"]) == ("unknown", ["bogus"])
    assert main._split_argv(["bogus", "/a"]) == ("unknown", ["bogus", "/a"])


def test_help_exits_zero(capsys):
    assert main.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "usage:" in out
    assert "switch" in out


def test_short_help_exits_zero(capsys):
    assert main.main(["-h"]) == 0
    out = capsys.readouterr().out
    assert "usage:" in out


def test_version_exits_zero(capsys):
    assert main.main(["--version"]) == 0
    out = capsys.readouterr().out
    assert "multi-sessionizer 0.1.1" in out


def test_unknown_command(monkeypatch, capsys):
    def fail(*_args):
        raise AssertionError("_run should not be called")

    monkeypatch.setattr(main, "_run", fail)
    assert main.main(["bogus"]) == 2
    err = capsys.readouterr().err
    assert "unknown command: bogus" in err
    assert "--help" in err


def test_switch_runs_with_paths(tmp_path, monkeypatch):
    d = tmp_path / "-foo"
    d.mkdir()
    captured = {}

    def fake_run(dirs, files):
        captured["dirs"] = dirs
        captured["files"] = files
        return 0

    monkeypatch.setattr(main, "_run", fake_run)
    assert main.main(["switch", str(d)]) == 0
    assert captured["dirs"] == [str(d)]
    assert captured["files"] == []


def test_switch_bad_path(monkeypatch, capsys):
    def fail(*_args):
        raise AssertionError("_run should not be called")

    monkeypatch.setattr(main, "_run", fail)
    assert main.main(["switch", "/nonexistent/xyz"]) == 1
    assert "Not a directory or file" in capsys.readouterr().err
