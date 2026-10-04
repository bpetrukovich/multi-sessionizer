# Research: tmuxp Config Support

**Phase 0 output** — resolves every technical unknown and integration question from the
plan's Technical Context. Format: Decision / Rationale / Alternatives.

## R1 — How to hand an inline workspace to tmuxp

- **Decision**: `tmuxp` is invoked as `tmuxp load -d --no-progress -s <session-name>
  <temp-config-file>`, where the temp config file contains the authored workspace YAML
  verbatim. The infrastructure `Runner` materializes the config into a temp file inside
  a per-run temp directory created **under the current working directory**
  (`tempfile.mkdtemp(dir=os.getcwd())`), appends the file path as the final argument,
  runs the subprocess with failure detection (non-zero exit → provisioning error), and
  removes the temp directory afterwards.
- **Rationale**: tmuxp v1.74's `tmuxp load` (verified in `src/tmuxp/cli/load.py`) accepts
  only file/dir/name specifiers (`find_workspace_file`); there is **no stdin support**,
  so an inline workspace must be materialized to a file. `-d` builds detached (the tool
  does its own attach/switch, preserving the existing one-plan/one-post-step model);
  `--no-progress` disables the animated spinner so scripted output stays clean;
  `-s <name>` overrides `session_name` *after* tmuxp's `expand()` step
  (`expanded_workspace["session_name"] = new_session_name`), so the tool never rewrites
  the user's YAML and always controls the final session name (honoring the declared
  `session_name` verbatim or injecting a fallback/disambiguated one). tmuxp resolves
  relative paths inside the workspace relative to the **config file's directory**
  (`loader.expand(raw, cwd=os.path.dirname(workspace_file))`); writing the temp file
  under the CWD therefore makes relative paths (e.g. `start_directory: ./src`) resolve
  relative to the directory the user invoked the tool from — the least surprising
  contract for inline configs. The file is transient and deleted after the run, so no
  mapping state ever leaves tmux (FR-014).
- **Alternatives considered**: piping via stdin (`tmuxp load -`) — not supported by
  tmuxp; passing the workspace through a persistent cache dir — violates statelessness;
  writing to the system temp dir — silently mis-resolves relative paths against `/tmp`;
  importing `tmuxp` as a Python library — contradicts the spec assumption that tmuxp is
  an external capability invoked through an infrastructure adapter.

## R2 — Session recognition: the marker

- **Decision**: The tool stamps every workspace session it creates with a tmux **session
  user option** named `@multi-sessionizer-marker`, whose value is the workspace
  **fingerprint** (R3). The marker is set immediately after a successful detached build
  with `tmux set-option -t <session> @multi-sessionizer-marker <fingerprint>`. The
  runtime snapshot reads it for every session in one call:
  `tmux list-sessions -F "#{session_name}\t#{session_path}\t#{@multi-sessionizer-marker}"`
  (missing option → empty field → session is not "ours"). Sessions are classified
  purely by marker match — **never by name** (FR-011).
- **Rationale**: A tmux user option is live tmux state: it needs no file, DB, or sidecar
  (FR-014), it travels with the session, and it disappears when the session is destroyed.
  Because identity is decoupled from the name, the tool never needs to police
  `session_name` (FR-015), correctly ignores foreign sessions with colliding names
  (FR-013, US3 scenario 3), and gives the downstream multi-repo tool full freedom to
  drive its own names. `#{@option}` format variables and `set-option -t <session> @name`
  are standard tmux 3.x features.
- **Alternatives considered**: encoding a prefix in the session name — breaks FR-015 and
  US3 scenario 3 (foreign session with the same name); a registry/database/sidecar file
  — violates FR-014; window/pane options — session options are the natural scope (one
  marker per session).

## R3 — Fingerprint (entry identity)

- **Decision**: `fingerprint = sha256(<authored workspace definition bytes>).hexdigest()`,
  computed over the exact inline YAML string as configured/passed (not over a
  re-serialized or name-injected form). It is the value of the marker and the identity
  of the entry (FR-010, spec Assumptions → Identity).
