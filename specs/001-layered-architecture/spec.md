# Feature Specification: Layered Architecture Refactoring

**Feature Branch**: `001-layered-architecture`

**Created**: 2026-10-04

**Status**: Draft

**Input**: User description: "Split the tool into layers — app, domain and infrastructure. CLI command parsing in main is infrastructure; interactive launch logic is app (wiring configs and then calling run); calling run is domain, although config parsing itself is infra; collecting shell commands is infra, although the plan logic is domain; how we know we are in tmux is infra, although it is called from domain. In general, these aspects need to be well separated. At the same time, form good DTOs between the layers, where DTOs are defined by the higher level and satisfied by the lower one."

## User Scenarios & Testing

### User Story 1 - Domain logic testable in isolation without external tools (Priority: P1)

The developer can run all session-planning logic (how sessions are named, created, attached, and the exact order of tmux/zoxide commands) without tmux, fzf, zoxide, the filesystem, or environment variables. Everything the planning logic needs to know — whether we are inside tmux, whether a tmux server is running, and which sessions already exist — is handed to it explicitly as a snapshot.

**Why this priority**: This is the core value of the refactor. Planning is the trickiest logic in the tool; making it fully deterministic and environment-free makes it fast to test and hard to break.

**Independent Test**: Run the planning tests on a machine where none of the external tools (tmux, fzf, zoxide) are installed or reachable. All tests pass, proving the logic has no hidden external dependency.

**Acceptance Scenarios**:

1. **Given** a selection (directories/files) and an explicit runtime snapshot, **When** planning runs, **Then** the produced command plan is fully determined by those inputs and never reads the environment, filesystem, or subprocesses.
2. **Given** the same selection and snapshot, **When** planning runs twice, **Then** the identical command plan is produced (deterministic).
3. **Given** a selection and a snapshot that already contains a session for the target path, **When** planning runs, **Then** the plan reuses that session instead of creating a duplicate.

---

### User Story 2 - Behavior parity for every existing flow (Priority: P1)

After the refactor, every user-facing flow behaves exactly as before: interactive run, `switch`, `--help`, `--version`, and error cases. Exit codes (0 success, 1 bad path/config, 2 unknown command), printed output, and the exact sequence of tmux/zoxide commands are identical to the pre-refactor tool.

**Why this priority**: A refactor that changes observable behavior is a regression. Parity is the gate that keeps the change safe.

**Independent Test**: Run the full existing test suite (unchanged) against the refactored code and compare the generated command sequences for representative scenarios. Also smoke-test the installed console script manually.

**Acceptance Scenarios**:

1. **Given** the interactive flow, **When** the user picks one or more projects in fzf, **Then** the same tmux/zoxide commands are executed in the same order as before the refactor.
2. **Given** the `switch PATH...` flow, **When** valid paths are supplied, **Then** the same command plan as before is produced and executed.
3. **Given** a missing config file, **When** the interactive flow starts, **Then** the tool exits with code 1 and prints the same guidance message.
4. **Given** an unknown first argument, **When** the CLI is invoked, **Then** the tool exits with code 2 and prints the same error message.

---

### User Story 3 - App is a thin, readable wiring layer (Priority: P2)

The interactive launch flow reads as a single wiring path: load configuration, discover candidate projects, rank by usage, let the user pick, classify the selection, then run. Each step is a call to either a domain capability or an infrastructure adapter. The wiring contains no business rules and no raw external calls (subprocess, filesystem, environment, terminal).

**Why this priority**: This is where a reader learns "what the tool does at startup". Keeping it pure composition makes the tool approachable and the other two layers provably clean.

**Independent Test**: Statically scan the app layer; no direct subprocess/environment/filesystem/terminal calls appear in it (only calls into infrastructure adapters or domain capabilities).

**Acceptance Scenarios**:

1. **Given** the app wiring for the interactive flow, **When** each step is inspected, **Then** it either loads an infrastructure adapter, queries a domain capability, or threads a value between them.
2. **Given** the app wiring for the `switch` flow, **When** inspected, **Then** it classifies arguments via infrastructure and delegates to the same domain run capability as the interactive flow.

