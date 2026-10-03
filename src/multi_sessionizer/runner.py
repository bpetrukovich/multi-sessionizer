"""Thin wrapper around the external programs (tmux, fzf, zoxide, pgrep)."""

from __future__ import annotations

import os
import subprocess

from .decisions import Command


class Runner:
    def __init__(
        self,
        *,
        tmux: str = "tmux",
        fzf: str = "fzf",
        zoxide: str = "zoxide",
        pgrep: str = "pgrep",
        env: dict[str, str] | None = None,
    ) -> None:
        self._tmux = tmux
        self._fzf = fzf
        self._zoxide = zoxide
        self._pgrep = pgrep
        self._env = env if env is not None else os.environ

    def tmux_running(self) -> bool:
        try:
            proc = subprocess.run(
                [self._pgrep, "tmux"],
                capture_output=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return False
        return proc.returncode == 0

    def existing_sessions(self) -> set[str]:
        try:
            proc = subprocess.run(
                [self._tmux, "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return set()
        if proc.returncode != 0:
            return set()
        return {line for line in proc.stdout.splitlines() if line}

    def zoxide_scores(self) -> str:
        try:
            proc = subprocess.run(
                [self._zoxide, "query", "-l", "-s"],
                capture_output=True,
                text=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return ""
        return proc.stdout

    def run_fzf(self, items: list[str]) -> list[str]:
        try:
            proc = subprocess.run(
                [self._fzf, "--tmux", "--multi", "--prompt", "Project > "],
                input="\n".join(items) + "\n",
                capture_output=True,
                text=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return []
        if proc.returncode != 0:
            return []
        return [line for line in proc.stdout.splitlines() if line]

    def execute(self, cmds: list[Command]) -> None:
        for cmd in cmds:
            subprocess.run(cmd.argv(), check=False, env=self._env)
