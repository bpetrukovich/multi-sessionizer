# Data Model: Named Session Groups

**Phase 1 output** — the entities, DTOs, layer rules, and boundary contracts that
this feature introduces. See [`contracts/`](./contracts/) for interface contracts and
[`research.md`](./research.md) for the decisions behind this model.

## 1. Entities

### 1.1 `SessionEntry` — *domain DTO* (new, FR-001/FR-003)

The unified element of the `sessions` config list. A discriminated union over the
three accepted forms:

| Field | Type | Kind | Notes |
|-------|------|------|-------|
| `kind` | `str` (`"directory"` \| `"workspace"` \| `"group"`) | all | discriminator |
| `path` | `str` | directory | realpath-normalized directory (canonicalized at infra boundary) |
| `definition` | `str` | workspace | authored inline YAML (verbatim — the fingerprint input) |
| `name` | `str` | group | group label |
| `members` | `tuple[SessionEntry, …]` | group | member entries — **directory/workspace only** (nesting rejected, FR-007) |

```python
@dataclass(frozen=True)
class SessionEntry:
    kind: str
    path: str = ""
    definition: str = ""
    name: str = ""
    members: tuple[SessionEntry, ...] = ()
```

Group members carry `kind == "directory" | "workspace"` and never `"group"`.

### 1.2 `Config` — *app DTO* (FR-001/FR-002, research R1/R7)

```python
@dataclass(frozen=True)
class Config:
    project_roots_depth_1: tuple[str, ...] = ()
    project_roots_depth_2: tuple[str, ...] = ()
    sessions: tuple[SessionEntry, ...] = ()
```

`additional_dirs` and `tmuxp_workspaces` are **removed**. A TOML file containing
either key raises `ConfigError` (FR-002). Missing keys → empty tuple (no built-in
defaults, constitution III).

### 1.3 `ConfigError` — *app exception* (new, FR-002/FR-010/FR-011)

Raised by `load_config` for a structurally invalid `sessions` list or a removed
key. Carries a collected list of specific messages.

### 1.4 `Selection`, `SessionSpec`, `RuntimeSnapshot`, `Command`, `CommandPlan` — *domain DTOs (unchanged)*

Exactly as feature 002 defines them. Groups are **expanded into a flat
`Selection(dirs, workspaces)` before `plan`**, so these runtime DTOs and the whole
marker-based switch-vs-create logic are untouched (SC-001).

### 1.5 `Session Marker` — *live tmux state (unchanged)*

`@multi-sessionizer-marker` = workspace fingerprint; recognition by marker match
only, never by name. Group members create/reuse sessions exactly like top-level
entries (FR-013).

## 2. Layer rules (unchanged)

```
domain   → (nothing)            # stdlib + PyYAML (pure); no subprocess, filesystem,
                                #   environment, app/infra imports, os.path.realpath
app      → domain               # plus its own DTOs/ports
infrastructure → domain, app    # satisfies app's contracts and domain's DTOs
```

Module map:

- `domain/models.py`: adds `SessionEntry`.
- `domain/session_entries.py` (**new**, pure): `classify_sessions`,
  `is_workspace_definition`, group-shape validation.
- `domain/workspace.py`, `domain/plan.py`, `domain/run.py`: **unchanged**.
- `app/configuration.py`: `Config` loses `additional_dirs`/`tmuxp_workspaces`,
  gains `sessions`; adds `ConfigError`.
- `app/ports.py`: `ConfigLoader.missing_dirs(cfg)` now reports directory **entries**
  (top-level + group members). `MessageOutput` unchanged (keeps
  `workspace_problems` for the `session` CLI flow).
- `app/flows.py`: `interactive_flow` builds the unified picker (ranked dirs +
  `[tmuxp]` labels + `[group]` labels) and expands selected groups into the flat
  `Selection`.
- `infrastructure/config_loader.py`: parses `sessions`, rejects removed keys,
  expands env/`~` + realpaths directory paths, classifies via `domain/session_entries.py`,
  raises `ConfigError`.
- `infrastructure/discovery.py`: `collect_dirs` drops `additional_dirs` (root scans
  only); directory entries are added by the flow.
- `infrastructure/messages.py`: `CONFIG_EXAMPLE` updated to `sessions`.

