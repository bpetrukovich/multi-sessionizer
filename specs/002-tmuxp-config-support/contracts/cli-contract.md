# CLI Contract

**External interface** of the tool (the `multi-sessionizer` console script). The tmuxp
feature changes the surface (FR-008, FR-001) while preserving the exit-code contract
(FR-021): **0** success, **1** bad path/config/workspace/provisioning, **2** unknown
command.

## Usage

```
usage: multi-sessionizer [-h] [--version] [switch PATH ...] [session YAML ...]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]   open the given directories non-interactively
  session YAML [YAML ...]  provision the given inline tmuxp workspaces

options:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
```

## Commands

| Invocation | Behavior | Exit code |
|------------|----------|-----------|
| (no args) | interactive flow: load config → validate workspaces → discover dirs → rank → fzf pick → classify → run | 0 / 1 |
| `switch PATH...` | classify each path (directories only; files rejected with a clear error) → run the plan | 0 / 1 |
| `session YAML...` | validate each inline workspace (parse + structural) → provision/reuse → attach/switch | 0 / 1 |
| `-h`, `--help` | print usage to stdout | 0 |
| `--version` | print `multi-sessionizer <version>` to stdout | 0 |
| anything else | print error to stderr + "Try ... --help" | 2 |

`switch` and `session` take everything after the subcommand verbatim (no `--` separator
ever needed; leading `-` is fine).

## Exit codes (FR-021)

| Code | Meaning |
|------|---------|
| 0 | success (including empty fzf selection) |
| 1 | bad path (switch), bad/missing config (interactive), invalid workspace, missing `tmuxp`, or a provisioning failure |
| 2 | unknown command |

## Error output

1. **Unknown command** (`multi-sessionizer nonsense`) → stderr:
   ```
   multi-sessionizer: error: unknown command: nonsense
   Try 'multi-sessionizer --help' for more information.
   ```
2. **Missing config** (interactive) → stderr: `Configuration file not found: <path>`,
   blank line, `Create it with an example:`, the example TOML block (shows
   `tmuxp_workspaces`), and the `MULTI_SESSIONIZER_CONFIG` override hint.
3. **Missing dirs in config** (interactive) → stderr lists them under
   `The following directories do not exist:`. (The files variant is removed.)
4. **Invalid workspace(s)** (interactive pre-run and `session`) → stderr lists each
   problem (e.g. YAML parse error, `windows` missing/empty, `session_name` not a
   string) and exits 1 — no session is created.
5. **`switch` bad path** → stderr: `Not a directory or file: <arg>` (exit 1).
6. **`switch` file path** → stderr, exit 1: `File paths are not supported: <path>`.
7. **`tmuxp` not installed** (workspace flow) → stderr, exit 1:
   `tmuxp is required for workspace sessions but was not found on PATH.`
8. **tmuxp build failure** (workspace flow) → stderr, exit 1: the tmuxp failure
   surfaced with the exit-code contract preserved (tmuxp's own interactive error
   prompt on a rare mid-build failure is a documented tmuxp behavior).

## tmux/zoxide/tmuxp command sequences

- Directory flows: byte-for-byte unchanged (see `domain-contracts.md`); `switch`
  produces the same ordered zoxide/tmux commands as today for directory arguments.
- Workspace flows: `tmuxp load -d --no-progress -s <name> <temp-config>` then
  `tmux set-option -t <name> @multi-sessionizer-marker <fingerprint>`, followed by
  attach/switch (single) or the shared post-step (multi).

## Related

- Domain planning rules: [`domain-contracts.md`](./domain-contracts.md)
- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Entity definitions: [`../data-model.md`](../data-model.md)