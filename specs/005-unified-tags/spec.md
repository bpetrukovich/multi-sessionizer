# Feature Specification: Unified Picker Tags

**Feature Branch**: `005-unified-tags`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Add an API to `msz` so external entries can be added with tags, shown as `[tag]` in the picker. `[tmuxp]`, `[external]` and `[group]` are tags too — everything flows through one unified interface into the picker. A review queue could then render `[external] [pp-000000] <название>`."

## User Scenarios & Testing

### User Story 1 - Every picker line renders through one tagged-label interface (Priority: P1)

Every entry in the interactive picker is shown as `<tag>* <label>`: the structural tags `[tmuxp]` (config workspace), `[group]` (named group) and `[external]` (external entry) plus any user-supplied tags, all rendered by a single pure helper. No labeler hand-builds its own prefix string.

**Why this priority**: The structural tags already exist in three separate functions; unifying them is the enabling shape for user-supplied tags and removes the drift where one labeler changes and others do not.

**Independent Test**: Build config-file entries (directory, workspace, group) and external entries with and without user tags, run the interactive picker, and verify every line is `<tag>* <label>` with the structural tag first and user tags after it.

**Acceptance Scenarios**:

1. **Given** a config-file workspace, **When** the picker runs, **Then** its line is `[tmuxp] <desired_name>` rendered by the unified interface.
2. **Given** a config-file group with user tags, **When** the picker runs, **Then** its line is `[group] [tag...] <name>`.
3. **Given** an external entry with user tags, **When** the picker runs, **Then** its line is `[external] [tag...] <deletion_key>`.
4. **Given** an entry with no user tags, **When** the picker runs, **Then** its line is unchanged from today.

---

### User Story 2 - External entries accept display tags (Priority: P1)

The `external add` command accepts tags: a top-level `tags:` key on group and workspace YAML documents, and a `--tags TAG[,TAG...]` flag for directory entries. Tags are stored with the entry and shown as `[tag]` prefixes in the picker and in `external list`.

**Why this priority**: This is the concrete API a review-queue/automation consumes to brand entries (e.g. `[external] [pp-000000] <label>`).

**Independent Test**: Add one directory with `--tags`, one workspace with a `tags:` key, and one group with a `tags:` key via the CLI; verify the picker and `external list` show each with its `[tag]` prefixes, and that a duplicate add of each is still rejected.

**Acceptance Scenarios**:

1. **Given** `multi-sessionizer external add --tags pp-000000,backend /path`, **When** the entry is listed, **Then** the directory appears as `[external] [pp-000000] [backend] /path`.
2. **Given** a group YAML with `tags: [pp-000000]`, **When** the entry is added, **Then** the group appears as `[external] [pp-000000] <name>` and its members round-trip unchanged.
3. **Given** a workspace YAML with a top-level `tags:` key, **When** the entry is added, **Then** the tag is stored for display and the workspace definition stored/provisioned to tmuxp is the document without the `tags` key.
4. **Given** a YAML document that declares `tags:` while `--tags` is also passed, **When** the entry is added, **Then** the add is rejected with a clear "tags twice" message and nothing is stored.

---

### User Story 3 - Tags are display-only metadata (Priority: P2)

Tags never affect identity: the deletion key, deduplication, collision naming, and the tmux session name all ignore tags. Removing an entry still uses the same deletion key as before tags existed.

**Why this priority**: Keeping tags out of identity avoids changing any switch-vs-create, dedup, or deletion rule, which keeps the existing behavior-parity gate trivially satisfied.

**Independent Test**: Add a directory and a group both with and without tags, and verify `external delete` accepts the same keys as before, duplicate adds are rejected regardless of tags, and the provisioned tmux session name is unchanged.

**Acceptance Scenarios**:

1. **Given** a tagged directory entry, **When** the user deletes by its path, **Then** the entry is removed and the deletion key equals the untagged path.
2. **Given** two workspaces with the same `session_name` but different tags, **When** the user deletes by that name, **Then** the result is ambiguous exactly as without tags (nothing removed).
3. **Given** a tagged workspace, **When** it is provisioned, **Then** the tmux session name is `desired_name(definition)` and never contains the tags.

---

