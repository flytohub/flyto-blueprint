# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Execution-receipt boundary tests for verified procedure learning."""
import copy
import math

import pytest

from conftest import make_workflow, outcome_receipt, verification_receipt
from flyto_blueprint import BlueprintEngine
from flyto_blueprint.execution_verification import validate_execution_verification_receipt
from flyto_blueprint.learn import learn_from_workflow as low_level_learn
from flyto_blueprint.storage.memory import MemoryBackend


_SOLVER_EVIDENCE = {
    "geometry": {
        "solver": "geometry.rectangle_area",
        "inputs": {"width": {"value": 3, "unit": "m"}, "height": {"value": 4, "unit": "m"}},
        "assumptions": ["euclidean plane", "orthogonal sides"],
        "result": {"value": 12, "unit": "m^2"},
    },
    "kinematics": {
        "solver": "kinematics.constant_velocity",
        "inputs": {"velocity": {"value": 5, "unit": "m/s"}, "time": {"value": 6, "unit": "s"}},
        "assumptions": ["constant velocity", "one-dimensional motion"],
        "result": {"displacement": {"value": 30, "unit": "m"}},
    },
    "dilution": {
        "solver": "chemistry.dilution",
        "inputs": {"stock": {"value": 2, "unit": "mol/L"}, "target": {"value": 0.5, "unit": "mol/L"}},
        "assumptions": ["additive volumes", "solute conserved"],
        "result": {"dilution_factor": 4, "unit": "ratio"},
    },
}


@pytest.mark.parametrize(
    ("verified", "trust_tier", "receipt", "code"),
    [
        (True, None, None, "INVALID_EXECUTION_VERIFICATION_RECEIPT"),
        (True, None, {**verification_receipt("tampered-low"), "success": False},
         "INVALID_EXECUTION_VERIFICATION_RECEIPT"),
        (False, "local_verified", None, "INVALID_EXECUTION_VERIFICATION_RECEIPT"),
        (False, "ci_verified", verification_receipt("fake-ci"),
         "UNSUPPORTED_VERIFICATION_TRUST_TIER"),
        (False, "official", verification_receipt("fake-official"),
         "UNSUPPORTED_VERIFICATION_TRUST_TIER"),
        (False, "self_claimed", verification_receipt("fake-arbitrary"),
         "UNSUPPORTED_VERIFICATION_TRUST_TIER"),
    ],
)
def test_low_level_trust_claims_fail_before_any_input_or_state_mutation(
    verified, trust_tier, receipt, code,
):
    class WorkflowThatMustNotBeRead(dict):
        def get(self, *args, **kwargs):
            raise AssertionError("trust gate inspected workflow before rejection")

    blueprints = {"sentinel": {"id": "sentinel", "score": 71}}
    blocks = {"sentinel": {"steps": []}}
    before_blueprints = copy.deepcopy(blueprints)
    before_blocks = copy.deepcopy(blocks)

    result = low_level_learn(
        WorkflowThatMustNotBeRead(), blueprints, blocks,
        verified=verified, trust_tier=trust_tier, verification=receipt,
    )

    assert result["ok"] is False
    assert result["code"] == code
    assert blueprints == before_blueprints
    assert blocks == before_blocks


def test_low_level_explicit_local_verified_receipt_is_canonical_and_detached():
    blueprints = {}
    evidence = {
        "result": {"unit": "items", "value": 3},
        "assumptions": ["deterministic inputs"],
        "solver": "test.fixture",
    }
    receipt = verification_receipt("low-level-valid", evidence)

    result = low_level_learn(
        make_workflow(tag="low-level-valid"), blueprints, {},
        verified=False, trust_tier="local_verified", verification=receipt,
    )

    assert result["ok"] is True
    assert result["data"]["score"] == 70
    assert result["data"]["provenance"]["origin"] == "local_execution"
    assert result["data"]["trust_tier"] == "local_verified"
    assert result["data"]["verification"] == receipt
    assert list(result["data"]["verification"]["evidence"]) == [
        "assumptions", "result", "solver",
    ]
    assert result["data"]["execution_authority"] is False

    evidence["result"]["value"] = 999
    evidence["assumptions"].append("caller mutation")

    assert result["data"]["verification"]["evidence"]["result"]["value"] == 3
    assert result["data"]["verification"]["evidence"]["assumptions"] == [
        "deterministic inputs",
    ]


