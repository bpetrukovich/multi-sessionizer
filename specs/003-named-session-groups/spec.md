# Feature Specification: Named Session Groups

**Feature Branch**: `003-named-session-groups`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "I want to be able to add an array of config entries under a name in the config, so that I can launch several sessions at once with a single fzf click. Please also assess whether we can merge the `additional_dirs` and `tmuxp_workspaces` configs into one (`sessions`), and whether we can recognize lines that are directories, lines that are YAML tmuxp configs, and objects with a `name` field and a `sessions` field that is an array of directory lines and YAML tmuxp config lines."

## User Scenarios & Testing

### User Story 1 - One fzf selection launches a group of sessions (Priority: P1)

The user declares a named group in the config — a collection of directories and/or tmuxp workspaces. The interactive picker shows the group name as a single selectable entry. Selecting the group provisions every member session and ends up in one of them (or lets the user move through them), instead of the user having to select each entry separately.

**Why this priority**: This is the core of the feature — the reason to add groups is to turn several repeated picks into a single action.

**Independent Test**: Populate the config with a group of two directories and one tmuxp workspace, run the interactive picker, select the single group entry, and verify all three sessions are created (visible via `tmux list-sessions`) and the user ends up attached to one.

**Acceptance Scenarios**:

1. **Given** a config with a named group containing directories and workspaces, **When** the user selects the group in the picker, **Then** every member is provisioned as its own session and the user lands in one of them.
2. **Given** a group whose members are already running as sessions, **When** the user selects the group again, **Then** the tool switches to the existing member sessions rather than creating duplicates.
3. **Given** a group and ungrouped entries in the same config, **When** the picker runs, **Then** the group appears as one entry alongside individual entries, and both kinds can be mixed in a single multi-select run.

---

### User Story 2 - Unified `sessions` config recognizes three entry forms (Priority: P1)

The config exposes a single `sessions` list. Each element is recognized by its form: a string that is a directory is treated as a directory session; a string that is an inline YAML tmuxp workspace is treated as a workspace session; a table with a `name` and a `sessions` array is treated as a named group whose members are directory strings and/or workspace strings. The previous separate `additional_dirs` and `tmuxp_workspaces` keys are gone.

**Why this priority**: A single, uniformly-recognized surface is what makes the unified config approachable and replaces the earlier split keys. It is the enabling shape for US1.

**Independent Test**: Write one `sessions` config mixing a directory string, a workspace string, and a `{name, sessions}` group, and verify the picker lists the directory, the workspace, and the group (three entries).

**Acceptance Scenarios**:

1. **Given** a `sessions` entry that is an existing directory path, **When** the config is loaded, **Then** the entry is treated as a directory session.
2. **Given** a `sessions` entry that is a string containing a valid tmuxp YAML workspace, **When** the config is loaded, **Then** the entry is treated as a workspace session.
3. **Given** a `sessions` entry that is a table with a `name` and a `sessions` array, **When** the config is loaded, **Then** it is treated as a named group and its members are classified the same way as top-level entries.
4. **Given** a config that still uses `additional_dirs` or `tmuxp_workspaces`, **When** it is loaded, **Then** the tool reports a clear error rather than silently loading the old keys.

---

### User Story 3 - Group validation and errors are clear (Priority: P2)

A group whose name is missing, whose members are malformed, or that nests groups unsupported-ly is rejected with a clear, specific message before any session is created, mirroring today's config validation.

**Why this priority**: Correctness of the unified surface matters, but the primary flow (US1/US2) can be demonstrated before every malformed shape is fully covered.

**Independent Test**: Write several intentionally broken group configs (missing name, empty member list, non-recognizable member, nested group) and verify each produces a distinct, helpful error at validation time.

**Acceptance Scenarios**:

1. **Given** a group table without a `name`, **When** validation runs, **Then** the tool reports the missing name and skips/fails that group without creating sessions.
2. **Given** a group member that is neither a valid directory nor a valid workspace, **When** validation runs, **Then** the tool reports the specific member and does not create that session.
3. **Given** a member that is itself a group table, **When** validation runs, **Then** the tool rejects nesting with a clear message (nested groups are not supported).

---

### Edge Cases

- What happens when a `sessions` string is ambiguous — it looks like a directory but its text also happens to be valid YAML? It is treated as a directory if it does not have tmuxp workspace structure; only a string with workspace structure is treated as a workspace.
- What happens when a group has no members? The group is rejected as invalid rather than appearing as an empty selectable entry.
- What happens when the same directory or workspace appears both inside a group and as a top-level entry? Each occurrence is a distinct config entry, and dedup is per entry (an existing session for one occurrence is reused for that occurrence).
- What happens when two groups share a member? They remain independent entries; opening one group provisions its member sessions, and those sessions are reused if the other group is opened later (per-entry dedup).
- What happens when a group's `name` collides with a directory or workspace label? The picker disambiguates labels so the group is still selectable.
- What happens when a workspace member's session collides with a directory session's name? The existing marker-based switch-vs-create rules (feature 002) govern; a foreign session is never switched into wrongly.
- What happens when the picker is closed without selecting anything? Clean exit 0, no commands run (existing behavior preserved).
- What happens on a multi-select mixing groups, directories, and workspaces? Member sessions are provisioned one per config entry, in a single plan and single post-step, consistent with existing mixed selection behavior.

