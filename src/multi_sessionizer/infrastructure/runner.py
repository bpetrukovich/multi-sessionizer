"""Infrastructure Runner: subprocess/tmux/zoxide/fzf/env adapter.

Implements the app ports ``EnvironmentProbe``, ``ZoxideScorer``, ``Picker`` and
the domain ``CommandExecutor``. The legacy methods (``tmux_running``,
``existing_sessions``, ``zoxide_scores``, ``run_fzf``, ``execute``) keep their
identical signatures and parse behavior so ``test_runner.py`` passes unchanged.
"""

from __future__ import annotations

import os
import subprocess

from ..domain.models import Command, RuntimeSnapshot

normalize_path = os.path.realpath


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

    # --- legacy methods (unchanged surface for test_runner.py) ---

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

    def existing_sessions(self) -> dict[str, str]:
        try:
            proc = subprocess.run(
                [self._tmux, "list-sessions", "-F", "#{session_name}\t#{session_path}"],
                capture_output=True,
                text=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return {}
        if proc.returncode != 0:
            return {}
        sessions: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            name, _, path = line.partition("\t")
            if name and path:
                sessions[name] = path
        return sessions

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

    # --- adapter methods (app ports / domain executor) ---

    def snapshot(self) -> RuntimeSnapshot:
        existing = {name: normalize_path(path) for name, path in self.existing_sessions().items()}
        return RuntimeSnapshot(
            in_tmux=bool(os.environ.get("TMUX")),
            tmux_server_running=self.tmux_running(),
            existing=existing,
        )

    def scores(self) -> str:
        return self.zoxide_scores()

    def pick(self, items: list[str]) -> list[str]:
        return self.run_fzf(items)
