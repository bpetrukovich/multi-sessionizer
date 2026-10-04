# Research: Layered Architecture Refactoring

**Phase 0 output** — resolves every "NEEDS CLARIFICATION" / dependency / integration
question from the Technical Context. Format: Decision / Rationale / Alternatives.

## R1 — Package layout for the three layers

- **Decision**: `src/multi_sessionizer/` keeps the top package; add `domain/`, `app/`,
  `infrastructure/` subpackages. All behavioral code lives in one of them.
- **Rationale**: src-layout is the modern Python/uv default and avoids accidental
  imports of unpackaged source. Layer subpackages under one top package are idiomatic
  (DDD naming), and give a single verifiable dependency rule. Empty `__init__.py`
  files avoid accidental cross-layer imports.
- **Alternatives considered**: flat package with `*_domain.py` prefixed files (loses
  grouping and makes the dependency rule harder to verify); putting everything at the
  package root and only renaming (fails FR-001).

## R2 — Domain purity vs. `os.path.realpath` (path normalization at the boundary)

- **Decision**: Remove `realpath` from the domain. The domain compares paths **literally**
  (`_same_path` becomes `a == b`). Infrastructure normalizes every path that enters the
  domain with one `normalize_path = os.path.realpath` helper, applied at:
  (a) `classify_args` (already realpaths — unchanged),
  (b) `classify_selection` (picker output → `Selection`),
  (c) the runtime-snapshot builder (existing-session values).
  `discovery` output stays `os.path.abspath` (logical) exactly as today so the discovery
  tests and the bounded-scan guarantees are untouched.
- **Rationale**: `os.path.realpath` resolves symlinks by stat'ing the filesystem — a
  side effect. US1/FR-002 forbid the domain from reading the filesystem. Today the
  domain realpaths *both* comparison sides inside `_same_path`; by realpath'ing the
  same sides at the infrastructure boundary, literal equality reproduces today's
  comparison. All existing planning tests use already-consistent literal paths, so the
  legacy wrapper passes unchanged.
- **Parity caveats (documented, covered by smoke tests)**: the interactive flow's
  session **name** and `-c`/`zoxide add` strings are derived from the selection path.
  Today those use the logical (abspath) string while the comparison uses realpath. After
  this change the interactive selection is realpath'd at classify time (matching what
  `switch` already does today), so reuse detection is preserved in all cases; the only
  observable delta is a session-name change when a selected project dir is a symlink
  whose target basename differs — rare, and arguably a correctness fix (name now matches
  the session's real cwd). Switch flow is unaffected (already realpath'd today).
- **Alternatives considered**: keep `realpath` in domain (violates purity gate);
  realpath discovery output (breaks `test_discovery` on macOS where `/tmp →
  /private/tmp`); inject a `PathNormalizer` callable into domain (extra indirection
  with no consumer).

## R3 — DTO storage shapes (frozen dataclasses)

- **Decision**: `@dataclass(frozen=True)` for all DTOs. `RuntimeSnapshot.existing` is a
  `Mapping[str, str]` field (a plain dict at construction).
- **Rationale**: frozen dataclasses give `__eq__`/`__hash__`/`repr` from the stdlib with
  zero dependencies; keyword construction keeps tests readable. The `Mapping` field means
  the domain can use `name in existing` / `existing.get(...)` with zero conversion, and
  tests keep building plain dicts. `CommandPlan` is a `list[Command]` subclass, so
  `plan(...) == [cmd, ...]`, `cmds[-1]`, and `cmds[-2:]` all keep working.
