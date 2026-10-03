# multi-sessionizer

A script for quickly creating and switching between tmux project sessions. It lets you spin up working environments for multiple directories and files in a couple of keystrokes: each selected directory gets its own tmux session (created or reused), and each file gets a session with the nvim editor already open.

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
| `find`, `realpath`, `pgrep`, `basename`, `dirname` | coreutils utilities | yes |

If `zoxide` is missing, the script keeps working: all directories get a zero "weight" and the ordering follows the order of the list.

## Installation

Copy the script into a directory from `$PATH` and make it executable:

```bash
cp multi-sessionizer ~/.local/bin/
chmod +x ~/.local/bin/multi-sessionizer
```

## Usage

### Interactive mode

Just run the script without arguments:

```bash
multi-sessionizer
```

An fzf picker opens (in tmux mode) with the `Project > ` prompt. You can mark several entries at once with the `Tab` key.

The list contains:

- all top-level directories inside `project_dirs_depth_1`;
- all directories up to the second level inside `project_dirs_depth_2`;
- the directories from `extra_dirs`;
- the files from `files`.

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

## Configuration

All project sources are defined at the top of the file in four arrays:

| Variable | What it adds to the list |
|---|---|
| `project_dirs_depth_1` | recursion depth 1: direct subdirectories of the listed directories |
| `project_dirs_depth_2` | recursion depth 2: subdirectories and their direct children |
| `extra_dirs` | directories added to the list directly |
| `files` | files added to the list directly |

Hidden directories (starting with `.`) are excluded from the search (`-not -path '*/.*'`).

Example configuration:

```bash
project_dirs_depth_1=(
  "$HOME/personal"
)

project_dirs_depth_2=(
  "$HOME/work"
)

extra_dirs=(
  "$HOME/obsidian-vault"
  "$HOME/.config/nvim"
)

files=(
  "$HOME/.config/fish/config.fish"
  "$HOME/.tmux.conf"
)
```