---

### User Story 4 - Infrastructure adapters are replaceable behind contracts (Priority: P3)

Every external interaction (config file reading, filesystem discovery, argument classification, tmux/zoxide/fzf subprocess execution, runtime-environment detection) is isolated behind a contract. Replacing an adapter — for example a fake executor in tests, or a different picker tool — requires no domain changes and no app flow changes beyond the wiring line.

**Why this priority**: This is what makes both the domain and the infrastructure independently testable, and it is what the plan phase needs in order to define clean boundaries.

**Independent Test**: Inject a fake command executor into a flow; run a full selection through the app wiring; verify the domain produced the expected commands without any real subprocess being executed.

**Acceptance Scenarios**:

1. **Given** a fake executor is injected, **When** a selection is run, **Then** the expected command plan is observed and no real external program executes.
2. **Given** a runtime-environment adapter is replaced with a stub that reports a fixed snapshot, **When** the flow runs, **Then** the domain consumes exactly that snapshot and no environment variable is read anywhere else.

---

### Edge Cases

- Unknown first argument (`multi-sessionizer nonsense`) → exit 2 with the current message.
- Missing config file on interactive run → exit 1 with the example configuration hint.
- `switch` argument that is neither an existing directory nor an existing file → exit 1 with the current message.
- No tmux server running and not inside tmux → the plan ends with a plain `attach` to the first session.
- Running inside tmux → the plan switches the client instead of attaching.
- User cancels the fzf picker (empty selection) → clean exit 0, no commands run.
- `switch` with one file → a session is created for its parent directory and `nvim <file>` is sent to it.
- `switch` with multiple paths → one plan covering all sessions, directories processed before files, single post-step.
- Existing session for the same path (duplicate basename) → reused without suffix; different path → name disambiguated with a numeric suffix.

## Requirements

### Functional Requirements

#### Layering and dependency direction

- **FR-001**: The code MUST be organized into three layers — **domain**, **app**, **infrastructure** — such that every source unit belongs to exactly one layer.
- **FR-002**: The domain layer MUST contain only business rules (session planning, session naming, usage ranking) and MUST NOT perform subprocess calls, filesystem access, environment reads, terminal interaction, or import anything from app or infrastructure.
- **FR-003**: The infrastructure layer MUST NOT contain business rules; it MUST only provide external capabilities (CLI argument parsing, config-file reading, candidate discovery, runtime-environment detection, subprocess/terminal execution) and adapt them to the contracts defined by higher layers.
- **FR-004**: The app layer MUST NOT contain business rules or raw external calls; it MUST only wire infrastructure-provided capabilities with domain capabilities (composition).
- **FR-005**: All side effects (subprocess, filesystem, environment variables, stdin/stdout, terminal) MUST be confined to the infrastructure layer.

#### DTO ownership

- **FR-006**: A data transfer object (DTO) that crosses a layer boundary MUST be defined by the higher (consuming) layer and satisfied/implemented by the lower (producing) layer. Infrastructure MUST never invent a cross-boundary shape that higher layers do not define.
- **FR-007**: The domain MUST define the DTO for the session **selection** (a set of directories and a set of files to open).
- **FR-008**: The domain MUST define the DTO for the **runtime snapshot** (whether the tool runs inside tmux, whether a tmux server is running, and the existing sessions as a name→path mapping).
- **FR-009**: The domain MUST define the DTO for a **command** (program + arguments) and for an ordered **command plan** (a list of commands).
- **FR-010**: The infrastructure MUST produce the runtime snapshot (from the `TMUX` environment variable, process detection, and session listing) and MUST produce the selection (from classified command-line arguments), using the domain-defined DTOs.
- **FR-011**: The app MUST define the **configuration** DTO (the user-configurable values) and the infrastructure MUST produce it from the config file; the domain MUST NOT depend on the configuration DTO.

#### Run flow, flows, and CLI