- **Alternatives considered**: `tuple[(name, path), ...]` or `frozenset` for the
  snapshot mapping (hashable but break "tests build dicts" parity and require lookup
  conversion — only worth it if snapshots must be dict/set keys, which they don't);
  `Sequence`/immutable plan container (`tuple == list` is `False`, needs `__eq__`
  overrides — most surprising).

## R4 — Legacy `plan()` signature vs. DTO-driven entry

- **Decision**: `plan(selection: Selection, snapshot: RuntimeSnapshot) -> CommandPlan`
  is the domain core. `plan(dirs, files, *, in_tmux=, tmux_server_running=,
  existing={})` is kept as a **pure** compatibility wrapper that builds the DTOs and
  delegates to the core (exposed as `plan` via the `decisions` facade).
- **Rationale**: The wrapper is trivially pure (it only positions arguments, never
  touches I/O), all 21 existing `plan(...)` calls stay byte-identical, and the DTO path
  becomes the single source of truth used by `run` and the app flows. This satisfies
  FR-007/FR-008 (domain defines the DTOs) and SC-001 at the same time.
- **Alternatives considered**: keep the primitive signature as the core and only wrap in
  app (makes the DTOs an app-layer convenience, failing "domain exposes DTOs"); migrate
  the signature and update tests (breaks the "tests pass unchanged" gate for no
  behavioral gain).

## R5 — Adapter contracts: Protocol vs ABC

- **Decision**: `typing.Protocol` (method-only, no `@runtime_checkable`) for every
  adapter contract. The domain defines the `CommandExecutor` protocol (FR-012); the app
  defines `ConfigLoader`, `CandidateDiscovery`, `Picker`, `SelectionClassifier`,
  `EnvironmentProbe`, `ZoxideScorer`, `MessageOutput`.
- **Rationale**: structural typing gives duck-typed fakes in tests with no inheritance
  and no runtime dependency; any object with matching methods satisfies the port, which
  is exactly what US4 (replace an adapter / inject a fake) needs. `@runtime_checkable`
  is skipped because we never call `isinstance` on the ports.
- **Alternatives considered**: ABCs (add inheritance + registration ceremony for no
  benefit here); no formalization (works for a tiny tool, but protocols cost nothing and
  document the boundary for FR-019/FR-020).

## R6 — Where the `run` capability lives

- **Decision**: `run(selection, snapshot, executor)` is a **domain** capability
  (FR-012): it calls `plan` and hands the `CommandPlan` to the injected executor. The
  app flows and infra composition root only supply the executor.
- **Rationale**: FR-012 states this explicitly ("The run capability MUST be a domain
  capability... The domain MUST define the executor contract"). The app layer owns the
  *flow* wiring, not the run orchestration.
- **Alternatives considered**: placing `run` in the app layer (proposed by one research
  pass) — rejected because it contradicts FR-012.

## R7 — Printing / user-facing output ownership

- **Decision**: All stdout/stderr writes live in infrastructure. Help/version/unknown-
  command/`switch` error output stay in `main.py` (infra CLI dispatch). Config-not-found
  guidance and missing-path listings are printed by an infra `MessageOutput` adapter the
  app flow calls through a port.
- **Rationale**: FR-004/FR-005 confine stdin/stdout and all side effects to the
  infrastructure layer, and US3's independent test statically scans the app layer for
  terminal calls. A `MessageOutput` port lets `interactive_flow` communicate errors
  without printing directly.
- **Alternatives considered**: app flow returns a structured result that `main` prints
  (more ceremony, same effect); let app call `print` (violates the static scan).

## R8 — Testability strategy (FR-018/FR-019/FR-020)

- **Decision**:
  - *Domain* (FR-018): tested directly by constructing `Selection`/`RuntimeSnapshot`
    and asserting `plan`/`run` outputs — no external tool, no environment, no execution.
    The existing `test_decisions.py`/`test_naming.py`/`test_rank.py` already do this and
    are the gate for SC-002.
  - *Infrastructure* (FR-019): each adapter tested with its dependency replaced at the
    boundary — monkeypatch `subprocess.run` (as `test_runner.py` does today), temp config
    files (`test_config.py`), real `tmp_path` trees (`test_discovery.py`, `test_cli.py`).
  - *App* (FR-020): `interactive_flow`/`switch_flow`/`run_selection` are tested by
    injecting fake adapters into `FlowDeps` and asserting the wiring sequence — no real
    subprocess/filesystem runs.
- **Rationale**: mirrors the existing test shape and the spec's stated testing strategy.

## Consolidated unknowns → resolved

| Unknown | Resolution |
|---------|------------|
| Package layout for 3 layers | R1 |
| Path normalization / domain purity | R2 |
| DTO storage shapes | R3 |
| Legacy `plan` vs DTO entry | R4 |
| Protocol vs ABC for ports | R5 |
| `run` capability ownership | R6 |
| Printing ownership | R7 |
| Testing strategy per layer | R8 |