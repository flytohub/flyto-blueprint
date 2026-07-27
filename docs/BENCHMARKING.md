# Proving Blueprint Helps

## A fast demo is not proof

Imagine an agent completes the same job twice.

The first time it plans every step with a model. The second time Blueprint
reuses a procedure that worked before. The second run looks faster and cheaper,
so it is tempting to declare victory.

But three failures can hide behind that demo:

- the reused procedure may silently produce the wrong result;
- the router may call Blueprint during ordinary conversation or ignore
  “do not use MCP” in another language;
- a different model, environment, or lucky random seed may explain the win.

This benchmark exists to catch those failures. It does not execute an agent.
The host runs the experiment; this package checks that the evidence is paired,
complete, comparable, and strong enough to support a narrow claim.

## The result in one screen

On 2026-07-28, a local `flyto-qwen3:8b` planner ran 10 routing, reuse, and
guardrail tasks 20 times in every mode: 800 records and 200 paired trials.

| Mode | Assertion success | Planner calls | Planner tokens | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| Agent baseline | 10% | 200 | 26,366 | 1,018.602 ms |
| Flyto2, no Blueprint | 60% | 80 | 10,660 | 1,002.218 ms |
| Blueprint cold | 60% | 80 | 11,040 | 1,003.872 ms |
| Blueprint warm | 100% | 20 | 2,880 | 755.311 ms |

Warm Blueprint versus Flyto2 without Blueprint used 72.98% fewer total planner
tokens and 75% fewer planner model calls. Its benchmark success rate improved
by 40 percentage points, p95 latency fell 24.64%, all 600 candidate assertions
passed, and false reuse was zero. Across the 80 informative token pairs, the
median reduction and its exact 95% confidence lower bound were both 100%.
Pairs where neither mode called a planner are excluded from that median rather
than treated as free wins.

This is a focused planner-routing benchmark, not a general intelligence or
coding benchmark. The 10% baseline is the rate at which that baseline satisfied
these task-specific routing and safety assertions; it is not a statement that
Qwen3 succeeds at only 10% of ordinary work. The full story, raw JSONL, and
scorecard are in the
[v2 result directory](../benchmarks/results/blueprint-effectiveness-v2/README.md).

## The experiment

Every task and trial runs in four modes with the same model, environment, and
seed:

| Mode | Question it answers |
| --- | --- |
| `agent_baseline` | What happens when the agent works without Flyto2 routing? |
| `flyto_no_blueprint` | What does Flyto2 routing cost before Blueprint helps? |
| `blueprint_cold` | What happens before a verified reusable procedure is warm? |
| `blueprint_warm` | What happens when verified reuse is available? |

The scorecard reports three comparisons. `end_to_end` compares
`blueprint_warm` with `agent_baseline`; `blueprint_effect` compares it with
`flyto_no_blueprint`; and `warmup_effect` compares it with `blueprint_cold`.
The evidence gate requires both the end-to-end and Blueprint-specific
comparisons to pass. This prevents a routing improvement from being
misattributed to Blueprint. The warm-up comparison remains visible for
diagnosis but is not used to manufacture a claim.

The public suite includes successful reuse, ordinary conversation that must not
call MCP, Traditional Chinese and Japanese negation, forged community evidence,
and an incompatible Blueprint that must not be reused. A sealed holdout is
stored only as a SHA-256 commitment so its prompt does not become training data
in the repository.

## What one run records

The trusted host writes one `benchmark-run.v1` JSON object per line. It records
identities and measurements, not prompts or model responses:

- suite, task, dataset commit, model, and environment identities;
- mode, trial, paired seed, split, and `ci_verified` evidence tier;
- passed assertions and the resulting success value;
- planner input/output tokens and planner model calls;
- tool calls, retries, duration, false reuse, and optional visible cost.

The validator rejects unknown or duplicate fields and requires the recorded
assertion count to match the suite. That is deliberate: ambiguous records, raw
prompts, credentials, provider request bodies, and customer output do not
belong in committed evidence.

Use the suite description to obtain the exact digests a host must record:

```bash
flyto-blueprint-benchmark describe-suite \
  --suite benchmarks/suites/blueprint-effectiveness-v2.yaml
```

Inside a repository checkout, the equivalent command is:

```bash
python scripts/benchmark-scorecard.py describe-suite \
  --suite benchmarks/suites/blueprint-effectiveness-v2.yaml
```

The reusable, secret-free host configuration is
[`benchmarks/templates/host-run-template.yaml`](../benchmarks/templates/host-run-template.yaml).
It pins the local model digest, disables model thinking, limits the response to
32 tokens, and requires 20 trials. A sealed task prompt stays outside Git and
must match the digest in the suite; replace both when creating a private
holdout for a new benchmark.

## What counts as passing

Version 1 refuses a verified result unless all configured checks pass:

- every task and required split is present;
- every task has at least 20 fully paired trials;
- warm reuse loses no more than two percentage points of success against
  either the agent or no-Blueprint baseline;
- its Wilson 95% success lower bound is at least 0.80;
- the exact paired 95% confidence lower bound for median planner-token
  reduction is at least 30% against both baselines;
- p95 latency grows by no more than 10% against either baseline;
- false reuse is zero;
- every candidate assertion passes.

A scorecard can therefore be `verified`, `insufficient_evidence`, or
`regression`. Missing trials are not mislabeled as failure, and a cheaper but
less reliable candidate does not pass.

Generate a scorecard after the trusted host writes its JSONL records:

```bash
python scripts/benchmark-scorecard.py score \
  --suite benchmarks/suites/blueprint-effectiveness-v2.yaml \
  --runs benchmarks/results/blueprint-effectiveness-v2/<release>.runs.jsonl \
  --output benchmarks/results/blueprint-effectiveness-v2/<release>.scorecard.json \
  --fail-on-regression
```

Commit both files. CI rebuilds every scorecard and rejects missing, edited,
stale, malformed, incomplete, or below-threshold evidence:

```text
benchmarks/results/blueprint-effectiveness-v2/<release>.runs.jsonl
benchmarks/results/blueprint-effectiveness-v2/<release>.scorecard.json
```

When the directory is empty, verification passes only as `no_results`. That
means there is no performance claim—not that Blueprint passed the benchmark.

## What this can and cannot prove

The scorecard's claim scope is `planner_model_usage_only`. It can show that the
host observed fewer planner tokens or calls while correctness gates held. It
cannot claim that an `llm.*` workflow step used no tokens, or reveal
provider-internal usage that the host could not observe.

`ci_verified` is a trust boundary, not cryptographic provider attestation. The
validator proves that committed records are internally consistent and that the
scorecard matches them exactly. It cannot prove that a dishonest host ran the
hidden prompt behind a sealed digest. Stronger future evidence should add
provider-signed usage receipts or an independent benchmark runner without
putting private prompts in Git.

That limitation is why the published result says exactly “planner usage on this
suite and host.” It does not turn one local run into a claim that Blueprint
makes every model, coding task, or model-backed workflow step cheaper.
