# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Portable, integrity-checked Blueprint bundles for explicit sharing."""
import copy
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Mapping, Optional, Union


BUNDLE_FORMAT = "flyto-blueprint-bundle"
BUNDLE_VERSION = 1
TRUST_TIERS = ("community", "local_verified", "ci_verified", "official")

_INITIAL_SCORE_BY_TIER = {
    "community": 40,
    "local_verified": 60,
    "ci_verified": 70,
    "official": 80,
}
_EXPORT_FIELDS = (
    "id",
    "name",
    "description",
    "tags",
    "args",
    "compose",
    "connections",
    "steps",
    "fingerprint",
    "compatibility",
    "verification",
)
_DEFINITION_DIGEST_FIELDS = (
    "args",
    "compose",
    "connections",
    "steps",
    "compatibility",
)
_BLUEPRINT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|token|secret|api[_-]?key|authorization|cookie|private[_-]?key)",
    re.IGNORECASE,
)

SigningKey = Union[str, bytes]


def export_blueprint_bundle(
    blueprint: dict,
    *,
    publisher: str = "",
    claimed_tier: Optional[str] = None,
    evidence: Optional[dict] = None,
    signing_key: Optional[SigningKey] = None,
) -> dict:
    """Create a portable Blueprint bundle without uploading it anywhere.

    A SHA-256 digest always protects integrity. When ``signing_key`` is
    supplied, an HMAC signature lets a receiving host preserve the claimed
    trust tier if it has the matching publisher key.
    """
    validation_error = _validate_blueprint_definition(blueprint)
    if validation_error:
        return {"ok": False, "error": validation_error}

    definition = {
        field: copy.deepcopy(blueprint[field])
        for field in _EXPORT_FIELDS
        if field in blueprint
    }
    shared_evidence = copy.deepcopy(evidence or blueprint.get("verification", {}))
    sensitive_paths = _shared_sensitive_paths(definition, shared_evidence)
    if sensitive_paths:
        return {
            "ok": False,
            "error": "Blueprint contains non-parameterized sensitive values",
            "sensitive_paths": sensitive_paths,
        }

    tier = claimed_tier or blueprint.get("trust_tier", "community")
    if tier not in TRUST_TIERS:
        return {"ok": False, "error": "Unknown trust tier '{}'".format(tier)}
    if signing_key is not None and not publisher:
        return {"ok": False, "error": "Signed bundles require a publisher"}

    body = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "blueprint": definition,
        "provenance": {
            "publisher": publisher,
            "claimed_tier": tier,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "evidence": shared_evidence,
        },
    }
    payload = _canonical_bytes(body)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    bundle = copy.deepcopy(body)
    bundle["digest"] = digest
    if signing_key is not None:
        try:
            key = _key_bytes(signing_key)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
        bundle["signature"] = "hmac-sha256:" + signature

    return {"ok": True, "data": bundle}


def import_blueprint_bundle(
    bundle: dict,
    *,
    trusted_keys: Optional[Mapping[str, SigningKey]] = None,
) -> dict:
    """Validate a portable bundle and prepare a quarantined learned Blueprint.

    Unsigned bundles, unknown publishers, and invalid signatures are always
    downgraded to ``community``. A digest proves integrity, not publisher
    identity; only a signature verified with a host-configured key preserves a
    higher claimed tier.
    """
    if not isinstance(bundle, dict):
        return {"ok": False, "error": "Bundle must be an object"}
    if bundle.get("format") != BUNDLE_FORMAT:
        return {"ok": False, "error": "Unsupported Blueprint bundle format"}
    if bundle.get("version") != BUNDLE_VERSION:
        return {"ok": False, "error": "Unsupported Blueprint bundle version"}

    body = {
        "format": bundle.get("format"),
        "version": bundle.get("version"),
        "blueprint": bundle.get("blueprint"),
        "provenance": bundle.get("provenance"),
    }
    payload = _canonical_bytes(body)
    expected_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(str(bundle.get("digest", "")), expected_digest):
        return {"ok": False, "error": "Blueprint bundle digest mismatch"}

    definition = bundle.get("blueprint")
    validation_error = _validate_blueprint_definition(definition)
    if validation_error:
        return {"ok": False, "error": validation_error}

    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        return {"ok": False, "error": "Blueprint bundle provenance must be an object"}
    sensitive_paths = _shared_sensitive_paths(
        definition,
        provenance.get("evidence", {}),
    )
    if sensitive_paths:
        return {
            "ok": False,
            "error": "Blueprint bundle contains non-parameterized sensitive values",
            "sensitive_paths": sensitive_paths,
        }

    publisher = str(provenance.get("publisher", ""))
    claimed_tier = provenance.get("claimed_tier", "community")
    if claimed_tier not in TRUST_TIERS:
        claimed_tier = "community"

    signature_verified = _verify_signature(
        bundle.get("signature"),
        payload,
        publisher,
        trusted_keys or {},
    )
    trust_tier = claimed_tier if signature_verified else "community"

    imported = copy.deepcopy(definition)
    imported["trust_tier"] = trust_tier
    imported["score"] = _INITIAL_SCORE_BY_TIER[trust_tier]
    imported["use_count"] = 0
    imported["success_count"] = 0
    imported["fail_count"] = 0
    imported["community_success_count"] = 0
    imported["community_fail_count"] = 0
    imported["community_success_rate"] = None
    imported["last_used_at"] = None
    imported["retired"] = False
    imported["imported_at"] = datetime.now(timezone.utc).isoformat()
    imported["bundle_digest"] = expected_digest
    imported["provenance"] = {
        "publisher": publisher,
        "claimed_tier": claimed_tier,
        "signature_verified": signature_verified,
        "exported_at": provenance.get("exported_at"),
        "evidence": copy.deepcopy(provenance.get("evidence", {})),
    }

    return {
        "ok": True,
        "data": imported,
        "trust_tier": trust_tier,
        "signature_verified": signature_verified,
    }


