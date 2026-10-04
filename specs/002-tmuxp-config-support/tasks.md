---

description: "Task list for tmuxp config support implementation"

---

# Tasks: tmuxp Config Support

**Input**: Design documents from `/specs/002-tmuxp-config-support/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests ARE included for every behavior change — the project constitution (Principle II) mandates test-first development (Red-Green-Refactor) and "a behavior change without a test is a failed change".

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single Python CLI project: `src/multi_sessionizer/`, `tests/` at repository root
- Layers: `domain/` (pure, no I/O), `app/` (thin wiring), `infrastructure/` (all side effects), `main.py` (composition root)
- Top-level modules (`cli.py`, `config.py`, `discovery.py`, `rank.py`, `naming.py`, `decisions.py`, `runner.py`) are zero-logic re-export facades — do NOT add logic to them
- The domain layer MUST stay free of subprocess/filesystem/environment access and `os.path.realpath` (guarded by `tests/test_layer_boundaries.py`)
- All tmux-touching work MUST run under `scripts/tmux-sandbox.sh` (never `tmux kill-server` on the default/current server)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Version bump, new dependency, and the constitution clarification that the feature requires

- [X] T001 Bump package version 0.1.1 → 0.2.0 in `src/multi_sessionizer/__init__.py` and the `version` field of `pyproject.toml`; update the `--version` expectation in `tests/test_main.py` and `tests/test_cli.py` if pinned
- [X] T002 Add PyYAML as the only new runtime dependency in `pyproject.toml` (`dependencies = ["PyYAML"]`), justified by research R4 (workspace YAML validation/extraction; tmuxp itself uses PyYAML)
- [X] T003 [P] Amend the constitution to **v1.2.2** in `.specify/memory/constitution.md`: Principle II's domain module list gains `+ workspace`; Principle V's dependency examples lose `nvim` and gain `tmuxp`/`PyYAML`; bump `**Version**: 1.2.2`, update `Last Amended` to 2026-10-04, and record the diff description (PATCH: workspace domain module + tmuxp/PyYAML dependency list per plan.md Constitution Check)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure domain layer every user story consumes — DTO extensions, the `workspace` capability, and per-spec planning with marker-based dedup. No I/O anywhere in `domain/`. MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. `tests/test_layer_boundaries.py` must stay green throughout.

- [X] T004 Update `Selection` in `src/multi_sessionizer/domain/models.py`: rename field `files` → `workspaces` (second positional field, `workspaces: tuple[str, ...] = ()`), preserving the positional construction shape so existing `Selection(dirs, files)` calls keep working (SC-001, research R5). Add the `SessionSpec` DTO with fields `kind: str` (`"directory"` | `"workspace"`), `path: str = ""`, `definition: str = ""`, `fingerprint: str = ""`, `desired_name: str = ""` (data-model §1.2)
- [X] T005 Add `markers: Mapping[str, str] = {}` (session name → marker fingerprint) as the LAST field of `RuntimeSnapshot` in `src/multi_sessionizer/domain/models.py` so 3-arg positional constructions keep working (R12); add `input: str | None = None` as a keyword field on `Command` (executor materializes it to a temp file whose path is appended as the final argument — R12)
- [X] T006 [P] Write pure tests for the workspace capability in `tests/test_workspace.py` (RED): `fingerprint` is deterministic and name-independent; `validate_workspace` rejects invalid YAML, a non-mapping root, `windows` missing/not-a-list/empty, and a non-string `session_name`, and accepts a valid single-window workspace; `desired_name` honors a declared `session_name` and falls back to `msz-<fp[:12]>`; `workspace_label` returns `[tmuxp] <session_name>` or `[tmuxp] msz-<fp[:12]>` (data-model §1.9, R6/R10/R11)
- [X] T007 Create `src/multi_sessionizer/domain/workspace.py` (pure, PyYAML `yaml.safe_load`): `parse_workspace`, `validate_workspace(definition) -> list[str]`, `fingerprint` = `sha256(definition.encode()).hexdigest()` over the authored bytes (R3), `workspace_label`, `desired_name`, and a `Workspace` view with `definition`/`session_name`/`start_directory`/`windows`/`problems` (data-model §1.9). MUST satisfy the same purity rules as the rest of `domain/` (no subprocess, no `os.path.realpath`, no `os.environ`) so `tests/test_layer_boundaries.py` stays green
- [X] T008 [P] Add the workspace fallback name to `src/multi_sessionizer/domain/naming.py`: `desired_name` for a workspace without a declared `session_name` is `msz-<fingerprint[:12]>` (R11); keep `session_name` byte-identical for directories
- [X] T009 [P] Write plan tests for workspace specs in `tests/test_plan_workspaces.py` (RED): single new workspace emits `tmuxp load -d --no-progress -s <name> <cfg>` (with `input` set) then `tmux set-option -t <name> @multi-sessionizer-marker <fp>` then attach/switch; reuse emits NO tmuxp/set-option command; a taken desired name gets a numeric suffix; mixed dir+workspace selections produce the single-plan/single-post-step shape (domain-contracts §Command sequences)
- [X] T010 Extend `src/multi_sessionizer/domain/plan.py` with per-spec workspace planning: expand the selection into a flat ordered `SessionSpec` collection (directories first, then workspaces); keep the directory path-reuse logic byte-identical (SC-001); for workspaces reuse a session whose snapshot `markers[s] == fingerprint` (never keyed on name — FR-011), otherwise resolve a free name starting at `desired_name` (numeric suffix, never treating a foreign session as ours — FR-013) and emit `Command("tmuxp", ("load", "-d", "--no-progress", "-s", name, "<cfg>"), input=definition)` followed by `Command("tmux", ("set-option", "-t", name, "@multi-sessionizer-marker", fp))`; keep the single-selection shortcut and the shared multi-selection post-step; keep `plan_legacy(dirs, files, *, in_tmux, tmux_server_running, existing=None)` and make non-empty `files` a program error (domain-contracts §plan legacy wrapper)
- [X] T011 Update the file/nvim assertions that `plan.py` no longer supports: remove `test_single_file_opens_nvim`, `test_two_files_same_dir_share_session`, `test_file_dirname_collision_with_dir_disambiguated`, `test_mixed_dirs_then_files_processed_in_order`, `test_multi_files_first_session_from_dirname`, and the `test_core_plan_matches_legacy_wrapper_single_file` variant in `tests/test_decisions.py` and `tests/test_domain.py`; keep every directory assertion byte-identical (SC-001, SC-007)
- [X] T012 Verify the foundational checkpoint: `tests/test_workspace.py`, `tests/test_plan_workspaces.py`, `tests/test_domain.py`, `tests/test_decisions.py`, and `tests/test_layer_boundaries.py` all green with `.venv/bin/python -m pytest`

**Checkpoint**: Foundation ready — `plan()` already plans workspace selections (marker reuse, disambiguation, tmuxp + set-option commands) with zero I/O; user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Interactive picker provisions inline tmuxp workspaces (Priority: P1) 🎯 MVP

**Goal**: Workspaces declared as inline YAML under `tmuxp_workspaces` in `config.toml` appear in the interactive picker alongside directories; selecting one provisions a full multi-window/multi-pane tmux session matching the definition (FR-004, FR-006, FR-007).

**Independent Test**: Populate the config with an inline workspace definition, run the interactive picker, select the entry, and verify a tmux session with the exact windows/panes/commands is created and opened (spec US1).

### Tests for User Story 1 (write first — RED) ⚠️

- [X] T013 [P] [US1] Write interactive-flow tests in `tests/test_app_flows.py` (RED): with a fake config containing a `tmuxp_workspaces` entry, `interactive_flow` validates workspaces BEFORE the picker, lists `[tmuxp] <label>` lines in picker items alongside dirs, splits workspace labels from directory lines, builds `Selection(dirs, definitions)` and the executor observes the full workspace plan with NO real subprocess (fake adapters in `FlowDeps`, app-ports §FlowDeps)
- [X] T014 [P] [US1] Write Runner tests in `tests/test_runner.py` (RED, monkeypatch `subprocess.run` and `tempfile.mkdtemp`): a `Command` with `input` set is materialized to a temp file created under the CWD (`tempfile.mkdtemp(dir=os.getcwd())`), its path appended as the final `tmuxp load` argument, the temp dir removed afterwards (R1); non-zero tmuxp returncode raises a provisioning error; `snapshot()` populates `markers` from `tmux list-sessions -F "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}"` (R2)

### Implementation for User Story 1

- [X] T015 [US1] Add `tmuxp_workspaces: tuple[str, ...] = ()` to the `Config` DTO in `src/multi_sessionizer/app/configuration.py` (removing `additional_files` is US4 — add the field here, remove the other later); load it in `src/multi_sessionizer/infrastructure/config_loader.py` (`_FIELDS` + `"tmuxp_workspaces"`; missing key → empty tuple, no built-in defaults — constitution III). Each string is ONE picker entry (R8)
- [X] T016 [US1] Add `workspace_problems(self, problems: list[str]) -> None` to the `MessageOutput` protocol in `src/multi_sessionizer/app/ports.py` and its implementation in `src/multi_sessionizer/infrastructure/messages.py` (prints each validation problem to stderr, cli-contract §Error output item 5); leave `missing_paths`/`missing_files` in place (US4 removes them)
- [X] T017 [US1] Implement workspace provisioning in `src/multi_sessionizer/infrastructure/runner.py`: check `shutil.which("tmuxp")` before a build (raise a `ProvisioningError` with `tmuxp is required for workspace sessions but was not found on PATH.` — cli-contract error 8, FR-020); materialize `Command.input` to `tempfile.mkdtemp(dir=os.getcwd())`, append the path as the final arg, run `tmuxp load -d --no-progress -s <name> <temp-config>` with failure detection (non-zero returncode → provisioning error); after a successful build stamp the marker: `tmux set-option -t <name> @multi-sessionizer-marker <fp>`; delete the temp dir after the subprocess (R1/R9/R2)
- [X] T018 [US1] Populate `snapshot().markers` in `src/multi_sessionizer/infrastructure/runner.py`: extend the session listing format to `tmux list-sessions -F "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}"`; sessions without the option yield NO `markers` entry (treated foreign — FR-013); keep `existing_sessions()` and `execute()` signatures unchanged for legacy tests
- [X] T019 [US1] Rework `interactive_flow` in `src/multi_sessionizer/app/flows.py`: after config load, validate ALL configured workspaces via domain `validate_workspace` and report problems via `messages.workspace_problems` (return 1, no session created — FR-018, US5 scenario 2); build a `label -> definition` map and picker items (`[tmuxp] <label>` lines appended after dirs, duplicate display names disambiguated with the existing numeric-suffix rule — R10); split workspace labels from directory lines, classify the remaining directory lines via the unchanged `classify_selection`, and build `Selection(dirs, definitions)` for `run_selection` (data-model §6)
- [X] T020 [US1] Update the existing wiring tests in `tests/test_app_flows.py` and `tests/test_main.py` so the suite is green with the new `interactive_flow` sequence (validation before picker, label splitting, no `collect_files`/`missing_files` calls in the workspace path — full-wiring tests keep passing unchanged, SC-001)

**Checkpoint**: At this point, User Story 1 is fully functional — the picker lists `[tmuxp]` entries, selecting one builds the exact session from the workspace definition, and the session is stamped with its marker.

---

## Phase 4: User Story 2 - CLI provisions inline tmuxp workspaces (Priority: P1)

**Goal**: `multi-sessionizer session '<yaml>' [<yaml> ...]` provisions workspaces non-interactively with the same provisioning/reuse/switch semantics as interactive mode; `switch` remains directory-only (FR-008).

**Independent Test**: Run the CLI with an inline workspace definition and verify the session is built; run it again and verify the existing session is switched to, not duplicated (spec US2).

### Tests for User Story 2 (write first — RED) ⚠️

- [X] T021 [P] [US2] Write tests for the `session` subcommand in `tests/test_main.py` (RED): `_split_argv(["session", "<yaml>", "<yaml>"])` routes to `("session", ["<yaml>", "<yaml>"])`; `main(["session", "<yaml>"])` runs the session flow; an unknown command still exits 2 (FR-021); USAGE text shows the `session` subcommand
- [X] T022 [P] [US2] Write `session_flow` tests in `tests/test_app_flows.py` (RED): a valid inline workspace produces `Selection((), (definition,))` → `run_selection`; an invalid workspace (e.g. `'windows: []'`) reports the specific problem via `messages.workspace_problems` and returns 1 with NO executor call and no session created (FR-019, cli-contract error 5)

### Implementation for User Story 2

- [X] T023 [US2] Add the `session` branch to `_split_argv` and dispatch in `src/multi_sessionizer/main.py`: `first == "session"` → `("session", list(argv[1:]))`; dispatch to a new `session_flow(paths, deps)`; update `USAGE` to add `session YAML [YAML ...]` per cli-contract §Usage; `session` does NOT read the config file (self-contained, like `switch` today — R7)
- [X] T024 [US2] Implement `session_flow(paths: Sequence[str], deps: FlowDeps) -> int` in `src/multi_sessionizer/app/flows.py`: validate each inline workspace via domain `validate_workspace`; on any problem report via `messages.workspace_problems` and return 1 (no session created); otherwise `Selection((), tuple(paths))` → `run_selection` (data-model §6)
- [X] T025 [US2] Update `tests/test_cli.py` and the help/usage expectations in `tests/test_main.py` for the new subcommand surface (R7)

**Checkpoint**: `multi-sessionizer session '<yaml>'` builds the session and re-runs switch to the existing session (reuse relies on the US1 marker snapshot + the foundational dedup planning).

---

## Phase 5: User Story 3 - Dedup and session mapping per config entry (Priority: P1)

**Goal**: Per-entry, marker-based switch-vs-create decisions derived purely from live tmux state — never by session name, never with persisted state (FR-010..FR-014). The pure planning rules landed in Phase 2; this story hardens them (same-plan reuse, foreign sessions, restart statelessness) and proves them end-to-end.

**Independent Test**: Provision a workspace, restart the tmux server, and verify the tool still decides switch-vs-create correctly from the live tmux state alone (the marker survives inside the session — spec US3).

### Tests for User Story 3 (write first — RED) ⚠️

- [X] T026 [P] [US3] Write same-plan reuse tests in `tests/test_plan_workspaces.py` (RED): two identical definitions in ONE selection produce ONE session (one `tmuxp` + one `set-option`, then the shared post-step); a definition selected twice across plans reuses the snapshot-marked session under whatever name it has
- [X] T027 [P] [US3] Write foreign-session tests in `tests/test_plan_workspaces.py` (RED): a session whose name equals a candidate but whose marker is missing/mismatched is NEVER switched into — the plan creates its own session under a disambiguated name (US3 scenario 3, FR-013); two different definitions declaring the same `session_name` map to two sessions, the second created under `name-2` (US3 scenario 2, FR-017, SC-005)
- [X] T028 [P] [US3] Write restart/statelessness tests in `tests/test_plan_workspaces.py` (RED): the switch-vs-create decision derives purely from `snapshot.markers` + the spec fingerprint (no registry/DB/sidecar — FR-014); editing the definition produces a new fingerprint → a new session, never silent re-attach to the old one (spec edge case, R3)

### Implementation for User Story 3

- [X] T029 [US3] Implement per-plan marker tracking (`fp -> name`) in `src/multi_sessionizer/domain/plan.py` so two identical definitions in one plan reuse the same session; ensure a workspace reuse emits NO `tmuxp` and NO `set-option` command — only the attach/switch (domain-contracts §Command sequences); verify the marker check runs BEFORE name resolution so a foreign session with a colliding name is never adopted (FR-011/FR-013)
- [X] T030 [US3] Run the end-to-end dedup smoke verification from `specs/002-tmuxp-config-support/quickstart.md` step 5 under `scripts/tmux-sandbox.sh` (and `--zoxide-isolated`): SC-002 dedup (opening the same entry twice → one session), SC-003 multi-window/panes reproduced, SC-004 misnamed foreign session never switched into, SC-005 two workspaces with the same `session_name` → two sessions each recognized by its own marker, SC-006/US3-restart (kill-server inside the sandbox → fresh correct decision from live state), FR-020 (tmuxp hidden from PATH → clear error + exit 1), SC-008 (`session 'windows: []'` → exit 1, no session)

**Checkpoint**: Opening the same config entry twice reuses one session; foreign sessions are never hijacked; a server restart does not change switch-vs-create behavior — all from live tmux state alone.

---

## Phase 6: User Story 4 - File + nvim support is removed (Priority: P2)

**Goal**: File paths can no longer be configured or passed; the tool never launches nvim. The `additional_files` key, file/nvim code paths, and the nvim dependency are gone. Directory flows unchanged (FR-001..FR-003, SC-007).

**Independent Test**: Search the codebase and docs for file-path and nvim references; verify the config schema, CLI contract, dependency table, and tests no longer contain them, and that all directory behavior still passes (spec US4).

### Tests for User Story 4 (write first — RED) ⚠️

- [X] T031 [P] [US4] Update/remove the file/nvim tests across `tests/test_config.py` (drop `missing_files` imports/calls, `additional_files` configs), `tests/test_classifier.py` (file-path cases now expect the clear "files no longer supported" error), and `tests/test_runner.py` (no `send-keys`/nvim expectations) — RED against the current implementation
- [X] T032 [P] [US4] Write the rejection test in `tests/test_config.py` (RED): a TOML file containing `additional_files` raises `ConfigError` with the exact message `The 'additional_files' key is no longer supported; remove it or migrate entries to 'tmuxp_workspaces'.` (US4 scenario 1, R8)

### Implementation for User Story 4

- [X] T033 [US4] Reject `additional_files` in `src/multi_sessionizer/infrastructure/config_loader.py`: if the key is present in the TOML, raise `ConfigError` with the cli-contract message (never silently loaded); remove `additional_files` from `_FIELDS` and delete `missing_files`
- [X] T034 [US4] Remove file handling from `src/multi_sessionizer/infrastructure/classifier.py`: `classify_args` accepts directories only — a file path raises `ValueError("File paths are no longer supported; use directories or the 'session' subcommand with an inline tmuxp workspace: <path>")` and anything else raises `ValueError("Not a directory or file: <arg>")`, keeping the 2-tuple return shape (second slot always empty — app-ports §SelectionClassifier); `classify_selection` returns `Selection(dirs, ())`
- [X] T035 [US4] Remove `collect_files` from `src/multi_sessionizer/infrastructure/discovery.py` and the `CandidateDiscovery` protocol in `src/multi_sessionizer/app/ports.py`; remove `missing_files` from the `ConfigLoader` protocol and `flows.py` (the flow no longer references files); drop `additional_files` from the `Config` DTO in `src/multi_sessionizer/app/configuration.py`
- [X] T036 [US4] Update `src/multi_sessionizer/infrastructure/messages.py`: remove the files variant of the missing-path text (dirs-only output under `The following directories do not exist:` — cli-contract error 4), drop `missing_paths` in favor of dirs-only reporting, and update `CONFIG_EXAMPLE` (no `additional_files`, show `tmuxp_workspaces`)
- [X] T037 [US4] Remove every nvim/file reference from `README.md` (Features "Editor launch" bullet, Dependencies table `nvim` row, the config example, the file-path usage note) and add the two new dependency rows `tmuxp` (required for workspace sessions) and `PyYAML` (required — workspace YAML parsing) with documented purposes (constitution V)
- [X] T038 [US4] Update the legacy zero-logic facades: drop `missing_files` from `src/multi_sessionizer/config.py` and `collect_files` from `src/multi_sessionizer/discovery.py` (re-export only the surviving symbols)
- [X] T039 [US4] Run the removal verification from `specs/002-tmuxp-config-support/quickstart.md` step 6: `grep -rniE "nvim|additional_files|collect_files|send-keys" src/ tests/ README.md` → `CLEAN` (SC-007)

**Checkpoint**: No `additional_files`, no file arguments, no nvim anywhere in code, tests, docs, or the dependency table; all directory behavior still passes (SC-001).

---

## Phase 7: User Story 5 - Config and CLI surface for inline workspaces (Priority: P2)

**Goal**: A clear, documented, validated surface for inline workspaces (config list key + `session` subcommand), with validation that catches mistakes before any session is created; the selection is modeled as a collection of session specs so future array support is surface-only (FR-022).

**Independent Test**: A new user can declare a workspace and open it without reading tmuxp's docs, and invalid YAML is caught with a helpful message before the interactive run (spec US5).

### Tests for User Story 5 (write first — RED) ⚠️

- [X] T040 [P] [US5] Write config-surface tests in `tests/test_config.py` (RED): `tmuxp_workspaces` entries are loaded as a tuple of strings, each string is one entry, a missing key → `()`, and env/`~` expansion applies only to directory paths (workspace YAML is never expanded — R6)
- [X] T041 [P] [US5] Write picker-label tests in `tests/test_workspace.py` and `tests/test_plan_workspaces.py` (RED): `workspace_label` yields `[tmuxp] <session_name>` when declared and `[tmuxp] msz-<fp[:12]>` otherwise; duplicate displayed names are disambiguated for display with the numeric-suffix rule (R10, FR-007)
- [X] T042 [US5] Add the array-readiness test in `tests/test_plan_workspaces.py` (RED): expanding one input entry into multiple `SessionSpec`s BEFORE `plan` requires no change to the per-spec dedup/provisioning rules — proving the collection-of-session-specs model (FR-022, data-model §1.2)

### Implementation for User Story 5

- [X] T043 [US5] Document the inline-workspace surface in `README.md`: a "Workspaces" section with a `tmuxp_workspaces` config example (one string per entry), the `session` subcommand usage (`multi-sessionizer session '<yaml>'`), the validation rules (invalid YAML, non-mapping root, `windows` missing/empty, non-string `session_name`), and the array-readiness note (one entry → N sessions is a surface-only change)
- [X] T044 [US5] Ensure `CONFIG_EXAMPLE` in `src/multi_sessionizer/infrastructure/messages.py` shows a realistic `tmuxp_workspaces` entry so the missing-config hint teaches the new surface (cli-contract error 2)

**Checkpoint**: A new user can declare and open a workspace from the docs alone; invalid YAML is caught before any run; the domain is provably array-ready.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, full end-to-end validation, and final parity/removal verification across the whole feature.

- [X] T045 [P] Run the quality gates from `specs/002-tmuxp-config-support/quickstart.md` step 7: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check` — all green
- [X] T046 Run quickstart steps 1–4 (pure): full suite, pure workspace domain tests, static layer-boundary check (`DOMAIN CLEAN`), and app wiring + CLI gates
- [X] T047 Run quickstart step 5 end-to-end smoke under `scripts/tmux-sandbox.sh --zoxide-isolated` (US1–US3, SC-002–SC-006, FR-020, SC-008) and steps 6–7 (removal verification + quality gates)
- [X] T048 Final cross-cutting review: confirm SC-001 (100% of pre-existing directory tests unchanged), SC-007 (file/nvim fully absent), exit codes 0/1/2 preserved (FR-021), and the constitution v1.2.2 amendment is recorded in `.specify/memory/constitution.md`

