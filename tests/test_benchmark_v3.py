import copy
import json
from pathlib import Path

import pytest

from flyto_blueprint.benchmark import (
    BenchmarkValidationError,
    REQUIRED_MODES,
    build_scorecard,
    describe_suite,
    load_suite,
    suite_digest,
    verify_result_directory,
    write_scorecard,
)


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "benchmarks/suites/blueprint-effectiveness-v3.yaml"
WORKLOAD_KINDS = {
    "real-coding-change-and-test": "coding",
    "real-browser-fetch-and-extract": "browser",
    "real-api-fetch-and-persist": "api",
    "real-llm-summary-with-usage": "llm",
    "ordinary-conversation-no-tools-v3": "conversation",
    "multilingual-negation-zh-v3": "conversation",
    "multilingual-negation-ja-v3": "conversation",
    "malformed-community-evidence-v3": "trust",
    "incompatible-blueprint-v3": "compatibility",
    "sealed-multilingual-routing-holdout-v3": "sealed",
}


def _suite(trials=2):
    suite = copy.deepcopy(load_suite(SUITE_PATH))
    suite["thresholds"]["min_trials_per_task"] = trials
    return suite


def _records(
    suite,
    *,
    run_id="qwen-local-a",
    model_id="ollama/qwen3:0.6b@sha256:" + ("a" * 64),
    model_family="qwen3",
    host_id="local-apple-silicon",
    hardware_family="apple-silicon",
    runner_kind="local",
    started_at="2026-07-28T01:00:00Z",
    trials=2,
):
    identity = describe_suite(suite)
    task_digests = {
        task["id"]: task["task_digest"] for task in identity["tasks"]
    }
    planner_metrics = {
        "agent_baseline": (80, 20, 2),
        "flyto_no_blueprint": (70, 20, 2),
        "blueprint_cold": (60, 20, 2),
        "blueprint_warm": (35, 15, 1),
    }
    records = []
    for task in suite["tasks"]:
        assertion_count = len(task["assertions"])
        for trial in range(1, trials + 1):
            for mode in REQUIRED_MODES:
                planner_input, planner_output, planner_calls = planner_metrics[
                    mode
                ]
                workflow_input = (
                    12 if task["id"] == "real-llm-summary-with-usage" else 0
                )
                workflow_output = (
                    6 if task["id"] == "real-llm-summary-with-usage" else 0
                )
                workflow_calls = int(
                    task["id"] == "real-llm-summary-with-usage"
                )
                records.append(
                    {
                        "schema_version": "benchmark-run.v2",
                        "suite_id": suite["suite_id"],
                        "suite_digest": suite_digest(suite),
                        "dataset_commit": "1" * 40,
                        "task_id": task["id"],
                        "task_digest": task_digests[task["id"]],
                        "split": task["split"],
                        "mode": mode,
                        "trial": trial,
                        "seed": 1000 + trial,
                        "model_id": model_id,
                        "environment_digest": "sha256:" + ("b" * 64),
                        "evidence_tier": "ci_verified",
                        "success": True,
                        "assertions_passed": assertion_count,
                        "assertions_total": assertion_count,
                        "planner_input_tokens": planner_input,
                        "planner_output_tokens": planner_output,
                        "planner_model_calls": planner_calls,
                        "tool_calls": 1,
                        "retries": 0,
                        "duration_ms": 100,
                        "false_reuse": False,
                        "visible_cost_usd": 0.0,
                        "run_id": run_id,
                        "run_started_at": started_at,
                        "host_id": host_id,
                        "hardware_family": hardware_family,
                        "runner_kind": runner_kind,
                        "model_family": model_family,
                        "workload_kind": WORKLOAD_KINDS[task["id"]],
                        "workload_digest": "sha256:" + ("c" * 64),
                        "workload_success": True,
                        "workflow_input_tokens": workflow_input,
                        "workflow_output_tokens": workflow_output,
                        "workflow_model_calls": workflow_calls,
                        "workflow_duration_ms": 5,
                        "manual_corrections": 0,
                        "planner_visible_cost_usd": 0.0,
                        "workflow_visible_cost_usd": 0.0,
                        "total_input_tokens": (
                            planner_input + workflow_input
                        ),
                        "total_output_tokens": (
                            planner_output + workflow_output
                        ),
                        "total_model_calls": (
                            planner_calls + workflow_calls
                        ),
                        "total_visible_cost_usd": 0.0,
                    }
                )
    return records


