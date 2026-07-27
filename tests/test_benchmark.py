import copy
import json
from pathlib import Path

import pytest

from flyto_blueprint.benchmark import (
    BenchmarkValidationError,
    REQUIRED_MODES,
    build_scorecard,
    describe_suite,
    load_runs,
    load_suite,
    main,
    suite_digest,
    verify_result_directory,
    write_scorecard,
)


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "benchmarks/suites/blueprint-effectiveness-v1.yaml"
ENVIRONMENT_DIGEST = "sha256:" + ("a" * 64)
DATASET_COMMIT = "1" * 40


def _suite(min_trials=2):
    suite = copy.deepcopy(load_suite(SUITE_PATH))
    suite["thresholds"]["min_trials_per_task"] = min_trials
    return suite


def _records(suite, trials=2):
    description = describe_suite(suite)
    task_digests = {
        task["id"]: task["task_digest"] for task in description["tasks"]
    }
    metrics = {
        "agent_baseline": {
            "planner_input_tokens": 80,
            "planner_output_tokens": 20,
            "planner_model_calls": 2,
            "tool_calls": 5,
            "retries": 1,
            "duration_ms": 100,
        },
        "flyto_no_blueprint": {
            "planner_input_tokens": 70,
            "planner_output_tokens": 20,
            "planner_model_calls": 2,
            "tool_calls": 5,
            "retries": 1,
            "duration_ms": 102,
        },
        "blueprint_cold": {
            "planner_input_tokens": 60,
            "planner_output_tokens": 20,
            "planner_model_calls": 2,
            "tool_calls": 5,
            "retries": 1,
            "duration_ms": 103,
        },
        "blueprint_warm": {
            "planner_input_tokens": 35,
            "planner_output_tokens": 15,
            "planner_model_calls": 1,
            "tool_calls": 4,
            "retries": 0,
            "duration_ms": 105,
        },
    }
    records = []
    for task in suite["tasks"]:
        assertion_count = len(task["assertions"])
        for trial in range(1, trials + 1):
            for mode in REQUIRED_MODES:
                values = metrics[mode]
                tool_calls = values["tool_calls"]
                if task["id"] == "ordinary-conversation-does-not-call-mcp":
                    tool_calls = 0
                records.append(
                    {
                        "schema_version": "benchmark-run.v1",
                        "suite_id": suite["suite_id"],
                        "suite_digest": suite_digest(suite),
                        "dataset_commit": DATASET_COMMIT,
                        "task_id": task["id"],
                        "task_digest": task_digests[task["id"]],
                        "split": task["split"],
                        "mode": mode,
                        "trial": trial,
                        "seed": 1000 + trial,
                        "model_id": "gpt-test",
                        "environment_digest": ENVIRONMENT_DIGEST,
                        "evidence_tier": "ci_verified",
                        "success": True,
                        "assertions_passed": assertion_count,
                        "assertions_total": assertion_count,
                        "planner_input_tokens": values["planner_input_tokens"],
                        "planner_output_tokens": values["planner_output_tokens"],
                        "planner_model_calls": values["planner_model_calls"],
                        "tool_calls": tool_calls,
                        "retries": values["retries"],
                        "duration_ms": values["duration_ms"],
                        "false_reuse": False,
                        "visible_cost_usd": 0.01,
                    }
                )
    return records


def _warm_record(records, task_id=None):
    return next(
        record
        for record in records
        if record["mode"] == "blueprint_warm"
        and (task_id is None or record["task_id"] == task_id)
    )


