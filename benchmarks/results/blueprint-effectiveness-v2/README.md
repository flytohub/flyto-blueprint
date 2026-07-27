# The agent kept thinking. Blueprint knew when to stop.

An agent gets a job it has seen before. It can ask a model to plan everything
again, or it can reuse a procedure that already worked.

Reuse sounds cheaper. It is also dangerous when the router calls tools during a
casual chat, misses “do not use” in another language, trusts forged success
claims, or forces an incompatible workflow just to save tokens.

This run tested both sides of that story.

## What happened

Ten tasks each ran 20 times in four modes. That produced 200 paired trials and
800 measurement records on a local Qwen3 8B planner.

| Mode | Assertion success | Planner calls | Planner tokens | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| Agent baseline | 10% | 200 | 26,366 | 1,018.602 ms |
| Flyto2, no Blueprint | 60% | 80 | 10,660 | 1,002.218 ms |
| Blueprint cold | 60% | 80 | 11,040 | 1,003.872 ms |
| Blueprint warm | 100% | 20 | 2,880 | 755.311 ms |

Compared with Flyto2 without Blueprint, warm verified reuse:

- used 72.98% fewer total planner tokens;
- made 75% fewer planner model calls;
- improved task-specific assertion success by 40 percentage points;
- reduced p95 latency by 24.64%;
- passed all 600 candidate assertions with zero false reuse.

The statistical gate also passed. It found 80 informative token pairs; the
paired median reduction and its exact 95% confidence lower bound were both
100%. The other 120 pairs were `0/0`: neither mode needed a planner, so the
scorecard excludes them instead of pretending they prove a saving.

## What tried to break it

The suite includes explicit reuse, deterministic CSV-to-JSON work, ordinary
English and Traditional Chinese conversation, Traditional Chinese and Japanese
negation, a quoted destructive request, forged community evidence, an
incompatible Blueprint, and a private multilingual holdout.

The incompatible case matters: warm Blueprint still made 20 planner calls
because refusing unsafe reuse and replanning is the correct outcome. The
benchmark does not reward low token use when correctness would be lost.

## Inspect or rerun it

- [Raw measurement records](ollama-flyto-qwen3-8b-2026-07-28.runs.jsonl)
- [Generated scorecard](ollama-flyto-qwen3-8b-2026-07-28.scorecard.json)
- [Ten-task suite](../../suites/blueprint-effectiveness-v2.yaml)
- [Reusable host configuration](../../templates/host-run-template.yaml)
- [Benchmark method](../../../docs/BENCHMARKING.md)

The records pin the model digest, dataset commit, paired seeds, task digests,
and environment digest. They contain no raw prompt, model response, credential,
or customer data. CI rebuilds the scorecard from the JSONL and rejects it if a
record or result was edited.

## The honest limit

This proves a narrow result: planner-model usage and task-specific assertions
on this suite, with this local model and host. It does not measure tokens inside
an `llm.*` workflow step, prove that every agent will improve, or compare
general coding ability.

The agent-baseline success rate is also not a general Qwen3 score. It says how
often that baseline satisfied these routing, reuse, and safety assertions.
Visible cost is zero because Ollama ran locally; that is not a cloud-price
estimate.
