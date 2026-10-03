"""Classification of command-line arguments into directories and files."""

from __future__ import annotations

import os


def classify_args(args: list[str]) -> tuple[list[str], list[str]]:
    dirs: list[str] = []
    files: list[str] = []
    for arg in args:
        if os.path.isdir(arg):
            dirs.append(os.path.realpath(arg))
        elif os.path.isfile(arg):
            files.append(os.path.realpath(arg))
        else:
            raise ValueError(f"Not a directory or file: {arg}")
    return dirs, files
