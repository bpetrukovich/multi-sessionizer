"""Infrastructure Runner: subprocess/tmux/tmuxp/zoxide/fzf/env adapter.

Implements the app ports ``EnvironmentProbe``, ``ZoxideScorer``, ``Picker`` and
the domain ``CommandExecutor``. The legacy methods (``tmux_running``,
``existing_sessions``, ``zoxide_scores``, ``run_fzf``, ``execute``) keep their
identical signatures and parse behavior so ``test_runner.py`` passes unchanged.

Workspace provisioning (research R1/R2/R9): a :class:`Command` with ``input``
set carries the authored definition; the executor materializes it to a temp
file under the CWD (so tmuxp resolves relative paths against the invocation
directory), appends the path as the final ``tmuxp load`` argument, deletes the
temp directory afterwards, and stamps the built session with the marker via
``tmux set-option``. A missing ``tmuxp`` or a non-zero build exit raises
:class:`ProvisioningError`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from ..domain.models import Command, RuntimeSnapshot
from ..domain.run import ProvisioningError

normalize_path = os.path.realpath


class Runner:
    def __init__(
        self,
        *,
        tmux: str = "tmux",
        fzf: str = "fzf",
        zoxide: str = "zoxide",
        pgrep: str = "pgrep",
        tmuxp: str = "tmuxp",
        env: dict[str, str] | None = None,
    ) -> None:
        self._tmux = tmux
        self._fzf = fzf
        self._zoxide = zoxide
        self._pgrep = pgrep
        self._tmuxp = tmuxp
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
            if cmd.input is None:
                subprocess.run(cmd.argv(), check=False, env=self._env)
            else:
                self._provision(cmd)

    def _provision(self, cmd: Command) -> None:
        """Materialize ``cmd.input`` to a temp file and run the build (R1/R9)."""
        if shutil.which(self._tmuxp) is None:
            raise ProvisioningError(
                "tmuxp is required for workspace sessions but was not found on PATH."
            )
        tmpdir = tempfile.mkdtemp(dir=os.getcwd())
        try:
            cfg_path = os.path.join(tmpdir, "workspace.yaml")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write(cmd.input)
            proc = subprocess.run(
                [cmd.program, *cmd.args, cfg_path],
                check=False,
                env=self._env,
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        if proc.returncode != 0:
            raise ProvisioningError(
                f"{cmd.program} failed to provision the workspace (exit code {proc.returncode})."
            )

    def list_session_markers(self) -> dict[str, str]:
        """Read the ``@multi-sessionizer-marker`` for every session (R2).

        Sessions without the option yield no entry — they are foreign (FR-013).
        """
        try:
            proc = subprocess.run(
                [
                    self._tmux,
                    "list-sessions",
                    "-F",
                    "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=self._env,
            )
        except OSError:
            return {}
        if proc.returncode != 0:
            return {}
        markers: dict[str, str] = {}
        for line in proc.stdout.splitlines():
            name, _, rest = line.partition("\t")
            _, _, marker = rest.partition("\t")
            if name and marker:
                markers[name] = marker
        return markers

    # --- adapter methods (app ports / domain executor) ---

    def snapshot(self) -> RuntimeSnapshot:
        existing = {name: normalize_path(path) for name, path in self.existing_sessions().items()}
        return RuntimeSnapshot(
            in_tmux=bool(os.environ.get("TMUX")),
            tmux_server_running=self.tmux_running(),
            existing=existing,
            markers=self.list_session_markers(),
        )

    def scores(self) -> str:
        return self.zoxide_scores()

    def pick(self, items: list[str]) -> list[str]:
        return self.run_fzf(items)
