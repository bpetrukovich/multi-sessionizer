"""SelectionClassifier adapter: path classification at the infra boundary.

Every path entering the domain is realpath-normalized here (research R2):
``classify_args`` realpaths each argument; ``classify_selection`` realpaths
each picker line. ``normalize_path = os.path.realpath`` is the single helper.

Directories only (FR-001): file paths are no longer accepted — a file argument
raises a clear ``ValueError``; the 2-tuple shape is kept for the legacy facade
with the second slot always empty.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from ..domain.models import Selection

normalize_path = os.path.realpath


def classify_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    dirs: list[str] = []
    for arg in argv:
        if os.path.isdir(arg):
            dirs.append(normalize_path(arg))
        elif os.path.isfile(arg):
            raise ValueError(f"File paths are not supported: {arg}")
        else:
            raise ValueError(f"Not a directory or file: {arg}")
    return dirs, []


def classify_selection(lines: list[str]) -> Selection:
    dirs: list[str] = []
    for line in lines:
        path = normalize_path(line)
        if os.path.isdir(path):
            dirs.append(path)
    return Selection(tuple(dirs), ())


class PathSelectionClassifier:
    """Object adapter satisfying the app ``SelectionClassifier`` port."""

    def classify_args(self, argv: Sequence[str]) -> tuple[list[str], list[str]]:
        return classify_args(argv)

    def classify_selection(self, lines: list[str]) -> Selection:
        return classify_selection(lines)
