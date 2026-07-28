# Copyright 2024 Flyto2
# Licensed under the Apache License, Version 2.0
"""Reproducible scorecards for host-executed Blueprint benchmarks.

This module never executes an agent or workflow. A trusted host records paired
runs, then this module validates their identity, computes measurements, and
decides whether the configured evidence gates pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

SUITE_SCHEMA = "benchmark-suite.v1"
RUN_SCHEMA = "benchmark-run.v1"
RUN_SCHEMA_V2 = "benchmark-run.v2"
SCORECARD_SCHEMA = "benchmark-scorecard.v1"
SCORECARD_SCHEMA_V2 = "benchmark-scorecard.v2"
REQUIRED_MODES = (
    "agent_baseline",
    "flyto_no_blueprint",
    "blueprint_cold",
    "blueprint_warm",
)
ALLOWED_SPLITS = {"public_eval", "adversarial", "sealed_holdout"}
ALLOWED_RUNNER_KINDS = {"local", "independent_ci"}
ALLOWED_WORKLOAD_KINDS = {
    "api",
    "browser",
    "coding",
    "compatibility",
    "conversation",
    "llm",
    "sealed",
    "trust",
}
VERIFIED_EVIDENCE_TIER = "ci_verified"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
_SAFE_TEXT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_SUITE_FIELDS = {
    "schema_version",
    "suite_id",
    "suite_version",
    "description",
    "required_modes",
    "trusted_evidence_tier",
    "thresholds",
    "tasks",
    "measurement",
}
_THRESHOLD_FIELDS = {
    "min_trials_per_task",
    "max_success_rate_drop",
    "min_candidate_wilson_lower_bound",
    "min_planner_token_reduction",
    "max_p95_latency_increase",
    "max_false_reuse_count",
    "min_assertion_pass_rate",
    "required_splits",
}
_TASK_FIELDS = {
    "id",
    "split",
    "sealed",
    "prompt",
    "expected_behavior",
    "assertions",
    "tags",
    "task_digest",
}
_MEASUREMENT_FIELDS = {
    "scope",
    "required_workload_kinds",
    "min_full_token_reduction",
    "max_manual_corrections",
    "min_workload_success_rate",
    "min_model_families",
    "min_hardware_families",
    "require_independent_runner",
    "min_history_comparisons",
    "max_history_success_drop",
    "max_history_total_token_increase",
}
_RUN_FIELDS = {
    "schema_version",
    "suite_id",
    "suite_digest",
    "dataset_commit",
    "task_id",
    "task_digest",
    "split",
    "mode",
    "trial",
    "seed",
    "model_id",
    "environment_digest",
    "evidence_tier",
    "success",
    "assertions_passed",
    "assertions_total",
    "planner_input_tokens",
    "planner_output_tokens",
    "planner_model_calls",
    "tool_calls",
    "retries",
    "duration_ms",
    "false_reuse",
    "visible_cost_usd",
}
_RUN_V2_FIELDS = _RUN_FIELDS | {
    "run_id",
    "run_started_at",
    "host_id",
    "hardware_family",
    "runner_kind",
    "model_family",
    "workload_kind",
    "workload_digest",
    "workload_success",
    "workflow_input_tokens",
    "workflow_output_tokens",
    "workflow_model_calls",
    "workflow_duration_ms",
    "manual_corrections",
    "planner_visible_cost_usd",
    "workflow_visible_cost_usd",
    "total_input_tokens",
    "total_output_tokens",
    "total_model_calls",
    "total_visible_cost_usd",
}


class BenchmarkValidationError(ValueError):
    """Raised when benchmark evidence is malformed or cannot be compared."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict:
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise BenchmarkValidationError("YAML mapping keys must be strings")
        if key in mapping:
            raise BenchmarkValidationError(
                "duplicate YAML mapping key '{}'".format(key)
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def canonical_digest(value: Any) -> str:
    """Return a stable SHA-256 digest for JSON-compatible data."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def task_digest(task: Mapping[str, Any]) -> str:
    """Return the public task digest or an opaque sealed-task commitment."""
    if task.get("sealed") is True:
        digest = task.get("task_digest")
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise BenchmarkValidationError(
                "sealed task '{}' needs a SHA-256 task_digest".format(
                    task.get("id", "<unknown>")
                )
            )
        return digest
    public_task = dict(task)
    public_task.pop("task_digest", None)
    return canonical_digest(public_task)


def suite_digest(suite: Mapping[str, Any]) -> str:
    """Validate and bind a benchmark suite to its exact contents."""
    validate_suite(suite)
    return canonical_digest(suite)


def load_suite(path: str | Path) -> dict:
    """Load and validate a versioned YAML benchmark suite."""
    suite_path = Path(path)
    data = yaml.load(
        suite_path.read_text(encoding="utf-8"),
        Loader=_UniqueKeyLoader,
    )
    if not isinstance(data, dict):
        raise BenchmarkValidationError("benchmark suite must be a YAML object")
    validate_suite(data)
    return data


def load_runs(path: str | Path) -> list[dict]:
    """Load benchmark-run.v1 JSON objects from a JSON Lines file."""
    records = []
    for line_number, raw_line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(
                raw_line,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (json.JSONDecodeError, BenchmarkValidationError) as exc:
            raise BenchmarkValidationError(
                "invalid JSON on run line {}: {}".format(line_number, exc)
            ) from exc
        if not isinstance(record, dict):
            raise BenchmarkValidationError(
                "run line {} must contain a JSON object".format(line_number)
            )
        records.append(record)
    if not records:
        raise BenchmarkValidationError("run file contains no records")
    return records


def validate_suite(suite: Mapping[str, Any]) -> None:
    """Reject ambiguous suites before any score is calculated."""
    if not isinstance(suite, Mapping):
        raise BenchmarkValidationError("benchmark suite must be an object")
    _reject_unknown_fields(suite, _SUITE_FIELDS, "suite")
    if suite.get("schema_version") != SUITE_SCHEMA:
        raise BenchmarkValidationError("suite schema_version must be " + SUITE_SCHEMA)
    _require_id(suite.get("suite_id"), "suite_id")
    _require_int(suite.get("suite_version"), "suite_version", minimum=1)
    _require_text(suite.get("description"), "description")

    modes = suite.get("required_modes")
    if tuple(modes or ()) != REQUIRED_MODES:
        raise BenchmarkValidationError(
            "required_modes must contain the four canonical comparison modes"
        )
    if suite.get("trusted_evidence_tier") != VERIFIED_EVIDENCE_TIER:
        raise BenchmarkValidationError(
            "trusted_evidence_tier must be " + VERIFIED_EVIDENCE_TIER
        )

    thresholds = suite.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise BenchmarkValidationError("thresholds must be an object")
    _reject_unknown_fields(thresholds, _THRESHOLD_FIELDS, "thresholds")
    _require_int(
        thresholds.get("min_trials_per_task"),
        "min_trials_per_task",
        minimum=1,
    )
    for field in (
        "max_success_rate_drop",
        "min_candidate_wilson_lower_bound",
        "min_planner_token_reduction",
        "min_assertion_pass_rate",
    ):
        _require_number(thresholds.get(field), field, minimum=0, maximum=1)
    _require_number(
        thresholds.get("max_p95_latency_increase"),
        "max_p95_latency_increase",
        minimum=0,
    )
    _require_int(
        thresholds.get("max_false_reuse_count"),
        "max_false_reuse_count",
        minimum=0,
    )
    required_splits = thresholds.get("required_splits")
    if (
        not isinstance(required_splits, list)
        or not required_splits
        or len(required_splits) != len(set(required_splits))
        or not set(required_splits).issubset(ALLOWED_SPLITS)
    ):
        raise BenchmarkValidationError(
            "required_splits must be a unique, non-empty list of known splits"
        )

    measurement = suite.get("measurement")
    if suite["suite_version"] >= 3 and not isinstance(measurement, Mapping):
        raise BenchmarkValidationError(
            "suite version 3 or newer requires a measurement contract"
        )
    if measurement is not None:
        _validate_measurement(measurement)

    tasks = suite.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise BenchmarkValidationError("tasks must be a non-empty list")
    seen = set()
    for index, task in enumerate(tasks):
        _validate_task(task, index)
        task_id = task["id"]
        if task_id in seen:
            raise BenchmarkValidationError("duplicate task id '{}'".format(task_id))
        seen.add(task_id)
    available_splits = {task["split"] for task in tasks}
    missing_splits = set(required_splits) - available_splits
    if missing_splits:
        raise BenchmarkValidationError(
            "suite has no task for required split(s): {}".format(
                ", ".join(sorted(missing_splits))
            )
        )


def _validate_measurement(measurement: Mapping[str, Any]) -> None:
    _reject_unknown_fields(measurement, _MEASUREMENT_FIELDS, "measurement")
    if measurement.get("scope") != "full_observed_model_usage":
        raise BenchmarkValidationError(
            "measurement scope must be full_observed_model_usage"
        )
    kinds = measurement.get("required_workload_kinds")
    if (
        not isinstance(kinds, list)
        or not kinds
        or len(kinds) != len(set(kinds))
        or not set(kinds).issubset(ALLOWED_WORKLOAD_KINDS)
    ):
        raise BenchmarkValidationError(
            "required_workload_kinds must be a unique non-empty list"
        )
    for field in (
        "min_full_token_reduction",
        "min_workload_success_rate",
        "max_history_success_drop",
        "max_history_total_token_increase",
    ):
        _require_number(
            measurement.get(field),
            field,
            minimum=0,
            maximum=1,
        )
    for field in (
        "max_manual_corrections",
        "min_model_families",
        "min_hardware_families",
        "min_history_comparisons",
    ):
        _require_int(measurement.get(field), field, minimum=0)
    if not isinstance(measurement.get("require_independent_runner"), bool):
        raise BenchmarkValidationError(
            "require_independent_runner must be boolean"
        )


def describe_suite(suite: Mapping[str, Any]) -> dict:
    """Return the identities a host must copy into raw run records."""
    validate_suite(suite)
    summary = {
        "schema_version": SUITE_SCHEMA,
        "suite_id": suite["suite_id"],
        "suite_version": suite["suite_version"],
        "suite_digest": suite_digest(suite),
        "required_modes": list(REQUIRED_MODES),
        "trusted_evidence_tier": VERIFIED_EVIDENCE_TIER,
        "tasks": [
            {
                "id": task["id"],
                "split": task["split"],
                "sealed": task["sealed"],
                "task_digest": task_digest(task),
            }
            for task in suite["tasks"]
        ],
    }
    return summary


def build_scorecard(
    suite: Mapping[str, Any],
    raw_records: Sequence[Mapping[str, Any]],
) -> dict:
    """Validate paired evidence and build a deterministic benchmark scorecard."""
    validate_suite(suite)
    if not isinstance(raw_records, Sequence) or not raw_records:
        raise BenchmarkValidationError("at least one run record is required")

    expected_suite_digest = suite_digest(suite)
    task_map = {task["id"]: task for task in suite["tasks"]}
    records = [
        _validate_run(record, suite, task_map, expected_suite_digest)
        for record in raw_records
    ]
    run_schemas = {record["schema_version"] for record in records}
    if len(run_schemas) != 1:
        raise BenchmarkValidationError(
            "one scorecard cannot mix run schema versions"
        )
    full_scope = run_schemas == {RUN_SCHEMA_V2}
    if bool(suite.get("measurement")) != full_scope:
        raise BenchmarkValidationError(
            "measurement suites require benchmark-run.v2 evidence"
        )
    _validate_global_identity(records)
    pair_count = _validate_pairs(records)

    ordered_records = sorted(
        records,
        key=lambda item: (item["task_id"], item["trial"], item["mode"]),
    )
    by_mode = {
        mode: _aggregate(
            [record for record in ordered_records if record["mode"] == mode]
        )
        for mode in REQUIRED_MODES
    }
    comparisons = {
        "end_to_end": _compare_modes(
            "agent_baseline",
            by_mode["agent_baseline"],
            "blueprint_warm",
            by_mode["blueprint_warm"],
            ordered_records,
        ),
        "blueprint_effect": _compare_modes(
            "flyto_no_blueprint",
            by_mode["flyto_no_blueprint"],
            "blueprint_warm",
            by_mode["blueprint_warm"],
            ordered_records,
        ),
        "warmup_effect": _compare_modes(
            "blueprint_cold",
            by_mode["blueprint_cold"],
            "blueprint_warm",
            by_mode["blueprint_warm"],
            ordered_records,
        ),
    }
    gate = _build_gate(suite, ordered_records, by_mode, comparisons)
    dataset_commit = ordered_records[0]["dataset_commit"]
    model_id = ordered_records[0]["model_id"]
    environment_digest = ordered_records[0]["environment_digest"]

    provenance = {
        "dataset_commit": dataset_commit,
        "model_id": model_id,
        "environment_digest": environment_digest,
        "evidence_tier": VERIFIED_EVIDENCE_TIER,
        "record_count": len(ordered_records),
        "pair_count": pair_count,
    }
    limitations = [
        (
            "The host executes tasks; this scorecard validates only the "
            "records supplied by that trusted boundary."
        ),
    ]
    if full_scope:
        first = ordered_records[0]
        provenance.update(
            {
                "run_id": first["run_id"],
                "run_started_at": first["run_started_at"],
                "host_id": first["host_id"],
                "hardware_family": first["hardware_family"],
                "runner_kind": first["runner_kind"],
                "model_family": first["model_family"],
            }
        )
        limitations.append(
            "Visible cost is zero for local Ollama and is not a cloud-price estimate."
        )
    else:
        limitations.append(
            (
                "Planner tokens exclude model-backed workflow steps and any "
                "provider-internal usage the host cannot observe."
            )
        )

    scorecard = {
        "schema_version": (
            SCORECARD_SCHEMA_V2 if full_scope else SCORECARD_SCHEMA
        ),
        "suite_id": suite["suite_id"],
        "suite_version": suite["suite_version"],
        "suite_digest": expected_suite_digest,
        "evidence_digest": canonical_digest(ordered_records),
        "proof_status": gate["status"],
        "claim_scope": (
            "full_observed_model_usage"
            if full_scope
            else "planner_model_usage_only"
        ),
        "provenance": provenance,
        "modes": by_mode,
        "comparisons": comparisons,
        "gate": gate,
        "limitations": limitations,
    }
    scorecard["scorecard_digest"] = canonical_digest(scorecard)
    return scorecard


def verify_result_directory(
    suite: Mapping[str, Any],
    results_dir: str | Path,
) -> dict:
    """Rebuild every committed scorecard and report missing or stale evidence."""
    validate_suite(suite)
    directory = Path(results_dir)
    if not directory.is_dir():
        return {
            "passed": False,
            "status": "failed",
            "result_count": 0,
            "verified_count": 0,
            "issues": ["benchmark results directory does not exist"],
        }
    run_files = sorted(directory.glob("*.runs.jsonl"))
    scorecard_files = sorted(directory.glob("*.scorecard.json"))
    run_prefixes = {
        path.name[: -len(".runs.jsonl")]
        for path in run_files
    }
    orphan_scorecards = [
        path.name
        for path in scorecard_files
        if path.name[: -len(".scorecard.json")] not in run_prefixes
    ]
    if orphan_scorecards:
        return {
            "passed": False,
            "status": "failed",
            "result_count": len(run_files),
            "verified_count": 0,
            "issues": [
                "{}: missing raw run evidence".format(name)
                for name in orphan_scorecards
            ],
        }
    if not run_files:
        return {
            "passed": True,
            "status": "no_results",
            "result_count": 0,
            "issues": [],
            "message": "No committed benchmark results; no performance claim exists.",
        }

    issues = []
    verified = 0
    verified_scorecards = []
    for run_path in run_files:
        prefix = run_path.name[: -len(".runs.jsonl")]
        scorecard_path = run_path.with_name(prefix + ".scorecard.json")
        try:
            generated = build_scorecard(suite, load_runs(run_path))
        except (BenchmarkValidationError, OSError) as exc:
            issues.append("{}: {}".format(run_path.name, exc))
            continue
        if not scorecard_path.exists():
            issues.append("{}: missing generated scorecard".format(run_path.name))
            continue
        try:
            committed = json.loads(
                scorecard_path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (json.JSONDecodeError, BenchmarkValidationError) as exc:
            issues.append("{}: invalid JSON ({})".format(scorecard_path.name, exc))
            continue
        if committed != generated:
            issues.append("{}: scorecard is stale or edited".format(scorecard_path.name))
            continue
        if generated["proof_status"] != "verified":
            issues.append(
                "{}: evidence gate is {}".format(
                    scorecard_path.name,
                    generated["proof_status"],
                )
            )
            continue
        verified += 1
        verified_scorecards.append(generated)

    closure = None
    if not issues and suite.get("measurement") is not None:
        closure, closure_issues = _verify_diversity_and_history(
            verified_scorecards,
            suite["measurement"],
        )
        issues.extend(closure_issues)

    result = {
        "passed": not issues,
        "status": "verified" if not issues else "failed",
        "result_count": len(run_files),
        "verified_count": verified,
        "issues": issues,
    }
    if closure is not None:
        result["closure"] = closure
    return result


def _verify_diversity_and_history(
    scorecards: Sequence[Mapping[str, Any]],
    measurement: Mapping[str, Any],
) -> tuple[dict, list[str]]:
    model_families = {
        card["provenance"]["model_family"] for card in scorecards
    }
    hardware_families = {
        card["provenance"]["hardware_family"] for card in scorecards
    }
    independent_count = sum(
        card["provenance"]["runner_kind"] == "independent_ci"
        for card in scorecards
    )
    issues = []
    if len(model_families) < measurement["min_model_families"]:
        issues.append(
            "model diversity is {} but at least {} families are required".format(
                len(model_families),
                measurement["min_model_families"],
            )
        )
    if len(hardware_families) < measurement["min_hardware_families"]:
        issues.append(
            "hardware diversity is {} but at least {} families are required".format(
                len(hardware_families),
                measurement["min_hardware_families"],
            )
        )
    if measurement["require_independent_runner"] and independent_count == 0:
        issues.append("at least one independent_ci result is required")

    series: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for card in scorecards:
        provenance = card["provenance"]
        key = (
            provenance["model_family"],
            provenance["hardware_family"],
            provenance["runner_kind"],
        )
        series.setdefault(key, []).append(card)

    comparisons = []
    for key, cards in sorted(series.items()):
        ordered = sorted(
            cards,
            key=lambda card: (
                card["provenance"]["run_started_at"],
                card["provenance"]["run_id"],
            ),
        )
        for previous, current in zip(ordered, ordered[1:]):
            old = previous["modes"]["blueprint_warm"]
            new = current["modes"]["blueprint_warm"]
            success_drop = round(
                old["success_rate"] - new["success_rate"],
                4,
            )
            token_increase = _relative_increase(
                new["total_tokens_total"],
                old["total_tokens_total"],
            )
            passed = (
                success_drop <= measurement["max_history_success_drop"]
                and token_increase is not None
                and token_increase
                <= measurement["max_history_total_token_increase"]
            )
            comparison = {
                "series": {
                    "model_family": key[0],
                    "hardware_family": key[1],
                    "runner_kind": key[2],
                },
                "previous_run_id": previous["provenance"]["run_id"],
                "current_run_id": current["provenance"]["run_id"],
                "success_drop": success_drop,
                "total_token_increase": token_increase,
                "passed": passed,
            }
            comparisons.append(comparison)
            if not passed:
                issues.append(
                    "history regression {} -> {}".format(
                        comparison["previous_run_id"],
                        comparison["current_run_id"],
                    )
                )
    if len(comparisons) < measurement["min_history_comparisons"]:
        issues.append(
            "history has {} comparison(s), expected at least {}".format(
                len(comparisons),
                measurement["min_history_comparisons"],
            )
        )

    return (
        {
            "model_families": sorted(model_families),
            "hardware_families": sorted(hardware_families),
            "independent_runner_count": independent_count,
            "history_comparisons": comparisons,
            "passed": not issues,
        },
        issues,
    )


def write_scorecard(scorecard: Mapping[str, Any], path: str | Path) -> None:
    """Write canonical, reviewable scorecard JSON."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            scorecard,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scorecard, suite-description, or repository verification CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    describe_parser = subparsers.add_parser(
        "describe-suite",
        help="print suite and task digests for a host runner",
    )
    describe_parser.add_argument("--suite", required=True)

    score_parser = subparsers.add_parser(
        "score",
        help="validate run records and generate a scorecard",
    )
    score_parser.add_argument("--suite", required=True)
    score_parser.add_argument("--runs", required=True)
    score_parser.add_argument("--output")
    score_parser.add_argument("--fail-on-regression", action="store_true")

    verify_parser = subparsers.add_parser(
        "verify-results",
        help="rebuild and verify every committed result",
    )
    verify_parser.add_argument("--suite", required=True)
    verify_parser.add_argument("--results-dir", required=True)

    args = parser.parse_args(argv)
    try:
        suite = load_suite(args.suite)
        if args.command == "describe-suite":
            _print_json(describe_suite(suite))
            return 0
        if args.command == "score":
            scorecard = build_scorecard(suite, load_runs(args.runs))
            if args.output:
                write_scorecard(scorecard, args.output)
            else:
                _print_json(scorecard)
            if args.fail_on_regression and scorecard["proof_status"] != "verified":
                return 1
            return 0
        result = verify_result_directory(suite, args.results_dir)
        _print_json(result)
        return 0 if result["passed"] else 1
    except (BenchmarkValidationError, OSError, yaml.YAMLError) as exc:
        _print_json({"error": str(exc)}, stream=sys.stderr)
        return 2


