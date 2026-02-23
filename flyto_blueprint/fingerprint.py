# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Structural fingerprinting for blueprint deduplication."""
import hashlib
from typing import List


def compute_fingerprint(steps: List[dict]) -> str:
    """Compute an MD5 fingerprint of a workflow's module+param-key structure.

    Two workflows with the same modules and the same parameter keys
    (regardless of values) produce the same fingerprint.

    Returns a 12-character hex string.
    """
    sig = []
    for step in steps:
        module = step.get("module", "")
        param_keys = sorted(step.get("params", {}).keys())
        sig.append("{}:{}".format(module, ",".join(param_keys)))
    return hashlib.md5("|".join(sig).encode()).hexdigest()[:12]
