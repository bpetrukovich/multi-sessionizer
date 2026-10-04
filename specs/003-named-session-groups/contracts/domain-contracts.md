# Domain Contracts

Internal contracts owned by the **domain** layer. Infrastructure satisfies these;
app consumes them. Domain code is pure: no subprocess, no filesystem, no
environment reads, no `os.path.realpath`, no app/infrastructure imports. Feature 003
**adds** a classification capability and **leaves the runtime contracts
unchanged** — the entire basis for behavior parity (SC-001).

## DTOs (`domain/models.py`)

Existing DTOs unchanged (`Selection`, `SessionSpec`, `RuntimeSnapshot`, `Command`,
`CommandPlan` — see feature 002). Added:

```python
@dataclass(frozen=True)
class SessionEntry:
    kind: str  # "directory" | "workspace" | "group"
    path: str = ""  # directory (kind == "directory")
    definition: str = ""  # authored YAML (kind == "workspace")
    name: str = ""  # group label (kind == "group")
    members: tuple[SessionEntry, ...] = ()  # group members (dir/workspace only)
```

## Unified-session classification (`domain/session_entries.py`, pure)

| Function | Signature | Notes |
|----------|-----------|-------|
| `is_workspace_definition` | `(value: str) -> bool` | `yaml.safe_load` → mapping with a non-empty `windows` list |
| `classify_sessions` | `(raw: Iterable[object]) -> tuple[list[SessionEntry], list[str]]` | classify + structurally validate; returns entries and collected problems |

`classify_sessions` rules (FR-003/FR-007/FR-008/FR-011):
- string + workspace-shaped → `SessionEntry(kind="workspace", definition=…)`;
- string, not workspace-shaped → `SessionEntry(kind="directory", path=…)`;
- table with string `name` + non-empty `sessions` array → `SessionEntry(kind="group", …)`
  with members classified the same way;
- nested group member → problem (nesting rejected);
- group without `name` / empty `sessions` → problem;
- any other element / malformed member → problem.

No filesystem access here: directory entries are realpath'd by the caller.

## Runtime (`domain/plan.py`, `domain/run.py`, `domain/workspace.py`) — unchanged

`plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan` and
`run(selection, snapshot, executor)` are byte-identical to feature 002. A selected
group is expanded into a flat `Selection(dirs, workspaces)` **before** `plan`, so:

- directory specs reuse by path match (unchanged);
- workspace specs reuse by marker match only, never name (unchanged);
- per-entry dedup and the single-plan/single-post-step multi flow hold for group
  members exactly as for top-level entries (FR-005/FR-009/FR-013);
- a group is never a merged session (FR-006).

`plan_legacy` wrapper and the workspace pure functions are unchanged (SC-001).

## Purity / testability guarantees

- `classify_sessions`, `is_workspace_definition`, `plan`, `run`, and the workspace
  functions are exercised with hand-built values on a machine with no tmux, tmuxp,
  fzf, or zoxide, no `TMUX` env var, and no real execution.
- No subprocess, filesystem, environment, or terminal access anywhere in `domain/`
  (PyYAML parsing and `hashlib` are pure). `tests/test_layer_boundaries.py` stays
  green; `session_entries.py` obeys the same forbidden patterns.

## Related

- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Config surface: [`config-contract.md`](./config-contract.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)