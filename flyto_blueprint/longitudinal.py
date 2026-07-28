# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Real SQLite evidence for the complete Blueprint learning lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from flyto_blueprint.benchmark import canonical_digest
from flyto_blueprint.engine import BlueprintEngine
from flyto_blueprint.storage.sqlite import SQLiteBackend

SCHEMA_VERSION = "blueprint-longitudinal-evidence.v1"
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXPECTED_CHECKS = (
    "learned_and_persisted",
    "trusted_success_increased_score",
    "reused_without_relearning",
    "trusted_failures_decreased_score",
    "retired_below_threshold",
    "retirement_effective_immediately",
    "retirement_persisted_after_reload",
)


def run_longitudinal_evidence(
    db_path: str | Path,
    *,
    repository_commit: str,
    run_id: str,
    reuse_trials: int = 20,
    success_reports: int = 4,
) -> dict:
    """Exercise learn, reuse, downgrade, retirement, and reload via SQLite."""
    if not _COMMIT_RE.fullmatch(repository_commit):
        raise ValueError("repository_commit must be a lowercase Git commit")
    if not _ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a safe identifier")
    if (
        isinstance(reuse_trials, bool)
        or not isinstance(reuse_trials, int)
        or reuse_trials < 1
    ):
        raise ValueError("reuse_trials must be a positive integer")
    if (
        isinstance(success_reports, bool)
        or not isinstance(success_reports, int)
        or success_reports < 1
    ):
        raise ValueError("success_reports must be a positive integer")

    database = Path(db_path)
    if database.exists():
        raise ValueError("longitudinal database path must not already exist")
    database.parent.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    blueprint_id = "longitudinal-real-lifecycle"
    workflow = {
        "name": "Longitudinal real lifecycle",
        "steps": [
            {
                "id": "fetch",
                "module": "api.get",
                "params": {"url": "https://example.invalid/items"},
            },
            {
                "id": "sort",
                "module": "array.sort",
                "params": {"array": [3, 1, 2]},
            },
            {
                "id": "label",
                "module": "string.upper",
                "params": {"text": "verified"},
            },
        ],
    }

    storage = SQLiteBackend(db_path=str(database))
    engine = BlueprintEngine(storage=storage)
    learned = engine.learn_from_workflow(
        workflow,
        blueprint_id=blueprint_id,
        name="Longitudinal real lifecycle",
        tags=["longitudinal", "lifecycle", "sqlite"],
        verified=True,
        trust_tier="ci_verified",
    )
    if not learned.get("ok"):
        raise RuntimeError("real lifecycle could not learn the Blueprint")
    initial = _required_record(storage, blueprint_id)
    initial_score = _score(initial)

    promotion_scores = []
    for index in range(success_reports):
        outcome = engine.report_outcome(
            blueprint_id,
            True,
            execution_id="{}-success-{}".format(run_id, index),
            evidence_tier="ci_verified",
            evidence=_execution_evidence(success=True),
        )
        if not outcome.get("ok"):
            raise RuntimeError("trusted success report failed")
        promotion_scores.append(_score(_required_record(storage, blueprint_id)))

    successful_reuses = 0
    for _ in range(reuse_trials):
        expanded = engine.expand(
            blueprint_id,
            {
                "url": "https://example.invalid/items",
                "array": [3, 1, 2],
                "text": "verified",
            },
        )
        successful_reuses += int(expanded.get("ok") is True)
    after_reuse = _required_record(storage, blueprint_id)

    downgrade_scores = []
    failure_index = 0
    while not _required_record(storage, blueprint_id).get("retired"):
        outcome = engine.report_outcome(
            blueprint_id,
            False,
            execution_id="{}-failure-{}".format(run_id, failure_index),
            evidence_tier="ci_verified",
            evidence=_execution_evidence(success=False),
        )
        if not outcome.get("ok"):
            raise RuntimeError("trusted failure report failed")
        downgrade_scores.append(_score(_required_record(storage, blueprint_id)))
        failure_index += 1
        if failure_index > 20:
            raise RuntimeError("Blueprint did not retire within 20 failures")

    retired = _required_record(storage, blueprint_id)
    immediate_expand = engine.expand(
        blueprint_id,
        {
            "url": "https://example.invalid/items",
            "array": [3, 1, 2],
            "text": "verified",
        },
    )
    reloaded = BlueprintEngine(
        storage=SQLiteBackend(db_path=str(database))
    )
    reloaded_ids = {item["id"] for item in reloaded.list_blueprints()}
    reloaded_expand = reloaded.expand(
        blueprint_id,
        {
            "url": "https://example.invalid/items",
            "array": [3, 1, 2],
            "text": "verified",
        },
    )

    checks = {
        "learned_and_persisted": initial.get("id") == blueprint_id,
        "trusted_success_increased_score": (
            len(promotion_scores) == success_reports
            and promotion_scores[-1] > initial_score
        ),
        "reused_without_relearning": (
            successful_reuses == reuse_trials
            and int(after_reuse.get("use_count", 0)) >= reuse_trials
        ),
        "trusted_failures_decreased_score": (
            bool(downgrade_scores)
            and downgrade_scores[-1] < promotion_scores[-1]
            and all(
                later < earlier
                for earlier, later in zip(
                    [promotion_scores[-1], *downgrade_scores[:-1]],
                    downgrade_scores,
                )
            )
        ),
        "retired_below_threshold": (
            retired.get("retired") is True and _score(retired) < 10
        ),
        "retirement_effective_immediately": not immediate_expand.get("ok"),
        "retirement_persisted_after_reload": (
            blueprint_id not in reloaded_ids and not reloaded_expand.get("ok")
        ),
    }
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_started_at": started_at,
        "run_finished_at": _utc_now(),
        "repository_commit": repository_commit,
        "storage_backend": "sqlite",
        "database_digest": _file_digest(database),
        "blueprint_id": blueprint_id,
        "initial_score": initial_score,
        "promotion_scores": promotion_scores,
        "successful_reuses": successful_reuses,
        "reuse_trials": reuse_trials,
        "persisted_use_count": int(after_reuse.get("use_count", 0)),
        "downgrade_scores": downgrade_scores,
        "trusted_failure_reports": failure_index,
        "retired_score": _score(retired),
        "retired": retired.get("retired") is True,
        "checks": [
            {"id": check_id, "passed": checks[check_id]}
            for check_id in _EXPECTED_CHECKS
        ],
        "proof_status": (
            "verified" if all(checks.values()) else "regression"
        ),
        "limitations": [
            (
                "This evidence proves the local Blueprint/SQLite lifecycle; "
                "it does not claim that every external workflow will succeed."
            )
        ],
    }
    evidence["evidence_digest"] = canonical_digest(evidence)
    return evidence