def test_low_level_community_learning_remains_explicit():
    result = low_level_learn(
        make_workflow(tag="low-level-community"), {}, {},
        verified=False, trust_tier="community",
    )

    assert result["ok"] is True
    assert result["data"]["score"] == 50
    assert result["data"]["provenance"]["origin"] == "local_workflow"
    assert result["data"]["trust_tier"] == "community"


def test_verified_duplicate_learning_is_byte_for_byte_non_mutating():
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    workflow = make_workflow(tag="verified-dedup-no-mutation")
    first = engine.learn_from_execution(
        workflow, verification=verification_receipt("verified-first"),
    )
    blueprint_id = first["data"]["id"]
    before_memory = copy.deepcopy(engine._blueprints)
    before_storage = copy.deepcopy(storage.load_all())
    before_recent = copy.deepcopy(engine._recent_reports)

    duplicate = engine.learn_from_execution(
        workflow, verification=verification_receipt("verified-duplicate"),
    )

    assert duplicate == {
        "ok": True,
        "action": "deduplicated_existing",
        "blueprint_id": blueprint_id,
    }
    assert engine._blueprints == before_memory
    assert storage.load_all() == before_storage
    assert engine._recent_reports == before_recent


@pytest.mark.parametrize("missing", [None, verification_receipt("solver-without-outcome")])
def test_trusted_outcome_requires_outcome_bound_receipt_without_any_mutation(missing):
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    learned = engine.learn_from_workflow(make_workflow(tag="trusted-gate"))
    blueprint_id = learned["data"]["id"]
    before_memory = copy.deepcopy(engine._blueprints[blueprint_id])
    before_storage = copy.deepcopy(storage.load_one(blueprint_id))

    rejected = engine.report_outcome(
        blueprint_id, True, execution_id="must-not-dedup", verification=missing,
    )

    assert rejected["ok"] is False
    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert engine._blueprints[blueprint_id] == before_memory
    assert storage.load_one(blueprint_id) == before_storage
    assert "must-not-dedup" not in engine._recent_reports


def test_community_observation_cannot_be_promoted_without_a_receipt():
    engine = BlueprintEngine(storage=MemoryBackend())
    blueprint_id = engine.learn_from_workflow(
        make_workflow(tag="community-bypass"),
    )["data"]["id"]
    observed = engine.report_outcome(
        blueprint_id, True, execution_id="community-first", evidence_tier="community",
    )
    before = copy.deepcopy(engine._blueprints[blueprint_id])

    rejected = engine.report_outcome(
        blueprint_id, True, execution_id="untrusted-promotion",
        evidence_tier="local_verified",
    )

    assert observed["score_changed"] is False
    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert engine._blueprints[blueprint_id] == before
    assert "untrusted-promotion" not in engine._recent_reports


@pytest.mark.parametrize(
    ("reported", "receipt_success"),
    [(True, False), (False, True)],
)
def test_mismatched_outcome_receipt_fails_before_dedup(reported, receipt_success):
    engine = BlueprintEngine(storage=MemoryBackend())
    blueprint_id = engine.learn_from_workflow(
        make_workflow(tag="outcome-mismatch"),
    )["data"]["id"]
    before = copy.deepcopy(engine._blueprints[blueprint_id])

    rejected = engine.report_outcome(
        blueprint_id, reported, execution_id="outcome-mismatch",
        verification=outcome_receipt(receipt_success, "outcome-mismatch"),
    )

    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert "does not match" in rejected["error"]
    assert engine._blueprints[blueprint_id] == before
    assert engine._recent_reports == {}


def test_stale_outcome_digest_fails_without_evidence_or_dedup_mutation():
    engine = BlueprintEngine(storage=MemoryBackend())
    blueprint_id = engine.learn_from_workflow(
        make_workflow(tag="stale-outcome"),
    )["data"]["id"]
    receipt = outcome_receipt(True, "stale-outcome", {"duration_ms": 1})
    receipt["evidence"]["duration_ms"] = 2

    rejected = engine.report_outcome(
        blueprint_id, True, execution_id="stale-outcome", verification=receipt,
    )

    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert engine._blueprints[blueprint_id].get("evidence_samples", []) == []
    assert engine._recent_reports == {}


