# The agent stopped solving the same job from scratch

The pain is simple: an agent can finish a job today and still spend another
full planning call rediscovering the same steps tomorrow. Chat memory remembers
the conversation. Vector search can find similar text. Neither one guarantees
that the exact procedure which passed its tests will run again.

Blueprint turns the successful procedure into executable memory. The first run
may still plan. A verified warm run searches the learned procedure, checks its
trust and compatibility, expands it, executes it, and records the outcome. If
failures drive its score below 10, it is retired immediately and remains
retired after SQLite reload.

## What we actually ran

This result contains five complete runs. Each run has 10 tasks, 20 paired
trials, and four modes: 800 raw records per run, 4,000 in total.

- Models: Qwen3 0.6B, Llama 3.2 1B, and Gemma 3 1B.
- Hardware: Apple M1 Pro and GitHub-hosted Linux x86-64.
- Independent boundary: one Qwen run executed in GitHub Actions
  ([run 30322935702](https://github.com/flytohub/flyto-ai/actions/runs/30322935702)).
- Real work: Python files plus `unittest`, loopback HTTP plus HTML parsing,
  loopback JSON API plus filesystem persistence, and a real Ollama-backed LLM
  workflow step.
- Guardrails: ordinary conversation, Traditional Chinese and Japanese
  negation, hostile community evidence, incompatible reuse, and a sealed
  multilingual holdout.
- Mocks: none in the published run path. Loopback services are controlled real
  HTTP fixtures, not replaced function calls.

Every model response and private prompt stayed out of Git. The raw records keep
only identities, counters, assertion results, timings, and SHA-256 digests.

## Result

| Run | Host | Warm success | Workload success | Total tokens vs agent | Total tokens vs Flyto2 without Blueprint |
| --- | --- | ---: | ---: | ---: | ---: |
| Qwen3 0.6B A | Apple Silicon | 100% | 100% | -85.78% | -72.90% |
| Qwen3 0.6B B | Apple Silicon | 100% | 100% | -85.78% | -72.90% |
| Llama 3.2 1B | Apple Silicon | 100% | 100% | -84.80% | -71.25% |
| Gemma 3 1B | Apple Silicon | 100% | 100% | -85.39% | -72.62% |
| Qwen3 0.6B | GitHub Linux | 100% | 100% | -84.99% | -71.83% |

All five runs had zero manual corrections and zero false reuse. The paired 95%
lower bound for the Blueprint-specific full-token reduction ranged from 63.29%
to 64.43%, above the suite's 15% gate. The two Qwen Apple runs also form a
longitudinal comparison: success drop 0 and total-token increase 0.

The directory-level verifier rebuilt all five scorecards and closed these
gates:

```text
verified scorecards: 5/5
model families:       3
hardware families:    2
independent runners:  1
history comparisons:  1 passed
```

The separate [longitudinal evidence](../longitudinal/) exercises the product
lifecycle itself: learn → trusted successes → 20 reuses → trusted failures →
score below 10 → immediate retirement → reload still retired. Both the local
and GitHub SQLite runs passed.

## Rebuild the claim

Do not trust this page. Rebuild every scorecard from its JSONL:

```bash
python scripts/benchmark-scorecard.py verify-results \
  --suite benchmarks/suites/blueprint-effectiveness-v3.yaml \
  --results-dir benchmarks/results/blueprint-effectiveness-v3
```

The command fails if a raw record is missing, a scorecard was edited, model or
hardware diversity disappears, the independent result is absent, or a later
Qwen run loses success or grows total tokens beyond the configured limit.

The reusable local matrix lives in
[`flyto-ai/benchmarks/blueprint-v3-model-matrix.yaml`](https://github.com/flytohub/flyto-ai/blob/main/benchmarks/blueprint-v3-model-matrix.yaml).
Its model names are bound to installed Ollama digests. The private holdout
prompt must be supplied through `FLYTO_BENCHMARK_SEALED_PROMPT`; it is never
committed.

## What this does not prove

This is a controlled workload suite, not a general coding leaderboard.
Loopback browser/API work proves real network and filesystem paths without
depending on a changing public website. Local Ollama has zero visible dollar
cost, so the scorecards do not invent a cloud-price estimate. Provider-internal
usage that Ollama does not expose is outside the claim. A different model,
task distribution, or production host must rerun the same gates before making
its own performance claim.
