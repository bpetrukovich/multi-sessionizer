# multi-sessionizer

A tool for quickly creating and switching between tmux project sessions. It lets you spin up working environments for multiple directories and inline tmuxp workspaces in a couple of keystrokes: each selected directory gets its own tmux session (created or reused), and each workspace is provisioned from its tmuxp definition (windows, panes, layouts, commands) via the external `tmuxp` tool.

Python 3.12+ rewrite of the original bash script: configuration moved to a TOML file, logic split into pure, unit-tested modules.

## Features

- **Interactive project picker** via fzf: the script collects a list of directories and inline workspaces from configured locations, sorts directories by frequency of use (via zoxide) and shows them in a convenient multi-select.
- **Non-interactive launch**: pass directory paths via the `switch` subcommand or inline workspaces via the `session` subcommand — fzf is not invoked.
- **Multiple sessions**: selecting several projects creates a separate tmux session for each one.
- **Session auto-creation**: if a session with the required name already exists and belongs to the same directory, it is reused instead of being recreated.
- **Workspace provisioning**: inline tmuxp workspaces build their exact windows/panes/layouts via tmuxp, and each built session is stamped with a marker (a fingerprint of the definition) so it is recognized and reused on later runs — never by session name.
- **Smart switching**: depending on the context, the script either attaches to the first session, calls `tmux choose-session` (when already inside tmux), or performs a plain `tmux attach`.
- **zoxide statistics**: every opened directory is added to zoxide (`zoxide add`), and more frequently used projects appear higher in the picker.
- **Configuration validation**: before an interactive run, the script verifies that all configured directories exist and all configured workspaces are valid; otherwise it prints a list of problems.
- **Dot-free session names**: dots in directory names are replaced with underscores (e.g. `my.project` → `my_project`).
- **Collision-safe session names**: duplicate basenames never share a session — the second and later ones get a numeric suffix (`dup`, `dup-2`, `dup-3`); an existing session is reused only when it points at the same directory, so you never silently land in someone else's cwd.

## Dependencies

