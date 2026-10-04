# Research: Named Session Groups

**Phase 0 output** — decisions that resolve every unknown in the Technical
Context and every dependency/integration for feature 003. Findings are
consolidated as **Decision / Rationale / Alternatives**.

## 1. What is the classification rule for a `sessions` element?

**Decision**: Classify each element by its **shape**, purely and
deterministically:
- a **string** that parses (via `yaml.safe_load`) to a mapping with a non-empty
  `windows` list → **workspace** entry (definition kept verbatim);
- any other **string** → **directory** entry (path);
- a **table** (mapping) with a string `name` and a non-empty `sessions` array →
  **group** entry;
- a table with any other shape, or any non-string/non-table element → **invalid**
  (reported specifically, no session created).

**Rationale**: FR-003 and the edge case ("treated as a directory if it does not
have tmuxp workspace structure") demand a deterministic default: workspace only
when it *has* workspace structure, directory otherwise. Shape is decidable from
the value alone, so classification lives in the **pure domain** (PyYAML) with no
filesystem access; directory *existence* is a separate infra concern
(`missing_dirs`).

**Alternatives considered**:
- Heuristic prefix (`[workspace]`, `[group]`) for config strings — rejected: it
  would invent a config syntax the user never asked for and break tmuxp inline
  YAML.
- A separate `type` key on each element — rejected: adds ceremony; the shape
  already disambiguates deterministically.

## 2. Does a string that is also a directory ever get misclassified as a workspace?

**Decision**: No, in practice. A directory path like `/home/u/proj` does not
parse to a YAML mapping with a `windows` list. The only way a string becomes a
workspace is workspace-shape, so ambiguous-but-non-workspace strings stay
directories (FR-003 edge case).

**Rationale**: Deterministic and unambiguous by construction.

**Alternatives considered**: Lexing the string for newlines before parsing —
rejected: fragile; `yaml.safe_load` is authoritative and already pure.

## 3. Where does group expansion happen relative to `plan`/`run`?

**Decision**: In the **app flow**, before `run_selection`. A selected group is
expanded into member directory paths + member workspace definitions, aggregated
with any other selected directories/workspaces into one flat
`Selection(dirs, workspaces)`, then handed to the unchanged `run_selection`.

**Rationale**: FR-006 (a group is never a merged session), FR-009 (per-entry
dedup), and FR-013 (member sessions behave identically to top-level) are all
satisfied for free by reusing the existing single-plan/single-post-step multi
selection. The domain `plan`/`run` are byte-identical → SC-001/SC-002 hold with
zero domain-plan changes. The 002 data-model already anticipated this: "Future
'one entry → N sessions' is a surface-only change: expand the input into more
specs before `plan`."

**Alternatives considered**: Making `plan` accept group specs directly — rejected:
would couple the runtime to a config-surface concept and risk parity; expansion
upstream is strictly simpler.

## 4. Should group member directories/workspaces also appear as individual picker entries?

**Decision**: No. Group members are reachable only through their group's single
picker line (labeled by the group name). Only **top-level** directory entries
and workspace entries become individual picker lines.

**Rationale**: US1/SC-004: "one entry per element" — each *top-level* element
yields one picker entry; a group is one entry that expands. Members are still
validated (FR-010/FR-011) and provisioned (FR-005) when the group is opened.

**Alternatives considered**: Flattening all members into the picker as separate
lines — rejected: defeats the whole purpose (one pick per group) and would make
members implicitly individually selectable, contradicting the spec's single-entry
group model.

## 5. How are picker labels disambiguated (group name collisions)?

**Decision**: Prefix workspace lines with `[tmuxp] ` (unchanged) and group lines
with `[group] `, then numeric-suffix any duplicate displayed labels (`foo`,
`foo-2`, …) using the existing `picker_labels` disambiguation pattern. The flow
keeps `label → SessionEntry` maps to route a selected line to its entry.

**Rationale**: The prefix makes group labels structurally distinct from directory
paths (which never literally equal `[group] …`) and from workspace labels, so
selection routing is unambiguous. FR-009 edge case ("picker disambiguates labels
so the group is still selectable") is satisfied; group names need not be globally
unique.

**Alternatives considered**: No prefix, relying on path-vs-name differences —
rejected: a group named identically to a discovered directory path or a workspace
label would be ambiguous to route.

## 6. How are removed config keys rejected?

**Decision**: `load_config` raises an app-owned `ConfigError` when the TOML file
contains `additional_dirs` or `tmuxp_workspaces`, with a clear message naming the
key. No migration hint, no deprecation warning, no compatibility shim (FR-002,
constitution "No backward compatibility").

**Rationale**: The rule is explicit: the old surfaces are removed outright and a
config that uses them must fail loudly, never be silently ignored.

**Alternatives considered**: Silently ignoring the old keys (status quo for the
previously-removed `additional_files`) — rejected: FR-002 mandates rejection.

## 7. Where does `sessions` validation run relative to the picker?

**Decision**: Structural validation (group shape, workspace structure, element
type) is folded into `load_config`; any problem raises `ConfigError` (all messages
collected) before the picker. Directory **existence** is checked separately by
`missing_dirs` (infra, filesystem), unchanged in spirit.

**Rationale**: FR-010 requires validating every entry before the interactive run.
Because classification and shape validation are intrinsic to *building* the
`sessions` structure, doing both at load is the single validation point and
matches "bad config → exit 1". `missing_dirs` stays separate because it needs
filesystem access and keeps the existing message contract.

**Alternatives considered**: Keeping structural validation as a separate flow step
over already-classified entries — rejected: it would require `load_config` to
return entries that may be structurally invalid, complicating the DTO for no
benefit.

## 8. Should top-level directory entries be realpath-normalized at load?

**Decision**: Yes. Directory entry paths are env/`~`-expanded **and**
realpath-normalized in `config_loader` (infra). Workspace definitions are never
expanded or normalized (verbatim identity for fingerprinting).

**Rationale**: Group-member directory paths never pass through
`classify_selection` (which realpaths picker lines), so they must be canonical
before entering the domain; doing it at load makes top-level and member
directories uniform. `missing_dirs` and `plan` both rely on canonical paths.
Domain stays free of `os.path.realpath` (constitution II).

**Alternatives considered**: Realpath only member dirs at group-open time —
rejected: inconsistent and redundant; load-time normalization is uniform.

## 9. Interaction with feature 002 (dependency satisfied)

**Decision**: Feature 002 (tmuxp workspace support) is already implemented on
`main` (commit `1dbd5ae`). Its `workspace.py` (parse/validate/fingerprint/
label/desired_name) and `plan.py` marker-based switch-vs-create are reused as-is.
The `sessions` key **supersedes** the `tmuxp_workspaces` key.

**Rationale**: The spec's Assumptions note 002 as a dependency; it is present, so
no sequencing risk. Classification reuses `yaml.safe_load` semantics and
`validate_workspace`-style structural checks.

**Alternatives considered**: Re-implementing workspace parsing inside the new
classifier — rejected: reuse the existing pure `domain/workspace.py`.