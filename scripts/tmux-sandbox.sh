#!/usr/bin/env bash
# Run a command inside an isolated tmux server so it can never touch the
# live/default server (e.g. smoke-testing `multi-sessionizer switch`).
#
# Why this exists: tmux 3.4 silently ignores $TMUX_TMPDIR / $TMPDIR when the
# directory does not already exist, falling back to the default socket
# (/tmp/tmux-$UID/default). Combined with `$TMUX` still being set, a "sandboxed"
# command or a later `tmux kill-server` can target -- and destroy -- the
# developer's live tmux tree. This script pre-creates the socket directory and
# unsets $TMUX so the command and its cleanup are scoped to a throwaway server.
#
# Usage:
#   scripts/tmux-sandbox.sh [--zoxide-isolated] -- <command> [args...]
#
# Examples:
#   scripts/tmux-sandbox.sh -- ./scripts/smoke-switch.sh
#   scripts/tmux-sandbox.sh -- env -u TMUX .venv/bin/python -m pytest tests/test_runner.py
#
# On exit the throwaway server is killed (scoped to the sandbox socket only).
set -euo pipefail

ZO_ISOLATED=0
if [[ "${1:-}" == "--zoxide-isolated" ]]; then
    ZO_ISOLATED=1
    shift
fi

if [[ "${1:-}" != "--" ]]; then
    echo "usage: $0 [--zoxide-isolated] -- <command> [args...]" >&2
    exit 2
fi
shift

sandbox="$(mktemp -d /tmp/tmux-sandbox.XXXXXX)"
chmod 700 "$sandbox"

cleanup() {
    # TMUX unset + an existing TMUX_TMPDIR dir => targets ONLY the sandbox socket.
    env -u TMUX TMUX_TMPDIR="$sandbox" tmux -f /dev/null kill-server >/dev/null 2>&1 || true
    rm -rf "$sandbox"
}
trap cleanup EXIT

env_args=(-u TMUX TMUX_TMPDIR="$sandbox")
if [[ $ZO_ISOLATED -eq 1 ]]; then
    mkdir -p "$sandbox/zoxide"
    env_args+=(_ZO_DATA_DIR="$sandbox/zoxide")
fi

env "${env_args[@]}" "$@"
