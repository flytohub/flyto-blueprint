# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Tests for portable Blueprint bundles and trust quarantine."""
import copy

from conftest import verification_receipt

from flyto_blueprint import BlueprintEngine
from flyto_blueprint.sharing import (
    blueprint_definition_digest,
    export_blueprint_bundle,
    import_blueprint_bundle,
)
from flyto_blueprint.storage.memory import MemoryBackend


def _blueprint():
    return {
        "id": "shared_api_pattern",
        "name": "Shared API pattern",
        "description": "Fetch, transform, and store an API response",
        "tags": ["api", "shared"],
        "args": {
            "url": {"type": "string", "required": True},
            "api_token": {"type": "string", "required": True},
        },
        "steps": [
            {
                "id": "fetch",
                "module": "api.get",
                "params": {
                    "url": "{{url}}",
                    "headers": {"Authorization": "Bearer {{api_token}}"},
                },
            },
            {
                "id": "transform",
                "module": "data.transform",
                "params": {"value": "{{value}}"},
            },
            {
                "id": "save",
                "module": "file.write",
                "params": {"path": "{{path}}", "content": "{{content}}"},
            },
        ],
        "fingerprint": "abc123",
        "trust_tier": "official",
    }


def test_unsigned_bundle_is_quarantined_as_community():
    exported = export_blueprint_bundle(
        _blueprint(),
        publisher="community-user",
        claimed_tier="official",
    )

    imported = import_blueprint_bundle(exported["data"])

    assert imported["ok"] is True
    assert imported["trust_tier"] == "community"
    assert imported["signature_verified"] is False
    assert imported["data"]["score"] == 40


def test_trusted_signature_preserves_claimed_tier():
    signing_key = "ci-signing-key-at-least-16-bytes"
    exported = export_blueprint_bundle(
        _blueprint(),
        publisher="flyto-ci",
        claimed_tier="ci_verified",
        signing_key=signing_key,
    )

    imported = import_blueprint_bundle(
        exported["data"],
        trusted_keys={"flyto-ci": signing_key},
    )

    assert imported["ok"] is True
    assert imported["trust_tier"] == "ci_verified"
    assert imported["signature_verified"] is True
    assert imported["data"]["score"] == 70


def test_tampered_bundle_is_rejected():
    exported = export_blueprint_bundle(_blueprint())
    tampered = copy.deepcopy(exported["data"])
    tampered["blueprint"]["steps"][0]["module"] = "shell.exec"

    imported = import_blueprint_bundle(tampered)

    assert imported["ok"] is False
    assert "digest mismatch" in imported["error"]


def test_non_parameterized_secret_is_rejected():
    blueprint = _blueprint()
    blueprint["steps"][0]["params"]["api_key"] = "plain-text-secret"

    exported = export_blueprint_bundle(blueprint)

    assert exported["ok"] is False
    assert exported["sensitive_paths"] == [
        "blueprint.steps.0.params.api_key",
    ]


def test_sensitive_verification_evidence_is_rejected():
    blueprint = _blueprint()
    blueprint["verification"] = {"api_token": "plain-text-secret"}

    exported = export_blueprint_bundle(blueprint)

    assert exported["ok"] is False
    assert exported["sensitive_paths"] == [
        "blueprint.verification.api_token",
        "provenance.evidence.api_token",
    ]


def test_signed_bundle_requires_publisher_and_strong_key():
    no_publisher = export_blueprint_bundle(
        _blueprint(),
        signing_key="long-enough-signing-key",
    )
    weak_key = export_blueprint_bundle(
        _blueprint(),
        publisher="flyto-ci",
        signing_key="weak",
    )

    assert no_publisher["ok"] is False
    assert "publisher" in no_publisher["error"]
    assert weak_key["ok"] is False
    assert "16 bytes" in weak_key["error"]


def test_definition_digest_ignores_mutable_scores():
    blueprint = _blueprint()
    digest = blueprint_definition_digest(blueprint)
    blueprint["score"] = 99
    blueprint["success_count"] = 1000

    assert blueprint_definition_digest(blueprint) == digest


def test_definition_digest_ignores_labels_but_keeps_compatibility():
    blueprint = _blueprint()
    digest = blueprint_definition_digest(blueprint)
    blueprint["id"] = "renamed"
    blueprint["name"] = "Different label"
    blueprint["description"] = "Different prose"
    blueprint["verification"] = {"run": "new"}

    assert blueprint_definition_digest(blueprint) == digest
    blueprint["compatibility"] = {"repository": "flytohub/other"}
    assert blueprint_definition_digest(blueprint) != digest


def test_engine_round_trip_preserves_repo_compatibility():
    signing_key = "ci-signing-key-at-least-16-bytes"
    source = BlueprintEngine(storage=MemoryBackend())
    workflow = {
        "name": "FastAPI endpoint",
        "description": "Add and verify a repository endpoint",
        "steps": copy.deepcopy(_blueprint()["steps"]),
    }
    learned = source.learn_from_execution(
        workflow,
        name="fastapi_endpoint",
        compatibility={
            "repository": "flytohub/example-api",
            "framework": "fastapi",
            "python": ">=3.10",
        },
        verification=verification_receipt("ci-run-123"),
    )

    exported = source.export_blueprint(
        learned["data"]["id"],
        publisher="flyto-ci",
        claimed_tier="ci_verified",
        signing_key=signing_key,
    )
    target = BlueprintEngine(storage=MemoryBackend())
    imported = target.import_blueprint(
        exported["data"],
        trusted_keys={"flyto-ci": signing_key},
    )

    assert imported["ok"] is True
    assert imported["trust_tier"] == "ci_verified"
    imported_id = imported["data"]["id"]
    assert target._blueprints[imported_id]["compatibility"]["framework"] == "fastapi"
    assert target._blueprints[imported_id]["verification"]["evidence_id"] == "ci-run-123"


def test_same_structure_in_different_repositories_is_not_deduplicated():
    engine = BlueprintEngine(storage=MemoryBackend())
    workflow = {
        "name": "Repository pattern",
        "steps": copy.deepcopy(_blueprint()["steps"]),
    }

    first = engine.learn_from_execution(
        workflow,
        name="repo_a",
        compatibility={"repository": "flytohub/repo-a"},
        verification=verification_receipt("repo-a"),
    )
    second = engine.learn_from_execution(
        workflow,
        name="repo_b",
        compatibility={"repository": "flytohub/repo-b"},
        verification=verification_receipt("repo-b", {"solver": "repo-b", "result": {"value": 2}}),
    )

    assert first["data"]["id"] != second["data"]["id"]
