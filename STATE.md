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
- A versioned benchmark can validate host-executed four-mode paired evidence,
  generate deterministic scorecards, and reject reliability, false-reuse,
  planner-token, or latency regressions. No result dataset is committed, so no
  benchmark performance claim exists yet.
- Generated reference covers 20 package modules and 155 class, function, and
  method declarations. CI rejects declaration, catalog, and MCP schema drift.
- Documentation contract maps seven source areas and nine feature surfaces to
  durable docs and test evidence.
- Routine Dependabot version branches are disabled for Python and GitHub
  Actions; security updates remain enabled. Release Actions use verified
  updates, and the single Grype exception is bound to the patched PyPI Action
  commit instead of suppressing the package broadly.
- Latest local verification on 2026-07-27: Ruff passed, 167 tests passed,
  generated documentation is current, benchmark result integrity passed with
  the explicit `no_results` status, and sdist/wheel build passed. Flyto2
  Indexer strict full-scan passed 17/17 with no warnings and a documentation
  score of 100. Remote workflow verification remains the final release gate for
  this change.

## Release Notes

- No repository-local release blocker is recorded.
- Publishing to PyPI and provider-side workflow success still require remote
  evidence; local verification cannot prove registry permissions.
- A trusted host must still collect at least 20 paired trials per benchmark task
  before the repository can make a performance claim.
