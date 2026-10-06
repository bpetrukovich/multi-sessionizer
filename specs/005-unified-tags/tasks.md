---

description: "Task list for Unified Picker Tags implementation"
---

# Tasks: Unified Picker Tags

**Input**: Design documents from `/specs/005-unified-tags/`

**Prerequisites**: plan.md, spec.md, data-model.md

**Tests**: Tests ARE requested — the constitution mandates test-first (Red-Green-Refactor). All feature 002/003/004 tests must pass unchanged (SC-001).

**Organization**: Tasks are grouped by slice to enable independent implementation and testing of each slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Existing layered architecture: `src/multi_sessionizer/domain/` (pure), `src/multi_sessionizer/app/` (wiring), `src/multi_sessionizer/infrastructure/` (side effects). Top-level modules under `src/multi_sessionizer/` are zero-logic re-export facades.
- Quality gates: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format . --check`

---

## Slice 1: Domain (US1/US2/US3)

**Purpose**: Unified tag model and rendering in the pure domain layer

- [x] T001 Add `tags: tuple[str, ...] = ()` to `SessionEntry` in `src/multi_sessionizer/domain/models.py`
- [x] T002 [P] Create `src/multi_sessionizer/domain/labels.py` with `render_picker_line(tags, label)` and `parse_tags(value)` (pure; validate non-empty, no whitespace/brackets; dedup first-occurrence)
- [x] T003 [P] Write `parse_tags`/group-tag tests in `tests/test_session_entries.py` (group with tags dedups; invalid `tags` type and whitespace tag reject the group)
- [x] T004 [P] Write `classify_external_input` tag tests in `tests/test_external.py` (group `tags:`; workspace `tags:` stripped from definition; tagless workspace stays verbatim; directory via CLI tags; `--tags` conflict rejects; invalid workspace tag rejects)
- [x] T005 Rewire `workspace_label` in `src/multi_sessionizer/domain/workspace.py` through `render_picker_line(("tmuxp",), desired_name)`
- [x] T006 Parse optional group `tags` in `src/multi_sessionizer/domain/session_entries.py::_classify_item` via `parse_tags`, attach to the group entry
- [x] T007 Extend `classify_external_input(arg, tags=())` in `src/multi_sessionizer/domain/external.py`: workspace `tags:` strip + `--tags` conflict, group conflict merge, directory CLI tags

## Slice 2: Storage (US2/US3)

**Purpose**: Persist and round-trip tags, migrate legacy stores

- [x] T008 [P] Add `tags TEXT` to `_SCHEMA` and a guarded idempotent `_migrate` (ALTER TABLE) in `src/multi_sessionizer/infrastructure/external_store.py`; serialize/deserialize JSON; re-attach tags in `_reconstruct_group(name, definition, tags)`; preserve tags in `_normalize`; serialize connect-time DDL with a process-wide lock
- [x] T009 [P] Write store tests in `tests/test_external_store.py` (directory/workspace/group tags round-trip; legacy schema without `tags` column is migrated and readable)

## Slice 3: App + CLI + display (US1/US2/US3)

**Purpose**: Unified labels surface, `--tags` CLI, docs

- [x] T010 Rewire `external_label` and `_group_display` in `src/multi_sessionizer/app/flows.py` through `render_picker_line` with structural tag + user tags; add `tags=` to `add_external_flow`
- [x] T011 Preserve group tags in `_normalize_entry` in `src/multi_sessionizer/infrastructure/config_loader.py`
- [x] T012 Add `_split_tags` and `--tags TAG[,TAG...]` handling to `src/multi_sessionizer/main.py::_external_dispatch`; update USAGE
- [x] T013 [P] Write app-flow tests in `tests/test_app_flows.py` (external_label with tags; add_external_flow with CLI tags; config group with tags renders `[group] [tag] name`; external tagged entry renders in the picker)
- [x] T014 [P] Write CLI tests in `tests/test_main.py` (`_split_tags`; `--tags` dispatch; `--tags`-only add is a missing-entry error; help text shows `--tags`)
- [x] T015 Update README: unified picker tags bullet, `--tags`/`tags:` examples, display-only semantics note

## Slice 4: Docs / follow-up (US2)

**Purpose**: Specs and the review-queue consumer

- [x] T016 Add `specs/005-unified-tags/` (spec.md, data-model.md, tasks.md); update the label-related FRs in `specs/002-tmuxp-config-support/spec.md`, `specs/003-named-session-groups/spec.md`, `specs/004-external-config-cli/spec.md` to the unified tagged rendering
- [ ] T017 (separate repo) `tmux-review-queue`: add `tags: [task.id]` to `group_yaml` in `src/tmux_review_queue/domain/workspaces.py` on its own branch, so the picker shows `[external] [<id>] <name>`