"""Legacy facade: re-exports the infrastructure Runner adapter (zero logic).

Also re-exposes ``subprocess`` so tests keep monkeypatching
``runner.subprocess.run``.
"""

from __future__ import annotations

import subprocess

from .infrastructure.runner import Runner

__all__ = ["Runner", "subprocess"]
