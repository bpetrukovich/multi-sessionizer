# Data Model: Layered Architecture Refactoring

**Phase 1 output** — the entities, DTOs, layer rules, and boundary contracts that the
refactor introduces. This is a *target* model; implementation moves existing behavior
into it. See [`contracts/`](./contracts/) for the interface contracts and
[`research.md`](./research.md) for the decisions behind this model.

## 1. Entities

### 1.1 `Selection` — *domain DTO* (FR-007)

The set of directories and files the user wants to open.

| Field | Type | Notes |
|-------|------|-------|
| `dirs` | `tuple[str, ...]` | session per directory |
| `files` | `tuple[str, ...]` | opened with `nvim` in their parent directory's session |

Frozen dataclass. Produced by **infrastructure** (`classify_args` / `classify_selection`),
consumed by **domain** (`plan`, `run`).

### 1.2 `RuntimeSnapshot` — *domain DTO* (FR-008)

A point-in-time view of the tmux environment consumed by planning.

| Field | Type | Notes |
|-------|------|-------|
| `in_tmux` | `bool` | tool runs inside tmux (`TMUX` env) |
| `tmux_server_running` | `bool` | a tmux server is up (`pgrep`) |
| `existing` | `Mapping[str, str]` | session name → **realpath-normalized** path |

Frozen dataclass. Produced by **infrastructure** (`EnvironmentProbe.snapshot()`), defined
by **domain**. Domain NEVER reads `TMUX`, probes tmux, or lists sessions itself.

### 1.3 `Command` — *domain DTO* (FR-009)

A single executable unit. `Command(program, args_tuple)` with `argv() -> list[str]`.

### 1.4 `CommandPlan` — *domain DTO* (FR-009)

`class CommandPlan(list[Command])` — an ordered list of commands. Equality, indexing,
and slicing behave like a plain `list`, so existing test assertions hold unchanged.

### 1.5 `Configuration` — *app DTO* (FR-011)

The user-configurable values. **Defined by app**, produced by infrastructure from the
TOML file. The domain MUST NOT depend on it.

| Field | Type | Notes |
|-------|------|------|
| `project_roots_depth_1` | `tuple[str, ...]` | depth-1 roots |
| `project_roots_depth_2` | `tuple[str, ...]` | depth-2 roots |
| `additional_dirs` | `tuple[str, ...]` | verbatim dirs |
| `additional_files` | `tuple[str, ...]` | verbatim files |

Frozen dataclass named `Config`. Missing keys → empty tuple (no built-in defaults).

## 2. Layer rules (FR-001 → FR-005, SC-003, SC-004)

Single verifiable dependency rule:

```
domain   → (nothing)            # stdlib `os.path` string helpers only; no subprocess,
                                #   no filesystem stat, no environment, no app/infra imports
app      → domain               # plus its own DTOs/ports
infrastructure → domain, app    # satisfies app's contracts and domain's DTOs
```

Consequences:
- All subprocess, filesystem, environment, stdin/stdout, and terminal side effects live
  in `infrastructure/` (FR-005).
- `domain/` contains exactly: `models`, `naming`, `rank`, `plan`, `run`.
- `app/` contains exactly: `configuration` (DTO), `ports` (contracts), `flows` (wiring).
- The top-level legacy modules (`cli.py`, `config.py`, `discovery.py`, `rank.py`,
  `naming.py`, `decisions.py`, `runner.py`) are **re-export facades with zero logic** —
  part of the infrastructure layer's public surface. `main.py` is real infra code
  (CLI dispatch + composition root). SC-004's "no mixed-layer files" is interpreted as
  "no file mixing layer *behavior*"; facades contain none.

**Static verification (SC-003/SC-004)**: a test or `ruff`-time check asserts that no
module under `multi_sessionizer/domain/` imports `app`, `infrastructure`, `subprocess`,
reads `os.environ`, or calls `os.path.realpath`. See `quickstart.md` §Static checks.

## 3. Path normalization contract (R2)

- Every path entering the domain is already canonical: `classify_args` and
  `classify_selection` realpath; the snapshot builder realpaths existing-session values.
