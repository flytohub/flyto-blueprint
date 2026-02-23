# Copyright 2024 Flyto
# Licensed under the Apache License, Version 2.0
"""Tests for fingerprint computation — hash stability and uniqueness."""
from flyto_blueprint.fingerprint import compute_fingerprint


class TestFingerprint:

    def test_same_structure_same_fingerprint(self):
        steps_a = [
            {"module": "math.add", "params": {"a": 1}},
            {"module": "string.reverse", "params": {"text": "hello"}},
        ]
        steps_b = [
            {"module": "math.add", "params": {"a": 999}},
            {"module": "string.reverse", "params": {"text": "world"}},
        ]
        assert compute_fingerprint(steps_a) == compute_fingerprint(steps_b)

    def test_different_modules_different_fingerprint(self):
        steps_a = [{"module": "math.add", "params": {"a": 1}}]
        steps_b = [{"module": "math.multiply", "params": {"a": 1}}]
        assert compute_fingerprint(steps_a) != compute_fingerprint(steps_b)

    def test_different_param_keys_different_fingerprint(self):
        steps_a = [{"module": "api.get", "params": {"url": "x"}}]
        steps_b = [{"module": "api.get", "params": {"url": "x", "headers": {}}}]
        assert compute_fingerprint(steps_a) != compute_fingerprint(steps_b)

    def test_fingerprint_length(self):
        fp = compute_fingerprint([{"module": "a.b", "params": {"x": 1}}])
        assert len(fp) == 12

    def test_deterministic(self):
        steps = [{"module": "x.y", "params": {"a": 1, "b": 2}}]
        assert compute_fingerprint(steps) == compute_fingerprint(steps)

    def test_empty_steps(self):
        fp = compute_fingerprint([])
        assert isinstance(fp, str)
        assert len(fp) == 12
