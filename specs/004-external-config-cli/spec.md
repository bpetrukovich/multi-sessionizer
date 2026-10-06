# Feature Specification: External Config CLI

**Feature Branch**: `004-external-config-cli`

**Created**: 2026-10-05

**Status**: Draft

**Input**: User description: "Add a CLI API for permanently extending the interactive list. The CLI must accept a valid parameter (like from the configs array). It must also support deleting and listing the added configs. The user's own config file is never modified. Deletion is by session name (for tmuxp), by group name, or by path (for a directory) — the list shows the same. It is best if the operations are thread-safe, so sqlite may need to be used as the backing store. Think about it. For these, fzf should show a good name, like [external] or similar."

## User Scenarios & Testing

### User Story 1 - Add an external config entry permanently from the CLI (Priority: P1)

The user adds a directory, an inline tmuxp workspace, or a named group to the picker without editing their config file. The entry is stored in a persistent store and appears in every subsequent interactive run alongside the config-file entries, labeled clearly as externally added.

**Why this priority**: This is the core value — permanently extending the picker list without touching the user's config file, driven from the CLI so it can be scripted.

**Independent Test**: Add one directory, one workspace, and one group via the CLI, run the interactive picker, and verify all three appear (labeled as external) alongside the config-file entries, in a fresh run.

**Acceptance Scenarios**:

1. **Given** a directory path added via the CLI, **When** an interactive run lists entries, **Then** the directory appears as an external entry, and selecting it provisions/switches to its session exactly as a config-file directory entry would.
2. **Given** an inline tmuxp workspace added via the CLI, **When** an interactive run lists entries, **Then** the workspace appears as an external entry, and selecting it provisions/switches to its session as a config-file workspace would.
3. **Given** a named group added via the CLI, **When** an interactive run lists entries, **Then** the group appears as a single external entry and expands into its member sessions on selection, as a config-file group would.
4. **Given** the user's config file, **When** entries are added via the CLI, **Then** the config file's bytes are unchanged.

---

### User Story 2 - List external config entries (Priority: P1)

The user lists every externally added entry. The listing identifies each entry's type and the deletion key: the directory path for a directory, the session name for a workspace, the group name for a group.

**Why this priority**: Listing is the read surface that makes adding, dedup, and deletion transparent; it is the natural companion to US1 and is independently demonstrable.

**Independent Test**: Add a few entries of each type, run the list command, and verify each entry is shown with its type and its correct deletion key.

**Acceptance Scenarios**:

1. **Given** external entries of all three types, **When** the user lists them, **Then** each entry shows its type (directory / workspace / group), its label, and the key used to delete it (path, session name, group name respectively).
2. **Given** no external entries, **When** the user lists them, **Then** the command reports an empty list with a clean success exit.

---

### User Story 3 - Delete an external config entry (Priority: P1)

The user removes an externally added entry by its deletion key: path (directory), session name (workspace), or group name (group). Deletion affects only the external store — never the user's config file — and does not destroy any live tmux sessions.

**Why this priority**: Being able to remove what was added is required for the store to be usable over time; without it the feature would be write-only.

**Independent Test**: Add entries of each type, delete one by its key, list again, and verify it is gone while the config file is untouched and its session (if running) still exists.

**Acceptance Scenarios**:

1. **Given** a directory external entry, **When** the user deletes by its path, **Then** the entry no longer appears in the list or the picker, and the config file is unchanged.
2. **Given** a workspace external entry, **When** the user deletes by its session name, **Then** the entry is removed, and any running session it provisioned is left untouched.
3. **Given** a group external entry, **When** the user deletes by its group name, **Then** the group is removed, and no member session is destroyed.
4. **Given** a deletion key that matches no external entry, **When** the user deletes, **Then** the command reports a clear error and a non-zero exit code, and the store is unchanged.

---

### User Story 4 - External entries integrate with existing picker behavior (Priority: P2)

External entries are first-class members of the interactive picker: they are multi-selectable together with config entries, share the same switch-vs-create and dedup semantics, and are clearly labeled `[external]` so the user can distinguish them.

**Why this priority**: The entries must not be second-class; they must work identically in mixed selections. P2 because US1–US3 already deliver standalone value.

**Independent Test**: Mix config-file and external entries in one multi-select run and verify each gets its own session with the correct switch-vs-create behavior, and that the picker labels external entries distinctly.

**Acceptance Scenarios**:

1. **Given** a picker listing both config-file and external entries, **When** the user multi-selects across both, **Then** each selected entry is provisioned/switched exactly once, in a single plan and post-step.
2. **Given** an external entry and a config-file entry that resolve to the same session, **When** both are opened, **Then** dedup is per entry (each maps to its own session) consistent with existing rules.
3. **Given** the fzf picker, **When** external entries are present, **Then** each is shown with a clear `[external]` label prefix distinct from `[tmuxp]` and `[group]`, with any user tags as `[tag]` prefixes after it.

---

### Edge Cases

