# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Blueprint scoring: outcome reporting, boosting, use tracking, auto-retire."""
import hashlib
import logging
import math
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flyto_blueprint.storage.base import StorageBackend

logger = logging.getLogger(__name__)

_RECENT_REPORTS_MAX = 200
_EVIDENCE_SAMPLE_LIMIT = 100
_TRUST_TIER_RANK = {
    "community": 0,
    "local_verified": 1,
    "ci_verified": 2,
    "official": 3,
}
_SAFE_EVIDENCE_TEXT = re.compile(r"^[A-Za-z0-9._:+/-]{1,100}$")
_SHA256_DIGEST = re.compile(r"^(?:sha256:)?[a-fA-F0-9]{64}$")


def evidence_card(blueprint: dict) -> dict:
    """Summarize trusted outcomes without inventing token-savings estimates."""
    successes = max(0, int(blueprint.get("success_count", 0)))
    failures = max(0, int(blueprint.get("fail_count", 0)))
    outcome_count = successes + failures
    success_rate = round(successes / outcome_count, 4) if outcome_count else None

    raw_samples = blueprint.get("evidence_samples", [])
    samples = [item for item in raw_samples if isinstance(item, dict)]
    durations = [
        float(item["duration_ms"])
        for item in samples
        if _is_bounded_number(item.get("duration_ms"), maximum=604_800_000)
    ]
    retry_samples = [
        item
        for item in samples
        if _is_bounded_int(item.get("step_count"), maximum=1_000_000)
        and _is_bounded_int(item.get("total_attempts"), maximum=1_000_000)
    ]
    retry_runs = sum(
        int(item["total_attempts"]) > int(item["step_count"])
        for item in retry_samples
    )
    assertion_samples = [
        item for item in samples if isinstance(item.get("assertion_passed"), bool)
    ]
    assertion_passes = sum(item["assertion_passed"] for item in assertion_samples)
    model_call_samples = [
        item
        for item in samples
        if _is_bounded_int(item.get("model_calls_used"), maximum=10_000)
    ]
    zero_llm_reuse_count = sum(
        int(item["model_calls_used"]) == 0 for item in model_call_samples
    )
    planner_model_call_samples = [
        item
        for item in samples
        if _is_bounded_int(item.get("planner_model_calls_used"), maximum=10_000)
    ]
    zero_planner_model_call_count = sum(
        int(item["planner_model_calls_used"]) == 0
        for item in planner_model_call_samples
    )

    return {
        "status": (
            "no_evidence"
            if outcome_count == 0
            else "collecting"
            if outcome_count < 5
            else "measured"
        ),
        "sample_count": outcome_count,
        "detailed_sample_count": len(samples),
        "success_count": successes,
        "failure_count": failures,
        "success_rate": success_rate,
        "wilson_95_lower_bound": _wilson_lower_bound(successes, outcome_count),
        "duration_sample_count": len(durations),
        "duration_ms_p50": _percentile(durations, 0.50),
        "duration_ms_p95": _percentile(durations, 0.95),
        "retry_sample_count": len(retry_samples),
        "retry_run_count": retry_runs,
        "retry_rate": (
            round(retry_runs / len(retry_samples), 4) if retry_samples else None
        ),
        "assertion_sample_count": len(assertion_samples),
        "assertion_pass_count": assertion_passes,
        "assertion_pass_rate": (
            round(assertion_passes / len(assertion_samples), 4)
            if assertion_samples
            else None
        ),
        "model_call_sample_count": len(model_call_samples),
        "planner_model_call_sample_count": len(planner_model_call_samples),
        "zero_planner_model_call_count": zero_planner_model_call_count,
        "zero_planner_model_call_rate": (
            round(
                zero_planner_model_call_count / len(planner_model_call_samples),
                4,
            )
            if planner_model_call_samples
            else None
        ),
        # Deprecated compatibility aliases. These predate explicit call scope
        # and must not be interpreted as workflow-wide token measurements.
        "zero_llm_reuse_count": zero_llm_reuse_count,
        "zero_llm_reuse_rate": (
            round(zero_llm_reuse_count / len(model_call_samples), 4)
            if model_call_samples
            else None
        ),
        "evidence_window_limit": _EVIDENCE_SAMPLE_LIMIT,
    }


