# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for MemoryBackend."""
from flyto_blueprint.storage.memory import MemoryBackend


class TestMemoryBackend:

    def test_save_and_load_one(self):
        backend = MemoryBackend()
        backend.save("bp1", {"id": "bp1", "name": "Test"})
        loaded = backend.load_one("bp1")
        assert loaded["id"] == "bp1"
        assert loaded["name"] == "Test"

    def test_load_one_not_found(self):
        backend = MemoryBackend()
        assert backend.load_one("nope") is None

    def test_load_all(self):
        backend = MemoryBackend()
        backend.save("a", {"id": "a"})
        backend.save("b", {"id": "b"})
        all_data = backend.load_all()
        assert len(all_data) == 2

    def test_update(self):
        backend = MemoryBackend()
        backend.save("bp1", {"id": "bp1", "score": 50})
        backend.update("bp1", {"score": 70})
        assert backend.load_one("bp1")["score"] == 70

    def test_delete(self):
        backend = MemoryBackend()
        backend.save("bp1", {"id": "bp1"})
        backend.delete("bp1")
        assert backend.load_one("bp1") is None

    def test_atomic_update(self):
        backend = MemoryBackend()
        backend.save("bp1", {"id": "bp1", "score": 50})
        result = backend.atomic_update("bp1", lambda d: {**d, "score": 60})
        assert result["score"] == 60
        assert backend.load_one("bp1")["score"] == 60

    def test_atomic_update_abort(self):
        backend = MemoryBackend()
        backend.save("bp1", {"id": "bp1", "score": 50})
        result = backend.atomic_update("bp1", lambda d: None)
        assert result is None
        assert backend.load_one("bp1")["score"] == 50

    def test_atomic_update_not_found(self):
        backend = MemoryBackend()
        result = backend.atomic_update("nope", lambda d: {**d, "x": 1})
        assert result is None

    def test_isolation_from_mutations(self):
        """Saved data should be isolated from external mutations."""
        backend = MemoryBackend()
        data = {"id": "bp1", "tags": ["a"]}
        backend.save("bp1", data)
        data["tags"].append("b")  # mutate original
        loaded = backend.load_one("bp1")
        assert loaded["tags"] == ["a"]  # should not be affected