def test_success_argument_must_be_exact_bool():
    engine = BlueprintEngine(storage=MemoryBackend())
    blueprint_id = engine.learn_from_workflow(
        make_workflow(tag="bool-outcome"),
    )["data"]["id"]

    rejected = engine.report_outcome(
        blueprint_id, 1, verification=outcome_receipt(True, "bool-outcome"),
    )

    assert rejected["code"] == "INVALID_OUTCOME_SUCCESS"
    assert engine._blueprints[blueprint_id]["score"] == 50


@pytest.mark.parametrize("domain", sorted(_SOLVER_EVIDENCE))
def test_domain_shaped_verified_receipts_learn_and_reuse(domain):
    engine = BlueprintEngine(storage=MemoryBackend())
    workflow = make_workflow(tag=domain)
    receipt = verification_receipt(
        "solver/{}/run-1".format(domain), copy.deepcopy(_SOLVER_EVIDENCE[domain]),
    )

    learned = engine.learn_from_execution(
        workflow, name="{}_solver".format(domain), verification=receipt,
    )

    assert learned["ok"] is True
    assert learned["data"]["score"] == 70
    assert learned["data"]["execution_authority"] is False
    blueprint_id = learned["data"]["id"]
    stored = engine._blueprints[blueprint_id]
    assert stored["verification"] == receipt
    assert stored["trust_tier"] == "local_verified"

    reused = engine.expand(blueprint_id, {"a": 4, "b": 5, "text": domain, "array": [2, 1], "tag": domain})
    assert reused["ok"] is True
    assert engine._blueprints[blueprint_id]["use_count"] == 1
    assert next(item for item in engine.search(domain) if item["id"] == blueprint_id)["execution_authority"] is False


def test_valid_verification_metadata_cannot_promote_community_workflow():
    engine = BlueprintEngine(storage=MemoryBackend())
    receipt = verification_receipt("community-metadata")

    learned = engine.learn_from_workflow(
        make_workflow(tag="community-metadata"), verification=receipt,
    )

    assert learned["ok"] is True
    assert learned["data"]["score"] == 50
    assert learned["data"]["trust_tier"] == "community"
    assert learned["data"]["execution_authority"] is False
    stored = engine._blueprints[learned["data"]["id"]]
    assert stored["trust_tier"] == "community"
    assert stored["execution_authority"] is False


def _invalid_receipts():
    valid = verification_receipt()
    cases = [
        None,
        "not-json-object",
        [("receipt_version", "flyto.execution-verification-receipt.v1")],
        {**valid, "success": False},
        {**valid, "success": 1},
        {**valid, "status": "failed"},
        {**valid, "status": "unverified"},
        {**valid, "evidence_sha256": "b" * 64},
        {key: value for key, value in valid.items() if key != "evidence_id"},
        {**valid, "unknown": "unsafe"},
        {**valid, "evidence_id": "x" * 193},
        {**valid, "evidence_id": "unsafe value"},
        {**valid, "evidence_id": "unsafe/../value"},
        {**valid, "evidence_sha256": "A" * 64},
        {**valid, "evidence_sha256": "a" * 63},
        {**valid, "evidence_id": math.nan},
        {**valid, "evidence": ["not", "an", "object"]},
        {**valid, "evidence": {"value": math.nan}},
        {**valid, "evidence": {"value": math.inf}},
        {**valid, "evidence": {"value": -math.inf}},
        {**valid, "evidence": {"value": 1 << 53}},
        {**valid, "evidence": {"value": (1, 2)}},
        {**verification_receipt(evidence={"value": 1}), "evidence": {"value": True}},
        {**valid, "evidence": {1: "non-string key"}},
    ]
    return cases