def report_outcome(
    blueprint_id: str,
    success: bool,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
    execution_id: str = "",
    recent_reports: Optional[Dict[str, float]] = None,
    evidence_tier: str = "local_verified",
    evidence: Optional[dict] = None,
) -> dict:
    """Report whether a blueprint-generated workflow succeeded or failed.

    Trusted success: +5 (cap 100). Trusted failure: -10 (floor 0).
    Community observations update separate Bayesian counters and can influence
    ranking within a small cap, but never directly change the trusted score.

    The in-memory *blueprints* dict is the source of truth; changes are
    persisted to *storage* afterwards on a best-effort basis.
    """
    if evidence_tier not in _TRUST_TIER_RANK:
        return {"ok": False, "error": "Unknown evidence tier '{}'".format(evidence_tier)}
    if evidence_tier == "community" and not execution_id:
        return {
            "ok": False,
            "error": "Community observations require an execution_id",
        }

    bp = blueprints.get(blueprint_id)
    if not bp:
        return {"ok": False, "error": "Blueprint '{}' not found".format(blueprint_id)}

    # Dedup
    if execution_id and recent_reports is not None:
        if execution_id in recent_reports:
            return {
                "ok": True,
                "blueprint_id": blueprint_id,
                "skipped": "already_reported",
                "evidence_card": evidence_card(bp),
            }
        recent_reports[execution_id] = time.time()
        if len(recent_reports) > _RECENT_REPORTS_MAX:
            cutoff = time.time() - 3600
            stale = [k for k, v in recent_reports.items() if v <= cutoff]
            for k in stale:
                del recent_reports[k]

    if evidence_tier == "community":
        return _record_community_observation(
            blueprint_id,
            success,
            bp,
            storage,
        )

    # Compute new values from in-memory state
    old_score = bp.get("score", 50)
    if success:
        new_score = min(100, old_score + 5)
        bp["success_count"] = bp.get("success_count", 0) + 1
    else:
        new_score = max(0, old_score - 10)
        bp["fail_count"] = bp.get("fail_count", 0) + 1

    bp["score"] = new_score
    current_tier = bp.get("trust_tier", "community")
    if success and _TRUST_TIER_RANK[evidence_tier] > _TRUST_TIER_RANK.get(current_tier, 0):
        bp["trust_tier"] = evidence_tier
    bp["last_evidence_tier"] = evidence_tier
    bp["last_verified_at"] = datetime.now(timezone.utc).isoformat()
    normalized_evidence = _normalize_evidence(
        evidence,
        success=success,
        evidence_tier=evidence_tier,
        execution_id=execution_id,
        observed_at=bp["last_verified_at"],
    )
    if normalized_evidence is not None:
        samples = [
            item
            for item in bp.get("evidence_samples", [])
            if isinstance(item, dict)
        ]
        samples.append(normalized_evidence)
        bp["evidence_samples"] = samples[-_EVIDENCE_SAMPLE_LIMIT:]
    retired = new_score < 10
    if retired:
        bp["retired"] = True
        logger.info("Blueprint '%s' auto-retired (score=%d)", blueprint_id, new_score)

    # Best-effort persist to storage
    if storage is not None:
        try:
            fields = {
                "score": new_score,
                "success_count": bp.get("success_count", 0),
                "fail_count": bp.get("fail_count", 0),
                "retired": retired,
                "trust_tier": bp.get("trust_tier", "community"),
                "last_evidence_tier": evidence_tier,
                "last_verified_at": bp["last_verified_at"],
            }
            if normalized_evidence is not None:
                fields["evidence_samples"] = bp["evidence_samples"]
            storage.update(blueprint_id, fields)
        except Exception:
            pass

    return {
        "ok": True,
        "blueprint_id": blueprint_id,
        "score": new_score,
        "success_count": bp.get("success_count", 0),
        "fail_count": bp.get("fail_count", 0),
        "retired": retired,
        "trust_tier": bp.get("trust_tier", "community"),
        "evidence_tier": evidence_tier,
        "score_changed": True,
        "evidence_card": evidence_card(bp),
    }


def _normalize_evidence(
    evidence: Optional[dict],
    *,
    success: bool,
    evidence_tier: str,
    execution_id: str,
    observed_at: str,
) -> Optional[dict]:
    """Keep a small allowlist of execution facts and discard arbitrary payloads."""
    if not isinstance(evidence, dict):
        return None

    sample: Dict[str, Any] = {
        "success": success,
        "evidence_tier": evidence_tier,
        "observed_at": observed_at,
    }
    if execution_id:
        digest = hashlib.sha256(execution_id.encode("utf-8")).hexdigest()
        sample["execution_ref"] = "sha256:{}".format(digest)

    duration = evidence.get("duration_ms")
    if _is_bounded_number(duration, maximum=604_800_000):
        sample["duration_ms"] = round(float(duration), 3)

    for field, maximum in (
        ("step_count", 1_000_000),
        ("total_attempts", 1_000_000),
        ("model_calls_used", 10_000),
        ("planner_model_calls_used", 10_000),
    ):
        value = evidence.get(field)
        if _is_bounded_int(value, maximum=maximum):
            sample[field] = int(value)

    model_call_scope = evidence.get("model_call_scope")
    if model_call_scope == "planner":
        sample["model_call_scope"] = "planner"
        if (
            "planner_model_calls_used" not in sample
            and "model_calls_used" in sample
        ):
            sample["planner_model_calls_used"] = sample["model_calls_used"]

    assertion_passed = evidence.get("assertion_passed")
    if isinstance(assertion_passed, bool):
        sample["assertion_passed"] = assertion_passed

    workflow_hash = evidence.get("workflow_hash")
    if isinstance(workflow_hash, str) and _SHA256_DIGEST.fullmatch(workflow_hash):
        sample["workflow_hash"] = workflow_hash.lower()

    for field in ("selection_mode", "executor_version"):
        value = evidence.get(field)
        if isinstance(value, str) and _SAFE_EVIDENCE_TEXT.fullmatch(value):
            sample[field] = value

    return sample


