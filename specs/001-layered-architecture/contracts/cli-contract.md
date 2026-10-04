# CLI Contract

**External interface** of the tool (the `multi-sessionizer` console script). Must be
preserved byte-for-byte by the refactor (FR-016/FR-017, US2).

## Usage

```
usage: multi-sessionizer [-h] [--version] [switch PATH ...]

Create and switch between tmux project sessions.

With no arguments, opens the interactive fzf picker.

subcommands:
  switch PATH [PATH ...]   open the given directories/files non-interactively

options:
  -h, --help     show this help message and exit
  --version      show program's version number and exit
```

## Commands

| Invocation | Behavior | Exit code |
|------------|----------|-----------|
| (no args) | interactive flow: load config → discover → rank → fzf pick → classify → run | 0 / 1 |
| `switch PATH...` | classify each path (dir or file); run the plan | 0 / 1 |
| `-h`, `--help` | print usage to stdout | 0 |
| `--version` | print `multi-sessionizer <version>` to stdout | 0 |
| anything else | print error to stderr + "Try ... --help" | 2 |

## Exit codes (FR-016)

| Code | Meaning |
|------|---------|
| 0 | success (including empty fzf selection) |
| 1 | bad path (switch) or bad/missing config (interactive) |
| 2 | unknown command |

## Error output (unchanged)

1. **Unknown command** (`multi-sessionizer nonsense`) → stderr:
   ```
   multi-sessionizer: error: unknown command: nonsense
   Try 'multi-sessionizer --help' for more information.
   ```
2. **Missing config** (interactive) → stderr: `Configuration file not found: <path>`,
   blank line, `Create it with an example:`, the example TOML block, and the
   `MULTI_SESSIONIZER_CONFIG` override hint (exact text in `main.py`/`CONFIG_EXAMPLE`).
3. **Missing files/dirs in config** → stderr lists them under
   `The following files do not exist:` / `The following directories do not exist:`.
4. **`switch` bad path** → stderr: `Not a directory or file: <arg>`.

## tmux/zoxide command sequence (parity, US2)

For every scenario the exact ordered command sequence is identical to the pre-refactor
tool (see `test_decisions.py` for the pinned sequences and `domain-contracts.md`).

## Related

- Domain planning rules: [`domain-contracts.md`](./domain-contracts.md)
- Entity definitions: [`../data-model.md`](../data-model.md)