- **FR-012**: The run capability MUST be a domain capability: given a selection and a runtime snapshot, it MUST produce a command plan and hand it to an injected command executor. The domain MUST define the executor contract.
- **FR-013**: The interactive flow MUST be app wiring: load configuration (infra) → discover candidates (infra) → rank by usage (domain) → user pick (infra) → classify selection (infra) → run (domain).
- **FR-014**: The `switch` flow MUST also be app wiring: classify arguments into a selection (infra) → run (domain).
- **FR-015**: CLI command parsing (which command was requested: help, version, switch, or interactive; and the unknown-command case) MUST live in infrastructure and MUST dispatch into app flows, returning the exit code.
- **FR-016**: The exit-code contract MUST be preserved exactly: 0 success, 1 bad path or config, 2 unknown command.

#### Behavior preservation

- **FR-017**: All existing user-visible behavior MUST remain identical, including printed output, exit codes, and the generated tmux/zoxide command sequence for every scenario.

#### Testability

- **FR-018**: The domain MUST be testable with zero external dependencies: tests MUST construct selections and runtime snapshots directly, with no external tool installed, no environment set, and no real execution.
- **FR-019**: Each infrastructure adapter MUST be testable with its external dependency replaced at the boundary (e.g., a fake executor, a stub environment, a temp config file).
- **FR-020**: The app wiring MUST be testable by substituting fake infrastructure adapters, verifying the correct sequence of wiring calls without real side effects.

### Key Entities

- **Selection**: the set of directories and files the user wants to open (one session per directory, files opened with nvim in their parent directory's session).
- **RuntimeSnapshot**: a point-in-time view of the tmux environment consumed by planning — inside-tmux flag, server-running flag, and existing sessions (name → path). Produced by infrastructure, defined by domain.
- **Command / CommandPlan**: a single executable unit (program + arguments) and the ordered list of such units the tool executes. Defined by domain.
- **Configuration**: the user's declared project roots (depth 1 and depth 2), additional directories, and additional files. Defined by app, produced by infrastructure.
- **Layer**: the organizational unit of the codebase (domain / app / infrastructure) that owns responsibilities and defines or satisfies DTOs as described above.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of pre-existing tests pass unchanged after the refactor (behavior parity gate).
- **SC-002**: The domain test suite passes on a machine with no tmux, fzf, or zoxide installed and no `TMUX` environment variable set.
- **SC-003**: Static analysis confirms 100% of domain code imports nothing from app or infrastructure and performs no subprocess/environment/filesystem calls.
- **SC-004**: Every source unit has an unambiguous layer assignment verifiable by a single dependency-direction rule (no mixed-layer files).
- **SC-005**: Replacing an external interaction (e.g., swapping the picker tool or injecting a fake executor) requires no domain changes and no more than the corresponding app wiring line.
- **SC-006**: A reader can trace the interactive flow end-to-end (config → discovery → ranking → pick → classify → run) as a linear chain of infra/domain calls, with no business rule or raw external call embedded in the wiring.

## Assumptions

- The three layers map to distinct packages under the source tree (e.g., `domain`, `app`, `infrastructure`); exact package and file naming is a planning detail, not part of this spec.
- "run" means the plan-then-execute orchestration: it is a domain capability that receives a selection and a runtime snapshot and delegates execution to an injected executor (the real executor is an infrastructure adapter).
- The runtime snapshot is an explicit DTO; the domain never reads the `TMUX` environment variable, never probes for tmux, and never lists sessions itself — infrastructure assembles the snapshot and the domain consumes it.
- Both the interactive flow and the `switch` flow route through the same domain run capability; the two flows differ only in how the selection is produced.
- The configuration DTO is an app-level contract; the domain does not consume configuration directly, only the discovery output derived from it.
- Behavior parity is the top priority: this refactor adds no new features and removes no existing ones.
- The existing pure-module principle (behavior in small pure modules) is restated in terms of the domain layer: after the refactor, all pure business logic lives in domain, and all side effects live in infrastructure. The constitution's module-list section (Principle II) will be updated to reflect the layered structure as part of this feature.
- Testing strategy: domain tested directly with hand-built inputs; infrastructure tested with injected fakes/stubs at the adapter boundary; app tested by substituting fake adapters.