def blueprint_definition_digest(blueprint: dict) -> str:
    """Return a stable semantic digest, excluding labels and mutable evidence."""
    definition = {
        field: copy.deepcopy(blueprint[field])
        for field in _DEFINITION_DIGEST_FIELDS
        if field in blueprint
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(definition)).hexdigest()


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _key_bytes(key: SigningKey) -> bytes:
    result = key if isinstance(key, bytes) else key.encode("utf-8")
    if len(result) < 16:
        raise ValueError("Blueprint signing keys must be at least 16 bytes")
    return result


def _verify_signature(
    signature: object,
    payload: bytes,
    publisher: str,
    trusted_keys: Mapping[str, SigningKey],
) -> bool:
    if not isinstance(signature, str) or not signature.startswith("hmac-sha256:"):
        return False
    key = trusted_keys.get(publisher)
    if key is None:
        return False
    try:
        key_bytes = _key_bytes(key)
    except ValueError:
        return False
    expected = hmac.new(key_bytes, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.removeprefix("hmac-sha256:"), expected)


def _shared_sensitive_paths(definition: dict, evidence: object) -> list:
    paths = _find_sensitive_paths(
        definition.get("steps", []),
        ("blueprint", "steps"),
    )
    paths.extend(_find_sensitive_paths(
        definition.get("compatibility", {}),
        ("blueprint", "compatibility"),
    ))
    paths.extend(_find_sensitive_paths(
        definition.get("verification", {}),
        ("blueprint", "verification"),
    ))
    paths.extend(_find_sensitive_paths(evidence, ("provenance", "evidence")))
    return sorted(set(paths))


def _validate_blueprint_definition(blueprint: object) -> Optional[str]:
    if not isinstance(blueprint, dict):
        return "Blueprint definition must be an object"
    blueprint_id = blueprint.get("id")
    if not isinstance(blueprint_id, str) or not _BLUEPRINT_ID_RE.fullmatch(blueprint_id):
        return "Blueprint ID is missing or invalid"
    steps = blueprint.get("steps", [])
    compose = blueprint.get("compose", [])
    if not isinstance(steps, list) or not isinstance(compose, list):
        return "Blueprint steps and compose fields must be arrays"
    if not steps and not compose:
        return "Blueprint must contain steps or composition blocks"
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not isinstance(step.get("module"), str):
            return "Blueprint step {} is invalid".format(index)
    return None


def _find_sensitive_paths(value: object, path: tuple) -> list:
    paths = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = path + (str(key),)
            if _SENSITIVE_KEY_RE.search(str(key)) and not _is_parameterized(child):
                paths.append(".".join(child_path))
            paths.extend(_find_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_find_sensitive_paths(child, path + (str(index),)))
    return sorted(set(paths))


def _is_parameterized(value: object) -> bool:
    if value in (None, "", [], {}):
        return True
    if isinstance(value, str):
        return "{{" in value and "}}" in value
    if isinstance(value, list):
        return all(_is_parameterized(item) for item in value)
    if isinstance(value, dict):
        return all(_is_parameterized(item) for item in value.values())
    return False
