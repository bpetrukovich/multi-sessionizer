# Implementation Plan: tmuxp Config Support

**Branch**: `002-tmuxp-config-support` | **Date**: 2026-10-04 | **Spec**: [`spec.md`](./spec.md)

**Input**: Feature specification from `/specs/002-tmuxp-config-support/spec.md`

## Summary

Replace the file + nvim flow with declarative inline tmuxp workspaces. Users declare
workspaces as inline YAML strings in `config.toml` (new `tmuxp_workspaces` key) or pass
them on a dedicated `session` subcommand. Provisioning delegates to the external `tmuxp`
tool through the infrastructure `Runner` (detached build, spinner disabled, session name
injected via `-s`), then stamps each built session with a **session marker** — a
fingerprint of the workspace definition stored as a tmux session option
(`@multi-sessionizer-marker`). Recognition of the tool's own sessions is marker-based
(never by name), so switch-vs-create decisions are derived purely from live tmux state
plus the config entry (stateless — FR-014). The domain models a selection as a flat
collection of `SessionSpec`s (FR-022) and processes each spec with per-spec dedup
(marker for workspaces, path for directories), one shared post-step. File paths, the
`additional_files` key, and the nvim dependency are removed (FR-001/FR-002). Directory
flows, naming rules, zoxide ranking, and attach/switch logic are byte-for-byte
unchanged (FR-003, SC-001). New runtime dependency **PyYAML** (workspace YAML
validation/extraction, justified in research R4) and documented external dependency
**tmuxp**. One documented constitution clarification (PATCH → v1.2.2) updates Principle
V's dependency examples (nvim removed, tmuxp/PyYAML added) and Principle II's domain
module list (`+ workspace`).

## Technical Context

**Language/Version**: Python 3.12+ (managed with `uv`, `uv_build` backend)

**Primary Dependencies**: runtime gains **PyYAML** (`yaml.safe_load`/`safe_dump`) for
pure workspace YAML parsing, validation, and extraction — stdlib otherwise
(`subprocess`, `os`, `tomllib`, `hashlib`, `tempfile`, `dataclasses`, `typing`).
External tools invoked via subprocess: `tmux`, `fzf`, `zoxide`, `pgrep` (unchanged) and
**`tmuxp`** (new — workspace provisioning, invoked only through the `Runner` adapter).
Dev: `pytest>=8`, `ruff>=0.9`.

**Storage**: TOML config at `~/.config/multi-sessionizer/config.toml` (overridable via
`MULTI_SESSIONIZER_CONFIG`); the switch-vs-create mapping is stateless (a session-marker
stored inside tmux is live tmux state, not external state). The only transient file is
the materialized workspace config written to a per-run temp directory (under the CWD so
relative paths in an inline workspace resolve relative to the invocation directory) and
deleted after the `tmuxp` subprocess completes.

**Testing**: `pytest` (93 tests today; directory-related tests pass unchanged — SC-001;
file/nvim tests are updated/removed — SC-007) + `ruff check` / `ruff format`. New tests
are written first (Red-Green-Refactor, constitution II): pure domain tests for workspace
parse/fingerprint/validate/label and the plan sequences; infra tests monkeypatch
`subprocess.run` and `tempfile`; end-to-end tmux smoke tests run under
`scripts/tmux-sandbox.sh`.

**Target Platform**: Linux CLI (tmux 3.x user environment; tmuxp >= 1.x installed as an
external tool).

**Project Type**: CLI tool (single console script `multi-sessionizer`).

**Performance Goals**: workspace handling MUST only process declared entries — no
scanning, parsing, or provisioning beyond the configured workspaces (FR-023). Directory
discovery stays bounded by configured depth levels (constitution IV, unchanged).

**Constraints**: behavior parity for directory flows is the top priority (identical
command sequences and output, SC-001); domain stays pure (no subprocess/filesystem/
environment access, no `os.path.realpath`); the mapping is stateless (no registry, DB,
or sidecar file — FR-014); recognition is never by session name (FR-011); exit codes
0/1/2 preserved (FR-021); nvim/file references fully removed from code, tests, docs,
and the dependency table (SC-007); external tools only through infrastructure adapters.

