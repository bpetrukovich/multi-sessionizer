"""App-owned configuration DTO (FR-011).

The higher layer defines the boundary contracts; infrastructure loads and
raises ``ConfigNotFoundError``. Missing keys mean empty tuples — no built-in
defaults. ``ConfigError`` carries the collected validation problems for a
structurally invalid ``sessions`` list or a removed config key (FR-002/FR-010).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..domain.models import SessionEntry


class ConfigNotFoundError(FileNotFoundError):
    """Raised when the configuration file does not exist."""


class ConfigError(Exception):
    """Raised for a removed config key or a structurally invalid ``sessions``.

    Carries one message per problem (FR-002/FR-010). The messages already use
    the CLI-contract wording and are reported verbatim via ``MessageOutput.error``.
    """

    def __init__(self, messages: Sequence[str]) -> None:
        self.messages: tuple[str, ...] = tuple(messages)
        super().__init__("\n".join(self.messages))


@dataclass(frozen=True)
class Config:
    project_roots_depth_1: tuple[str, ...] = ()
    project_roots_depth_2: tuple[str, ...] = ()
    sessions: tuple[SessionEntry, ...] = ()
