# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Tests for listing, ranking, relevance, and retired-hidden behavior."""
from conftest import make_workflow, make_workflow_alt


class TestListAndSearch:

    def test_builtins_always_present(self, engine):
        ids = [b["id"] for b in engine.list_blueprints()]
        assert "browser_scrape" in ids
        assert "api_get" in ids

    def test_learned_sorted_by_score_desc(self, engine):
        engine.learn_from_workflow(make_workflow(tag="low_score"), name="low")
        r2 = engine.learn_from_workflow(make_workflow_alt(), name="high")
        engine._blueprints[r2["data"]["id"]]["score"] = 90

        learned = [b for b in engine.list_blueprints() if b.get("source") == "learned"]
        scores = [b["score"] for b in learned]
        assert scores == sorted(scores, reverse=True)

    def test_search_returns_builtins(self, engine):
        results = engine.search("screenshot")
        ids = [b["id"] for b in results]
        assert "browser_screenshot" in ids

    def test_search_empty_returns_all(self, engine):
        assert len(engine.search("")) == len(engine.list_blueprints())

    def test_search_by_tag(self, engine):
        results = engine.search("api")
        ids = [b["id"] for b in results]
        assert "api_get" in ids

    def test_search_by_name(self, engine):
        results = engine.search("Login")
        ids = [b["id"] for b in results]
        assert "browser_login" in ids

    def test_search_no_match(self, engine):
        results = engine.search("xyznonexistent")
        assert len(results) == 0

    def test_summary_has_required_fields(self, engine):
        results = engine.list_blueprints()
        for bp in results:
            assert "id" in bp
            assert "name" in bp
            assert "description" in bp
            assert "tags" in bp
            assert "args" in bp

    def test_learned_summary_exposes_trust_and_community_confidence(self, engine):
        learned = engine.learn_from_workflow(
            make_workflow(tag="summary_trust"),
            name="summary_trust",
        )
        bp_id = learned["data"]["id"]
        engine.report_outcome(
            bp_id,
            success=True,
            execution_id="community-summary-1",
            evidence_tier="community",
        )

        summary = next(bp for bp in engine.list_blueprints() if bp["id"] == bp_id)

        assert summary["trust_tier"] == "community"
        assert summary["community_observations"] == 1
        assert summary["effective_score"] == summary["score"]

    def test_search_matches_repository_compatibility(self, engine):
        learned = engine.learn_from_execution(
            make_workflow(tag="repo_context"),
            name="generic_endpoint",
            compatibility={
                "repository": "flytohub/payments-api",
                "framework": "fastapi",
            },
        )

        results = engine.search("payments-api")

        assert learned["data"]["id"] in [bp["id"] for bp in results]

    def test_summary_exposes_evidence_card(self, engine):
        learned = engine.learn_from_workflow(
            make_workflow(tag="evidence_summary"),
            name="evidence_summary",
        )
        bp_id = learned["data"]["id"]
        engine.report_outcome(
            bp_id,
            success=True,
            execution_id="summary-evidence-1",
            evidence={
                "duration_ms": 42,
                "model_calls_used": 0,
                "planner_model_calls_used": 0,
                "model_call_scope": "planner",
                "selection_mode": "deterministic",
            },
        )

        summary = next(bp for bp in engine.list_blueprints() if bp["id"] == bp_id)

        assert summary["evidence_card"]["sample_count"] == 1
        assert summary["evidence_card"]["zero_planner_model_call_count"] == 1
        assert summary["evidence_card"]["zero_llm_reuse_count"] == 1

    def test_community_signal_influences_ranking_without_rewriting_score(self, engine):
        low = engine.learn_from_workflow(
            make_workflow(tag="community_low"),
            name="community_low",
        )
        high = engine.learn_from_workflow(
            make_workflow_alt(),
            name="community_high",
        )
        low_id = low["data"]["id"]
        high_id = high["data"]["id"]

        for index in range(20):
            engine.report_outcome(
                high_id,
                success=True,
                execution_id="community-rank-{}".format(index),
                evidence_tier="community",
            )

        learned = [bp for bp in engine.list_blueprints() if bp.get("source") == "learned"]
        ids = [bp["id"] for bp in learned]
        assert ids.index(high_id) < ids.index(low_id)
        assert engine._blueprints[high_id]["score"] == 50
