---

description: "Task list for External Config CLI implementation"
---

# Tasks: External Config CLI

**Input**: Design documents from `/specs/004-external-config-cli/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests ARE requested — the constitution mandates test-first (Red-Green-Refactor) for every behavior change, and plan.md §Testing requires the new pure domain module to be unit-tested first and the sqlite store tested via an in-memory DB. All feature 002/003 tests must pass unchanged (SC-001).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Existing layered architecture: `src/multi_sessionizer/domain/` (pure), `src/multi_sessionizer/app/` (wiring), `src/multi_sessionizer/infrastructure/` (side effects). Top-level modules under `src/multi_sessionizer/` are zero-logic re-export facades.
- Quality gates: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check`
- Tmux safety: anything creating/killing tmux sessions runs under `scripts/tmux-sandbox.sh -- <cmd>`; never `tmux kill-server` on the default/current server.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared infrastructure for the external store

No new runtime dependency is introduced (sqlite3 is stdlib — constitution V, research §10). The repository already has `uv`, `pytest`, `ruff` configured; this phase wires the new store location plumbing.

- [x] T001 Add the XDG state directory constant and `MULTI_SESSIONIZER_STORE` override resolution in `src/multi_sessionizer/infrastructure/external_store.py` (default `~/.local/state/multi-sessionizer/external.db`, per research §2 and store-contract §Location)
- [x] T002 [P] Document the store location and `MULTI_SESSIONIZER_STORE` override in the README (no new dependency table entry — sqlite3 is stdlib, per constitution V and research §10)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

These are the pure domain rules (used by all add/list/delete flows and the picker merge), the `ExternalStore` port + result types, the sqlite adapter, and the new message methods. Write tests FIRST and confirm they FAIL before implementing each unit.

- [x] T003 [P] Write unit tests for `classify_external_input` in `tests/test_external.py` (workspace via non-empty `windows` list; group via string `name` + non-empty `sessions`; any other mapping → invalid with specific message; scalar string or YAML parse failure → directory; returns `(SessionEntry | None, list[str])`)
- [x] T004 [P] Write unit tests for `deletion_key` in `tests/test_external.py` (directory → realpath-normalized `path`; workspace → `domain/workspace.desired_name(definition)`; group → `name`)
- [x] T005 [P] Write unit tests for `resolve_delete` in `tests/test_external.py` (0 matches → `([], ["No external entry with deletion key '<key>'."])`; 1 match → `([entry], [])`; >1 matches → `([m1, m2, ...], [ambiguous message])`, none removed; the ambiguous case must cover two workspaces sharing a session name)
- [x] T006 Implement `classify_external_input(arg) -> tuple[SessionEntry | None, list[str]]` in `src/multi_sessionizer/domain/external.py` (reuse `domain/session_entries.classify_sessions`; `yaml.safe_load` the arg once; classification rule from domain-contracts §classify_external_input)
- [x] T007 Implement `deletion_key(entry) -> str` in `src/multi_sessionizer/domain/external.py` (delegates to `domain/workspace.desired_name` for workspaces)
- [x] T008 Implement `resolve_delete(entries, key) -> tuple[list[SessionEntry], list[str]]` in `src/multi_sessionizer/domain/external.py` (precise-match rule: exactly one → delete; >1 → report matches, delete none; 0 → not-found message)
- [x] T009 [P] Add the `ExternalAddResult` and `ExternalDeleteResult` frozen dataclasses and the `ExternalStore` Protocol to `src/multi_sessionizer/app/ports.py` (signatures from app-ports §ExternalStore; add/delete/list_entries; do not use `@runtime_checkable`)
- [x] T010 [P] Extend the `MessageOutput` Protocol in `src/multi_sessionizer/app/ports.py` with `external_added(label)`, `external_list(rows: list[tuple[str, str, str]])`, `external_deleted(message)`, `external_empty()` (app-ports §MessageOutput)
- [x] T011 Add `external_store: ExternalStore` field to the `FlowDeps` dataclass in `src/multi_sessionizer/app/ports.py`
- [x] T012 [P] Write store unit tests against an in-memory sqlite DB (`:memory:`) in `tests/test_external_store.py` (schema creation; `add` success returns the stored entry; duplicate add → `ok=False` duplicate error, nothing stored for each of path/definition/name; `delete` success/not-found/ambiguous via `resolve_delete`; `list_entries` returns a stable `ORDER BY id` snapshot; WAL mode enabled)
- [x] T013 [P] Write the concurrent stress test in `tests/test_external_store.py` (SC-005: parallel add/delete/list across threads/processes never yields a torn list, a duplicate directory, or a partially-applied delete)
- [x] T014 Implement the sqlite `ExternalStore` adapter in `src/multi_sessionizer/infrastructure/external_store.py` (schema from store-contract §Schema with `CHECK (kind IN (...))` and nullable `UNIQUE (path) UNIQUE (definition) UNIQUE (name)`; WAL mode; one transaction per add/delete; `list_entries` reads one consistent snapshot ordered by `id`; parent dir created if missing; duplicate via `IntegrityError`; corrupt/unreadable store raises a clear error rather than crashing)
- [x] T015 Implement the new external message methods in `src/multi_sessionizer/infrastructure/messages.py` (`external_added`, `external_list` formatting `(kind, label, deletion_key)`, `external_deleted`, `external_empty` per app-ports §MessageOutput)
- [x] T016 Update the existing `test_main.py`/`test_app_flows.py` wiring tests so `FlowDeps` construction includes the new `external_store` field (a fake), preserving SC-001

