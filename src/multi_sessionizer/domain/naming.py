"""Session name generation (basename with dots replaced by underscores).

Pure string helper: ``os.path.basename`` never touches the filesystem.
"""

from __future__ import annotations

import os


def session_name(path: str) -> str:
    name = os.path.basename(path.rstrip("/"))
    return (name or "/").replace(".", "_")


def workspace_fallback_name(fingerprint_hex: str) -> str:
    """Deterministic fallback session name for a nameless workspace (R11)."""
    return f"msz-{fingerprint_hex[:12]}"
