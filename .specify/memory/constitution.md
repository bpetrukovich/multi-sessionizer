# multi-sessionizer Constitution

## Core Principles

### I. CLI Interface (MUST)

The tool is a command-line program. All functionality MUST be reachable via
subcommands and flags (interactive run without args, `switch`, `--help`,
`--version`). Text goes in via args, results and errors via stdout/stderr, and
exit codes MUST be meaningful (0 success, 1 bad path/config, 2 unknown
command).

Rationale: the value of the tool is fast, scriptable tmux session management
from the terminal.

### II. Pure, Test-First Modules (NON-NEGOTIABLE)

Behavior MUST live in small, single-responsibility, pure modules that are
unit-tested before integration. Pure business logic lives in the `domain`
layer (`naming`, `rank`, `plan`, `run`, `workspace`) and MUST stay free of
direct side effects. The `app` layer is a thin wiring layer that owns the
configuration DTO and the adapter contracts and contains no business rules.
All side effects (subprocess, filesystem, environment, stdin/stdout, terminal)
live in the `infrastructure` layer. External tools (tmux, fzf, zoxide, pgrep,
tmuxp) MUST be invoked only through infrastructure adapters. A behavior change
MUST come with tests written first (Red-Green-Refactor).

Rationale: tmux/zoxide/fzf interplay is hard to test end-to-end; pure modules
make the logic deterministic and verifiable.

### III. TOML Configuration

User configuration MUST live in `~/.config/multi-sessionizer/config.toml`
(overridable via `MULTI_SESSIONIZER_CONFIG`). There MUST be no built-in
personal defaults; a missing key means an empty list. Environment variables
and `~` MUST be expanded in all paths.

Rationale: hardcoded personal defaults caused silent skips in the original
bash version.

### IV. Bounded Performance

Directory discovery MUST touch only the configured depth levels and MUST NEVER
walk the whole tree. A regression test MUST guard this bound.

Rationale: the bash version's full-tree walk was a silent cost bug; the
`test_scan_cost_is_bounded_by_max_depth` test pins the guarantee.

### V. Simplicity (YAGNI)

Start simple. No speculative features, abstractions, or dependencies without a
concrete need. Every dependency (tmux, fzf, tmuxp, PyYAML, zoxide, uv,
pytest, ruff) MUST have a documented purpose.

Rationale: this is a small personal tool; complexity is its main cost.

## Additional Constraints

- Python 3.12+, managed with `uv`.
- Lint and format with `ruff`; tests with `pytest`.
- No new runtime dependencies without justification in the README dependency
  table.
- External tools MUST be invoked only through infrastructure adapters, never
  inline.
- Development MUST never risk the developer's live tmux server: `tmux
  kill-server` is forbidden on the default/current server; test sessions are
  killed by name (`tmux kill-session -t <name>`); anything that creates/kills
  tmux sessions runs under `scripts/tmux-sandbox.sh` (which pre-creates the
  socket directory and unsets `$TMUX`, because tmux 3.4 silently falls back to
  the default socket when `$TMUX_TMPDIR` points to a directory that does not
  exist).
- Config format stays TOML; session naming rules (dots → `_`, collision
  suffixes) are stable and MUST NOT change silently.
- All repository content (source code, comments, documentation, specs, and
  config files) MUST be written in English. Quoted user-provided input in specs
  MUST be translated to English. Non-English text MUST NOT be committed.

## Development Workflow

- Quality gates: `uv run pytest`, `uv run ruff check .`, and
  `uv run ruff format .` MUST pass before a change is done.
- Installation uses `uv tool install .` or `./scripts/install.sh`; the
  installed console script is the contract under test.
- A behavior change without a test is a failed change.

## Governance

This constitution supersedes informal conventions. Amendments MUST be recorded
as version bumps (MAJOR for breaking principle changes, MINOR for new
principles, PATCH for clarifications) with an updated `Last Amended` date and
a diff description. Reviews MUST verify compliance with the principles above.
When a principle and a convenience conflict, the principle wins.

**Version**: 1.2.2 | **Ratified**: 2026-10-04 | **Last Amended**: 2026-10-04 (PATCH: domain module list gains `workspace`; Principle V dependency examples lose `nvim` and gain `tmuxp`/`PyYAML` per the tmuxp config support plan)