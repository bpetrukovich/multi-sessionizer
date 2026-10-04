# Data Model: tmuxp Config Support

**Phase 1 output** — the entities, DTOs, layer rules, and boundary contracts that this
feature introduces. See [`contracts/`](./contracts/) for the interface contracts and
[`research.md`](./research.md) for the decisions behind this model.

## 1. Entities

### 1.1 `Config Entry` — *domain concept* (FR-004/FR-007)

One selectable item in the picker. Either:

| Kind | Carries | Identity |
|------|---------|----------|
| **directory** | a path | the realpath-normalized path (unchanged) |
| **inline tmuxp workspace** | an authored YAML definition string | the workspace **fingerprint** (R3) |

### 1.2 `SessionSpec` — *domain DTO* (FR-022, research R5)

The provisioning unit the plan iterates over.

| Field | Type | Kind | Notes |
|-------|------|------|-------|
| `kind` | `str` (`"directory"` \| `"workspace"`) | both | discriminator |
| `path` | `str` | directory | realpath-normalized directory |
| `definition` | `str` | workspace | authored inline YAML (verbatim) |
| `fingerprint` | `str` | workspace | `sha256(definition).hexdigest()` |
| `desired_name` | `str` | workspace | declared `session_name`, or `msz-<fp[:12]>` fallback |

A selection expands into a flat ordered collection of `SessionSpec`s — directories
first, then workspaces. Future "one entry → N sessions" is a surface-only change:
expand the input into more specs before `plan` (FR-022).

### 1.3 `Session Marker` — *live tmux state* (FR-011/FR-014, research R2)

The value stored inside a tmux session that lets the tool recognize a session it
provisioned from a given entry.

- **Storage**: tmux session user option `@multi-sessionizer-marker`
- **Value**: the entry's **fingerprint** (R3)
- **Written**: by the tool, immediately after a successful detached `tmuxp load`
  (`tmux set-option -t <session> @multi-sessionizer-marker <fingerprint>`)
- **Read**: in the runtime snapshot, once, via
  `tmux list-sessions -F "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}"`
- **Contract**: recognition is **by marker match only — never by session name**. A
  missing/mismatched marker ⇒ **foreign** session, never switched into as the tool's own
  (FR-013).

### 1.4 `Selection` — *domain DTO*

```python
@dataclass(frozen=True)
class Selection:
    dirs: tuple[str, ...]  # directory paths
    workspaces: tuple[str, ...] = ()  # authored inline YAML strings
```

The second field is renamed from `files` to `workspaces`; positional construction and
equality of existing directory-related tests are preserved (SC-001). Produced by
**infrastructure** (classifier / flows), consumed by **domain** (`plan`, `run`).

### 1.5 `RuntimeSnapshot` — *domain DTO*

```python
@dataclass(frozen=True)
class RuntimeSnapshot:
    in_tmux: bool
    tmux_server_running: bool
    existing: Mapping[str, str]  # session name -> realpath-normalized path
    markers: Mapping[str, str] = {}  # session name -> marker fingerprint
```

`markers` is appended with a default so existing 3-arg positional constructions keep
working. Produced by **infrastructure** (`EnvironmentProbe.snapshot()`), defined by
**domain**. The domain reads nothing itself.

### 1.6 `Command` — *domain DTO*

```python
@dataclass(frozen=True)
class Command:
    program: str
    args: tuple[str, ...]
    input: str | None = None  # content the executor materializes to a temp file
    # whose path is appended as the final argument (R12)
```

`input` is only ever set on the `tmuxp` provisioning command (research R1).

### 1.7 `CommandPlan` — *domain DTO* (unchanged)

`class CommandPlan(list[Command])` — ordered command list; list-compatible equality.

### 1.8 `Configuration` — *app DTO* (FR-011, research R8)

```python
@dataclass(frozen=True)
class Config:
    project_roots_depth_1: tuple[str, ...] = ()
    project_roots_depth_2: tuple[str, ...] = ()
    additional_dirs: tuple[str, ...] = ()
    tmuxp_workspaces: tuple[str, ...] = ()  # inline YAML strings
```