def _validate_task(task: Any, index: int) -> None:
    if not isinstance(task, Mapping):
        raise BenchmarkValidationError("task {} must be an object".format(index))
    _reject_unknown_fields(task, _TASK_FIELDS, "task")
    _require_id(task.get("id"), "task id")
    if task.get("split") not in ALLOWED_SPLITS:
        raise BenchmarkValidationError(
            "task '{}' has an unknown split".format(task["id"])
        )
    if not isinstance(task.get("sealed"), bool):
        raise BenchmarkValidationError(
            "task '{}' sealed must be boolean".format(task["id"])
        )
    _require_text(task.get("expected_behavior"), "expected_behavior")
    assertions = task.get("assertions")
    if (
        not isinstance(assertions, list)
        or not assertions
        or any(not isinstance(item, str) or not item.strip() for item in assertions)
    ):
        raise BenchmarkValidationError(
            "task '{}' needs non-empty assertion names".format(task["id"])
        )
    tags = task.get("tags")
    if not isinstance(tags, list) or any(
        not isinstance(tag, str) or not _ID_RE.fullmatch(tag) for tag in tags
    ):
        raise BenchmarkValidationError(
            "task '{}' tags must be safe identifiers".format(task["id"])
        )
    if task["sealed"]:
        if "prompt" in task:
            raise BenchmarkValidationError(
                "sealed task '{}' must not expose a prompt".format(task["id"])
            )
        task_digest(task)
    else:
        _require_text(task.get("prompt"), "task prompt")
        if "task_digest" in task:
            raise BenchmarkValidationError(
                "public task '{}' digest is generated, not declared".format(task["id"])
            )


