# Flyto2 Blueprint State

## Current State

- `SQLiteBackend` is safe across processes as well as threads: WAL plus
  `BEGIN IMMEDIATE` on every read-modify-write. Before this it lost 785 of 1,200
  concurrent updates without raising, in the ordinary configuration where each
  `flyto-ai` agent and the CLI open the same default `~/.flyto/blueprints.db`.
  Verified by `tests/test_storage_concurrency.py`, which spawns real processes.
- The `core` extra floors at `flyto-core>=2.29.0`; flyto-ai's stack floor gate
  derives that number from Core's own advisory manifest and checks this file.

- `flyto-blueprint` is Flyto2's independently usable layer-2
  `procedure_memory` package. It owns reusable procedure learning and scoring,
  procedure expansion and compatibility, and procedure outcome history. It
  never executes workflows; intent/provider governance belongs to Flyto2 AI,
  while deterministic validation, execution, replay, and evidence belong to
  Flyto2 Core.
- Blueprint is evidence-first: hosts supply validated execution outcomes that
  it persists and ranks. It does not guess mathematics, physics, chemistry,
  robotics, or other domain facts; bounded capabilities and hosts own those
  solvers and their acceptance evidence.
- Phase one of the Blueprint Capability Search Document/Index contract is
  implemented as stateless, provider-neutral JSON-native validation and
  derivation helpers. It is not wired to Flyto2 AI, Cloud, Core, a UI, storage,
  network, an embedding provider, or a vector database. Search results are
  candidate-only and the host still owns authorization and execution.
  The dialect matches upstream v1 192-character safe identifiers, at most 32
  semantic identifiers per field, NFC-preserved 2,000-character title/summary
  fields, exact `sha256:` digests,
  declared/static-derived origins, domain-neutral source kinds, and valid
  empty/incomplete audit data. Public reads detach bounded JSON, canonicalize
  set-like filters, bind candidates to model/index/snapshot digests, and require
  authenticated forward-only continuation state with a cumulative `top_k`
  count. Boundary-specific finite envelopes admit maximum producer documents
  and minimal 100-candidate pages without relaxing the shared depth ceiling.
  Null source kind is retained only for coherent incomplete audit projections;
  accepted projections require host-visible audit state, deterministic trust
  and routability coherence, and producer-sorted semantic IDs. The producer's
  192-character tenant/space/capability identity remains intact through
  documents, requests, candidates, and cursors.
- Repository status: active open-source Python package, version 0.3.0 (prepared
  in the working tree; PyPI still serves 0.2.2 until the `v0.3.0` tag is
  pushed).
- Why 0.3.0 exists: `flyto-ai` passes `available_module_ids` only when the
  installed engine signature accepts it, so the module-availability gate added
  in 0.2.2+ development was silently inert for every PyPI install -- 0.2.2 has
  no such parameter. The gate becomes reachable when this release ships, not
  when it was merged.
- A release-drift check now guards that condition instead of memory:
  `scripts/check_release_drift.py` is a required check in `.flyto/coding.yaml`
  and a CI step, and fails when a tag `v<version>` exists while the packaged
  source at HEAD differs from it. An unreleased version passes, so it asks for a
  correct version number rather than a release. The matching advisory-floor
  check lives in `flyto-ai`, the only repository whose CI has all three
  checkouts present; it covers this project's `flyto-core` floor too.
- Stable package root exports `BlueprintEngine`, `StorageBackend`,
  `MemoryBackend`, and `get_engine`.
- The package ships 33 workflow blueprints, one composition block, six MCP
  tool schemas, and memory, SQLite, and optional Firestore storage.
- Continuous learning separates trusted scores from bounded community
  observations, scopes reuse with compatibility metadata, and preserves
  retry/assertion contracts.
- Duplicate learning is non-promoting for both community and verified calls:
  it reports `deduplicated_existing` with memory, storage, trust, evidence,
  counters, and recent-report state unchanged. Arbitrary score boosts are
  disabled; the direct low-level learner independently receipt-gates trusted
  input and generic receipts cannot claim CI or official trust.
- Portable bundle export/import is explicit, integrity-checked, sensitive-data
  guarded, optionally host-signed, and quarantines unknown publishers.
- Every Blueprint summary exposes an Evidence Card with trusted outcome counts,
  Wilson 95% lower bound, retry/assertion rates, latency percentiles, and
  measured zero-planner-call reuse. This does not claim that model-backed
  workflow steps are token-free. Detailed evidence is allowlisted and capped
  to the latest 100 samples.
