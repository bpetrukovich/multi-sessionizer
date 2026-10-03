#!/usr/bin/env bash
# Rebuild and reinstall the multi-sessionizer console script into PATH.
#
# `uv tool upgrade` will NOT rebuild a local-path install when the version is
# unchanged (it installs a stale cached wheel), so we build a fresh wheel
# explicitly and force-install it.
set -euo pipefail

cd "$(dirname "$0")/.."

uv sync
uv build --wheel --no-build-logs
wheel=$(ls -t dist/multi_sessionizer-*.whl | head -n1)
uv tool install --force "$wheel"

echo "Installed: $wheel"