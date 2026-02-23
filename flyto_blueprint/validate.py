# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Optional flyto-core module validation for expanded steps."""
import logging
from typing import List

logger = logging.getLogger(__name__)


def _get_core_validator():
    """Get flyto-core's validate_params. Returns None if unavailable."""
    try:
        from core.mcp_handler import validate_params
        return validate_params
    except Exception:
        return None


def validate_steps(steps: List[dict]) -> List[str]:
    """Check expanded steps against the flyto-core module registry.

    Returns a list of warning strings. Empty list = all good.
    Non-blocking: if flyto-core is unavailable, returns no warnings.

    Skips "module not found" errors since blueprints may use abstract
    module names that are resolved at runtime.
    """
    validate = _get_core_validator()
    if validate is None:
        return []

    warnings = []
    for step in steps:
        module_id = step.get("module", "")
        params = step.get("params", {})
        try:
            result = validate(module_id=module_id, params=params)
            if not result.get("valid", True):
                errors = result.get("errors", [])
                for err in errors:
                    if "not found" in err.lower():
                        continue
                    warnings.append("Step '{}' ({}): {}".format(
                        step.get("id", "?"), module_id, err,
                    ))
        except Exception:
            pass
    return warnings