**Checkpoint**: Feature complete and validated end-to-end under the sandbox; all quality gates green.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational completion
  - **US1 → US2**: US2's "re-run switches" test needs the US1 marker snapshot/provisioning
  - **US3**: Runs after the foundational planning (Phase 2); the end-to-end smoke (T030) requires US1 infra
  - **US4/US5**: Independent of each other; both depend on the Foundational layer. US4's classifier/config removals assume the US1/US2 surfaces are in place (removal only lands safely once nothing depends on files)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational (Phase 2) — no dependency on other stories
- **User Story 2 (P1)**: After Foundational + US1 marker snapshot (switching to an existing session needs `snapshot().markers`)
- **User Story 3 (P1)**: After Foundational; smoke verification (T030) after US1
- **User Story 4 (P2)**: After US1/US2 surfaces exist (removal follows replacement)
- **User Story 5 (P2)**: After Foundational; can run in parallel with US1–US4

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Red-Green-Refactor, constitution II)
- Domain/planning before infrastructure; infrastructure before flow wiring
- Story complete before moving to the next priority

### Parallel Opportunities

- Setup: T002, T003 are [P]
- Foundational: T006, T008, T009 (distinct test/source files) are [P]; T004 → T005 sequential (same file)
- US1: T013, T014 (distinct test files) are [P]; T015, T016, T017 are [P] (distinct files); T018, T019, T020 sequential
- US2: T021, T022 are [P]; T023, T024, T025 sequential
- US3: T026, T027, T028 are [P]; T029, T030 sequential
- US4: T031, T032 are [P]; T033..T039 mostly distinct files, several parallelizable (mark [P] as applicable)
- US5: T040, T041, T042 are [P]

