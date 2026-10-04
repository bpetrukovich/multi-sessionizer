# Implementation Plan: Layered Architecture Refactoring

**Branch**: `001-layered-architecture` | **Date**: 2026-10-04 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `/specs/001-layered-architecture/spec.md`

## Summary

Refactor the CLI tool from a flat module set into three strictly separated layers —
**domain** (pure business logic), **app** (thin wiring + DTO ownership), and
**infrastructure** (all side effects) — without changing any observable behavior.
Domain gains first-class DTOs (`Selection`, `RuntimeSnapshot`, `Command`/`CommandPlan`),
a DTO-driven `plan` and a domain `run` capability with an injected executor contract.
The app layer owns the `Configuration` DTO and the adapter contracts infra satisfies.
All side effects (subprocess, filesystem, environment, stdin/stdout, terminal) move
into `infrastructure/`. The existing 71-test suite passes unchanged via thin re-export
facades at the legacy module paths. One documented constitution amendment (Principle II
module list restated in layered terms, MINOR → v1.2.0) is required and is mandated by
the spec's stated assumptions.

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`, `uv_build` backend)

**Primary Dependencies**: none at runtime (stdlib only: `subprocess`, `os`, `tomllib`,
`dataclasses`, `typing`). External tools invoked via subprocess: `tmux`, `fzf`, `zoxide`,
`pgrep`. Dev: `pytest>=8`, `ruff>=0.9`.

**Storage**: TOML config at `~/.config/multi-sessionizer/config.toml`
(overridable via `MULTI_SESSIONIZER_CONFIG`); no persistent application state.

**Testing**: `pytest` (currently 71 tests, all passing) + `ruff check` / `ruff format`.

**Target Platform**: Linux CLI (tmux user environment).

**Project Type**: CLI tool (single console script `multi-sessionizer`).

**Performance Goals**: directory discovery MUST stay bounded by configured depth levels
(never walk the whole tree) — pinned by `test_scan_cost_is_bounded_by_max_depth`.

**Constraints**: behavior parity is the top priority (exit codes 0/1/2, printed output,
and the exact tmux/zoxide command sequence must be identical); domain MUST be
deterministic and free of subprocess/filesystem/environment access; zero new runtime
dependencies.

**Scale/Scope**: small personal tool — 10 current source modules, ~6k LOC incl. tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **I** CLI interface, meaningful exit codes (0/1/2) | PASS | Preserved verbatim by FR-015/FR-016; `main()` keeps dispatch + printing in infra. |
| **II** Pure, test-first modules; module list (`config`, `discovery`, `rank`, `naming`, `cli`, `decisions` pure; `runner`/`main` only side-effect touchpoints) | **AMEND** | The spec's assumptions explicitly direct restating Principle II in layered terms (see Complexity Tracking). Pure business modules (`rank`, `naming`, `decisions`) move to domain and stay pure; `config`/`discovery`/`cli` become infrastructure adapters that (as today) touch the filesystem; `runner`/`main` remain infra. Recorded as MINOR constitution amendment → v1.2.0. |
| **II** External tools invoked only through `runner`, never inline | PASS | Restated as "only through infrastructure adapters"; `Runner` remains the sole subprocess touchpoint, now satisfying adapter contracts. |
| **III** TOML config, `MULTI_SESSIONIZER_CONFIG`, env/`~` expansion, no built-in defaults | PASS | Config loading logic and semantics unchanged. |
| **IV** Bounded discovery | PASS | `discovery` logic untouched; `test_scan_cost_is_bounded_by_max_depth` still pins the bound. |
| **V** Simplicity / YAGNI | PASS* | Three-layer split, DTOs, and adapter protocols add structure, but are mandated by FR-001–FR-020 and justified by the testability/replaceability goals (US1/US4). No speculative abstractions beyond what the spec requires. |
| Dev workflow: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .` | PASS | All quality gates run in implementation; note `uv run pytest` currently fails to spawn in this environment (permission denied) — use `.venv/bin/python -m pytest` locally. |
| Repository content in English | PASS | All code/docs/comments remain English. |

**No ERROR-level gate failures.** The single Principle II amendment is required by the
feature spec itself and will be recorded per constitution governance as version 1.2.0
(MINOR: restate the module list in terms of domain/app/infrastructure layers; external
tools through infrastructure adapters).

## Project Structure

### Documentation (this feature)

```text
specs/001-layered-architecture/
├── plan.md              # This file
├── research.md          # Phase 0: research + decisions
├── data-model.md        # Phase 1: entities, DTOs, layer rules
├── quickstart.md        # Phase 1: validation guide
└── contracts/           # Phase 1: external + layer-boundary contracts
    ├── cli-contract.md
    ├── domain-contracts.md
    └── app-ports.md
```

### Source Code (repository root)

