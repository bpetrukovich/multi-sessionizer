"""Unit tests for the sqlite ExternalStore adapter (FR-002/FR-003/FR-005/FR-009).

Store logic is exercised against an in-memory sqlite DB (``:memory:``); the WAL
mode and the concurrent stress test (SC-005) run against a temp-file DB so the
developer's real store is never touched.
"""

from __future__ import annotations

from threading import Thread

import pytest

from multi_sessionizer.app.ports import ExternalStoreError
from multi_sessionizer.domain.models import SessionEntry
from multi_sessionizer.infrastructure.external_store import SqliteExternalStore


def dir_entry(path):
    return SessionEntry(kind="directory", path=path)


def ws_entry(definition):
    return SessionEntry(kind="workspace", definition=definition)


def group_entry(name, members):
    return SessionEntry(kind="group", name=name, members=tuple(members))


WS = 'session_name: "ext-ws"\nwindows:\n  - shell_command: "echo hi"\n'


def test_schema_creation_lists_empty(tmp_path):
    store = SqliteExternalStore(":memory:")
    assert store.list_entries() == ()


def test_add_directory_returns_stored_entry():
    store = SqliteExternalStore(":memory:")
    result = store.add(dir_entry("/x/y"))
    assert result.ok is True
    assert result.entry == dir_entry("/x/y")


def test_add_workspace_returns_stored_entry():
    store = SqliteExternalStore(":memory:")
    result = store.add(ws_entry(WS))
    assert result.ok is True
    assert result.entry == ws_entry(WS)


def test_add_group_round_trips_members():
    store = SqliteExternalStore(":memory:")
    g = group_entry("ext-stack", [dir_entry("/p/b"), ws_entry(WS)])
    result = store.add(g)
    assert result.ok is True
    listed = store.list_entries()
    assert len(listed) == 1
    assert listed[0] == g


def test_add_directory_with_tags_round_trips():
    store = SqliteExternalStore(":memory:")
    entry = SessionEntry(kind="directory", path="/x/y", tags=("pp-1", "pp-2"))
    assert store.add(entry).ok is True
    assert store.list_entries() == (entry,)


def test_add_workspace_with_tags_round_trips():
    store = SqliteExternalStore(":memory:")
    entry = SessionEntry(kind="workspace", definition=WS, tags=("pp-000000",))
    assert store.add(entry).ok is True
    assert store.list_entries() == (entry,)


def test_add_group_with_tags_round_trips():
    store = SqliteExternalStore(":memory:")
    entry = SessionEntry(
        kind="group", name="ext-stack", tags=("pp-000000",), members=(dir_entry("/p/b"),)
    )
    assert store.add(entry).ok is True
    assert store.list_entries() == (entry,)


def test_legacy_schema_without_tags_column_is_migrated(tmp_path):
    import sqlite3

    db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE external_entries ("
        " id INTEGER PRIMARY KEY,"
        " kind TEXT NOT NULL,"
        " path TEXT, definition TEXT, name TEXT,"
        " UNIQUE (path) UNIQUE (definition) UNIQUE (name))"
    )
    conn.execute(
        "INSERT INTO external_entries (kind, path, definition, name) VALUES (?, ?, ?, ?)",
        ("directory", "/old/path", None, None),
    )
    conn.commit()
    conn.close()

    store = SqliteExternalStore(db)
    assert store.list_entries() == (SessionEntry(kind="directory", path="/old/path"),)
    assert store.add(SessionEntry(kind="directory", path="/new/path", tags=("t1",))).ok is True
    entries = store.list_entries()
    assert len(entries) == 2
    assert entries[1].tags == ("t1",)


@pytest.mark.parametrize(
    "entry", [dir_entry("/dup"), ws_entry(WS), group_entry("g", [dir_entry("/p/m")])]
)
def test_duplicate_add_rejected_for_each_kind(entry):
    store = SqliteExternalStore(":memory:")
    assert store.add(entry).ok is True
    second = store.add(entry)
    assert second.ok is False
    assert "already exists" in second.error
    assert len(store.list_entries()) == 1