def _write_result(result_dir, name, suite, records):
    runs_path = result_dir / "{}.runs.jsonl".format(name)
    scorecard_path = result_dir / "{}.scorecard.json".format(name)
    runs_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    write_scorecard(build_scorecard(suite, records), scorecard_path)


def test_v3_scorecard_proves_full_observed_model_usage():
    suite = _suite()

    scorecard = build_scorecard(suite, _records(suite))

    assert scorecard["schema_version"] == "benchmark-scorecard.v2"
    assert scorecard["claim_scope"] == "full_observed_model_usage"
    assert scorecard["proof_status"] == "verified"
    assert (
        scorecard["comparisons"]["end_to_end"][
            "paired_total_token_reduction_ci_95_lower_bound"
        ]
        >= suite["measurement"]["min_full_token_reduction"]
    )
    assert scorecard["modes"]["blueprint_warm"][
        "manual_corrections_total"
    ] == 0


def test_v3_rejects_missing_full_usage_fields():
    suite = _suite()
    records = _records(suite)
    del records[0]["total_input_tokens"]

    with pytest.raises(
        BenchmarkValidationError,
        match="missing field.*total_input_tokens",
    ):
        build_scorecard(suite, records)


def test_v3_rejects_forged_total_token_arithmetic():
    suite = _suite()
    records = _records(suite)
    records[0]["total_input_tokens"] += 1

    with pytest.raises(
        BenchmarkValidationError,
        match="total_input_tokens must equal",
    ):
        build_scorecard(suite, records)


def test_v3_directory_requires_diversity_and_history(tmp_path):
    suite = _suite()
    _write_result(tmp_path, "qwen-a", suite, _records(suite))

    result = verify_result_directory(suite, tmp_path)

    assert result["passed"] is False
    assert any("model diversity" in issue for issue in result["issues"])
    assert any("hardware diversity" in issue for issue in result["issues"])
    assert any("independent_ci" in issue for issue in result["issues"])
    assert any("history has" in issue for issue in result["issues"])


def test_v3_directory_closes_model_hardware_runner_and_history_gates(
    tmp_path,
):
    suite = _suite()
    result_sets = [
        ("qwen-a", {}),
        (
            "qwen-b",
            {
                "run_id": "qwen-local-b",
                "started_at": "2026-07-28T02:00:00Z",
            },
        ),
        (
            "llama",
            {
                "run_id": "llama-local",
                "model_id": "ollama/llama3.2:1b@sha256:" + ("d" * 64),
                "model_family": "llama3.2",
                "started_at": "2026-07-28T03:00:00Z",
            },
        ),
        (
            "gemma",
            {
                "run_id": "gemma-local",
                "model_id": "ollama/gemma3:1b@sha256:" + ("e" * 64),
                "model_family": "gemma3",
                "started_at": "2026-07-28T04:00:00Z",
            },
        ),
        (
            "qwen-ci",
            {
                "run_id": "qwen-independent-ci",
                "host_id": "github-linux-x86-64",
                "hardware_family": "linux-x86-64",
                "runner_kind": "independent_ci",
                "started_at": "2026-07-28T05:00:00Z",
            },
        ),
    ]
    for name, overrides in result_sets:
        _write_result(
            tmp_path,
            name,
            suite,
            _records(suite, **overrides),
        )

    result = verify_result_directory(suite, tmp_path)

    assert result["passed"] is True
    assert result["verified_count"] == 5
    assert result["closure"]["model_families"] == [
        "gemma3",
        "llama3.2",
        "qwen3",
    ]
    assert result["closure"]["hardware_families"] == [
        "apple-silicon",
        "linux-x86-64",
    ]
    assert len(result["closure"]["history_comparisons"]) >= 1
