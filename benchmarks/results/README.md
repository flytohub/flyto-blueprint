# Benchmark results

This directory starts empty on purpose. An empty directory means **Flyto2
Blueprint makes no benchmark performance claim yet**.

When a trusted host completes the full suite, commit two files with the same
prefix:

```text
<release>.runs.jsonl
<release>.scorecard.json
```

Generate the scorecard from the raw records:

```bash
python scripts/benchmark-scorecard.py score \
  --suite benchmarks/suites/blueprint-effectiveness-v1.yaml \
  --runs benchmarks/results/<release>.runs.jsonl \
  --output benchmarks/results/<release>.scorecard.json \
  --fail-on-regression
```

CI rebuilds every scorecard byte-for-byte and fails when evidence is malformed,
edited, stale, incomplete, or below the suite's thresholds. Do not commit raw
prompts, credentials, customer data, provider request bodies, or private
holdout content. `ci_verified` means the configured host is trusted to produce
the run facts; the scorecard cannot see or prove provider-internal token usage.
