# Flyto2 Blueprint State

## Current State

- Repository status: active open-source Python package, version 0.2.2.
- Stable package root exports `BlueprintEngine`, `StorageBackend`,
  `MemoryBackend`, and `get_engine`.
- The package ships 33 workflow blueprints, one composition block, six MCP
  tool schemas, and memory, SQLite, and optional Firestore storage.
- Continuous learning separates trusted scores from bounded community
  observations, scopes reuse with compatibility metadata, and preserves
  retry/assertion contracts.
- Portable bundle export/import is explicit, integrity-checked, sensitive-data
  guarded, optionally host-signed, and quarantines unknown publishers.
- Every Blueprint summary exposes an Evidence Card with trusted outcome counts,
  Wilson 95% lower bound, retry/assertion rates, latency percentiles, and
  measured zero-planner-call reuse. This does not claim that model-backed
  workflow steps are token-free. Detailed evidence is allowlisted and capped
  to the latest 100 samples.
- Blueprint list/search summaries expose ordered, unique `module_ids` without
  step parameters, enabling trust-gated capability ranking in Flyto2 AI.
- V3 benchmark evidence is committed: five verified 800-record runs across
  Qwen, Llama, and Gemma; Apple Silicon and Linux x86-64; and one independent
  GitHub runner. Warm benchmark/workload success is 100% in every run, manual
  corrections and false reuse are zero, and full observed tokens fall
  71.25–72.90% versus Flyto2 without Blueprint.
- The result-directory gate rebuilds scorecards and requires three model
  families, two hardware families, an independent runner, and a non-regressing
  historical comparison. The repeated Qwen series has success drop 0 and token
  increase 0.
- Real SQLite lifecycle evidence exists for local and GitHub hosts. It proves
  learn, trusted promotion, 20 reuses, trusted failure downgrade, immediate
  retirement below score 10, and retirement persistence after Engine reload.
- Generated reference covers 21 package modules and 168 class, function, and
  method declarations. CI rejects declaration, catalog, and MCP schema drift.
- Documentation contract maps seven source areas and nine feature surfaces to
  durable docs and test evidence.
- Routine Dependabot version branches are disabled for Python and GitHub
  Actions; security updates remain enabled. Release Actions use verified
  updates, and the single Grype exception is bound to the patched PyPI Action
  commit instead of suppressing the package broadly.
- Robotics/vision is not yet promoted to an official Blueprint; it is gated on
  evidence, not excluded from the product. A Blueprint search
  for `robotics vision exhibition` returns no candidates; that is an honest
  not-applicable result, and Flyto2 AI may continue to Core discovery and
  validation. On 2026-08-10 a read-only lower check with the real
  `core.mcp_handler.validate_params` accepted `robotics.move`, `robotics.turn`,
  `robotics.stop`, and `vision.observe` with bounded arguments, and rejected
  missing distance, distance 999, missing degrees, a non-text zone, and unknown
  `robotics.fly`. That proves module registration and parameter validation only:
  no execute call, gateway request, pixels, physical camera identity, robot or
  motor action, or authenticated Cloud route. Physical acceptance remains
  pending the OpenCR/device-side issue.
- Latest full local verification on 2026-07-28: Ruff passed, 183 tests passed,
  generated documentation was current, sdist/wheel build passed, and Flyto2
  Indexer strict full-scan passed 17/17 with no warnings and documentation
  score 100. The independent Flyto2 AI benchmark workflow run 30322935702
  passed all steps; final CI for the evidence/documentation commit remains the
  release gate.

## Release Notes

- No repository-local release blocker is recorded.
- Publishing to PyPI and provider-side workflow success still require remote
  evidence; local verification cannot prove registry permissions.
- No official robotics/vision Blueprint may be shipped before repeated trusted
  real-workload outcomes and a completed physical loop; see `DECISIONS.md`
  (2026-08-10) for the promotion checklist. Gazebo and gateway-report evidence
  from lower repositories is not Blueprint outcome evidence.
- New model, task, or host claims must collect at least 20 paired trials per
  task and pass the same v3 directory closure; the current result must not be
  generalized beyond its committed suite and observable provider counters.
