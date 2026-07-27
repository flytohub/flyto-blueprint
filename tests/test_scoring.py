# Copyright 2024 Flyto2
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

    def test_community_observation_requires_execution_id(self, engine):
        bp_id = self._create_blueprint(engine)

        result = engine.report_outcome(
            bp_id,
            success=True,
            evidence_tier="community",
        )

        assert result["ok"] is False
        assert "execution_id" in result["error"]

    def test_community_observation_does_not_change_trusted_score(self, engine):
        bp_id = self._create_blueprint(engine)

        result = engine.report_outcome(
            bp_id,
            success=True,
            execution_id="community-1",
            evidence_tier="community",
        )

        assert result["ok"] is True
        assert result["score"] == 50
        assert result["score_changed"] is False
        assert engine._blueprints[bp_id]["community_success_count"] == 1

    def test_verified_success_promotes_community_blueprint_locally(self, engine):
        bp_id = self._create_blueprint(engine)
        engine._blueprints[bp_id]["trust_tier"] = "community"

        result = engine.report_outcome(
            bp_id,
            success=True,
            execution_id="local-verified-1",
            evidence_tier="local_verified",
        )

        assert result["trust_tier"] == "local_verified"

    def test_unknown_evidence_tier_is_rejected(self, engine):
        bp_id = self._create_blueprint(engine)

        result = engine.report_outcome(
            bp_id,
            success=True,
            evidence_tier="self_claimed_super_trusted",
        )

        assert result["ok"] is False
        assert "Unknown evidence tier" in result["error"]

    def test_evidence_card_uses_observed_outcomes_and_wilson_bound(self, engine):
        bp_id = self._create_blueprint(engine)

        for index in range(20):
            engine.report_outcome(
                bp_id,
                success=True,
                execution_id="success-{}".format(index),
            )
        for index in range(3):
            result = engine.report_outcome(
                bp_id,
                success=False,
                execution_id="failure-{}".format(index),
            )

        card = result["evidence_card"]
        assert card["status"] == "measured"
        assert card["sample_count"] == 23
        assert card["success_count"] == 20
        assert card["failure_count"] == 3
        assert card["success_rate"] == round(20 / 23, 4)
        assert 0.65 < card["wilson_95_lower_bound"] < card["success_rate"]

    def test_evidence_card_measures_retries_assertions_and_planner_calls(self, engine):
        bp_id = self._create_blueprint(engine)
        samples = [
            (100, 2, 2, True, 0),
            (200, 2, 3, True, 1),
            (300, 2, 2, False, 0),
            (400, 2, 4, True, 1),
        ]

        for index, (duration, steps, attempts, asserted, model_calls) in enumerate(samples):
            result = engine.report_outcome(
                bp_id,
                success=asserted,
                execution_id="evidence-{}".format(index),
                evidence={
                    "duration_ms": duration,
                    "step_count": steps,
                    "total_attempts": attempts,
                    "assertion_passed": asserted,
                    "model_calls_used": model_calls,
                    "planner_model_calls_used": model_calls,
                    "model_call_scope": "planner",
                    "selection_mode": "deterministic" if model_calls == 0 else "model_selected",
                },
            )

        card = result["evidence_card"]
        assert card["detailed_sample_count"] == 4
        assert card["duration_ms_p50"] == 250
        assert card["duration_ms_p95"] == 385
        assert card["retry_run_count"] == 2
        assert card["retry_rate"] == 0.5
        assert card["assertion_pass_rate"] == 0.75
        assert card["planner_model_call_sample_count"] == 4
        assert card["zero_planner_model_call_count"] == 2
        assert card["zero_planner_model_call_rate"] == 0.5
        assert card["zero_llm_reuse_count"] == 2
        assert card["zero_llm_reuse_rate"] == 0.5

    def test_evidence_is_allowlisted_hashed_and_bounded(self, engine):
        bp_id = self._create_blueprint(engine)

        engine.report_outcome(
            bp_id,
            success=True,
            execution_id="private-runtime-id",
            evidence={
                "duration_ms": 120,
                "selection_mode": "deterministic",
                "model_calls_used": 0,
                "planner_model_calls_used": 0,
                "model_call_scope": "planner",
                "raw_prompt": "do not persist me",
                "api_key": "secret",
            },
        )

        sample = engine._blueprints[bp_id]["evidence_samples"][0]
        assert sample["execution_ref"].startswith("sha256:")
        assert "private-runtime-id" not in str(sample)
        assert sample["model_call_scope"] == "planner"
        assert sample["planner_model_calls_used"] == 0
        assert "raw_prompt" not in sample
        assert "api_key" not in sample

    def test_legacy_model_call_sample_is_not_treated_as_planner_scoped(self, engine):
        bp_id = self._create_blueprint(engine)

        result = engine.report_outcome(
            bp_id,
            success=True,
            execution_id="legacy-model-call-scope",
            evidence={"model_calls_used": 0},
        )

        card = result["evidence_card"]
        assert card["model_call_sample_count"] == 1
        assert card["planner_model_call_sample_count"] == 0
        assert card["zero_planner_model_call_count"] == 0
        assert card["zero_planner_model_call_rate"] is None

    def test_detailed_evidence_window_is_capped(self, engine):
        bp_id = self._create_blueprint(engine)

        for index in range(105):
            result = engine.report_outcome(
                bp_id,
                success=True,
                execution_id="bounded-{}".format(index),
                evidence={"duration_ms": index},
            )

        card = result["evidence_card"]
        assert card["sample_count"] == 105
        assert card["detailed_sample_count"] == 100
        assert len(engine._blueprints[bp_id]["evidence_samples"]) == 100

    def test_community_observation_cannot_add_trusted_evidence(self, engine):
        bp_id = self._create_blueprint(engine)

        result = engine.report_outcome(
            bp_id,
            success=True,
            execution_id="community-evidence",
            evidence_tier="community",
            evidence={"model_calls_used": 0, "duration_ms": 1},
        )

        assert result["evidence_card"]["sample_count"] == 0
        assert engine._blueprints[bp_id].get("evidence_samples", []) == []


class TestEffectiveQualityScore:

    def test_community_signal_is_capped_and_confidence_weighted(self):
        from flyto_blueprint.scoring import effective_quality_score

        blueprint = {
            "score": 50,
            "community_success_count": 1000,
            "community_fail_count": 0,
        }

        assert 50 < effective_quality_score(blueprint) <= 60

    def test_fewer_than_three_observations_do_not_affect_ranking(self):
        from flyto_blueprint.scoring import effective_quality_score

        blueprint = {
            "score": 50,
            "community_success_count": 2,
            "community_fail_count": 0,
        }

        assert effective_quality_score(blueprint) == 50


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