def _validate_run(
    raw_record: Mapping[str, Any],
    suite: Mapping[str, Any],
    task_map: Mapping[str, Mapping[str, Any]],
    expected_suite_digest: str,
) -> dict:
    if not isinstance(raw_record, Mapping):
        raise BenchmarkValidationError("every run must be an object")
    schema = raw_record.get("schema_version")
    if schema == RUN_SCHEMA:
        allowed_fields = _RUN_FIELDS
        optional_fields = {"visible_cost_usd"}
    elif schema == RUN_SCHEMA_V2:
        allowed_fields = _RUN_V2_FIELDS
        optional_fields = set()
    else:
        raise BenchmarkValidationError(
            "run schema_version must be {} or {}".format(
                RUN_SCHEMA,
                RUN_SCHEMA_V2,
            )
        )
    _reject_unknown_fields(raw_record, allowed_fields, "run")
    missing = allowed_fields - optional_fields - set(raw_record)
    if missing:
        raise BenchmarkValidationError(
            "run is missing field(s): {}".format(", ".join(sorted(missing)))
        )
    record = dict(raw_record)
    if record["suite_id"] != suite["suite_id"]:
        raise BenchmarkValidationError("run suite_id does not match the suite")
    if record["suite_digest"] != expected_suite_digest:
        raise BenchmarkValidationError("run suite_digest does not match the suite")
    if not _COMMIT_RE.fullmatch(str(record["dataset_commit"])):
        raise BenchmarkValidationError("dataset_commit must be a hexadecimal git SHA")
    if record["task_id"] not in task_map:
        raise BenchmarkValidationError(
            "unknown task_id '{}'".format(record["task_id"])
        )
    task = task_map[record["task_id"]]
    if record["task_digest"] != task_digest(task):
        raise BenchmarkValidationError(
            "task_digest mismatch for '{}'".format(record["task_id"])
        )
    if record["split"] != task["split"]:
        raise BenchmarkValidationError(
            "split mismatch for '{}'".format(record["task_id"])
        )
    if record["mode"] not in REQUIRED_MODES:
        raise BenchmarkValidationError(
            "unknown benchmark mode '{}'".format(record["mode"])
        )
    _require_int(record["trial"], "trial", minimum=1)
    _require_int(record["seed"], "seed", minimum=0, maximum=(2**63) - 1)
    if not isinstance(record["model_id"], str) or not _SAFE_TEXT_RE.fullmatch(
        record["model_id"]
    ):
        raise BenchmarkValidationError("model_id contains unsafe characters")
    if not isinstance(record["environment_digest"], str) or not _DIGEST_RE.fullmatch(
        record["environment_digest"]
    ):
        raise BenchmarkValidationError("environment_digest must be SHA-256")
    if record["evidence_tier"] != VERIFIED_EVIDENCE_TIER:
        raise BenchmarkValidationError(
            "only {} evidence can enter a scorecard".format(
                VERIFIED_EVIDENCE_TIER
            )
        )
    for field in ("success", "false_reuse"):
        if not isinstance(record[field], bool):
            raise BenchmarkValidationError("{} must be boolean".format(field))
    for field in (
        "assertions_passed",
        "assertions_total",
        "planner_input_tokens",
        "planner_output_tokens",
        "planner_model_calls",
        "tool_calls",
        "retries",
    ):
        minimum = 1 if field == "assertions_total" else 0
        _require_int(record[field], field, minimum=minimum, maximum=1_000_000_000)
    if record["assertions_passed"] > record["assertions_total"]:
        raise BenchmarkValidationError(
            "assertions_passed cannot exceed assertions_total"
        )
    if record["assertions_total"] != len(task["assertions"]):
        raise BenchmarkValidationError(
            "assertions_total does not match task '{}'".format(record["task_id"])
        )
    assertion_success = (
        record["assertions_passed"] == record["assertions_total"]
    )
    if record["success"] != assertion_success:
        raise BenchmarkValidationError(
            "success must equal the assertion outcome"
        )
    _require_number(
        record["duration_ms"],
        "duration_ms",
        minimum=0,
        maximum=604_800_000,
    )
    if "visible_cost_usd" in record:
        _require_number(
            record["visible_cost_usd"],
            "visible_cost_usd",
            minimum=0,
            maximum=1_000_000,
        )
    if schema == RUN_SCHEMA_V2:
        _validate_full_scope_run(record)
    return record


