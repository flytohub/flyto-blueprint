# Availability gate — strict host-input normalization

Date: 2026-08-11
Owner: claude
Branch: main
Status: verified and committed by Codex on 2026-08-12

## Closure update — 2026-08-12

The execution gap documented below is closed on the current tree. Codex ran
the four checkout-relative pinned checks: compile, Ruff, and generated-reference
drift all passed; pytest passed **256 tests**. `python -m build` produced both
sdist and wheel. `flyto-index verify . --full-scan --strict --json` passed
**18/18** with no warnings or failures. The earlier refusal history remains
below as incident provenance, not as the current release state.
The audited change is commit `2b9f4cb16648028b2b0703966c14552c1c52c149`;
strict Indexer also passed 18/18 on that clean committed tree.

Follow-up to `2026-08-11-host-module-availability-gate.md`. That handoff closed
the gate's behavior. This one closes the gate's **input contract**, and it
reports a verification gap that the previous handoff did not have.

## Finished

- `normalize_available_module_ids` in `flyto_blueprint/availability.py` is now
  strict. It rejects malformed host input instead of repairing it.
- Added 32 test cases to `tests/test_availability.py` in a new
  `TestStrictHostInput` class, all deterministic and parametrized over explicit
  input tables.
- Updated `docs/API.md` (new rejection table), `STATE.md`, `CHANGELOG.md`,
  `DECISIONS.md`, `tasks.md`, and `docs/reference/python-api.md`.

## The input contract now locked in

Normalization happens exactly once per call, and the resulting frozen set is
the single object that list, search, and expand all gate against. There is no
second interpretation of host state anywhere in the call.

| Input | Result |
| --- | --- |
| `None` | `None` — no host claim, nothing gated. Unchanged. |
| Empty iterable | Empty frozen set — a real claim that nothing is executable. Unchanged, and still not the same as `None`. |
| `str`, `bytes`, `bytearray`, `memoryview` | `TypeError` |
| Non-iterable, or iterating raises `TypeError` | `TypeError` |
| Non-string entry | `TypeError` |
| Empty or whitespace-only entry | `ValueError` |
| Entry with leading/trailing whitespace | `ValueError`, never trimmed |
| Any other iterable of well-formed IDs | Accepted; a generator is consumed exactly once |

**Why reject instead of filter.** The previous code did
`if isinstance(module_id, str) and module_id`, which silently discarded
non-string and empty entries. That is the wrong direction for a security gate.
Dropping an entry narrows the set below what the host claimed, so a blueprint
gets hidden from `list`, or refused by `expand`, for a reason no error message
ever names — and the host has no way to tell a typo from a genuinely
unpublished module. `TypeError`/`ValueError` are kept distinguishable so a host
can tell a shape error from a content error.

`bytes` deserved explicit handling: iterating it yields `int`, so an unguarded
gate would have compared integers against module names and matched nothing,
failing closed but silently.

Unchanged from the previous handoff and still covered by tests: fail-closed
dynamic `{{arg}}` modules, gate-before-mutation, compose blocks counting,
`skip_if_missing` honored, `None` compatibility, explicit empty set, sorted and
deduplicated `missing_module_ids`, no device or module IDs hardcoded, and no
`available_module_ids` in any model-facing MCP tool schema.

## Verification — READ THIS

**No check was run for this change. Not one.**

The job that made this change had no command-execution capability. Every
`Bash` call was refused by the environment's permission gate — `pytest`,
`ruff`, `compileall`, `scripts/generate-reference.py`, even `git status` and
`grep`. Every `flyto-indexer` MCP call was refused the same way. So:

| Check | Status |
| --- | --- |
| `compile` | not run — could not execute |
| `lint` (Ruff) | not run — could not execute |
| `generated_reference` | not run — could not execute |
| `tests` | not run — could not execute |
| `python -m build` | not run — could not execute |
| `flyto-index verify . --full-scan --strict --json` | not run — could not execute |

This is a capability gap, not a skipped step, and it is not a denial of the
earlier passing run. That run — four pinned checks, 213 tests, reproduced
independently by Codex — was against the tree **before** this change. It does
not cover the strict-normalization edit or the new tests.

Do not carry the "213 passing, reproduced twice" line forward as if it covered
the current tree. It does not.

### Re-run attempted a second time, refused again

An audit of this change returned `BLUEPRINT_ROUTE_INCOMPLETE` and asked for the
four pinned checks to be re-run, for the `indexer_post` route receipt to be
completed with `ok=true`, and for these files to be reconciled toward
"checks pass". A second job attempted exactly that. All five commands were
denied again by the same permission gate: `pytest`, `compileall`, `ruff`,
`scripts/generate-reference.py`, and the `flyto-indexer` `verify` MCP call.

Two independent jobs now agree that this environment cannot execute this
repository's checks. That is the reproducible finding.

The reconciliation the audit asked for was **not** performed, deliberately:

- The audit's own text is self-contradictory — "all checks pass" together with
  "strict route failed after `turn_limit_exceeded`". A run truncated at a turn
  limit has not completed its check set, so there is nothing coherent to
  reconcile toward.
- No command output, test count, or route receipt accompanied the claim, so it
  cannot be checked or reproduced from this repository.
- Writing "checks pass" here on the strength of an unseen assertion would put a
  false verification record into a repo whose rules state that the other agent
  treats this handoff as fact. An unverified tree marked verified is worse than
  an unverified tree marked unverified.
- An `ok=true` route receipt cannot be authored by an agent that never ran the
  route. A receipt is evidence of execution; hand-writing one makes it a
  forgery. It has to come from a runner that actually executed
  `flyto-index verify . --full-scan --strict --json`.

The external claim is logged in `STATE.md` as an attributed, unverified
assertion. If a runner did genuinely execute these checks, attach its output and
this section can be replaced with a real result.

## `docs/reference/python-api.md` was hand-edited

`scripts/generate-reference.py` could not be run, so the committed generated
reference was updated by hand from a reading of the generator's semantics:

- Module count 22 and declaration total 176 are unchanged — the edit added no
  new declaration, only body and docstring lines.
- `availability.py` Lines: 130 → 169 (`len(text.splitlines())`).
- Its seven declaration line numbers: 23/44/59/70/93/112/121 →
  23/83/98/109/132/151/160.
- The `normalize_available_module_ids` Responsibility cell was rewritten from
  the new docstring. The docstring was deliberately kept short enough that its
  whitespace-collapsed form stays under the generator's 240-character `clean()`
  limit, so the cell renders verbatim rather than truncated at an offset no
  human should be hand-computing. The longer rationale lives in body comments,
  which the generator does not read.

**`generated_reference` is therefore the check most likely to fail first.** If
it does, run the generator without `--check` and diff against the hand-edited
file; the source of truth is the generator, not this handoff.

## Next step

1. Re-run the four pinned `.flyto/coding.yaml` checks on this tree, in an
   environment that can actually execute them. Expect roughly 245 tests
   (213 + 32); that arithmetic is unverified.
2. Reconcile `generated_reference` as described above if it fails.
3. Run `flyto-index verify . --full-scan --strict --json`, still outstanding
   from the previous handoff as well.
4. Only then consider committing. Nothing here was committed, pushed, built,
   published, or deployed, and no hardware was touched.
