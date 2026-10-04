"""Legacy facade: re-exports the domain planning capability (zero logic).

Exposes ``Command`` and ``plan`` (= the legacy wrapper ``plan_legacy``) plus
``plan_legacy`` so the existing ``plan(...)`` calls stay byte-identical.
"""

from __future__ import annotations

from .domain.models import Command
from .domain.plan import plan_legacy

plan = plan_legacy

__all__ = ["Command", "plan", "plan_legacy"]
