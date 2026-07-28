import copy
import json
from pathlib import Path

from flyto_blueprint.longitudinal import (
    main,
    run_longitudinal_evidence,
    verify_longitudinal_evidence,
)


COMMIT = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def test_real_sqlite_lifecycle_closes_learning_loop(tmp_path):
    evidence = run_longitudinal_evidence(
        tmp_path / "lifecycle.sqlite3",
        repository_commit=COMMIT,
        run_id="real-lifecycle-test",
    )

    assert evidence["proof_status"] == "verified"
    assert evidence["successful_reuses"] == 20
    assert evidence["persisted_use_count"] >= 20
    assert evidence["promotion_scores"][-1] > evidence["initial_score"]
    assert evidence["retired"] is True
    assert evidence["retired_score"] < 10
    assert verify_longitudinal_evidence(evidence)["passed"] is True


def test_longitudinal_verifier_rejects_edited_metrics(tmp_path):
    evidence = run_longitudinal_evidence(
        tmp_path / "lifecycle.sqlite3",
        repository_commit=COMMIT,
        run_id="tamper-test",
    )
    edited = copy.deepcopy(evidence)
    edited["successful_reuses"] = 999

    result = verify_longitudinal_evidence(edited)

    assert result["passed"] is False
    assert result["issues"] == ["evidence_digest mismatch"]


def test_longitudinal_cli_runs_and_verifies_real_sqlite(tmp_path, capsys):
    database = tmp_path / "lifecycle.sqlite3"
    output = tmp_path / "lifecycle.evidence.json"

    assert main(
        [
            "run",
            "--database",
            str(database),
            "--repository-commit",
            COMMIT,
            "--run-id",
            "cli-real-lifecycle",
            "--output",
            str(output),
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True
    assert main(["verify", "--evidence", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_committed_local_and_independent_lifecycle_evidence_is_verified():
    evidence_paths = sorted(
        (ROOT / "benchmarks/results/longitudinal").glob(
            "*.evidence.json"
        )
    )

    assert [path.name for path in evidence_paths] == [
        "github-longitudinal.evidence.json",
        "local-longitudinal.evidence.json",
    ]
    for path in evidence_paths:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        assert verify_longitudinal_evidence(evidence)["passed"] is True