`additional_files` is removed. Missing keys → empty tuple (no built-in defaults).
Presence of `additional_files` in the TOML file → `ConfigError` (rejected with a clear
message, never silently loaded).

### 1.9 `Workspace` — *domain parsed view* (research R4/R6)

The pure result of parsing an authored definition:

| Value | Meaning |
|-------|---------|
| `definition` | the authored YAML string (verbatim; the fingerprint input) |
| `session_name` | declared `session_name` or `None` |
| `start_directory` | declared `start_directory` (honored, never overridden — FR-016) |
| `windows` | the windows list (non-empty required) |
| `problems` | validation problems (empty ⇒ valid) |

Produced by pure `domain/workspace.py` functions (`parse_workspace`,
`validate_workspace`, `workspace_label`, `desired_name`, `fingerprint`).

## 2. Layer rules (unchanged)

```
domain   → (nothing)            # stdlib string helpers + PyYAML (pure, no I/O);
                                #   no subprocess, no filesystem, no environment,
                                #   no app/infra imports, no os.path.realpath
app      → domain               # plus its own DTOs/ports
infrastructure → domain, app    # satisfies app's contracts and domain's DTOs
```

New module map:

- `domain/` gains: `workspace.py` (parse/validate/fingerprint/label/name — pure).
- `domain/plan.py`: per-spec planning (directory path-reuse + workspace marker-reuse).
- `app/configuration.py`: `Config` loses `additional_files`, gains `tmuxp_workspaces`.
- `app/ports.py`: `ConfigLoader` loses `missing_files`; `CandidateDiscovery` loses
  `collect_files`; `MessageOutput` gains `workspace_problems`; rest unchanged.
- `infrastructure/config_loader.py`: loads `tmuxp_workspaces`, raises `ConfigError` on
  `additional_files`.
- `infrastructure/runner.py`: `Runner` gains tmuxp provisioning (temp-file materialize,
  failure detection), marker listing/setting, and populates `snapshot().markers`.
- `infrastructure/classifier.py`: `classify_args` accepts directories only (clear error
  for files).
- `infrastructure/messages.py`: `ConsoleMessageOutput` gains `workspace_problems`;
  `missing_files`/`additional_files` text removed; `CONFIG_EXAMPLE` updated.

Static verification (`tests/test_layer_boundaries.py`) still asserts the domain package
stays pure; the new `domain/workspace.py` must satisfy the same forbidden-pattern rules.

## 3. Path normalization contract (unchanged)

Every path entering the domain is already canonical (realpath at the infrastructure
boundary); the domain compares paths literally. Workspace **content** is never
path-normalized by the tool (FR-016, spec Assumptions → Path validation): `start_directory`
and other paths inside the YAML are honored verbatim and governed by tmuxp.

## 4. State transitions: switch-vs-create decision (FR-012)

Per workspace spec, the plan decides exactly one of **switch** or **create**:

```
workspace spec (fingerprint fp, desired name N)
  │
  ├─ does an existing session have markers[s] == fp?
  │     │  yes → SWITCH: attach/switch to s   (session may be named anything)
  │     │        (also reuses a session created earlier in the SAME plan)
  │     │
  │     no  → resolve a free name starting at N (skip names taken by any session,
  │            numeric suffix N-2, N-3, … — never treating a foreign session as ours)
  │            → CREATE:
  │               1. tmuxp load -d --no-progress -s <name> <tempfile>   (input = definition)
  │               2. tmux set-option -t <name> @multi-sessionizer-marker <fp>
  │               3. attach/switch (single) or shared post-step (multi)
```

Directory specs keep today's path-based decision exactly (reuse iff snapshot path equals
the target path; otherwise suffix-disambiguate; `zoxide add`; `new-session -ds -c`).

