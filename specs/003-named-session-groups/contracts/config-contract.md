# Config Contract: unified `sessions`

**External interface** of the tool's TOML config (`~/.config/multi-sessionizer/
config.toml`, override via `MULTI_SESSIONIZER_CONFIG`). This is the surface the
feature changes (FR-001/FR-002/FR-003).

## File location

`~/.config/multi-sessionizer/config.toml` (or `$MULTI_SESSIONIZER_CONFIG`).

## Top-level keys

| Key | Type | Meaning | Default |
|-----|------|---------|---------|
| `project_roots_depth_1` | array of strings | roots whose direct children are picker candidates | empty list |
| `project_roots_depth_2` | array of strings | roots whose children + grandchildren are candidates | empty list |
| `sessions` | array (mixed) | directory strings, workspace strings, and group tables — the unified session surface | empty list |

`additional_dirs` and `tmuxp_workspaces` are **removed**. A file containing either
fails to load with a clear `ConfigError` (FR-002); there is no migration or
compatibility shim.

## `sessions` element forms (FR-003)

Each element is classified by shape:

1. **Directory** — any string that is **not** workspace-shaped. Env variables and
   `~` are expanded, then the path is realpath-normalized. Must exist on disk
   (checked by `missing_dirs`).
2. **Workspace** — a string that parses (via YAML) to a mapping with a non-empty
   `windows` list. Kept verbatim; never expanded or normalized. Recognized by the
   marker-based rules of feature 002.
3. **Group** — a table `{ name = "<label>", sessions = [ … ] }`. Members are
   directory strings and/or workspace strings (no nested groups). Appears in the
   picker as a single `[group] <name>` line and expands to one session per member.

```toml
project_roots_depth_1 = ["$HOME/work"]
project_roots_depth_2 = ["$HOME/personal"]

sessions = [
  # 1. a directory
  "$HOME/work/api",

  # 2. an inline tmuxp workspace (verbatim)
  'session_name: "web"
windows:
  - shell_command: "npm run dev"',

  # 3. a named group of directories and workspaces
  { name = "frontend stack",
    sessions = [
      "$HOME/work/web-frontend",
      'session_name: "dev-server"
windows:
  - shell_command: "yarn dev"',
    ] },
]
```

## Validation (FR-007/FR-008/FR-010/FR-011)

Rejected at load with a specific `ConfigError` (exit 1, no session created):

- group without a string `name`;
- group with an empty `sessions` array;
- a group member that is itself a group table (nesting);
- a member that is neither a valid workspace-shaped string nor a directory;
- presence of removed keys `additional_dirs` / `tmuxp_workspaces`.

Directory entries (top-level and group members) that do not exist on disk are
reported by `missing_dirs` (exit 1), as today.

## Example (mirrors `CONFIG_EXAMPLE`)

```toml
project_roots_depth_1 = ["$HOME"]
project_roots_depth_2 = ["$HOME/work"]
sessions = [
  "$HOME/Documents",
  "$HOME/Projects",
  'session_name: "project"
windows:
  - shell_command: "vim"',
]
```

## Related

- Picker / CLI behavior: [`cli-contract.md`](./cli-contract.md)
- Adapter contracts: [`app-ports.md`](./app-ports.md)
- Pure classifier: [`domain-contracts.md`](./domain-contracts.md)
- Entities: [`../data-model.md`](../data-model.md)