def test_delete_success_removes_row():
    store = SqliteExternalStore(":memory:")
    store.add(dir_entry("/a"))
    result = store.delete("/a")
    assert result.ok is True
    assert store.list_entries() == ()


def test_delete_not_found_returns_error_and_unchanged():
    store = SqliteExternalStore(":memory:")
    store.add(dir_entry("/a"))
    result = store.delete("/nope")
    assert result.ok is False
    assert result.message == "No external entry with deletion key '/nope'."
    assert store.list_entries() == (dir_entry("/a"),)


def test_delete_ambiguous_removes_nothing():
    store = SqliteExternalStore(":memory:")
    ws1 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: one\n')
    ws2 = ws_entry('session_name: "shared"\nwindows:\n  - shell_command: two\n')
    store.add(ws1)
    store.add(ws2)
    result = store.delete("shared")
    assert result.ok is False
    assert "matches multiple entries" in result.message
    assert len(store.list_entries()) == 2


def test_list_entries_stable_order_by_id():
    store = SqliteExternalStore(":memory:")
    store.add(dir_entry("/z"))
    store.add(ws_entry(WS))
    store.add(dir_entry("/a"))
    kinds = [e.kind for e in store.list_entries()]
    assert kinds == ["directory", "workspace", "directory"]
    assert store.list_entries() == store.list_entries()


def test_parent_directory_created_if_missing(tmp_path):
    db = str(tmp_path / "does" / "not" / "exist" / "ext.db")
    store = SqliteExternalStore(db)
    assert store.add(dir_entry("/a")).ok is True
    assert (tmp_path / "does" / "not" / "exist" / "ext.db").is_file()


def test_wal_mode_enabled(tmp_path):
    import sqlite3

    db = str(tmp_path / "ext.db")
    store = SqliteExternalStore(db)
    store.add(dir_entry("/a"))
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_corrupt_store_raises_clear_error(tmp_path):
    db = str(tmp_path / "ext.db")
    db_path = tmp_path / "ext.db"
    db_path.write_text("not a sqlite database")
    store = SqliteExternalStore(db)
    with pytest.raises(ExternalStoreError):
        store.list_entries()


# --- concurrency stress (SC-005) ---------------------------------------------


def _run_threads(target, count=20):
    threads = [Thread(target=target, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_concurrent_same_path_adds_produce_no_duplicate(tmp_path):
    db = str(tmp_path / "ext.db")
    results = []
    errors = []

    def worker(_i):
        try:
            results.append(SqliteExternalStore(db).add(dir_entry("/base/shared")))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    _run_threads(worker)
    assert not errors
    assert sum(1 for r in results if r.ok) == 1
    assert [e.path for e in SqliteExternalStore(db).list_entries()] == ["/base/shared"]


def test_concurrent_unique_adds_never_torn_list(tmp_path):
    db = str(tmp_path / "ext.db")
    store = SqliteExternalStore(db)
    store.add(dir_entry("/base/a0"))
    n = 40
    errors = []

    def worker(i):
        try:
            s = SqliteExternalStore(db)
            s.add(dir_entry(f"/base/a{i + 1}"))
            s.list_entries()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    _run_threads(worker, n)
    assert not errors
    paths = [e.path for e in store.list_entries()]
    assert len(paths) == len(set(paths)) == n + 1


def test_concurrent_delete_is_atomic(tmp_path):
    db = str(tmp_path / "ext.db")
    store = SqliteExternalStore(db)
    store.add(dir_entry("/base/k"))
    for i in range(10):
        store.add(dir_entry(f"/base/o{i}"))
    errors = []

    def worker(_i):
        try:
            s = SqliteExternalStore(db)
            s.delete("/base/k")
            s.list_entries()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    _run_threads(worker, 10)
    assert not errors
    paths = [e.path for e in store.list_entries()]
    assert "/base/k" not in paths
    assert len(paths) == len(set(paths)) == 10
