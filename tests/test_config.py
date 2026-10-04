import pytest

from multi_sessionizer.config import (
    Config,
    ConfigNotFoundError,
    load_config,
    missing_dirs,
)


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigNotFoundError):
        load_config(tmp_path / "missing.toml")


def test_empty_config_file(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("")
    assert load_config(p) == Config()


def test_partial_override(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_dirs = ["/x", "/y"]\n')
    cfg = load_config(p)
    assert cfg.additional_dirs == ("/x", "/y")
    assert cfg.project_roots_depth_1 == ()


def test_single_string_coerced_to_list(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_dirs = "/x"\n')
    cfg = load_config(p)
    assert cfg.additional_dirs == ("/x",)


def test_env_var_and_tilde_in_config_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "c.toml"
    p.write_text('additional_dirs = ["$HOME/x", "~/y"]\n')
    cfg = load_config(p)
    assert cfg.additional_dirs == (str(tmp_path / "x"), str(tmp_path / "y"))


def test_missing_dirs(tmp_path):
    exists = tmp_path / "exists"
    exists.mkdir()
    cfg = Config(
        additional_dirs=(str(exists), str(tmp_path / "nodir")),
    )
    assert missing_dirs(cfg) == [str(tmp_path / "nodir")]


def test_additional_files_key_is_ignored(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('additional_files = ["/x"]\nadditional_dirs = ["/y"]\n')
    cfg = load_config(p)
    assert cfg.additional_dirs == ("/y",)
    assert not hasattr(cfg, "additional_files")


def test_tmuxp_workspaces_loaded_as_tuple_of_strings(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('tmuxp_workspaces = ["a: 1", "b: 2"]\n')
    cfg = load_config(p)
    assert cfg.tmuxp_workspaces == ("a: 1", "b: 2")


def test_tmuxp_workspaces_each_string_is_one_entry(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('tmuxp_workspaces = ["windows:\\n  - shell_command: vim", "windows: []"]\n')
    cfg = load_config(p)
    assert cfg.tmuxp_workspaces == ("windows:\n  - shell_command: vim", "windows: []")


def test_tmuxp_workspaces_missing_key_defaults_to_empty(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text("")
    cfg = load_config(p)
    assert cfg.tmuxp_workspaces == ()


def test_tmuxp_workspaces_never_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "c.toml"
    p.write_text('tmuxp_workspaces = ["$HOME/x", "~/y"]\n')
    cfg = load_config(p)
    assert cfg.tmuxp_workspaces == ("$HOME/x", "~/y")
