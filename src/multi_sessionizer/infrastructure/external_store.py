"""ExternalStore adapter: persistent, concurrent-safe sqlite store (FR-002/FR-003).

The store lives at ``~/.local/state/multi-sessionizer/external.db`` (XDG state),
overridable via ``MULTI_SESSIONIZER_STORE``; the parent directory is created if
missing. WAL mode + one transaction per add/delete give concurrent-safe,
torn-free results (SC-005); sqlite's file-level locking serializes concurrent
processes. The user's config file is never read for external decisions and never
written (FR-001), and the store never runs or kills tmux (FR-014).

Group entries are stored as a serialized YAML blob in ``definition`` (with the
group name in ``name``) so their members round-trip; the given schema has no
separate members column. A corrupt or unreadable store raises the app-owned
``ExternalStoreError`` rather than crashing (FR-016).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import yaml

from ..app.ports import ExternalAddResult, ExternalDeleteResult, ExternalStoreError
from ..domain.external import deletion_key, resolve_delete
from ..domain.models import SessionEntry
from ..domain.session_entries import classify_sessions

DEFAULT_STORE_PATH = Path.home() / ".local" / "state" / "multi-sessionizer" / "external.db"
ENV_STORE_PATH = "MULTI_SESSIONIZER_STORE"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_entries (
    id         INTEGER PRIMARY KEY,
    kind       TEXT NOT NULL CHECK (kind IN ('directory', 'workspace', 'group')),
    path       TEXT,
    definition TEXT,
    name       TEXT,
    UNIQUE (path) UNIQUE (definition) UNIQUE (name)
);
"""


def store_path() -> Path:
    """Resolve the store path honouring the ``MULTI_SESSIONIZER_STORE`` override."""
    override = os.environ.get(ENV_STORE_PATH)
    if override:
        return Path(override).expanduser()
    return DEFAULT_STORE_PATH


def _normalize(entry: SessionEntry) -> SessionEntry:
    """Realpath/expand directory paths; keep workspace definitions verbatim."""
    if entry.kind == "directory":
        expanded = os.path.expanduser(os.path.expandvars(entry.path))
        return SessionEntry(kind="directory", path=os.path.realpath(expanded))
    if entry.kind == "group":
        return SessionEntry(
            kind="group",
            name=entry.name,
            members=tuple(_normalize(m) for m in entry.members),
        )
    return entry


def _serialize_group(entry: SessionEntry) -> str:
    sessions = []
    for member in entry.members:
        sessions.append(member.path if member.kind == "directory" else member.definition)
    return yaml.safe_dump({"name": entry.name, "sessions": sessions})


def _reconstruct_group(name: str, definition: str) -> SessionEntry:
    data = yaml.safe_load(definition)
    entries, problems = classify_sessions([data])
    if problems or len(entries) != 1 or entries[0].kind != "group":
        raise ExternalStoreError(f"Corrupt external group entry '{name}'.")
    return entries[0]


class SqliteExternalStore:
    """Object adapter satisfying the app ``ExternalStore`` port."""

    def __init__(self, db: str | Path | None = None):
        self._path = str(db) if db is not None else str(store_path())
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            parent = os.path.dirname(self._path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            self._conn = sqlite3.connect(self._path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_SCHEMA)
        return self._conn

    def _run(self, fn):
        with self._connect() as conn:
            return fn(conn)

    def add(self, entry: SessionEntry) -> ExternalAddResult:
        stored = _normalize(entry)
        if stored.kind == "group":
            definition = _serialize_group(stored)
            path, name = None, stored.name
        elif stored.kind == "workspace":
            definition, path, name = stored.definition, None, None
        else:
            path, definition, name = stored.path, None, None
        try:
            self._run(
                lambda conn: conn.execute(
                    "INSERT INTO external_entries (kind, path, definition, name)"
                    " VALUES (?, ?, ?, ?)",
                    (stored.kind, path, definition, name),
                )
            )
        except sqlite3.IntegrityError:
            return ExternalAddResult(
                ok=False, error=f"External entry already exists: {deletion_key(stored)}."
            )
        except sqlite3.DatabaseError as exc:
            raise ExternalStoreError(str(exc)) from exc
        return ExternalAddResult(ok=True, entry=stored)

    def delete(self, key: str) -> ExternalDeleteResult:
        def _do(conn):
            rows = self._rows(conn)
            entries = [self._row_to_entry(row) for row in rows]
            matches, problems = resolve_delete(entries, key)
            if len(matches) != 1:
                return ExternalDeleteResult(ok=False, message=problems[0] if problems else "")
            row = self._find_row(rows, matches[0])
            if row is None:
                return ExternalDeleteResult(
                    ok=False, message=f"No external entry with deletion key '{key}'."
                )
            conn.execute("DELETE FROM external_entries WHERE id = ?", (row[0],))
            return ExternalDeleteResult(ok=True, message=f"Deleted external entry '{key}'.")

        try:
            return self._run(_do)
        except sqlite3.DatabaseError as exc:
            raise ExternalStoreError(str(exc)) from exc

    def list_entries(self) -> tuple[SessionEntry, ...]:
        try:
            conn = self._connect()
            rows = self._rows(conn)
        except sqlite3.DatabaseError as exc:
            raise ExternalStoreError(str(exc)) from exc
        return tuple(self._row_to_entry(row) for row in rows)

    @staticmethod
    def _rows(conn):
        return conn.execute(
            "SELECT id, kind, path, definition, name FROM external_entries ORDER BY id"
        ).fetchall()

    @staticmethod
    def _row_to_entry(row) -> SessionEntry:
        _, kind, path, definition, name = row
        if kind == "group":
            return _reconstruct_group(name, definition)
        if kind == "workspace":
            return SessionEntry(kind="workspace", definition=definition)
        return SessionEntry(kind="directory", path=path)

    @staticmethod
    def _find_row(rows, entry: SessionEntry):
        for row in rows:
            _, kind, path, definition, name = row
            if kind == "group" and name == entry.name:
                return row
            if kind == "workspace" and definition == entry.definition:
                return row
            if kind == "directory" and path == entry.path:
                return row
        return None
