# Domain Contracts

Internal contracts owned by the **domain** layer (FR-007/FR-010/FR-011/FR-012/FR-015/
FR-016/FR-022). The infrastructure layer satisfies these; the app layer consumes them.
Domain code is pure: no subprocess, no filesystem stat, no environment reads, no
`os.path.realpath`, no app/infrastructure imports.

## DTOs (`domain/models.py`)

```python
@dataclass(frozen=True)
class Selection:
    dirs: tuple[str, ...]  # directory paths
    workspaces: tuple[str, ...] = ()  # authored inline tmuxp YAML strings


@dataclass(frozen=True)
class SessionSpec:
    kind: str  # "directory" | "workspace"
    path: str = ""  # directory path (kind == "directory")
    definition: str = ""  # authored YAML (kind == "workspace")
    fingerprint: str = ""  # sha256(definition).hexdigest() (kind == "workspace")
    desired_name: str = ""  # declared session_name or `msz-<fp[:12]>` fallback (workspace)


@dataclass(frozen=True)
class RuntimeSnapshot:
    in_tmux: bool
    tmux_server_running: bool
    existing: Mapping[str, str]  # session name -> realpath-normalized path
    markers: Mapping[str, str] = {}  # session name -> marker fingerprint


@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]
    input: str | None = None  # executor materializes to a temp file,
    # appends its path as the final argument

    def argv(self) -> list[str]: ...


class CommandPlan(list[Command]): ...  # ordered list; list-compatible equality/slicing
```

### Compatibility invariants (SC-001)

- `Selection(dirs, workspaces)` keeps the old positional shape — every existing
  `Selection(dirs, files)` construction still works (the second field is `workspaces`).
- `RuntimeSnapshot` fields 1–3 are unchanged and positional; `markers` is appended with
  a default, so `RuntimeSnapshot(False, False, {})` keeps working.
- `Command(program, args)` still constructs with `input=None`; plan equality against
  existing expectations is unaffected.
- `plan_legacy(dirs, files, *, in_tmux, tmux_server_running, existing=None)` is kept
  for the existing test suite; directory flows pass `files=[]`. Non-empty `files` is a
  program error (the file feature is removed) and is rejected.

## Workspace capability (`domain/workspace.py`, pure)

| Function | Signature | Notes |
|----------|-----------|-------|
| `parse_workspace` | `(definition: str) -> Workspace` | `yaml.safe_load`; raises nothing (problems are collected) |
| `validate_workspace` | `(definition: str) -> list[str]` | parse failure; not a mapping; `windows` missing/not-a-list/empty; `session_name` not a string |
| `fingerprint` | `(definition: str) -> str` | `sha256(definition.encode()).hexdigest()` over the authored bytes (R3) |
| `workspace_label` | `(definition: str) -> str` | `[tmuxp] <session_name>` or `[tmuxp] msz-<fp[:12]>` (R10) |
| `desired_name` | `(definition: str) -> str` | declared `session_name` or `msz-<fp[:12]>` fallback (R11) |

## Capabilities

### `plan` — core (`domain/plan.py`)

```python
def plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan
```

Deterministic function of its inputs: same input twice → identical plan. Expands the
selection into a flat ordered collection of `SessionSpec`s (directories first, then
workspaces — mirrors today's dirs-before-files ordering) and processes each spec:

- **Directory spec** (unchanged behavior): reuse an existing session iff
  `snapshot.existing[name] == path`; otherwise disambiguate with a numeric suffix
  (`dup`, `dup-2`, …); emit `zoxide add <path>` and, when creating,
  `tmux new-session -ds <name> -c <path>`.
- **Workspace spec**: reuse iff a session (existing or created earlier in the same
  plan) carries `markers == fingerprint` — switch to it under whatever name it has
  (**never** keyed on the session name). Otherwise resolve a free name starting at
  `desired_name` (skipping names taken by any session, numeric suffix; the foreign
  session is never treated as ours), then emit:
  1. `tmuxp load -d --no-progress -s <name> <temp-config>` (`input = definition`);
  2. `tmux set-option -t <name> @multi-sessionizer-marker <fingerprint>`.

  Per-plan marker tracking (`fp -> name`) makes two identical definitions selected in
  one plan reuse the same single session.

Single-selection shortcut: one directory *or* one workspace attaches/switches straight
in. Multiple selections (dirs + workspaces, any mix): per-spec provision/reuse, then
one shared post-step: `attach -t <first>` (no server, outside tmux),
`choose-session` + `refresh-client -S` (inside tmux), or plain `attach` (server
running). Empty selection → `[]`.

### `plan` — legacy wrapper

```python
def plan(dirs, files, *, in_tmux, tmux_server_running, existing=None) -> CommandPlan
```

Pure argument-positioning wrapper retained so the existing directory-related test
calls stay byte-identical (SC-001). `files` must be empty (file support removed).

### `run` (`domain/run.py`)

```python
class CommandExecutor(Protocol):
    def execute(self, cmds: CommandPlan) -> None: ...

def run(selection: Selection, snapshot: RuntimeSnapshot, executor: CommandExecutor) -> None
```

Unchanged: plans via `plan`, hands the plan to the injected executor.

## Session marker (FR-011/FR-013/FR-014)

- Option name: `@multi-sessionizer-marker`; value: the workspace fingerprint.
- The domain decides switch-vs-create solely from `snapshot.markers` + the spec's
  fingerprint; it never uses a session name as an identity signal.
- A session with a missing/mismatched marker is **foreign** — the plan must never
  attach/switch to it as if it were the tool's own (it may, however, cause a
  disambiguation, like any taken name).

## Purity / testability guarantees (FR-018, US1)

- `plan`, `run`, and the workspace functions can be exercised with hand-built DTOs on a
  machine with no tmux, tmuxp, fzf, or zoxide installed, no `TMUX` env var, and no real
  execution.
- No subprocess, filesystem, environment, or terminal access anywhere in `domain/`
  (PyYAML parsing and `hashlib` are pure).

## Command sequences (parity + new)

Pinned in `tests/test_decisions.py` (unchanged for directories) and new
`tests/test_plan_workspaces.py`. Representative:

- Single dir → `zoxide add <dir>`; `tmux new-session -ds <name> -c <dir>`;
  `tmux attach -t <name>` (or `switch-client`/`refresh-client` inside tmux).
- Single workspace (new) → `tmuxp load -d --no-progress -s <name> <cfg>` (input =
  definition); `tmux set-option -t <name> @multi-sessionizer-marker <fp>`;
  `tmux attach -t <name>` (or switch).
- Workspace reuse (new) → just the attach/switch command (no `tmuxp`, no
  `set-option`).
- Multiple (dirs then workspaces) → one post-step (attach first | choose-session |
  plain attach).

## Related

- CLI behavior: [`cli-contract.md`](./cli-contract.md)
- App-owned adapter contracts: [`app-ports.md`](./app-ports.md)
- Entities & layer rules: [`../data-model.md`](../data-model.md)