# Quickstart: Validating tmuxp Config Support

Runnable validation scenarios that prove the feature works end-to-end. Links to the
contracts and data model instead of duplicating them.

## Prerequisites

- Python 3.12+ with `uv` (or the existing `.venv/`).
- Working tree on branch `002-tmuxp-config-support`.
- `tmuxp` installed as an external tool (`uv tool install tmuxp` or
  `pipx install tmuxp`); `tmux`, `fzf`, `zoxide` as today.
- External tools are NOT required for steps 1–4 (pure tests); `tmuxp` is only needed
  for the end-to-end smoke test (step 5).

> Note: `uv run pytest` may fail to spawn `pytest` in some environments (permission
> denied). Use `.venv/bin/python -m pytest`. Everything that creates/kills tmux
> sessions MUST run under `scripts/tmux-sandbox.sh`.

## 1. Behavior parity gate (SC-001)

```bash
.venv/bin/python -m pytest -q
```

**Expected**: all pre-existing **directory-related** tests pass unchanged — identical
tmux/zoxide command sequences, session naming, collision suffixes, post-step logic.
File/nvim tests are gone (SC-007); new workspace tests are green.

## 2. Pure workspace domain tests (US1, FR-018/FR-022)

```bash
env -u TMUX .venv/bin/python -m pytest tests/test_workspace.py tests/test_plan_workspaces.py tests/test_domain.py -q
```

**Expected**: with no external tools reachable and no `TMUX` env var:

- `fingerprint` is deterministic and name-independent: the same definition yields the
  same marker even after a session-name disambiguation;
- `validate_workspace` rejects: invalid YAML, a non-mapping root, missing/empty
  `windows`, and a non-string `session_name`; accepts a valid single-window workspace;
- `desired_name` honors a declared `session_name` and falls back to `msz-<fp[:12]>`;
- `plan` reuses a session whose snapshot `markers` match (whatever its name), creates
  a disambiguated name for a taken desired name, never switches into a foreign session,
  emits `tmuxp load -d --no-progress -s <name> <cfg>` + marker `set-option` for
  creations, and emits **no** `tmuxp` command for reuses;
- the single-plan/single-post-step shape holds for mixed dir+workspace selections.

## 3. Static layer-boundary check (SC-003/SC-004)

```bash
.venv/bin/python -m pytest tests/test_layer_boundaries.py -q && \
  grep -rEl "subprocess|os\.environ|os\.path\.realpath|import app|import infrastructure" \
    src/multi_sessionizer/domain/ || echo "DOMAIN CLEAN"
```

**Expected**: `DOMAIN CLEAN`; the new `domain/workspace.py` satisfies the same purity
rules. External tools (`tmuxp` included) are invoked only through `infrastructure/`.

## 4. App wiring + CLI gates (FR-020, US4)

```bash
.venv/bin/python -m pytest tests/test_app_flows.py tests/test_main.py tests/test_config.py -q
```

**Expected** (with fake adapters injected into `FlowDeps`):

- a fake executor observes the full workspace plan with **no real subprocess executed;
- `interactive_flow` validates workspaces before the picker and reports problems
  without creating a session;
- a config containing the removed `additional_files` key is silently ignored
  (the key is not loaded);
- `main(["session", "<yaml>"])` routes to the session flow; `main(["switch", file])`
  errors with `File paths are not supported` (exit 1).

## 5. End-to-end smoke test (US1–US3, SC-002–SC-006)

Sandboxed so the live tmux tree is never touched. With `tmuxp` installed:

```bash
scripts/tmux-sandbox.sh --zoxide-isolated -- \
  env MULTI_SESSIONIZER_CONFIG=/tmp/msz-smoke/config.toml \
  .venv/bin/multi-sessionizer
```

Prepare `/tmp/msz-smoke/config.toml` with `additional_dirs` plus a `tmuxp_workspaces`
entry, then run the picker (or `session` subcommand) inside the sandbox and verify:

- **SC-002/SC-003**: selecting a multi-window/multi-pane workspace creates exactly one
  session whose windows/panes/layouts/start directory/commands match the definition
  (`tmux list-sessions`, `tmux list-windows -t <name>`, `tmux list-panes -t <name>`);
  selecting the same entry again **switches** to it (still one session);
- **SC-004**: a deliberately misnamed foreign session without the marker is never
  switched into — the entry provisions its own session under a disambiguated name;
- **SC-005**: two workspaces declaring the same `session_name` produce two distinct
  sessions, each later recognized by its own marker;
- **SC-006**: deleting any tool-created temp/state directory and restarting the sandbox
  tmux server does not change switch-vs-create behavior (decisions derive from the live
  tmux marker alone);
- **US3 restart**: after `tmux kill-server` inside the sandbox, re-running the entry
  makes a fresh, correct decision from live state (no files consulted);
- **FR-020**: with `tmuxp` hidden from `PATH`, a workspace run reports a clear error
  naming `tmuxp` and exits 1;
- **SC-008**: `multi-sessionizer session 'windows: []'` and other invalid YAML exit 1
  with a specific message and create no session.

## 6. Removal verification (SC-007)

```bash
grep -rniE "nvim|additional_files|collect_files|send-keys" src/ tests/ README.md \
  || echo "CLEAN"
.venv/bin/python -m pytest tests/test_config.py -q   # config no longer loads additional_files
```

**Expected**: `CLEAN` (plus the intended test updates); nvim/file references are absent
from code, tests, docs, and the dependency table.

## 7. Quality gates

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format . --check
```

**Expected**: green. (Constitution dev-workflow gate.)

## Contracts & data model references

- CLI exit codes / output: [`contracts/cli-contract.md`](./contracts/cli-contract.md)
- Domain DTOs, session marker, command sequences: [`contracts/domain-contracts.md`](./contracts/domain-contracts.md)
- App adapter contracts & `FlowDeps`: [`contracts/app-ports.md`](./contracts/app-ports.md)
- Entities & layer rules: [`data-model.md`](./data-model.md)
- Design decisions (tmuxp invocation, fingerprint, marker): [`research.md`](./research.md)