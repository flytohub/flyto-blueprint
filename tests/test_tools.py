# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Tests for Blueprint MCP declaration safety and completeness."""
from flyto_blueprint.tools import get_blueprint_tools


def test_blueprint_tool_inventory_includes_portable_exchange():
    tools = get_blueprint_tools()
    names = [tool["name"] for tool in tools]

    assert names == [
        "list_blueprints",
        "use_blueprint",
        "save_as_blueprint",
        "report_blueprint_outcome",
        "export_blueprint",
        "import_blueprint",
    ]


def test_model_facing_export_never_accepts_signing_keys():
    export_tool = next(
        tool for tool in get_blueprint_tools()
        if tool["name"] == "export_blueprint"
    )

    assert "signing_key" not in export_tool["inputSchema"]["properties"]
