# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Full lifecycle integration test: learn → expand → report → search."""
from flyto_blueprint import BlueprintEngine
from flyto_blueprint.storage.memory import MemoryBackend
from flyto_blueprint.storage.sqlite import SQLiteBackend


class TestFullLifecycleMemory:
    """End-to-end with MemoryBackend."""

    def test_learn_expand_report_search(self):
        engine = BlueprintEngine(storage=MemoryBackend())

        # 1. Learn a workflow
        wf = {
            "name": "Full Test",
            "description": "Integration test workflow",
            "steps": [
                {"id": "s1", "module": "browser.launch", "params": {"headless": True}},
                {"id": "s2", "module": "browser.goto", "params": {"url": "https://x.com"}},
                {"id": "s3", "module": "browser.click", "params": {"selector": "#btn"}},
            ],
        }
        learn_result = engine.learn_from_workflow(wf, name="integration_test", tags=["test"])
        assert learn_result["ok"] is True
        bp_id = learn_result["data"]["id"]

        # 2. Expand (requires args since params were abstracted)
        # url is needed by compose block browser_init; selector by the click step
        expand_result = engine.expand(bp_id, {"url": "https://y.com", "selector": "#btn"})
        assert expand_result["ok"] is True
        assert "yaml" in expand_result["data"]
        assert expand_result["data"].get("source_blueprint_id") == bp_id

        # 3. Report success (score starts at 50, +5 = 55)
        outcome = engine.report_outcome(bp_id, success=True)
        assert outcome["score"] == 55

    def test_learn_expand_report_search_verified(self):
        engine = BlueprintEngine(storage=MemoryBackend())

        wf = {
            "name": "Verified Test",
            "steps": [
                {"id": "s1", "module": "api.get", "params": {"url": "https://x.com"}},
                {"id": "s2", "module": "string.uppercase", "params": {"text": "hello"}},
                {"id": "s3", "module": "array.sort", "params": {"array": [3, 1]}},
            ],
        }
        learn_result = engine.learn_from_workflow(wf, name="verified_int", verified=True)
        bp_id = learn_result["data"]["id"]
        assert learn_result["data"]["score"] == 70

        engine.report_outcome(bp_id, success=True)
        assert engine._blueprints[bp_id]["score"] == 75

        # Search should find it
        results = engine.search("verified")
        ids = [b["id"] for b in results]
        assert bp_id in ids

    def test_dedup_and_boost_cycle(self):
        engine = BlueprintEngine(storage=MemoryBackend())

        wf = {
            "name": "Dedup Cycle",
            "steps": [
                {"id": "s1", "module": "math.add", "params": {"a": 1, "b": 2}},
                {"id": "s2", "module": "string.reverse", "params": {"text": "x"}},
                {"id": "s3", "module": "array.sort", "params": {"array": []}},
            ],
        }

        r1 = engine.learn_from_workflow(wf, name="original")
        assert "data" in r1
        bp_id = r1["data"]["id"]
        original_score = engine._blueprints[bp_id]["score"]

        # Same structure → dedup boost
        r2 = engine.learn_from_workflow(wf, name="duplicate")
        assert r2["action"] == "boosted_existing"
        assert engine._blueprints[bp_id]["score"] == original_score + 3


class TestFullLifecycleSQLite:
    """End-to-end with real SQLite."""

    def test_persist_and_reload(self, tmp_path):
        db = str(tmp_path / "test.db")

        # Create engine, learn a blueprint
        engine1 = BlueprintEngine(storage=SQLiteBackend(db_path=db))
        wf = {
            "name": "SQLite Test",
            "steps": [
                {"id": "s1", "module": "api.get", "params": {"url": "https://x.com"}},
                {"id": "s2", "module": "string.upper", "params": {"text": "hi"}},
                {"id": "s3", "module": "array.sort", "params": {"array": []}},
            ],
        }
        result = engine1.learn_from_workflow(wf, name="sqlite_test")
        bp_id = result["data"]["id"]

        # Create fresh engine from same DB
        engine2 = BlueprintEngine(storage=SQLiteBackend(db_path=db))
        ids = [b["id"] for b in engine2.list_blueprints()]
        assert bp_id in ids

        # Expand from reloaded engine
        expand = engine2.expand(bp_id, {"url": "https://y.com", "text": "hey", "array": [1]})
        assert expand["ok"] is True