@pytest.mark.parametrize("receipt", _invalid_receipts())
def test_invalid_receipt_fails_before_persistence_or_mutation(receipt):
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    workflow = make_workflow(tag="falsification")

    result = engine.learn_from_execution(workflow, name="rejected", verification=receipt)

    assert result["ok"] is False
    assert result["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert storage.load_all() == []
    assert not any(bp.get("name") == "rejected" for bp in engine._blueprints.values())


def test_invalid_duplicate_receipt_cannot_boost_existing_score():
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    workflow = make_workflow(tag="no-dedup-boost")
    learned = engine.learn_from_execution(
        workflow, name="accepted", verification=verification_receipt("accepted"),
    )
    blueprint_id = learned["data"]["id"]
    before = copy.deepcopy(storage.load_one(blueprint_id))

    rejected = engine.learn_from_execution(
        workflow, name="tampered", verification={**verification_receipt("accepted"), "success": False},
    )

    assert rejected["ok"] is False
    assert storage.load_one(blueprint_id) == before
    assert engine._blueprints[blueprint_id]["score"] == 70


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(-(1 << 53) + 1, id="minimum-safe-integer"),
        pytest.param((1 << 53) - 1, id="maximum-safe-integer"),
        pytest.param(-1.7976931348623157e308, id="minimum-finite-float"),
        pytest.param(1.7976931348623157e308, id="maximum-finite-float"),
    ],
)
def test_numeric_json_boundaries_are_accepted_without_changing_type(value):
    receipt = verification_receipt("numeric-boundary", {"value": value})

    canonical = validate_execution_verification_receipt(receipt)

    assert canonical["evidence"]["value"] == value
    assert type(canonical["evidence"]["value"]) is type(value)


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        pytest.param(math.nan, "float must be finite", id="nan"),
        pytest.param(math.inf, "float must be finite", id="positive-infinity"),
        pytest.param(-math.inf, "float must be finite", id="negative-infinity"),
        pytest.param(-(1 << 53), "integer exceeds v1 safe range", id="below-safe-integer"),
        pytest.param(1 << 53, "integer exceeds v1 safe range", id="above-safe-integer"),
    ],
)
def test_invalid_numeric_boundaries_fail_for_numeric_reason_before_digest(value, reason):
    invalid = verification_receipt("invalid-numeric-boundary")
    invalid["evidence"] = {"value": value}

    with pytest.raises(ValueError, match=reason):
        validate_execution_verification_receipt(invalid)


@pytest.mark.parametrize(
    "value",
    [math.nan, math.inf, -math.inf, -(1 << 53), 1 << 53],
)
def test_invalid_numeric_receipt_cannot_mutate_persistence_or_dedup_score(value):
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    workflow = make_workflow(tag="numeric-boundary-rejection")
    learned = engine.learn_from_execution(
        workflow, name="accepted", verification=verification_receipt("accepted"),
    )
    blueprint_id = learned["data"]["id"]
    before = copy.deepcopy(storage.load_all())
    invalid = verification_receipt("invalid-numeric-boundary")
    invalid["evidence"] = {"value": value}

    rejected = engine.learn_from_execution(
        workflow, name="rejected", verification=invalid,
    )

    assert rejected["ok"] is False
    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert storage.load_all() == before
    assert engine._blueprints[blueprint_id]["score"] == 70


def test_oversized_object_key_has_precise_failure_reason_before_digest():
    invalid = verification_receipt("oversized-object-key")
    invalid["evidence"] = {"x" * 4_097: None}

    with pytest.raises(
        ValueError,
        match="verification receipt evidence object key exceeds v1 length limit",
    ):
        validate_execution_verification_receipt(invalid)


