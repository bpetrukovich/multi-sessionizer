"""App-owned adapter contracts (FR-003/FR-006/FR-011, research R5).

``typing.Protocol`` (method-only, no ``@runtime_checkable``) gives structural
typing: any object with matching methods satisfies the port, which is exactly
what replaceability (US4) and fake injection in tests need. ``FlowDeps`` bundles
all adapters for the app flows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ..domain.models import RuntimeSnapshot, Selection, SessionEntry
from ..domain.run import CommandExecutor
from .configuration import Config


class ExternalStoreError(Exception):
    """Raised when the store is corrupt or unreadable (FR-016)."""


@dataclass(frozen=True)
class ExternalAddResult:
    ok: bool
    entry: SessionEntry | None = None  # stored entry on success
    error: str = ""  # duplicate / invalid message on failure


@dataclass(frozen=True)
class ExternalDeleteResult:
    ok: bool
    message: str = ""  # success / not-found / ambiguous text


class ExternalStore(Protocol):
    def add(self, entry: SessionEntry) -> ExternalAddResult: ...
    def delete(self, key: str) -> ExternalDeleteResult: ...
    def list_entries(self) -> tuple[SessionEntry, ...]: ...


class ConfigLoader(Protocol):
    def load(self) -> Config: ...
    def missing_dirs(self, cfg: Config) -> list[str]: ...


class CandidateDiscovery(Protocol):
    def collect_dirs(self, cfg: Config) -> list[str]: ...


class ZoxideScorer(Protocol):
    def scores(self) -> str: ...


class Picker(Protocol):
    def pick(self, items: list[str]) -> list[str]: ...


class SelectionClassifier(Protocol):
    def classify_args(self, argv: Sequence[str]) -> tuple[list[str], list[str]]: ...
    def classify_selection(self, lines: list[str]) -> Selection: ...


class EnvironmentProbe(Protocol):
    def snapshot(self) -> RuntimeSnapshot: ...


class MessageOutput(Protocol):
    def config_not_found(self, path: object) -> None: ...
    def missing_dirs(self, missing_dirs: list[str]) -> None: ...
    def workspace_problems(self, problems: list[str]) -> None: ...
    def error(self, msg: str) -> None: ...
    def external_added(self, label: str) -> None: ...
    def external_list(self, rows: list[tuple[str, str, str]]) -> None: ...
    def external_deleted(self, message: str) -> None: ...
    def external_empty(self) -> None: ...


@dataclass(frozen=True)
class FlowDeps:
    config_loader: ConfigLoader
    discovery: CandidateDiscovery
    scorer: ZoxideScorer
    picker: Picker
    classifier: SelectionClassifier
    probe: EnvironmentProbe
    executor: CommandExecutor
    messages: MessageOutput
    external_store: ExternalStore
