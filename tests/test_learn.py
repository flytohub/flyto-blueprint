# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for learning, dedup, abstraction, and compose detection."""
from conftest import make_workflow, make_workflow_alt


class TestLearnFromWorkflow:

    def test_creates_with_score_50(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="score50")
        assert result["ok"] is True
        assert result["data"]["score"] == 50
        assert result["data"].get("use_count", 0) == 0

    def test_verified_gets_score_70(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="verified", verified=True)
        assert result["ok"] is True
        assert result["data"]["score"] == 70

    def test_rejects_under_3_steps(self, engine):
        short = {"steps": [
            {"id": "s1", "module": "math.add", "params": {"a": 1}},
            {"id": "s2", "module": "math.add", "params": {"b": 2}},
        ]}
        result = engine.learn_from_workflow(short, name="short")
        assert result["ok"] is False
        assert "simple" in result["error"].lower()

    def test_rejects_empty_steps(self, engine):
        result = engine.learn_from_workflow({"steps": []})
        assert result["ok"] is False

    def test_dedup_boosts_existing(self, engine):
        wf = make_workflow(tag="dedup_test")
        r1 = engine.learn_from_workflow(wf, name="dedup_orig")
        assert r1["ok"] is True
        assert "data" in r1

        r2 = engine.learn_from_workflow(wf, name="dedup_copy")
        assert r2["ok"] is True
        assert r2["action"] == "boosted_existing"

    def test_dedup_boost_adds_3(self, engine):
        wf = make_workflow(tag="boost_test")
        r1 = engine.learn_from_workflow(wf, name="boost_orig")
        bp_id = r1["data"]["id"]

        before = engine._blueprints[bp_id]["score"]
        engine.learn_from_workflow(wf, name="boost_dup")
        after = engine._blueprints[bp_id]["score"]
        assert after == before + 3

    def test_stores_fingerprint(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="fp_test")
        bp_id = result["data"]["id"]
        bp = engine._blueprints[bp_id]
        assert isinstance(bp["fingerprint"], str)
        assert len(bp["fingerprint"]) == 12

    def test_stores_all_scoring_fields(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="fields_test")
        bp_id = result["data"]["id"]
        bp = engine._blueprints[bp_id]
        assert bp["score"] == 50
        assert bp["use_count"] == 0
        assert bp["success_count"] == 0
        assert bp["fail_count"] == 0
        assert bp["last_used_at"] is None
        assert bp["retired"] is False

    def test_different_structure_creates_separate(self, engine):
        r1 = engine.learn_from_workflow(make_workflow(tag="unique_a"), name="struct_a")
        r2 = engine.learn_from_workflow(make_workflow_alt(), name="struct_b")
        assert "data" in r1
        assert "data" in r2

    def test_compose_detection_browser_init(self, engine):
        """browser.launch + browser.goto at start → compose: [browser_init]."""
        wf = {
            "name": "Compose Test",
            "steps": [
                {"id": "s1", "module": "browser.launch", "params": {"headless": False}},
                {"id": "s2", "module": "browser.goto", "params": {"url": "https://x.com"}},
                {"id": "s3", "module": "browser.click", "params": {"selector": "#btn"}},
            ],
        }
        result = engine.learn_from_workflow(wf, name="compose_test")
        assert result["ok"] is True
        bp = engine._blueprints[result["data"]["id"]]
        assert "browser_init" in bp.get("compose", [])
        # s1 and s2 should be removed from steps (handled by compose block)
        modules = [s["module"] for s in bp["steps"]]
        assert "browser.launch" not in modules
        assert "browser.goto" not in modules

    def test_auto_id_generation(self, engine):
        wf = make_workflow()
        result = engine.learn_from_workflow(wf)
        assert result["ok"] is True
        assert "data" in result
        assert result["data"]["id"]  # should have auto-generated ID
