# Benchmark results

Results live in a suite-specific subdirectory. The first verified result is
[`blueprint-effectiveness-v2`](blueprint-effectiveness-v2/README.md): 10 tasks,
20 paired trials per task, four modes, and 800 measurement records.

Each result commits two files with the same prefix:

```text
<suite>/<release>.runs.jsonl
<suite>/<release>.scorecard.json
```

Generate the scorecard from the raw records:

```bash
python scripts/benchmark-scorecard.py score \
  --suite benchmarks/suites/blueprint-effectiveness-v2.yaml \
  --runs benchmarks/results/blueprint-effectiveness-v2/<release>.runs.jsonl \
  --output benchmarks/results/blueprint-effectiveness-v2/<release>.scorecard.json \
  --fail-on-regression
```

CI rebuilds every scorecard byte-for-byte and fails when evidence is malformed,
edited, stale, incomplete, or below the suite's thresholds. Do not commit raw
prompts, credentials, customer data, provider request bodies, or private
holdout content. `ci_verified` means the configured host is trusted to produce
the run facts; the scorecard cannot see or prove provider-internal token usage.
