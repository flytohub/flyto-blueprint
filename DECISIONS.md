# Decisions

## 2026-08-24 - Learning repetition is not outcome evidence

Decision: structural duplicate learning is an identity result only. Return
`deduplicated_existing` for both community and receipt-valid calls and leave
the existing Blueprint, persisted row, score, trust tier, evidence, counters,
and recent-report state unchanged. Reject the arbitrary public `boost_score`
mutation path; trusted score changes require receipt-bound `report_outcome`.

Enforce the receipt boundary again inside the directly importable low-level
learner before reading workflow steps or fingerprinting. A generic valid host
receipt may establish only `local_verified`; caller-selected `ci_verified` and
`official` claims are rejected because those tiers require their separately
governed provenance paths.

Reason: repetition proves only that the same structure was submitted again.
Treating it as a quality outcome or allowing direct callers to select trust
bypasses the evidence contract even when the engine wrapper is correct.

## 2026-08-24 - Durable means durable across processes, not across threads

Decision: `SQLiteBackend` is correct under concurrent processes. WAL, a
`busy_timeout`, and `BEGIN IMMEDIATE` around every read-modify-write; the
`threading.Lock` remains only as an intra-process fast path and is no longer
what correctness rests on.

Why: the class claimed thread safety and atomicity, and the claims were
published in the API docs, but a `threading.Lock` is per-instance and the read
and write were separate autocommit statements. Two processes - the ordinary
configuration, since every host opens the same default database path - could
read one row and both write it. Four processes performing 300 increments each
left 415 of 1,200, with nothing raised. A package whose thesis is evidence-first
procedure memory was deleting evidence in its default deployment.

Consequence: `update_fn` runs while the write lock is held, so it must stay
pure bookkeeping and must not block. Concurrency tests use real processes;
a threading-only test passes against the broken implementation, and did.

## 2026-08-23 - Verified procedure learning requires an exact host receipt

Decision: `learn_from_execution` and every non-community `report_outcome`
accept only the bounded, exact
`flyto.execution-verification-receipt.v1` JSON shape binding `success=true`,
`status=verified`, a safe evidence identifier, and a lowercase SHA-256 evidence
digest to a detached bounded JSON evidence object. Canonicalize that object as
sorted-key compact UTF-8 JSON with finite exact JSON types and bounded bytes,
depth, nodes, strings, and integers; recompute SHA-256 and require an exact
lowercase match. Validate it before workflow fingerprinting, deduplication, persistence,
score/trust promotion, or mutation. Keep `learn_from_workflow` explicitly
community/unverified and mark learned/list/search results as having no execution
authority.

For trusted outcome scoring, the canonical nested evidence must contain an
exact boolean `outcome_success` equal to the public `success` argument. The
top-level `success=true` and `status=verified` bind the host verification claim,
not the observed workflow result. A solver receipt without `outcome_success`
therefore remains sufficient for verified learning but cannot change trusted
outcome state. Receipt validation precedes recent-report deduplication and all
score, count, trust, evidence-window, retirement, persistence, or other state
mutation. Community reports keep isolated counters and never enter this trust
path.

Blueprint validates internal receipt integrity plus a host-supplied verified
claim and stores procedure memory; it does not prove an external event, call Core,
execute a domain solver, use hardware/network/LLM access, or approve execution.
The generic envelope imports no Core code, so a Core domain solver may return
the same envelope directly.

Reason: arbitrary caller metadata previously became verified memory. An exact
versioned, content-bound receipt makes the host boundary deterministic and fail-closed without
coupling this independently usable package to any executor.

## 2026-08-23 - One product has three independently usable package boundaries

Decision: Flyto2 has one promise and three independently usable packages.
`flyto-ai` owns intent, provider governance, and routing; `flyto-blueprint`
owns reusable procedure learning and scoring, procedure expansion and
compatibility, and procedure outcome history; `flyto-core` owns deterministic
schema validation, execution, replay, and evidence. Blueprint never executes:
it persists and ranks procedures only from validated execution outcomes
supplied by a host.

General packages encode deterministic, verifiable contracts instead of
pretending mathematics, physics, chemistry, robotics, or any other domain is a
universal dependency. Domain solvers and their safety or acceptance evidence
belong in bounded capabilities and hosts.

Reason: a shared product contract makes the package handoffs explicit without
coupling independent installation or use. Keeping execution outside Blueprint
prevents procedure memory from turning stored patterns or model language into
claims that work ran or scientific facts are true.

## 2026-08-13 - Capability indexing starts with a safe, rebuildable contract

Decision: accept only the exact versioned capability-card projection and emit
deterministic JSON-native documents, mutations, tombstones, hard-filter query
requests, candidate pages, and HMAC-bound keyset cursors. Bind source,
upstream-content, document, model, filter, index, and snapshot digests. Derive
lexical fields and vector-input text only from accepted display and semantic
fields. Require tenant/space/status/ACL/risk/resource filters before lexical or
ANN retrieval. Candidates explicitly carry no execution authority.

