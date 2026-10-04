# CLI Contract

**External interface** of the tool (the `multi-sessionizer` console script). This
feature adds an `external` subcommand while preserving the CLI shape and the
exit-code contract (FR-011): **0** success, **1** bad path/config/entry/delete
key/store, **2** unknown command.

## Usage

```
usage: multi-sessionizer [-h] [--version]
                         [switch PATH ...] [session YAML ...]
                         [external add ENTRY | external list | external delete KEY]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]       open the given directories non-interactively
  session YAML [YAML ...]      provision the given inline tmuxp workspaces
  external add ENTRY           permanently add a directory / workspace / group
  external list                list externally added entries
  external delete KEY          delete an external entry by its key

options:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
```

`switch`, `session`, `--help`, `--version` are unchanged. `external` is new.

## Interactive picker (FR-004/FR-012)

The fzf list mixes four line kinds:

| Line form | Meaning |
|-----------|---------|
| a directory path | a discovered root child or a config directory session entry |
| `[tmuxp] <label>` | a config workspace session entry (feature 002) |
| `[group] <name>` | a config named group (feature 003) |
| `[external] <path\|name\|desired_name>` | an externally added directory / group / workspace (this feature) |

External entries are multi-selectable alongside config entries, share the same
switch-vs-create and per-entry dedup semantics, and are distinctly labeled
`[external]` (FR-012/FR-013). Empty selection → clean exit 0 (unchanged).

## Commands

| Invocation | Behavior | Exit code |
|------------|----------|-----------|
| (no args) | load config → missing-dir check → discover → rank → load external entries (warn on store failure, continue with config) → fzf pick → route selection (expand groups) → run | 0 / 1 |
| `switch PATH...` | classify each path (directories only) → run | 0 / 1 |
| `session YAML...` | validate each inline workspace → provision/reuse → attach | 0 / 1 |
| `external add ENTRY` | classify ENTRY (directory / workspace / group) → validate → store → confirm | 0 / 1 |
| `external list` | list type + label + deletion key per entry (empty → clean success) | 0 / 1 |
| `external delete KEY` | resolve KEY → precise delete (or not-found / ambiguous error) | 0 / 1 |
| `-h`, `--help` | print usage to stdout | 0 |
| `--version` | print `multi-sessionizer <version>` to stdout | 0 |
| anything else / `external <unknown>` | error to stderr + "Try … --help" | 2 |

## Exit codes (FR-011)

| Code | Meaning |
|------|---------|
| 0 | success (including empty fzf selection and empty `external list`) |
| 1 | bad path (switch); bad/missing config, malformed group, missing dirs (interactive); invalid workspace; missing `tmuxp`; provisioning failure; invalid `external add` entry; duplicate add; store unreadable/corrupt; delete not found / ambiguous |
| 2 | unknown command / unknown `external` verb |

## Deletion keys (FR-008/FR-009)

| Entry kind | Deletion key |
|------------|--------------|
| directory | the realpath-normalized path |
| workspace | the session name (`session_name` or the deterministic fallback) |
| group | the group name |

`external list` prints the key per entry so it is discoverable.

## Error output (additions vs feature 003)

1. **Invalid add entry** → stderr, exit 1, nothing stored (message reuses the
   config classifier wording; group/workspace structure problems reported
   specifically).
2. **Duplicate add** → stderr, exit 1:
   ```
   External entry already exists: <deletion key>.
   ```
3. **Delete not found** → stderr, exit 1, store unchanged:
   ```
   No external entry with deletion key '<key>'.
   ```
4. **Delete ambiguous** → stderr, exit 1, none removed (list the matches):
   ```
   External delete key '<key>' matches multiple entries: <paths|names>.
   No entry was removed.
   ```
5. **Store corrupt/unreadable** (list / interactive) → stderr, exit 1; the
   interactive run still serves config entries (FR-016):
   ```
   External store error: <detail>.
   ```
6. **Unknown `external` verb** → stderr, exit 2:
   ```
   multi-sessionizer: error: unknown external command: <verb>
   ```

All other messages (missing config example, invalid workspace, missing `tmuxp`,
provisioning failure) unchanged from feature 003.

## Store location

Store: `~/.local/state/multi-sessionizer/external.db`, overridable via the
`MULTI_SESSIONIZER_STORE` environment variable. The config file is never read for
external decisions and never written (FR-001). See
[`store-contract.md`](./store-contract.md).

## Related

- Store schema & concurrency: [`store-contract.md`](./store-contract.md)
- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Pure domain rules: [`domain-contracts.md`](./domain-contracts.md)