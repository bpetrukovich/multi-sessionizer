# Data Model: External Config CLI

**Phase 1 output** — the entities, DTOs, layer rules, and boundary contracts this
feature introduces. See [`contracts/`](./contracts/) for interface contracts and
[`research.md`](./research.md) for the decisions behind this model.

## 1. Entities

### 1.1 `SessionEntry` — *domain DTO (reused, feature 003)*

External entries are stored and routed as **`SessionEntry`** values (the unified
`sessions` entry: `kind` `"directory" | "workspace" | "group"` with `path` /
`definition` / `name` + `members`). No new entry DTO is introduced; this reuse is
the basis for FR-013 parity and SC-001.

### 1.2 `ExternalEntry` — *store row (infrastructure)*

The persisted form in `external_entries`. Fields map 1:1 to `SessionEntry` plus a
unique row identity:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PRIMARY KEY` | unique stored identity used for the actual delete (precise-match) |
| `kind` | `TEXT` | `"directory" \| "workspace" \| "group"`, `CHECK (kind IN (...))` |
| `path` | `TEXT` | directory path, realpath-normalized (kind == `directory`); `UNIQUE` when non-null |
| `definition` | `TEXT` | authored workspace YAML, verbatim (kind == `workspace`); `UNIQUE` when non-null |
| `name` | `TEXT` | group name (kind == `group`); `UNIQUE` when non-null |

Dedup constraints (FR-005), one per type:
- `UNIQUE(path)` for directory entries;
- `UNIQUE(definition)` for workspace entries;
- `UNIQUE(name)` for group entries.

A nullable-unique pattern gives per-type uniqueness without a composite key.

### 1.3 `Deletion Key` — *computed identity (domain)*

The user-facing key used to delete and listed per entry (FR-008/FR-009):

| kind | deletion key |
|------|--------------|
| `directory` | realpath-normalized `path` |
| `workspace` | `desired_name(definition)` (declared `session_name` or fingerprint fallback) |
| `group` | `name` |

Computed by pure `domain/external.deletion_key(entry)`; for a workspace it
delegates to `domain/workspace.desired_name`.

### 1.4 `ExternalAddResult` / `ExternalDeleteResult` — *store result types (app)*

Small result objects the `ExternalStore` port returns instead of raising for the
expected non-success cases:

```python
@dataclass(frozen=True)
class ExternalAddResult:
    ok: bool
    entry: SessionEntry | None = None   # stored entry on success
    error: str = ""                     # duplicate / invalid message on failure

@dataclass(frozen=True)
class ExternalDeleteResult:
    ok: bool
    message: str = ""                   # success / not-found / ambiguous text
```

### 1.5 `Config`, `Selection`, `SessionSpec`, `RuntimeSnapshot`, `Command`, `CommandPlan` — *unchanged*

The config file and the session runtime are untouched. External entries are
expanded into the same flat `Selection(dirs, workspaces)` before `plan`, so all
runtime DTOs and marker-based rules are unchanged (SC-001).

## 2. Layer rules (unchanged)

```
domain   → (nothing)            # stdlib + PyYAML (pure); no subprocess, filesystem,
                                #   environment, app/infra imports, os.path.realpath
app      → domain               # plus its own DTOs/ports
infrastructure → domain, app    # satisfies app's contracts and domain's DTOs
```

Module map:

- `domain/external.py` (**new**, pure): `classify_external_input(arg)` (reuses
  `session_entries.classify_sessions`), `deletion_key(entry)`,
  `resolve_delete(entries, key)`.
- `domain/session_entries.py`, `domain/workspace.py`, `domain/plan.py`,
  `domain/run.py`: **unchanged**.
- `app/ports.py`: adds the `ExternalStore` protocol + result types.
- `app/flows.py`: `interactive_flow` merges `[external]` entries into the picker;
  adds `add_external_flow`, `list_external_flow`, `delete_external_flow`.
- `infrastructure/external_store.py` (**new**): sqlite adapter (schema, WAL,
  per-operation transactions, `UNIQUE` dedup).
- `infrastructure/messages.py`: adds external add/list/delete message methods.
- `main.py`: dispatches the `external` subcommand.

Static verification (`tests/test_layer_boundaries.py`) must still pass;
`domain/external.py` must satisfy the same forbidden-pattern rules (PyYAML +
stdlib only).

## 3. Path normalization contract

Directory **external entries** are realpath-normalized and env/`~`-expanded at
the infrastructure boundary (the `add` flow / store adapter), so the domain and
the `UNIQUE(path)` dedup compare canonical paths. Workspace **definitions** are
stored verbatim (they are the identity and the fingerprint input). Group member
directories follow the same normalization as config (feature 003).

## 4. Add flow (FR-007/FR-015/FR-005)

```
external add <arg>
  │  domain/external.classify_external_input(arg)   (pure, PyYAML)
  ▼
