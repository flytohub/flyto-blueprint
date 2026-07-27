# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""MCP tool definitions for blueprint operations."""
from typing import List

LIST_BLUEPRINTS_TOOL = {
    "name": "list_blueprints",
    "description": (
        "List available workflow blueprints (pre-built patterns). "
        "Call this FIRST to check if a blueprint matches the user's request "
        "before building a workflow from scratch."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Optional search query to filter blueprints by name, description, or tags",
            }
        },
    },
}

USE_BLUEPRINT_TOOL = {
    "name": "use_blueprint",
    "description": (
        "Expand a workflow blueprint with provided arguments. "
        "Returns a complete workflow YAML ready to use. "
        "Call inspect_page() first to get real selectors, "
        "then call this with the blueprint ID and args."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "blueprint_id": {
                "type": "string",
                "description": "Blueprint ID (from list_blueprints)",
            },
            "args": {
                "type": "object",
                "description": "Arguments to fill into the blueprint",
            },
        },
        "required": ["blueprint_id", "args"],
    },
}

SAVE_BLUEPRINT_TOOL = {
    "name": "save_as_blueprint",
    "description": (
        "Save a workflow as a reusable blueprint. Pass a complete workflow "
        "(with steps array) and the engine will abstract concrete values "
        "into parameters, creating a reusable pattern."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "workflow": {
                "type": "object",
                "description": "Workflow dict with steps array",
            },
            "name": {
                "type": "string",
                "description": "Blueprint name",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for search",
            },
        },
        "required": ["workflow"],
    },
}

REPORT_OUTCOME_TOOL = {
    "name": "report_blueprint_outcome",
    "description": (
        "Report whether a blueprint-generated workflow succeeded or failed. "
        "Call this after the user runs a workflow that was built from a blueprint."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "blueprint_id": {
                "type": "string",
                "description": "Blueprint ID that was used",
            },
            "success": {
                "type": "boolean",
                "description": "True if the workflow succeeded, false if it failed",
            },
            "execution_id": {
                "type": "string",
                "description": "Stable execution ID used to deduplicate outcome reports",
            },
        },
        "required": ["blueprint_id", "success"],
    },
}

EXPORT_BLUEPRINT_TOOL = {
    "name": "export_blueprint",
    "description": (
        "Create an integrity-checked portable bundle for an existing Blueprint. "
        "This does not upload or publish anything. Host-controlled signing keys "
        "are never accepted through the model-facing tool."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "blueprint_id": {
                "type": "string",
                "description": "Blueprint ID to export",
            },
            "publisher": {
                "type": "string",
                "description": "Optional publisher label included as an untrusted claim",
            },
        },
        "required": ["blueprint_id"],
    },
}

IMPORT_BLUEPRINT_TOOL = {
    "name": "import_blueprint",
    "description": (
        "Validate and import a portable Blueprint bundle. Unsigned or unknown "
        "publishers are quarantined as community trust; the host owns trusted keys."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "bundle": {
                "type": "object",
                "description": "Portable bundle returned by export_blueprint",
            },
        },
        "required": ["bundle"],
    },
}


def get_blueprint_tools() -> List[dict]:
    """Return all blueprint MCP tool definitions."""
    return [
        LIST_BLUEPRINTS_TOOL,
        USE_BLUEPRINT_TOOL,
        SAVE_BLUEPRINT_TOOL,
        REPORT_OUTCOME_TOOL,
        EXPORT_BLUEPRINT_TOOL,
        IMPORT_BLUEPRINT_TOOL,
    ]
