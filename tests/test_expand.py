# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for blueprint expansion: builtins, compose, missing args."""


class TestExpand:

    def test_builtin_produces_valid_workflow(self, engine):
        result = engine.expand("browser_scrape", {
            "url": "https://example.com", "extract_selector": "#data",
        })
        assert result["ok"] is True
        assert len(result["data"]["steps"]) >= 3
        assert "yaml" in result["data"]

    def test_not_found(self, engine):
        assert engine.expand("nonexistent_xyz", {})["ok"] is False

    def test_missing_required_args(self, engine):
        result = engine.expand("browser_scrape", {})
        assert result["ok"] is False
        assert "missing" in result["error"].lower()

    def test_api_get_headers(self, engine):
        r = engine.expand("api_get", {
            "url": "https://api.example.com", "headers": {"Auth": "Bearer tok"},
        })
        step = next(s for s in r["data"]["steps"] if s["id"] == "api_request")
        assert step["params"]["headers"] == {"Auth": "Bearer tok"}

    def test_api_post_body(self, engine):
        r = engine.expand("api_post", {
            "url": "https://x.com", "body": {"k": "v"},
        })
        step = next(s for s in r["data"]["steps"] if s["id"] == "api_request")
        assert step["params"]["body"] == {"k": "v"}

    def test_browser_scrape_extract_type(self, engine):
        r = engine.expand("browser_scrape", {
            "url": "https://x.com", "extract_selector": "#p", "extract_type": "html",
        })
        step = next(s for s in r["data"]["steps"] if s["id"] == "extract_data")
        assert step["params"]["extract_type"] == "html"

    def test_browser_scrape_list_multiple(self, engine):
        r = engine.expand("browser_scrape_list", {
            "url": "https://x.com", "extract_selector": ".i",
        })
        step = next(s for s in r["data"]["steps"] if s["id"] == "extract_list")
        assert step["params"]["multiple"] is True

    def test_browser_login_selectors(self, engine):
        r = engine.expand("browser_login", {
            "url": "https://x.com", "username": "u", "password": "p",
            "username_selector": "#u", "password_selector": "#p", "submit_selector": "#s",
        })
        step = next(s for s in r["data"]["steps"] if s["id"] == "login")
        assert step["params"]["username_selector"] == "#u"

    def test_browser_screenshot_full_page(self, engine):
        r = engine.expand("browser_screenshot", {"url": "https://x.com", "full_page": True})
        step = next(s for s in r["data"]["steps"] if s["id"] == "take_screenshot")
        assert step["params"]["full_page"] is True

    def test_skip_if_missing(self, engine):
        """Steps with skip_if_missing should be omitted when arg is absent."""
        r = engine.expand("browser_scrape", {
            "url": "https://x.com", "extract_selector": "#d",
        })
        # wait_content has skip_if_missing: [wait_selector]
        step_ids = [s["id"] for s in r["data"]["steps"]]
        assert "wait_content" not in step_ids

    def test_skip_if_missing_included_when_present(self, engine):
        r = engine.expand("browser_scrape", {
            "url": "https://x.com", "extract_selector": "#d", "wait_selector": ".loaded",
        })
        step_ids = [s["id"] for s in r["data"]["steps"]]
        assert "wait_content" in step_ids

    def test_edges_generated(self, engine):
        r = engine.expand("browser_scrape", {
            "url": "https://x.com", "extract_selector": "#d",
        })
        edges = r["data"]["edges"]
        assert len(edges) == len(r["data"]["steps"]) - 1

    def test_source_blueprint_id_on_learned(self, engine):
        from conftest import make_workflow
        engine.learn_from_workflow(make_workflow(tag="src_bp"), name="src_bp_test")
        r = engine.expand("src_bp_test", {
            "a": 1, "b": 2, "text": "x", "array": [], "tag": "y",
        })
        assert r["ok"] is True
        assert r["data"].get("source_blueprint_id") == "src_bp_test"