**Scale/Scope**: small personal tool — ~10 source modules + 4 layer packages, ~6k LOC
incl. tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **I** CLI interface, meaningful exit codes (0/1/2) | PASS | New `session` subcommand (FR-008); `switch` keeps directory-only paths; codes preserved (FR-021). |
| **II** Pure, test-first modules; domain purity; external tools only through adapters | **AMEND** | Domain gains a pure `workspace` module (parse/fingerprint/validate/label/materialize — no I/O); tmuxp invoked only via `Runner` (infra adapter), never inline; behavior changes land with tests first. Recorded as PATCH constitution clarification → v1.2.2 (domain module list `+ workspace`). |
| **III** TOML config, `MULTI_SESSIONIZER_CONFIG`, env/`~` expansion, no built-in defaults | PASS | Config stays TOML; new `tmuxp_workspaces` list key; `additional_files` rejected with a clear message (US4/FR-001); missing keys → empty tuple. |
| **IV** Bounded discovery | PASS | Discovery untouched; `test_scan_cost_is_bounded_by_max_depth` still pins the bound. |
| **V** Simplicity / YAGNI | **AMEND** | New runtime dependency PyYAML (justified: FR-005/FR-018 require structural YAML validation + `session_name` extraction; tmuxp itself uses PyYAML, so parse semantics match) and documented external dep tmuxp (spec assumption, FR-006/FR-020). The marker mechanism is the minimal stateless identity solution the spec mandates (FR-011/FR-014). Recorded as PATCH constitution clarification → v1.2.2 (Principle V dependency list: nvim removed, tmuxp + PyYAML added). No speculative abstractions beyond the spec. |
| Dev workflow: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .` | PASS | All quality gates run in implementation; `uv run pytest` may fail to spawn in this environment (permission denied) — use `.venv/bin/python -m pytest`. Anything creating/killing tmux sessions runs under `scripts/tmux-sandbox.sh`. |
| Repository content in English | PASS | All code/docs/comments remain English. |

**No ERROR-level gate failures.** Two PATCH-level constitution clarifications (Principle
II module list, Principle V dependency list) are recorded as one version bump to **v1.2.2**
with an updated `Last Amended` date per governance.

## Project Structure

### Documentation (this feature)

```text
specs/002-tmuxp-config-support/
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
├── __init__.py                  # version (bumped to 0.2.0)
├── __main__.py                  # python -m entry (unchanged)
├── main.py                      # [infrastructure] CLI dispatch + composition root
│                                #   _split_argv: + "session" branch; USAGE updated;
│                                #   _run(dirs, files) signature kept (files always []),
│                                #   session_flow wiring for the new subcommand
├── domain/                      # [domain] pure business logic, no I/O
│   ├── __init__.py
│   ├── models.py                #   Selection(dirs, workspaces), SessionSpec,
│   │                            #   RuntimeSnapshot(+ markers), Command(+ input)
│   ├── naming.py                #   session_name (unchanged) + workspace fallback name
│   ├── rank.py                  #   unchanged (zoxide ranking of directories)
│   ├── workspace.py             #   NEW: parse_workspace, validate_workspace,
│   │                            #   fingerprint, workspace_label, desired_name,
│   │                            #   materialized_config (PyYAML, pure)
│   ├── plan.py                  #   per-spec planning: marker-based reuse for
│   │                            #   workspaces, path-based reuse for dirs, -2 suffix
│   │                            #   disambiguation, tmuxp + set-option commands,
│   │                            #   single attach/switch or shared post-step
│   └── run.py                   #   unchanged (CommandExecutor protocol + run)
├── app/                         # [app] thin wiring, DTO + adapter-contract ownership
│   ├── __init__.py
│   ├── configuration.py         #   Config: - additional_files, + tmuxp_workspaces
│   ├── ports.py                 #   ConfigLoader(- missing_files), CandidateDiscovery
│   │                            #   (- collect_files), MessageOutput(+ workspace_problems),
│   │                            #   Picker/ZoxideScorer/SelectionClassifier/
│   │                            #   EnvironmentProbe/CommandExecutor unchanged; FlowDeps
│   └── flows.py                 #   interactive_flow (validate workspaces, label map,
│   │                            #   picker, classify dirs + map labels), session_flow,
│   │                            #   switch_flow (dirs only), run_selection
├── infrastructure/              # [infrastructure] all side effects
│   ├── __init__.py
│   ├── config_loader.py         #   load tmuxp_workspaces; reject additional_files;
│   │                            #   drop missing_files; raise ConfigError
│   ├── discovery.py             #   collect_dirs unchanged; collect_files removed
│   ├── classifier.py            #   classify_args: dirs only, clear error for files
│   ├── runner.py                #   Runner: + tmuxp provisioning (temp config file,
│   │                            #   failure detection), + marker list/set via tmux,
│   │                            #   snapshot() populates markers; existing_sessions
│   │                            #   and execute() kept for legacy tests
│   └── messages.py              #   ConsoleMessageOutput: + workspace_problems,
│   │                            #   - missing_files text; CONFIG_EXAMPLE updated
│
# Legacy compatibility facades (zero logic, re-export only) — public surface of the
# infrastructure layer so the existing directory-related test suite passes unchanged:
│   ├── cli.py                   #   re-exports classify_args
│   ├── config.py                #   re-exports Config, load_config, missing_dirs
│   ├── discovery.py             #   re-exports collect_dirs
│   ├── rank.py                  #   re-exports from domain.rank
│   ├── naming.py                #   re-exports session_name from domain.naming
│   ├── decisions.py             #   re-exports Command, plan/plan_legacy
│   └── runner.py                #   re-exports Runner

