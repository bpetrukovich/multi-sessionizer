# Domain Contracts (pure external rules)

Contracts owned by the **domain** layer. These functions are pure (stdlib +
PyYAML only), deterministic, and unit-tested before integration. No
subprocess/filesystem/environment access, no `os.path.realpath` — so
`tests/test_layer_boundaries.py` stays green.

## `classify_external_input(arg) -> tuple[SessionEntry | None, list[str]]`

Classify a single CLI `add` argument into a `SessionEntry` or specific problems.

```python
def classify_external_input(arg: str) -> tuple[SessionEntry | None, list[str]]:
    ...
```

Reuses `domain/session_entries.classify_sessions`. The argument is
`yaml.safe_load`ed once:
- decodes to a mapping with a non-empty `windows` list → **workspace**;
- decodes to a mapping with a string `name` + non-empty `sessions` → **group**
  (members validated like config — no nesting);
- decodes to any other mapping → invalid (specific message);
- decodes to a scalar string or fails to parse → **directory** (path).

An invalid value returns `(None, problems)` and must not be stored (FR-015).
Valid values are the same forms as the config `sessions` array (FR-007).

## `deletion_key(entry) -> str`

The user-facing key used to delete and listed per entry (FR-008/FR-009).

```python
def deletion_key(entry: SessionEntry) -> str:
    ...
```

| kind | result |
|------|--------|
| `directory` | `entry.path` (already realpath-normalized at the boundary) |
| `workspace` | `domain/workspace.desired_name(entry.definition)` |
| `group` | `entry.name` |

## `resolve_delete(entries, key) -> tuple[list[SessionEntry], list[str]]`

Resolve a deletion request against the current external entries (FR-009/FR-010).

```python
def resolve_delete(
    entries: Sequence[SessionEntry], key: str
) -> tuple[list[SessionEntry], list[str]]:
    ...
```

Returns `(matches, problems)`:
- **0 matches** → `([], ["No external entry with deletion key '<key>'."])` — not
  found (FR-010), caller does not delete.
- **1 match** → `([entry], [])` — caller deletes that unique entry.
- **>1 matches** → `([m1, m2, ...], [ambiguous message])` — the matches are
  reported and **none** is removed (precise-match rule; e.g. two workspaces with
  the same session name).

The actual row delete is by the store's unique `id`, recovered from the matched
entry's identity, so the precise-match guarantee is enforced end-to-end.

## Layer constraints

- Lives in `domain/external.py`; imports only stdlib, `yaml`, `domain.models`,
  `domain.session_entries`, `domain.workspace`.
- Must not import `app` or `infrastructure` (boundary test).
- No `subprocess`, `os.environ`, `os.path.realpath` (boundary test).

## Related

- App ports & flows: [`app-ports.md`](./app-ports.md)
- Store schema: [`store-contract.md`](./store-contract.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)