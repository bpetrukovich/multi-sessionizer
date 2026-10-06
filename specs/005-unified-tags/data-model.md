# Data Model: Unified Picker Tags

**Phase 1 output** — the entities, DTOs, and layer rules this feature introduces.
See [`spec.md`](./spec.md) for the user stories and requirements.

## 1. Entities

### 1.1 `SessionEntry.tags` — *domain DTO field (feature 004 reused)*

`SessionEntry` (the unified `sessions` entry) gains one field:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `tags` | `tuple[str, ...]` | `()` | user-supplied picker tags, display-only (FR-008) |

The field is a plain tuple of validated strings: non-empty, no whitespace, no
`[`/`]`, deduplicated with first-occurrence order (FR-004). All existing
constructors keep working because the default is empty.

### 1.2 `ExternalEntry` — *store row (infrastructure, feature 004 extended)*

The `external_entries` table gains one column:

| Column | Type | Notes |
|--------|------|-------|
| `tags` | `TEXT` | JSON array of strings; `NULL`/empty means no tags |

- Fresh installs create the column via the `CREATE TABLE IF NOT EXISTS` schema.
- Existing stores are migrated with a guarded, idempotent
  `ALTER TABLE external_entries ADD COLUMN tags TEXT` (FR-010). Schema DDL on
  connect is serialized by a process-wide lock so concurrent first-use never
  races into `database is locked`.
- The `tags` column is the single source of truth for all kinds. Group
  entries keep storing only `{name, sessions}` in their `definition` blob; the
  tags column is re-attached on reconstruction.

## 2. Domain functions

### 2.1 `domain/labels.render_picker_line(tags, label)` — *new, pure*

```python
def render_picker_line(tags: Sequence[str], label: str) -> str
```

Joins `[tag] ` prefixes with a label. Empty tags yield just the label. Every
picker labeler delegates to it (FR-001):

| Labeler | Structural tag | Label |
|---------|----------------|-------|
| `workspace_label(definition)` | `tmuxp` | `desired_name(definition)` |
| `_group_display(entry)` | `group` | `entry.name` |
| `external_label(entry)` | `external` | `deletion_key(entry)` |

User tags follow the structural tag in order: `[group] [pp-1] stack`,
`[external] [pp-000000] /path` (FR-002).

### 2.2 `domain/labels.parse_tags(value)` — *new, pure*

```python
def parse_tags(value: object) -> tuple[tuple[str, ...], str | None]
```

- `None` → `((), None)` (no tags).
- non-list or non-string element → problem `"The 'tags' key must be a list of
  strings."`.
- a tag that is empty, has whitespace, or contains `[`/`]` → problem
  `"Invalid tag '<tag>': ..."`.
- otherwise deduped tuple with first-occurrence order (FR-004).

### 2.3 Classification wiring

- `domain/session_entries._classify_item` (group branch) parses `tags` with
  `parse_tags`; an invalid value rejects the group with a specific message.
  This covers config-file groups and, via `classify_sessions`, external groups.
- `domain/external.classify_external_input(arg, tags=())`:
  - **workspace** (`windows` mapping): parses `tags` from the document, rejects
    when `--tags` is also non-empty (`"Tags are specified both in the entry and
    via '--tags'."`), and stores `definition` = the document minus the `tags`
    key (deterministic re-dump) so tmuxp never receives it (FR-006). A document
    without `tags` keeps its definition verbatim, so fingerprints are stable.
  - **group**: reuses `classify_sessions`; rejects a `--tags` conflict the same
    way; effective tags = document tags or the `--tags` values.
  - **directory** (scalar string): tags = the `--tags` values only.

### 2.4 Storage round-trip

- `infrastructure/external_store` serializes tags as a JSON array string on
  `add` and decodes them on `list_entries`; `_reconstruct_group(name, definition, tags)`
  re-attaches the column tags to the reconstructed group.
- `_normalize` (both the store and the config loader) preserves `tags` when it
  re-wraps directory/group entries.

## 3. Layer rules

- All tag logic lives in `domain/` and stays pure (no process spawning,
  filesystem, environment access, or realpath) so
  `tests/test_layer_boundaries.py` stays green.
- `app/flows` only renders and forwards: `external_label`, `_group_display`,
  and `add_external_flow(arg, deps, tags=())`.
- The CLI (`main._split_tags`) splits `--tags TAG[,TAG...]` flags from the
  positional entry and hands the tag list to the flow.