def _validate_full_scope_run(record: Mapping[str, Any]) -> None:
    for field in ("run_id", "host_id", "hardware_family", "model_family"):
        _require_id(record[field], field)
    if (
        not isinstance(record["run_started_at"], str)
        or not _TIMESTAMP_RE.fullmatch(record["run_started_at"])
    ):
        raise BenchmarkValidationError(
            "run_started_at must be a UTC ISO-8601 timestamp"
        )
    if record["runner_kind"] not in ALLOWED_RUNNER_KINDS:
        raise BenchmarkValidationError("runner_kind is not supported")
    if record["workload_kind"] not in ALLOWED_WORKLOAD_KINDS:
        raise BenchmarkValidationError("workload_kind is not supported")
    if (
        not isinstance(record["workload_digest"], str)
        or not _DIGEST_RE.fullmatch(record["workload_digest"])
    ):
        raise BenchmarkValidationError("workload_digest must be SHA-256")
    if not isinstance(record["workload_success"], bool):
        raise BenchmarkValidationError("workload_success must be boolean")
    for field in (
        "workflow_input_tokens",
        "workflow_output_tokens",
        "workflow_model_calls",
        "manual_corrections",
        "total_input_tokens",
        "total_output_tokens",
        "total_model_calls",
    ):
        _require_int(record[field], field, minimum=0, maximum=1_000_000_000)
    for field in (
        "workflow_duration_ms",
        "planner_visible_cost_usd",
        "workflow_visible_cost_usd",
        "total_visible_cost_usd",
    ):
        _require_number(
            record[field],
            field,
            minimum=0,
            maximum=1_000_000,
        )
    if record["total_input_tokens"] != (
        record["planner_input_tokens"] + record["workflow_input_tokens"]
    ):
        raise BenchmarkValidationError(
            "total_input_tokens must equal planner plus workflow input tokens"
        )
    if record["total_output_tokens"] != (
        record["planner_output_tokens"] + record["workflow_output_tokens"]
    ):
        raise BenchmarkValidationError(
            "total_output_tokens must equal planner plus workflow output tokens"
        )
    if record["total_model_calls"] != (
        record["planner_model_calls"] + record["workflow_model_calls"]
    ):
        raise BenchmarkValidationError(
            "total_model_calls must equal planner plus workflow model calls"
        )
    if abs(
        record["total_visible_cost_usd"]
        - (
            record["planner_visible_cost_usd"]
            + record["workflow_visible_cost_usd"]
        )
    ) > 0.000001:
        raise BenchmarkValidationError(
            "total_visible_cost_usd must equal planner plus workflow visible cost"
        )


