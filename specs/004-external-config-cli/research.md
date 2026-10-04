# Research: External Config CLI

**Phase 0 output** — decisions that resolve every unknown in the Technical
Context and every dependency/integration for feature 004. Findings are
consolidated as **Decision / Rationale / Alternatives**.

## 1. What is the backing store and how is concurrency achieved?

**Decision**: A **sqlite3 database** (Python stdlib `sqlite3`), one table, with
**WAL mode** and one **transaction per operation**. Add/delete are wrapped in
atomic transactions; list reads a single consistent snapshot. Each CLI
invocation opens its own short-lived connection (`check_same_thread=True` is
irrelevant for single-threaded processes; sqlite's file locking serializes
concurrent processes).

**Rationale**: FR-003 demands concurrent-safe add/delete/list without torn or
partially-applied results. sqlite gives transactional ACID semantics with zero
new dependency (stdlib), which also satisfies constitution V ("no new runtime
dependencies without justification"). It survives restarts and is shared across
invocations (FR-002). Unique constraints implement FR-005 dedup at the storage
level.

**Alternatives considered**:
- A JSON file with an `fcntl`/`O_EXCL` lock — rejected: lock correctness across
  processes is easy to get wrong and non-portable; sqlite is battle-tested and
  free.
- An in-process lock only — rejected: concurrent **processes** (SC-005 stress
  run) would not share an in-process lock; sqlite's file-level locking is the
  correct serialization point.

## 2. Where does the store live?

**Decision**: `~/.local/state/multi-sessionizer/external.db` (XDG state
directory), overridable via a `MULTI_SESSIONIZER_STORE` environment variable.
The parent directory is created if missing.

**Rationale**: Runtime state (entries the user added that are not in their
config) belongs under `state`, not `config`. Keeping it out of the config file
directory reinforces FR-001 (config file is never written). The env override
matches the existing `MULTI_SESSIONIZER_CONFIG` override pattern and makes tests
isolated.

**Alternatives considered**:
- Co-locating next to `config.toml` — rejected: conflates config with runtime
  state; the spec says "tool's state/config directory", and XDG state is the
  semantically correct home.
- A user-chosen path via CLI flag — rejected: YAGNI; the env override already
  covers the scripting/test use case.

## 3. What is the CLI surface?

**Decision**: A grouped top-level `external` subcommand with three verbs:

```
multi-sessionizer external add <entry>
multi-sessionizer external list
multi-sessionizer external delete <key>
```

**Rationale**: FR-006 requires add/list/delete reachable without opening the
picker. A grouped `external` namespace keeps the three generic verbs (`add`,
`list`, `delete`) from colliding with future top-level verbs and reads clearly.
It matches the existing top-level-verb style while scoping to external entries.

**Alternatives considered**:
- Three bare top-level verbs `add`/`list`/`delete` — rejected: too generic at
  the root namespace; `external add` is self-documenting.
- A single `config` verb with `--add/--list/--delete` flags — rejected: departs
  from the existing `switch`/`session` positional-subcommand idiom.

## 4. How is an `add` argument classified and validated?

**Decision**: Reuse the existing **pure** `domain/session_entries.classify_sessions`
semantics via a thin pure wrapper `domain/external.classify_external_input(arg)`.
The argument is `yaml.safe_load`ed once; if it decodes to a **mapping** it is
classified as a config-style item (workspace via a non-empty `windows` list, or
a group via a string `name` + non-empty `sessions`); if it decodes to a scalar
string (a plain path) or fails to parse, it is classified as a **directory**
string. Validation is identical to config (FR-007): invalid input yields a
specific message and is not stored (FR-015).

**Rationale**: A CLI `add` argument is a string; config items are already-decoded
TOML values, so the only gap is decoding a group/workspace given as inline YAML
into a mapping before the shared classifier runs. Reusing `classify_sessions`
means the add command accepts exactly the config `sessions` forms and validates
them the same way (FR-007), with no second schema.

**Alternatives considered**:
- A separate type flag (`--type dir|workspace|group`) — rejected: adds a second
  schema and a new concept; shape-based classification is already deterministic.
- Authoring groups only through the config file — rejected: FR-007 explicitly
  requires the named-group form on the add command.

## 5. What is the dedup rule for a duplicate add?

**Decision**: A duplicate add is **rejected with a clear message and a non-zero
exit code**; nothing is stored. Duplicate means: an existing entry with the same
directory path (realpath-normalized), the same workspace definition (verbatim),
or the same group name. Enforced by sqlite `UNIQUE` constraints.

**Rationale**: FR-005 permits reject-with-message or idempotent no-op; rejection
is more explicit and lets the user learn the exact key to delete. The uniqueness
key is per-type and matches the deletion key, keeping the model coherent.

**Alternatives considered**: Idempotent silent no-op success — rejected: hides
the existing entry and is less informative than a clear "already exists" message.

## 6. How is deletion keyed and how is ambiguity handled?

**Decision**: Deletion is by **deletion key**: the realpath-normalized path for a
directory, the workspace **session name** (`domain/workspace.desired_name`), or
the group name. Pure `domain/external.resolve_delete(entries, key)` finds all
entries whose deletion key equals the requested key: exactly one → delete it;
more than one → report the matches and delete none (precise-match only); zero →
"not found" error (FR-010). The store uses the row's unique stored identity for
the actual delete.

**Rationale**: FR-009 fixes the key per type and FR-008 requires listing it; the
edge case ("deleting by a key that matches no / matches multiple entries") is
resolved by the precise-match rule. `desired_name` already computes the session
name for workspaces, so no new naming logic.

**Alternatives considered**: Deleting by an internal numeric row id — rejected:
the spec fixes user-facing keys (path / session name / group name); an opaque id
would be un-discoverable and contradicts FR-008.

## 7. How do external entries integrate into the interactive picker?

**Decision**: In `interactive_flow`, after building the config candidates, load
the external entries and append one candidate per entry with a **`[external]`
prefix**:
- directory → `[external] <path>`;
- workspace → `[external] <desired_name>`;
- group → `[external] <name>`.

Each maps to its `SessionEntry` in the label→entry route; on selection the entry
is routed exactly like a config entry (directory→classify_selection,
workspace→definition, group→expand members), so provisioning, marker-based
switch-vs-create, per-entry dedup, and single-plan/single-post-step are all
shared (FR-013).

**Rationale**: FR-012 requires a label distinct from `[tmuxp]` and `[group]`;
`[external]` satisfies that while still routing to the same `SessionEntry`-typed
provisioning path. Because external entries are the same DTO as config entries,
US4 (mixed multi-select, per-entry dedup) holds with zero runtime changes.

**Alternatives considered**: Rendering external workspaces as
`[external] [tmuxp] <label>` — rejected: redundant nesting; a single `[external]`
prefix with the entry's natural label is clear and distinct.

## 8. What happens in an interactive run when the store is corrupt/unreadable?

**Decision**: The external load is wrapped so a store failure produces a clear
error on stderr and the run **continues with config entries only** (external
entries omitted), exit code reflecting the run. The config file path is
untouched.

**Rationale**: FR-016 requires a clear error, no crash, and that config entries
still work. Degrading gracefully (skip external, still serve config) is the
least-surprise behavior for an interactive run; the store error is surfaced so
the user can repair it.

**Alternatives considered**: Aborting the whole interactive run on a corrupt
store — rejected: would prevent config entries from working, violating FR-016.

## 9. Interaction with features 002/003 (dependencies satisfied)

**Decision**: Features 002 (workspace support) and 003 (named groups / unified
`sessions`) are already implemented on `main` (`1dbd5ae`, `2eadf96`). External
entries are stored as `SessionEntry` values and flow through the unchanged
`plan`/`run`; group expansion and marker-based switch-vs-create are reused
verbatim. The `sessions` classifier (`domain/session_entries.py`) is the shared
entry classifier.

**Rationale**: The spec lists 002/003 as dependencies; both are present. Storing
`SessionEntry` directly is the entire basis for SC-001/SC-006 parity.

**Alternatives considered**: A separate external entry schema parallel to
`SessionEntry` — rejected: doubles the model for no benefit; reuse the unified
DTO.

## 10. Dependency justification (constitution V)

**Decision**: No new runtime dependency. `sqlite3` is Python stdlib and the
concurrency/ACID mechanism (FR-003). PyYAML remains the only third-party runtime
dependency (already documented for workspace parsing). No new entry is required
in the README dependency table; the sqlite3 choice is documented here and in
`data-model.md`.

**Rationale**: Constitution V demands every dependency have a documented purpose;
sqlite3's purpose is transactional concurrency. Using stdlib avoids a new
dependency line entirely.

**Alternatives considered**: `sqlite3` via a wrapper library (e.g., SQLAlchemy)
— rejected: a heavy dependency for one table and three operations; YAGNI.