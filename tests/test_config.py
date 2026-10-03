import pytest

from multi_sessionizer.config import (
    Config,
    ConfigNotFoundError,
    load_config,
    missing_dirs,
    missing_files,
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
    assert cfg.additional_files == ()
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


def test_missing_files_and_dirs(tmp_path):
    exists = tmp_path / "exists"
    exists.mkdir()
    f1 = tmp_path / "f1"
    f1.touch()
    cfg = Config(
        additional_files=(str(f1), str(tmp_path / "nofile")),
        additional_dirs=(str(exists), str(tmp_path / "nodir")),
    )
    assert missing_files(cfg) == [str(tmp_path / "nofile")]
    assert missing_dirs(cfg) == [str(tmp_path / "nodir")]


def test_missing_files_uses_exists_like_bash_e(tmp_path):
    d = tmp_path / "adir"
    d.mkdir()
    cfg = Config(additional_files=(str(d),))
    assert missing_files(cfg) == []