Do not connect a backend, compute/store vectors, infer missing display or
semantics, accept workflow arguments or secrets, or treat filters, scores, or
cursor integrity as approval. Retired or otherwise ineligible cards cannot
produce upserts; tombstones contain identity and digests but no search content.

Query resource/capability lists differ from document identity: empty means no
additional restriction, allowing discovery of unknown IDs; non-empty is a hard
filter. An empty document resource list explicitly means no named resource is
required. ACL remains non-empty and risk is an ordered `minimal` through
`critical` ceiling. Set-like ACL/resource/capability metadata is duplicate-free
and sorted at document, request, and candidate boundaries; semantic projection
order remains producer-owned. Requests are rebuilt before cursor/page
validation, a non-null request cursor requires an integrity key, and every
paged candidate must sort strictly after its authenticated last score/ID key.
The cursor also binds the cumulative emitted count; a page must fit the
remaining `top_k` budget and cannot issue or consume a continuation at
exhaustion. Separate finite projection/document/request/page budgets admit the
complete producer envelope and a minimal 100-candidate page without making
depth, nodes, or bytes unbounded. Producer display text preserves NFC
whitespace and private/unassigned code points, rejects control/format/surrogate
characters, and whitespace-only display data remains audit-only.
An undefined source kind is likewise audit-visible incomplete data, never a
candidate. Accepted cards must be host-verified and audit-visible, carry the
producer-derived trust state, and make autonomous routability exactly match
their complete/approved/verified/active/not-retired flags. Complete cards need
a source kind, stripped nonblank display fields, and semantic identity.
Producer semantic lists must arrive sorted; the consumer does not normalize a
second projection digest. Producer tenant, space, and capability identifiers
retain their 192-character width across every retrieval handoff.
Every candidate binds the request's model, index, and snapshot digests.
Tombstones rebuild from an ineligible projection plus prior document digest or
an exact minimal prior identity envelope, without retaining search content.

Reason: the first reusable boundary must be independently rebuildable and safe
to pass to different million-scale retrieval backends without making Blueprint
an authorization system or leaking execution material. Exact schemas and
content-free failures make drift, hostile mappings, and tampering fail closed.

## 2026-08-11 - Malformed availability input is rejected, never repaired

Decision: `normalize_available_module_ids` validates host input strictly and
normalizes it exactly once per call into a single frozen set that
`list_blueprints`, `search`, and `expand` all gate against. A
`str`/`bytes`/`bytearray`/`memoryview`, a non-iterable, an iterable whose
iteration raises `TypeError`, and any non-string entry raise `TypeError`. A
blank, whitespace-only, or whitespace-padded entry raises `ValueError`, and a
padded ID is never trimmed on the host's behalf. `None` and the empty iterable
keep their existing, distinct meanings.

Reason: the first implementation filtered malformed entries out with
`if isinstance(module_id, str) and module_id`. For a safety gate that is the
wrong failure direction. Dropping an entry produces a set that claims *less*
than the host claimed, so a blueprint is hidden from `list` or refused by
`expand` for a reason no error names, and the host cannot distinguish its own
typo from a genuinely unpublished module. Repairing input also makes the gate's
meaning depend on how badly the caller malformed it. Raising keeps the frozen
set a faithful statement of host capability, and keeping `TypeError` and
`ValueError` distinct lets a host separate a shape error from a content error.
Trimming was rejected specifically: a padded ID cannot match a real module name,
so trimming would invent a claim the host never made, while rejecting says so.
`bytes` is called out because iterating it yields `int`, which would compare
integers against module names and match nothing — failing closed, but silently.

## 2026-08-11 - Host module availability is trusted host state and fails closed

Decision: `list_blueprints`, `search`, and `expand` accept an optional
`available_module_ids` collection supplied by the embedding host. `None` means
the host made no claim and behavior is unchanged, including for abstract or
host-unknown module names. A supplied collection filters list/search to
blueprints whose every required module is available, and makes `expand` return
`{"ok": False, "code": "BLUEPRINT_MODULE_UNAVAILABLE", "missing_module_ids":
[...]}` before any use count, score, or expanded workflow is produced. An empty
collection is a real claim that nothing is available. Required modules include
composition block steps and exclude steps that `skip_if_missing` would drop.
The parameter is deliberately absent from every model-facing MCP tool schema,
and `flyto_blueprint.availability` imports no Flyto2 Core module.

The gate fails closed on dynamic module names. A step whose module is still a
`{{arg}}` template cannot be proven runnable, so the blueprint is hidden from
list/search, and `expand` gates on the module the supplied arguments actually
resolve to — an unresolved template is reported verbatim as missing.

Reason: an availability hint that a model could supply, or that defaulted to
"available" when it could not be proven, is an escalation path rather than a
safety control: `file_transform` runs `{{operation}}`, so an optimistic gate
would let a caller name any module string and have the host expand a workflow
around it. Trusting only host state, defaulting to "no claim" when nothing is
passed, and refusing to guess on unresolved templates keeps the existing
permissive integration working while making the gated integration honest.

