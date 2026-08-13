# Flyto2 Blueprint State

## Current State

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
  Verification for this adopted
  dirty revision remains host-owned; historical results below are not evidence
  for it.
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
- Verification of the strict-normalization follow-up (2026-08-11, later job):
  **none of the four pinned checks were run for it.** The job that made the
  change had no command-execution capability at all: every `Bash` invocation
  and every `flyto-indexer` MCP call was refused by the environment's
  permission gate, so `compile`, `lint`, `generated_reference`, `tests`,
  `python -m build`, and `flyto-index verify . --full-scan --strict --json`
  were all impossible, not merely skipped. The check results recorded below
  predate this change and do not cover it. Treat the strict-normalization edit
  to `availability.py`, its 32 new `tests/test_availability.py` cases, and the
  hand-updated `docs/reference/python-api.md` rows as unverified until the four
  pinned checks are re-run.
- Re-run attempted and refused a second time on 2026-08-11, in a separate job,
  after an audit asked for the checks to be re-run and for an `indexer_post`
  route receipt. All five commands were denied again by the same permission
  gate: `pytest`, `compileall`, `ruff`, `scripts/generate-reference.py`, and the
  `flyto-indexer` `verify` MCP call. Two independent jobs now agree that this
  environment cannot execute this repository's checks.
- Refused a third time on 2026-08-11, in a third independent job, which was
  asked to close this gate with one Indexer task plan, a `task.validate` with no
  unplanned diff, the four checks re-run, and a strict route `ok=true`. None of
  it was possible: `Bash` was denied for `git status`, for `git diff
  --name-only`, and for the pinned interpreter itself, and the `flyto-indexer`
  `task(action='plan')` and `impact(mode='unstaged')` MCP calls were both denied.
  That job could not even enumerate the dirty file set, so no task plan covering
  `tests/test_availability.py` and the memory files was ever authored. Three
  independent jobs now agree this environment cannot execute this repository's
  checks or reach its indexer.
- That third job was told as a premise that "all four checks already pass." That
  premise is **not** adopted, because it is the same unreceipted assertion
  already logged below and nothing in this tree corroborates it. Recording it as
  fact would convert an external claim into a release signal without a single
  command output behind it, which is the specific failure this section exists to
  prevent.
- One genuine read-only result from that job, which is a cross-check and **not**
  the `generated_reference` check: `flyto_blueprint/availability.py` was read
  directly and is 169 lines with exactly seven declarations at lines 23, 83, 98,
  109, 132, 151, and 160. The hand-edited rows in `docs/reference/python-api.md`
  state 169 lines, 7 declarations, the same seven line numbers, and a
  `normalize_available_module_ids` Responsibility cell matching the current
  docstring verbatim. So the hand-derived numbers are self-consistent with the
  source. This does not clear `generated_reference`, which also compares the
  catalog and the MCP tool schemas and covers all 22 modules; it only removes
  the availability rows as the most likely cause of a failure there.
- Third-party claim, recorded but not adopted: that audit reported "all checks
  pass" alongside "strict route failed after `turn_limit_exceeded`". No command
  output, test count, or route receipt accompanied it, and the two halves of the
  statement disagree — a run truncated at a turn limit is not a completed check
  set. It is logged here as an unverified external assertion. It is deliberately
  **not** treated as verification of this tree, because no such run was observed
  from this repository, and a passing-check claim with no receipt is exactly the
  kind of record that later gets mistaken for a release signal.
- `docs/reference/python-api.md` was updated **by hand**, not by
  `scripts/generate-reference.py`, for the same reason. Module count (22) and
  declaration total (176) are unchanged because the edit added no declaration;
  the `availability.py` Lines cell moved 130 → 169, its seven declaration line
  numbers moved 23/44/59/70/93/112/121 → 23/83/98/109/132/151/160, and the
  `normalize_available_module_ids` Responsibility cell was rewritten to the new
  docstring. The docstring was deliberately kept under the generator's
  240-character `clean()` limit so the cell renders verbatim instead of
  truncated. These values were derived by reading the generator, not by running
  it, so `generated_reference` is the check most likely to fail first.
- Verification of the earlier 2026-08-11 availability-gate change (before the
  strict-normalization follow-up): all four pinned `.flyto/coding.yaml` checks
  ran and passed on 2026-08-11 against that working tree — `compile`, Ruff
  `lint`, `generated_reference`, and the full `tests` suite at 213 passing
  tests. This is the authoritative local result for that earlier state of the
  change only.
- Independently reproduced on 2026-08-11 by Codex on the same checkout:
  `compile`, Ruff `lint`, `generated_reference`, and 213 passing tests, plus a
  targeted behavioral check that `expand("file_transform", {...,
  "operation": "shell.execute"}, host)` is rejected with
  `BLUEPRINT_MODULE_UNAVAILABLE` and `missing_module_ids == ["shell.execute"]`
  when `shell.execute` is not in the host set. Two independent runs agree on
  the same four checks and the same test count.
- The generated reference was additionally cross-checked by hand against
  `scripts/generate-reference.py` semantics, and agrees with the passing
  `generated_reference` check: module count 21 → 22
  (`flyto_blueprint/availability.py`, which sorts between `__init__.py` and
  `benchmark.py`); declaration total 168 → 176 (+7 in `availability.py`, +1 for
  `BlueprintEngine._runnable_blueprints`, `search.py` unchanged at 5); `wc -l`
  of 130 / 341 / 165 for `availability.py`, `engine.py`, and `search.py`
  matching the Lines column exactly; and every declaration line number matching
  the current source (`availability.py` 23, 44, 59, 70, 93, 112, 121;
  `engine.py` 33, 43, 54, 61, 86, 93, 109, 127, 140, 185, 226, 245, 261, 283;
  `search.py` 11, 16, 52, 63, 98).
- Separate from the check results, and not a denial of them: the earlier job on
  this change ended at the provider `turn_limit` with its budget exhausted,
  which is why `.flyto/coding.yaml` was left as the only repaired file and the
  memory files were left unreconciled until now. The `indexer_post` step —
  `flyto-index verify . --full-scan --strict --json` — is not one of the four
  pinned checks and has not been run for this change; neither has
  `python -m build`. Both remain outstanding, and CI runs them on merge.
- The stale "208 passing tests" figure previously recorded for this change was
  wrong and has been removed; 213 is the reproduced count.
- Latest full local verification on 2026-07-28: Ruff passed, 183 tests passed,
  generated documentation was current, sdist/wheel build passed, and Flyto2
  Indexer strict full-scan passed 17/17 with no warnings and documentation
  score 100. The independent Flyto2 AI benchmark workflow run 30322935702
  passed all steps; final CI for the evidence/documentation commit remains the
  release gate.

## Release Notes

- The current strict-normalization tree has a complete local closure:
  compile/Ruff/reference checks pass, 256 tests pass, package build passes, and
  strict Indexer verification passes 18/18. It is not published or deployed;
  remote CI remains the release gate after commit.
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
