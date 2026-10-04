# Quickstart: Named Session Groups — validation guide

End-to-end validation scenarios that prove the feature works. References the
contracts and data model instead of duplicating them.

## Prerequisites

- `multi-sessionizer` installed (`uv tool install .` or `./scripts/install.sh`).
- `tmux`, `fzf`, `zoxide`, `tmuxp` on `PATH`.
- A config file at `~/.config/multi-sessionizer/config.toml` (or set
  `MULTI_SESSIONIZER_CONFIG`).
- **tmux safety**: run anything that creates/kills sessions under
  `scripts/tmux-sandbox.sh -- <command>` (see `AGENTS.md`). Never run
  `tmux kill-server` on your live server; inspect sessions by name.

## Scenario A — Unified `sessions` surface loads (SC-004)

**Setup**: config with a directory string, a workspace string, and a group:

```toml
sessions = [
  "/tmp/proj-a",
  'session_name: "ws-one"
windows:
  - shell_command: "vim"',
  { name = "stack",
    sessions = ["/tmp/proj-b", 'session_name: "ws-two"\nwindows:\n  - shell_command: "htop"'] },
]
```

**Run**:
```bash
mkdir -p /tmp/proj-a /tmp/proj-b
scripts/tmux-sandbox.sh -- multi-sessionizer --help
```
`--help` only checks the CLI; to exercise the picker surface use a fake picker in
tests (Scenario D). **Expected**: config parses; `--help` exits 0; no parse or
classification error. With a fake-picker harness, the picker lists exactly
`/tmp/proj-a`, `[tmuxp] ws-one`, and `[group] stack` (one entry per element).

## Scenario B — One pick selects and provisions a whole group (SC-002)

**Setup**: as Scenario A, using the sandbox with an injected picker that returns
`[group] stack`.

**Run / verify**:
```bash
scripts/tmux-sandbox.sh -- <interactive run with picker returning "[group] stack">
tmux list-sessions
```
**Expected**: exactly 3 distinct sessions for the group (`/tmp/proj-b` dir session
+ the `ws-one`… group members), i.e. one session per member; the user lands
attached to one of them.

## Scenario C — Opening a group twice does not duplicate (SC-003)

**Setup**: Scenario B, then run it again with the same group selection.

**Verify**: `tmux list-sessions` still shows exactly 3 sessions (per-entry reuse),
not 6.

## Scenario D — Behavior parity for directory / workspace flows (SC-001)

**Run** the existing unit suite — domain planning must be byte-identical:
```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format . --check
```
**Expected**: the existing directory and workspace planning tests
(`test_decisions.py`, `test_plan_workspaces.py`) pass **unchanged**; only
config-surface tests that referenced the removed `additional_dirs`/
`tmuxp_workspaces` keys are rewritten for `sessions`.

## Scenario E — Removed keys rejected (SC-005)

**Setup**: config that still uses `additional_dirs` or `tmuxp_workspaces`.

**Run**: any interactive run (sandboxed).

**Expected**: exit 1 with a clear message naming the removed key (e.g. the
`additional_dirs` key is no longer supported; use `sessions`), and **0** sessions
created.

## Scenario F — Malformed groups rejected (SC-006)

**Setup**: one broken group at a time — missing `name`; empty `sessions`; a member
that is neither a directory nor a valid workspace; a nested group.

**Run**: interactive run (sandboxed).

**Expected**: exit 1, a **specific** message for each case (see
[`cli-contract.md`](./contracts/cli-contract.md)), and **0** sessions created.

## What this does NOT cover

Implementation code, migrations, and full test suites belong in `tasks.md` (Phase 2,
not produced by `/speckit.plan`). Group provisioning internals (picker label
disambiguation, label→entry maps) are detailed in
[`app-ports.md`](./contracts/app-ports.md) and [`data-model.md`](./data-model.md).