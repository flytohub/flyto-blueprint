# Flyto2 Blueprint State

## Current State

- `flyto-blueprint` is Flyto2's independently usable layer-2
  `procedure_memory` package. It owns reusable procedure learning and scoring,
  procedure expansion and compatibility, and procedure outcome history. It
  never executes workflows; intent/provider governance belongs to Flyto AI,
  while deterministic validation, execution, replay, and evidence belong to
  Flyto Core.
- Blueprint is evidence-first: hosts supply validated execution outcomes that
  it persists and ranks. It does not guess mathematics, physics, chemistry,
  robotics, or other domain facts; bounded capabilities and hosts own those
  solvers and their acceptance evidence.
- Phase one of the Blueprint Capability Search Document/Index contract is
  implemented as stateless, provider-neutral JSON-native validation and
  derivation helpers. It is not wired to Flyto AI, Cloud, Core, a UI, storage,
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
- Generated reference covers 22 package modules and 176 class, function, and
  method declarations. CI rejects declaration, catalog, and MCP schema drift.
- `.flyto/coding.yaml` still declares the same four required checks — `compile`,
  `lint`, `generated_reference`, `tests` — but every `argv[0]` is now pinned to
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

## Verification (2026-08-23)

- All four commands in `.flyto/coding.yaml` passed exactly as declared:
  compile, Ruff, generated-reference drift, and the full suite (322 tests).
  Generated references are unchanged because no runtime source, packaged
  blueprint, catalogue, or tool schema changed.
- `git diff --check` passed. Indexer task validation passed with its subprocess
  resolved through the repository-pinned `.venv/bin` toolchain: Ruff passed
  and the two product-contract tests passed. Strict full-scan verification
  passed 18/18 with 0 warnings, 0 failures, and 0 scan errors; it scanned 43
  files, found 536 symbols and 3,032 dependencies, and reported documentation
  score 100.
- `python -m build` was run but could not complete in the network-restricted
  worker: its isolated environment attempted to obtain the declared Hatchling
  backend from PyPI, and Hatchling is not installed locally. A no-isolation
  retry confirmed the backend is unavailable. This is an environment limit,
  not a package-source failure; no dependency or package metadata was changed.

## Release Notes

- This product-contract change does not alter runtime behavior, public APIs,
  schemas, packaged blueprints, dependencies, version 0.2.2, or Apache-2.0
  licensing. It is not published or deployed; remote CI remains a separate
  release gate after commit.
- Publishing to PyPI and provider-side workflow success still require remote
  evidence; local verification cannot prove registry permissions.
- No official robotics/vision Blueprint may be shipped before repeated trusted
  real-workload outcomes and a completed physical loop; see `DECISIONS.md`
  (2026-08-10) for the promotion checklist. Gazebo and gateway-report evidence
  from lower repositories is not Blueprint outcome evidence.
- New model, task, or host claims must collect at least 20 paired trials per
  task and pass the same v3 directory closure; the current result must not be
  generalized beyond its committed suite and observable provider counters.