def _validate_global_identity(records: Sequence[Mapping[str, Any]]) -> None:
    fields = ["dataset_commit", "model_id", "environment_digest"]
    if records[0]["schema_version"] == RUN_SCHEMA_V2:
        fields.extend(
            [
                "run_id",
                "run_started_at",
                "host_id",
                "hardware_family",
                "runner_kind",
                "model_family",
            ]
        )
    for field in fields:
        values = {record[field] for record in records}
        if len(values) != 1:
            raise BenchmarkValidationError(
                "{} must be identical across one scorecard".format(field)
            )


def _validate_pairs(records: Sequence[Mapping[str, Any]]) -> int:
    pairs: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = {}
    for record in records:
        key = (record["task_id"], record["trial"])
        modes = pairs.setdefault(key, {})
        if record["mode"] in modes:
            raise BenchmarkValidationError(
                "duplicate mode '{}' for task '{}' trial {}".format(
                    record["mode"],
                    record["task_id"],
                    record["trial"],
                )
            )
        modes[record["mode"]] = record

    required = set(REQUIRED_MODES)
    for (task_id, trial), modes in pairs.items():
        if set(modes) != required:
            missing = required - set(modes)
            raise BenchmarkValidationError(
                "task '{}' trial {} is missing mode(s): {}".format(
                    task_id,
                    trial,
                    ", ".join(sorted(missing)),
                )
            )
        seeds = {record["seed"] for record in modes.values()}
        if len(seeds) != 1:
            raise BenchmarkValidationError(
                "task '{}' trial {} must use one paired seed".format(task_id, trial)
            )
    return len(pairs)


