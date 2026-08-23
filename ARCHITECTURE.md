# Architecture

Flyto2 is one product with three independently usable packages. Blueprint is
layer 2, `procedure_memory`: it accepts host-supplied validated outcomes and
deterministically stores, expands, learns from, and scores procedures. Flyto AI
owns intent and provider governance; Flyto Core owns validation, execution,
replay, and evidence. Blueprint never executes a procedure.

This repository is a Python library with four runtime layers and one
independent evidence layer:

```text
package API (BlueprintEngine)
  -> deterministic search / expansion / learning / scoring
  -> storage contract (memory, SQLite, Firestore)
  -> packaged YAML blueprints and composition blocks

trusted host benchmark runner
  -> real coding / HTTP / filesystem / model-backed work
  -> paired planner + workflow usage records
  -> identity and evidence validation
  -> deterministic scorecards
  -> model / hardware / independent-runner / history CI gates

real longitudinal runner
  -> SQLite learn / reuse / outcome transitions
  -> immediate retirement and reload check
  -> digest-bound lifecycle evidence
```

Boundary:

- Blueprint owns exactly reusable procedure learning and scoring, procedure
  expansion and compatibility, and procedure outcome history. It does not own
  intent and provider governance, workflow execution, or hosted product and
  account logic.
- Language and LLM systems may understand or route. Validated execution
  outcomes enter through a host; Blueprint persists and ranks their procedures
  without guessing domain facts. Mathematics, physics, chemistry, robotics,
  and other domain solvers belong in bounded capabilities and hosts, not this
  general procedure-memory package.
- Product lines: cloud_apps_automation, data, zero_person_agent
- Phase-one capability search is a provider-neutral contract layer in
  `flyto_blueprint.intent`. It validates one exact safe catalogue projection,
  derives deterministic lexical/vector-input documents, and defines bounded
  upsert, tombstone, hard-filter query, candidate-page, and keyset-cursor
  envelopes. It computes no vectors and owns no index, cache, storage,
  authorization, routing, execution, network, provider, or database behavior.
  Host filters must precede lexical/ANN retrieval and remain retrieval filters,
  never trust or execution authority. Empty query resource/capability lists
  mean no additional restriction, enabling discovery without knowing result
  IDs; non-empty lists are hard constraints. Risk uses the ordered `minimal`
  through `critical` ceiling. Documents bind exactly one capability and may
  carry an empty resource set to mean that no named resource is required.
  Projection identifiers use the producer's 192-character safe-ASCII bound and
  display fields use its 2,000-character NFC-preserving dialect and each
  semantic field carries at most 32 producer-ordered identifiers; unrelated
  host identifiers keep their narrower limits. Set-like ACL/resource/capability filters are sorted at
  boundaries, while producer-canonical semantic ordering is preserved.
  Undefined `source_kind` remains valid audit data but cannot be complete or
  indexable. Producer tenant/space/capability identity retains its 192-character
  width through document filters, requests, candidates, and cursors. Accepted
  projections require visible, host-verified audit state and exact deterministic
  trust/routability coherence; semantic lists must already be producer-sorted.
  Projection, derived-document, request, and 100-candidate page boundaries use
  separate finite byte/node envelopes with one shared finite depth ceiling.
  Signed cursors bind the last key and cumulative emitted count, so pagination
  cannot exceed `top_k` across pages.
- Core relationship: planning/blueprint tooling
- This repo must not bypass shared `flyto-core` runtime boundaries.
- SaaS, enterprise, community, and internal-only behavior must remain explicit.
- `flyto_blueprint.tools` exposes schemas only; an embedding application owns
  MCP transport, authentication, authorization, and tool execution.
- Host module availability (`flyto_blueprint.availability`) is a trust boundary,
  not a feature flag. The set of executable module IDs is authoritative host
  state passed in by the embedding application; the library never imports
  Flyto2 Core to discover modules and never accepts the set from a model, so it
  is absent from every schema in `flyto_blueprint.tools`. Omitting the set
  (`None`) is "no claim" and preserves the previous permissive behavior; an
  empty set is the real claim that nothing is executable. The gate fails closed:
  a required module that cannot be proven available — including a step whose
  module is still an unresolved `{{arg}}` template — hides the blueprint from
  list/search, and `expand` rejects it before any use count, score, or expanded
  workflow exists.
- Learned workflows stay in the configured backend and are never uploaded by
  the library itself.
- Sharing is explicit export/import of integrity-checked bundles. Unsigned or
  unknown-publisher imports are quarantined as community content; only
  host-configured publisher keys can preserve CI or official trust.
- Community observations are stored separately from trusted execution scores.
  They can influence search within a bounded confidence cap but cannot
  self-promote a Blueprint to a verified tier.
- Repository/framework/runtime compatibility participates in learning
  deduplication so one codebase's conventions do not overwrite another's.
- `flyto_blueprint.benchmark` does not execute an agent, MCP tool, or workflow.
  A host owns execution and supplies paired facts for the same task, trial,
  model, environment, dataset, and seed.
- Benchmark scorecards accept only `ci_verified` evidence and compare warm
  reuse with both the agent baseline and Flyto2 without Blueprint. V1/v2
  planner-only evidence remains supported. V3 accepts a full-usage claim only
  when planner and workflow counters are both present and their totals match.
- The v3 result directory must keep at least three model families, two hardware
  families, one independent runner, and one passing historical comparison.
  This is an explicit trust boundary: record consistency is validated, but
  provider execution is not cryptographically attested.
- Longitudinal evidence uses the production Engine and SQLite backend to prove
  that trusted outcomes change scores, repeated failure retires a Blueprint
  immediately, and a fresh Engine does not reload it.
- An empty benchmark result directory means no performance claim exists. A
  claim begins only when versioned raw records and their exactly reproducible,
  threshold-passing scorecard are committed.

Update this file when package exports, deployment mode, provider boundaries, or
cross-repo dependencies change.