def _write_runs(path, records):
    path.write_text(
        "".join(
            json.dumps(record, sort_keys=True, allow_nan=False) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def test_versioned_suite_covers_the_required_proof_surfaces():
    suite = load_suite(SUITE_PATH)
    task_ids = {task["id"] for task in suite["tasks"]}
    splits = {task["split"] for task in suite["tasks"]}

    assert {
        "ordinary-conversation-does-not-call-mcp",
        "multilingual-negation-zh",
        "multilingual-negation-ja",
        "malformed-community-evidence-cannot-promote",
        "incompatible-blueprint-is-not-reused",
    }.issubset(task_ids)
    assert splits == {"public_eval", "adversarial", "sealed_holdout"}


def test_describe_suite_hides_the_sealed_prompt_and_binds_every_task():
    description = describe_suite(load_suite(SUITE_PATH))
    sealed = next(task for task in description["tasks"] if task["sealed"])

    assert description["suite_digest"].startswith("sha256:")
    assert sealed["task_digest"].startswith("sha256:")
    assert "prompt" not in sealed


def test_verified_scorecard_measures_planner_scope_without_overclaiming():
    suite = _suite()
    scorecard = build_scorecard(suite, _records(suite))

    assert scorecard["proof_status"] == "verified"
    assert scorecard["gate"]["passed"] is True
    assert scorecard["claim_scope"] == "planner_model_usage_only"
    assert scorecard["comparisons"]["end_to_end"]["planner_token_reduction"] == 0.5
    assert (
        scorecard["comparisons"]["blueprint_effect"]["planner_token_reduction"]
        == 0.4444
    )
    assert (
        scorecard["comparisons"]["blueprint_effect"]["baseline_mode"]
        == "flyto_no_blueprint"
    )
    assert (
        scorecard["comparisons"]["blueprint_effect"][
            "paired_planner_token_reduction_ci_95_lower_bound"
        ]
        == 0.4444
    )
    assert scorecard["comparisons"]["end_to_end"]["success_rate_delta"] == 0.0
    assert scorecard["comparisons"]["end_to_end"]["p95_latency_increase"] == 0.05
    assert scorecard["modes"]["blueprint_warm"]["false_reuse_count"] == 0
    assert scorecard["modes"]["blueprint_warm"]["assertion_pass_rate"] == 1.0
    assert scorecard["scorecard_digest"].startswith("sha256:")


def test_scorecard_is_deterministic_when_run_order_changes():
    suite = _suite()
    records = _records(suite)

    first = build_scorecard(suite, records)
    second = build_scorecard(suite, list(reversed(records)))

    assert first == second


def test_missing_task_evidence_is_insufficient_not_verified():
    suite = _suite()
    records = [
        record
        for record in _records(suite)
        if record["task_id"] != "sealed-multilingual-routing-holdout"
    ]

    scorecard = build_scorecard(suite, records)

    assert scorecard["proof_status"] == "insufficient_evidence"
    coverage = next(
        check for check in scorecard["gate"]["checks"]
        if check["id"] == "task_coverage"
    )
    assert coverage["passed"] is False


def test_too_few_trials_is_insufficient_evidence():
    suite = _suite(min_trials=3)

    scorecard = build_scorecard(suite, _records(suite, trials=2))

    assert scorecard["proof_status"] == "insufficient_evidence"


def test_token_claim_fails_when_reduction_is_below_threshold():
    suite = _suite()
    records = _records(suite)
    for record in records:
        if record["mode"] == "blueprint_warm":
            record["planner_input_tokens"] = 75
            record["planner_output_tokens"] = 15

    scorecard = build_scorecard(suite, records)

    assert scorecard["proof_status"] == "regression"
    assert scorecard["comparisons"]["end_to_end"]["planner_token_reduction"] == 0.1


def test_blueprint_must_help_beyond_flyto_routing_to_pass():
    suite = _suite()
    records = _records(suite)
    for record in records:
        if record["mode"] == "blueprint_warm":
            record["planner_input_tokens"] = 50
            record["planner_output_tokens"] = 15

    scorecard = build_scorecard(suite, records)

    assert (
        scorecard["comparisons"]["end_to_end"]["planner_token_reduction"]
        == 0.35
    )
    assert (
        scorecard["comparisons"]["blueprint_effect"]["planner_token_reduction"]
        == 0.2778
    )
    assert scorecard["proof_status"] == "regression"
    blueprint_check = next(
        check
        for check in scorecard["gate"]["checks"]
        if check["id"] == "blueprint_effect_planner_token_reduction"
    )
    assert blueprint_check["passed"] is False


def test_token_reduction_must_survive_paired_confidence_bound():
    suite = _suite()
    records = _records(suite)
    warm_records = [
        record for record in records if record["mode"] == "blueprint_warm"
    ]
    for index, record in enumerate(warm_records):
        if index < 9:
            record["planner_input_tokens"] = 35
            record["planner_output_tokens"] = 15
        else:
            record["planner_input_tokens"] = 75
            record["planner_output_tokens"] = 15

    scorecard = build_scorecard(suite, records)

    blueprint_effect = scorecard["comparisons"]["blueprint_effect"]
    assert blueprint_effect["paired_planner_token_reduction_median"] == 0.4444
    assert (
        blueprint_effect[
            "paired_planner_token_reduction_ci_95_lower_bound"
        ]
        == 0.0
    )
    assert scorecard["proof_status"] == "regression"


def test_false_reuse_fails_the_gate_even_when_every_run_succeeds():
    suite = _suite()
    records = _records(suite)
    _warm_record(
        records,
        task_id="incompatible-blueprint-is-not-reused",
    )["false_reuse"] = True

    scorecard = build_scorecard(suite, records)

    assert scorecard["proof_status"] == "regression"
    false_reuse = next(
        check for check in scorecard["gate"]["checks"]
        if check["id"] == "false_reuse"
    )
    assert false_reuse["actual"] == 1


def test_failed_assertion_cannot_be_reported_as_success():
    suite = _suite()
    records = _records(suite)
    record = _warm_record(records)
    record["assertions_passed"] -= 1

    with pytest.raises(BenchmarkValidationError, match="assertion outcome"):
        build_scorecard(suite, records)


def test_host_cannot_skip_suite_assertions():
    suite = _suite()
    records = _records(suite)
    records[0]["assertions_total"] -= 1
    records[0]["assertions_passed"] -= 1

    with pytest.raises(BenchmarkValidationError, match="does not match task"):
        build_scorecard(suite, records)


def test_missing_comparison_mode_is_rejected():
    suite = _suite()
    records = _records(suite)
    records.pop()

    with pytest.raises(BenchmarkValidationError, match="missing mode"):
        build_scorecard(suite, records)


def test_duplicate_mode_for_one_trial_is_rejected():
    suite = _suite()
    records = _records(suite)
    records.append(copy.deepcopy(records[0]))

    with pytest.raises(BenchmarkValidationError, match="duplicate mode"):
        build_scorecard(suite, records)


def test_paired_modes_must_use_the_same_seed():
    suite = _suite()
    records = _records(suite)
    _warm_record(records)["seed"] = 9999

    with pytest.raises(BenchmarkValidationError, match="paired seed"):
        build_scorecard(suite, records)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_commit", "2" * 40, "dataset_commit"),
        ("model_id", "different-model", "model_id"),
        ("environment_digest", "sha256:" + ("b" * 64), "environment_digest"),
    ],
)
def test_one_scorecard_cannot_mix_provenance(field, value, message):
    suite = _suite()
    records = _records(suite)
    _warm_record(records)[field] = value

    with pytest.raises(BenchmarkValidationError, match=message):
        build_scorecard(suite, records)


