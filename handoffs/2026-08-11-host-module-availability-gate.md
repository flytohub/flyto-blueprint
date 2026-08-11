# Host module availability gate

Date: 2026-08-11
Owner: claude
Branch: main

## Finished

- Closed out the host module availability gate that was left dirty in the
  working tree. New module `flyto_blueprint/availability.py`, new suite
  `tests/test_availability.py`, and edits to `flyto_blueprint/engine.py` and
  `flyto_blueprint/search.py`.
- `list_blueprints`, `search`, and `expand` take an optional
  `available_module_ids` collection supplied by the embedding host.
- Reconciled `ARCHITECTURE.md`, `STATE.md`, `DECISIONS.md`, `CHANGELOG.md`,
  `tasks.md`, `docs/API.md`, `docs/FEATURES.md`,
  `docs/documentation-manifest.json`, and `docs/reference/python-api.md` with
  the behavior that is actually in the tree.
- Kept and documented Codex's `.flyto/coding.yaml` entry repair.

## Behavior that is locked in

- **Fail-closed dynamic modules.** A step whose module is still a `{{arg}}`
  template cannot be proven runnable. Such a blueprint is hidden from `list`
  and `search`, and `expand` gates on the module the supplied arguments
  actually resolve to. An unresolved template is reported verbatim in
  `missing_module_ids`. `file_transform` runs `{{operation}}`, so this is the
  difference between a gate and an escalation path.
- **Gate before mutation.** `expand` returns the availability failure after the
  not-found check and before `record_use`, scoring, and `expand_blueprint`. A
  blocked expansion leaves the stored blueprint byte-identical.
- **Compose blocks count.** Required modules include the steps a composition
  block contributes, because those become real steps of the expanded workflow.
  `browser_scrape` composes `browser_init`, so `browser.launch` and
  `browser.goto` are required even though neither appears in its own `steps`.
- **`skip_if_missing` is honored.** A step expansion would drop is not
  required, so a host without `browser.wait` can still expand `browser_scrape`
  when `wait_selector` is absent.
- **`None` compatibility.** Omitting the argument means the host made no claim:
  nothing is filtered and abstract or host-unknown module names still expand,
  exactly as before this change.
- **Explicit empty set.** An empty collection is a real claim that nothing is
  executable: `list` and `search` return nothing and every `expand` fails. It
  is deliberately not the same as `None`.
- **Not model-facing.** The parameter appears in no schema returned by
  `get_blueprint_tools()`; a test asserts this. `availability.py` imports no
  Flyto2 Core module and discovers nothing itself. A bare `str`/`bytes` raises
  `TypeError` rather than being iterated into single characters.
- Failures are deterministic: `missing_module_ids` is sorted and deduplicated,
  so `["browser.goto"]` and `{"browser.goto"}` produce identical results.

## Verification

All four required checks in `.flyto/coding.yaml` ran and passed on 2026-08-11
against this working tree:

| Check | Result |
| --- | --- |
| `compile` | pass |
| `lint` (Ruff) | pass |
| `generated_reference` | pass |
| `tests` | pass, 213 tests |

Codex independently reproduced the same four checks on the same checkout —
`compile`, Ruff, `generated_reference`, and 213 passing tests — plus a targeted
behavioral check that expanding `file_transform` with
`operation="shell.execute"` against a host set that lacks `shell.execute` is
rejected with `BLUEPRINT_MODULE_UNAVAILABLE` and
`missing_module_ids == ["shell.execute"]`. Two independent runs agree.

The generated reference was also cross-checked by hand against
`scripts/generate-reference.py` semantics and agrees with the passing
`generated_reference` check: 21 → 22 modules, 168 → 176 declarations, line
counts 130 / 341 / 165 for `availability.py` / `engine.py` / `search.py`, and
every declaration line number matching the current source.

## Not verified

- `python -m build` was not run for this change.
- `flyto-index verify . --full-scan --strict --json` (the `indexer_post` step)
  was not run for this change. Neither is one of the four pinned checks.
- Nothing was committed, merged, tagged, built, published, or deployed. There
  is no release or deployment claim here. CI on merge remains the release gate,
  and it runs the build and Indexer verification independently.

## The `.flyto/coding.yaml` entry repair — kept

Codex's prior job repaired only this file, and the repair is preserved. Every
`argv[0]` is pinned to the checkout-local `.venv/bin/python`
instead of a bare `python`, because the trusted local runner executes these
checks under a private HOME whose `python` resolves to an interpreter without
`pytest`, `ruff`, or this package. The bare-name form therefore failed at
process entry and produced no verification signal at all — which reads like an
environment fault rather than a repository result.

Limits, now written into the file itself, into `STATE.md`, and into
`DECISIONS.md` (2026-08-11):

- The path is checkout-relative. Another operator creates that checkout's
  `.venv`; no user account, clone path, or sibling repository is encoded.
- `.github/workflows/ci.yml` does not read `.flyto/coding.yaml`. CI installs
  its own Python 3.12 toolchain and runs `ruff check .`, `pytest`,
  `python -m build`, and `flyto-index verify . --full-scan --strict --json`
  independently, so CI is unaffected by the pin.
- Only the interpreter changed. The four checks, their arguments, their order,
  and their `required: true` status are identical.

## Context on the prior job

The earlier job on this change ended at the provider `turn_limit` with its
budget exhausted. That is why `.flyto/coding.yaml` was the only file it
repaired and why the memory files were left unreconciled until now. It does not
qualify the check results above, which were produced after that repair.

## Next step

Commit the working tree and let CI re-run the pinned checks plus the build and
Indexer verification on a clean checkout. Do not treat the local passes as a
release signal.