| Dependency | Purpose | Required |
|---|---|---|
| [tmux](https://github.com/tmux/tmux) | session management | yes |
| [fzf](https://github.com/junegunn/fzf) | interactive picker (`--tmux` flag) | yes (for interactive mode) |
| [tmuxp](https://github.com/tmux-python/tmuxp) | provisioning workspace sessions (`tmuxp load`) | yes (for workspace sessions) |
| [PyYAML](https://pyyaml.org/) | workspace YAML parsing/validation (Python dependency) | yes |
| [zoxide](https://github.com/ajeetdsouza/zoxide) | sorting projects by frequency of use | no (optional) |
| [uv](https://github.com/astral-sh/uv) | installation and running | for installation only |

If `zoxide` is missing, the script keeps working: all directories get a zero "weight" and the ordering follows the order of the list.

## Installation

Install the console script into your `~/.local/bin` (uses a dedicated uv-managed environment):

```bash
cd multi-sessionizer-project
uv tool install .
```

Alternatively, run it straight from the project without installing:

```bash
uv run multi-sessionizer
```

or create a symlink to the project's console script:

```bash
ln -s "$(pwd)/.venv/bin/multi-sessionizer" ~/.local/bin/
```

## Configuration

Configuration lives in `~/.config/multi-sessionizer/config.toml` (override the path with the `MULTI_SESSIONIZER_CONFIG` environment variable). **The file is required** — there are no built-in defaults; you are expected to write your own. Every key is optional, and a missing key simply means an empty list. Environment variables (`$HOME`, ...) and `~` are expanded in all paths.

| Key | What it adds to the list |
|---|---|
| `project_roots_depth_1` | project roots searched 1 level deep: their direct subdirectories become entries |
| `project_roots_depth_2` | project roots searched 2 levels deep: subdirectories and their direct children become entries |
| `additional_dirs` | directories added to the list directly |
| `tmuxp_workspaces` | inline tmuxp workspace YAML strings, one per picker entry |

Hidden directories (starting with `.`, e.g. `.git`, `.config`) are listed in the picker like any other directory.

```toml
project_roots_depth_1 = [
    "$HOME/personal",
]

project_roots_depth_2 = [
    "$HOME/work",
]

additional_dirs = [
    "$HOME/obsidian-vault",
    "$HOME/.config/dotfiles",
]

tmuxp_workspaces = ["""
session_name: "workbench"
start_directory: "$HOME/workbench"
windows:
  - window_name: editor
    panes:
      - shell_command: vim
  - window_name: shell
    shell_command: "make dev"
"""]
```

## Workspaces

A **workspace** is a full tmuxp session definition (windows, panes, layouts,
start directory, shell commands) supplied **inline** — either as a string in
`tmuxp_workspaces` in the config file, or as an argument to the `session`
subcommand. Each configured string is one picker entry; each `session`
argument is one workspace.

```bash
multi-sessionizer session 'session_name: "project"
windows:
  - shell_command: "make dev"
'
```

When provisioned, the workspace builds its exact session via
`tmuxp load -d --no-progress -s <name> <config>`, and the session is stamped
with a marker — a fingerprint of the definition — so later runs recognize and
switch to it (never by session name). The declared `session_name` is honored
verbatim; a workspace without one gets a deterministic `msz-<fingerprint[:12]>`
name.

**Validation**: before an interactive run every configured workspace is
validated, and the `session` subcommand validates its input before building.
Invalid definitions are rejected with a specific message and no session is
created:

- invalid YAML (parse error);
- a root that is not a mapping;
- `windows` missing, not a list, or empty;
- `session_name` present but not a string.

The YAML itself is never `~`/environment-expanded by the tool (tmuxp governs
path expansion); paths inside a definition are not pre-validated.

**Array-readiness**: the domain models a selection as a flat collection of
session specs, so a future "one entry / one CLI parameter expands into several
sessions" is a surface-only change — the per-spec dedup and provisioning rules
stay the same.

## Usage

### Interactive mode

Just run the script without arguments:

```bash
multi-sessionizer
```

An fzf picker opens (in tmux mode) with the `Project > ` prompt. You can mark several entries at once with the `Tab` key.

The list contains:

- all top-level directories inside `project_roots_depth_1`;
- all directories up to the second level inside `project_roots_depth_2`;
- the directories from `additional_dirs`;
- the inline workspaces from `tmuxp_workspaces` (shown as `[tmuxp] <label>` lines).

Directories are sorted by frequency of use (zoxide); workspace entries are appended to the end of the list.

### Non-interactive mode (`switch`)

Pass the directory paths via the `switch` subcommand — no interactive picker needed:

```bash
multi-sessionizer switch /path/to/project
multi-sessionizer switch /path/to/project1 /path/to/project2
```

Everything after `switch` is taken verbatim as paths, so a leading `-` is fine and no `--` separator is ever needed. `--help`/`--version` are top-level flags only:

```bash
multi-sessionizer --help
multi-sessionizer --version
```

### Inline workspaces (`session`)

Pass one or more inline tmuxp workspaces on the command line:

```bash
multi-sessionizer session 'session_name: "project"
windows:
  - shell_command: "make dev"
'
```

Each argument is one workspace definition (YAML). The session is provisioned with `tmuxp load -d --no-progress -s <name> <config>`, stamped with the marker, and reused on later runs. The `session` subcommand does not read the config file — each workspace passed on the CLI is self-contained.

Exit codes: `0` — success (including `--help`/`--version`), `1` — a bad path, an invalid workspace, a configuration problem, or a provisioning failure, `2` — an unknown command.

Behavior:

- a path to a **directory** → tmux session named after its `basename` (dots replaced with `_`), with the folder itself as the working directory; if that name already belongs to a different directory, a numeric suffix is appended (`dup`, `dup-2`, …);
- an inline **workspace** → a tmux session reproduced from the definition, named after its declared `session_name` (or a deterministic `msz-<fingerprint[:12]>` fallback), with the marker stamped so a later run switches to it instead of duplicating it;
- multiple selections → one session per entry;
- mixed selections → directories are processed first, then workspaces;
- if a `switch` argument is neither a directory nor a file → the error `Not a directory or file: <path>` is printed and the script exits with code `1`;
- if a `switch` argument is a file → `File paths are not supported: <path>` and exit code `1`.

## What the script does after a selection

The connection logic is the same for both modes:

| Situation | Action |
|---|---|
| Not in tmux, tmux server not running | `tmux attach` to the first created session |
| Already inside tmux | `tmux choose-session` (interactive session picker) |
| tmux server is running, but you are outside | plain `tmux attach` |

If exactly one project was selected:

- outside tmux → `tmux attach -t <name>`;
- inside tmux → `tmux switch-client -t <name>` (instant switch of the current window).

If you opened the picker but closed it without selecting anything (`Esc`) — the script simply exits.

## Development

The project uses [uv](https://github.com/astral-sh/uv), [pytest](https://pytest.org) and [ruff](https://github.com/astral-sh/ruff).

```bash
uv sync                # create the environment
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```

The code is split into three strictly separated layers:

| Layer | Responsibility | Modules |
|---|---|---|
| `domain` | pure business logic, no I/O | `models` (DTOs), `naming`, `rank`, `plan`, `run` |
| `app` | thin wiring, DTO + adapter-contract ownership | `configuration`, `ports`, `flows` |
| `infrastructure` | all side effects (subprocess, filesystem, environment, terminal) | `config_loader`, `discovery`, `classifier`, `runner`, `messages` |

Dependency direction is a single rule: `domain` imports nothing, `app` imports
`domain` only, `infrastructure` imports both. The domain owns the DTOs
(`Selection`, `RuntimeSnapshot`, `Command`/`CommandPlan`); the app owns the
`Configuration` DTO and the adapter contracts (protocols) that infrastructure
implements; external tools (tmux, fzf, zoxide, pgrep) are invoked only through
infrastructure adapters, so any adapter (e.g. the command executor) can be
replaced without touching the domain or the app wiring. The top-level modules
(`cli.py`, `config.py`, `discovery.py`, `rank.py`, `naming.py`, `decisions.py`,
`runner.py`) are zero-logic re-export facades kept so the public import paths
stay unchanged.

### Reinstalling into PATH

After changing the source, rebuild and reinstall the console script:

```bash
./scripts/install.sh
```

This builds a fresh wheel and force-installs it. Note that `uv tool upgrade` is
not enough for a local-path install: with an unchanged version it reuses a
stale cached wheel and the installed binary keeps the old code.

### Performance

Directory discovery is guaranteed to touch only the configured levels, never
the whole tree — enforced by the `test_scan_cost_is_bounded_by_max_depth` test
(a regression to a full-tree walk fails it deterministically). For a live
measurement against your real config:

```bash
uv run scripts/benchmark.py
```

## Differences from the original bash version

- **Configuration** moved from hardcoded arrays at the top of the script into `~/.config/multi-sessionizer/config.toml` and is now **required**: the personal defaults were removed, so the tool refuses to start without a config file (printing an example skeleton). The non-interactive mode works without a config.
- **zoxide sorting fixed**: the bash version called `zoxide query -l` without `--score`, so the score parsing was a silent no-op and the list was never actually sorted by frequency. The Python version uses `zoxide query -l -s` and sorts correctly.
- **Mixed selections**: the bash version processed a single directory and then exited early, silently skipping anything else passed alongside it. The Python version processes all selected entries — directories first, then workspaces — with a single post-step.
- **Hidden directories are listed**: the bash version excluded directories with a hidden component (`.git`, `.config`, ...) and, as a side effect, silently ignored whole project roots whose own path contained a dot (e.g. `$HOME/.config/dotfiles`). The Python version lists hidden directories like any other and honors every configured root.
- **Faster discovery**: the bash version used `find -maxdepth`, the Python version prunes the traversal at the configured depth too, so deep trees are never walked.
- **Session existence check**: instead of one `tmux has-session` call per path, the existing sessions are queried once with `tmux list-sessions`.