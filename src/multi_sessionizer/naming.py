"""Legacy facade: re-exports the domain naming capability (zero logic)."""

from __future__ import annotations

from .domain.naming import session_name

__all__ = ["session_name"]
