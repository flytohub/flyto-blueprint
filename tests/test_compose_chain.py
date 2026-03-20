# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for compose_chain — Phase 2 of factory v2 pipeline."""

import pytest

from flyto_blueprint.compose import compose_chain


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blocks():
    return {}


@pytest.fixture
def blueprints():
    return {
        "string_split": {
            "id": "string_split",
            "name": "Split Text",
            "args": {"text": {"required": True}, "delimiter": {"required": False}},
            "compose": [],
            "connections": {"output_field": "data.result"},
            "steps": [
                {
                    "id": "split_text",
                    "module": "string.split",
                    "label": "Split text",
                    "params": {"text": "{{text}}", "delimiter": "{{delimiter}}"},
                },
            ],
        },
        "foreach_loop": {
            "id": "foreach_loop",
            "name": "Loop Over Items",
            "args": {
                "items": {"required": True},
                "module": {"required": True},
                "params": {"required": False},
            },
            "compose": [],
            "connections": {"output_field": "data.result"},
            "steps": [
                {
                    "id": "loop",
                    "module": "flow.foreach",
                    "label": "Loop",
                    "params": {"items": "{{items}}", "module": "{{module}}"},
                },
            ],
        },
        "qrcode_generate": {
            "id": "qrcode_generate",
            "name": "Generate QR Code",
            "args": {"content": {"required": True}, "output_path": {"required": False}},
            "compose": [],
            "connections": {"output_field": "data.result"},
            "steps": [
                {
                    "id": "generate_qr",
                    "module": "image.qrcode_generate",
                    "label": "Generate QR",
                    "params": {"content": "{{content}}"},
                },
            ],
        },
        "notify_slack": {
            "id": "notify_slack",
            "name": "Send Slack",
            "args": {"webhook_url": {"required": True}, "text": {"required": True}},
            "compose": [],
            "connections": {"output_field": "data.message_id"},
            "steps": [
                {
                    "id": "send_message",
                    "module": "notification.slack.send_message",
                    "label": "Send Slack",
                    "params": {"webhook_url": "{{webhook_url}}", "text": "{{text}}"},
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestComposeChain:

    def test_single_blueprint(self, blueprints, blocks):
        result = compose_chain(
            blueprint_ids=["string_split"],
            args={"string_split": {"text": "a,b,c", "delimiter": ","}},
            blueprints=blueprints,
            blocks=blocks,
        )
        assert result["ok"] is True
        assert len(result["data"]["steps"]) == 1
        assert result["data"]["steps"][0]["module"] == "string.split"
        assert result["data"]["steps"][0]["params"]["text"] == "a,b,c"

    def test_two_blueprints_chained(self, blueprints, blocks):
        result = compose_chain(
            blueprint_ids=["string_split", "notify_slack"],
            args={
                "string_split": {"text": "hello\nworld", "delimiter": "\n"},
                "notify_slack": {"webhook_url": "https://hooks.slack.com/x", "text": "done"},
            },
            blueprints=blueprints,
            blocks=blocks,
        )
        assert result["ok"] is True
        data = result["data"]
        assert len(data["steps"]) == 2
        # Cross-blueprint edge should exist
        edges = data["edges"]
        cross_edges = [e for e in edges if e["source"] == "split_text" and e["target"] == "send_message"]
        assert len(cross_edges) == 1

    def test_three_blueprints_qrcode_pipeline(self, blueprints, blocks):
        """Simulates: split text → loop → generate QR code."""
        result = compose_chain(
            blueprint_ids=["string_split", "foreach_loop", "qrcode_generate"],
            args={
                "string_split": {"text": "url1\nurl2"},
                "foreach_loop": {"items": "${steps.split_text.data.result}", "module": "image.qrcode_generate"},
                "qrcode_generate": {"content": "test"},
            },
            blueprints=blueprints,
            blocks=blocks,
        )
        assert result["ok"] is True
        assert len(result["data"]["steps"]) == 3

    def test_deconflict_step_ids(self, blocks):
        """Two blueprints with same step ID should be deconflicted."""
        bps = {
            "bp_a": {
                "id": "bp_a",
                "args": {},
                "compose": [],
                "steps": [{"id": "step1", "module": "a.do", "label": "A"}],
            },
            "bp_b": {
                "id": "bp_b",
                "args": {},
                "compose": [],
                "steps": [{"id": "step1", "module": "b.do", "label": "B"}],
            },
        }
        result = compose_chain(
            blueprint_ids=["bp_a", "bp_b"],
            args={},
            blueprints=bps,
            blocks=blocks,
        )
        assert result["ok"] is True
        ids = [s["id"] for s in result["data"]["steps"]]
        assert len(set(ids)) == 2  # No duplicates
        assert "step1" in ids
        assert any("bp1_" in sid for sid in ids)

    def test_missing_blueprint_returns_error(self, blueprints, blocks):
        result = compose_chain(
            blueprint_ids=["nonexistent"],
            args={},
            blueprints=blueprints,
            blocks=blocks,
        )
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_empty_ids_returns_error(self, blueprints, blocks):
        result = compose_chain(
            blueprint_ids=[],
            args={},
            blueprints=blueprints,
            blocks=blocks,
        )
        assert result["ok"] is False

    def test_cross_blueprint_wiring(self, blocks):
        """Unresolved {{input}} in second blueprint should wire to first blueprint's output.

        Only non-optional args get wired — optional args are stripped instead.
        """
        bps = {
            "producer": {
                "id": "producer",
                "args": {},
                "compose": [],
                "connections": {"output_field": "data.items"},
                "steps": [{"id": "produce", "module": "data.get", "label": "Produce", "params": {}}],
            },
            "consumer": {
                "id": "consumer",
                "args": {"input": {"required": False}},
                "compose": [],
                "steps": [
                    {
                        "id": "consume",
                        "module": "data.process",
                        "label": "Consume",
                        "params": {"data": "{{input}}"},
                    },
                ],
            },
        }

        # input is optional → should be stripped, not wired
        result = compose_chain(
            blueprint_ids=["producer", "consumer"],
            args={"consumer": {}},
            blueprints=bps,
            blocks=blocks,
        )
        assert result["ok"] is True
        consume_step = result["data"]["steps"][1]
        assert "data" not in consume_step.get("params", {}), \
            "Optional arg {{input}} should be stripped, not wired"

        # Now make input NOT optional and NOT provided → should be wired
        bps["consumer"]["args"]["input"]["required"] = True
        result = compose_chain(
            blueprint_ids=["producer", "consumer"],
            args={"consumer": {}},  # Don't provide 'input' → expand will fail (required)
            blueprints=bps,
            blocks=blocks,
        )
        # expand_blueprint fails on missing required arg
        assert result["ok"] is False

        # Provide empty dict so expand passes, but {{input}} stays unresolved → wired
        bps["consumer"]["args"] = {}  # No declared args at all
        bps["consumer"]["steps"][0]["params"]["data"] = "{{input}}"
        result = compose_chain(
            blueprint_ids=["producer", "consumer"],
            args={"consumer": {}},
            blueprints=bps,
            blocks=blocks,
        )
        assert result["ok"] is True
        consume_step = result["data"]["steps"][1]
        assert "${steps.produce.data.items}" in consume_step["params"]["data"]
