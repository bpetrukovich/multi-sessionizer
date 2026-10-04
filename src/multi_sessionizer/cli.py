"""Legacy facade: re-exports the infrastructure classifier (zero logic)."""

from __future__ import annotations

from .infrastructure.classifier import classify_args

__all__ = ["classify_args"]