## Requirements

### Functional Requirements

#### Unified `sessions` config surface

- **FR-001**: The config MUST expose a single `sessions` list that accepts three element forms: directory strings, inline YAML tmuxp workspace strings, and group tables with a `name` field and a `sessions` array.
- **FR-002**: The `additional_dirs` and `tmuxp_workspaces` config keys MUST be removed; a config that uses them MUST be rejected with a clear error, not silently loaded.
- **FR-003**: Each `sessions` element MUST be classified by form: a string with tmuxp workspace structure is a workspace; any other string is a directory; a table with `name` and `sessions` is a group. Directory-like strings that are not workspace-shaped MUST be treated as directories.

#### Named groups

- **FR-004**: A group MUST appear in the interactive picker as a single entry labeled `[group] <name>` (plus any user-supplied `[tag...]` prefixes) via the unified tagged-label interface (feature 005).
- **FR-005**: Selecting a group MUST provision a separate session for each of its members and attach the user to one of them, with the same switch-vs-create behavior as selecting the members individually.
- **FR-006**: A group MUST NOT be provisionable as a single merged session; its members always map to distinct sessions.
- **FR-007**: Groups MUST NOT nest: a group whose `sessions` array contains another group table MUST be rejected.
- **FR-008**: A group without a `name` or with an empty `sessions` array MUST be rejected as invalid.
- **FR-009**: Dedup MUST remain per config entry: opening the same entry (top-level or as a group member) twice MUST reuse one session; two different entries MUST never map to the same session.

#### Validation and errors

- **FR-010**: Before an interactive run, the tool MUST validate every `sessions` entry (directory existence where applicable, workspace structure, group shape) and report problems in the same spirit as today's validation.
- **FR-011**: A malformed group member that is neither a valid directory nor a valid workspace MUST be reported specifically, and no session MUST be created for it.
- **FR-012**: The exit-code contract MUST be preserved: 0 success, 1 bad path/config, 2 unknown command.

#### Reuse of existing behavior

- **FR-013**: Directory sessions, workspace sessions (feature 002), marker-based switch-vs-create, collision naming, processing order, and the single-plan/single-post-step flow MUST behave identically for members of a group as they do for top-level entries.

### Key Entities

- **Config Entry**: a single selectable element in `sessions` — a directory string, a workspace string, or a group table.
- **Group**: a named collection of config entries (`name` + `sessions` array); appears as one picker entry and expands to one session per member.
- **Session**: an existing tmux session created from a directory or workspace entry; group members create sessions exactly as top-level entries do, with the same marker-based recognition.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of existing directory and workspace tests pass unchanged after the merge (behavior-parity gate for non-removed flows).
- **SC-002**: Selecting one group of N members produces exactly N distinct sessions (verified by `tmux list-sessions`), reachable in a single interactive pick.
- **SC-003**: Opening the same group twice produces exactly N sessions, not 2N (per-entry dedup verified).
- **SC-004**: A config mixing directory strings, workspace strings, and a group of both is loaded and rendered as one entry per element without parse or classification errors (0 failed entries).
- **SC-005**: Any config still using `additional_dirs` or `tmuxp_workspaces` fails with a clear error and no sessions are created.
- **SC-006**: Every malformed group shape (missing name, empty members, invalid member, nested group) is caught by validation with a specific message and 0 sessions created.

## Assumptions

- **Merge is breaking**: per the project's no-backward-compatibility rule, `additional_dirs` and `tmuxp_workspaces` are removed outright and replaced by `sessions`; no migration hint or compatibility shim is added.
- **Classification default**: a string is a workspace only if it has tmuxp workspace structure; any other string is a directory. This is deterministic and avoids ambiguous splits.
- **Group semantics**: a group is a shorthand for selecting several entries at once; it is not a merged session and is not provisionable as one. Group membership does not change how any member session is created, named, or recognized.
- **Nesting**: groups are one level deep only; nested groups are unsupported and rejected.
- **Group name uniqueness**: the picker disambiguates labels when a group name collides with another entry's label; group names are not required to be globally unique.
- **Attachment**: after a group selection, the user ends up in one member session; the exact member chosen and the means of moving between them (e.g., a follow-up prompt vs. landing on the first member) are planning details.
- **Interaction with feature 002**: this feature builds on the tmuxp workspace support (spec 002) and its marker-based session mapping; the unified `sessions` key supersedes the `tmuxp_workspaces` key introduced there. If 002 is not yet implemented, its workspace/marker behavior is a dependency for the workspace and group-member cases.