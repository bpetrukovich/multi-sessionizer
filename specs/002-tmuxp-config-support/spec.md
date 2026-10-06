# Feature Specification: tmuxp Config Support

**Feature Branch**: `002-tmuxp-config-support`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Currently users can specify files in the config and we open the folder containing that file and the file with nvim. This is inflexible, nvim is hardcoded and I generally want to move away from it. The idea is to add support for tmuxp configs. Again, there should be dedup by config entry. Support is also needed in the CLI. There are many business questions here — your task is to find out all of them from me. 1. Remove the ability to specify file paths and open nvim. 2. I do not think we need to add the ability to specify tmuxp config file paths yet — I think we can do inline config (both in the interactive user config and passed on the CLI). Then I want to support a case where a folder opens separately in one session, and in another we can open the same tmuxp in the same folder. So most likely we need some way to map tmux sessions to our provisioned/processed configs (to know whether to switch to a session or create a new one), which I think is the hardest part, while keeping our tool stateless. tmuxp supports both JSON and YAML configs; we need to choose at least one, we are not required to support both. 3. Another point — whether to use the user's session_name or manage it ourselves; I think managing it on our side may be needed, take a look."

**Clarifications resolved** (2026-10-04):

- Q1 **Format**: YAML only (tmuxp's canonical format; JSON documents parse as-is since JSON is a subset of YAML, but JSON is not a supported surface).
- Q2 **Mapping & naming**: The tool recognizes its own sessions by a marker stored inside tmux (a session option) — **never by session name**. The tool does NOT manage `session_name` or the working directory (`start_directory`): both are honored from the workspace definition, because identity comes from the marker, not from the name. This is the flexible choice for the downstream tool.
- Q3 **Surface**: Inline YAML strings in `config.toml` (a list key), and a dedicated CLI subcommand taking an inline workspace. The domain model treats a selection as a *collection* of session specs from the start, so future support for arrays of sessions (one entry / one CLI param = several sessions) is a surface-only change.

## User Scenarios & Testing

### User Story 1 - Interactive picker provisions inline tmuxp workspaces (Priority: P1)

The user declares tmuxp workspaces inline in the config file. The interactive picker lists them alongside directories. Selecting one builds a full multi-window/multi-pane tmux session matching the workspace definition (window names, layouts, start directories, shell commands). This replaces today's "file → nvim" flows entirely.

**Why this priority**: This is the heart of the feature — the reason to add tmuxp support is to replace the hardcoded nvim file-opening with declarative, user-defined workspaces that the picker can open.

**Independent Test**: Without tmuxp or the config file paths feature, populate the config with an inline workspace definition, run the interactive picker, select the entry, and verify a tmux session with the exact windows/panes/commands is created and opened.

**Acceptance Scenarios**:

1. **Given** a config containing an inline tmuxp workspace, **When** the interactive run lists entries, **Then** the workspace appears in the picker and selecting it provisions a session that reproduces the workspace definition.
2. **Given** a config with both directories and inline workspaces, **When** the user multi-selects, **Then** each selected entry gets its own session, with directory sessions and workspace sessions never merged.
3. **Given** an inline workspace whose start directory is also a configured directory entry, **When** both are opened in separate runs, **Then** two independent sessions exist — a plain folder session and a workspace session — without conflict.
4. **Given** a workspace whose definition sets `session_name` and `start_directory`, **When** the session is provisioned, **Then** the session is named and rooted exactly as the workspace declares, unless a name collision forces a disambiguation.

---

### User Story 2 - CLI provisions inline tmuxp workspaces (Priority: P1)

The user passes an inline tmuxp workspace on the CLI without opening the interactive picker. The workspace is provisioned the same way and with the same reuse/switch semantics as in interactive mode.

**Why this priority**: Scriptability is a core constitution principle (Principle I); a feature that only works interactively would break the tool's contract. A dedicated CLI surface is also what the planned downstream tool (a multi-repo review-queue wrapper) will call to launch per-repository sessions.

**Independent Test**: Run the CLI with an inline workspace definition and verify the session is built; run it again and verify the existing session is switched to, not duplicated.

**Acceptance Scenarios**:

1. **Given** a valid inline workspace passed on the CLI, **When** the command runs, **Then** the session is provisioned and the user ends up in it (or it is switched to, depending on context).
2. **Given** an invalid inline workspace passed on the CLI, **When** the command runs, **Then** the tool exits with a clear error and a meaningful exit code, and no session is created.

---

### User Story 3 - Dedup and session mapping per config entry (Priority: P1)

The tool recognizes its own provisioned sessions and decides "switch to existing" vs "create new" per config entry, without any external state (no registry file, no database). Recognition is based on a marker stored inside the tmux session itself — not on the session name — so even a session with any name, or a foreign session that happens to match, is classified correctly. Opening the same config entry twice reuses one session; two different entries never share a session.

**Why this priority**: This is the hardest and most valuable part (stated by the user). Because identity is decoupled from names, the tool does not need to police or manage session names, which keeps it flexible for future array support and for the downstream tool that drives its own named sessions.

**Independent Test**: Provision a workspace, restart the tmux server, and verify the tool still decides switch-vs-create correctly from the live tmux state alone (the marker survives inside the session).

**Acceptance Scenarios**:

1. **Given** a session already provisioned from config entry X, **When** entry X is selected again, **Then** the tool switches to the existing session instead of creating a duplicate.
2. **Given** two different config entries, **When** both are opened, **Then** they map to two different sessions even if their definitions declare the same `session_name` (the second is created with a disambiguated name).
3. **Given** an unrelated user-created tmux session whose name collides with a candidate, **When** the corresponding entry is opened, **Then** the tool does not switch into the foreign session and provisions its own session instead.
4. **Given** a workspace that declares no `session_name`, **When** it is provisioned, **Then** the tool assigns it a deterministic name so the session is still created and later recognized.
5. **Given** the tool's behavior after a tmux server restart, **When** an entry is opened again, **Then** the decision (switch vs create) is made without any persisted state other than what lives inside tmux itself.

---

### User Story 4 - File + nvim support is removed (Priority: P2)

File paths can no longer be configured or passed; the tool never launches nvim. The file/nvim code paths, the `additional_files` config key, and the nvim dependency are gone. Directory-based flows are unchanged.

**Why this priority**: The user explicitly wants to move away from hardcoded nvim; removing it shrinks the tool and its dependency surface. It is P2 because the value only lands together with the tmuxp replacement (US1/US2).

**Independent Test**: Search the codebase and docs for file-path and nvim references; verify the config schema, CLI contract, dependency table, and tests no longer contain them, and that all directory behavior still passes.

**Acceptance Scenarios**:

1. **Given** a config that previously used `additional_files`, **When** the tool reads it, **Then** the key is rejected/ignored with a clear message, not silently loaded.
2. **Given** a `switch` invocation that previously accepted a file path, **When** a file path is passed, **Then** the tool reports a clear error and exits with the bad-path exit code.
3. **Given** the dependency documentation, **When** nvim is referenced, **Then** it is no longer listed as a required or optional dependency.

---

### User Story 5 - Config and CLI surface for inline workspaces (Priority: P2)

A clear, documented way to express inline workspaces both in the config file (as inline YAML strings) and on the CLI (a dedicated subcommand), with validation that catches mistakes before any session is created. The chosen surface is shaped so that supporting arrays of sessions later (one entry or one CLI parameter = several sessions) changes only the input shape, not the core behavior.

**Why this priority**: The representation and validation determine how approachable the feature is; they are P2 because US1–US3 could be demonstrated with a provisional surface first.

**Independent Test**: Write the config surface documentation; a new user can declare a workspace and open it without reading tmuxp's docs, and invalid YAML is caught with a helpful message before the interactive run.

**Acceptance Scenarios**:

1. **Given** a valid inline YAML workspace in the config, **When** the tool validates the config before an interactive run, **Then** the entry passes validation and appears in the picker.
2. **Given** a malformed or structurally invalid workspace, **When** validation runs, **Then** the tool reports the specific problem and skips/fails that entry with a clear message, without creating a session.
3. **Given** the domain's representation of a selection, **When** it is inspected, **Then** workspace entries are modeled as a collection of session specs, so a future array of sessions per entry does not change the core dedup/provisioning logic.

---

### Edge Cases

- What happens when tmuxp is not installed? The tool reports a clear error naming the missing tool and exits with a meaningful code.
- What happens when the inline workspace is empty or has no windows? The tool rejects it as invalid rather than creating an empty session.
- What happens when the workspace definition is edited between runs? The changed definition is treated as a new entry (new fingerprint) — an existing session for the old definition is not silently re-attached to.
- What happens when a workspace's `session_name` matches a plain directory session's name? The two are independent entry types and never switched into wrongly (the marker, not the name, drives the decision).
- What happens when two different workspaces declare the same `session_name`? Each still gets its own session; the second and later ones are created under a disambiguated name.
- What happens on a multi-select mixing directories and workspaces? Directories are processed first, then workspaces, one session each, with a single post-step (mirrors today's directories-before-files ordering).
- What happens when the picker is closed without selecting anything? Clean exit 0, no commands run (existing behavior preserved).
- What happens when a workspace's start directory does not exist? The workspace is still created by tmuxp with its default behavior; the tool does not block on it.
- What happens when tmuxp itself fails to load a valid-looking workspace? The error is surfaced with the exit-code contract preserved.
- What happens when the marker option is missing from a session that a later run must classify? The session is treated as foreign — never switched into as if it were ours.

## Requirements

### Functional Requirements

#### Removal of file + nvim support

- **FR-001**: The tool MUST no longer accept file paths in the config or on the CLI; the `additional_files` config key and all file handling MUST be removed.
- **FR-002**: The tool MUST no longer launch nvim or any editor for selected entries; the nvim dependency MUST be removed from the dependency documentation.
- **FR-003**: Existing directory flows MUST remain unchanged: session naming (dots → `_`), collision suffixes (`dup`, `dup-2`, …), reuse of a session that already belongs to the same directory, processing order, and post-step logic.

#### Inline tmuxp workspace support

- **FR-004**: The tool MUST support tmuxp workspace definitions supplied inline (not as config file paths), both in the interactive config and on the CLI.
- **FR-005**: The tool MUST support the YAML workspace format of tmuxp (chosen format; JSON documents that are also valid YAML are accepted, but JSON is not a formally supported surface).
- **FR-006**: When a workspace is provisioned, the resulting session MUST reproduce the workspace definition: window names, panes, layouts, start directories, and shell commands.
- **FR-007**: Interactive config entries: inline workspaces declared in the config MUST appear in the interactive picker alongside directories; the picker label is `[tmuxp] <session_name>`, or `[tmuxp] <tool-derived label>` when none is declared, rendered through the unified tagged-label interface (feature 005).
- **FR-008**: CLI: the user MUST be able to pass an inline workspace through a dedicated subcommand (proposed name `session`, e.g. `multi-sessionizer session '<yaml>'`), keeping `switch` reserved for directory paths.
- **FR-009**: Mixed selections (directories and workspaces together) MUST be supported with the same single-plan/single-post-step behavior as today's mixed directory/file selections.

#### Dedup and stateless session mapping

- **FR-010**: Each config entry MUST be deduplicated by the entry itself: opening the same entry twice MUST reuse one session; two different entries MUST NEVER map to the same session.
- **FR-011**: Recognition of the tool's own sessions MUST be based on a marker stored inside the tmux session (a session option), NOT on the session name; a session's name MUST never be the basis for a switch-vs-create decision.
- **FR-012**: For a given entry, the tool MUST decide between switching to an existing session and creating a new one, based on whether a session it provisioned from an identical entry already exists (matching marker).
- **FR-013**: A session whose marker is missing or does not match MUST be treated as foreign and never switched into as if it were the tool's own.
- **FR-014**: The mapping MUST be stateless: all switch-vs-create decisions MUST be derived from the live tmux state plus the config entry; the tool MUST NOT persist a registry, database, or sidecar file.
- **FR-015**: The tool MUST honor the workspace's own `session_name` when declaring one and MUST NOT require or impose a naming scheme; when a workspace declares none, the tool MUST assign a deterministic name.
- **FR-016**: The tool MUST honor the workspace's `start_directory` and MUST NOT override the working directory of provisioned workspace sessions.
- **FR-017**: When the desired session name is already taken (by a foreign session or by another provisioned session), the tool MUST create its session under a disambiguated name (numeric suffix, consistent with existing collision rules) without treating the existing session as its own.

#### Validation and errors

- **FR-018**: Before an interactive run, the tool MUST validate all configured workspaces and report problems (parse errors, structural errors) in the same spirit as today's directory/file existence check.
- **FR-019**: Invalid workspaces passed on the CLI MUST produce a clear error and the bad-path/config exit code, without creating a session.
- **FR-020**: When the required external capability (tmuxp) is unavailable, the tool MUST report a clear error naming the missing tool and exit with a meaningful code.
- **FR-021**: The exit-code contract MUST be preserved: 0 success, 1 bad path/config, 2 unknown command.

#### Array-readiness

- **FR-022**: The domain MUST model a selection as a collection of session specs (directories and workspaces), so that future support for one entry or one CLI parameter expanding into several sessions requires only surface/input changes and MUST NOT change the per-spec dedup and provisioning rules.

#### Performance

- **FR-023**: Workspace handling MUST only process declared entries; it MUST NOT scan, parse, or provision anything beyond the configured workspaces (bounded work, consistent with the existing bounded-discovery principle).

### Key Entities

- **Config Entry**: one selectable item in the picker — either a directory or an inline tmuxp workspace.
- **Session Spec**: the provisioning unit for a workspace — the tmuxp-format definition (windows, panes, layouts, start directory, shell commands) plus its identity. A selection is a collection of session specs (FR-022).
- **Session Marker**: the value stored inside the tmux session that lets the tool recognize a session it provisioned from a given entry; it is the source of truth for switch-vs-create (FR-011), never the session name.
- **Session**: an existing tmux session; the tool classifies sessions as directory sessions, workspace sessions it provisioned (matching marker), and foreign sessions (missing/mismatched marker).

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of existing directory-related tests pass unchanged after the change (behavior-parity gate for the non-removed flows).
- **SC-002**: Opening the same workspace entry twice produces exactly one session (dedup verified by `tmux list-sessions`).
- **SC-003**: A user can provision a workspace with multiple windows and panes in a single command and observe the full layout/commands (0 failed pane/window creations in a representative workspace).
- **SC-004**: A session named identically to a candidate is never switched into unless its marker matches the entry (verified by creating a deliberately misnamed foreign session with no marker).
- **SC-005**: Two workspaces that declare the same `session_name` still produce two distinct sessions, each later recognized by its own marker.
- **SC-006**: Deleting any tool-created state directory and restarting the tmux server does not change switch-vs-create behavior (statelessness verified).
- **SC-007**: The file/nvim feature is fully absent: no `additional_files`, no file arguments, no nvim reference anywhere in code, tests, docs, or dependency table.
- **SC-008**: A malformed workspace is caught by validation before an interactive run (0 sessions created for an invalid entry) and produces a clear, specific error on the CLI.

## Assumptions

- **Execution model**: the tool provisions sessions by delegating to the tmuxp tool as an external capability (an infrastructure adapter), consistent with how tmux/fzf/zoxide are already handled; tmuxp becomes a documented dependency.
- **Hybrid provisioning**: directory sessions are provisioned natively via tmux (fast, no new dependency on the critical path, behavior parity preserved); only tmuxp workspaces go through tmuxp. The orchestration flow — one session-spec model, one switch-vs-create decision, one post-step — is shared by both.
- **Identity**: an entry's identity is the fingerprint of its workspace definition, stored as the session marker; editing the definition makes it a new entry — the tool never silently re-attaches an edited definition to the old session.
- **Lifecycle ownership**: the tool is stateless and never destroys sessions; consuming tools (e.g., the planned multi-repo review-queue wrapper) own session lifecycle and kill stale sessions when done.
- **Inline-only**: no tmuxp config file paths are supported in v1, per the user's explicit scope decision.
- **Config representation**: workspaces are declared in `config.toml` as inline YAML strings under a new list key (e.g., `tmuxp_workspaces`), alongside the existing directory keys; each string is one picker entry.
- **CLI contract**: a dedicated subcommand (proposed `session`) passes one inline workspace; `switch` continues to accept directory paths only. The exact subcommand name is a planning detail.
- **Naming**: the tool does not impose a naming scheme — it honors `session_name` when declared and only assigns a deterministic fallback name when absent or when a collision requires disambiguation. The working directory of workspace sessions is governed by the workspace's `start_directory`.
- **Future array support**: the domain already models selections as a collection of session specs; supporting several sessions per entry/CLI parameter later is a surface-only change (FR-022) and is out of scope for v1.
- **Path validation**: the tool validates the workspace structure but does not pre-validate paths inside the definition (e.g., `start_directory`); tmuxp's own behavior governs them.
- **Directory flows**: directory sessions, `project_roots_depth_1/2`, `additional_dirs`, zoxide ranking, and all connection/attach logic remain exactly as they are today.
- **Statelessness**: "stateless" means no state outside of tmux; a marker stored as a tmux session option is considered part of the live tmux state, not external state.