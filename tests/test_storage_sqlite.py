# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for SQLiteBackend — real SQLite file."""
import tempfile
from pathlib import Path

import pytest

from flyto_blueprint.storage.sqlite import SQLiteBackend


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_blueprints.db")


@pytest.fixture
def backend(db_path):
    return SQLiteBackend(db_path=db_path)


class TestSQLiteBackend:

    def test_save_and_load_one(self, backend):
        backend.save("bp1", {"id": "bp1", "name": "Test"})
        loaded = backend.load_one("bp1")
        assert loaded["id"] == "bp1"
        assert loaded["name"] == "Test"

    def test_load_one_not_found(self, backend):
        assert backend.load_one("nope") is None

    def test_load_all(self, backend):
        backend.save("a", {"id": "a"})
        backend.save("b", {"id": "b"})
        all_data = backend.load_all()
        assert len(all_data) == 2

    def test_update(self, backend):
        backend.save("bp1", {"id": "bp1", "score": 50})
        backend.update("bp1", {"score": 70})
        assert backend.load_one("bp1")["score"] == 70

    def test_update_nonexistent_is_noop(self, backend):
        backend.update("nope", {"score": 70})  # should not raise

    def test_delete(self, backend):
        backend.save("bp1", {"id": "bp1"})
        backend.delete("bp1")
        assert backend.load_one("bp1") is None

    def test_save_overwrite(self, backend):
        backend.save("bp1", {"id": "bp1", "v": 1})
        backend.save("bp1", {"id": "bp1", "v": 2})
        assert backend.load_one("bp1")["v"] == 2

    def test_atomic_update(self, backend):
        backend.save("bp1", {"id": "bp1", "score": 50})
        result = backend.atomic_update("bp1", lambda d: {**d, "score": 60})
        assert result["score"] == 60
        assert backend.load_one("bp1")["score"] == 60

    def test_atomic_update_abort(self, backend):
        backend.save("bp1", {"id": "bp1", "score": 50})
        result = backend.atomic_update("bp1", lambda d: None)
        assert result is None
        assert backend.load_one("bp1")["score"] == 50

    def test_atomic_update_not_found(self, backend):
        result = backend.atomic_update("nope", lambda d: d)
        assert result is None

    def test_persistence_across_instances(self, db_path):
        """Data persists when creating a new backend instance."""
        b1 = SQLiteBackend(db_path=db_path)
        b1.save("bp1", {"id": "bp1", "name": "Persist"})
        b2 = SQLiteBackend(db_path=db_path)
        loaded = b2.load_one("bp1")
        assert loaded["name"] == "Persist"
