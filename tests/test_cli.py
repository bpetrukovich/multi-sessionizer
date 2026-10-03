import pytest

from multi_sessionizer.cli import classify_args


def test_classify_dirs_and_files(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    f = tmp_path / "f"
    f.touch()
    dirs, files = classify_args([str(d), str(f)])
    assert dirs == [str(d)]
    assert files == [str(f)]


def test_classify_resolves_realpath(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    dirs, files = classify_args([str(tmp_path / "." / "d")])
    assert dirs == [str(d)]
    assert files == []


def test_classify_isdir_priority_over_isfile(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    dirs, files = classify_args([str(d)])
    assert dirs == [str(d)]
    assert files == []


def test_classify_bad_path_raises(tmp_path):
    with pytest.raises(ValueError, match="Not a directory or file"):
        classify_args([str(tmp_path / "nope")])


def test_classify_bad_path_after_good_raises(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    with pytest.raises(ValueError, match="Not a directory or file"):
        classify_args([str(d), str(tmp_path / "nope")])
