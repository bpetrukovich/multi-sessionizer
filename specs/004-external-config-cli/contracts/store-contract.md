# Store Contract (sqlite external store)

**Infrastructure contract** — the persistent, concurrent-safe store that holds
externally added entries (FR-002/FR-003). Implemented in
`infrastructure/external_store.py` using stdlib `sqlite3` (research §1, §10).

## Location

- Path: `~/.local/state/multi-sessionizer/external.db` (XDG state), overridable
  via `MULTI_SESSIONIZER_STORE`.
- The parent directory is created if missing.
- The user's config file is never read for external decisions and never written
  (FR-001).

## Schema

```sql
CREATE TABLE IF NOT EXISTS external_entries (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL CHECK (kind IN ('directory', 'workspace', 'group')),
    path       TEXT,
    definition TEXT,
    name       TEXT,
    UNIQUE (path) UNIQUE (definition) UNIQUE (name)
);
```

- Per-type uniqueness via nullable `UNIQUE` columns gives FR-005 dedup:
  - a duplicate directory path → rejected;
  - a duplicate workspace definition (verbatim) → rejected;
  - a duplicate group name → rejected.
- `id` is the unique stored identity used for a precise-match delete (FR-009
  edge case).

## Concurrency (FR-003, SC-005)

- **WAL mode** enabled on each connection.
- Each CLI invocation opens a **short-lived connection**; add/delete run in a
  single `BEGIN`/`COMMIT` transaction (atomic, no partially-applied writes);
  list reads one consistent snapshot. `sqlite3`'s file-level locking serializes
  concurrent processes, so a concurrent stress run never observes a torn list, a
  duplicate directory, or a partially-applied delete.
- On a transaction failure the change is rolled back and the operation returns
  an error; the store is never left in a partially-applied state.

## Operations

| Operation | Behavior |
|-----------|----------|
| `add(entry)` | insert the row in a transaction; on `IntegrityError` → duplicate error, nothing stored (FR-005); success returns the stored entry |
| `delete(key)` | `list_entries()` → pure `domain/external.resolve_delete` → if exactly one match, `DELETE WHERE id = ?` in a transaction; returns success / not-found / ambiguous (FR-009/FR-010) |
| `list_entries()` | `SELECT ... ORDER BY id` → `tuple[SessionEntry, ...]` snapshot |

Deletion only removes a row — it never runs or kills tmux (FR-014).

## Corruption / unreadable store (FR-016)

- A corrupt or unreadable store raises a clear error, does **not** crash the
  tool, and does **not** prevent config-file entries from working:
  - `external list` / `external delete` → message + exit 1;
  - interactive run → message to stderr, run continues with config entries only.

## Testing

- Unit tests use an in-memory sqlite DB (`:memory:`) for store logic and an
  isolated `MULTI_SESSIONIZER_STORE` path for the wiring tests, so the
  developer's real store/state directory is never touched.
- Concurrent add/delete/list is covered by a stress test (SC-005).

## Related

- App port: [`app-ports.md`](./app-ports.md)
- Pure domain rules: [`domain-contracts.md`](./domain-contracts.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)