# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""SQLite storage backend for blueprints."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

from flyto_blueprint.storage.base import StorageBackend

_DEFAULT_DB_PATH = Path.home() / ".flyto" / "blueprints.db"


class SQLiteBackend(StorageBackend):
    """Persists blueprints in a local SQLite database.

    Thread-safe via a threading lock around writes.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = str(db_path) if db_path else str(_DEFAULT_DB_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS blueprints ("
                "  id TEXT PRIMARY KEY,"
                "  data TEXT NOT NULL"
                ")"
            )
            conn.commit()

    def load_all(self) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data FROM blueprints").fetchall()
        return [json.loads(row[0]) for row in rows]

    def save(self, blueprint_id: str, data: dict) -> None:
        blob = json.dumps(data, ensure_ascii=False, default=str)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO blueprints (id, data) VALUES (?, ?)",
                (blueprint_id, blob),
            )
            conn.commit()

    def update(self, blueprint_id: str, fields: dict) -> None:
        with self._lock, self._connect() as conn:
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
            conn.commit()

    def load_one(self, blueprint_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM blueprints WHERE id = ?", (blueprint_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, blueprint_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM blueprints WHERE id = ?", (blueprint_id,))
            conn.commit()

    def atomic_update(
        self,
        blueprint_id: str,
        update_fn: Callable[[dict], Optional[dict]],
    ) -> Optional[dict]:
        with self._lock, self._connect() as conn:
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
                conn.commit()
            return result