- Blueprint list/search summaries expose ordered, unique `module_ids` without
  step parameters, enabling trust-gated capability ranking in Flyto2 AI.
- `list_blueprints`, `search`, and `expand` accept an optional authoritative
  `available_module_ids` set supplied by the host. `None` preserves the
  previous behavior exactly, including abstract module names; a supplied set
  filters list/search and blocks `expand` before any use or score is recorded
  with code `BLUEPRINT_MODULE_UNAVAILABLE` and sorted `missing_module_ids`; an
  empty set means nothing is available. The gate is in
  `flyto_blueprint/availability.py`, imports no Flyto2 Core module, and is not
  exposed in any model-facing MCP tool schema. It fails closed for dynamic
  `{{arg}}` module names: such blueprints are hidden from list/search, and
  `expand` gates the module the arguments resolve to, so a host cannot be
  argued into running an unpublished module through `file_transform`.
- Host input is normalized exactly once per call, into one frozen set that
  list, search, and expand all gate against. Normalization is strict and
  rejects rather than repairs: `str`/`bytes`/`bytearray`/`memoryview`, a
  non-iterable or `TypeError`-raising iterable, and a non-string entry raise
  `TypeError`; a blank, whitespace-only, or whitespace-padded entry raises
  `ValueError`. A padded ID is never trimmed. Silently dropping a malformed
  entry, which is what the code did before 2026-08-11, would narrow the set
  below what the host claimed and hide or refuse a blueprint for a reason no
  error ever names.
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
- Verified procedure learning now requires an exact bounded v1 host receipt
  before fingerprinting, deduplication, persistence, score/trust promotion, or
  mutation. Its detached bounded JSON evidence is canonicalized and its
  SHA-256 recomputed, so nested content tampering fails with the old digest.
  The community workflow path cannot self-promote, and every
  learned/list/search surface explicitly denies execution authority. Blueprint
  validates internal receipt integrity plus a host-supplied verified claim; it
  does not prove or execute the external software or physical event.
- Every non-community outcome report now requires that receipt before dedup or
  mutation, with canonical nested `outcome_success` as an exact boolean equal
  to the report argument. A receipt without that binding remains usable for
  verified learning only. Invalid, stale-digest, unsafe, and mismatched reports
  leave memory, storage, evidence windows, retirement, and dedup state intact;
  community observations remain isolated from trusted score and evidence.
- Generated reference covers 23 package modules and 209 class, function, and
  method declarations. CI rejects declaration, catalog, and MCP schema drift.
- `.flyto/coding.yaml` declares five required checks — `compile`, `lint`,
  `release_drift`, `generated_reference`, `tests` — and every `argv[0]` is pinned to
  the checkout-relative interpreter `.venv/bin/python` because the trusted
  local runner's private HOME resolves `python` to an interpreter without
  `pytest`, `ruff`, or this package. Contributors create the checkout
  environment, but no developer or clone path is committed;
  `.github/workflows/ci.yml` does not read it and remains an independent gate.
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

## Verification status (2026-08-24)

- This trusted-outcome change requires all five commands in
  `.flyto/coding.yaml`, package build/import smoke, `git diff --check`, and
  strict Indexer task/full-scan post-validation. The governed host owns and
  records the authoritative results after this uncommitted implementation
  round; this file does not pre-claim those results.

## Release Notes

- The product-contract change did not alter runtime behavior, public APIs,
  schemas, packaged blueprints, or Apache-2.0 licensing. The 2026-08-23 change
  does move two dependency floors (`core` extra to `flyto-core>=2.31.0`, the
  `firestore` extra to bounded ranges) and the version to 0.3.0. Nothing is
  published or deployed by committing it: the PyPI workflow triggers on a `v*`
  tag, which is a separate, deliberate step.
- Publishing to PyPI and provider-side workflow success still require remote
  evidence; local verification cannot prove registry permissions.
- No official robotics/vision Blueprint may be shipped before repeated trusted
  real-workload outcomes and a completed physical loop; see `DECISIONS.md`
  (2026-08-10) for the promotion checklist. Gazebo and gateway-report evidence
  from lower repositories is not Blueprint outcome evidence.
- New model, task, or host claims must collect at least 20 paired trials per
  task and pass the same v3 directory closure; the current result must not be
  generalized beyond its committed suite and observable provider counters.
