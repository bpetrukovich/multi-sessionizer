# Quickstart: Validating the Layered-Architecture Refactor

Runnable validation scenarios that prove the refactor works end-to-end without
reimplementing the tool. Links to the contracts instead of duplicating them.

## Prerequisites

- Python 3.12+ with `uv` (or the existing `.venv/`).
- Working tree on branch `001-layered-architecture`.
- External tools (`tmux`, `fzf`, `zoxide`) NOT required for steps 1–4; required only
  for the manual smoke test (step 5).

> Note: `uv run pytest` fails to spawn `pytest` in some environments (permission
> denied). Use `.venv/bin/python -m pytest` when that happens.

## 1. Behavior parity gate (SC-001, US2)

```bash
.venv/bin/python -m pytest -q
```

**Expected**: all 71 pre-existing tests pass **unchanged**. This proves exit codes,
printed output, and every pinned tmux/zoxide command sequence survived the refactor
exactly.

## 2. Domain isolation gate (SC-002, US1)

Run the domain tests with no external tools reachable and no `TMUX` env var:

```bash
env -u TMUX .venv/bin/python -m pytest tests/test_decisions.py tests/test_naming.py tests/test_rank.py -q
```

**Expected**: all planning tests pass with zero subprocess/filesystem/environment
dependency. To make the check stronger, temporarily rename the `tmux`/`fzf`/`zoxide`
binaries (or run in a container without them) and re-run — the planning tests never
invoke them.

**Determinism**: the same `Selection` + `RuntimeSnapshot` always yields the identical
`CommandPlan` (reuse of existing sessions instead of duplicates is covered by
`test_existing_session_reused_when_same_path`).

## 3. Static layer-boundary check (SC-003/SC-004)

```bash
.venv/bin/python -m pytest tests/ -q && \
  grep -rEl "subprocess|os\.environ|os\.path\.realpath|import app|import infrastructure" \
    src/multi_sessionizer/domain/ || echo "DOMAIN CLEAN"
```

**Expected**: `DOMAIN CLEAN` (or the dedicated boundary test added in implementation
passes). Domain imports nothing from app/infrastructure and performs no
subprocess/environment/filesystem calls. Every behavioral module lives in exactly one
layer; the top-level legacy modules are zero-logic re-export facades.

## 4. App wiring gate (FR-020, US4)

Run the new app-layer tests that inject fake adapters into `FlowDeps`:

```bash
.venv/bin/python -m pytest tests/test_app_flows.py -q   # added in implementation
```

**Expected**: with a fake `CommandExecutor` (and fake probe/picker/classifier) injected,
a full selection flows through `interactive_flow`/`switch_flow` and the expected
`CommandPlan` is observed with **no real subprocess executed**. Swapping the executor for
a fake touches only the wiring line, not domain or app flow code.

## 5. Console-script smoke test (US2)

With real tools installed and a valid config present:

```bash
uv tool install .   # or ./scripts/install.sh
multi-sessionizer --help            # usage text, exit 0
multi-sessionizer --version         # "multi-sessionizer 0.1.1", exit 0
multi-sessionizer nonsense          # exit 2, "unknown command"
multi-sessionizer /nonexistent/xyz  # exit 1, "Not a directory or file"
MULTI_SESSIONIZER_CONFIG=/tmp/nope.toml multi-sessionizer   # exit 1, config guidance
multi-sessionizer switch /some/real/dir /some/file.py       # runs tmux/zoxide sequence
```

**Expected**: byte-identical output and exit codes to the pre-refactor tool for every
invocation; `switch` produces the same ordered tmux/zoxide commands.

## 6. Quality gates

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format . --check
```

**Expected**: green. (Constitution dev-workflow gate.)

## Contracts & data model references

- CLI exit codes / output: [`contracts/cli-contract.md`](./contracts/cli-contract.md)
- Domain DTOs & command sequences: [`contracts/domain-contracts.md`](./contracts/domain-contracts.md)
- App adapter contracts & `FlowDeps`: [`contracts/app-ports.md`](./contracts/app-ports.md)
- Entities & layer rules: [`data-model.md`](./data-model.md)