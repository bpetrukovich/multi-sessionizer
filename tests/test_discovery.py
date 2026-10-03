import os

from multi_sessionizer import discovery
from multi_sessionizer.config import Config
from multi_sessionizer.discovery import collect_dirs, collect_files


def test_depth1_lists_direct_children_including_hidden(tmp_path):
    root = tmp_path / "root"
    (root / "alpha").mkdir(parents=True)
    (root / "beta").mkdir()
    (root / ".hidden").mkdir()
    (root / "alpha" / "file.txt").touch()
    cfg = Config(project_roots_depth_1=(str(root),))
    assert collect_dirs(cfg) == [
        str(root / ".hidden"),
        str(root / "alpha"),
        str(root / "beta"),
    ]


def test_depth2_includes_nested(tmp_path):
    root = tmp_path / "root"
    (root / "alpha" / "nested").mkdir(parents=True)
    (root / "alpha" / "file.txt").touch()
    cfg = Config(project_roots_depth_2=(str(root),))
    assert collect_dirs(cfg) == [str(root / "alpha"), str(root / "alpha" / "nested")]


def test_hidden_dirs_included_at_depth_two(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "alpha").mkdir()
    (root / ".git" / "objects").mkdir(parents=True)
    cfg = Config(project_roots_depth_2=(str(root),))
    assert collect_dirs(cfg) == [
        str(root / ".git"),
        str(root / ".git" / "objects"),
        str(root / "alpha"),
    ]


def test_hidden_root_lists_its_children(tmp_path):
    hidden = tmp_path / "root" / ".config" / "nvim"
    hidden.mkdir(parents=True)
    (hidden / "lua").mkdir()
    cfg = Config(project_roots_depth_1=(str(hidden),))
    assert collect_dirs(cfg) == [str(hidden / "lua")]


def test_depth2_does_not_descend_beyond_two_levels(tmp_path):
    root = tmp_path / "root"
    (root / "a" / "b" / "c" / "d").mkdir(parents=True)
    cfg = Config(project_roots_depth_2=(str(root),))
    assert collect_dirs(cfg) == [str(root / "a"), str(root / "a" / "b")]


def test_depth1_does_not_descend_beyond_one_level(tmp_path):
    root = tmp_path / "root"
    (root / "a" / "b").mkdir(parents=True)
    cfg = Config(project_roots_depth_1=(str(root),))
    assert collect_dirs(cfg) == [str(root / "a")]


def test_scan_does_not_descend_beyond_max_depth(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "a" / "b" / "c" / "d").mkdir(parents=True)
    calls: list[str] = []
    real_scandir = os.scandir

    def spy(path):
        calls.append(path)
        return real_scandir(path)

    monkeypatch.setattr(discovery.os, "scandir", spy)
    cfg = Config(project_roots_depth_2=(str(root),))
    collect_dirs(cfg)
    assert str(root / "a") in calls
    assert str(root / "a" / "b") not in calls
    assert str(root / "a" / "b" / "c") not in calls


class _FakeEntry:
    def __init__(self, path):
        self.name = os.path.basename(path)
        self.path = path

    def is_dir(self, follow_symlinks=True):
        return True


def test_scan_cost_is_bounded_by_max_depth(tmp_path, monkeypatch):
    """The scan must touch only the configured levels, never the whole tree.

    Simulates a deep tree (6 levels x 5 children each = thousands of nodes)
    purely in memory and asserts the number of ``os.scandir`` calls stays
    bounded by the width of the levels actually scanned (1 + 5 + 25). A
    regression to a full-tree walk (``os.walk``) explodes the call count and
    fails this test deterministically.
    """
    root = tmp_path / "root"
    root.mkdir()
    calls: list[str] = []
    real_scandir = os.scandir

    def fake_scandir(path):
        calls.append(path)
        depth = 0 if path == str(root) else len(os.path.relpath(path, root).split(os.sep))
        if depth >= 6:
            return real_scandir(path)
        return [_FakeEntry(os.path.join(path, f"d{i}")) for i in range(5)]

    monkeypatch.setattr(discovery.os, "scandir", fake_scandir)
    cfg = Config(project_roots_depth_2=(str(root),))
    dirs = collect_dirs(cfg)
    assert len(dirs) == 5 + 25
    assert len(calls) <= 1 + 5 + 25


def test_additional_dirs_verbatim_even_if_missing(tmp_path):
    missing = tmp_path / "nope"
    cfg = Config(additional_dirs=(str(missing), "/some/where"))
    assert collect_dirs(cfg) == [str(missing), "/some/where"]


def test_order_depth1_then_depth2_then_extra(tmp_path):
    r1 = tmp_path / "r1"
    r1.mkdir()
    (r1 / "a").mkdir()
    (r1 / "b").mkdir()
    r2 = tmp_path / "r2"
    r2.mkdir()
    (r2 / "c" / "d").mkdir(parents=True)
    cfg = Config(
        project_roots_depth_1=(str(r1),),
        project_roots_depth_2=(str(r2),),
        additional_dirs=("/extra",),
    )
    assert collect_dirs(cfg) == [
        str(r1 / "a"),
        str(r1 / "b"),
        str(r2 / "c"),
        str(r2 / "c" / "d"),
        "/extra",
    ]


def test_no_dedup_when_roots_overlap(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a").mkdir()
    cfg = Config(
        project_roots_depth_1=(str(root),),
        project_roots_depth_2=(str(root),),
    )
    assert collect_dirs(cfg) == [str(root / "a"), str(root / "a")]


def test_collect_files(tmp_path):
    f = tmp_path / "x"
    f.touch()
    cfg = Config(additional_files=(str(f),))
    assert collect_files(cfg) == [str(f)]


def test_collect_files_empty(tmp_path):
    assert collect_files(Config()) == []
