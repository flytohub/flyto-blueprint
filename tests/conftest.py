# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Shared fixtures for flyto-blueprint tests."""
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
    return BlueprintEngine(storage=memory_backend)


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
