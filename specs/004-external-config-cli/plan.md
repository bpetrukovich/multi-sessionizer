# Implementation Plan: External Config CLI

**Branch**: `004-external-config-cli` | **Date**: 2026-10-05 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `/specs/004-external-config-cli/spec.md`

## Summary

Add a persistent, concurrent-safe external store so a user can **add, list, and
delete** picker entries (directory, inline tmuxp workspace, named group) from the
CLI without ever touching their own config file. The store is a sqlite3 database
(stdlib — **no new runtime dependency**), co-located under the tool's XDG state
directory. External entries are merged into the interactive picker on every run
under a distinct `[external]` label and behave identically to their config-file
counterparts (provisioning, marker-based switch-vs-create, per-entry dedup,
single-plan/single-post-step). The session runtime (`domain/plan.py`,
`domain/run.py`, `domain/workspace.py`) is untouched — external entries are
`SessionEntry` values, so feature 002/003 parity holds and SC-001 is preserved.
Deleting an external entry removes only its row, never a live tmux session.

The design keeps the unified `sessions` entry model (feature 003) as the storage
shape, reuses the pure classifier for add-input classification, adds a pure
domain module for external-specific rules (deletion-key resolution), a new
`ExternalStore` port implemented with sqlite in infrastructure, and three new
app flows. The config file is never read for external decisions and never
written.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`).

**Primary Dependencies**: PyYAML (existing, workspace-shape detection and
validation), plus existing external tools tmux / tmuxp / fzf / zoxide, and
stdlib `sqlite3`. **No new runtime dependencies** — sqlite3 is stdlib and is the
concurrency mechanism (FR-003), so constitution V's dependency justification is
satisfied without adding to the README dependency table.

**Storage**: SQLite database at `~/.local/state/multi-sessionizer/external.db`
(XDG state), overridable via a `MULTI_SESSIONIZER_STORE` environment variable.
One table `external_entries` with unique constraints for dedup; WAL mode + a
transaction per operation for concurrent-safe add/delete/list (FR-003). The
user's config file is neither read for external decisions nor written (FR-001).

**Testing**: `pytest` (`.venv/bin/python -m pytest -q`), `ruff check .`,
`ruff format . --check`. New pure domain module is unit-tested first; sqlite
store is tested via an in-memory DB with an isolated `MULTI_SESSIONIZER_STORE`.
All feature 002/003 tests pass unchanged (SC-001).

**Target Platform**: Linux terminal (tmux/fzf/zoxide/tmuxp available).

**Project Type**: CLI (tmux session manager).

**Performance Goals**: Not latency-critical (personal tool, tens of entries).
Concurrent add/delete/list must be serialized so no torn list or partially
applied write is ever observed (SC-005).

**Constraints**: Domain layer stays pure (PyYAML + stdlib only — no subprocess,
filesystem, environment, `os.path.realpath`). No backward compatibility (a
changed/removed surface is removed outright). Exit codes preserved: 0 / 1 / 2
(FR-011). Deleting an external entry never destroys a live tmux session
(FR-014, constitution Additional Constraints).

**Scale/Scope**: Small personal tool; one store per user; tens of entries.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|-----------|
| **I. CLI interface (MUST)** | PASS. New top-level `external` subcommand with `add`/`list`/`delete`; stdout/stderr and exit codes preserved (0 success / 1 bad path, config, entry, delete key, or store / 2 unknown command). |
| **II. Pure, test-first modules (NON-NEGOTIABLE)** | PASS. New `domain/external.py` is pure (stdlib + PyYAML only): add-input classification and deletion-key resolution have no side effects and are unit-tested first. All sqlite/file/env/terminal side effects stay in `infrastructure/external_store.py` and `infrastructure/messages.py`. Existing `plan`/`run`/`workspace` gain no side effects. |
| **III. TOML configuration** | PASS. The user's config file is untouched; the external store is a separate sqlite file. No built-in personal defaults. |
| **IV. Bounded performance** | PASS. Directory discovery unchanged and depth-bounded. External store access is O(entries) on an indexed key; no tree walks. |
| **V. Simplicity (YAGNI)** | PASS. sqlite3 is stdlib (no new dependency); one table, three operations, one new port, three new flows. No speculative abstractions. |

**Gate result**: No violations. Re-checked after design (see `data-model.md`).
Complexity table not required.

## Project Structure

### Documentation (this feature)

```text
specs/004-external-config-cli/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
src/multi_sessionizer/
├── main.py                      # CLI dispatch: + external add/list/delete (command table)
├── app/
│   ├── configuration.py         # unchanged (config file is not involved)
│   ├── ports.py                 # + ExternalStore protocol + ExternalAdd/Delete result types
│   └── flows.py                 # interactive_flow: merge [external] entries; + external_* flows
├── domain/
│   ├── models.py                # + ExternalEntry wrapper (or reuse SessionEntry)
│   ├── session_entries.py       # unchanged (classify_sessions reused)
│   ├── external.py              # NEW pure: classify_external_input, deletion_key, resolve_delete
│   ├── workspace.py             # unchanged (desired_name for workspace deletion key)
│   ├── plan.py                  # unchanged
│   └── run.py                   # unchanged
└── infrastructure/
    ├── external_store.py        # NEW sqlite adapter: add/list/delete, WAL, transactions
    ├── config_loader.py         # unchanged
    ├── discovery.py             # unchanged
    ├── classifier.py            # unchanged
    ├── runner.py                # unchanged
    └── messages.py              # + external add/list/delete messages
```

**Structure Decision**: Single project (existing layered architecture). The new
surface is one pure `domain/external.py` module, a new `app/ports.ExternalStore`
port, three new app flows, and a new `infrastructure/external_store.py` sqlite
adapter. The session runtime (`plan`/`run`/`workspace`) is untouched — external
entries are plain `SessionEntry` values — which is the basis for SC-001 parity.