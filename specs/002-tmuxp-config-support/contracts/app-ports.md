# App Ports (adapter contracts)

Contracts owned by the **app** layer (FR-003/FR-011/FR-020). Infrastructure provides
concrete implementations; tests provide fakes. The domain defines its own executor
contract (see [`domain-contracts.md`](./domain-contracts.md)). Replacing an adapter
requires no domain change and no more than the corresponding wiring line (US4, SC-005).

## `ConfigLoader` → `Configuration`

```python
class ConfigLoader(Protocol):
    def load(self) -> Config: ...
    def missing_dirs(self, cfg: Config) -> list[str]: ...
```

- `load()` reads the TOML file at `$MULTI_SESSIONIZER_CONFIG` or
  `~/.config/multi-sessionizer/config.toml`; raises `ConfigNotFoundError` if absent;
  expands env vars and `~` in every **directory** path; missing keys → empty tuple.
  Unknown keys (including the removed `additional_files`) are silently ignored.
- `missing_dirs` reports configured directory roots/`additional_dirs` that do not
  exist. (`missing_files` and `additional_files` are removed with the file feature.)

## `CandidateDiscovery` → candidate paths

```python
class CandidateDiscovery(Protocol):
    def collect_dirs(self, cfg: Config) -> list[str]: ...
```

Depth-1 roots → direct children; depth-2 roots → children + grandchildren; additional
dirs verbatim. Traversal pruned at the configured depth (never a full-tree walk).
(`collect_files` is removed; the discovery port is directory-only now.)

## `ZoxideScorer` → raw score text

```python
class ZoxideScorer(Protocol):
    def scores(self) -> str: ...
```

Runs `zoxide query -l -s`; returns raw stdout (parsed by domain `rank`). Unchanged.

## `Picker` → selected lines

```python
class Picker(Protocol):
    def pick(self, items: list[str]) -> list[str]: ...
```

`fzf --tmux --multi --prompt "Project > "`. Empty selection on cancel/error. Items are
zoxide-ranked directory paths followed by `[tmuxp] <label>` workspace lines. Unchanged
port.

## `SelectionClassifier` → domain `Selection`

```python
class SelectionClassifier(Protocol):
    def classify_args(self, argv: Sequence[str]) -> tuple[list[str], list[str]]: ...
    def classify_selection(self, lines: list[str]) -> Selection: ...
```

- `classify_args`: each arg is `realpath`'d; **directories only** — a file path raises
  `ValueError("File paths are not supported: <path>")`, anything else raises
  `ValueError("Not a directory or file: <arg>")`. The 2-tuple shape is kept for the
  legacy facade; the second slot is always empty (`files` are gone).
- `classify_selection`: picker **directory** lines → `Selection(dirs, ())`. Workspace
  lines are never passed to this method — the interactive flow splits `[tmuxp] `
  labels out via its `label -> definition` map before calling it (research R10).

## `EnvironmentProbe` → domain `RuntimeSnapshot`

```python
class EnvironmentProbe(Protocol):
    def snapshot(self) -> RuntimeSnapshot: ...
```

`in_tmux` from the `TMUX` env var; `tmux_server_running` via `pgrep tmux`;
`existing` from `tmux list-sessions -F "#{session_name}\t#{session_path}"` (values
realpath-normalized); `markers` from the same-style listing extended with the marker
column: `tmux list-sessions -F "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}"`
(sessions without the option → no entry in `markers`). The domain consumes exactly this
snapshot and reads nothing itself.

## `MessageOutput` → user-facing text

```python
class MessageOutput(Protocol):
    def config_not_found(self, path: object) -> None: ...
    def missing_dirs(self, missing_dirs: list[str]) -> None: ...
    def workspace_problems(self, problems: list[str]) -> None: ...
    def error(self, msg: str) -> None: ...
```

Infra implementation writes the exact text to stderr (see `cli-contract.md`).
`workspace_problems` prints each validation problem (FR-018, US5 scenario 2).
(`missing_files` is removed.)

## `CommandExecutor` → runs a plan

Owned by **domain** (`CommandExecutor` protocol, `execute(cmds: CommandPlan) -> None`);
the real implementation lives in infrastructure (`Runner.execute`). The executor
honors `Command.input`: content is written to a per-run temp file under the CWD, its
path appended as the final argument, and removed after the subprocess (research R1/R12).

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

App flows (`interactive_flow`, `session_flow`, `switch_flow`, `run_selection`) take
`FlowDeps` and contain **no** business rules and **no** raw external calls (US3).

## Concrete implementations (infrastructure)

| Port | Implementation |
|------|----------------|
| `ConfigLoader` | `infrastructure/config_loader.py` |
| `CandidateDiscovery` | `infrastructure/discovery.py` |
| `SelectionClassifier` | `infrastructure/classifier.py` |
| `EnvironmentProbe`, `ZoxideScorer`, `Picker`, `CommandExecutor` | `infrastructure/runner.py` (`Runner`; also tmuxp provisioning + marker read/write) |
| `MessageOutput` | `infrastructure/messages.py` |

## Related

- Domain contracts: [`domain-contracts.md`](./domain-contracts.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)