- **Rationale**: A byte hash of the authored string is deterministic, pure, and
  dependency-free (`hashlib`), and matches the spec's "fingerprint of its workspace
  definition" definition. Because it deliberately **excludes** the injected/disambiguated
  `session_name`, dedup survives name drift: an entry whose first run had to use
  `foo-2` still matches its original session on later runs (FR-010, FR-012). Editing the
  definition — including a reformat — produces a new fingerprint, so an edited entry is
  never silently re-attached to the old session (edge case "definition edited between
  runs"), which errs on the safe side.
- **Alternatives considered**: hashing the materialized config (with injected name) —
  breaks dedup across name collisions; a canonical re-serialization (sorted keys) —
  robust to formatting but requires a lossy YAML round-trip (tags/aliases/comments) and
  is more machinery than the spec needs; using the `session_name` as identity — violates
  FR-011/FR-013 (two entries may share a name, foreign sessions may collide).

## R4 — YAML parsing and new dependencies

- **Decision**: add **PyYAML** (`yaml`) as a runtime dependency and parse with
  `yaml.safe_load` in a new pure `domain/workspace.py`. tmuxp itself uses PyYAML, so
  client-side parsing semantics match tmuxp's. Document both new dependencies in the
  README dependency table (constitution V): **PyYAML** (required — workspace YAML
  validation/extraction) and **tmuxp** (required for workspace flows — session
  provisioning).
- **Rationale**: FR-005 (YAML format), FR-007 (picker label from `session_name`),
  FR-015 (honor/derive `session_name`), and FR-018 (structural validation **before** an
  interactive run) all require in-process YAML parsing. Validation cannot be delegated
  to tmuxp, because a "validation" `tmuxp load` would actually build sessions and would
  violate FR-023 (bounded work). Parsing is pure (no I/O), so it belongs in the domain
  and stays testable with zero external tools.
- **Alternatives considered**: stdlib-only parsing — Python has no YAML module;
  delegating validation to tmuxp — builds real sessions, unbounded, and unusable for
  the pre-picker check (FR-018); a JSON-only surface — contradicted by Q1 (YAML chosen).

## R5 — Selection / session-spec modeling (FR-022)

- **Decision**: `Selection` becomes `Selection(dirs: tuple[str, ...], workspaces:
  tuple[str, ...] = ())` — the second field is **renamed** from `files` to `workspaces`
  (authored inline YAML strings), which preserves every existing positional construction
  (`Selection(("/a/one",), ())` etc.) so directory-related tests pass unchanged (SC-001).
  The domain `plan` internally expands a selection into a flat ordered collection of
  `SessionSpec`s (`kind=directory|workspace`, plus `path`/`definition`/`fingerprint`/
  `desired_name`), and iterates per-spec with per-spec dedup (path-match for directories,
  marker-match for workspaces) and per-spec name resolution.
- **Rationale**: FR-022 requires the domain to model a selection as a collection of
  session specs whose dedup/provisioning rules are per-spec; this makes "one entry or
  one CLI parameter expands into several sessions" a pure surface/input change (expand
  to more specs before `plan`). Keeping `Selection`'s positional shape is the minimal
  change that preserves SC-001.
- **Alternatives considered**: `Selection(specs: tuple[SessionSpec, ...])` — cleaner
  reading of FR-022 but breaks every existing `Selection(dirs, files)` construction in
  `test_domain.py`/`test_app_flows.py`, violating SC-001; a separate workspaces DTO
  threaded alongside `Selection` — adds plumbing for no behavioral gain.

## R6 — Workspace validation rules (FR-018)

