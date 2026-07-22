# Decisions

## 2026-07-22 - Stable API and exhaustive implementation docs stay separate

Decision: `docs/API.md` defines the compatibility promise, while generated
references inventory every implementation declaration, packaged pattern, and
MCP schema without promoting internals to public API.

Reason: integrators need a small stable surface and maintainers still need
complete source-level documentation that cannot silently drift.

## 2026-06-21 - Project memory bootstrapped

Decision: track Flyto2 product-line role, repo boundary, state, roadmap, tasks,
and handoffs in this repo.

Reason: `flyto-blueprint` must be maintainable by future agents without relying on
conversation memory.
