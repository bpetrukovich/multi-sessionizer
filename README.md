# multi-sessionizer

A tool for quickly creating and switching between tmux project sessions. It lets you spin up working environments for multiple directories and files in a couple of keystrokes: each selected directory gets its own tmux session (created or reused), and each file gets a session with the nvim editor already open.

Python 3.12+ rewrite of the original bash script: configuration moved to a TOML file, logic split into pure, unit-tested modules.

## Features

- **Interactive project picker** via fzf: the script collects a list of directories and files from configured locations, sorts them by frequency of use (via zoxide) and shows them in a convenient multi-select.
- **Non-interactive launch**: pass directory and file paths as arguments directly — fzf is not invoked.
- **Multiple sessions**: selecting several projects creates a separate tmux session for each one.
- **Session auto-creation**: if a session with the required name already exists, it is reused instead of being recreated.
- **Editor launch**: when a file is selected, `nvim <file>` is automatically opened in the created session.
- **Smart switching**: depending on the context, the script either attaches to the first session, calls `tmux choose-session` (when already inside tmux), or performs a plain `tmux attach`.
- **zoxide statistics**: every opened directory is added to zoxide (`zoxide add`), and more frequently used projects appear higher in the picker.
- **Configuration validation**: before an interactive run, the script verifies that all configured directories and files exist; otherwise it prints a list of problems.
- **Dot-free session names**: dots in directory names are replaced with underscores (e.g. `my.project` → `my_project`).

## Dependencies

| Dependency | Purpose | Required |
|---|---|---|
| [tmux](https://github.com/tmux/tmux) | session management | yes |
| [fzf](https://github.com/junegunn/fzf) | interactive picker (`--tmux` flag) | yes (for interactive mode) |
| [nvim](https://github.com/neovim/neovim) | opening selected files | yes (if you pick files) |
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
| `additional_files` | files added to the list directly |

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
    "$HOME/.config/nvim",
]

additional_files = [
    "$HOME/.config/fish/config.fish",
    "$HOME/.tmux.conf",
]
```

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
- the files from `additional_files`.

Directories are sorted by frequency of use (zoxide); files are simply appended to the end of the list.

### Non-interactive mode (arguments)

Pass the paths as arguments — no interactive picker needed:

```bash
multi-sessionizer /path/to/project
multi-sessionizer /path/to/project1 /path/to/project2
multi-sessionizer /path/to/file.md
multi-sessionizer /path/to/project /path/to/file.py
```

Behavior:

- a path to a **directory** → tmux session named after its `basename` (dots replaced with `_`), with the folder itself as the working directory;
- a path to a **file** → tmux session in the file's directory with `nvim <file>` running;
- multiple paths → one session per path;
- mixed paths → directories are processed first, then files;
- if an argument is neither a file nor a directory → the error `Not a directory or file: <path>` is printed and the script exits with code `1`.

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

The code is split into pure, unit-tested modules:

| Module | Responsibility |
|---|---|
| `config.py` | TOML config loading, defaults, existence validation |
| `discovery.py` | directory/file collection (depth 1/2, pruned traversal) |
| `rank.py` | zoxide score parsing and ranking |
| `naming.py` | session name generation |
| `cli.py` | argument classification |
| `decisions.py` | pure planning of the tmux/zoxide command sequence |
| `runner.py` | thin subprocess wrapper around tmux/fzf/zoxide/pgrep |
| `main.py` | wiring and the entry point |

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
- **Mixed dir + file selections**: the bash version processed a single directory and then exited early, silently skipping any files passed alongside it. The Python version processes all selected paths.
- **Hidden directories are listed**: the bash version excluded directories with a hidden component (`.git`, `.config`, ...) and, as a side effect, silently ignored whole project roots whose own path contained a dot (e.g. `$HOME/.config/nvim`). The Python version lists hidden directories like any other and honors every configured root.
- **Faster discovery**: the bash version used `find -maxdepth`, the Python version prunes the traversal at the configured depth too, so deep trees are never walked.
- **Session existence check**: instead of one `tmux has-session` call per path, the existing sessions are queried once with `tmux list-sessions`.