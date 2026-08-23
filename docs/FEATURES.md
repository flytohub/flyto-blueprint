# What Blueprint Actually Adds

Most agents are good at solving a new problem. They are less good at admitting
that a solved problem should stop being an AI problem.

Blueprint keeps the useful part of a successful run—the parameterized workflow
and its execution evidence—so the next run can be cheaper, faster, and easier
to inspect.

| Question | Model-first agent | Flyto2 AI + Blueprint |
|---|---|---|
| Who plans a repeated job? | The model, again | The saved workflow |
| What counts as proof? | A plausible response | Trusted outcome, step execution, assertions |
| Can reuse skip the model? | Usually no | Yes, on deterministic exact reuse |
| Does shared data become trusted? | Often unclear | No; unknown imports stay `community` |
| Can you see reliability? | Read logs manually | Read the Evidence Card |

## Evidence Card

`list_blueprints()` and `search()` return an `evidence_card` for every
Blueprint. It contains:

- `sample_count`, `success_count`, `failure_count`, and `success_rate`;
- `wilson_95_lower_bound`, a conservative reliability floor that does not let
  one lucky run look production-ready;
- `retry_rate` and `assertion_pass_rate`;
- `duration_ms_p50` and `duration_ms_p95`;
- `planner_model_call_sample_count`, `zero_planner_model_call_count`, and
  `zero_planner_model_call_rate`;
- deprecated `model_call_sample_count`, `zero_llm_reuse_count`, and
  `zero_llm_reuse_rate` aliases for older clients.

The success rate and Wilson bound use all trusted outcome counters. Detailed
latency/retry/assertion/model-call statistics use a rolling window of at most
100 allowlisted samples.

What is not stored: prompts, workflow parameters, API keys, raw tool output, or
arbitrary evidence fields. Execution identifiers are stored only as SHA-256
references.

What is not claimed: an estimated token or dollar saving. A zero planner-call
reuse is counted only when the trusted host reports
`planner_model_calls_used=0`. This proves the agent skipped re-planning; an
`llm.*` workflow step can still consume tokens. If step-level provider counters
are not present, workflow-wide token use stays unknown.

## Packaged Blueprint Catalog

The package ships browser, API, data conversion, file, image, OCR, PDF,
monitoring, and notification patterns plus reusable composition blocks. The
loader reads these package resources; user workflows do not need repository
paths at runtime.

## Search And Intent Matching

Deterministic search scores identifiers, names, descriptions, and tags. The
optional intent matcher adds query expansion, keyword candidates, embeddings,
and query tracking without changing the deterministic engine API.

The separate phase-one Capability Search contract accepts one exact safe host
projection and derives deterministic lexical and embedding-input documents. It
also defines backend-neutral, million-scale request/page contracts: tenant,
space, active-status, ACL, risk, resource, and capability filters must run
before lexical/ANN retrieval; pagination uses a tamper-evident keyset cursor,
not an offset. Vector scores produce candidates only. This library neither
computes vectors nor owns an index, backend, authorization decision, or
execution route, and documents never include workflow parameters, payloads,
prompts, endpoints, headers, tokens, credentials, or source references.
Empty query resource/capability lists mean no additional restriction, so ANN
discovery need not pre-enumerate result IDs; non-empty lists are hard filters.
Risk is an ordered `minimal`→`critical` ceiling. Requests are rebuilt before
page/cursor use, and continuation cursors authenticate the request plus last
score/ID. Empty/incomplete upstream projections remain audit-visible but are
never indexed and receive no synthesized content. A non-null request cursor
requires its integrity key and every returned key must be strictly forward.
Candidates bind model, index, and snapshot digests. Empty document resources
mean no named resource is required, and duplicate-free ACL/resource/capability
sets are canonicalized without reordering upstream semantic fields.
Producer semantic fields accept at most 32 identifiers. Title and summary
preserve NFC text, including surrounding whitespace, while controls, format
characters, and surrogates are rejected; whitespace-only display data cannot
be indexed. Separate finite projection, document, request, and page envelopes
support maximum valid derivation and 100 minimal candidates. Cursor state also
binds cumulative emitted count, preventing later pages from exceeding `top_k`.
An undefined source kind is accepted only for visible, coherent incomplete
audit data and is never indexed. Trust state and autonomous routability must
exactly match the producer flags, complete cards require source/display/
semantic content, and producer semantic lists must already be sorted. The
192-character tenant/space/capability identity bound is preserved across
documents, requests, candidates, and cursors.

## Expansion And Composition

Expansion resolves arguments recursively, expands named blocks, chains multiple
blueprints, deconflicts step identifiers, wires cross-blueprint references, and
reports unresolved placeholders. Resulting steps can be validated against
Flyto2 Core when the optional dependency is installed.

An embedding host may also pass the set of module IDs it can actually execute.
Listing and search then return only blueprints whose every required module —
including modules contributed by composition blocks — is available, and
expansion refuses a blueprint the host cannot run before any use count or score
changes. Passing nothing keeps the previous permissive behavior; passing an
empty set is the explicit claim that nothing is executable. The gate never
guesses: a step whose module is still an unresolved `{{arg}}` template hides
the blueprint from discovery, and expansion gates on the module the supplied
arguments actually resolve to. See
[API.md](API.md#host-module-availability).

## Workflow Learning

Verified learning first validates an exact, bounded v1 host receipt binding
`success=true`, `status=verified`, an evidence identifier, and a SHA-256
digest to a detached, solver-shaped JSON evidence object. The digest covers
the object's sorted-key, compact UTF-8 JSON encoding and is recomputed before
learning. Invalid receipts are rejected before fingerprinting,
deduplication, persistence, or scoring. `learn_from_workflow` remains the
explicit community/unverified route. Blueprint validates the host claim's
internal integrity; it does not prove the external software or physical event,
train a model, execute a solver, contact Core, hardware, a network, or an LLM,
or grant execution approval. The envelope is generic and has no Core import.

## Outcome Scoring

Trusted local, CI, and official success/failure evidence updates the primary
score only after an exact digest-validated receipt binds nested boolean
`outcome_success` to the reported result. Validation occurs before deduplication
or any trusted mutation; a learning receipt without that field cannot score an
outcome. Community outcomes require execution identifiers and update separate
Bayesian counters. Their confidence-weighted ranking adjustment is capped, so
shared observations improve discovery without being able to overwrite trusted
quality. Duplicate recent execution reports are rejected. Only trusted reports
may add detailed Evidence Card samples.

## Portable Sharing And Trust

Explicit export creates a canonical SHA-256 bundle and optionally a
host-signed publisher claim. Import validates integrity, rejects
non-parameterized sensitive metadata, resets mutable counters, and quarantines
unsigned or unknown publishers as community content. The package performs no
upload, registry access, key management, or tenant authorization itself.

## Storage Backends

Memory, SQLite, and Firestore backends implement the same persistence contract.
Applications choose storage explicitly; built-in blueprints remain package
resources and are not rewritten by learned data.

## MCP Integration

The package exposes six MCP-compatible JSON Schema tool definitions for list,
expand, save, outcome reporting, export, and import. Model-facing schemas never
accept signing or trusted-publisher keys, and never accept the host's executable
module set — availability is passed in by the host when it binds these tools to
engine methods. The embedding host owns credentials,
tenant scope, tool authorization, trust configuration, and Flyto2 Core
execution.

## Public API

The supported Python interface, return shapes, storage methods, model roles,
side effects, and error behavior are documented in [API.md](API.md).
