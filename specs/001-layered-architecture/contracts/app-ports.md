# App Ports (adapter contracts)

Contracts owned by the **app** layer (FR-003/FR-006/FR-011). Infrastructure provides
concrete implementations; tests provide fakes. The domain defines its own executor
contract (see [`domain-contracts.md`](./domain-contracts.md)). Replacing an adapter
requires no domain change and no more than the corresponding wiring line (US4, SC-005).

## `ConfigLoader` → `Configuration`

```python
class ConfigLoader(Protocol):
    def load(self) -> Config: ...
    def missing_files(self, cfg: Config) -> list[str]: ...
    def missing_dirs(self, cfg: Config) -> list[str]: ...
```

- `load()` reads the TOML file at `$MULTI_SESSIONIZER_CONFIG` or
  `~/.config/multi-sessionizer/config.toml`; raises `ConfigNotFoundError` if absent;
  expands env vars and `~` in every path; missing keys → empty tuple.
- `missing_files` / `missing_dirs` report configured paths that do not exist.

## `CandidateDiscovery` → candidate paths

```python
class CandidateDiscovery(Protocol):
    def collect_dirs(self, cfg: Config) -> list[str]: ...
    def collect_files(self, cfg: Config) -> list[str]: ...
```

Depth-1 roots → direct children; depth-2 roots → children + grandchildren; additional
dirs/files verbatim. Traversal pruned at the configured depth (never a full-tree walk).

## `ZoxideScorer` → raw score text

```python
class ZoxideScorer(Protocol):
    def scores(self) -> str: ...
```

Runs `zoxide query -l -s`; returns raw stdout (parsed by domain `rank`).

## `Picker` → selected lines

```python
class Picker(Protocol):
    def pick(self, items: list[str]) -> list[str]: ...
```

`fzf --tmux --multi --prompt "Project > "`. Empty selection on cancel/error.

## `SelectionClassifier` → domain `Selection`

```python
class SelectionClassifier(Protocol):
    def classify_args(self, argv: Sequence[str]) -> tuple[list[str], list[str]]: ...
    def classify_selection(self, lines: list[str]) -> Selection: ...
```

- `classify_args`: each arg is `realpath`'d; dir → dirs, file → files; otherwise raises
  `ValueError("Not a directory or file: <arg>")`. (Tuple form retained for the legacy
  facade; `switch_flow` wraps into `Selection`.)
- `classify_selection`: picker output → `Selection` (realpath each line; dir vs file).

## `EnvironmentProbe` → domain `RuntimeSnapshot`

```python
class EnvironmentProbe(Protocol):
    def snapshot(self) -> RuntimeSnapshot: ...
```

`in_tmux` from the `TMUX` env var; `tmux_server_running` via `pgrep tmux`;
`existing` from `tmux list-sessions -F "#{session_name}\t#{session_path}"` with values
realpath-normalized. The domain consumes exactly this snapshot and reads nothing itself.

## `MessageOutput` → user-facing text

```python
class MessageOutput(Protocol):
    def config_not_found(self, path: object) -> None: ...
    def missing_paths(self, missing_files: list[str], missing_dirs: list[str]) -> None: ...
    def error(self, msg: str) -> None: ...
```

Infra implementation writes the exact pre-refactor text to stderr.

## `CommandExecutor` → runs a plan

Owned by **domain** (`CommandExecutor` protocol, `execute(cmds: CommandPlan) -> None`);
the real implementation lives in infrastructure (`Runner.execute`).

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
```

App flows (`interactive_flow`, `switch_flow`, `run_selection`) take `FlowDeps` and
contain **no** business rules and **no** raw external calls (US3): each step either
loads an adapter, queries a domain capability, or threads a value between them.

## Concrete implementations (infrastructure)

| Port | Implementation |
|------|----------------|
| `ConfigLoader` | `infrastructure/config_loader.py` |
| `CandidateDiscovery` | `infrastructure/discovery.py` |
| `SelectionClassifier` | `infrastructure/classifier.py` |
| `EnvironmentProbe`, `ZoxideScorer`, `Picker`, `CommandExecutor` | `infrastructure/runner.py` (`Runner`) |
| `MessageOutput` | `infrastructure/messages.py` |

## Related

- Domain contracts: [`domain-contracts.md`](./domain-contracts.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)