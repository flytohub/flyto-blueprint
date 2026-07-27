# Decisions

## 2026-07-26 - Token reduction must be measurable

Decision: claim zero **planner** calls only when a trusted runtime records
`planner_model_calls_used=0`. Keep the old `model_calls_used` and
`zero_llm_reuse_*` names as deprecated compatibility aliases, not as
workflow-wide token claims. Show outcome count, success rate, Wilson 95% lower
bound, retry/assertion rates, and latency percentiles in an Evidence Card. Do
not convert those facts into invented token or dollar savings.

Reason: “the agent learned” is too vague to test. A user should be able to see
how often a Blueprint ran, how often it passed, how conservative confidence
looks, and how many runs actually skipped agent re-planning. A model-backed
workflow step is a separate cost and must be measured separately.

## 2026-07-26 - Continuous learning uses evidence tiers and explicit sharing

Decision: Blueprint improvement changes reusable workflow definitions,
compatibility metadata, and evidence-backed ranking—not model weights. Sharing
is an explicit portable bundle operation. Unsigned or unknown-publisher content
enters the community tier, community outcomes cannot modify trusted scores, and
only host-configured keys can preserve CI or official trust.

Reason: teams should benefit from each other's verified procedures without
automatic uploads, secret leakage, or self-reported evidence poisoning the
trusted library.

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
