# Architecture

This repository is a Python library with four layers:

```text
package API (BlueprintEngine)
  -> deterministic search / expansion / learning / scoring
  -> storage contract (memory, SQLite, Firestore)
  -> packaged YAML blueprints and composition blocks
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

Update this file when package exports, deployment mode, provider boundaries, or
cross-repo dependencies change.
