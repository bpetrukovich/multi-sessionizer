import pytest

from multi_sessionizer.config import (
    Config,
    ConfigError,
    ConfigNotFoundError,
    load_config,
    missing_dirs,
)
from multi_sessionizer.domain.models import SessionEntry

WS_DEF = 'session_name: "myws"\nwindows:\n  - shell_command: "vim"\n'


def _entry(**kw):
    return SessionEntry(**kw)


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigNotFoundError):
        load_config(tmp_path / "missing.toml")


def test_empty_config_file(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("")
    assert load_config(p) == Config()


def test_partial_override(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('sessions = ["/x", "/y"]\n')
    cfg = load_config(p)
    assert cfg.sessions == (
        _entry(kind="directory", path="/x"),
        _entry(kind="directory", path="/y"),
    )
    assert cfg.project_roots_depth_1 == ()


def test_single_string_coerced_to_list(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('sessions = "/x"\n')
    cfg = load_config(p)
    assert cfg.sessions == (_entry(kind="directory", path="/x"),)


def test_directory_strings_expanded_and_realpathed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "c.toml"
    p.write_text('sessions = ["$HOME/x", "~/y", "$HOME/z"]\n')
    cfg = load_config(p)
    assert cfg.sessions == (
        _entry(kind="directory", path=str(tmp_path / "x")),
        _entry(kind="directory", path=str(tmp_path / "y")),
        _entry(kind="directory", path=str(tmp_path / "z")),
    )


def test_workspace_strings_kept_verbatim_not_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "c.toml"
    p.write_text('sessions = ["$HOME/keep", "session_name: w\\nwindows:\\n  - x: 1"]\n')
    cfg = load_config(p)
    assert cfg.sessions == (
        _entry(kind="directory", path=str(tmp_path / "keep")),
        _entry(kind="workspace", definition="session_name: w\nwindows:\n  - x: 1"),
    )


def test_missing_dirs_reports_roots_and_directory_entries(tmp_path):
    exists = tmp_path / "exists"
    exists.mkdir()
    group_missing = tmp_path / "groupmissing"
    cfg = Config(
        project_roots_depth_1=(str(tmp_path / "rootmissing"), str(exists)),
        sessions=(
            _entry(kind="directory", path=str(exists)),
            _entry(kind="directory", path=str(tmp_path / "topmissing")),
            _entry(
                kind="group",
                name="g",
                members=(
                    _entry(kind="directory", path=str(exists)),
                    _entry(kind="directory", path=str(group_missing)),
                ),
            ),
        ),
    )
    assert missing_dirs(cfg) == [
        str(tmp_path / "rootmissing"),
        str(tmp_path / "topmissing"),
        str(group_missing),
    ]


def test_sessions_missing_key_defaults_to_empty(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("")
    cfg = load_config(p)
    assert cfg.sessions == ()


def test_sessions_classifies_mixed_forms(tmp_path):
    ws1 = 'session_name: "w"\nwindows:\n  - shell_command: vim'
    ws2 = 'session_name: "w2"\nwindows:\n  - shell_command: vim'
    p = tmp_path / "c.toml"
    p.write_text(
        'sessions = ["/tmp/a", "session_name: \\"w\\"\\nwindows:\\n  - shell_command: vim", '
        '{ name = "g", sessions = ["/tmp/b", "session_name: \\"w2\\"\\nwindows:\\n  - shell_command: vim"] }]\n'
    )
    cfg = load_config(p)
    assert [e.kind for e in cfg.sessions] == ["directory", "workspace", "group"]
    assert cfg.sessions[0].path == "/tmp/a"
    assert cfg.sessions[1].definition == ws1
    group = cfg.sessions[2]
    assert group.name == "g"
    assert [m.kind for m in group.members] == ["directory", "workspace"]
    assert group.members[0].path == "/tmp/b"
    assert group.members[1].definition == ws2


def test_removed_key_additional_dirs_raises_config_error(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_dirs = ["/x"]\n')
    with pytest.raises(ConfigError) as excinfo:
        load_config(p)
    assert excinfo.value.messages == (
        "Configuration error: the 'additional_dirs' key is no longer supported; use 'sessions' instead.",
    )


def test_removed_key_tmuxp_workspaces_raises_config_error(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('tmuxp_workspaces = ["a: 1"]\n')
    with pytest.raises(ConfigError) as excinfo:
        load_config(p)
    assert excinfo.value.messages == (
        "Configuration error: the 'tmuxp_workspaces' key is no longer supported; use 'sessions' instead.",
    )


def test_both_removed_keys_reported_together(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_dirs = ["/x"]\ntmuxp_workspaces = ["a: 1"]\n')
    with pytest.raises(ConfigError) as excinfo:
        load_config(p)
    assert excinfo.value.messages == (
        "Configuration error: the 'additional_dirs' key is no longer supported; use 'sessions' instead.",
        "Configuration error: the 'tmuxp_workspaces' key is no longer supported; use 'sessions' instead.",
    )


def test_additional_files_unknown_key_ignored(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_files = ["/x"]\n')
    cfg = load_config(p)
    assert cfg.sessions == ()
    assert not hasattr(cfg, "additional_files")


def test_malformed_group_raises_config_error(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('sessions = [{ name = "g", sessions = [] }]\n')
    with pytest.raises(ConfigError) as excinfo:
        load_config(p)
    assert excinfo.value.messages == ("Group 'g' has an empty 'sessions' list.",)