Static verification (`tests/test_layer_boundaries.py`) must still pass;
`domain/session_entries.py` must satisfy the same forbidden-pattern rules (PyYAML
only).

## 3. Path normalization contract (unchanged)

Every directory **entry** path is env/`~`-expanded and realpath-normalized at the
infrastructure boundary (`config_loader`), so the domain compares paths literally.
Workspace **definitions** are never expanded or path-normalized — verbatim
identity for fingerprinting (FR-016 carryover).

## 4. Classification & validation flow (FR-001/FR-003/FR-010/FR-011)

Pure classification + structural validation, then infra existence checks:

```
raw sessions list (TOML)
  │  domain/session_entries.classify_sessions  (pure, PyYAML)
  ▼
tuple[SessionEntry, ...]  +  list[str] problems
  │  any problem → ConfigError (all messages)   [load_config]
  │  directory entries → env/~/expand + realpath  [config_loader, infra]
  ▼
Config(sessions=…)
  │  missing_dirs(cfg): every directory entry path (top-level + group members)
  │   that os.path.isdir == False                [infra, exit 1]
  ▼
interactive picker
```

Group shape validation rules (all → specific problem, 0 sessions):
- group without a string `name` → rejected (FR-008);
- group with empty `sessions` array → rejected (FR-008);
- a group member that is itself a group table → nesting rejected (FR-007);
- a member that is neither a valid workspace-shaped string nor a (validatable)
  directory → rejected specifically (FR-011).

## 5. State transitions: picker → selection (FR-004/FR-005/FR-006/FR-009)

Group is a picker/expansion concept; the runtime transition graph is unchanged.

```
picker items = ranked dirs (root scans + top-level directory entries)
             + [tmuxp] <label> workspace lines
             + [group] <name> group lines
  │ pick
  ▼
selected lines → route by label:
  - directory line          → classify_selection (realpath) → dir
  - [tmuxp] <label>         → workspace entry definition
  - [group] <name>          → expand members → member dir paths + member workspace defs
  ▼
one flat Selection(dirs, workspaces)  → run_selection → plan/run (unchanged)
```

FR-009 per-entry dedup: two entries (top-level or member) are independent; `plan`'s
existing per-entry reuse (directory path match / workspace marker match) applies
unchanged. Opening a group twice reuses the same N sessions (SC-003).

## 6. Capabilities & ports (who calls whom)

| Capability | Layer | Signature |
|------------|-------|-----------|
| `classify_sessions` | domain | `(raw: Iterable[object]) -> tuple[list[SessionEntry], list[str]]` (pure) |
| `is_workspace_definition` | domain | `(value: str) -> bool` (pure shape check) |
| `plan` / `run` | domain | unchanged (`Selection`, `RuntimeSnapshot`) |
| `interactive_flow` | app | load → (ConfigError → error/1) → missing_dirs → discovery → rank → build unified picker → route selection → expand groups → `run_selection` |
| `session_flow` / `switch_flow` | app | unchanged (workspace CLI / dir CLI) |
| `ConfigLoader` impl | infra | `load` (+`sessions`, `ConfigError` on removed keys), `missing_dirs` (directory entries) |
| `CandidateDiscovery` impl | infra | `collect_dirs` (root scans only; no `additional_dirs`) |
| `MessageOutput` impl | infra | `config_not_found`, `missing_dirs`, `workspace_problems`, `error`; updated `CONFIG_EXAMPLE` |

## 7. Entity → module map

| Entity / rule | Module |
|---------------|--------|
| `SessionEntry`, `Selection`, `SessionSpec`, `RuntimeSnapshot`, `Command`, `CommandPlan` | `domain/models.py` |
| classify / validate unified `sessions` | `domain/session_entries.py` |
| workspace parse/validate/fingerprint/label/name | `domain/workspace.py` (unchanged) |
| session planning (marker reuse, post-step) | `domain/plan.py` (unchanged) |
| `Config` (+`sessions`, −removed keys), `ConfigError` | `app/configuration.py` |
| adapter protocols + `FlowDeps` | `app/ports.py` |
| flow wiring (picker build, group expansion) | `app/flows.py` |
| config file → `Config` (+reject removed keys, realpath dirs) | `infrastructure/config_loader.py` |
| root-scan directory discovery | `infrastructure/discovery.py` |
| user-facing text + `CONFIG_EXAMPLE` | `infrastructure/messages.py` |