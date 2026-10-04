# multi-sessionizer — agent & contributor notes

## tmux safety (READ BEFORE RUNNING ANY TMUX COMMAND)

A live tmux session is usually attached to the default server socket
(`/tmp/tmux-$UID/default`, see `$TMUX`). Two tmux 3.4 traps have already cost a
whole server tree:

1. **`$TMUX_TMPDIR`/`$TMPDIR` are silently ignored when the directory does not
   already exist.** tmux then falls back to the default socket. Always
   `mkdir` the sandbox directory first, or use an explicit `tmux -S <path>`.
2. **`tmux kill-server` kills every session on the targeted server.** Never run
   it while `$TMUX` is set or against the default socket. Kill test sessions by
   name (`tmux kill-session -t <name>`), and kill only servers you created
   yourself via `-S` or a pre-created sandbox directory.

Rules:

- NEVER run `tmux kill-server` on the default/current server.
- NEVER "isolate" tmux by only setting `TMUX_TMPDIR` without pre-creating the
  directory AND unsetting `$TMUX`.
- For anything that creates/kills tmux sessions (smoke tests, `switch` runs),
  use `scripts/tmux-sandbox.sh -- <command>` — it pre-creates the socket dir,
  unsets `$TMUX`, and cleans up only its own throwaway server.
- `zoxide add` and `tmux` commands that the tool runs have real side effects;
  add `--zoxide-isolated` to the sandbox wrapper to sandbox zoxide too.

## Test & quality commands

`uv run pytest` may fail to spawn pytest (permission denied) — use:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format . --check
```

Behavior parity is the top priority: the existing test suite must pass
unchanged. Top-level modules under `src/multi_sessionizer/` are zero-logic
re-export facades; do not add logic to them. Domain (`src/multi_sessionizer/domain/`)
must stay free of subprocess/filesystem/environment access and
`os.path.realpath` (guarded by `tests/test_layer_boundaries.py`).