def _aggregate(records: Sequence[Mapping[str, Any]]) -> dict:
    successes = sum(record["success"] for record in records)
    planner_tokens = [
        record["planner_input_tokens"] + record["planner_output_tokens"]
        for record in records
    ]
    durations = [float(record["duration_ms"]) for record in records]
    assertions_passed = sum(record["assertions_passed"] for record in records)
    assertions_total = sum(record["assertions_total"] for record in records)
    visible_costs = [
        float(record["visible_cost_usd"])
        for record in records
        if "visible_cost_usd" in record
    ]
    lower, upper = _wilson_interval(successes, len(records))
    summary = {
        "run_count": len(records),
        "success_count": successes,
        "success_rate": _round_ratio(successes, len(records)),
        "wilson_95_lower_bound": lower,
        "wilson_95_upper_bound": upper,
        "assertions_passed": assertions_passed,
        "assertions_total": assertions_total,
        "assertion_pass_rate": _round_ratio(
            assertions_passed,
            assertions_total,
        ),
        "planner_tokens_total": sum(planner_tokens),
        "planner_tokens_median": _median(planner_tokens),
        "planner_model_calls_total": sum(
            record["planner_model_calls"] for record in records
        ),
        "planner_model_calls_median": _median(
            [record["planner_model_calls"] for record in records]
        ),
        "tool_calls_total": sum(record["tool_calls"] for record in records),
        "tool_calls_median": _median(
            [record["tool_calls"] for record in records]
        ),
        "retry_count": sum(record["retries"] for record in records),
        "retry_median": _median([record["retries"] for record in records]),
        "false_reuse_count": sum(record["false_reuse"] for record in records),
        "duration_ms_p50": _percentile(durations, 0.50),
        "duration_ms_p95": _percentile(durations, 0.95),
        "visible_cost_sample_count": len(visible_costs),
        "visible_cost_usd_total": (
            round(sum(visible_costs), 6) if visible_costs else None
        ),
        "visible_cost_usd_median": _median(visible_costs),
    }
    if records and records[0]["schema_version"] == RUN_SCHEMA_V2:
        workflow_tokens = [
            record["workflow_input_tokens"] + record["workflow_output_tokens"]
            for record in records
        ]
        total_tokens = [
            record["total_input_tokens"] + record["total_output_tokens"]
            for record in records
        ]
        workload_successes = sum(record["workload_success"] for record in records)
        summary.update(
            {
                "workflow_tokens_total": sum(workflow_tokens),
                "workflow_tokens_median": _median(workflow_tokens),
                "workflow_model_calls_total": sum(
                    record["workflow_model_calls"] for record in records
                ),
                "total_tokens_total": sum(total_tokens),
                "total_tokens_median": _median(total_tokens),
                "total_model_calls_total": sum(
                    record["total_model_calls"] for record in records
                ),
                "manual_corrections_total": sum(
                    record["manual_corrections"] for record in records
                ),
                "workload_success_count": workload_successes,
                "workload_success_rate": _round_ratio(
                    workload_successes,
                    len(records),
                ),
                "workflow_duration_ms_p95": _percentile(
                    [float(record["workflow_duration_ms"]) for record in records],
                    0.95,
                ),
                "total_visible_cost_usd": round(
                    sum(
                        float(record["total_visible_cost_usd"])
                        for record in records
                    ),
                    6,
                ),
            }
        )
    return summary


