# Changelog

## 0.3.0

Released because the host-side gate depended on it. `flyto-ai` decides whether
to pass `available_module_ids` by inspecting the engine signature, and falls
back to unfiltered behaviour when the parameter is absent. Every published
`flyto-ai` therefore ran with module gating silently off, because 0.2.2 was the
newest Blueprint on PyPI and 0.2.2 has no such parameter: the gate existed only
in a source checkout. Cutting this release is what makes it reachable. The
matching `flyto-blueprint>=0.3.0` floor lands in `flyto-ai` alongside it.

### Changed

- Raised the `core` extra's floor to `flyto-core>=2.28.1`, the first Core
  release that clears every published advisory. The previous `>=2.12.0` was
  satisfied by releases predating all 33 of them.
- Gave the `firestore` extra real version bounds
  (`google-cloud-firestore>=2.19.0,<3`, `firebase-admin>=6.5.0,<8`); they were
  the only unbounded requirements in the project.
- Renamed the retired bare product name in `ARCHITECTURE.md`, `STATE.md` and
  this file: `Flyto AI` / `Flyto Core` / `Flyto host` become `Flyto2 AI` /
  `Flyto2 Core` / `Flyto2 host`, which is what the organisation documentation
  contract requires and what every other repository already used.

### Added

- Added the deterministic `flyto.product-contract.v1` manifest and a
  Python-3.9-compatible dependency-free contract test.
- Documented Blueprint as Flyto2's independently usable procedure-memory
  package: it learns, expands, scores, and persists reusable procedures from
  host-validated outcomes, but never executes them or supplies domain solvers.
- Added the phase-one provider-neutral Capability Search contract: strict safe
  projection validation; deterministic digest-bound documents and mutations;
  content-free retirement tombstones; explicit prefilter-first query plans;
  bounded candidate pages; and tamper-evident, query-bound keyset cursors. It
  computes no embeddings, stores nothing, grants no authorization, and is not
  connected to any Flyto2 host or retrieval backend.
- Hardened that contract for the upstream v1 projection, recursively bounded
  JSON snapshots, hostile-container redaction, request rebuilds, unknown-ID
  discovery, ordered risk ceilings, candidate digest binding, authenticated
  continuation keys, and content-free retirement from ineligible source or a
  minimal prior identity.
- Aligned safe projection identifiers and display fields with the accepted v1
  producer maxima; required keyed, forward-only continuation requests; bound
  candidates to the request index digest; allowed software capabilities with
  no named resource; and canonicalized duplicate-free set-like filter metadata
  without changing producer semantic ordering.
- Repaired boundary budgets so maximum accepted producer projections can build
  and validate derived documents and a minimal 100-result page remains valid;
  all envelopes retain finite depth, node, and byte limits. Cursor signatures
  now bind cumulative emitted count and refuse `top_k` exhaustion. Projection
  semantics now enforce 32 IDs per field and preserve the producer's NFC
  display whitespace/private-use dialect while keeping whitespace-only cards
  non-routable.
- Accepted producer projections now preserve null source kind as incomplete
  audit data, reject hidden audit state, contradictory trust/routability flags,
  incomplete complete-cards, and unsorted semantic IDs. Tenant, space, and
  capability identifiers retain their 192-character producer width through
  document, request, candidate, and cursor validation.
- `list_blueprints`, `search`, and `expand` accept an optional authoritative
  `available_module_ids` set from the embedding host. `None` keeps the previous
  behavior; a supplied set hides blueprints the host cannot run and fails
  `expand` before any use or score is recorded with code
  `BLUEPRINT_MODULE_UNAVAILABLE` and sorted `missing_module_ids`; an empty set
  means nothing is available. The gate fails closed for dynamic `{{arg}}`
  module names, imports no Flyto2 Core module, and is not exposed to models
  through any MCP tool schema.
- Host availability input is validated strictly and normalized exactly once per
  call into a single frozen set shared by list, search, and expand. A
  `str`/`bytes`/`bytearray`/`memoryview`, a non-iterable, an iterable that
  raises `TypeError`, and a non-string entry all raise `TypeError`; a blank,
  whitespace-only, or whitespace-padded entry raises `ValueError`. A padded ID
  is never trimmed on the host's behalf. Any iterable of well-formed IDs is
  accepted, including a generator, which is consumed exactly once.

### Fixed

- Malformed entries in `available_module_ids` are no longer silently dropped.
  The previous filter discarded non-string and empty entries, which narrowed
  the gate below what the host actually claimed and could hide or refuse a
  blueprint with no error explaining why. Operator-visible: a host that was
  passing a malformed collection now gets an exception instead of a quietly
  reduced set.

- The four required checks in `.flyto/coding.yaml` now launch again on the
  trusted local runner. Each Python `argv[0]` is pinned to the checkout-local
  interpreter `.venv/bin/python`, because the
  runner's private HOME resolved a bare `python` to an interpreter without
  `pytest`, `ruff`, or this package, so every check failed at process entry and
  produced no verification signal. Operator-visible only: the checks, their
  arguments, their order, and their `required: true` status are unchanged, the
  path contains no developer or clone identity, and `.github/workflows/ci.yml`
  does not read this file.

### Changed

- Blueprint list/search summaries now expose ordered, unique `module_ids`
  without step parameters or results for trust-gated capability routing.
- Clarified the public `ci_verified` evidence-tier constant name and emit
  benchmark JSON through an explicit CLI output stream, preserving the exact
  payload without classifying public verification metadata as a secret.
- Stopped weekly dependency-version branches from piling up while keeping
  Dependabot security updates enabled. Verified and merged the current
  checkout, Python setup, and PyPI publishing actions.
- Narrowed Grype's GitHub Action false-positive handling to one advisory, one
  package type, and the exact patched PyPI publishing commit.
- Blueprint summaries now carry a data-driven Evidence Card with trusted sample
  counts, observed success, Wilson 95% lower bound, retry/assertion rates,
  latency percentiles, and measured zero-planner-call reuse. Older ambiguous
  zero-LLM field names remain compatibility aliases.
- Trusted runtime outcome reports accept a bounded evidence allowlist. Raw
  execution IDs are hashed, detailed samples are capped at 100, and community
  reports cannot add trusted evidence.
- Rewrote the product explanation around the concrete difference from
  model-first agents and removed unverifiable token-saving language.
- Split outcome learning into trusted evidence scores and bounded community
  observations, and scoped deduplication with repository/runtime compatibility.
- Learned and expanded workflows now preserve retry and assertion contracts.
- Prepared a metadata-only PyPI patch release so live registry backlinks and
  the Flyto2 package description can replace the stale pre-Flyto2 listing.

### Added

- Added a versioned four-mode effectiveness suite, strict paired-run validator,
  deterministic scorecard CLI, statistical reliability/token/latency gates,
  adversarial multilingual cases, a sealed holdout commitment, and CI
  verification for committed evidence. No benchmark result is committed yet,
  so this adds a proof mechanism rather than a performance claim.
- Added explicit integrity-checked Blueprint export/import, optional
  host-controlled HMAC publisher signatures, semantic deduplication, sensitive
  metadata rejection, and quarantine for unsigned or unknown publishers.
- Added model-facing export/import schemas without signing or trust-key inputs.
- Added feature and stable Python API guides plus a source-backed reference for
  all package declarations, packaged blueprints, composition blocks, and MCP
  input schemas.
- Added a machine-readable documentation contract and CI drift gate.
- Added project memory files, workflow docs, and handoff registry.
