# Effectiveness benchmark handoff

Date: 2026-07-27

## Finished

- Added a versioned suite covering explicit reuse, ordinary conversation,
  Traditional Chinese and Japanese negation, hostile community evidence,
  incompatible reuse, and a sealed holdout.
- Added a validator and CLI for four-mode, same-seed paired evidence.
- Added deterministic scorecards with success confidence, planner tokens and
  calls, tool calls, retries, false reuse, latency, and visible cost.
- Added CI verification that rebuilds committed scorecards and rejects stale,
  malformed, incomplete, or below-threshold evidence.
- Added adversarial tests for identity drift, evidence poisoning, malformed
  numbers, pairing errors, false reuse, and regression status.

## Honest current limit

`benchmarks/results/` contains no run dataset. Verification therefore returns
`no_results`, which means no performance claim exists yet. The harness proves
how a claim will be checked; it does not prove that Blueprint is already
stronger or cheaper.

`ci_verified` also trusts the host to report real measurements. The scorecard
checks internal consistency and reproducibility, not provider-side execution.

## Next evidence step

Run all tasks through a trusted Flyto2 AI host in the four required modes with
at least 20 paired trials per task. Keep model, environment, dataset commit, and
seed identities fixed. Commit `<release>.runs.jsonl` and the generated
`<release>.scorecard.json` only when the gate reports `verified`.