---

## Parallel Example: User Story 1

```bash
# Launch tests and infrastructure for User Story 1 together:
Task: "Write interactive-flow tests in tests/test_app_flows.py"
Task: "Write Runner provisioning/marker tests in tests/test_runner.py"
Task: "Add tmuxp_workspaces to Config DTO + config_loader"
Task: "Add workspace_problems to ports.py + messages.py"
Task: "Implement tmuxp provisioning + marker set in runner.py"
```

---

## Parallel Example: User Story 3

```bash
# Launch all dedup tests for User Story 3 together:
Task: "Same-plan reuse tests in tests/test_plan_workspaces.py"
Task: "Foreign-session collision tests in tests/test_plan_workspaces.py"
Task: "Restart/statelessness tests in tests/test_plan_workspaces.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories; pure domain incl. marker-based dedup)
3. Complete Phase 3: User Story 1 (interactive picker provisions workspaces)
4. **STOP and VALIDATE**: picker lists `[tmuxp]` entries; selecting builds the exact session; same entry re-selected switches (marker dedup already in the domain)
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready (pure domain fully tested)
2. User Story 1 → interactive workspace provisioning (MVP!) → validate → deploy/demo
3. User Story 2 → `session` subcommand → validate → deploy/demo
4. User Story 3 → dedup/mapping hardening + end-to-end smoke → validate
5. User Story 4 → file/nvim removal → SC-007 clean
6. User Story 5 → docs + surface polish → validate
7. Polish → full quality gates + sandbox validation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (interactive picker + provisioning)
   - Developer B: User Story 5 (surface + docs) — independent of US1's infra details
   - Developer C: User Story 3 planning tests (Red) can start immediately after Foundational
3. US2 follows US1; US4 follows US1/US2; all integrate through the shared domain layer

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to a specific user story for traceability
- Each user story is independently completable and testable (pure domain tests need no external tools)
- Verify tests fail (RED) before implementing (Green) — constitution II is non-negotiable
- Anything creating/killing tmux sessions runs under `scripts/tmux-sandbox.sh` — never on the live default server (AGENTS.md tmux safety)
- Quality gates: `.venv/bin/python -m pytest -q` (not `uv run pytest`), `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check`
- The `domain/` layer must stay pure — `tests/test_layer_boundaries.py` guards it; PyYAML and `hashlib` are pure
- Avoid: vague tasks, same-file parallel conflicts, cross-story dependencies that break independence, adding logic to the top-level re-export facades

---

## Phase 9: Convergence

**Purpose**: Remaining work found by the convergence pass — dead code removal per Constitution V (YAGNI). `/speckit.implement` completes these; a follow-up converge run should find nothing further in scope.

- [X] T049 Keep and use `switch_flow`: move the actual switch implementation (classify with `ValueError` → error message → return 1) into `switch_flow` in `src/multi_sessionizer/app/flows.py`, wire `main.py`'s `switch` branch to call `switch_flow(paths, default_deps())`, drop the now-redundant `_run` seam, and update `tests/test_main.py` to dispatch to `switch_flow` (Constitution V / YAGNI; no-backward-compatibility rule)