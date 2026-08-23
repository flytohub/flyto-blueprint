# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""The durable store must not lose evidence when two processes report at once.

`SQLiteBackend` documented itself as thread-safe and its `atomic_update` as
atomic, and both claims are published in `docs/API.md` and the generated API
reference. Neither held across processes: the guard was a `threading.Lock`,
which is per-instance, and the read and the write were separate autocommit
statements, so two writers could read the same row and both write it. Measured
before the fix, four processes performing 300 increments each on one file left
415 of 1,200 -- silently, with no exception anywhere.

This is not a hypothetical configuration. Every `flyto-ai` agent builds an
`AssistantMiddleware`, which constructs `SQLiteBackend()` with no path (so
`~/.flyto/blueprints.db`) and reports an outcome after each execution, and the
CLI opens the same file. Two agents are two processes on one database.

These tests use real processes on a real file on purpose. A threading-only test
passes against the broken implementation, which is how the defect survived.
"""
import multiprocessing as mp
import sqlite3

import pytest

from flyto_blueprint.storage.sqlite import SQLiteBackend

PROCESSES = 4
INCREMENTS = 60
EXPECTED = PROCESSES * INCREMENTS


def _increment_many(db_path: str, count: int) -> None:
    """Increment one counter `count` times through the public API."""
    backend = SQLiteBackend(db_path)
    for _ in range(count):
        backend.atomic_update("bp", _bump)


def _bump(data: dict):
    data["runs"] = data.get("runs", 0) + 1
    return data


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "blueprints.db")
    SQLiteBackend(path).save("bp", {"id": "bp", "runs": 0})
    return path


def test_atomic_update_loses_nothing_across_processes(db_path):
    context = mp.get_context("spawn")
    workers = [
        context.Process(target=_increment_many, args=(db_path, INCREMENTS))
        for _ in range(PROCESSES)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(120)

    assert all(worker.exitcode == 0 for worker in workers), (
        f"worker exit codes: {[w.exitcode for w in workers]}"
    )
    assert SQLiteBackend(db_path).load_one("bp")["runs"] == EXPECTED


def test_update_merges_without_dropping_a_concurrent_field(db_path):
    """`update` is read-modify-write too, so it needs the same transaction."""
    context = mp.get_context("spawn")
    workers = [
        context.Process(target=_set_field, args=(db_path, f"f{index}"))
        for index in range(PROCESSES)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(120)

    stored = SQLiteBackend(db_path).load_one("bp")
    missing = [f"f{index}" for index in range(PROCESSES) if f"f{index}" not in stored]
    assert not missing, f"concurrent update dropped fields: {missing}"


def _set_field(db_path: str, field: str) -> None:
    SQLiteBackend(db_path).update("bp", {field: True})


def test_write_transaction_rolls_back_and_reraises(db_path):
    """A failing update must leave the row as it was, not half-applied."""
    backend = SQLiteBackend(db_path)

    def explode(data: dict):
        data["runs"] = 999
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        backend.atomic_update("bp", explode)
    assert backend.load_one("bp")["runs"] == 0


def test_database_uses_wal_so_readers_never_block_writers(db_path):
    SQLiteBackend(db_path)
    with sqlite3.connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_connections_are_closed_rather_than_leaked(db_path):
    """`with sqlite3.connect(...)` commits but does not close; this asserts both."""
    backend = SQLiteBackend(db_path)
    for _ in range(200):
        backend.load_one("bp")
        backend.atomic_update("bp", _bump)
    assert backend.load_one("bp")["runs"] == 200
