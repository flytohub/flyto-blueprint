# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Host-supplied module availability gating for blueprints.

The available module IDs are authoritative host state, not model input. This
module never imports Flyto2 Core and never discovers modules itself: a host
that knows its own registry passes the set in, and a host that passes nothing
keeps the previous permissive behavior. Because the set is trusted host state,
it is deliberately absent from the model-facing schemas in
``flyto_blueprint.tools``.

The gate fails closed. A module name that is still a ``{{arg}}`` template is
never assumed to be available: list and search hide the blueprint, and expand
only clears it once the supplied arguments resolve it to an available module.
"""
from typing import Dict, FrozenSet, Iterable, List, Optional

from flyto_blueprint.template import _TEMPLATE_RE, substitute

MODULE_UNAVAILABLE_CODE = "BLUEPRINT_MODULE_UNAVAILABLE"


def normalize_available_module_ids(
    available_module_ids: Optional[Iterable[str]],
) -> Optional[FrozenSet[str]]:
    """Normalize host input to one frozen set; ``None`` means "not supplied".

    Raises TypeError for a str/bytes-like or non-iterable input and for a
    non-string entry, and ValueError for a blank or whitespace-padded entry.
    """
    # The returned set is the single authoritative set used by list, search,
    # and expand for the rest of the call, so a host claim is interpreted
    # exactly once per call.
    #
    # Malformed input is rejected loudly instead of being repaired. Silently
    # dropping an entry the host believed it had published narrows the set
    # below what the host actually claimed, and a blueprint is then hidden or
    # refused for a reason no error ever names. Raising keeps the set a
    # faithful statement of host capability.
    #
    # None is the absence of a claim, so nothing is gated. An empty iterable
    # is a real claim that no module is executable and stays an empty frozen
    # set; the two must not collapse into each other.
    if available_module_ids is None:
        return None
    # A bare string or bytes-like object is iterable, so it would silently
    # degrade into a gate over single characters or integers.
    if isinstance(available_module_ids, (str, bytes, bytearray, memoryview)):
        raise TypeError(
            "available_module_ids must be an iterable of module ID strings, "
            "not {}".format(type(available_module_ids).__name__),
        )
    # Materialize once, before validating, so a generator is consumed exactly
    # once and a malformed iterable fails here rather than mid-gate.
    try:
        entries = list(available_module_ids)
    except TypeError as error:
        raise TypeError(
            "available_module_ids must be an iterable of module ID strings, "
            "not {}".format(type(available_module_ids).__name__),
        ) from error
    for entry in entries:
        if not isinstance(entry, str):
            raise TypeError(
                "available_module_ids entries must be module ID strings; got "
                "{}".format(type(entry).__name__),
            )
        if not entry.strip():
            raise ValueError(
                "available_module_ids entries must be non-blank module IDs",
            )
        # Not stripped for the host: a padded ID would never match a real
        # module name, and quietly trimming it invents a claim the host did
        # not make.
        if entry != entry.strip():
            raise ValueError(
                "available_module_ids entries must not have leading or "
                "trailing whitespace; got {!r}".format(entry),
            )
    return frozenset(entries)


def step_module_ids(steps: Iterable[dict]) -> List[str]:
    """Return ordered, unique module IDs of *steps* without step parameters."""
    module_ids: List[str] = []
    seen = set()
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        module_id = step.get("module")
        if not isinstance(module_id, str) or not module_id or module_id in seen:
            continue
        seen.add(module_id)
        module_ids.append(module_id)
    return module_ids


def _gated_steps(bp: dict, blocks: Optional[Dict[str, dict]]) -> List[dict]:
    """Return the composition block steps and own steps of a blueprint."""
    steps: List[dict] = []
    for block_id in bp.get("compose", []) or []:
        block = (blocks or {}).get(block_id)
        if block:
            steps.extend(block.get("steps", []) or [])
    steps.extend(bp.get("steps", []) or [])
    return [step for step in steps if isinstance(step, dict)]


def required_module_ids(
    bp: dict,
    blocks: Optional[Dict[str, dict]] = None,
    args: Optional[dict] = None,
) -> List[str]:
    """Return ordered, unique module IDs a blueprint needs in order to expand."""
    # Composition block steps count: they become real steps of the expanded
    # workflow. With *args*, dynamic module names are resolved and steps that
    # expansion would skip are dropped, so the gate sees what will really run.
    # Without *args*, an unresolved ``{{arg}}`` module name is returned as is
    # and treated as unavailable by the caller.
    steps = _gated_steps(bp, blocks)
    if args is None:
        return step_module_ids(steps)
    runnable = []
    for step in steps:
        skip_args = step.get("skip_if_missing", []) or []
        if skip_args and any(arg not in args for arg in skip_args):
            continue
        runnable.append({**step, "module": substitute(step.get("module"), args)})
    return step_module_ids(runnable)


def missing_module_ids(
    bp: dict,
    available_module_ids: Optional[FrozenSet[str]],
    blocks: Optional[Dict[str, dict]] = None,
    args: Optional[dict] = None,
) -> List[str]:
    """Return the sorted required module IDs the host cannot provide."""
    # Always empty without a host claim. Sorting keeps the gate deterministic.
    # The template test is independent of membership: an unresolved ``{{arg}}``
    # name is reported verbatim, so a literal token in the host set proves nothing.
    if available_module_ids is None:
        return []
    return sorted({
        module_id
        for module_id in required_module_ids(bp, blocks, args)
        if _TEMPLATE_RE.search(module_id) or module_id not in available_module_ids
    })


def is_blueprint_available(
    bp: dict,
    available_module_ids: Optional[FrozenSet[str]],
    blocks: Optional[Dict[str, dict]] = None,
) -> bool:
    """Return whether every module required by *bp* is available on the host."""
    return not missing_module_ids(bp, available_module_ids, blocks)


def module_unavailable_error(blueprint_id: str, missing: List[str]) -> dict:
    """Build the deterministic module-availability failure for ``expand``."""
    return {
        "ok": False,
        "error": "Blueprint '{}' requires modules unavailable on this host: {}".format(
            blueprint_id, ", ".join(missing),
        ),
        "code": MODULE_UNAVAILABLE_CODE,
        "missing_module_ids": missing,
    }
