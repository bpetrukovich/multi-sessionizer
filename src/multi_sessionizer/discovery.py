"""Legacy facade: re-exports the infrastructure discovery adapter (zero logic).

Also re-exposes ``os`` so tests keep monkeypatching ``discovery.os.scandir``.
"""

from __future__ import annotations

import os

from .infrastructure.discovery import collect_dirs

__all__ = ["collect_dirs", "os"]