tests/                      # directory tests unchanged; file/nvim tests removed/updated;
│                           # new tests: test_workspace.py (domain), test_plan_workspaces,
│                           # test_session_cli, test_runner_markers, test_config updates
```

**Structure Decision**: same src-layout with one subpackage per layer under the existing
top package. The single dependency rule is unchanged (`domain` imports nothing,
`app` → `domain`, `infrastructure` → both). New behavior lands in the existing layers:
a new pure `domain/workspace.py`, per-spec logic in `domain/plan.py`, extended DTOs in
`domain/models.py`, config/CLI/runner changes in the infrastructure layer, and flow
wiring in `app/flows.py`. Top-level facades stay zero-logic re-exports.

## Complexity Tracking

> Deviation from the constitution is limited to the two recorded PATCH clarifications;
> the remaining entries justify structure the spec itself requires.

| Violation / Complexity | Why Needed | Simpler Alternative Rejected Because |
|------------------------|------------|--------------------------------------|
| **Constitution II + V clarification** (domain module list, dependency list) | FR-001/FR-002 remove nvim; FR-005/FR-018 require client-side YAML parsing (PyYAML); the spec mandates tmuxp as an external provisioning tool; FR-022 adds a `workspace` domain capability. | Not updating the constitution would leave the recorded principles factually stale (they list nvim as a dependency); recorded as one PATCH → v1.2.2 per governance. |
| **Session marker as tmux session option** (stateless mapping) | FR-011/FR-012/FR-014 mandate recognition by an in-session marker, never by name, with zero persisted state. A tmux user option (`@multi-sessionizer-marker`) is the minimal in-tmux store; it survives the session's lifetime and is lost with it, so a server restart that drops sessions simply yields fresh sessions. | A sidecar registry file or DB violates FR-014; name-based recognition violates FR-011; encoding the marker in the session name would break FR-015 (the tool must not impose naming) and US3 scenario 3 (name collisions with foreign sessions). |
| **PyYAML runtime dependency** | FR-005 (YAML), FR-007 (picker label from `session_name`), FR-015 (honor/derive name), FR-018 (structural validation before a run) all require parsing workspace YAML in-process. | Delegating validation to a per-entry `tmuxp load` before the run would create real sessions on "validation" and is unbounded work; hand-rolled parsing is fragile and untestable. PyYAML is the canonical parser tmuxp itself uses. |
| **Temp config file for `tmuxp load`** | tmuxp v1.74 `load` accepts only file/dir/name specifiers — no stdin — so an inline workspace must be materialized to a file (see research R1). | A persisted workspace cache or leaving the file behind violates the statelessness spirit; writing under the CWD (deleted after the run) makes relative paths resolve to the invocation directory, matching tmuxp's `expand(cwd=config_dir)` semantics. |

*Re-checked after Phase 1: no new violations introduced; gate state unchanged.*

## Done When

- [x] Plan workflow executed; Technical Context and Constitution Check filled.
- [x] Phase 0 research complete (`research.md`) — all design unknowns resolved.
- [x] Phase 1 design complete (`data-model.md`, `contracts/`, `quickstart.md`).
- [ ] Implementation (Phase 2+) follows `tasks.md` under `scripts/tmux-sandbox.sh` for all tmux-touching work.