SessionEntry | specific problems
  │  invalid → MessageOutput.error, exit 1          (FR-015, nothing stored)
  │  valid → realpath/expand directory paths         [store adapter, infra]
  ▼
store.add(entry)
  │  UNIQUE violation → "already exists" error, exit 1   (FR-005)
  ▼
inserted; success message, exit 0
```

Classification rule (`classify_external_input`): `yaml.safe_load(arg)`:
- decodes to a mapping with a non-empty `windows` list → **workspace**;
- decodes to a mapping with a string `name` + non-empty `sessions` → **group**
  (members validated like config — no nesting, FR-007);
- decodes to any other mapping → invalid (specific message);
- decodes to a scalar string or fails to parse → **directory** (path).

## 5. List flow (FR-008, US2)

```
external list
  │  store.list_entries()  (transactional snapshot)
  ▼
empty  → "no external entries" + exit 0   (clean success, US2 ac2)
else   → one line per entry: type + [external] label + deletion key, exit 0
```

Each row prints: `kind`, the picker label (same as the picker shows:
`[external] <path|name|desired_name>`), and the deletion key (path / session
name / group name).

## 6. Delete flow (FR-009/FR-010/FR-014)

```
external delete <key>
  │  store.list_entries() → entries
  │  domain/external.resolve_delete(entries, key)
  ▼
0 matches    → "not found" error, exit 1, store unchanged      (FR-010)
1 match      → store.delete(by unique id); success, exit 0     (FR-009)
>1 matches   → list the matches, delete none, error, exit 1    (edge case: precise match)
```

Deletion removes only the store row (FR-014) — it never runs or kills tmux, never
reads or writes the config file (FR-001/FR-009).

## 7. Interactive picker integration (FR-004/FR-012/FR-013)

```
interactive candidates =
    ranked dirs (root scans + config dir entries)
  + [tmuxp] <label> workspace lines (config)
  + [group] <name> group lines (config)
  + [external] <path|desired_name|name> external lines   (NEW)
  │ pick (multi-select across all kinds)
  ▼
route each selected line → SessionEntry (external lines route to their stored entry)
  - directory  → classify_selection (realpath) → dir
  - workspace  → definition
  - group      → expand members
  ▼
one flat Selection(dirs, workspaces) → run_selection → plan/run (unchanged)
```

On a corrupt/unreadable store, `interactive_flow` reports the error to stderr and
continues with config entries only (FR-016); the config file path is untouched.

## 8. State transitions

The store has no internal state machine; the only transitions are the row-level
add / delete and the read-only list. Live tmux session lifecycle is not part of
this model (the tool never creates or kills sessions here; deletion is a store
write only, per constitution Additional Constraints).

## 9. Capabilities & ports (who calls whom)

| Capability | Layer | Signature |
|------------|-------|-----------|
| `classify_external_input` | domain | `(arg: str) -> tuple[SessionEntry | None, list[str]]` (pure) |
| `deletion_key` | domain | `(entry: SessionEntry) -> str` (pure; delegates to `workspace.desired_name`) |
| `resolve_delete` | domain | `(entries: Sequence[SessionEntry], key: str) -> tuple[list[SessionEntry], list[str]]` (matches, problems) (pure) |
| `add_external_flow` | app | classify → store.add → message; returns exit code |
| `list_external_flow` | app | store.list_entries → message; returns exit code |
| `delete_external_flow` | app | store.list_entries → resolve_delete → store.delete → message |
| `interactive_flow` | app | load external entries (warn on failure) → merge `[external]` candidates → route → run |
| `ExternalStore` impl | infra | `add`, `delete`, `list_entries` (sqlite, WAL, transactions) |
| `MessageOutput` impl | infra | `external_added`, `external_list`, `external_deleted`, `external_error`, `external_empty` |

## 10. Entity → module map

| Entity / rule | Module |
|---------------|--------|
| `SessionEntry` (stored shape) | `domain/models.py` |
| external classify / deletion-key / resolve-delete | `domain/external.py` |
| workspace `desired_name` (workspace deletion key) | `domain/workspace.py` (unchanged) |
| `ExternalAddResult` / `ExternalDeleteResult`, `ExternalStore` | `app/ports.py` |
| external flows + picker merge | `app/flows.py` |
| sqlite store (schema, WAL, transactions) | `infrastructure/external_store.py` |
| user-facing external text | `infrastructure/messages.py` |
| `external` subcommand dispatch | `main.py` |