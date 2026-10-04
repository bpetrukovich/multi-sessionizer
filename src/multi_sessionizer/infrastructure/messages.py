"""MessageOutput adapter: all user-facing stderr/stdout text (research R7).

Prints the exact text so the app flow never prints directly.
"""

from __future__ import annotations

import sys

CONFIG_EXAMPLE = """\
project_roots_depth_1 = ["$HOME"]
project_roots_depth_2 = ["$HOME/work"]
sessions = [
  "$HOME/Documents",
  "$HOME/Projects",
  'session_name: "project"
windows:
  - shell_command: "vim"',
  { name = "frontend stack",
    sessions = [
      "$HOME/work/web-frontend",
      'session_name: "dev-server"
windows:
  - shell_command: "yarn dev"',
    ] },
]
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

    def external_added(self, label: str) -> None:
        print(f"multi-sessionizer: added [external] {label}")

    def external_list(self, rows: list[tuple[str, str, str]]) -> None:
        width = max((len(label) for _, label, _ in rows), default=0)
        for kind, label, deletion_key in rows:
            print(f"{kind:<11}{label:<{width}}  {deletion_key}")

    def external_deleted(self, message: str) -> None:
        print(message)

    def external_empty(self) -> None:
        print("No external entries yet.")