- **Decision**: a pure domain `validate_workspace(definition) -> list[str]` reports
  problems for: YAML parse failure; root not a mapping; `windows` missing, not a list,
  or empty (edge case: an empty workspace is rejected rather than building an empty
  session); `session_name` present but not a string. Deeper structural validity is left
  to tmuxp at build time (spec Assumptions → Path validation). Before an interactive
  run, **all** configured workspaces are validated and every problem is reported (like
  today's missing-path check); on the CLI, the `session` subcommand validates its input
  and errors with exit 1 if invalid. The workspace YAML itself is never
  env/`~`-expanded by the tool (tmuxp handles its own expansion).
- **Rationale**: catches mistakes before any session is created (US5), with the
  tool's own messages and exit codes (FR-019/FR-021); defers deep workspace semantics to
  the tool that owns them (tmuxp), per the spec's explicit assumption.
- **Alternatives considered**: full schema validation (every window/pane shape) —
  duplicates tmuxp and risks drift; calling tmuxp to validate — side effects + FR-023.

## R7 — CLI surface for inline workspaces

- **Decision**: new subcommand `multi-sessionizer session <yaml> [<yaml> ...]` — each
  argument is one inline workspace; `switch <path>...` remains the directory-only
  surface and now rejects file paths with a clear error (US4 scenario 2). `_split_argv`
  gains a `session` branch; exit codes stay 0/1/2 (FR-021); USAGE and `--help` updated.
  `session` does not read the config file (like `switch` today) — a workspace passed on
  the CLI is self-contained.
- **Rationale**: a dedicated subcommand keeps `switch`'s "everything after is a path"
  contract intact (no `--` gymnastics, per the existing CLI design) and gives the
  downstream multi-repo tool a scriptable entry point (constitution I, US2).
- **Alternatives considered**: extending `switch` with a flag (e.g. `--workspace`) —
  muddies the "verbatim paths" contract and the classifier; a positional YAML under
  `switch` — ambiguous with paths.

## R8 — Config surface for inline workspaces

- **Decision**: new list key `tmuxp_workspaces = [ "<yaml>", "<yaml>", ... ]` (each
  string is one picker entry). `additional_files` is removed from the `Config` DTO and
  the loader; if the key is present in the TOML file, the loader raises a clear
  `ConfigError` ("The 'additional_files' key is no longer supported; remove it or
  migrate entries to 'tmuxp_workspaces'"), surfaced by the interactive flow as a message
  with exit 1 — rejected with a clear message, never silently loaded (US4 scenario 1).
- **Rationale**: matches the spec's proposed representation (Assumptions → Config
  representation) and Q3; a hard, named error avoids silently dropping a user's old
  configuration.
- **Alternatives considered**: auto-migrating `additional_files` — files no longer
  exist as a concept (FR-001), so there is nothing valid to migrate; ignoring the key
  — explicitly forbidden by US4 scenario 1.

## R9 — tmuxp unavailability and provisioning failures (FR-020)

- **Decision**: the `Runner` checks `shutil.which("tmuxp")` before a workspace build
  and raises a `ProvisioningError` naming the missing tool; the `tmuxp load` subprocess
  is run with failure detection (non-zero returncode → same error path). The flow
  surfaces the message to stderr and exits 1. Because tmuxp is only invoked after the
  switch-vs-create decision and always targets a free session name, a failure cannot
  leave a half-mapped session: if the build failed, the subsequent marker `set-option`
  targets a session that does not exist and the run aborts with the provisioning error.
  tmuxp's own interactive error-recovery prompt (rare mid-build-failure path, inherent
  to tmuxp) is documented as a known tmuxp behavior; the tool reports its own error and
  exit code afterward.
- **Rationale**: gives a clear, actionable error naming the missing tool with a
  meaningful exit code, preserving the exit-code contract (FR-020/FR-021).
- **Alternatives considered**: letting the `set-option` failure be the only signal —
  less clear than naming tmuxp; pre-checking `tmuxp --version` for every interactive run
  — the check is only needed when a workspace is actually selected (FR-023).

## R10 — Picker labels and selection classification (FR-007)