**Checkpoint**: Foundation ready — pure domain rules tested, port defined, sqlite store implemented and stress-tested, messages available. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Add an external config entry (Priority: P1) 🎯 MVP

**Goal**: `external add <entry>` classifies, validates, and persists a directory / inline workspace / group into the external store without touching the config file (FR-001/FR-005/FR-007/FR-015).

**Independent Test**: `external add` for one directory, one workspace, and one group, each printing a success confirmation; the config file checksum is unchanged; duplicate adds are rejected (quickstart Scenario 1 & 5).

### Tests for User Story 1 (test-first — MUST FAIL before implementation) ⚠️

- [x] T017 [P] [US1] Unit test for `add_external_flow` in `tests/test_app_flows.py` (valid directory/workspace/group → `store.add` called with the classified `SessionEntry`, success message, exit 0)
- [x] T018 [P] [US1] Unit test for `add_external_flow` invalid input in `tests/test_app_flows.py` (invalid entry → problem message via `messages.error`, exit 1, `store.add` never called — FR-015)
- [x] T019 [P] [US1] Unit test for duplicate-add path in `tests/test_app_flows.py` (store returns `ok=False` duplicate → "already exists" error, exit 1, nothing stored — FR-005)

### Implementation for User Story 1

- [x] T020 [US1] Implement `add_external_flow(arg, deps) -> int` in `src/multi_sessionizer/app/flows.py` (call `domain/external.classify_external_input`; on invalid → `deps.messages.error(...)`, return 1; on valid → `deps.external_store.add(entry)`; duplicate → error, return 1; success → `deps.messages.external_added(label)`, return 0)
- [x] T021 [US1] Add the `external` subcommand dispatch for `external add ENTRY` to `src/multi_sessionizer/main.py` (`_split_argv` returns an `external` command with its verb; `external add` → `add_external_flow`; `external <unknown>` → exit 2; update `USAGE` with the `external add ENTRY / external list / external delete KEY` lines per cli-contract §Usage)
- [x] T022 [US1] Wire `external_store=SqliteExternalStore()` into `default_deps()` in `src/multi_sessionizer/main.py`

**Checkpoint**: User Story 1 is functional and independently testable.

---

## Phase 4: User Story 2 - List external config entries (Priority: P1)

**Goal**: `external list` shows every stored entry with its type, picker label, and deletion key; empty store is a clean success (FR-008, US2).

**Independent Test**: Add a few entries of each type, run `external list`, verify each row shows `kind`, `[external]` label, and correct deletion key (path / session name / group name); empty list exits 0 (quickstart Scenario 2).

### Tests for User Story 2 (test-first — MUST FAIL before implementation) ⚠️

