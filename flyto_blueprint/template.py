# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Template substitution for {{arg}} placeholders."""
import re
from typing import Any, Dict, FrozenSet

_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")
_STEP_REF_RE = re.compile(r"^\$\{.+\}$")

# Params that are always constants (structural, not user-specific)
CONSTANT_PARAMS: FrozenSet[str] = frozenset({
    "headless", "key", "state", "wait_until", "full_page",
    "multiple", "click_method",
})

# Params that are always args (user-specific, different every time)
ARG_PARAMS: FrozenSet[str] = frozenset({
    "url", "selector", "text", "query", "path", "body", "headers",
    "username", "password", "content", "fields",
})


def substitute(value: str, args: dict) -> str:
    """Replace ``{{arg_name}}`` placeholders in a string."""
    if not isinstance(value, str):
        return value

    def replacer(match: re.Match) -> str:
        arg_name = match.group(1)
        return str(args.get(arg_name, match.group(0)))

    return _TEMPLATE_RE.sub(replacer, value)


def substitute_deep(obj: Any, args: dict) -> Any:
    """Recursively substitute ``{{arg_name}}`` in dicts, lists, and strings.

    When an entire string is a single ``{{arg}}`` placeholder and the arg
    value is non-string (int, dict, list, bool), the original type is
    preserved instead of being stringified.
    """
    if isinstance(obj, str):
        match = _TEMPLATE_RE.fullmatch(obj)
        if match:
            arg_name = match.group(1)
            if arg_name in args:
                return args[arg_name]
            return obj
        return substitute(obj, args)
    elif isinstance(obj, dict):
        return {k: substitute_deep(v, args) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_deep(item, args) for item in obj]
    return obj


def abstract_params(
    params: dict,
    args_def: Dict[str, dict],
) -> dict:
    """Replace concrete param values with ``{{arg}}`` templates where appropriate.

    Builds up *args_def* as a side effect — each new arg is registered there.
    """
    result = {}
    for param_name, value in params.items():
        # Already a step reference like ${steps.xxx} → keep as-is
        if isinstance(value, str) and _STEP_REF_RE.match(value):
            result[param_name] = value
            continue

        # Already a template → keep as-is
        if isinstance(value, str) and _TEMPLATE_RE.search(value):
            result[param_name] = value
            continue

        # Constant params → keep original value
        if param_name in CONSTANT_PARAMS:
            result[param_name] = value
            continue

        # Abstract to template
        arg_name = param_name
        result[param_name] = "{{{{{}}}}}".format(arg_name)

        # Register arg definition if not already present
        if arg_name not in args_def:
            arg_type = "string"
            if isinstance(value, bool):
                arg_type = "boolean"
            elif isinstance(value, (int, float)):
                arg_type = "number"
            elif isinstance(value, dict):
                arg_type = "object"
            elif isinstance(value, list):
                arg_type = "array"
            args_def[arg_name] = {
                "type": arg_type,
                "required": True,
                "description": "",
            }

    return result
