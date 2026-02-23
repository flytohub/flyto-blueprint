# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for listing, ranking, relevance, and retired-hidden behavior."""
from conftest import make_workflow, make_workflow_alt


class TestListAndSearch:

    def test_builtins_always_present(self, engine):
        ids = [b["id"] for b in engine.list_blueprints()]
        assert "browser_scrape" in ids
        assert "api_get" in ids

    def test_learned_sorted_by_score_desc(self, engine):
        r1 = engine.learn_from_workflow(make_workflow(tag="low_score"), name="low")
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
