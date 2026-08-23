# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Validate host-supplied execution-verification receipts.

The receipt proves only that a host made a bounded, internally consistent
verification claim.  Blueprint does not execute or cryptographically attest
the physical or software event described by that claim.
"""
import hashlib
import json
import math
import re
from typing import Any, Dict


EXECUTION_VERIFICATION_RECEIPT_VERSION = "flyto.execution-verification-receipt.v1"
_FIELDS = frozenset({
    "receipt_version", "success", "status", "evidence_id",
    "evidence_sha256", "evidence",
})
_EVIDENCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECEIPT_BYTES = 36_000
_MAX_EVIDENCE_BYTES = 32_768
_MAX_EVIDENCE_DEPTH = 12
_MAX_EVIDENCE_NODES = 2_048
_MAX_STRING_CHARS = 4_096
_MAX_INTEGER = (1 << 53) - 1


def _canonicalize_evidence(evidence: Any) -> tuple[Dict[str, Any], bytes]:
    """Validate and detach one bounded, exact-JSON evidence object."""
    if type(evidence) is not dict:
        raise ValueError("verification receipt evidence must be a JSON object")

    nodes = 0

    def visit(value: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > _MAX_EVIDENCE_NODES:
            raise ValueError("verification receipt evidence exceeds v1 node limit")
        if depth > _MAX_EVIDENCE_DEPTH:
            raise ValueError("verification receipt evidence exceeds v1 depth limit")
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError("verification receipt evidence object keys must be strings")
                if len(key) > _MAX_STRING_CHARS:
                    raise ValueError(
                        "verification receipt evidence object key exceeds v1 length limit"
                    )
                visit(item, depth + 1)
        elif type(value) is list:
            for item in value:
                visit(item, depth + 1)
        elif type(value) is str:
            if len(value) > _MAX_STRING_CHARS:
                raise ValueError("verification receipt evidence string exceeds v1 length limit")
        elif type(value) is int:
            if not -_MAX_INTEGER <= value <= _MAX_INTEGER:
                raise ValueError("verification receipt evidence integer exceeds v1 safe range")
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError("verification receipt evidence float must be finite")
        elif value is None or type(value) is bool:
            pass
        else:
            raise ValueError("verification receipt evidence contains a non-JSON value")

    visit(evidence, 1)
    try:
        encoded = json.dumps(
            evidence, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("verification receipt evidence is not finite JSON") from exc
    if len(encoded) > _MAX_EVIDENCE_BYTES:
        raise ValueError("verification receipt evidence exceeds v1 byte limit")
    # Canonical JSON sorts nested object keys, preserves list order, and detaches exact JSON.
    return json.loads(encoded), encoded


def validate_execution_verification_receipt(
    receipt: Any,
    *,
    expected_outcome_success: Any = None,
    require_outcome_success: bool = False,
) -> Dict[str, Any]:
    """Return a detached canonical receipt or raise ``ValueError``.

    The v1 envelope is deliberately exact, while ``evidence`` is one nested,
    bounded, detached JSON object. Unknown fields, non-JSON containers,
    contradictory success/status values, and malformed evidence identity fail
    before learning can fingerprint, deduplicate, or persist.
    """
    if type(receipt) is not dict:
        raise ValueError("verification receipt must be a JSON object")
    if frozenset(receipt) != _FIELDS or any(type(key) is not str for key in receipt):
        raise ValueError("verification receipt fields do not match v1 contract")

    version = receipt["receipt_version"]
    success = receipt["success"]
    status = receipt["status"]
    evidence_id = receipt["evidence_id"]
    evidence_sha256 = receipt["evidence_sha256"]
    evidence = receipt["evidence"]
    if version != EXECUTION_VERIFICATION_RECEIPT_VERSION:
        raise ValueError("unsupported verification receipt version")
    if success is not True or status != "verified":
        raise ValueError("verification receipt must bind success=true and status=verified")
    if (
        type(evidence_id) is not str
        or not _EVIDENCE_ID.fullmatch(evidence_id)
        or ".." in evidence_id
        or "//" in evidence_id
    ):
        raise ValueError("verification receipt evidence_id is malformed")
    if type(evidence_sha256) is not str or not _SHA256.fullmatch(evidence_sha256):
        raise ValueError("verification receipt evidence_sha256 is malformed")
    detached_evidence, encoded_evidence = _canonicalize_evidence(evidence)
    if hashlib.sha256(encoded_evidence).hexdigest() != evidence_sha256:
        raise ValueError("verification receipt evidence_sha256 does not match evidence")
    if require_outcome_success:
        if type(expected_outcome_success) is not bool:
            raise ValueError("reported outcome success must be an exact boolean")
        if "outcome_success" not in detached_evidence:
            raise ValueError("verification receipt evidence must bind outcome_success")
        if type(detached_evidence["outcome_success"]) is not bool:
            raise ValueError("verification receipt outcome_success must be an exact boolean")
        if detached_evidence["outcome_success"] is not expected_outcome_success:
            raise ValueError("verification receipt outcome_success does not match reported outcome")

    canonical = {
        "receipt_version": version,
        "success": True,
        "status": status,
        "evidence_id": evidence_id,
        "evidence_sha256": evidence_sha256,
        "evidence": detached_evidence,
    }
    try:
        encoded = json.dumps(
            canonical, ensure_ascii=False, allow_nan=False,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("verification receipt is not finite JSON") from exc
    if len(encoded) > _MAX_RECEIPT_BYTES:
        raise ValueError("verification receipt exceeds v1 byte limit")
    return canonical
