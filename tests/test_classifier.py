"""SelectionClassifier adapter tests (FR-019)."""

from __future__ import annotations

import os

import pytest

from multi_sessionizer.domain.models import Selection
from multi_sessionizer.infrastructure.classifier import classify_args, classify_selection


def test_classify_args_dirs_and_files(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    f = tmp_path / "f"
    f.touch()
    dirs, files = classify_args([str(d), str(f)])
    assert dirs == [str(d)]
    assert files == [str(f)]


def test_classify_args_resolves_realpath(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    dirs, files = classify_args([str(tmp_path / "." / "d")])
    assert dirs == [str(d)]
    assert files == []


def test_classify_args_bad_path_raises(tmp_path):
    with pytest.raises(ValueError, match="Not a directory or file: .*"):
        classify_args([str(tmp_path / "nope")])


def test_classify_args_error_names_the_arg(tmp_path):
    with pytest.raises(ValueError) as exc:
        classify_args([str(tmp_path / "nope")])
    assert f"Not a directory or file: {tmp_path / 'nope'}" == str(exc.value)


def test_classify_selection_dirs_and_files_realpathed(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    f = tmp_path / "f"
    f.touch()
    selection = classify_selection([str(tmp_path / "." / "d"), str(f)])
    assert selection == Selection((str(d),), (str(f),))


def test_classify_selection_non_dir_goes_to_files(tmp_path):
    f = tmp_path / "f"
    f.touch()
    selection = classify_selection([str(f)])
    assert selection == Selection((), (str(f),))


def test_classify_selection_resolves_symlinked_dir(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    selection = classify_selection([str(link)])
    assert selection == Selection((os.path.realpath(str(link)),), ())
    assert selection.dirs == (str(target),)
