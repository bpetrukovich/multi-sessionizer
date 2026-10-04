# App Ports (adapter contracts)

Contracts owned by the **app** layer. Infrastructure provides concrete
implementations; tests provide fakes. Replacing an adapter requires no domain
change and no more than the corresponding wiring line.

## `ExternalStore` → external entries (new)

```python
class ExternalStore(Protocol):
    def add(self, entry: SessionEntry) -> ExternalAddResult: ...
    def delete(self, key: str) -> ExternalDeleteResult: ...
    def list_entries(self) -> tuple[SessionEntry, ...]: ...
```

Result types:

```python
@dataclass(frozen=True)
class ExternalAddResult:
    ok: bool
    entry: SessionEntry | None = None
    error: str = ""

@dataclass(frozen=True)
class ExternalDeleteResult:
    ok: bool
    message: str = ""
```

- `add(entry)`: persists a validated `SessionEntry`. Returns `ok=True` + the
  stored entry, or `ok=False` + an error for a duplicate (UNIQUE violation,
  FR-005). The store never reads or writes the config file (FR-001).
- `delete(key)`: resolves `key` against current entries (via pure
  `domain/external.resolve_delete`) and removes the single matching row by its
  unique `id`. Returns a message for success / not-found / ambiguous (FR-009/
  FR-010). Deleting only removes the row — never a live tmux session (FR-014).
- `list_entries()`: a consistent snapshot of all stored `SessionEntry` values in
  stable order (empty tuple when the store is empty).

The config `ConfigLoader`, `CandidateDiscovery`, `ZoxideScorer`, `Picker`,
`SelectionClassifier`, `EnvironmentProbe`, `CommandExecutor`, and `MessageOutput`
ports are **unchanged**.

## `MessageOutput` → external text (extended)

```python
class MessageOutput(Protocol):
    # existing (unchanged)
    def config_not_found(self, path: object) -> None: ...
    def missing_dirs(self, missing_dirs: list[str]) -> None: ...
    def workspace_problems(self, problems: list[str]) -> None: ...
    def error(self, msg: str) -> None: ...
    # new
    def external_added(self, label: str) -> None: ...
    def external_list(self, rows: list[tuple[str, str, str]]) -> None: ...
    def external_deleted(self, message: str) -> None: ...
    def external_empty(self) -> None: ...
```

`external_list` receives one tuple per entry: `(kind, label, deletion_key)` and
formats it to stdout. All external messages are also reachable through `error`
where an exit-1 outcome is intended.

## `FlowDeps` — wiring bundle

```python
@dataclass(frozen=True)
class FlowDeps:
    config_loader: ConfigLoader
    discovery: CandidateDiscovery
    scorer: ZoxideScorer
    picker: Picker
    classifier: SelectionClassifier
    probe: EnvironmentProbe
    executor: CommandExecutor
    messages: MessageOutput
    external_store: ExternalStore      # NEW
```

## Concrete implementations (infrastructure)

| Port | Implementation |
|------|----------------|
| `ConfigLoader` | `infrastructure/config_loader.py` (unchanged) |
| `CandidateDiscovery` | `infrastructure/discovery.py` (unchanged) |
| `SelectionClassifier` | `infrastructure/classifier.py` (unchanged) |
| `EnvironmentProbe`, `ZoxideScorer`, `Picker`, `CommandExecutor` | `infrastructure/runner.py` (unchanged) |
| `MessageOutput` | `infrastructure/messages.py` (+ external text) |
| `ExternalStore` | `infrastructure/external_store.py` (**new** sqlite adapter) |

## Related

- Pure domain rules: [`domain-contracts.md`](./domain-contracts.md)
- Store schema & concurrency: [`store-contract.md`](./store-contract.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)