def verify_longitudinal_evidence(evidence: Mapping[str, Any]) -> dict:
    """Fail closed when lifecycle evidence is malformed, edited, or regressed."""
    issues = []
    if not isinstance(evidence, Mapping):
        return {"passed": False, "issues": ["evidence must be an object"]}
    if evidence.get("schema_version") != SCHEMA_VERSION:
        issues.append("unsupported schema_version")
    if not _ID_RE.fullmatch(str(evidence.get("run_id", ""))):
        issues.append("invalid run_id")
    if not _COMMIT_RE.fullmatch(str(evidence.get("repository_commit", ""))):
        issues.append("invalid repository_commit")
    if not _DIGEST_RE.fullmatch(str(evidence.get("database_digest", ""))):
        issues.append("invalid database_digest")
    checks = evidence.get("checks")
    if (
        not isinstance(checks, list)
        or [item.get("id") for item in checks if isinstance(item, Mapping)]
        != list(_EXPECTED_CHECKS)
        or len(checks) != len(_EXPECTED_CHECKS)
    ):
        issues.append("lifecycle checks are missing or reordered")
    elif any(item.get("passed") is not True for item in checks):
        issues.append("one or more lifecycle checks failed")
    if evidence.get("proof_status") != "verified":
        issues.append("proof_status is not verified")
    supplied_digest = evidence.get("evidence_digest")
    without_digest = dict(evidence)
    without_digest.pop("evidence_digest", None)
    if supplied_digest != canonical_digest(without_digest):
        issues.append("evidence_digest mismatch")
    return {
        "passed": not issues,
        "status": "verified" if not issues else "failed",
        "issues": issues,
    }


def write_longitudinal_evidence(
    evidence: Mapping[str, Any],
    path: str | Path,
) -> None:
    """Write canonical lifecycle evidence without prompts or workflow outputs."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            evidence,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run or verify the real longitudinal lifecycle from the command line."""
    parser = argparse.ArgumentParser(
        description="Run or verify real Blueprint SQLite lifecycle evidence."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--database", required=True)
    run_parser.add_argument("--repository-commit", required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--reuse-trials", type=int, default=20)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--evidence", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            output = Path(args.output)
            if output.exists():
                raise ValueError("output path must not already exist")
            evidence = run_longitudinal_evidence(
                args.database,
                repository_commit=args.repository_commit,
                run_id=args.run_id,
                reuse_trials=args.reuse_trials,
            )
            write_longitudinal_evidence(evidence, output)
            result = verify_longitudinal_evidence(evidence)
        else:
            raw = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
            result = verify_longitudinal_evidence(raw)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


def _required_record(storage: SQLiteBackend, blueprint_id: str) -> dict:
    record = storage.load_one(blueprint_id)
    if not isinstance(record, dict):
        raise RuntimeError("Blueprint was not persisted to SQLite")
    return record


def _score(record: Mapping[str, Any]) -> int:
    value = record.get("score")
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError("persisted Blueprint score is not an integer")
    return value


def _execution_evidence(*, success: bool) -> dict:
    return {
        "duration_ms": 1,
        "step_count": 3,
        "total_attempts": 3,
        "assertion_passed": success,
        "planner_model_calls_used": 0,
    }


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
