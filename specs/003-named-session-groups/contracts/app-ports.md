# App Ports (adapter contracts)

Contracts owned by the **app** layer. Infrastructure provides concrete
implementations; tests provide fakes. Replacing an adapter requires no domain
change and no more than the corresponding wiring line.

## `ConfigLoader` → `Configuration`

```python
class ConfigLoader(Protocol):
    def load(self) -> Config: ...
    def missing_dirs(self, cfg: Config) -> list[str]: ...
```

- `load()` reads the TOML file at `$MULTI_SESSIONIZER_CONFIG` or
  `~/.config/multi-sessionizer/config.toml`; raises `ConfigNotFoundError` if absent;
  expands env vars and `~` and realpaths every **directory** entry; keeps workspace
  definitions verbatim; builds `Config.sessions` via the pure domain classifier.
  Raises `ConfigError` (app-owned) when:
  - the removed keys `additional_dirs` / `tmuxp_workspaces` are present (FR-002);
  - any `sessions` element is structurally invalid (malformed group / invalid
    member / nested group — FR-007/FR-008/FR-011). All messages are collected into
    the one exception.
- `missing_dirs(cfg)` reports every directory **entry** (top-level and group
  members) whose path does not exist.

## `CandidateDiscovery` → candidate paths

```python
class CandidateDiscovery(Protocol):
    def collect_dirs(self, cfg: Config) -> list[str]: ...
```

Depth-1 roots → direct children; depth-2 roots → children + grandchildren.
`additional_dirs` is **removed** — directory session entries are added by the flow,
not by discovery. Traversal pruned at the configured depth (never a full-tree walk).

## `ZoxideScorer` → raw score text

Unchanged: `zoxide query -l -s`, raw stdout parsed by domain `rank`.

## `Picker` → selected lines

```python
class Picker(Protocol):
    def pick(self, items: list[str]) -> list[str]: ...
```

`fzf --tmux --multi --prompt "Project > "`. Items are zoxide-ranked directory paths
followed by `[tmuxp] <label>` workspace lines and `[group] <name>` group lines.
Empty selection on cancel/error. Unchanged port.

## `SelectionClassifier` → domain `Selection`

Unchanged from feature 002: `classify_args` (directories only) and
`classify_selection` (picker **directory** lines → realpath + `Selection(dirs, ())`).
Group/workspace lines are routed by the flow via its label maps, never passed here.

## `EnvironmentProbe` → domain `RuntimeSnapshot`

Unchanged: `in_tmux`, `tmux_server_running`, `existing`, `markers`
(`@multi-sessionizer-marker`).

## `MessageOutput` → user-facing text

```python
class MessageOutput(Protocol):
    def config_not_found(self, path: object) -> None: ...
    def missing_dirs(self, missing_dirs: list[str]) -> None: ...
    def workspace_problems(self, problems: list[str]) -> None: ...
    def error(self, msg: str) -> None: ...
```

Unchanged. `workspace_problems` is still used by the `session` CLI flow.
Interactive-flow config/group errors surface via `error` (from `ConfigError`).

## `CommandExecutor` → runs a plan

Unchanged (owned by domain; infra `Runner.execute` honors `Command.input`).

## `FlowDeps` — wiring bundle

Unchanged field set:

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

## Concrete implementations (infrastructure)

| Port | Implementation |
|------|----------------|
| `ConfigLoader` | `infrastructure/config_loader.py` (+`ConfigError`, `sessions`) |
| `CandidateDiscovery` | `infrastructure/discovery.py` (root scans only) |
| `SelectionClassifier` | `infrastructure/classifier.py` |
| `EnvironmentProbe`, `ZoxideScorer`, `Picker`, `CommandExecutor` | `infrastructure/runner.py` |
| `MessageOutput` | `infrastructure/messages.py` (updated `CONFIG_EXAMPLE`) |

## Related

- Domain contracts: [`domain-contracts.md`](./domain-contracts.md)
- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Config surface: [`config-contract.md`](./config-contract.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)