"""SelectionClassifier adapter: path classification at the infra boundary.

Every path entering the domain is realpath-normalized here (research R2):
``classify_args`` realpaths each argument; ``classify_selection`` realpaths
each picker line. ``normalize_path = os.path.realpath`` is the single helper.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from ..domain.models import Selection

normalize_path = os.path.realpath


def classify_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    dirs: list[str] = []
    files: list[str] = []
    for arg in argv:
        if os.path.isdir(arg):
            dirs.append(normalize_path(arg))
        elif os.path.isfile(arg):
            files.append(normalize_path(arg))
        else:
            raise ValueError(f"Not a directory or file: {arg}")
    return dirs, files


def classify_selection(lines: list[str]) -> Selection:
    dirs: list[str] = []
    files: list[str] = []
    for line in lines:
        path = normalize_path(line)
        if os.path.isdir(path):
            dirs.append(path)
        else:
            files.append(path)
    return Selection(tuple(dirs), tuple(files))


class PathSelectionClassifier:
    """Object adapter satisfying the app ``SelectionClassifier`` port."""

    def classify_args(self, argv: Sequence[str]) -> tuple[list[str], list[str]]:
        return classify_args(argv)

    def classify_selection(self, lines: list[str]) -> Selection:
        return classify_selection(lines)