- [x] T023 [P] [US2] Unit test for `list_external_flow` in `tests/test_app_flows.py` (non-empty store → `deps.messages.external_list(rows)` with one `(kind, label, deletion_key)` tuple per entry, exit 0)
- [x] T024 [P] [US2] Unit test for empty-store list in `tests/test_app_flows.py` (empty store → `deps.messages.external_empty()`, exit 0 — US2 ac2)
- [x] T025 [P] [US2] Unit test for `resolve_delete`-backed deletion-key computation reused by list in `tests/test_external.py` (label and deletion key match the pure `deletion_key` output)

### Implementation for User Story 2

- [x] T026 [US2] Implement `list_external_flow(deps) -> int` in `src/multi_sessionizer/app/flows.py` (call `deps.external_store.list_entries()`; empty → `deps.messages.external_empty()`, return 0; else build `(kind, label, deletion_key)` rows via `deletion_key` and pass to `deps.messages.external_list(...)`, return 0)
- [x] T027 [US2] Add `external list` dispatch to `src/multi_sessionizer/main.py` (already stubbed by T021's `external` command; wire the verb to `list_external_flow`)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Delete an external config entry (Priority: P1)

**Goal**: `external delete <key>` removes an entry by its deletion key (path / session name / group name) via precise-match; affects only the store, never the config file, never a live tmux session (FR-009/FR-010/FR-014).

**Independent Test**: Add entries of each type, delete one by key, list again to confirm it is gone, config checksum unchanged, and its running session (if any) survives (quickstart Scenario 4 & 5).

### Tests for User Story 3 (test-first — MUST FAIL before implementation) ⚠️

- [x] T028 [P] [US3] Unit test for `delete_external_flow` in `tests/test_app_flows.py` (store lists entries → `resolve_delete` gives exactly one match → `store.delete(key)` called → success message, exit 0)
- [x] T029 [P] [US3] Unit test for delete-not-found in `tests/test_app_flows.py` (0 matches → error message, exit 1, `store.delete` NOT called, store unchanged — FR-010)
- [x] T030 [P] [US3] Unit test for delete-ambiguous in `tests/test_app_flows.py` (>1 matches → matches reported, none removed, exit 1)

### Implementation for User Story 3

- [x] T031 [US3] Implement `delete_external_flow(key, deps) -> int` in `src/multi_sessionizer/app/flows.py` (call `deps.external_store.list_entries()`; `resolve_delete(entries, key)`; 0 matches → `deps.messages.error(...)`, return 1; >1 matches → report matches, return 1; exactly 1 → `deps.external_store.delete(key)`, `deps.messages.external_deleted(...)`, return 0)
- [x] T032 [US3] Add `external delete KEY` dispatch to `src/multi_sessionizer/main.py` (wire the verb to `delete_external_flow`)

**Checkpoint**: User Stories 1–3 are independently functional.

---

## Phase 6: User Story 4 - External entries integrate with picker behavior (Priority: P2)

**Goal**: External entries merge into the interactive picker as `[external]` lines, are multi-selectable with config entries, share switch-vs-create and per-entry dedup, and route to the unchanged `plan`/`run` (FR-004/FR-012/FR-013, US4, SC-006).

**Independent Test**: Run the picker (sandboxed via `scripts/tmux-sandbox.sh -- multi-sessionizer`), verify `[external]` lines appear alongside `[tmuxp]`/`[group]`/directory lines, multi-select one external + one config entry, confirm each is provisioned/switched exactly once; corrupt store degrades gracefully (FR-016).

### Tests for User Story 4 (test-first — MUST FAIL before implementation) ⚠️

- [x] T033 [P] [US4] Unit test for picker-merge in `tests/test_app_flows.py` (interactive_flow appends `[external] <path|desired_name|name>` candidates from `store.list_entries()` alongside config candidates, with correct label mapping)
- [x] T034 [P] [US4] Unit test for mixed multi-select routing in `tests/test_app_flows.py` (selecting external + config entries expands to one flat `Selection(dirs, workspaces)` and runs once — FR-013, SC-006)
- [x] T035 [P] [US4] Unit test for corrupt-store degradation in `tests/test_app_flows.py` (store failure → error to stderr, run continues with config entries only, does not crash — FR-016)

### Implementation for User Story 4

- [x] T036 [US4] Extend `interactive_flow` in `src/multi_sessionizer/app/flows.py` to load external entries after building config candidates and append `[external]` lines (directory → `[external] <path>`, workspace → `[external] <desired_name>`, group → `[external] <name>`) routed to their stored `SessionEntry` (data-model §7)
- [x] T037 [US4] Extend the selection-routing block in `interactive_flow` in `src/multi_sessionizer/app/flows.py` so a selected `[external]` entry routes exactly like a config entry (directory → dir line, workspace → definition, group → expand members) into the single `Selection(dirs, workspaces)` → `run_selection`
- [x] T038 [US4] Wrap the external load in `interactive_flow` in `src/multi_sessionizer/app/flows.py` so a corrupt/unreadable store reports `External store error: <detail>.` to stderr and continues with config entries only (FR-016)

**Checkpoint**: All user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [x] T039 [P] Update the README CLI documentation with the `external add/list/delete` subcommands and the `[external]` picker label
- [x] T040 Run `quickstart.md` validation end-to-end (Scenarios 1–7) against an isolated `MULTI_SESSIONIZER_STORE`, with interactive/provisioning steps sandboxed under `scripts/tmux-sandbox.sh --`
- [x] T041 [P] Run the full suite: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check` — confirm all feature 002/003 tests pass unchanged (SC-001)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories (pure domain rules, `ExternalStore` port, sqlite adapter, messages)
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (add), US2 (list), US3 (delete) are P1; US4 (picker integration) is P2
  - US1–US3 can be built in parallel (different flows) after Foundational
  - US4 depends on US1–US3 (the store and flows it merges)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1) add**: can start after Phase 2; no dependency on other stories
- **US2 (P1) list**: can start after Phase 2; independent
- **US3 (P1) delete**: can start after Phase 2; independent
- **US4 (P2) picker integration**: depends on US1–US3 (needs the store populated and the add/list flows in place); independently testable once US1 is merged

### Within Each User Story

- Tests (included — constitution test-first) MUST be written and FAIL before implementation
- Pure domain rules → store port → store adapter → flow → main dispatch
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (tests for the three pure functions T003/T004/T005; ports/messages T009/T010; store tests T012/T013)
- Once Foundational completes, US1–US3 flows can be built in parallel (different flow functions, same `flows.py` file — coordinate to avoid merge conflicts on `add_external_flow`/`list_external_flow`/`delete_external_flow`)
- All tests for a user story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (test-first):
Task: "Unit test for add_external_flow in tests/test_app_flows.py"
Task: "Unit test for add_external_flow invalid input in tests/test_app_flows.py"
Task: "Unit test for duplicate-add path in tests/test_app_flows.py"

# Then the implementation (depends on the tests passing red):
Task: "Implement add_external_flow in src/multi_sessionizer/app/flows.py"
Task: "Add external subcommand dispatch in src/multi_sessionizer/main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (`external add`) → MVP: user can permanently add entries to the picker
4. **STOP and VALIDATE**: add one entry of each type, confirm success + config checksum unchanged (quickstart Scenario 1)
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (add) → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 (list) → Test independently → Deploy/Demo
4. Add User Story 3 (delete) → Test independently → Deploy/Demo
5. Add User Story 4 (picker integration) → Test independently → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (domain rules, store adapter, ports, messages)
2. Once Foundational is done:
   - Developer A: User Story 1 (add flow + dispatch)
   - Developer B: User Story 2 (list flow + dispatch)
   - Developer C: User Story 3 (delete flow + dispatch)
3. Team merges US1–US3, then Developer D: User Story 4 (picker merge)
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (constitution test-first)
- `domain/external.py` MUST stay pure (stdlib + PyYAML only; no subprocess, filesystem, environment, `os.path.realpath`) so `tests/test_layer_boundaries.py` stays green
- The sqlite store must never read or write the config file (FR-001) and must never run/kill tmux (FR-014, constitution Additional Constraints)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence