# Architecture

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

- Product lines: cloud_apps_automation, data, zero_person_agent
- Core relationship: planning/blueprint tooling
- This repo must not bypass shared `flyto-core` runtime boundaries.
- SaaS, enterprise, community, and internal-only behavior must remain explicit.
- `flyto_blueprint.tools` exposes schemas only; an embedding application owns
  MCP transport, authentication, authorization, and tool execution.
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