Plan shape (mirrors today's, files replaced by workspaces):

```
selection + snapshot
  ├─ single dir, no workspaces      → ensure session → attach/switch          (unchanged)
  ├─ single workspace, no dirs      → provision-or-reuse → attach/switch
  ├─ multiple dirs/workspaces       → per-spec provision/reuse (dirs first, then
  │                                   workspaces) → one post-step
  │                                   (attach -t first | choose-session | plain attach)
  └─ empty                          → []
```

## 5. Capabilities & ports (who calls whom)

| Capability | Layer | Signature |
|------------|-------|-----------|
| `parse_workspace` / `validate_workspace` / `fingerprint` / `workspace_label` / `desired_name` | domain | pure functions over the authored YAML string |
| `plan` (core) | domain | `plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan` |
| `plan` (legacy wrapper) | domain | `plan(dirs, files, *, in_tmux, tmux_server_running, existing=None) -> CommandPlan` (kept for SC-001; `files` retained for signature parity, empty in all directory flows) |
| `run` | domain | `run(selection, snapshot, executor) -> None` (unchanged) |
| `run_selection` | app | `run_selection(selection, deps: FlowDeps) -> int` (unchanged) |
| `interactive_flow` | app | validate workspaces → missing-dir check → discover dirs → zoxide rank → build picker (dirs + `[tmuxp] <label>` lines) → pick → split labels/paths → classify dirs → `run_selection` |
| `session_flow` | app | validate the CLI workspace(s) → `run_selection` |
| `switch_flow` | app | dirs-only classifier → `run_selection` |
| `main` / `_split_argv` / `_run` / `default_deps` | infra | + `session` subcommand dispatch; `_run(dirs, files)` signature kept (files always `[]`) |
| `Runner` | infra | implements `EnvironmentProbe` (snapshot incl. `markers`), `ZoxideScorer`, `Picker`, `CommandExecutor`; tmuxp provisioning + marker set/read |
| `ConfigLoader` impl | infra | `load_config` (+`tmuxp_workspaces`, `ConfigError` on `additional_files`), `missing_dirs` |
| `CandidateDiscovery` impl | infra | `collect_dirs` (unchanged) |
| `SelectionClassifier` impl | infra | `classify_args` (dirs only), `classify_selection` (dirs) |
| `MessageOutput` impl | infra | `config_not_found`, `missing_dirs`, `workspace_problems`, `error` |

## 6. Flow wiring (new)

**Interactive**: `ConfigLoader.load` → validate workspaces (domain) → `missing_dirs`
→ `CandidateDiscovery.collect_dirs` → `ZoxideScorer.scores` → domain `rank` → build
`label -> definition` map + picker list → `Picker.pick` → split workspace labels from
paths → `SelectionClassifier.classify_selection` (dirs) → `Selection(dirs, defs)` →
`run_selection`.

**Session (CLI)**: validate each inline workspace (domain) → error+1 if invalid →
`Selection((), defs)` → `run_selection`.

**Switch (CLI)**: `SelectionClassifier.classify_args` (dirs only) → `run_selection`.

**`run_selection`**: `EnvironmentProbe.snapshot()` (incl. markers) → `run` (domain) → 0.

## 7. Entity → module map

| Entity / rule | Module |
|---------------|--------|
| `Selection`, `SessionSpec`, `RuntimeSnapshot`(+`markers`), `Command`(+`input`), `CommandPlan` | `domain/models.py` |
| workspace parse / validate / fingerprint / label / name | `domain/workspace.py` |
| session planning (marker reuse, tmuxp commands, post-step) | `domain/plan.py` |
| fallback workspace name, directory naming | `domain/naming.py` |
| `run` capability + `CommandExecutor` | `domain/run.py` |
| usage ranking | `domain/rank.py` (unchanged) |
| `Config` DTO (+`tmuxp_workspaces`, −`additional_files`) | `app/configuration.py` |
| adapter protocols + `FlowDeps` | `app/ports.py` |
| flow wiring (`interactive_flow`, `session_flow`, `switch_flow`, `run_selection`) | `app/flows.py` |
| CLI dispatch + composition root (+`session`) | `main.py` |
| config file → `Config` (+`ConfigError` on `additional_files`) | `infrastructure/config_loader.py` |
| filesystem discovery (dirs only) | `infrastructure/discovery.py` |
| argument / picker-output classification | `infrastructure/classifier.py` |
| tmux/tmuxp/zoxide/fzf/env/execution (+marker read/write, temp config) | `infrastructure/runner.py` |
| stderr/stdout output (+`workspace_problems`) | `infrastructure/messages.py` |