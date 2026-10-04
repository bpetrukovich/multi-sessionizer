# Domain Contracts

Internal contracts owned by the **domain** layer (FR-007/FR-008/FR-009/FR-012). The
infrastructure layer satisfies these; the app layer consumes them. Domain code is pure:
no subprocess, no filesystem stat, no environment reads, no `os.path.realpath`.

## DTOs (`domain/models.py`)

```python
@dataclass(frozen=True)
class Selection:
    dirs: tuple[str, ...]
    files: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeSnapshot:
    in_tmux: bool
    tmux_server_running: bool
    existing: Mapping[str, str]  # session name -> realpath-normalized path


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]

    def argv(self) -> list[str]: ...


class CommandPlan(list[Command]): ...  # ordered list; list-compatible equality/slicing
```

## Capabilities

### `plan` — core (`domain/plan.py`)

```python
def plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan
```

Deterministic function of its inputs. Produces the exact tmux/zoxide sequence. Same-input
twice → identical plan. Reuses an existing session iff its snapshot path equals the
target path; otherwise disambiguates the name with a numeric suffix.

### `plan` — legacy wrapper

```python
def plan(dirs, files, *, in_tmux, tmux_server_running, existing=None) -> CommandPlan
```

Pure argument-positioning wrapper that builds `Selection(dirs, files)` and
`RuntimeSnapshot(...)` and delegates to the core. Retained so the existing test suite
calls stay byte-identical.

### `run` (`domain/run.py`)

```python
class CommandExecutor(Protocol):
    def execute(self, cmds: CommandPlan) -> None: ...

def run(selection: Selection, snapshot: RuntimeSnapshot, executor: CommandExecutor) -> None
```

Plans via `plan`, then hands the plan to the injected executor. The domain defines the
executor contract; the real implementation is an infrastructure adapter (fake in tests).

## Purity / testability guarantees (FR-018, US1)

- `plan` and `run` can be exercised with hand-built DTOs on a machine with **no** tmux,
  fzf, or zoxide installed, **no** `TMUX` env var, and no real execution.
- No subprocess, filesystem, environment, or terminal access anywhere in `domain/`.

## Command sequences (parity reference)

Pinned in `tests/test_decisions.py` (unchanged). Representative:

- Single dir → `zoxide add <dir>`; `tmux new-session -ds <name> -c <dir>`;
  `tmux attach -t <name>` (or `switch-client`/`refresh-client` inside tmux).
- Single file → session for parent dir; `tmux send-keys -t <name> "nvim '<file>'"
  Enter`; attach/switch.
- Multiple → dirs before files; one post-step: `attach -t <first>` (no server outside
  tmux), `choose-session` + `refresh-client -S` (inside tmux), or plain `attach`
  (server running).

## Related

- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)