- `discovery` output keeps today's `os.path.abspath` (logical) form for display/commands.
- The domain compares paths **literally** (`a == b`). This reproduces today's
  `realpath(a) == realpath(b)` because both sides are realpath'd at the boundary.

## 4. State transitions

The session-planning state machine is unchanged and lives in `domain/plan.py`:

```
selection + snapshot
  ├─ single dir, no files        → ensure session → attach/switch
  ├─ single file, no dirs        → ensure session(parent) → send-keys nvim → attach/switch
  ├─ multiple dirs/files         → ensure session per dir (dirs before files), send-keys
  │                                for each file → post-step
  │                                (attach first | choose-session | plain attach)
  └─ empty                       → []
```

Reuse/disambiguation rules (unchanged): existing session reused iff same path; otherwise
name disambiguated with numeric suffix (`dup`, `dup-2`, ...). Name rules: basename, dots
→ `_`, stable.

## 5. Capabilities & ports (who calls whom)

| Capability | Layer | Signature |
|------------|-------|-----------|
| `plan` (core) | domain | `plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan` |
| `plan` (legacy, `plan_legacy` aliased as `plan` via `decisions` facade) | domain | `plan(dirs, files, *, in_tmux, tmux_server_running, existing=None) -> CommandPlan` (pure wrapper) |
| `run` | domain | `run(selection, snapshot, executor: CommandExecutor) -> None` |
| `session_name` | domain | `session_name(path: str) -> str` |
| `rank_dirs` / `build_picker_list` / `parse_zoxide_scores` | domain | pure |
| `run_selection` | app | `run_selection(selection, deps: FlowDeps) -> int` |
| `interactive_flow` | app | `interactive_flow(deps: FlowDeps) -> int` |
| `switch_flow` | app | `switch_flow(paths, deps: FlowDeps) -> int` |
| `main` / `_split_argv` / `_run` / `default_deps` | infra | CLI dispatch + composition root |
| `Runner` | infra | implements `EnvironmentProbe`, `ZoxideScorer`, `Picker`, `CommandExecutor` |
| `ConfigLoader` impl | infra | `load_config`, `missing_files`, `missing_dirs` |
| `CandidateDiscovery` impl | infra | `collect_dirs`, `collect_files` |
| `SelectionClassifier` impl | infra | `classify_args`, `classify_selection` |
| `MessageOutput` impl | infra | stderr/stdout printing (`config_not_found`, `missing_paths`, `error`) |

`FlowDeps` (app-owned bundle) carries the adapters into the app flows:

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

## 6. Flow wiring (FR-013 / FR-014)

**Interactive flow** (`app/ports` + `app/flows`):
`ConfigLoader.load` → `CandidateDiscovery.collect_dirs/collect_files` →
`ZoxideScorer.scores` → `rank.parse_zoxide_scores` + `rank.build_picker_list` (domain) →
`Picker.pick` → `SelectionClassifier.classify_selection` → `run_selection`.

**Switch flow**: `SelectionClassifier.classify_args` (infra, called from `main`) →
`run_selection` (app) → `run` (domain).

**`run_selection`**: `EnvironmentProbe.snapshot()` (infra) → `run(selection, snapshot,
executor)` (domain) → `0`.

## 7. Entity → module map

| Entity / rule | Module |
|---------------|--------|
| `Selection`, `RuntimeSnapshot`, `Command`, `CommandPlan` | `domain/models.py` |
| session planning | `domain/plan.py` |
| `run` capability + `CommandExecutor` | `domain/run.py` |
| session naming | `domain/naming.py` |
| usage ranking | `domain/rank.py` |
| `Config` DTO | `app/configuration.py` |
| adapter protocols + `FlowDeps` | `app/ports.py` |
| flow wiring | `app/flows.py` |
| CLI dispatch + composition root | `main.py` |
| config file → `Config` | `infrastructure/config_loader.py` |
| filesystem discovery | `infrastructure/discovery.py` |
| argument / picker-output classification | `infrastructure/classifier.py` |
| tmux/zoxide/fzf/env/execution | `infrastructure/runner.py` |
| stderr/stdout output | `infrastructure/messages.py` |