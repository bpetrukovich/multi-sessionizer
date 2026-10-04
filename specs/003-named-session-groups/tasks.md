---

description: "Task list for feature implementation: Named Session Groups"
---

# Tasks: Named Session Groups

**Input**: Design documents from `/specs/003-named-session-groups/`

**Prerequisites**: plan.md, spec.md (user stories US1/US2/US3), research.md, data-model.md, contracts/

**Tests**: Tests ARE included. Constitution II mandates test-first for every
behavior change, and the feature spec's Success Criteria (SC-001..SC-006) are
test-driven. Write tests FIRST, confirm they FAIL, then implement.

**Organization**: Tasks are grouped by user story to enable independent
implementation and testing of each story. The session runtime
(`domain/plan.py`, `domain/run.py`, `domain/workspace.py`) is UNTOUCHED
(SC-001 parity) — groups are expanded into a flat `Selection` before `plan`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/` and `tests/` at repository root (see plan.md structure).
Domain layer stays pure (PyYAML only — no subprocess/filesystem/environment/
`os.path.realpath`); guard with `tests/test_layer_boundaries.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish a green baseline so SC-001 (behavior parity) is provable.

- [X] T001 Run the existing full test suite, ruff check, and ruff format check to record the green baseline before any change: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check .` and `.venv/bin/ruff format . --check`
- [X] T002 [P] Review `tests/test_layer_boundaries.py` to confirm the exact forbidden-pattern assertions the new `domain/session_entries.py` must satisfy (PyYAML allowed; subprocess/filesystem/environment/`os.path.realpath` forbidden)

**Checkpoint**: Baseline is green; layer-boundary guard rules are known before adding the pure module.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure unified-session classifier that ALL user stories depend on. No user-story work can begin until this phase is complete.

**⚠️ CRITICAL**: This phase introduces the discriminated-union DTO and pure
classification/structural-validation; it BLOCKS US2 (config surface) and US1 (group expansion).

### Tests for the classifier (TDD — write and confirm FAIL first)

- [X] T003 [P] Unit tests for `classify_sessions` covering: directory string, workspace-shaped string, group table, and each structural problem (group missing `name`, empty `sessions`, nested group, non-string/non-table element) in `tests/test_session_entries.py`
- [X] T004 [P] Unit tests for `is_workspace_definition` covering: YAML mapping with non-empty `windows` list → True; directory-like string (`/home/u/proj`) → False; non-mapping YAML → False in `tests/test_session_entries.py`

### Implementation

- [X] T005 [P] Add `SessionEntry` frozen dataclass DTO (fields `kind`, `path`, `definition`, `name`, `members`) to `src/multi_sessionizer/domain/models.py` (kind is `"directory"` | `"workspace"` | `"group"`; group members are directory/workspace only)
- [X] T006 Create pure `domain/session_entries.py` implementing `is_workspace_definition(value: str) -> bool` (via `yaml.safe_load` → mapping with a non-empty `windows` list) and `classify_sessions(raw: Iterable[object]) -> tuple[list[SessionEntry], list[str]]` in `src/multi_sessionizer/domain/session_entries.py` (string+workspace-shaped → workspace entry; other string → directory entry; table with string `name` + non-empty `sessions` array → group entry with recursively classified members; nested-group member → problem; group without `name`/empty `sessions` → problem; any other element → problem; NO filesystem/env/realpath access)

**Checkpoint**: Pure classifier is complete, tested, and passes layer-boundary rules. User-story implementation can now begin in parallel.

---

## Phase 3: User Story 2 - Unified `sessions` config surface (Priority: P1) 🎯 MVP

**Goal**: Replace `additional_dirs`/`tmuxp_workspaces` with a single `sessions`
list that the loader parses into classified `SessionEntry` objects (FR-001/FR-002/FR-003).

**Independent Test**: Write one `sessions` config mixing a directory string, a
workspace string, and a `{name, sessions}` group; `load_config` returns a `Config`
with `sessions` classified into the three entry kinds; a config that still uses
`additional_dirs` or `tmuxp_workspaces` raises `ConfigError` with a clear message.

### Tests for User Story 2 (TDD — write and confirm FAIL first) ⚠️

- [X] T007 [P] [US2] Rewrite `tests/test_config.py`: `additional_dirs`/`tmuxp_workspaces` loading tests become `sessions` loading tests (directory strings expanded + realpath-normalized; workspace strings verbatim; removed keys raise `ConfigError`; missing key → empty tuple)
- [X] T008 [P] [US2] Unit test that a config containing `additional_dirs` or `tmuxp_workspaces` raises the app `ConfigError` with a message naming the removed key in `tests/test_config.py`
- [X] T009 [P] [US2] Update `tests/test_discovery.py`: `test_additional_dirs_verbatim_even_if_missing` and the `additional_dirs=("/extra",)` fixture are rewritten so directory session entries come from `Config.sessions` (root scans only)

### Implementation

- [X] T010 [P] [US2] Update `Config` DTO in `src/multi_sessionizer/app/configuration.py`: remove `additional_dirs` and `tmuxp_workspaces`, add `sessions: tuple[SessionEntry, ...] = ()`; add app-owned `ConfigError` exception (collects a list of message strings)
- [X] T011 [P] [US2] Rewrite `infrastructure/config_loader.py` `load_config`: reject `additional_dirs`/`tmuxp_workspaces` keys (raise `ConfigError`), parse `sessions` via `domain/session_entries.classify_sessions`, env/`~`-expand + realpath directory entries (top-level and group members), keep workspace definitions verbatim, collect all problems into one `ConfigError`
- [X] T012 [P] [US2] Update `infrastructure/config_loader.py` `missing_dirs` to report every directory ENTRY path (top-level and group members) whose `os.path.isdir` is False, plus roots
- [X] T013 [P] [US2] Update `infrastructure/discovery.py` `collect_dirs`: drop the `dirs.extend(cfg.additional_dirs)` line (root scans only); directory session entries are added by the flow, not discovery
- [X] T014 [P] [US2] Update `infrastructure/messages.py` `CONFIG_EXAMPLE` to demonstrate the unified `sessions` list (directory string + workspace string + group table) instead of `additional_dirs`/`tmuxp_workspaces`

**Checkpoint**: The unified `sessions` surface loads, classifies, and rejects removed keys — testable independently of the picker.

---

## Phase 4: User Story 1 - One fzf selection launches a group of sessions (Priority: P1)

**Goal**: The interactive picker shows a group as one `[group] <name>` line;
selecting it provisions every member session and attaches to one (FR-004/FR-005/FR-006).

**Independent Test**: With a fake picker injected that returns `[group] stack`,
run `interactive_flow` and verify the group expands into a flat
`Selection(dirs, workspaces)` whose members map one-to-one to session specs
(three members → three specs; opening the same group twice reuses the same three — SC-002/SC-003).

### Tests for User Story 1 (TDD — write and confirm FAIL first) ⚠️

- [X] T015 [P] [US1] Update `tests/test_app_flows.py` with a test that the unified picker item list mixes directory lines, `[tmuxp] <label>` lines, and `[group] <name>` lines (one entry per top-level element, group members NOT listed individually — research R4)
- [X] T016 [P] [US1] Update `tests/test_app_flows.py` with a test that selecting a `[group]` line routes via a label→entry map and expands to a flat `Selection(dirs, workspaces)` passed to the unchanged `run_selection` (FR-005/FR-006)

### Implementation

- [X] T017 [US1] Update `interactive_flow` in `src/multi_sessionizer/app/flows.py`: build the unified picker list (ranked dirs + `[tmuxp] <label>` workspace lines + `[group] <name>` group lines) and route selected lines via `label → SessionEntry` maps, expanding groups into a flat `Selection(dirs, workspaces)` before `run_selection` (single plan/single post-step)
- [X] T018 [US1] Implement group-label disambiguation in `src/multi_sessionizer/app/flows.py` (prefix group lines with `[group] `, workspace lines already prefixed `[tmuxp] `, numeric-suffix any duplicate displayed labels) so a group name colliding with a directory or workspace label stays selectable (FR-009 edge case)

**Checkpoint**: Group selection expands and provisions member sessions with per-entry dedup, reusing the untouched `plan`/`run` runtime.

---

## Phase 5: User Story 3 - Group validation and errors are clear (Priority: P2)

**Goal**: Malformed groups (missing name, empty members, invalid member, nested
group) and removed config keys are rejected with specific, distinct messages and
exit code 1 before any session is created (FR-007/FR-008/FR-010/FR-011/FR-012).

**Independent Test**: With several intentionally broken group configs, `interactive_flow`
returns 1 for each and prints the exact message from the CLI contract; 0 sessions created.

### Tests for User Story 3 (TDD — write and confirm FAIL first) ⚠️

- [X] T019 [P] [US3] Update `tests/test_cli.py`/`tests/test_main.py` to assert the exact CLI contract error strings and exit code 1 for: removed `additional_dirs`/`tmuxp_workspaces` key, `Group is missing a 'name'.`, `Group '<name>' has an empty 'sessions' list.`, `Group '<name>' has an invalid member: <detail>.`, and `Nested groups are not supported: group '<name>'.` — 0 sessions created in each case
- [X] T020 [P] [US3] Add a test that `ConfigError` from `load_config` surfaces through `interactive_flow` via `MessageOutput.error` and returns exit code 1 (FR-012) in `tests/test_app_flows.py`

### Implementation

- [X] T021 [US3] Update `interactive_flow` in `src/multi_sessionizer/app/flows.py` to catch app `ConfigError` from `config_loader.load()` and report the collected messages via `MessageOutput.error` (exit 1), before any picker/discovery step (FR-010)
- [X] T022 [US3] Ensure the app `ConfigError` message construction produces the CLI-contract wording for each malformed-group case in `src/multi_sessionizer/app/configuration.py` or where `ConfigError` is raised in `infrastructure/config_loader.py`

**Checkpoint**: All malformed-group shapes and removed-key configs fail loudly and specifically with the preserved exit-code contract.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation across all stories and the feature-wide quality gates.

- [X] T023 [P] Update `tests/test_app_flows.py` `FakeConfigLoader` fakes to construct `Config(sessions=…)` instead of `Config(tmuxp_workspaces=…)` (align all fake configs with the unified surface)
- [X] T024 Run the full suite + lint/format and fix any regressions: `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check .` and `.venv/bin/ruff format . --check`
- [X] T025 [P] Validate every quickstart scenario (A–F) from `/specs/003-named-session-groups/quickstart.md` under `scripts/tmux-sandbox.sh -- <command>` (SC-002/SC-003/SC-004/SC-005/SC-006); never run `tmux kill-server` on the default server; kill test sessions by name

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (the pure classifier is prerequisite to US2 and US1)
- **User Stories**: All depend on Phase 2.
  - **US2 (Phase 3)**: First — the unified config surface is the enabling shape for US1.
  - **US1 (Phase 4)**: Depends on US2 (groups must be loadable/classified before the picker can expand them).
  - **US3 (Phase 5)**: Overlaps US2's classifier problems but its CLI-message/exit-code surface is independent — can run in parallel with US1.
- **Polish (Phase 6)**: Depends on all desired user stories complete.

### User Story Dependencies

- **US1 (P1)**: Requires Foundational (classifier) + US2 config surface.
- **US2 (P1)**: Requires Foundational (classifier). No dependency on other stories.
- **US3 (P2)**: Requires Foundational (classifier problems exist). No hard dependency on US1/US2 wiring, but benefits from US2's `load_config` `ConfigError`.

### Within Each User Story

- Tests written and FAIL before implementation
- DTO/model before services, services before integration, runtime untouched
- Core implementation before disambiguation/integration details

### Parallel Opportunities

- All Phase 1/2 tasks marked [P] can run in parallel
- US2 implementation tasks T010–T014 touch different files — parallelizable
- US1 tests (T015/T016) and US3 tests (T019/T020) are independent files — parallelizable
- US1 and US3 can be worked in parallel once Phase 2 completes

---

## Parallel Example: User Story 2

```bash
# Launch the config-surface implementation tasks together:
Task: "Update Config DTO in src/multi_sessionizer/app/configuration.py"
Task: "Rewrite load_config in src/multi_sessionizer/infrastructure/config_loader.py"
Task: "Update missing_dirs in src/multi_sessionizer/infrastructure/config_loader.py"
Task: "Update collect_dirs in src/multi_sessionizer/infrastructure/discovery.py"
Task: "Update CONFIG_EXAMPLE in src/multi_sessionizer/infrastructure/messages.py"
```

---

## Implementation Strategy

### MVP First (User Story 2 Only)

1. Phase 1: Setup (green baseline)
2. Phase 2: Foundational — pure `domain/session_entries.py` classifier (CRITICAL)
3. Phase 3: User Story 2 — unified `sessions` surface loads + removed keys rejected
4. **STOP and VALIDATE**: run `tests/test_config.py` + `tests/test_discovery.py` independently
5. Deploy/demo the unified config surface

### Incremental Delivery

1. Setup + Foundational → classifier ready
2. Add US2 (unified `sessions` surface) → test → demo (MVP)
3. Add US1 (group selection expands + provisions) → test → demo
4. Add US3 (clear malformed-group/removed-key errors) → test
5. Each story adds value without changing the session runtime (SC-001 parity)

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US2 (config surface)
   - Developer B: US1 group expansion once US2 lands; or US3 error surface in parallel
3. Stories integrate independently against the unchanged `plan`/`run` runtime

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to its user story for traceability
- The session runtime (`domain/plan.py`, `domain/run.py`, `domain/workspace.py`) MUST stay byte-identical — parity is the whole basis of SC-001
- Domain `domain/session_entries.py` must stay pure (PyYAML only), guarded by `tests/test_layer_boundaries.py`
- No backward compatibility: removed keys are rejected, not migrated (FR-002)
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
- Avoid: vague tasks, same-file conflicts, cross-story dependencies that break independence