"""Rank directories by zoxide usage scores.

The original bash script called ``zoxide query -l`` without ``--score``, which
made the score parsing a silent no-op. This module uses ``-l -s`` and parses
the ``score path`` output correctly.
"""

from __future__ import annotations

from collections.abc import Iterable


def parse_zoxide_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if " " in line:
            score_str, path = line.split(" ", 1)
        else:
            score_str, path = "0", line
        try:
            scores[path] = float(score_str)
        except ValueError:
            scores[path] = 0.0
    return scores


def rank_dirs(dirs: Iterable[str], scores: dict[str, float]) -> list[str]:
    return sorted(dirs, key=lambda d: scores.get(d, 0.0), reverse=True)


def build_picker_list(
    dirs: Iterable[str],
    scores: dict[str, float],
    files: Iterable[str],
) -> list[str]:
    return [*rank_dirs(dirs, scores), *files]
