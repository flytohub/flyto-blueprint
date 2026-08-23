# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Shared fixtures for flyto-blueprint tests."""
import hashlib
import json
import uuid

import pytest

from flyto_blueprint import BlueprintEngine
from flyto_blueprint.storage.memory import MemoryBackend


RUN_ID = uuid.uuid4().hex[:6]


@pytest.fixture
def memory_backend():
    return MemoryBackend()


@pytest.fixture
def engine(memory_backend):
    instance = BlueprintEngine(storage=memory_backend)
    original = instance.report_outcome

    def report_with_host_receipt(blueprint_id, success, **kwargs):
        if kwargs.get("evidence_tier", "local_verified") != "community":
            evidence = kwargs.get("evidence")
            kwargs.setdefault(
                "verification",
                outcome_receipt(success, evidence=evidence),
            )
        return original(blueprint_id, success, **kwargs)

    instance.report_outcome = report_with_host_receipt
    return instance


def make_workflow(tag=None):
    """Build a 3-step workflow with a unique structure."""
    tag = tag or uuid.uuid4().hex[:6]
    return {
        "name": "Test {}".format(tag),
        "description": "test workflow",
        "steps": [
            {"id": "s1", "module": "math.add", "params": {"a": 1, "b": 2}},
            {"id": "s2", "module": "string.reverse", "params": {"text": tag}},
            {"id": "s3", "module": "array.sort", "params": {"array": [3, 1, 2], "tag": tag}},
        ],
    }


def make_workflow_alt():
    """Different structure (different modules) → different fingerprint."""
    return {
        "name": "Alt Workflow",
        "description": "alternative",
        "steps": [
            {"id": "s1", "module": "math.multiply", "params": {"a": 1, "b": 2}},
            {"id": "s2", "module": "string.uppercase", "params": {"text": "x"}},
            {"id": "s3", "module": "array.flatten", "params": {"array": []}},
        ],
    }


def verification_receipt(evidence_id="test-evidence", evidence=None):
    """Build a valid deterministic host verification receipt."""
    if evidence is None:
        evidence = {
            "solver": "test.fixture",
            "result": {"value": 3, "unit": "items"},
            "assumptions": ["deterministic inputs"],
        }
    digest = hashlib.sha256(json.dumps(
        evidence, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "receipt_version": "flyto.execution-verification-receipt.v1",
        "success": True,
        "status": "verified",
        "evidence_id": evidence_id,
        "evidence_sha256": digest,
        "evidence": evidence,
    }


def outcome_receipt(success, evidence_id="test-outcome", evidence=None):
    """Build a receipt whose canonical evidence binds an observed outcome."""
    if type(success) is not bool:
        raise TypeError("success must be an exact bool")
    bounded = dict(evidence or {})
    bounded["outcome_success"] = success
    return verification_receipt(evidence_id, bounded)