### Edge Cases

- What is a valid tag? A non-empty string without whitespace and without `[`/`]`; duplicates are removed and the first occurrence's order is kept.
- What happens when a `tags:` value is not a list of strings? The entry is rejected with a specific message (like a malformed group member).
- What happens when a workspace document has `tags:`? The tag is stripped from the stored definition so tmuxp never sees it; the fingerprint is over the stripped definition, consistently across adds.
- What happens to stores created before tags existed? The sqlite schema gains a `tags` column via a guarded, idempotent `ALTER TABLE`; existing rows read back with no tags.
- What happens when a legacy store is opened while another process also opens it? Schema DDL on connect is serialized so concurrent first-use does not race.
- What happens when the picker is closed without selecting anything? Clean exit 0, no commands run (existing behavior preserved).

## Requirements

### Functional Requirements

#### Unified label rendering

- **FR-001**: A single pure function MUST render every picker line as `<tag>* <label>`, taking an ordered tag sequence and a label; structural tags (`tmuxp`, `group`, `external`) and user tags MUST be passed through it.
- **FR-002**: The existing structural prefixes MUST NOT change: a config workspace is `[tmuxp] <desired_name>`, a config group `[group] <name>`, an external entry `[external] <deletion_key>`, and a directory path line stays bare.

#### External tags API

- **FR-003**: The `external add` command MUST accept tags via a top-level `tags:` list on group and workspace YAML documents and via a `--tags TAG[,TAG...]` flag for directory entries.
- **FR-004**: A tag MUST be a non-empty string without whitespace or brackets; duplicates MUST be collapsed preserving first-occurrence order; an invalid `tags:` value MUST reject the entry with a specific message.
- **FR-005**: Declaring `tags:` in a YAML document while also passing `--tags` MUST reject the add as ambiguous and store nothing.
- **FR-006**: For a workspace document, the `tags` key MUST be removed from the stored/provisioned definition (tmuxp must never receive it), while the tags themselves persist for display.
- **FR-007**: Tags MUST be persisted with the entry and MUST survive add/list round-trips for all three entry kinds, including group member round-trips.

#### Display-only semantics

- **FR-008**: Tags MUST NOT affect the deletion key, deduplication, collision naming, the marker-based switch-vs-create rules, or the tmux session name.
- **FR-009**: `external list` MUST show each entry's type, its tagged picker label, and its deletion key; the deletion key MUST be unchanged by the presence of tags.
- **FR-010**: A store created before this feature MUST keep working after the schema migration, reading its existing rows with no tags.

### Key Entities

- **Tag**: a short, non-empty, whitespace/bracket-free string used only for picker display, rendered as `[tag]`.
- **Structural Tag**: the origin tag a labeler attaches — `tmuxp`, `group`, or `external`.
- **Picker Line**: `<tag>* <label>` produced by the unified renderer; duplicate full lines are still disambiguated with the numeric-suffix rule.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of existing directory, workspace, group, and external tests pass unchanged (behavior-parity gate).
- **SC-002**: Adding a directory with `--tags`, a workspace with `tags:`, and a group with `tags:` yields exactly `[external] [tag...] <key>` lines in the next interactive run.
- **SC-003**: A workspace added with `tags:` provisions a session whose name is `desired_name(definition)` (never containing the tag) and whose marker fingerprint is stable across repeated adds.
- **SC-004**: Tagged entries delete by the same keys as untagged ones; ambiguous deletes behave identically.
- **SC-005**: A legacy sqlite store without a `tags` column opens, lists its rows with no tags, and accepts new tagged adds without error.

## Assumptions

- **Tags are free-form**: no fixed vocabulary or format (e.g. `pp-000000`, `backend`) — only the whitespace/bracket constraint; a constrained format can be layered later without schema changes.
- **Tags are display-only**: any future search/filter by tag is out of scope here and must not change identity semantics.
- **Config-file entries**: group tags are accepted in the config `sessions` array too (via the shared group classifier) and render through the same interface; no tag support is added for plain config directories or config workspaces.
- **No backward compatibility**: the `tags` API is new; no legacy tag surface exists to preserve, and removed behavior (if any surfaces in review) is dropped outright per the project rule.