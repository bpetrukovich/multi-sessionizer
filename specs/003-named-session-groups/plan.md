# Implementation Plan: Named Session Groups

**Branch**: `003-named-session-groups` | **Date**: 2026-10-04 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `/specs/003-named-session-groups/spec.md`

## Summary

Unify the config's session surface into a single `sessions` list that accepts
three element forms — directory strings, inline tmuxp workspace strings, and
named group tables — and let one interactive picker selection provision a whole
named group of sessions. `additional_dirs` and `tmuxp_workspaces` are removed
outright (no compatibility).

The design keeps the session runtime untouched: a group is a **config-surface +
app-flow** concept only. A selected group is expanded into a flat domain
`Selection(dirs, workspaces)` exactly like today's multi-select, so `plan`/`run`
and every marker-based switch-vs-create rule behave identically to feature 002.
This preserves behavior parity for the non-removed flows while adding the group
shorthand as a pure config classification plus an app-flow expansion.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`).

**Primary Dependencies**: PyYAML (existing, for workspace-shape detection and
workspace parse/validate), plus existing external tools tmux / tmuxp / fzf /
zoxide. **No new runtime dependencies.**

**Storage**: TOML config file at `~/.config/multi-sessionizer/config.toml`
(overridable via `MULTI_SESSIONIZER_CONFIG`). Directory strings are env/`~`-
expanded and realpath-normalized at the infra boundary; workspace definitions
are kept verbatim.

**Testing**: `pytest` (`.venv/bin/python -m pytest -q`), `ruff check .`,
`ruff format . --check`. Domain `plan`/`run`/`workspace` tests stay byte-identical
(SC-001); config-surface tests referencing the removed keys are rewritten for
`sessions`.

**Target Platform**: Linux terminal (tmux/fzf/zoxide/tmuxp available).

**Project Type**: CLI (tmux session manager).

**Performance Goals**: Group expansion is pure in-memory over config entries;
directory discovery cost is unchanged (bounded by configured max depth,
constitution IV).

**Constraints**: Domain layer stays pure (PyYAML only — no subprocess,
filesystem, environment, `os.path.realpath`). No backward compatibility
(removed keys are rejected, not migrated). Exit codes preserved: 0 / 1 / 2.

**Scale/Scope**: Small personal tool; one-level groups; tens of entries per
config.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|-----------|-----------|
| **I. CLI interface (MUST)** | PASS. The CLI surface (subcommands, exit codes, stdout/stderr contract) is unchanged. Group selection flows through the existing interactive picker; FR-012 exit codes preserved. |
| **II. Pure, test-first modules (NON-NEGOTIABLE)** | PASS. New `domain/session_entries.py` is pure (PyYAML + string helpers only); classification of workspace-shape and group structure is deterministic and unit-tested first. `plan`/`run`/`workspace` gain no side effects. Directory realpath/existence stay in infrastructure. |
| **III. TOML configuration** | PASS. A single `sessions` TOML list; missing key means empty list (no built-in defaults); env/`~` expansion in directory paths; workspace definitions verbatim. |
| **IV. Bounded performance** | PASS. Discovery is unchanged and depth-bounded; group expansion is O(entries). |
| **V. Simplicity (YAGNI)** | PASS. The unified `sessions` surface *removes* two config keys and adds one level of grouping — no speculative abstractions, no new dependencies. |

**Gate result**: No violations. The removed `additional_dirs`/`tmuxp_workspaces`
surfaces are rejected outright per the no-backward-compatibility rule (FR-002)
without migration hints or compatibility shims. Complexity table not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-named-session-groups/
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
├── main.py                      # CLI dispatch (unchanged; CONFIG_EXAMPLE re-export)
├── config.py                    # legacy re-export facade (Config/ConfigError/load/missing)
├── app/
│   ├── configuration.py         # Config DTO: +sessions, −additional_dirs/−tmuxp_workspaces; +ConfigError
│   ├── ports.py                 # ConfigLoader.missing_dirs → directory entries; MessageOutput unchanged
│   └── flows.py                 # interactive_flow: build unified picker, expand groups → Selection
├── domain/
│   ├── models.py                # + SessionEntry DTO (kind/path/definition/name/members)
│   ├── session_entries.py       # NEW pure: classify_sessions, is_workspace_definition, group shape validation
│   ├── workspace.py             # unchanged (parse/validate/fingerprint/label/desired_name)
│   ├── plan.py                  # unchanged (expands Selection → specs; groups handled pre-plan)
│   └── run.py                   # unchanged
└── infrastructure/
    ├── config_loader.py         # parse `sessions`, reject removed keys, realpath dirs, classify via domain
    ├── discovery.py             # collect_dirs: drop additional_dirs (root scans only)
    ├── classifier.py            # unchanged (dir-only classify_args/classify_selection)
    ├── runner.py                # unchanged
    └── messages.py              # CONFIG_EXAMPLE updated to `sessions`
```

**Structure Decision**: Single project (existing layered architecture). The new
surface lives in `app`/`infrastructure` and one new pure `domain/session_entries.py`
module; the session runtime (`domain/plan.py`, `domain/run.py`, `domain/workspace.py`)
is untouched, which is the entire basis for SC-001 parity.