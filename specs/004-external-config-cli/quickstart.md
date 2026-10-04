# Quickstart: External Config CLI

**Phase 1 validation guide** — runnable scenarios proving the feature works
end-to-end. This is a run/validation guide only; implementation detail lives in
`tasks.md` and the code. See [`contracts/`](./contracts/) for the exact behavior
and [`data-model.md`](./data-model.md) for the entities.

## Prerequisites

- The tool installed as the console script (`uv tool install .` or
  `./scripts/install.sh`).
- A working `~/.config/multi-sessionizer/config.toml` (any valid config).
- `tmux`, `fzf`, `zoxide`, `tmuxp` available.
- **Never run against the default/current tmux server.** Anything that
  creates/kills tmux sessions must run under `scripts/tmux-sandbox.sh -- <cmd>`
  (see `AGENTS.md`). The `external` commands themselves never touch tmux, so they
  are safe; the interactive/provisioning steps must be sandboxed.

## Setup for validation

Isolate the store so the developer's real store is never used:

```bash
export MULTI_SESSIONIZER_STORE="/tmp/msz-external-test/external.db"
mkdir -p /tmp/msz-external-test
```

## Scenario 1 — Add one entry of each type and verify the config is untouched

```bash
# a directory entry
multi-sessionizer external add "$HOME/tmp/msz-proj-a"

# an inline tmuxp workspace entry
multi-sessionizer external add 'session_name: "ext-ws"
windows:
  - shell_command: "echo hi"'

# a named group entry
multi-sessionizer external add '{ name = "ext-stack", sessions = [
  "'$HOME'/tmp/msz-proj-b",
  'session_name: "ext-svc"
windows:
  - shell_command: "echo svc"',
] }'
```

**Expected** (each prints a success confirmation, exit 0):

```
multi-sessionizer: added [external] /home/<u>/tmp/msz-proj-a
multi-sessionizer: added [external] ext-ws
multi-sessionizer: added [external] ext-stack
```

Verify the config file is byte-for-byte unchanged:

```bash
sha256sum ~/.config/multi-sessionizer/config.toml   # before
sha256sum ~/.config/multi-sessionizer/config.toml   # after — identical
```

## Scenario 2 — List the entries with type and deletion key

```bash
multi-sessionizer external list
```

**Expected** (exit 0), each row shows kind, picker label, and deletion key:

```
directory  [external] /home/<u>/tmp/msz-proj-a       /home/<u>/tmp/msz-proj-a
workspace  [external] ext-ws                         ext-ws
group      [external] ext-stack                      ext-stack
```

## Scenario 3 — See the external entries in the interactive picker

Run the picker (sandboxed — it provisions tmux sessions):

```bash
scripts/tmux-sandbox.sh -- multi-sessionizer
```

**Expected**: the fzf list shows the three `[external]` lines alongside the
config `[tmuxp]` / `[group]` / directory lines. Multi-select one external entry
and one config entry, accept — each is provisioned/switched exactly once in a
single plan (SC-006), and the external directory/workspace/group behave like
their config counterparts (FR-013).

## Scenario 4 — Delete by key and verify the session survives

```bash
multi-sessionizer external delete ext-ws        # by session name
multi-sessionizer external list                 # ext-ws gone, others remain
```

**Expected**: `ext-ws` no longer appears; exit 0 for both. If `ext-ws` had a
running session, `tmux list-sessions` (sandboxed) still shows it — deletion never
kills a live session (FR-014). Config file remains byte-for-byte unchanged.

## Scenario 5 — Error paths

```bash
multi-sessionizer external add "$HOME/tmp/msz-proj-a"   # duplicate
multi-sessionizer external delete does-not-exist        # not found
```

**Expected**:
- duplicate add → `External entry already exists: ...`, exit 1 (FR-005);
- delete not found → `No external entry with deletion key 'does-not-exist'.`,
  exit 1, store unchanged (FR-010);
- unknown verb → `multi-sessionizer external nope` → exit 2 (FR-011);
- `multi-sessionizer external add /definitely/not/a/dir` → invalid/invalid-path
  error, exit 1, nothing stored (FR-015).

## Scenario 6 — Corrupt store does not break config entries (FR-016)

```bash
echo "not a sqlite database" > "$MULTI_SESSIONIZER_STORE"
multi-sessionizer external list        # clear error, exit 1
scripts/tmux-sandbox.sh -- multi-sessionizer   # still shows config entries, runs
```

**Expected**: `external list` reports `External store error: ...` (exit 1); the
interactive run reports the error to stderr but still serves the config entries
and does not crash (FR-016).

## Scenario 7 — Concurrency (SC-005)

Run several add/list/delete invocations in parallel processes against the same
isolated `MULTI_SESSIONIZER_STORE`; afterwards the list is consistent, has no
duplicate directory entry, and no partially-applied delete is observed.

```bash
for i in 1 2 3 4 5; do multi-sessionizer external add "$HOME/tmp/msz-par-$i" & done; wait
multi-sessionizer external list
```

**Expected**: a coherent list with five entries, none duplicated; exit 0 (FR-003).

## Done criteria

- [ ] All three entry types add, list, and delete correctly (SC-002/SC-003).
- [ ] Config file checksum unchanged across every add/delete (SC-003, FR-001).
- [ ] Deleting an entry leaves any live session it provisioned running (SC-004).
- [ ] External and config entries mix in one multi-select, each provisioned once (SC-006).
- [ ] Concurrent run yields a consistent, non-torn store (SC-005).
- [ ] Existing test suite passes unchanged (`SC-001`; `.venv/bin/python -m pytest -q`,
  `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check`).