## 2026-08-12 - The local verification contract pins a checkout interpreter

Decision: keep every Python `argv[0]` in `.flyto/coding.yaml` pinned to the
checkout-relative `.venv/bin/python`, and record in that file that contributors
must create that environment, GitHub Actions does not read the file, and only
the interpreter changed.

Reason: the trusted local runner executes these checks under a private HOME
whose `python` has no `pytest`, `ruff`, or this package, so the previous
bare-name form failed at process entry and produced no verification signal at
all. A failure to launch is worse than a failing check because it looks like an
environment problem rather than a repository result. The pin is an operator
environment repair with no user or clone path: `.github/workflows/ci.yml` still
installs its own toolchain and remains an independent portable gate.

## 2026-08-10 - Robotics and vision are not yet promoted to an official Blueprint

Decision: a Blueprint search that returns no robotics/vision candidate is a
valid not-applicable result, not a defect and not a success. Flyto2 AI may
proceed to Core discovery and validation. Do not ship an official
robotics/vision Blueprint until there are repeated trusted real-workload
outcomes and a completed physical loop. This is a gate on current evidence, not
a permanent exclusion of robotics/vision from the product.

Blueprint remains a reusable pattern and evidence store. It is not the planner,
the dispatcher, the Core module registry, or the device safety authority.

A later promotion must carry: exact module IDs; explicit bounded motion
arguments with no default distance or angle; current Core validation; safe-stop
semantics; resource binding; a defined evidence output shape; repeated trusted
outcomes; Gazebo evidence; and the relevant physical acceptance.

Reason: parameter validation is cheap to obtain and easy to mistake for
capability. A real `core.mcp_handler.validate_params` check on 2026-08-10
accepted four bounded robotics/vision calls and rejected five malformed ones,
which proves registration and argument checking and nothing else — no
execution, hardware, pixels, or authenticated Cloud route. Simulation and
gateway evidence from lower repositories does not transfer to Blueprint.
Publishing a Blueprint on that basis would let an unproven motion pattern be
reused as if it were verified.

## 2026-07-28 - Search summaries expose module identity, not execution data

Decision: add ordered, unique `module_ids` to Blueprint list/search summaries.
Do not expose step params, argument values, results, or expanded workflows.
Consumers must still apply the existing trust/evidence gate before using these
IDs as routing hints.

Reason: capability routers need to know which installed atoms a verified prior
workflow used, but expanding a Blueprint merely for discovery would require
arguments and expose a larger data surface. Identity-only summaries provide the
minimum safe integration contract.

## 2026-07-28 - Full-usage claims require diversity and history

Decision: add `benchmark-run.v2` and `benchmark-scorecard.v2` for separately
observed planner and workflow usage. Require exact total arithmetic, real
workload success, zero manual corrections, and the existing reliability /
false-reuse gates. A committed v3 result set must include at least three model
families, two hardware families, one independent runner, and one same-series
historical comparison. Keep raw records and rebuild every scorecard in CI.
Verify learning separately through a real SQLite
learn→reuse→failure→retirement→reload lifecycle.

Reason: one local model run can show a promising number but cannot establish
portability or stability. Planner-only accounting can also hide a model-backed
workflow step. Diversity, native workflow counters, an independent trust
boundary, history gates, and lifecycle evidence make deletion, drift,
under-counting, and “learning” that does not survive failure visible.

## 2026-07-27 - Performance claims require paired host evidence

Decision: evaluate the same tasks in `agent_baseline`,
`flyto_no_blueprint`, `blueprint_cold`, and `blueprint_warm` modes with one
model, environment, dataset commit, and paired seed. Accept only
`ci_verified` records, include adversarial and sealed-holdout tasks, publish
planner-only measurements, and require warm reuse to pass against both the
agent baseline and Flyto2 without Blueprint. Rebuild committed scorecards in
CI. Gate token reduction on the exact paired 95% confidence lower bound, not
only a point estimate. Treat an empty result directory as no claim.

Reason: a successful demo or a self-reported token number cannot separate
Blueprint's effect from model choice, environment drift, lucky sampling,
unsafe routing, or false reuse. Paired identity checks and explicit reliability
gates make future claims falsifiable while keeping the host execution boundary
honest. The second baseline prevents Flyto2 routing gains from being
misattributed to Blueprint.

## 2026-07-27 - Keep routine dependency branches out of the way

Decision: disable Dependabot's weekly version-update PRs for Python and GitHub
Actions with `open-pull-requests-limit: 0`, while leaving repository security
updates enabled. Keep release Actions pinned and tested. If Grype cannot compare
a patched Action's commit SHA with an advisory's semantic version range, ignore
only the exact advisory, package, package type, and patched SHA.

Reason: a growing branch list hides real work and stale PRs waste CI. Turning
off security updates would solve the wrong problem, while a broad scanner ignore
could hide a future vulnerable Action. The narrow policy keeps urgent updates
visible without recreating routine version-bump branches.

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
