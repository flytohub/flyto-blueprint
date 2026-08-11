# Tasks

- [x] Gate blueprint discovery and expansion on host-supplied module
  availability, failing closed on unresolved `{{arg}}` module names.
- [x] Repair `.flyto/coding.yaml` so the four required checks launch on the
  trusted local runner, and document the interpreter pin as checkout-relative.
- [x] Reject malformed `available_module_ids` input strictly instead of silently
  dropping entries, and normalize once into a single frozen set shared by list,
  search, and expand.
- [x] Re-run all four pinned `.flyto/coding.yaml` checks on the current tree:
  compile, Ruff, generated-reference drift, and 256 tests passed on 2026-08-12.
- [x] Produce the `indexer_post` receipt: strict full-scan passed 18/18 with no
  warnings or failures on 2026-08-12.
- [x] Run the generated-reference check against the current source; the
  committed reference is generator-identical.
- [x] Build both sdist and wheel and run strict Indexer verification for the
  availability-gate change.
- [x] Commit the availability-gate change (`2b9f4cb`) and let CI re-run the pinned checks
  plus the build and Indexer verification on a clean checkout.
- [x] Add the reproducible four-mode benchmark harness and CI evidence gate.
- [x] Keep product-line, execution, trust, and `flyto-core` boundaries
  documented.
- [ ] Collect the first trusted dataset with at least 20 paired trials per task.
- [ ] Commit a generated scorecard only after every versioned evidence gate
  passes.
- [ ] Strengthen host attestation with provider-signed usage or an independent
  runner.