def test_wrong_task_digest_is_rejected():
    suite = _suite()
    records = _records(suite)
    records[0]["task_digest"] = "sha256:" + ("f" * 64)

    with pytest.raises(BenchmarkValidationError, match="task_digest mismatch"):
        build_scorecard(suite, records)


def test_community_evidence_cannot_enter_a_trusted_scorecard():
    suite = _suite()
    records = _records(suite)
    records[0]["evidence_tier"] = "community"

    with pytest.raises(BenchmarkValidationError, match="ci_verified"):
        build_scorecard(suite, records)


def test_arbitrary_prompt_or_secret_fields_are_rejected():
    suite = _suite()
    records = _records(suite)
    records[0]["raw_prompt"] = "do not persist"

    with pytest.raises(BenchmarkValidationError, match="raw_prompt"):
        build_scorecard(suite, records)


def test_boolean_is_not_accepted_as_a_numeric_metric():
    suite = _suite()
    records = _records(suite)
    records[0]["planner_input_tokens"] = True

    with pytest.raises(BenchmarkValidationError, match="integer"):
        build_scorecard(suite, records)


def test_non_finite_json_evidence_is_rejected_with_line_number(tmp_path):
    runs_path = tmp_path / "bad.runs.jsonl"
    runs_path.write_text('{"duration_ms": NaN}\n', encoding="utf-8")

    with pytest.raises(BenchmarkValidationError, match="line 1"):
        load_runs(runs_path)


def test_duplicate_json_fields_are_rejected(tmp_path):
    runs_path = tmp_path / "duplicate.runs.jsonl"
    runs_path.write_text(
        '{"schema_version":"benchmark-run.v1","schema_version":"forged"}\n',
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkValidationError, match="duplicate JSON"):
        load_runs(runs_path)