- What happens when the same directory is added externally twice? The second add is rejected or idempotently no-ops with a clear message, so there is exactly one external entry for it.
- What happens when an external workspace and a config-file workspace share a session name? They are independent entries; the marker-based switch-vs-create rules (feature 002) govern, never the name.
- What happens when deleting by a key that is ambiguous (e.g., two workspaces with the same session name)? Deletion is by the unique stored identity; the user is told which entries match and none is removed without a precise match.
- What happens when the persistent store is corrupt or unreadable? The tool reports a clear error, does not crash, and the config-file entries still work.
- What happens when an externally added directory no longer exists? It is still listed (matching today's validation behavior for config entries is a planning detail), but provisioning reports the missing path.
- What happens when the user edits their config to include an entry that also exists externally? Both are separate entries; dedup remains per entry.
- What happens on concurrent add/delete/list operations? Operations are serialized so the store never ends up in a partially-applied state and concurrent list never observes a torn view.
- What happens when the picker is closed without selecting anything? Clean exit 0, no commands run (existing behavior preserved).

## Requirements

### Functional Requirements

#### External store

- **FR-001**: The tool MUST persist externally added entries in a store that is separate from the user's config file; the user's config file MUST never be read for external entries and MUST never be written by any external-config operation.
- **FR-002**: The store MUST survive restarts and MUST be shared across invocations of the tool (one logical persistent store per user/tool).
- **FR-003**: The store MUST support concurrent-safe add, delete, and list operations without torn or partially-applied results.
- **FR-004**: Entries added via the CLI MUST appear in the interactive picker in every subsequent run, merged with config-file entries.
- **FR-005**: The same directory MUST NOT be represented by more than one external entry; a duplicate add MUST be rejected with a clear message or no-op idempotently.

#### CLI surface

- **FR-006**: The tool MUST expose CLI subcommands to add, list, and delete external entries; these MUST be reachable without opening the interactive picker.
- **FR-007**: The add command MUST accept the same valid entry forms as the config `sessions` array — a directory string, an inline tmuxp workspace string, and a named group — and MUST validate them the same way before storing.
- **FR-008**: The list command MUST show each external entry with its type, its picker label (including any `[tag...]` prefixes), and its deletion key.
- **FR-009**: Deletion MUST be keyed by: the path for a directory entry, the session name for a workspace entry, and the group name for a group entry; a delete MUST affect only external entries and MUST NOT modify the config file.
- **FR-010**: Deleting a key that matches no external entry MUST produce a clear error and a non-zero exit code, and MUST NOT change the store.
- **FR-011**: The exit-code contract MUST be preserved: 0 success, 1 bad path/config, 2 unknown command.

#### Picker integration

- **FR-012**: External entries MUST be labeled `[external] <key>` in the fzf picker (plus any user-supplied `[tag...]` prefixes), distinguishable from `[tmuxp]` and `[group]` labels, all rendered through the unified tagged-label interface (feature 005).
- **FR-013**: External entries MUST behave identically to their config-file counterparts for provisioning, switch-vs-create (marker-based), per-entry dedup, collision naming, processing order, and the single-plan/single-post-step flow.
- **FR-014**: Deletion of an external entry MUST NOT destroy any live tmux session it provisioned.

#### Validation and errors

- **FR-015**: An invalid entry passed to the add command (bad directory, malformed workspace, malformed group) MUST be rejected with a specific message and not stored.
- **FR-016**: A corrupt or unreadable external store MUST produce a clear error, MUST NOT crash the tool, and MUST NOT prevent config-file entries from working.

### Key Entities

- **External Entry**: a permanently added picker entry — a directory, an inline tmuxp workspace, or a named group — stored outside the user's config file.
- **Deletion Key**: the stable identifier used to delete and listed for an external entry — the path (directory), the session name (workspace), or the group name (group).
- **External Store**: the persistent, concurrent-safe collection of external entries that survives restarts and is merged into the picker on every run.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of existing directory, workspace, and group tests pass unchanged (behavior-parity gate for non-removed flows).
- **SC-002**: A user can add one directory, one workspace, and one group via the CLI and see all three as `[external]` entries in the very next interactive run (0 missing entries).
- **SC-003**: After an add, list, and delete cycle for each entry type, the list returns to its prior state and the user's config file is byte-for-byte unchanged (verified by checksum).
- **SC-004**: Deleting any external entry leaves any live session it provisioned running (verified by `tmux list-sessions`).
- **SC-005**: Running add/list/delete from multiple processes concurrently never yields a torn list, a duplicate directory entry, or a partially-applied delete (verified by a concurrent stress run).
- **SC-006**: External and config-file entries mix in a single multi-select and each selected entry is provisioned/switched exactly once.

## Assumptions

- **Store location**: the external store is a single persistent file owned by the tool (sqlite being the leading candidate per the thread-safety requirement), co-located under the tool's state/config directory; the exact path is a planning detail.
- **Thread safety**: concurrent operations are required and are best served by a store with transactional semantics; if sqlite is chosen it becomes a documented dependency.
- **Entry forms**: the add command mirrors the config `sessions` forms (directory, inline workspace, group), so users do not learn a second schema.
- **Deletion does not destroy sessions**: the tool is stateless about live tmux sessions (feature 002/003); deleting an external entry only removes the entry from the store, never a running session.
- **Labeling**: external entries are prefixed `[external]` in the picker (structural tag), with optional user-supplied `[tag]` prefixes after it; the exact label text is a planning detail, but it must be distinct from `[tmuxp]` and `[group]`.
- **Config immutability**: no external-config operation ever reads the user's config for storage decisions or writes it; the config file remains the user's own.
- **Interaction with features 002/003**: this feature reuses the unified `sessions` entry model, marker-based switch-vs-create, and group expansion from features 002 and 003; those are dependencies for the workspace and group cases.