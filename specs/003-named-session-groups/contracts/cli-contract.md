# CLI Contract

**External interface** of the tool (the `multi-sessionizer` console script). The
group feature changes the interactive picker surface while preserving the CLI
shape and exit-code contract (FR-012): **0** success, **1** bad path/config/
group/workspace/provisioning, **2** unknown command.

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

The `switch` and `session` subcommands are unchanged. `--help`/`--version` unchanged.

## Interactive picker (FR-004)

The fzf list mixes three line kinds:

| Line form | Meaning |
|-----------|---------|
| a directory path | a discovered root child or a top-level directory session entry |
| `[tmuxp] <label>` | a workspace session entry (feature 002) |
| `[group] <name>` | a named group — selecting it provisions every member session |

Duplicate displayed labels get a numeric suffix so every line is selectable
(FR-009 edge case). Empty selection → clean exit 0 (unchanged).

## Commands

| Invocation | Behavior | Exit code |
|------------|----------|-----------|
| (no args) | load config (reject removed keys / malformed `sessions`) → missing-dir check → discover dirs → rank → fzf pick → route selection (expand groups) → run | 0 / 1 |
| `switch PATH...` | classify each path (directories only; files rejected) → run | 0 / 1 |
| `session YAML...` | validate each inline workspace → provision/reuse → attach/switch | 0 / 1 |
| `-h`, `--help` | print usage to stdout | 0 |
| `--version` | print `multi-sessionizer <version>` to stdout | 0 |
| anything else | error to stderr + "Try … --help" | 2 |

## Exit codes (FR-012)

| Code | Meaning |
|------|---------|
| 0 | success (including empty fzf selection) |
| 1 | bad path (switch); bad/missing config, malformed group, missing dirs (interactive); invalid workspace; missing `tmuxp`; provisioning failure |
| 2 | unknown command |

## Error output (changes vs feature 002)

1. **Removed config keys** → stderr, exit 1:
   ```
   Configuration error: the 'additional_dirs' key is no longer supported; use 'sessions' instead.
   ```
   (identical wording for `tmuxp_workspaces`; no migration hint beyond naming the
   replacement — no compatibility shim).
2. **Malformed group** → stderr, exit 1, specific message per case, 0 sessions:
   - `Group is missing a 'name'.`
   - `Group '<name>' has an empty 'sessions' list.`
   - `Group '<name>' has an invalid member: <detail>.`
   - `Nested groups are not supported: group '<name>'.`
3. **Missing dirs in config** → stderr lists directory entries (top-level and
   group members) that do not exist, under `The following directories do not exist:`
   (unchanged style).
4. All other messages (unknown command, missing config example, invalid workspace,
   missing `tmuxp`, provisioning failure) unchanged from feature 002.

The `CONFIG_EXAMPLE` shown on a missing config now demonstrates the unified
`sessions` list (see [`config-contract.md`](./config-contract.md)).

## Related

- Config surface: [`config-contract.md`](./config-contract.md)
- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Domain planning rules: [`domain-contracts.md`](./domain-contracts.md)