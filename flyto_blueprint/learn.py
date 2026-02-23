# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Learn reusable blueprints from concrete workflows."""
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from flyto_blueprint.fingerprint import compute_fingerprint
from flyto_blueprint.template import abstract_params


def learn_from_workflow(
    workflow: dict,
    blueprints: Dict[str, dict],
    blocks: Dict[str, dict],
    *,
    blueprint_id: Optional[str] = None,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    verified: bool = False,
) -> dict:
    """Abstract a concrete workflow into a reusable blueprint.

    Concrete values become ``{{arg}}`` templates; structural constants
    stay fixed. Detects compose opportunities (browser.launch + browser.goto
    → browser_init).

    Dedup: if a blueprint with the same structure already exists, returns
    ``{"ok": True, "action": "boosted_existing", "blueprint_id": ...}``.

    Returns the new blueprint data dict (not yet persisted — caller must
    handle storage).
    """
    steps = workflow.get("steps", [])
    if not steps:
        return {"ok": False, "error": "Workflow has no steps"}

    if len(steps) < 3:
        return {"ok": False, "error": "Workflow too simple (min 3 steps)"}

    # Fingerprint dedup
    fingerprint = compute_fingerprint(steps)
    existing_id = _find_by_fingerprint(fingerprint, blueprints)
    if existing_id:
        return {
            "ok": True,
            "action": "boosted_existing",
            "blueprint_id": existing_id,
        }

    # Auto-generate id from name or module list
    if not blueprint_id:
        if name:
            blueprint_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        else:
            modules = [s.get("module", "unknown") for s in steps[:3]]
            blueprint_id = "_".join(m.replace(".", "_") for m in modules)
        # Ensure uniqueness
        base_id = blueprint_id
        counter = 1
        while blueprint_id in blueprints:
            counter += 1
            blueprint_id = "{}_{}".format(base_id, counter)

    # Abstract params → build args
    args_def: Dict[str, dict] = {}
    abstracted_steps = []

    for step in steps:
        new_step = {
            "id": step.get("id", "step_{}".format(len(abstracted_steps) + 1)),
            "module": step.get("module", ""),
            "label": step.get("label", step.get("id", "")),
        }
        if "params" in step:
            new_step["params"] = abstract_params(step["params"], args_def)
        if "skip_if_missing" in step:
            new_step["skip_if_missing"] = step["skip_if_missing"]
        abstracted_steps.append(new_step)

    # Detect compose opportunity
    compose: List[str] = []
    remaining_steps = abstracted_steps
    if (
        len(abstracted_steps) >= 2
        and abstracted_steps[0].get("module") == "browser.launch"
        and abstracted_steps[1].get("module") == "browser.goto"
        and "browser_init" in blocks
    ):
        compose = ["browser_init"]
        remaining_steps = abstracted_steps[2:]

    # Auto-generate name
    if not name:
        name = "Learned: {}".format(blueprint_id.replace("_", " ").title())

    # Auto-generate tags from modules
    if not tags:
        tags = list(set(
            s.get("module", "").split(".")[0]
            for s in steps
            if s.get("module")
        ))

    initial_score = 70 if verified else 50
    now = datetime.now(timezone.utc).isoformat()

    bp: dict = {
        "id": blueprint_id,
        "name": name,
        "description": workflow.get("description", ""),
        "tags": tags,
        "args": args_def,
    }
    if compose:
        bp["compose"] = compose
    bp["steps"] = remaining_steps
    bp["_source"] = "learned"
    bp["created_at"] = now
    bp["score"] = initial_score
    bp["use_count"] = 0
    bp["success_count"] = 0
    bp["fail_count"] = 0
    bp["last_used_at"] = None
    bp["fingerprint"] = fingerprint
    bp["retired"] = False

    return {"ok": True, "data": bp}


def _find_by_fingerprint(fingerprint: str, blueprints: Dict[str, dict]) -> Optional[str]:
    """Find an existing learned blueprint with the same fingerprint."""
    for bp_id, bp in blueprints.items():
        if bp.get("_source") == "learned" and bp.get("fingerprint") == fingerprint:
            return bp_id
    return None
