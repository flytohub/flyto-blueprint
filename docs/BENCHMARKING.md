# Proving Blueprint Helps

## The problem

An agent solves a job, passes the tests, and then forgets the useful part.
Tomorrow it asks a model to plan the same job again. That costs tokens and can
produce a different, worse plan.

Blueprint keeps the procedure which actually worked. But “it remembers” is not
enough. A reusable procedure can still be wrong, unsafe for another repository,
or accidentally invoked during ordinary conversation. A token claim can also
hide model calls inside the workflow.

The v3 benchmark makes those failures visible.

## The result in one screen

On 2026-07-28, five complete runs executed the same 10 tasks 20 times in four
paired modes: 4,000 raw records.

| Evidence gate | Result |
| --- | ---: |
| Verified scorecards | 5 / 5 |
| Model families | 3: Qwen, Llama, Gemma |
| Hardware families | 2: Apple Silicon, Linux x86-64 |
| Independent runners | 1 GitHub-hosted run |
| Warm benchmark success | 100% in every run |
| Warm real-workload success | 100% in every run |
| Manual corrections | 0 |
| False reuse | 0 |
| Total tokens vs generic agent | 84.80–85.78% lower |
| Total tokens vs Flyto2 without Blueprint | 71.25–72.90% lower |
| Paired 95% lower bound vs no Blueprint | 63.29–64.43% lower |
| Repeated Qwen history | success drop 0; token increase 0 |

Read the [result story](../benchmarks/results/blueprint-effectiveness-v3/README.md)
or rebuild every scorecard from the raw JSONL:

```bash
python scripts/benchmark-scorecard.py verify-results \
  --suite benchmarks/suites/blueprint-effectiveness-v3.yaml \
  --results-dir benchmarks/results/blueprint-effectiveness-v3
```

## What “real” means here

The published host does not replace planner, workflow, HTTP, subprocess, or
storage calls with mocks.

- Coding writes Python source and tests into an isolated directory, then runs
  `python -m unittest`.
- Browser work makes a real loopback HTTP request, parses returned HTML, and
  checks the heading.
- API work makes a real loopback JSON request, writes the response to disk,
  reloads it, and validates the data.
- LLM work makes a real Ollama chat call and uses Ollama's native input/output
  counters.
- Learning uses the real `BlueprintEngine`; longitudinal evidence uses the
  real `SQLiteBackend`.

Loopback HTTP keeps the fixture stable. It proves the network/parser/filesystem
path without letting a changing public website invalidate the experiment.

## Four paired modes

Every task and trial uses the same model, environment, dataset commit, and
seed:

| Mode | Question |
| --- | --- |
| `agent_baseline` | What happens when a generic agent plans without Flyto2 routing? |
| `flyto_no_blueprint` | What does Flyto2 routing cost before reusable memory helps? |
| `blueprint_cold` | What happens before the learned procedure is warm? |
| `blueprint_warm` | What happens when a verified compatible procedure is reused? |

The scorecard compares warm reuse with both the generic agent and Flyto2
without Blueprint. That second comparison matters: routing improvements must
not be mislabeled as Blueprint improvements.

The 10 tasks cover real coding, browser, API, and model-backed execution plus
ordinary conversation, Traditional Chinese and Japanese negation, hostile
community evidence, incompatible reuse, and a sealed multilingual holdout.

## Full usage accounting

`benchmark-run.v2` records planner and workflow counters separately:

- planner input/output tokens and model calls;
- workflow input/output tokens and model calls;
- checked totals for tokens, calls, and visible cost;
- real-workload success, duration, tool calls, and output digest;
- manual corrections, assertions, retries, and false reuse;
- exact model digest, host, hardware family, runner kind, repository commits,
  and run timestamp.

The validator rejects unknown or duplicate fields. Totals must equal planner
plus workflow values. Raw prompts, model responses, credentials, customer data,
and private holdout text are not accepted.

An individual Evidence Card still makes the narrower
`planner_model_calls_used=0` claim. Only a v3 scorecard with complete workflow
counters can use `full_observed_model_usage`.

## Gates that cannot be skipped

One scorecard is verified only when:

- all tasks, splits, modes, and 20 paired trials are present;
- success remains non-inferior against both baselines;
- the Wilson 95% lower bound for warm success passes;
- paired planner-token and full-token confidence bounds pass;
- p95 latency stays within the configured limit;
- real-workload success is 100%;
- manual corrections and false reuse are zero;
- every candidate assertion passes.

The result directory adds closure gates:

- at least three model families;
- at least two hardware families;
- at least one `independent_ci` run;
- at least one same-series historical comparison;
- no allowed success drop and no excessive token growth over history.

Deleting an inconvenient result therefore makes CI fail instead of making the
chart look better.

## Does learning survive failure?

Performance evidence is separate from lifecycle evidence. The longitudinal
runner uses SQLite to prove:

```text
learn -> trusted success -> reuse 20 times -> trusted failures
      -> score below 10 -> immediate retirement -> reload still retired
```

Run and verify it with the template in
[`benchmarks/results/longitudinal/`](../benchmarks/results/longitudinal/).

## Reproduce it

The model matrix and real host live in the sibling `flyto-ai` repository:

- `benchmarks/blueprint-v3-model-matrix.yaml`
- `scripts/run_blueprint_benchmark_matrix.py`
- `.github/workflows/blueprint-benchmark.yml`

Model names are bound to Ollama digests. The sealed prompt is injected through
`FLYTO_BENCHMARK_SEALED_PROMPT` and must match the suite's SHA-256 commitment.
It must never be written into Git.

After a host run, generate one scorecard:

```bash
python scripts/benchmark-scorecard.py score \
  --suite benchmarks/suites/blueprint-effectiveness-v3.yaml \
  --runs benchmarks/results/blueprint-effectiveness-v3/<run>.runs.jsonl \
  --output benchmarks/results/blueprint-effectiveness-v3/<run>.scorecard.json \
  --fail-on-regression
```

Then run the directory verifier shown above.

## What this does not prove

This is not a general intelligence or coding leaderboard. It is evidence for
the committed suite, model bytes, hosts, and runtime versions. Local Ollama
reports zero visible dollar cost, so the scorecards do not invent a cloud price.
Provider-internal use that Ollama does not expose stays outside the claim.

`ci_verified` is a trusted execution boundary, not cryptographic provider
attestation. The scorecard proves record consistency, reproducibility, gates,
and cross-run closure. A dishonest host could still lie. That is why the
independent GitHub runner, raw evidence, sealed digest, and exact model/commit
identities are kept together—and why a new production environment should rerun
the suite before repeating the claim.