```text
src/multi_sessionizer/
├── __init__.py              # version (unchanged)
├── __main__.py              # python -m entry (unchanged)
├── main.py                  # [infrastructure] CLI dispatch + composition root
│                            #   _split_argv, USAGE, CONFIG_EXAMPLE, _package_version,
│                            #   main(argv), _run(dirs, files), default_deps()
├── domain/                  # [domain] pure business logic, no I/O
│   ├── __init__.py
│   ├── models.py            #   Selection, RuntimeSnapshot, Command, CommandPlan
│   ├── naming.py            #   session_name
│   ├── rank.py              #   parse_zoxide_scores, rank_dirs, build_picker_list
│   ├── plan.py              #   plan(selection, snapshot) core + plan_legacy wrapper
│   └── run.py               #   CommandExecutor protocol + run(selection, snapshot, executor)
├── app/                     # [app] thin wiring, DTO + adapter-contract ownership
│   ├── __init__.py
│   ├── configuration.py     #   Config (configuration DTO)
│   ├── ports.py             #   ConfigLoader, CandidateDiscovery, Picker,
│   │                        #   SelectionClassifier, EnvironmentProbe, ZoxideScorer,
│   │                        #   MessageOutput protocols + FlowDeps bundle
│   └── flows.py             #   run_selection, interactive_flow, switch_flow
├── infrastructure/          # [infrastructure] all side effects
│   ├── __init__.py
│   ├── config_loader.py     #   load_config, missing_files, missing_dirs, ConfigNotFoundError
│   ├── discovery.py         #   collect_dirs, collect_files (unchanged logic)
│   ├── classifier.py        #   classify_args, classify_selection
│   ├── runner.py            #   Runner (probe env/tmux, zoxide, fzf, executor; realpath snapshot)
│   └── messages.py          #   ConsoleMessageOutput (stderr/stdout printing)
│
# Legacy compatibility facades (zero logic, re-export only) — public surface of the
# infrastructure layer so the existing test suite passes unchanged:
│   ├── cli.py               #   re-exports classify_args from infrastructure.classifier
│   ├── config.py            #   re-exports Config (app), load_config/missing_* (infra)
│   ├── discovery.py         #   re-exports collect_dirs/collect_files (+ `os` for test patching)
│   ├── rank.py              #   re-exports from domain.rank
│   ├── naming.py            #   re-exports session_name from domain.naming
│   ├── decisions.py         #   re-exports Command (domain.models), plan/plan_legacy (domain.plan)
│   └── runner.py            #   re-exports Runner (+ `subprocess` for test patching)

tests/                      # unchanged — 71 tests pass against the facades
```

**Structure Decision**: src-layout with one subpackage per layer under the existing
top package (`src/multi_sessionizer/`). Dependency direction is enforced as a single
rule and verified statically (see `data-model.md` §Layer Rules): `domain` imports
nothing from `app`/`infrastructure`; `app` imports `domain` only; `infrastructure`
may import `domain` and `app`. All behavioral code lives in the three layer packages;
the top-level modules are pure re-export facades owned by the infrastructure layer's
public surface (kept so `tests/` and the console-script entry point work unchanged —
see Complexity Tracking).

## Complexity Tracking

> The only deviation from the constitution is a spec-mandated amendment; the
> remaining entries justify structure the spec itself requires.

| Violation / Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------------------|------------|--------------------------------------|
| **Constitution II amendment** (module list restated in layered terms) | Spec assumption: "The constitution's module-list section (Principle II) will be updated to reflect the layered structure as part of this feature." FR-001–FR-005 require the layer split. | Keeping the old module list unchanged would contradict FR-001–FR-005; recorded as MINOR amendment v1.2.0 per governance. |
| **Top-level re-export facades** (7 modules, zero logic) | SC-001 / US2 require the existing test suite to pass unchanged; tests import legacy paths (`multi_sessionizer.cli`, `.config`, `.decisions`, ...) and monkeypatch `discovery.os.scandir` / `runner.subprocess.run`. | Updating test imports would violate the literal "tests pass unchanged" gate; the facades are pure aliases with no mixed behavior (SC-004 rule: no mixed-logic files). |
| **Three-layer split + DTOs + adapter protocols** | FR-001–FR-020; US1 (domain testable without external tools) is the core value; US4 requires replaceable adapters behind contracts. | Flat module structure cannot satisfy FR-002 (domain purity) or US4 (swap picker/executor with a wiring-line change). |
| **`os.path.realpath` removed from domain** | US1/FR-002 require the domain to never read the filesystem; `realpath` resolves symlinks via stat(). | Keeping `realpath` in domain violates the determinism gate; normalization is moved to infrastructure boundaries (see `research.md` decision R2). |

*Re-checked after Phase 1: no new violations introduced; gate state unchanged.*