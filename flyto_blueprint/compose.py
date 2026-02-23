# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Compose block expansion for blueprints."""
import logging
from typing import Dict, List

import yaml

from flyto_blueprint.template import substitute, substitute_deep

logger = logging.getLogger(__name__)


def expand_compose(bp: dict, blocks: Dict[str, dict]) -> List[dict]:
    """Expand compose blocks into a flat step list, followed by the blueprint's own steps."""
    steps = []
    for block_id in bp.get("compose", []):
        block = blocks.get(block_id)
        if not block:
            logger.warning("Block '%s' not found, skipping", block_id)
            continue
        steps.extend(block.get("steps", []))
    steps.extend(bp.get("steps", []))
    return steps


def expand_blueprint(bp: dict, args: dict, blocks: Dict[str, dict]) -> dict:
    """Expand a blueprint: validate args, substitute templates, skip optional steps.

    Returns a dict with ``ok``, ``data`` (workflow + yaml), and optionally ``warnings``.
    """
    # Validate required args
    missing = []
    for arg_name, arg_meta in bp.get("args", {}).items():
        if arg_meta.get("required") and arg_name not in args:
            missing.append(arg_name)

    if missing:
        return {
            "ok": False,
            "error": "Missing required arguments: {}".format(", ".join(missing)),
        }

    # Get all steps (compose blocks + blueprint's own)
    all_steps = expand_compose(bp, blocks)

    # Expand steps
    expanded_steps = []
    for step in all_steps:
        # Check skip_if_missing
        skip_args = step.get("skip_if_missing", [])
        if skip_args and any(a not in args for a in skip_args):
            continue

        expanded_step = {
            "id": step["id"],
            "module": substitute(step["module"], args),
            "label": step.get("label", step["id"]),
        }

        if "params" in step:
            expanded_step["params"] = substitute_deep(step["params"], args)

        expanded_steps.append(expanded_step)

    # Generate sequential edges
    edges = []
    for i in range(len(expanded_steps) - 1):
        edges.append({
            "source": expanded_steps[i]["id"],
            "target": expanded_steps[i + 1]["id"],
        })

    workflow = {
        "name": bp.get("name", bp.get("id", "")),
        "description": bp.get("description", ""),
        "steps": expanded_steps,
        "edges": edges,
    }

    # Tag with source blueprint for auto-outcome-reporting
    if bp.get("_source") == "learned":
        workflow["source_blueprint_id"] = bp["id"]

    yaml_str = yaml.dump(
        workflow,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    return {"ok": True, "data": {**workflow, "yaml": yaml_str}}
