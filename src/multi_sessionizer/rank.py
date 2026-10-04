"""Legacy facade: re-exports the domain ranking capability (zero logic)."""

from __future__ import annotations

from .domain.rank import build_picker_list, parse_zoxide_scores, rank_dirs

__all__ = ["build_picker_list", "parse_zoxide_scores", "rank_dirs"]
