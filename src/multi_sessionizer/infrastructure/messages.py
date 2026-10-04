"""MessageOutput adapter: all user-facing stderr/stdout text (research R7).

Prints the exact text so the app flow never prints directly.
"""

from __future__ import annotations

import sys

CONFIG_EXAMPLE = """\
project_roots_depth_1 = ["$HOME"]
project_roots_depth_2 = ["$HOME/work"]
additional_dirs = ["$HOME/Documents", "$HOME/Projects"]
tmuxp_workspaces = ["session_name: \"project\"\nwindows:\n  - shell_command: \"vim\"\n"]
"""


class ConsoleMessageOutput:
    def config_not_found(self, path: object) -> None:
        print(f"Configuration file not found: {path}", file=sys.stderr)
        print(file=sys.stderr)
        print("Create it with an example:", file=sys.stderr)
        print(CONFIG_EXAMPLE, file=sys.stderr, end="")
        print(
            "The path can be overridden with the MULTI_SESSIONIZER_CONFIG environment variable.",
            file=sys.stderr,
        )

    def missing_dirs(self, missing_dirs: list[str]) -> None:
        if missing_dirs:
            print("The following directories do not exist:", file=sys.stderr)
            for path in missing_dirs:
                print(f"  {path}", file=sys.stderr)

    def workspace_problems(self, problems: list[str]) -> None:
        for problem in problems:
            print(problem, file=sys.stderr)

    def error(self, msg: str) -> None:
        print(msg, file=sys.stderr)
