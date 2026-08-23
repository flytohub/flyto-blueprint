# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""SQLite storage backend for blueprints."""
import json
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from flyto_blueprint.storage.base import StorageBackend

_DEFAULT_DB_PATH = Path.home() / ".flyto" / "blueprints.db"
#: How long a writer waits for another writer's transaction before giving up.
#: Outcome reporting happens on the hot path of an agent run, so this is short
#: enough not to stall a caller and long enough to absorb a contended write.
_BUSY_TIMEOUT_SECONDS = 10.0


class SQLiteBackend(StorageBackend):
    """Persists blueprints in a local SQLite database.

    Safe across threads **and processes**. That distinction is the reason this
    class looks the way it does: the default database path is shared, and the
    host that uses it opens one per process. Every ``flyto-ai`` agent constructs
    an ``AssistantMiddleware``, which builds a ``SQLiteBackend()`` with no path
    (so: ``~/.flyto/blueprints.db``) and reports an outcome after each execution,
    and the CLI opens the same file. Two agents, or an MCP server plus one CLI
    invocation, are two processes writing one database.

    The previous implementation guarded read-modify-write with a
    ``threading.Lock`` and ran the read and the write as separate autocommit
    statements. A ``threading.Lock`` is per-instance, so it did nothing across
    processes and nothing across two backends in one process; and because the
    read took no write lock, two writers could both read the same row and both
    write, with the second silently discarding the first. Measured on four
    processes performing 300 ``atomic_update`` increments each: 415 of 1,200
    survived, with no error raised anywhere. What was being discarded is the
    execution evidence this package exists to accumulate.

    Two changes fix it, and both are properties of the database rather than of
    the object: WAL so a reader never blocks a writer, and ``BEGIN IMMEDIATE``
    so a read-modify-write takes its write lock *before* it reads. The
    ``threading.Lock`` stays as a cheap intra-process fast path -- it saves
    contended threads a round trip through SQLite's busy handler, and it is no
    longer what correctness rests on.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize SQLite backend, creating the database file if needed."""
        self._db_path = str(db_path) if db_path else str(_DEFAULT_DB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with cross-process settings applied.

        ``isolation_level=None`` turns off the driver's implicit transaction
        handling so this module can state its own boundaries; without it the
        ``BEGIN IMMEDIATE`` below would be issued inside a transaction sqlite3
        had already started for us.
        """
        conn = sqlite3.connect(
            self._db_path,
            timeout=_BUSY_TIMEOUT_SECONDS,
            isolation_level=None,
        )
        # WAL is a property of the file, so setting it here is idempotent and
        # affects every future connection from any process.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={int(_BUSY_TIMEOUT_SECONDS * 1000)}")
        return conn

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block as one exclusive read-modify-write transaction.

        ``BEGIN IMMEDIATE`` acquires the write lock up front, so a concurrent
        writer waits at the ``BEGIN`` instead of reading a value this block is
        about to replace. A deferred transaction would take the lock only at the
        first write, which is exactly the window that lost updates.
        """
        with self._lock, closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def _init_db(self) -> None:
        """Create the blueprints table if it does not exist."""
        with closing(self._connect()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS blueprints ("
                "  id TEXT PRIMARY KEY,"
                "  data TEXT NOT NULL"
                ")"
            )

    def load_all(self) -> List[dict]:
        """Load and deserialize all blueprints from the database."""
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT data FROM blueprints").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, blueprint_id: str, data: dict) -> None:
        """Serialize and upsert a blueprint row."""
        blob = json.dumps(data, ensure_ascii=False, default=str)
        with self._write_transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO blueprints (id, data) VALUES (?, ?)",
                (blueprint_id, blob),
            )

    def update(self, blueprint_id: str, fields: dict) -> None:
        """Merge *fields* into the stored JSON blob for *blueprint_id*."""
        with self._write_transaction() as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE id = ?", (blueprint_id,)
            ).fetchone()
            if row is None:
                return
            data = json.loads(row[0])
            data.update(fields)
            blob = json.dumps(data, ensure_ascii=False, default=str)
            conn.execute(
                "UPDATE blueprints SET data = ? WHERE id = ?", (blob, blueprint_id)
            )

    def load_one(self, blueprint_id: str) -> Optional[dict]:
        """Load a single blueprint by ID, or return None if not found."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE id = ?", (blueprint_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, blueprint_id: str) -> None:
        """Delete the blueprint row for *blueprint_id*."""
        with self._write_transaction() as conn:
            conn.execute("DELETE FROM blueprints WHERE id = ?", (blueprint_id,))

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        """Read-modify-write inside one exclusive transaction.

        Atomic against other threads *and* other processes. ``update_fn`` runs
        while the write lock is held, so it must not block on anything slow --
        it is expected to be pure bookkeeping on the blueprint dict.
        """
        with self._write_transaction() as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE id = ?", (blueprint_id,)
            ).fetchone()
            if row is None:
                return None
            data = json.loads(row[0])
            result = update_fn(data)
            if result is not None:
                blob = json.dumps(result, ensure_ascii=False, default=str)
                conn.execute(
                    "UPDATE blueprints SET data = ? WHERE id = ?",
                    (blob, blueprint_id),
                )
            return result