- **Decision**: workspace entries appear in the picker with a prefixed, unique label —
  `[tmuxp] <session_name>` when `session_name` is declared, else `[tmuxp] <fallback>`
  where the fallback is `msz-<fingerprint[:12]>` (R11). Duplicate displayed names are
  disambiguated for display with the existing numeric-suffix rule. The interactive flow
  builds a `label -> definition` map and, on selection, separates workspace labels from
  directory paths before calling the (unchanged) `classify_selection` port for the
  remaining directory lines.
- **Rationale**: the `[tmuxp] ` prefix makes workspace lines distinguishable from
  directory paths in the picker and keeps the `SelectionClassifier` port signature
  stable so `test_app_flows.py` fakes keep passing unchanged (SC-001). Labeling by the
  declared `session_name` (with a deterministic fallback) satisfies FR-007.
- **Alternatives considered**: raw YAML as the picker line — unreadable and ambiguous
  with paths; adding a workspaces parameter to `classify_selection` — breaks the port
  and the existing fakes.

## R11 — Deterministic fallback session name (FR-015)

- **Decision**: when a workspace declares no `session_name`, the tool derives
  `msz-<fingerprint[:12]>` as the desired name (deterministic, collision-resistant, and
  recognizable). The declared `session_name` is honored verbatim when present. Collision
  handling is unchanged in spirit: if the desired name is taken by any session, a
  numeric suffix is appended (`foo-2`, `foo-3`, ...) until free — but only after the
  marker check, so a foreign session with the same name is never switched into (FR-013).
- **Rationale**: FR-015 requires a deterministic name only when none is declared; the
  `msz-` prefix marks it as tool-derived without imposing a naming scheme on declared
  names; fingerprint-derived names make cross-entry collisions vanishingly unlikely.
- **Alternatives considered**: naming from the config entry ordinal or label — not
  stable across reordering; using the full fingerprint — unwieldy session names.

## R12 — Command / snapshot DTO extensions

- **Decision**: `Command` gains a keyword-only `input: str | None = None` field: a
  command with `input` set carries content the executor must materialize to a temp file
  whose path is appended as the final argument (the tmuxp provisioning convention from
  R1). `RuntimeSnapshot` gains a `markers: Mapping[str, str] = {}` field (session name →
  marker fingerprint) appended **after** `existing` so existing 3-arg positional
  constructions (`RuntimeSnapshot(False, False, {})`) keep working. Both fields default,
  so equality on existing test expectations is unaffected.
- **Rationale**: keeps the plan pure (content is a plain string; no random paths or
  filesystem access in the domain) while moving the filesystem side effect to the
  executor, exactly like today's `Command` separation (constitution II). Defaulted
  fields preserve SC-001.
- **Alternatives considered**: the domain emitting concrete temp paths — non-deterministic
  and a filesystem side effect in the domain; a parallel side-channel for config content
  — loses the single-plan/single-post-step model (FR-009).

## Consolidated unknowns → resolved

| Unknown | Resolution |
|---------|------------|
| How to pass inline workspace to tmuxp (no stdin) | R1 (temp file under CWD + `-d --no-progress -s`) |
| How to recognize the tool's own sessions statelessly | R2 (`@multi-sessionizer-marker` session option) |
| Entry identity / fingerprint definition | R3 (sha256 of authored YAML, name-independent) |
| YAML parsing & new dependencies | R4 (PyYAML in pure domain module) |
| FR-022 "collection of session specs" modeling | R5 (Selection rename + SessionSpec expansion in plan) |
| Validation rules & where validation runs | R6 (pure domain; pre-run for config, inline for CLI) |
| CLI surface for inline workspaces | R7 (`session` subcommand; `switch` dirs only) |
| Config surface for inline workspaces | R8 (`tmuxp_workspaces`; `additional_files` rejected) |
| tmuxp missing / build failure handling | R9 (ProvisioningError, exit 1) |
| Picker labels & classification | R10 (`[tmuxp] <label>` + label map in the flow) |
| Fallback session name when none declared | R11 (`msz-<fingerprint[:12]>`) |
| Command/snapshot DTO extension | R12 (`Command.input`, `RuntimeSnapshot.markers`) |