---

description: "Task list for the layered-architecture refactoring feature"
---

# Tasks: Layered Architecture Refactoring

**Input**: Design documents from `/specs/001-layered-architecture/`

**Prerequisites**: plan.md (done), spec.md (done), research.md (done), data-model.md (done), contracts/ (done)

**Tests**: Tests ARE included — FR-018/FR-019/FR-020 and `quickstart.md` explicitly require new test files (`tests/test_app_flows.py`, the layer-boundary guard) plus the existing 71-test suite as the parity gate.

**Organization**: Tasks are grouped by user story. Phases follow the true completion order (US1 → US3 → US4 → US2) because US2 (behavior parity) is the integration gate that consumes the domain, app, and infrastructure work products. Story priorities from spec.md are preserved and labeled.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Setup / Foundational / Polish tasks carry no story label
- Exact file paths included in every task

## Path Conventions

Single Python project (`src-layout`): source under `src/multi_sessionizer/`, tests under `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure for the three layers and a verified baseline.

- [x] T001 Create the three layer subpackages `src/multi_sessionizer/domain/`, `src/multi_sessionizer/app/`, `src/multi_sessionizer/infrastructure/`, each with an **empty** `__init__.py` (research R1: "Empty `__init__.py` files avoid accidental cross-layer imports"). No behavior in this phase.
- [x] T002 [P] Verify the pre-refactor baseline: run `.venv/bin/python -m pytest -q` from the repo root and confirm the full pre-existing suite passes (documented as 71 tests) BEFORE any code moves; record the green baseline.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain DTOs that every layer and every user story depends on, plus the static layer-boundary guard.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Create the domain DTOs in `src/multi_sessionizer/domain/models.py` as frozen dataclasses per data-model.md §1.1–§1.4:
  - `Selection(dirs: tuple[str, ...], files: tuple[str, ...])` — "Frozen dataclass" (FR-007)
  - `RuntimeSnapshot(in_tmux: bool, tmux_server_running: bool, existing: Mapping[str, str])` — "Frozen dataclass"; `existing` is a "Mapping[str, str] field (a plain dict at construction)" (FR-008)
  - `Command(program: str, args: tuple[str, ...])` with `def argv(self) -> list[str]: return [self.program, *self.args]` (FR-009)
  - `class CommandPlan(list[Command])` — "an ordered list of commands. Equality, indexing, and slicing behave like a plain `list`" (FR-009)
- [x] T004 [P] Add the static layer-boundary guard in `tests/test_layer_boundaries.py` per quickstart.md §3 (SC-003/SC-004): assert no module under `src/multi_sessionizer/domain/` imports `app` or `infrastructure`, references `subprocess`, reads `os.environ`, or calls `os.path.realpath`; and that every behavioral module has exactly one layer. This guard is written now and stays green for the whole refactor.

**Checkpoint**: Foundation ready — DTOs exist and the boundary guard is in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Domain logic testable in isolation (Priority: P1) 🎯 MVP

**Goal**: All session-planning logic (naming, ranking, planning, run) lives in a pure `domain/` package that receives everything it needs (selection, runtime snapshot, executor) explicitly and never touches tmux, fzf, zoxide, the filesystem, or the environment.

**Independent Test**: Run the domain tests on a machine where none of tmux/fzf/zoxide are installed or reachable and no `TMUX` env var is set — all pass (quickstart.md §2, SC-002).

### Tests for User Story 1

> **NOTE**: These are direct DTO-driven tests (FR-018). Write them to exercise the pure core; they must pass with zero external tools.

- [x] T009 [P] [US1] Write direct domain tests in `tests/test_domain.py` that construct `Selection`/`RuntimeSnapshot` by hand and assert:
  - determinism (same selection + snapshot twice → identical `CommandPlan`)
  - existing-session reuse (`existing={"dup": "/a/dup"}` → reuses, no `new-session`) and numeric-suffix disambiguation (`dup`, `dup-2`, `dup-3`)
  - DTO core `plan(selection, snapshot)` equals the legacy wrapper output for representative scenarios (single dir, single file, multi dirs, empty)
  - `run(selection, snapshot, fake_executor)` hands the produced `CommandPlan` to the executor and executes nothing else (FR-012/FR-018)

### Implementation for User Story 1

- [x] T005 [P] [US1] Implement `session_name(path: str) -> str` in `src/multi_sessionizer/domain/naming.py` (move logic verbatim from flat `src/multi_sessionizer/naming.py`; `os.path.basename` is an allowed pure string helper — NO filesystem/environment access in domain).
- [x] T006 [P] [US1] Implement `parse_zoxide_scores(text) -> dict[str, float]`, `rank_dirs(dirs, scores)`, `build_picker_list(dirs, scores, files)` in `src/multi_sessionizer/domain/rank.py` (move logic verbatim from flat `src/multi_sessionizer/rank.py`; stays pure).
- [x] T007 [US1] Implement session planning in `src/multi_sessionizer/domain/plan.py` (depends on T003, T005):
  - Core `plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan` (FR-007/FR-008, R4) plus pure wrapper `plan_legacy(dirs, files, *, in_tmux, tmux_server_running, existing=None)` that builds the DTOs and delegates to the core (R4: "exposed as `plan` via the `decisions` facade").
  - R2: "The domain compares paths **literally** (`_same_path` becomes `a == b`)". Remove `os.path.realpath` from the domain entirely; `os.path.dirname` (string helper) is allowed.
  - Preserve exact behavior: `zoxide add <dir>`; `tmux new-session -ds <name> -c <dir>`; single → `attach -t` / `switch-client` + `refresh-client -S`; single file → parent-dir session + `tmux send-keys -t <name> "nvim '<file>'" Enter`; multiple → dirs before files, one post-step (`attach -t <first>` | `choose-session` + `refresh-client -S` | plain `attach`) per domain-contracts.md.
- [x] T008 [US1] Implement `run` in `src/multi_sessionizer/domain/run.py` (R6/FR-012, depends on T007): define `CommandExecutor` as a `typing.Protocol` with `def execute(self, cmds: CommandPlan) -> None` and `def run(selection, snapshot, executor) -> None` that calls `plan(...)` then `executor.execute(plan)`.

**Checkpoint**: At this point, User Story 1 is complete — the domain is a pure, directly-testable package and the boundary guard (T004) is green.

---

## Phase 4: User Story 3 - App is a thin, readable wiring layer (Priority: P2)

**Goal**: `app/` owns the `Configuration` DTO and the adapter contracts, and `flows.py` reads as a pure composition chain (config → discover → rank → pick → classify → run) with no business rules and no raw external calls.

**Independent Test**: Statically scan the app layer — no direct subprocess/environment/filesystem/terminal calls appear in it (US3 acceptance, SC-006).

### Tests for User Story 3

> **NOTE**: App wiring tests inject fake adapters (FR-020). `quickstart.md` §4 references `tests/test_app_flows.py` explicitly.

- [x] T013 [US3] Write `tests/test_app_flows.py` that injects fake adapters into a `FlowDeps` bundle and asserts the wiring sequence with no real side effects (depends on T010–T012):
  - `interactive_flow`: fake config → fake discovery → fake scorer/rank → fake picker → fake classifier → fake probe → fake executor; assert the call order and the final `CommandPlan`
  - `switch_flow(paths, deps)`: fake classifier.classify_args → fake probe → fake executor
  - `run_selection`: fake probe snapshot + fake executor → expected plan observed, **no real subprocess executed** (US4 acceptance 1, covered here)
  - config-not-found → returns 1 and `messages.config_not_found` called
  - missing files/dirs → returns 1 and `messages.missing_paths` called
  - empty picker selection → returns 0, executor never called

### Implementation for User Story 3

- [x] T010 [US3] Define the app-owned `Configuration` DTO and config error in `src/multi_sessionizer/app/configuration.py` (FR-011): frozen dataclass named `Config` with `project_roots_depth_1`, `project_roots_depth_2`, `additional_dirs`, `additional_files`, all `tuple[str, ...]`; "Missing keys → empty tuple (no built-in defaults)". Also define `ConfigNotFoundError` here (FR-006: the higher layer defines boundary contracts; infra raises it).
- [x] T011 [US3] Define the adapter contracts in `src/multi_sessionizer/app/ports.py` per contracts/app-ports.md (depends on T010): `typing.Protocol`s — `ConfigLoader` (`load()`, `missing_files(cfg)`, `missing_dirs(cfg)`), `CandidateDiscovery` (`collect_dirs(cfg)`, `collect_files(cfg)`), `ZoxideScorer` (`scores() -> str`), `Picker` (`pick(items) -> list[str]`), `SelectionClassifier` (`classify_args(argv)`, `classify_selection(lines) -> Selection`), `EnvironmentProbe` (`snapshot() -> RuntimeSnapshot`), `MessageOutput` (`config_not_found`, `missing_paths`, `error`) — no `@runtime_checkable` (R5). Add frozen `@dataclass FlowDeps` bundling all seven plus `executor: CommandExecutor`.
- [x] T012 [US3] Implement the app flows in `src/multi_sessionizer/app/flows.py` (FR-013/FR-014, depends on T011):
  - `run_selection(selection, deps) -> int`: `probe.snapshot()` → `run(selection, snapshot, deps.executor)` (domain) → `0`
  - `interactive_flow(deps) -> int`: catch `ConfigNotFoundError` → `messages.config_not_found(path)` → `1`; missing paths → `messages.missing_paths(...)` → `1`; else config → `discovery.collect_dirs/collect_files` (infra) → `parse_zoxide_scores` + `build_picker_list` (domain) → `picker.pick` → `classifier.classify_selection` → `run_selection`; empty pick → `0`
  - `switch_flow(paths, deps) -> int`: `classifier.classify_args(paths)` → wrap into `Selection` → `run_selection`
  - Contains NO business rules and NO raw subprocess/filesystem/environment/terminal calls.

**Checkpoint**: At this point, User Story 3 is complete — the app layer is pure composition, testable end-to-end with fake adapters.

---

## Phase 5: User Story 4 - Infrastructure adapters are replaceable behind contracts (Priority: P3)

**Goal**: Every external interaction (config file, discovery, arg classification, subprocess execution, environment probe, terminal) is isolated behind an app/domain contract in `infrastructure/`. Replacing an adapter (fake executor, different picker) requires no domain change and at most the wiring line (SC-005).

**Independent Test**: Inject a fake command executor into a flow; run a full selection through the app wiring; verify the domain produced the expected commands without any real subprocess executing (US4 acceptance).

### Tests for User Story 4

- [x] T019 [P] [US4] Add infrastructure adapter tests:
  - `tests/test_classifier.py`: `classify_args` (realpath, dir vs file, `ValueError("Not a directory or file: <arg>")`) and `classify_selection` (realpaths each picker line, dir vs file → `Selection`)
  - Extend `tests/test_runner.py`: `Runner.snapshot()` builds `RuntimeSnapshot` — `in_tmux` from the `TMUX` env var, `tmux_server_running` via `pgrep tmux`, `existing` from `tmux list-sessions -F "#{session_name}\t#{session_path}"` with values **realpath-normalized** (monkeypatch `subprocess.run` as today)
  - Full-wiring replaceability test: build real infra adapters (temp config file, real `tmp_path` discovery, real classifier) into `FlowDeps` but inject a **fake executor**; run `interactive_flow`/`run_selection` and assert the expected `CommandPlan` is produced with no real subprocess (SC-005, US4 acceptance)

### Implementation for User Story 4

- [x] T014 [P] [US4] Implement `ConfigLoader` in `src/multi_sessionizer/infrastructure/config_loader.py` (depends on T010): `load_config(path=None)` reads the TOML file at `$MULTI_SESSIONIZER_CONFIG` or `~/.config/multi-sessionizer/config.toml`, raises `ConfigNotFoundError` (from app) if absent, expands env vars and `~` in every path, missing keys → empty tuple; `missing_files(cfg)` / `missing_dirs(cfg)` (constitution III). Move logic verbatim from flat `src/multi_sessionizer/config.py`.
- [x] T015 [P] [US4] Implement `CandidateDiscovery` in `src/multi_sessionizer/infrastructure/discovery.py` (depends on T010): `collect_dirs(cfg)` / `collect_files(cfg)` — move logic verbatim from flat `src/multi_sessionizer/discovery.py`. Keep `_find_dirs` pruned at the configured depth (constitution IV, pinned by `test_scan_cost_is_bounded_by_max_depth`) and output `os.path.abspath` (logical) form — do NOT realpath (R2).
- [x] T016 [P] [US4] Implement `SelectionClassifier` in `src/multi_sessionizer/infrastructure/classifier.py` (depends on T003): `classify_args(argv) -> tuple[list[str], list[str]]` — "each arg is realpath'd; dir → dirs, file → files; otherwise raises `ValueError("Not a directory or file: <arg>")`"; `classify_selection(lines) -> Selection` — realpath each line, dir vs file. Use a `normalize_path = os.path.realpath` helper (R2).
- [x] T017 [US4] Refactor `Runner` in `src/multi_sessionizer/infrastructure/runner.py` to satisfy the app ports (depends on T011, T003): implement `EnvironmentProbe.snapshot()` ("in_tmux from the TMUX env var; tmux_server_running via pgrep tmux; existing from tmux list-sessions with values realpath-normalized"), `ZoxideScorer.scores()` ("runs zoxide query -l -s; returns raw stdout"), `Picker.pick()` ("fzf --tmux --multi --prompt \"Project > \""), and `CommandExecutor.execute(cmds)`. KEEP the legacy methods `tmux_running()`, `existing_sessions()`, `zoxide_scores()`, `run_fzf()`, `execute()` with identical signatures and parse behavior (test_runner.py depends on them).
- [x] T018 [US4] Implement `ConsoleMessageOutput` in `src/multi_sessionizer/infrastructure/messages.py` per R7: `config_not_found(path)` prints the exact pre-refactor guidance to stderr (blank line, "Create it with an example:", the example TOML block, and the `MULTI_SESSIONIZER_CONFIG` override hint), `missing_paths(files, dirs)` prints "The following files do not exist:" / "The following directories do not exist:" listings, `error(msg)` prints the message to stderr. Define `CONFIG_EXAMPLE` here (exact text from current `src/multi_sessionizer/main.py`) so the app flow never prints directly.

**Checkpoint**: At this point, User Story 4 is complete — all side effects are isolated behind replaceable contracts.

---

## Phase 6: User Story 2 - Behavior parity for every existing flow (Priority: P1)

**Goal**: After wiring the layers together, every user-facing flow behaves exactly as before: interactive run, `switch`, `--help`, `--version`, error cases, exit codes (0/1/2), printed output, and the exact tmux/zoxide command sequence. The existing 71-test suite passes **unchanged** (SC-001).

**Independent Test**: Run the full existing test suite unchanged against the refactored code (`.venv/bin/python -m pytest -q`) and smoke-test the installed console script (quickstart.md §1 and §5).

### Implementation for User Story 2

> Convert the seven flat modules to **zero-logic re-export facades** (plan.md Complexity Tracking, SC-004). Tests import legacy paths and monkeypatch `discovery.os.scandir` / `runner.subprocess.run` — so the `discovery` and `runner` facades MUST expose the `os` / `subprocess` modules.

- [x] T020 [P] [US2] Convert `src/multi_sessionizer/naming.py` to a facade re-exporting `session_name` from `domain.naming` (depends on T005).
- [x] T021 [P] [US2] Convert `src/multi_sessionizer/rank.py` to a facade re-exporting `parse_zoxide_scores`, `rank_dirs`, `build_picker_list` from `domain.rank` (depends on T006).
- [x] T022 [P] [US2] Convert `src/multi_sessionizer/decisions.py` to a facade re-exporting `Command` from `domain.models` and `plan` (= the legacy wrapper `plan_legacy`) plus `plan_legacy` from `domain.plan` so the 21 existing `plan(...)` calls stay byte-identical (depends on T007).
- [x] T023 [P] [US2] Convert `src/multi_sessionizer/cli.py` to a facade re-exporting `classify_args` from `infrastructure.classifier` (depends on T016).
- [x] T024 [P] [US2] Convert `src/multi_sessionizer/config.py` to a facade re-exporting `Config` from `app.configuration` and `load_config`, `missing_files`, `missing_dirs`, `ConfigNotFoundError` from `infrastructure.config_loader` (depends on T010, T014).
- [x] T025 [P] [US2] Convert `src/multi_sessionizer/discovery.py` to a facade re-exporting `collect_dirs`/`collect_files` from `infrastructure.discovery`; MUST also `import os` so `discovery.os.scandir` monkeypatching keeps working (depends on T015).
- [x] T026 [P] [US2] Convert `src/multi_sessionizer/runner.py` to a facade re-exporting `Runner` from `infrastructure.runner`; MUST also `import subprocess` so `runner.subprocess.run` monkeypatching keeps working (depends on T017).
- [x] T027 [US2] Refactor `src/multi_sessionizer/main.py` into the infrastructure CLI dispatch + composition root (depends on T012, T016, T017, T018): keep `_split_argv`, `USAGE`, `_package_version`, `main(argv)`, and `_run(dirs, files)` (required by test_main.py monkeypatching); add `default_deps()` returning a real `FlowDeps` (one `Runner` as scorer/picker/probe/executor + config loader + discovery + classifier + `ConsoleMessageOutput`). `_run` builds `Selection(dirs, files)` and calls `run_selection` (app flow). Interactive branch → `interactive_flow(default_deps())`. Switch branch → classify via the classifier catching `ValueError` (print message, return 1) then `_run(dirs, files)`. Unknown/help/version output stays in `main.py`. Re-export `CONFIG_EXAMPLE` from `infrastructure.messages` so `main.CONFIG_EXAMPLE` still resolves.
- [x] T028 [US2] Run the full behavior-parity gate: `.venv/bin/python -m pytest -q` — ALL pre-existing tests (documented as 71) pass **unchanged** (SC-001).
- [x] T029 [US2] Manual console-script smoke test per quickstart.md §5 (real tools + valid config): `--help` (exit 0), `--version` ("multi-sessionizer 0.1.1", exit 0), unknown command (exit 2), missing config (exit 1 + guidance), bad switch path (exit 1), `switch /some/real/dir /some/file.py` — byte-identical output and exit codes; `switch` produces the same ordered tmux/zoxide commands.

**Checkpoint**: At this point, User Story 2 is complete — full behavior parity proven by the unchanged suite and smoke tests.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Governance amendment, documentation, cleanup, and final quality gates that affect the whole refactor.

- [x] T030 [P] Amend the constitution at `.specify/memory/constitution.md` to **v1.2.0** (spec-mandated, plan.md Constitution Check): restate Principle II's module list in layered terms (pure business logic lives in `domain`; all side effects live in `infrastructure`; external tools invoked only through infrastructure adapters). Bump the version, update `Last Amended`, and add the diff description per governance rules.
- [x] T031 [P] Update `README.md` project-structure documentation to describe the three layers, the DTO ownership rule (FR-006), and the adapter contracts (English only, per constitution).
- [x] T032 [P] Validate `quickstart.md` steps 1–4 end-to-end: behavior-parity gate, domain-isolation gate (`env -u TMUX .venv/bin/python -m pytest tests/test_decisions.py tests/test_naming.py tests/test_rank.py -q`), static layer-boundary check (`grep -rEl "subprocess|os\.environ|os\.path\.realpath|import app|import infrastructure" src/multi_sessionizer/domain/` → "DOMAIN CLEAN"), and app-wiring gate (`tests/test_app_flows.py`).
- [x] T033 Final cleanup: verify every top-level facade (`cli.py`, `config.py`, `discovery.py`, `rank.py`, `naming.py`, `decisions.py`, `runner.py`) is zero-logic re-export with no leftover duplicated code, and confirm no `os.path.realpath` remains anywhere under `src/multi_sessionizer/domain/`.
- [x] T034 Run final quality gates: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, and `.venv/bin/ruff format . --check` all green (constitution dev-workflow gate).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories (domain DTOs are the layer contracts).
- **User Stories (Phases 3–6)**: Depend on Foundational. Completion order is **US1 → US3 → US4 → US2**:
  - **US1** (domain) first — nothing else can exist without the pure core and DTOs.
  - **US3** (app) next — app ports/flows consume domain and define the contracts infra satisfies.
  - **US4** (infrastructure) next — adapters implement the app ports and produce domain DTOs.
  - **US2** (parity) LAST — the parity gate consumes all three layers: facades re-export domain/infra, and `main.py` dispatches into app flows. US2 is the integration gate, not the first implementation step.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational — no dependencies on other stories.
- **User Story 3 (P2)**: Depends on US1 (consumes `domain.rank`, `domain.run`, DTOs). Independently testable with fake adapters.
- **User Story 4 (P3)**: Depends on US3 (implements app ports) and US1 (produces domain DTOs).
- **User Story 2 (P1)**: Depends on US1 + US3 + US4 work products. This is why the parity gate is sequenced last.

### Within Each User Story

- Tests are written alongside implementation (FR-018/FR-019/FR-020 are functional requirements, not optional).
- Domain capabilities (naming/rank) before plan/run; plan before run.
- App: DTO (`configuration.py`) before ports, ports before flows, flows before tests.
- Infra: adapters before adapter tests; `config_loader`/`discovery`/`classifier`/`messages` are independent of `runner`.
- US2: facades before `main.py`, `main.py` before the parity gate, parity gate before smoke test.

### Parallel Opportunities

- All Setup/Foundational tasks marked [P] run in parallel.
- **US1**: `naming.py` and `rank.py` in parallel; direct tests in parallel with the plan/run work (they only need the DTOs).
- **US3**: `configuration.py` and `ports.py` are sequential (ports reference `Config`); flows then tests.
- **US4**: `config_loader.py`, `discovery.py`, `classifier.py`, `messages.py` in parallel; `runner.py` independent of those four; adapter tests in parallel.
- **US2**: all seven facade conversions in parallel (T020–T026) after US1/US4 artifacts exist; `main.py` after flows; parity gate after main.
- **Polish**: constitution, README, quickstart validation, and cleanup in parallel; final quality gates last.

---

## Parallel Example: User Story 1

```bash
# Launch the two pure modules together:
Task: "Implement session_name in src/multi_sessionizer/domain/naming.py"
Task: "Implement parse_zoxide_scores/rank_dirs/build_picker_list in src/multi_sessionizer/domain/rank.py"
```

## Parallel Example: User Story 4

```bash
# Launch the independent infrastructure adapters together:
Task: "Implement ConfigLoader in src/multi_sessionizer/infrastructure/config_loader.py"
Task: "Implement CandidateDiscovery in src/multi_sessionizer/infrastructure/discovery.py"
Task: "Implement SelectionClassifier in src/multi_sessionizer/infrastructure/classifier.py"
Task: "Implement ConsoleMessageOutput in src/multi_sessionizer/infrastructure/messages.py"
```

## Parallel Example: User Story 2 (facades)

```bash
# Launch all facade conversions together (after US1/US4 artifacts exist):
Task: "Convert src/multi_sessionizer/naming.py to a re-export facade"
Task: "Convert src/multi_sessionizer/rank.py to a re-export facade"
Task: "Convert src/multi_sessionizer/decisions.py to a re-export facade"
Task: "Convert src/multi_sessionizer/cli.py to a re-export facade"
Task: "Convert src/multi_sessionizer/config.py to a re-export facade"
Task: "Convert src/multi_sessionizer/discovery.py to a re-export facade"
Task: "Convert src/multi_sessionizer/runner.py to a re-export facade"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (subpackages + baseline).
2. Complete Phase 2: Foundational (DTOs + boundary guard).
3. Complete Phase 3: User Story 1 (pure domain + direct tests).
4. **STOP and VALIDATE**: run `tests/test_domain.py` and `tests/test_layer_boundaries.py` with no external tools — this is the deliverable proving the domain is isolable.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 (pure domain) → test independently → the refactor's core value is proven.
3. US3 (app wiring) → test with fakes → wiring is readable and side-effect-free.
4. US4 (infrastructure adapters) → adapters replaceable behind contracts.
5. US2 (parity gate) → facades + `main.py` → full 71-test suite passes unchanged → smoke test → deploy/demo.
6. Polish: constitution amendment v1.2.0, README, quickstart validation, quality gates.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together.
2. Developer A: User Story 1 (domain).
3. Developer B: User Story 3 (app) once US1's domain is available.
4. Developer C: User Story 4 (infrastructure) once US3's ports are available.
5. Everyone integrates for User Story 2 (facades + `main.py` + parity gate) — the behavior-parity gate is the final, shared checkpoint.

---

## Notes

- [P] tasks = different files, no dependencies.
- [Story] label maps a task to its user story for traceability.
- Behavior parity is the top priority: this refactor adds NO features and removes NO behavior (FR-017).
- Do NOT change the module-level constants or monkeypatch surfaces the tests rely on (`discovery.os`, `runner.subprocess`, `main._run`, `main._split_argv`, `Runner` legacy methods).
- The constitution amendment (T030) is spec-mandated and must be recorded as MINOR → v1.2.0.
- Commit after each task or logical group; stop at any checkpoint to validate.