def _is_bounded_number(value: Any, *, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= float(value) <= maximum
    )


def _is_bounded_int(value: Any, *, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= maximum
    )


def _wilson_lower_bound(successes: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    z = 1.96
    probability = successes / total
    denominator = 1 + (z * z / total)
    center = probability + (z * z / (2 * total))
    spread = z * math.sqrt(
        (probability * (1 - probability) / total)
        + (z * z / (4 * total * total))
    )
    return round(max(0.0, (center - spread) / denominator), 4)


def _percentile(values: List[float], quantile: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * weight
    return round(value, 3)


def effective_quality_score(blueprint: dict) -> float:
    """Blend trusted score with a capped, confidence-weighted community signal."""
    base_score = float(max(0, min(100, blueprint.get("score", 50))))
    successes = max(0, int(blueprint.get("community_success_count", 0)))
    failures = max(0, int(blueprint.get("community_fail_count", 0)))
    total = successes + failures
    if total < 3:
        return base_score

    # Beta(2, 2) prior avoids extreme scores from a handful of observations.
    posterior_success = (successes + 2.0) / (total + 4.0)
    confidence = min(1.0, total / 20.0)
    adjustment = (posterior_success - 0.5) * 20.0 * confidence
    return round(max(0.0, min(100.0, base_score + adjustment)), 2)


def _record_community_observation(
    blueprint_id: str,
    success: bool,
    blueprint: dict,
    storage: Optional[StorageBackend],
) -> dict:
    if success:
        key = "community_success_count"
    else:
        key = "community_fail_count"
    blueprint[key] = blueprint.get(key, 0) + 1

    successes = blueprint.get("community_success_count", 0)
    failures = blueprint.get("community_fail_count", 0)
    total = successes + failures
    success_rate = round((successes + 2.0) / (total + 4.0), 4)
    blueprint["community_success_rate"] = success_rate
    blueprint["last_community_observed_at"] = datetime.now(timezone.utc).isoformat()

    fields = {
        "community_success_count": successes,
        "community_fail_count": failures,
        "community_success_rate": success_rate,
        "last_community_observed_at": blueprint["last_community_observed_at"],
    }
    if storage is not None:
        try:
            storage.update(blueprint_id, fields)
        except Exception:
            pass

    return {
        "ok": True,
        "blueprint_id": blueprint_id,
        "score": blueprint.get("score", 50),
        "effective_score": effective_quality_score(blueprint),
        "community_success_count": successes,
        "community_fail_count": failures,
        "community_success_rate": success_rate,
        "evidence_tier": "community",
        "score_changed": False,
        "retired": blueprint.get("retired", False),
        "evidence_card": evidence_card(blueprint),
    }


def boost_score(
    blueprint_id: str,
    delta: int,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
) -> None:
    """Increase a blueprint's score by *delta* (clamped 0–100)."""
    bp = blueprints.get(blueprint_id)
    if not bp:
        return
    bp["score"] = min(100, max(0, bp.get("score", 50) + delta))
    if storage is not None:
        try:
            storage.update(blueprint_id, {"score": bp["score"]})
        except Exception:
            pass


def record_use(
    blueprint_id: str,
    blueprints: Dict[str, dict],
    storage: Optional[StorageBackend] = None,
) -> None:
    """Record that a blueprint was used (expand).

    Only tracks count — no score change. Score should only change from
    verified outcomes.
    """
    bp = blueprints.get(blueprint_id)
    if not bp:
        return
    bp["use_count"] = bp.get("use_count", 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    bp["last_used_at"] = now
    if storage is not None:
        try:
            storage.update(blueprint_id, {
                "use_count": bp["use_count"],
                "last_used_at": now,
            })
        except Exception:
            pass
