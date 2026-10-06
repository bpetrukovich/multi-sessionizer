"""Unified picker-line tags and label rendering (pure string helpers).

Every picker line is ``<tag>* <label>``: the structural tags (``tmuxp``,
``group``, ``external``) and any user-supplied tags all render as ``[tag]``
prefixes through the single ``render_picker_line`` interface. ``parse_tags``
validates a ``tags`` value (dedup, no whitespace/brackets). Purely functional:
no process spawning, filesystem, or environment access.
"""

from __future__ import annotations

from collections.abc import Sequence


def render_picker_line(tags: Sequence[str], label: str) -> str:
    """Join ``[tag]`` prefixes with a label into one picker line."""
    prefix = "".join(f"[{tag}] " for tag in tags)
    return f"{prefix}{label}"


def parse_tags(value: object) -> tuple[tuple[str, ...], str | None]:
    """Validate a ``tags`` value; returns (tags, problem) with one empty/None.

    ``None`` yields no tags. A valid list yields deduplicated, order-preserving
    non-empty tags without whitespace or brackets; otherwise a problem string.
    """
    if value is None:
        return (), None
    if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
        return (), "The 'tags' key must be a list of strings."
    cleaned: list[str] = []
    for tag in value:
        tag = tag.strip()
        if not tag or any(ch.isspace() for ch in tag) or "[" in tag or "]" in tag:
            return (), (
                f"Invalid tag '{tag}': tags must be non-empty and free of whitespace and brackets."
            )
        if tag not in cleaned:
            cleaned.append(tag)
    return tuple(cleaned), None