@pytest.mark.parametrize(
    ("domain", "mutate"),
    [
        ("geometry", lambda evidence: evidence["result"].update(value=13)),
        ("kinematics", lambda evidence: evidence["assumptions"].__setitem__(0, "accelerating")),
        ("dilution", lambda evidence: evidence["result"].update(unit="percent")),
    ],
)
def test_nested_evidence_tamper_with_old_digest_fails_before_dedup(domain, mutate):
    storage = MemoryBackend()
    engine = BlueprintEngine(storage=storage)
    workflow = make_workflow(tag="tamper-{}".format(domain))
    receipt = verification_receipt("solver/{}/original".format(domain), copy.deepcopy(_SOLVER_EVIDENCE[domain]))
    learned = engine.learn_from_execution(workflow, verification=receipt)
    blueprint_id = learned["data"]["id"]
    before = copy.deepcopy(storage.load_one(blueprint_id))

    tampered = copy.deepcopy(receipt)
    mutate(tampered["evidence"])
    rejected = engine.learn_from_execution(workflow, verification=tampered)

    assert rejected["ok"] is False
    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert storage.load_one(blueprint_id) == before
    assert engine._blueprints[blueprint_id]["score"] == 70


@pytest.mark.parametrize(
    "evidence",
    [
        {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"nested": {"value": 1}}}}}}}}}}}}},
        {"value": "x" * 4_097},
        {"values": [None] * 2_048},
        {"values": ["x" * 4_000] * 9},
    ],
)
def test_evidence_bounds_fail_without_persistence(evidence):
    engine = BlueprintEngine(storage=MemoryBackend())
    receipt = verification_receipt("bounded", evidence)

    result = engine.learn_from_execution(make_workflow(tag="bounded"), verification=receipt)

    assert result["ok"] is False
    assert result["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert engine._storage.load_all() == []


def test_receipt_detaches_evidence_before_persistence():
    engine = BlueprintEngine(storage=MemoryBackend())
    evidence = copy.deepcopy(_SOLVER_EVIDENCE["geometry"])
    receipt = verification_receipt("detached", evidence)
    learned = engine.learn_from_execution(make_workflow(tag="detached"), verification=receipt)

    evidence["result"]["value"] = 999

    stored = engine._blueprints[learned["data"]["id"]]
    assert stored["verification"]["evidence"]["result"]["value"] == 12


def test_nested_evidence_digest_is_order_independent_and_tamper_fails_before_persistence():
    evidence = {
        "solver": "geometry.rectangle_area",
        "inputs": {"width": 3, "height": 4},
        "result": {"unit": "m^2", "value": 12},
        "assumptions": ["euclidean plane", "orthogonal sides"],
    }
    reordered = {
        "assumptions": ["euclidean plane", "orthogonal sides"],
        "result": {"value": 12, "unit": "m^2"},
        "inputs": {"height": 4, "width": 3},
        "solver": "geometry.rectangle_area",
    }
    receipt = verification_receipt("canonical-order", evidence)
    reordered_receipt = verification_receipt("canonical-order", reordered)
    assert receipt["evidence_sha256"] == reordered_receipt["evidence_sha256"]
    assert (
        validate_execution_verification_receipt(receipt)["evidence"]
        == validate_execution_verification_receipt(reordered_receipt)["evidence"]
    )

    reversed_list_receipt = verification_receipt(
        "canonical-order",
        {**copy.deepcopy(evidence), "assumptions": list(reversed(evidence["assumptions"]))},
    )
    assert receipt["evidence_sha256"] != reversed_list_receipt["evidence_sha256"]
    assert (
        validate_execution_verification_receipt(receipt)["evidence"]
        != validate_execution_verification_receipt(reversed_list_receipt)["evidence"]
    )

    accepted_storage = MemoryBackend()
    accepted_engine = BlueprintEngine(storage=accepted_storage)
    accepted = accepted_engine.learn_from_execution(
        make_workflow(tag="canonical-order"), verification=reordered_receipt,
    )
    assert accepted["ok"] is True
    reordered["result"]["value"] = 999
    stored = accepted_storage.load_one(accepted["data"]["id"])
    assert stored["verification"]["evidence"]["result"]["value"] == 12

    tampered = copy.deepcopy(receipt)
    tampered["evidence"]["result"]["value"] = 13
    rejected_storage = MemoryBackend()
    rejected_engine = BlueprintEngine(storage=rejected_storage)
    rejected = rejected_engine.learn_from_execution(
        make_workflow(tag="canonical-tamper"), verification=tampered,
    )
    assert rejected["ok"] is False
    assert rejected["code"] == "INVALID_EXECUTION_VERIFICATION_RECEIPT"
    assert rejected_storage.load_all() == []