def _compare_modes(
    baseline_mode: str,
    baseline: Mapping[str, Any],
    candidate_mode: str,
    candidate: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict:
    paired_reductions = _paired_token_reductions(
        records,
        baseline_mode,
        candidate_mode,
    )
    reduction_lower, reduction_upper = _median_confidence_interval(
        paired_reductions
    )
    comparison = {
        "baseline_mode": baseline_mode,
        "candidate_mode": candidate_mode,
        "success_rate_delta": _round_optional(
            candidate["success_rate"] - baseline["success_rate"]
        ),
        "planner_token_reduction": _relative_reduction(
            candidate["planner_tokens_median"],
            baseline["planner_tokens_median"],
        ),
        "planner_token_total_reduction": _relative_reduction(
            candidate["planner_tokens_total"],
            baseline["planner_tokens_total"],
        ),
        "paired_planner_token_reduction_median": _median(paired_reductions),
        "paired_planner_token_reduction_ci_95_lower_bound": reduction_lower,
        "paired_planner_token_reduction_ci_95_upper_bound": reduction_upper,
        "paired_sample_count": len(paired_reductions),
        "planner_model_call_reduction": _relative_reduction(
            candidate["planner_model_calls_median"],
            baseline["planner_model_calls_median"],
        ),
        "tool_call_reduction": _relative_reduction(
            candidate["tool_calls_median"],
            baseline["tool_calls_median"],
        ),
        "retry_reduction": _relative_reduction(
            candidate["retry_median"],
            baseline["retry_median"],
        ),
        "p95_latency_increase": _relative_increase(
            candidate["duration_ms_p95"],
            baseline["duration_ms_p95"],
        ),
    }
    if "total_tokens_total" in baseline:
        total_reductions = _paired_token_reductions(
            records,
            baseline_mode,
            candidate_mode,
            token_fields=("total_input_tokens", "total_output_tokens"),
        )
        total_lower, total_upper = _median_confidence_interval(
            total_reductions
        )
        comparison.update(
            {
                "total_token_reduction": _relative_reduction(
                    candidate["total_tokens_median"],
                    baseline["total_tokens_median"],
                ),
                "total_token_total_reduction": _relative_reduction(
                    candidate["total_tokens_total"],
                    baseline["total_tokens_total"],
                ),
                "paired_total_token_reduction_median": _median(
                    total_reductions
                ),
                "paired_total_token_reduction_ci_95_lower_bound": total_lower,
                "paired_total_token_reduction_ci_95_upper_bound": total_upper,
                "paired_total_token_sample_count": len(total_reductions),
                "total_model_call_reduction": _relative_reduction(
                    candidate["total_model_calls_total"],
                    baseline["total_model_calls_total"],
                ),
                "manual_correction_delta": (
                    candidate["manual_corrections_total"]
                    - baseline["manual_corrections_total"]
                ),
            }
        )
    return comparison


def _build_gate(
    suite: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    by_mode: Mapping[str, Mapping[str, Any]],
    comparisons: Mapping[str, Mapping[str, Any]],
) -> dict:
    thresholds = suite["thresholds"]
    candidate = by_mode["blueprint_warm"]
    end_to_end = comparisons["end_to_end"]
    blueprint_effect = comparisons["blueprint_effect"]
    task_ids = {record["task_id"] for record in records}
    all_task_ids = {task["id"] for task in suite["tasks"]}
    observed_splits = {record["split"] for record in records}
    trial_counts = {
        task_id: len(
            {
                record["trial"]
                for record in records
                if record["task_id"] == task_id
            }
        )
        for task_id in all_task_ids
    }
    checks = [
        _check(
            "task_coverage",
            task_ids == all_task_ids,
            sorted(task_ids),
            sorted(all_task_ids),
        ),
        _check(
            "required_splits",
            set(thresholds["required_splits"]).issubset(observed_splits),
            sorted(observed_splits),
            sorted(thresholds["required_splits"]),
        ),
        _check(
            "minimum_trials",
            min(trial_counts.values(), default=0)
            >= thresholds["min_trials_per_task"],
            trial_counts,
            "at least {} per task".format(thresholds["min_trials_per_task"]),
        ),
        _check(
            "end_to_end_success_non_inferiority",
            end_to_end["success_rate_delta"]
            >= -thresholds["max_success_rate_drop"],
            end_to_end["success_rate_delta"],
            ">= -{}".format(thresholds["max_success_rate_drop"]),
        ),
        _check(
            "blueprint_effect_success_non_inferiority",
            blueprint_effect["success_rate_delta"]
            >= -thresholds["max_success_rate_drop"],
            blueprint_effect["success_rate_delta"],
            ">= -{}".format(thresholds["max_success_rate_drop"]),
        ),
        _check(
            "candidate_confidence",
            candidate["wilson_95_lower_bound"]
            >= thresholds["min_candidate_wilson_lower_bound"],
            candidate["wilson_95_lower_bound"],
            ">= {}".format(thresholds["min_candidate_wilson_lower_bound"]),
        ),
        _check(
            "end_to_end_planner_token_reduction",
            end_to_end[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ]
            is not None
            and end_to_end[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ]
            >= thresholds["min_planner_token_reduction"],
            end_to_end[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ],
            ">= {}".format(thresholds["min_planner_token_reduction"]),
        ),
        _check(
            "blueprint_effect_planner_token_reduction",
            blueprint_effect[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ]
            is not None
            and blueprint_effect[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ]
            >= thresholds["min_planner_token_reduction"],
            blueprint_effect[
                "paired_planner_token_reduction_ci_95_lower_bound"
            ],
            ">= {}".format(thresholds["min_planner_token_reduction"]),
        ),
        _check(
            "end_to_end_p95_latency",
            end_to_end["p95_latency_increase"] is not None
            and end_to_end["p95_latency_increase"]
            <= thresholds["max_p95_latency_increase"],
            end_to_end["p95_latency_increase"],
            "<= {}".format(thresholds["max_p95_latency_increase"]),
        ),
        _check(
            "blueprint_effect_p95_latency",
            blueprint_effect["p95_latency_increase"] is not None
            and blueprint_effect["p95_latency_increase"]
            <= thresholds["max_p95_latency_increase"],
            blueprint_effect["p95_latency_increase"],
            "<= {}".format(thresholds["max_p95_latency_increase"]),
        ),
        _check(
            "false_reuse",
            candidate["false_reuse_count"]
            <= thresholds["max_false_reuse_count"],
            candidate["false_reuse_count"],
            "<= {}".format(thresholds["max_false_reuse_count"]),
        ),
        _check(
            "assertion_pass_rate",
            candidate["assertion_pass_rate"]
            >= thresholds["min_assertion_pass_rate"],
            candidate["assertion_pass_rate"],
            ">= {}".format(thresholds["min_assertion_pass_rate"]),
        ),
    ]
    measurement = suite.get("measurement")
    if measurement is not None:
        required_kinds = set(measurement["required_workload_kinds"])
        observed_kinds = {record["workload_kind"] for record in records}
        checks.extend(
            [
                _check(
                    "required_workload_kinds",
                    required_kinds.issubset(observed_kinds),
                    sorted(observed_kinds),
                    sorted(required_kinds),
                ),
                _check(
                    "workload_success_rate",
                    candidate["workload_success_rate"]
                    >= measurement["min_workload_success_rate"],
                    candidate["workload_success_rate"],
                    ">= {}".format(
                        measurement["min_workload_success_rate"]
                    ),
                ),
                _check(
                    "manual_corrections",
                    candidate["manual_corrections_total"]
                    <= measurement["max_manual_corrections"],
                    candidate["manual_corrections_total"],
                    "<= {}".format(measurement["max_manual_corrections"]),
                ),
                _check(
                    "end_to_end_full_token_reduction",
                    end_to_end[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ]
                    is not None
                    and end_to_end[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ]
                    >= measurement["min_full_token_reduction"],
                    end_to_end[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ],
                    ">= {}".format(
                        measurement["min_full_token_reduction"]
                    ),
                ),
                _check(
                    "blueprint_effect_full_token_reduction",
                    blueprint_effect[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ]
                    is not None
                    and blueprint_effect[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ]
                    >= measurement["min_full_token_reduction"],
                    blueprint_effect[
                        "paired_total_token_reduction_ci_95_lower_bound"
                    ],
                    ">= {}".format(
                        measurement["min_full_token_reduction"]
                    ),
                ),
            ]
        )
    evidence_checks = {"task_coverage", "required_splits", "minimum_trials"}
    if measurement is not None:
        evidence_checks.add("required_workload_kinds")
    insufficient = any(
        not check["passed"] and check["id"] in evidence_checks
        for check in checks
    )
    passed = all(check["passed"] for check in checks)
    status = "verified" if passed else "insufficient_evidence" if insufficient else "regression"
    return {
        "passed": passed,
        "status": status,
        "checks": checks,
    }


def _check(check_id: str, passed: bool, actual: Any, expected: Any) -> dict:
    return {
        "id": check_id,
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
    }


def _wilson_interval(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    z = 1.96
    probability = successes / total
    denominator = 1 + (z * z / total)
    center = probability + (z * z / (2 * total))
    spread = z * math.sqrt(
        (probability * (1 - probability) / total)
        + (z * z / (4 * total * total))
    )
    return (
        round(max(0.0, (center - spread) / denominator), 4),
        round(min(1.0, (center + spread) / denominator), 4),
    )


def _percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(
        ordered[lower] + (ordered[upper] - ordered[lower]) * weight,
        3,
    )


def _median(values: Sequence[float]) -> float | None:
    return round(float(statistics.median(values)), 4) if values else None


def _paired_token_reductions(
    records: Sequence[Mapping[str, Any]],
    baseline_mode: str,
    candidate_mode: str,
    *,
    token_fields: tuple[str, str] = (
        "planner_input_tokens",
        "planner_output_tokens",
    ),
) -> list[float]:
    pairs: dict[tuple[str, int], dict[str, float]] = {}
    for record in records:
        if record["mode"] not in {baseline_mode, candidate_mode}:
            continue
        tokens = record[token_fields[0]] + record[token_fields[1]]
        pairs.setdefault((record["task_id"], record["trial"]), {})[
            record["mode"]
        ] = float(tokens)

    reductions = []
    for modes in pairs.values():
        baseline = modes[baseline_mode]
        if baseline <= 0:
            if modes[candidate_mode] > 0:
                return []
            continue
        reductions.append(1 - (modes[candidate_mode] / baseline))
    return reductions


def _median_confidence_interval(
    values: Sequence[float],
    confidence: float = 0.95,
) -> tuple[float | None, float | None]:
    """Return an exact distribution-free confidence interval for a median."""
    if not values:
        return (None, None)
    ordered = sorted(values)
    sample_count = len(ordered)
    tail_probability = (1 - confidence) / 2
    cumulative = 0.0
    boundary = 0
    for successes in range(sample_count + 1):
        probability = math.comb(sample_count, successes) / (2**sample_count)
        if cumulative + probability > tail_probability:
            boundary = max(1, successes)
            break
        cumulative += probability
    return (
        round(ordered[boundary - 1], 4),
        round(ordered[sample_count - boundary], 4),
    )


def _relative_reduction(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline <= 0:
        return None
    return round(1 - (candidate / baseline), 4)


def _relative_increase(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None or baseline <= 0:
        return None
    return round((candidate / baseline) - 1, 4)


def _round_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _round_optional(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _reject_unknown_fields(
    value: Mapping[str, Any],
    allowed: set[str],
    label: str,
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise BenchmarkValidationError(
            "{} contains unknown field(s): {}".format(
                label,
                ", ".join(sorted(unknown)),
            )
        )


def _require_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise BenchmarkValidationError("{} must be a safe identifier".format(label))
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkValidationError("{} must be non-empty text".format(label))
    return value


def _require_int(
    value: Any,
    label: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BenchmarkValidationError("{} must be an integer".format(label))
    if value < minimum or (maximum is not None and value > maximum):
        raise BenchmarkValidationError("{} is outside its allowed range".format(label))
    return value


def _require_number(
    value: Any,
    label: str,
    *,
    minimum: float,
    maximum: float | None = None,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise BenchmarkValidationError("{} must be a finite number".format(label))
    numeric = float(value)
    if numeric < minimum or (maximum is not None and numeric > maximum):
        raise BenchmarkValidationError("{} is outside its allowed range".format(label))
    return numeric


def _reject_json_constant(value: str) -> None:
    raise BenchmarkValidationError("non-finite JSON value '{}'".format(value))


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise BenchmarkValidationError(
                "duplicate JSON object field '{}'".format(key)
            )
        value[key] = item
    return value


def _print_json(value: Mapping[str, Any], stream: Any | None = None) -> None:
    output_stream = sys.stdout if stream is None else stream
    output_stream.write(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
