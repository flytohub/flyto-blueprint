# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for +5/-10 scoring, caps, auto-retire, and execution_id dedup."""
from conftest import make_workflow


class TestReportOutcome:

    def _create_blueprint(self, engine, name="outcome"):
        result = engine.learn_from_workflow(make_workflow(), name=name)
        return result["data"]["id"]

    def test_success_adds_5(self, engine):
        bp_id = self._create_blueprint(engine)
        r = engine.report_outcome(bp_id, success=True)
        assert r["score"] == 55

    def test_failure_subtracts_10(self, engine):
        bp_id = self._create_blueprint(engine)
        r = engine.report_outcome(bp_id, success=False)
        assert r["score"] == 40

    def test_multiple_successes(self, engine):
        bp_id = self._create_blueprint(engine)
        engine.report_outcome(bp_id, success=True)   # 55
        engine.report_outcome(bp_id, success=True)   # 60
        r = engine.report_outcome(bp_id, success=True)  # 65
        assert r["score"] == 65

    def test_score_capped_at_100(self, engine):
        bp_id = self._create_blueprint(engine)
        engine._blueprints[bp_id]["score"] = 98
        r = engine.report_outcome(bp_id, success=True)
        assert r["score"] == 100

    def test_score_floored_at_0(self, engine):
        bp_id = self._create_blueprint(engine)
        engine._blueprints[bp_id]["score"] = 5
        r = engine.report_outcome(bp_id, success=False)
        assert r["score"] == 0

    def test_auto_retire_below_10(self, engine):
        bp_id = self._create_blueprint(engine)
        engine._blueprints[bp_id]["score"] = 15
        r = engine.report_outcome(bp_id, success=False)
        assert r["score"] == 5
        assert r["retired"] is True

    def test_retired_hidden_from_list(self, engine):
        bp_id = self._create_blueprint(engine)
        engine._blueprints[bp_id]["score"] = 5
        engine.report_outcome(bp_id, success=False)
        ids = [b["id"] for b in engine.list_blueprints()]
        assert bp_id not in ids

    def test_retired_hidden_from_search(self, engine):
        bp_id = self._create_blueprint(engine, name="retire_search")
        engine._blueprints[bp_id]["score"] = 5
        engine.report_outcome(bp_id, success=False)
        ids = [b["id"] for b in engine.search("retire_search")]
        assert bp_id not in ids

    def test_not_found(self, engine):
        r = engine.report_outcome("nonexistent_xyz", success=True)
        assert r["ok"] is False

    def test_success_count_tracks(self, engine):
        bp_id = self._create_blueprint(engine)
        engine.report_outcome(bp_id, success=True)
        engine.report_outcome(bp_id, success=True)
        bp = engine._blueprints[bp_id]
        assert bp["success_count"] == 2
        assert bp["fail_count"] == 0

    def test_fail_count_tracks(self, engine):
        bp_id = self._create_blueprint(engine)
        engine.report_outcome(bp_id, success=False)
        engine.report_outcome(bp_id, success=False)
        bp = engine._blueprints[bp_id]
        assert bp["fail_count"] == 2

    def test_mixed_outcomes(self, engine):
        bp_id = self._create_blueprint(engine)
        engine.report_outcome(bp_id, success=True)   # 55
        engine.report_outcome(bp_id, success=True)   # 60
        engine.report_outcome(bp_id, success=False)   # 50
        bp = engine._blueprints[bp_id]
        assert bp["score"] == 50
        assert bp["success_count"] == 2
        assert bp["fail_count"] == 1

    def test_execution_id_dedup(self, engine):
        bp_id = self._create_blueprint(engine)
        r1 = engine.report_outcome(bp_id, success=True, execution_id="exec_1")
        assert r1["score"] == 55
        r2 = engine.report_outcome(bp_id, success=True, execution_id="exec_1")
        assert r2.get("skipped") == "already_reported"
        # Score should NOT have changed
        assert engine._blueprints[bp_id]["score"] == 55


class TestRecordUse:

    def test_count_increments(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="use_count")
        bp_id = result["data"]["id"]
        assert engine._blueprints[bp_id]["use_count"] == 0
        from flyto_blueprint.scoring import record_use
        record_use(bp_id, engine._blueprints)
        assert engine._blueprints[bp_id]["use_count"] == 1

    def test_score_unchanged_after_many_uses(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="use_score")
        bp_id = result["data"]["id"]
        original = engine._blueprints[bp_id]["score"]
        from flyto_blueprint.scoring import record_use
        for _ in range(20):
            record_use(bp_id, engine._blueprints)
        assert engine._blueprints[bp_id]["score"] == original

    def test_last_used_at_set(self, engine):
        result = engine.learn_from_workflow(make_workflow(), name="use_ts")
        bp_id = result["data"]["id"]
        assert engine._blueprints[bp_id]["last_used_at"] is None
        from flyto_blueprint.scoring import record_use
        record_use(bp_id, engine._blueprints)
        assert engine._blueprints[bp_id]["last_used_at"] is not None
