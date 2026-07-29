# Changelog

## Unreleased

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
