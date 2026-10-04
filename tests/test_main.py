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
    assert "multi-sessionizer 0.2.0" in out


def test_unknown_command(monkeypatch, capsys):
    def fail(*_args):
        raise AssertionError("switch_flow should not be called")

    monkeypatch.setattr(main, "switch_flow", fail)
    assert main.main(["bogus"]) == 2
    err = capsys.readouterr().err
    assert "unknown command: bogus" in err
    assert "--help" in err


def test_switch_dispatches_to_switch_flow(monkeypatch):
    captured = {}

    def fake_switch_flow(paths, deps):
        captured["paths"] = paths
        return 0

    monkeypatch.setattr(main, "switch_flow", fake_switch_flow)
    assert main.main(["switch", "-foo"]) == 0
    assert captured["paths"] == ["-foo"]


def test_switch_bad_path(capsys):
    assert main.main(["switch", "/nonexistent/xyz"]) == 1
    assert "Not a directory or file" in capsys.readouterr().err


def test_split_session():
    assert main._split_argv(["session", "<yaml>", "<yaml>"]) == ("session", ["<yaml>", "<yaml>"])


def test_session_runs_flow(monkeypatch):
    captured = {}

    def fake_session_flow(paths, deps):
        captured["paths"] = paths
        return 0

    monkeypatch.setattr(main, "session_flow", fake_session_flow)
    assert main.main(["session", "windows: []"]) == 0
    assert captured["paths"] == ["windows: []"]


def test_session_takes_everything_after_verbatim(monkeypatch):
    captured = {}

    def fake_session_flow(paths, deps):
        captured["paths"] = paths
        return 0

    monkeypatch.setattr(main, "session_flow", fake_session_flow)
    assert main.main(["session", "--leading", "-dash", "a: b"]) == 0
    assert captured["paths"] == ["--leading", "-dash", "a: b"]


def test_help_shows_session_subcommand(capsys):
    assert main.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "session" in out


def _interactive_with_config(tmp_path, monkeypatch, content):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(content)
    monkeypatch.setenv("MULTI_SESSIONIZER_CONFIG", str(cfg_path))
    return main.main([])


def test_interactive_rejects_removed_additional_dirs(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(tmp_path, monkeypatch, 'additional_dirs = ["/x"]\n')
    assert code == 1
    err = capsys.readouterr().err
    assert (
        "Configuration error: the 'additional_dirs' key is no longer supported; use 'sessions' instead."
        in err
    )


def test_interactive_rejects_removed_tmuxp_workspaces(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(tmp_path, monkeypatch, 'tmuxp_workspaces = ["a: 1"]\n')
    assert code == 1
    err = capsys.readouterr().err
    assert (
        "Configuration error: the 'tmuxp_workspaces' key is no longer supported; use 'sessions' instead."
        in err
    )


def test_interactive_group_missing_name(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(
        tmp_path, monkeypatch, 'sessions = [{ sessions = ["/tmp/a"] }]\n'
    )
    assert code == 1
    assert "Group is missing a 'name'." in capsys.readouterr().err


def test_interactive_group_empty_sessions(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(
        tmp_path, monkeypatch, 'sessions = [{ name = "g", sessions = [] }]\n'
    )
    assert code == 1
    assert "Group 'g' has an empty 'sessions' list." in capsys.readouterr().err


def test_interactive_group_invalid_member(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(
        tmp_path, monkeypatch, 'sessions = [{ name = "g", sessions = [{ foo = 1 }] }]\n'
    )
    assert code == 1
    assert (
        "Group 'g' has an invalid member: expected a directory or workspace."
        in capsys.readouterr().err
    )


def test_interactive_nested_group(tmp_path, monkeypatch, capsys):
    code = _interactive_with_config(
        tmp_path,
        monkeypatch,
        'sessions = [{ name = "o", sessions = [{ name = "i", sessions = ["/tmp/a"] }] }]\n',
    )
    assert code == 1
    assert "Nested groups are not supported: group 'i'." in capsys.readouterr().err
