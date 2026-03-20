# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Compose block expansion for blueprints."""
import copy
import logging
import re
from typing import Any, Dict, List, Optional, Set

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


# ---------------------------------------------------------------------------
# compose_chain — Phase 2: Chain multiple blueprints
# ---------------------------------------------------------------------------


def compose_chain(
    blueprint_ids: List[str],
    args: Dict[str, Any],
    blueprints: Dict[str, dict],
    blocks: Dict[str, dict],
) -> dict:
    """
    Expand and chain multiple blueprints into a single workflow.

    1. Expand each blueprint via expand_blueprint()
    2. Deconflict step IDs across blueprints
    3. Wire cross-blueprint variable references
    4. Generate edges (intra + cross-blueprint)

    Args:
        blueprint_ids: Ordered list of blueprint IDs to chain.
        args: Per-blueprint args: {blueprint_id: {arg: value}}.
        blueprints: All available blueprints (id → dict).
        blocks: All available compose blocks (id → dict).

    Returns:
        {ok: True, data: {steps, edges}} or {ok: False, error: str}.
    """
    if not blueprint_ids:
        return {"ok": False, "error": "No blueprint IDs provided"}

    all_steps: List[Dict[str, Any]] = []
    all_edges: List[Dict[str, Any]] = []
    seen_step_ids: Set[str] = set()
    last_step_id: Optional[str] = None
    bp_outputs: List[Dict[str, Any]] = []  # track last step + output_field per bp

    for idx, bp_id in enumerate(blueprint_ids):
        bp = blueprints.get(bp_id)
        if not bp:
            return {"ok": False, "error": f"Blueprint '{bp_id}' not found"}

        bp_args = args.get(bp_id, {})
        result = expand_blueprint(bp, bp_args, blocks)
        if not result.get("ok"):
            return {"ok": False, "error": f"Blueprint '{bp_id}': {result.get('error', 'expand failed')}"}

        data = result["data"]
        steps = copy.deepcopy(data.get("steps", []))
        edges = copy.deepcopy(data.get("edges", []))

        # Deconflict step IDs
        id_map = _deconflict_step_ids(steps, edges, seen_step_ids, idx)

        # Collect arg names for this blueprint
        all_declared_args = set(bp.get("args", {}).keys())
        optional_args = {
            name for name, meta in bp.get("args", {}).items()
            if not meta.get("required")
        }

        # Wire cross-blueprint variable references (first step only)
        # Skip ALL declared args — they were filled by sanitize or user
        if bp_outputs:
            prev = bp_outputs[-1]
            _wire_cross_blueprint_refs(steps, prev["last_step_id"], prev["output_field"], all_declared_args)

        # Strip remaining unresolved optional arg placeholders AFTER wiring
        _strip_unresolved_placeholders(steps, optional_args)

        # Track this blueprint's output
        output_field = bp.get("connections", {}).get("output_field", "data.result")
        bp_last_step_id = steps[-1]["id"] if steps else None

        # Cross-blueprint edge: previous last step → this first step
        if last_step_id and steps:
            all_edges.append({
                "source": last_step_id,
                "target": steps[0]["id"],
            })

        all_steps.extend(steps)
        all_edges.extend(edges)

        for s in steps:
            seen_step_ids.add(s["id"])

        if bp_last_step_id:
            last_step_id = bp_last_step_id
            bp_outputs.append({
                "last_step_id": bp_last_step_id,
                "output_field": output_field,
                "blueprint_id": bp_id,
            })

    return {
        "ok": True,
        "data": {
            "steps": all_steps,
            "edges": all_edges,
        },
    }


def _deconflict_step_ids(
    steps: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    seen_ids: Set[str],
    bp_index: int,
) -> Dict[str, str]:
    """Prefix colliding step IDs with bp{idx}_ and update edges + param refs."""
    id_map: Dict[str, str] = {}

    # Build rename map for collisions
    for step in steps:
        old_id = step["id"]
        if old_id in seen_ids:
            new_id = f"bp{bp_index}_{old_id}"
            # Avoid double-collision
            counter = 0
            while new_id in seen_ids:
                counter += 1
                new_id = f"bp{bp_index}_{old_id}_{counter}"
            id_map[old_id] = new_id

    if not id_map:
        return id_map

    # Apply renames to steps
    for step in steps:
        old_id = step["id"]
        if old_id in id_map:
            step["id"] = id_map[old_id]
        # Update variable refs in params
        params = step.get("params", {})
        for key, val in params.items():
            if isinstance(val, str):
                for old, new in id_map.items():
                    val = val.replace(f"${{steps.{old}.", f"${{steps.{new}.")
                    val = val.replace(f"${{{old}.", f"${{{new}.")
                params[key] = val

    # Apply renames to edges
    for edge in edges:
        if edge.get("source") in id_map:
            edge["source"] = id_map[edge["source"]]
        if edge.get("target") in id_map:
            edge["target"] = id_map[edge["target"]]

    return id_map


def _strip_unresolved_placeholders(
    steps: List[Dict[str, Any]],
    optional_args: Optional[Set[str]] = None,
) -> None:
    """Remove params whose value is an unresolved ``{{X}}`` placeholder
    where X is a known optional arg.

    If *optional_args* is None, strips ALL unresolved ``{{X}}`` placeholders.
    """
    placeholder_re = re.compile(r"^\{\{(\w+)\}\}$")
    for step in steps:
        params = step.get("params", {})
        to_remove = []
        for key, val in params.items():
            if not isinstance(val, str):
                continue
            m = placeholder_re.match(val.strip())
            if m:
                arg_name = m.group(1)
                if optional_args is None or arg_name in optional_args:
                    to_remove.append(key)
        for key in to_remove:
            del params[key]


def _wire_cross_blueprint_refs(
    steps: List[Dict[str, Any]],
    prev_last_step_id: str,
    output_field: str,
    optional_args: Optional[Set[str]] = None,
) -> None:
    """Replace unresolved {{X}} placeholders with refs to previous blueprint's output.

    Only wires params where the ENTIRE value is a single ``{{X}}`` placeholder
    and X is NOT a declared optional arg (those will be stripped instead).
    """
    if not steps:
        return

    optional_args = optional_args or set()
    exact_placeholder_re = re.compile(r"^\{\{(\w+)\}\}$")
    first_step = steps[0]
    params = first_step.get("params", {})

    for key, val in params.items():
        if not isinstance(val, str):
            continue
        match = exact_placeholder_re.match(val.strip())
        if match:
            arg_name = match.group(1)
            if arg_name in optional_args:
                continue  # Will be stripped later, not wired
            params[key] = f"${{steps.{prev_last_step_id}.{output_field}}}"
