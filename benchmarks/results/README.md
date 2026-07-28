# Benchmark results

Results live in a suite-specific subdirectory. Start with the
[`blueprint-effectiveness-v3` story](blueprint-effectiveness-v3/README.md):
five real runs, 4,000 records, three model families, two hardware families,
full observed planner/workflow usage, an independent runner, and history
regression gates. The earlier
[`blueprint-effectiveness-v2`](blueprint-effectiveness-v2/README.md) result is
the narrower single-host planner-only baseline.

Each result commits two files with the same prefix:

```text
<suite>/<release>.runs.jsonl
<suite>/<release>.scorecard.json
```

Generate the scorecard from the raw records:

```bash
python scripts/benchmark-scorecard.py score \
  --suite benchmarks/suites/blueprint-effectiveness-v3.yaml \
  --runs benchmarks/results/blueprint-effectiveness-v3/<release>.runs.jsonl \
  --output benchmarks/results/blueprint-effectiveness-v3/<release>.scorecard.json \
  --fail-on-regression
```

CI rebuilds every scorecard byte-for-byte and fails when evidence is malformed,
edited, stale, incomplete, below the suite's thresholds, or missing required
model/hardware/history diversity. Longitudinal SQLite evidence lives in
[`longitudinal/`](longitudinal/) and is verified separately.

Do not commit raw prompts, model responses, credentials, customer data,
provider request bodies, or private holdout content. `ci_verified` means the
configured host is trusted to produce the run facts. V3 accounts for every
planner and workflow model counter exposed by Ollama; provider-internal usage
that the host cannot observe remains outside the claim.