def test_duplicate_yaml_keys_are_rejected(tmp_path):
    suite_path = tmp_path / "duplicate-suite.yaml"
    suite_path.write_text(
        "schema_version: benchmark-suite.v1\n"
        "schema_version: forged\n",
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkValidationError, match="duplicate YAML"):
        load_suite(suite_path)


def test_sealed_task_cannot_expose_its_prompt():
    suite = _suite()
    sealed = next(task for task in suite["tasks"] if task["sealed"])
    sealed["prompt"] = "leaked holdout"

    with pytest.raises(BenchmarkValidationError, match="must not expose"):
        suite_digest(suite)


def test_public_task_cannot_supply_a_self_declared_digest():
    suite = _suite()
    public = next(task for task in suite["tasks"] if not task["sealed"])
    public["task_digest"] = "sha256:" + ("e" * 64)

    with pytest.raises(BenchmarkValidationError, match="generated"):
        suite_digest(suite)


def test_cli_writes_a_verified_scorecard(tmp_path):
    suite = _suite()
    suite_path = tmp_path / "suite.yaml"
    runs_path = tmp_path / "release.runs.jsonl"
    output_path = tmp_path / "release.scorecard.json"
    suite_path.write_text(
        json.dumps(suite, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_runs(runs_path, _records(suite))

    exit_code = main(
        [
            "score",
            "--suite",
            str(suite_path),
            "--runs",
            str(runs_path),
            "--output",
            str(output_path),
            "--fail-on-regression",
        ]
    )

    assert exit_code == 0
    assert json.loads(output_path.read_text())["proof_status"] == "verified"


def test_cli_returns_one_when_a_valid_scorecard_regresses(tmp_path):
    suite = _suite()
    records = _records(suite)
    for record in records:
        if record["mode"] == "blueprint_warm":
            record["planner_input_tokens"] = 80
            record["planner_output_tokens"] = 20
    suite_path = tmp_path / "suite.yaml"
    runs_path = tmp_path / "regression.runs.jsonl"
    suite_path.write_text(json.dumps(suite), encoding="utf-8")
    _write_runs(runs_path, records)

    assert main(
        [
            "score",
            "--suite",
            str(suite_path),
            "--runs",
            str(runs_path),
            "--fail-on-regression",
        ]
    ) == 1


def test_empty_result_directory_makes_no_performance_claim(tmp_path):
    result = verify_result_directory(_suite(), tmp_path)

    assert result["passed"] is True
    assert result["status"] == "no_results"
    assert "no performance claim" in result["message"]


def test_missing_result_directory_fails_closed(tmp_path):
    result = verify_result_directory(_suite(), tmp_path / "missing")

    assert result["passed"] is False
    assert result["status"] == "failed"
    assert result["issues"] == ["benchmark results directory does not exist"]


def test_orphan_scorecard_cannot_look_like_a_claim(tmp_path):
    (tmp_path / "release.scorecard.json").write_text("{}\n", encoding="utf-8")

    result = verify_result_directory(_suite(), tmp_path)

    assert result["passed"] is False
    assert result["issues"] == [
        "release.scorecard.json: missing raw run evidence"
    ]


def test_committed_scorecard_is_rebuilt_and_verified(tmp_path):
    suite = _suite()
    records = _records(suite)
    runs_path = tmp_path / "release.runs.jsonl"
    scorecard_path = tmp_path / "release.scorecard.json"
    _write_runs(runs_path, records)
    write_scorecard(build_scorecard(suite, records), scorecard_path)

    result = verify_result_directory(suite, tmp_path)

    assert result["passed"] is True
    assert result["verified_count"] == 1


def test_edited_or_stale_committed_scorecard_fails_verification(tmp_path):
    suite = _suite()
    records = _records(suite)
    runs_path = tmp_path / "release.runs.jsonl"
    scorecard_path = tmp_path / "release.scorecard.json"
    _write_runs(runs_path, records)
    scorecard = build_scorecard(suite, records)
    scorecard["comparisons"]["end_to_end"]["planner_token_reduction"] = 0.99
    write_scorecard(scorecard, scorecard_path)

    result = verify_result_directory(suite, tmp_path)

    assert result["passed"] is False
    assert result["issues"] == [
        "release.scorecard.json: scorecard is stale or edited"
    ]
