# Architecture

This repo belongs to the Flyto2 product system.

Boundary:

- Product lines: cloud_apps_automation, data, zero_person_agent
- Core relationship: planning/blueprint tooling
- This repo must not bypass shared `flyto-core` runtime boundaries.
- SaaS, enterprise, community, and internal-only behavior must remain explicit.

Update this file when package exports, deployment mode, provider boundaries, or
cross-repo dependencies change.
