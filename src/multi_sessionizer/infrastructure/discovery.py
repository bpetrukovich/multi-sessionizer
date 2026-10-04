"""CandidateDiscovery adapter: collect directories and files from the roots.

Replicates the ``find`` invocations of the original bash script:

- ``project_roots_depth_1``: direct subdirectories of each root;
- ``project_roots_depth_2``: subdirectories and their direct children;
- ``additional_dirs`` and ``additional_files`` are added verbatim.

The traversal is pruned at the configured depth (like ``find -maxdepth``), so
deep trees are never walked (constitution IV). Hidden directories (``.git``,
``.config``, ...) are listed like any other. Symbolic links are not followed.
Output keeps today's ``os.path.abspath`` (logical) form — NOT realpath (R2).
"""

from __future__ import annotations

import os

from ..app.configuration import Config


def _find_dirs(root: str, min_depth: int, max_depth: int) -> list[str]:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return []
    result: list[str] = []

    def walk(dirpath: str, depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            entries = sorted(os.scandir(dirpath), key=lambda e: e.name)
        except OSError:
            return
        for entry in entries:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if not is_dir:
                continue
            child = entry.path
            if depth + 1 >= min_depth:
                result.append(child)
            walk(child, depth + 1)

    walk(root, 0)
    return result


def collect_dirs(cfg: Config) -> list[str]:
    dirs: list[str] = []
    for root in cfg.project_roots_depth_1:
        dirs.extend(_find_dirs(root, 1, 1))
    for root in cfg.project_roots_depth_2:
        dirs.extend(_find_dirs(root, 1, 2))
    dirs.extend(cfg.additional_dirs)
    return dirs


def collect_files(cfg: Config) -> list[str]:
    return list(cfg.additional_files)


class FileCandidateDiscovery:
    """Object adapter satisfying the app ``CandidateDiscovery`` port."""

    def collect_dirs(self, cfg: Config) -> list[str]:
        return collect_dirs(cfg)

    def collect_files(self, cfg: Config) -> list[str]:
        return collect_files(cfg)
