# Flyto2 Blueprint Python API

The package root intentionally exports a small stable API:

```python
from flyto_blueprint import BlueprintEngine, MemoryBackend, StorageBackend, get_engine
```

Lower-level modules are available for contributors but are not a compatibility
promise unless listed here.

The exhaustive [generated Python reference](reference/python-api.md) documents
every implementation class, function, nested function, and method with a source
link. It is useful for maintenance but does not expand the stable API boundary.

## `get_engine`

```python
get_engine(storage: StorageBackend | None = None) -> BlueprintEngine
```

Creates the process-wide default engine on first use. The first call selects
the storage backend; later calls return the same instance. Construct
`BlueprintEngine` directly when tests or multiple tenants require isolation.

## `BlueprintEngine`

```python
BlueprintEngine(storage: StorageBackend | None = None)
```

Loads packaged blueprints and composition blocks immediately. A storage backend
adds learned blueprints; omitting it creates a built-in-only engine.

### `list_blueprints(available_module_ids=None)`

Returns non-retired summaries ordered by score. Stored blueprints are refreshed
after the internal cache TTL. See
[host module availability](#host-module-availability) for the optional filter.

### `search(query, available_module_ids=None)`

Matches a query against blueprint identifiers, names, descriptions, and tags.
An empty query returns the same set as `list_blueprints()`. The optional filter
behaves exactly as in `list_blueprints`.

### `expand(blueprint_id, args, available_module_ids=None)`

Substitutes arguments, expands composition blocks, validates the resulting
steps against Flyto2 Core when available, and returns a result object:

```python
{"ok": True, "data": {"steps": [...]}, "warnings": []}
```

Unknown identifiers return `{"ok": False, "error": ...}` instead of raising a
lookup exception. Learned blueprint use counters are updated through storage.

## Host Module Availability

`available_module_ids` is authoritative host state: the set of module
identifiers the embedding host can actually execute. The engine never imports
Flyto2 Core and never discovers modules itself.

| Value | Behavior |
|---|---|
| `None` (default) | Unchanged behavior. Nothing is filtered and expansion accepts abstract or host-unknown module names. |
| A collection of IDs | `list`/`search` return only blueprints whose required modules are all available; `expand` fails when a required module is not. |
| An empty collection | A real claim that no module is available: nothing is listed and every expansion fails. |

Required modules include composition block steps, because those become real
workflow steps. The gate fails closed for dynamic module names: a step whose
module is still a `{{arg}}` template cannot be proven runnable, so the
blueprint is hidden from `list`/`search`, and `expand` gates on the module the
supplied arguments actually resolve to. Steps that expansion would skip
through `skip_if_missing` are not required.

The value is normalized exactly once per call, into one frozen set that
`list`, `search`, and `expand` all gate against. Malformed input raises rather
than being silently repaired, because dropping an entry would narrow the set
below what the host claimed and hide or refuse a blueprint for a reason no
error ever names:

| Input | Result |
|---|---|
| `str`, `bytes`, `bytearray`, `memoryview` | `TypeError` — iterating it would gate on single characters or integers. |
| Not iterable, or iterating raises `TypeError` | `TypeError`. |
| An entry that is not a `str` | `TypeError`. |
| An empty or whitespace-only entry | `ValueError`. |
| An entry with leading or trailing whitespace | `ValueError` — it is never trimmed, because a padded ID cannot match a real module name. |

Any iterable of well-formed ID strings is accepted, including a `set`,
`tuple`, `dict` (its keys), or a generator, which is consumed exactly once.

A blocked expansion is returned before any use or score is recorded:

```python
{
    "ok": False,
    "error": "Blueprint 'file_transform' requires modules unavailable on this host: shell.execute",
    "code": "BLUEPRINT_MODULE_UNAVAILABLE",
    "missing_module_ids": ["shell.execute"],
}
```

`missing_module_ids` is sorted and deduplicated, so the response is
deterministic. This parameter is deliberately absent from the model-facing MCP
tool schemas; a trusted host passes it internally when it binds the tools to
engine methods.

### `learn_from_workflow(...)`

```python
engine.learn_from_workflow(
    workflow,
    blueprint_id=None,
    name=None,
    tags=None,
    verified=False,
    compatibility=None,
    verification=None,
    trust_tier=None,
)
```

Abstracts concrete workflow values into reusable arguments, fingerprints the
structure, boosts an existing match when deduplicated, and persists a new
blueprint when storage is configured. `compatibility` scopes structurally
identical patterns to a repository, framework, runtime, or environment;
`verification` stores non-secret evidence metadata.

### `learn_from_execution(...)`

Convenience method for a successful execution. It delegates to
`learn_from_workflow(..., verified=True)` and starts the learned pattern with a
`local_verified` trust tier.

### `report_outcome(...)`

```python
engine.report_outcome(
    blueprint_id,
    success,
    execution_id="",
    evidence_tier="local_verified",
    evidence=None,
)
```

Trusted evidence (`local_verified`, `ci_verified`, or `official`) updates the
primary score. `community` evidence requires an execution identifier and
updates separate Bayesian counters; it can influence ranking within a bounded
confidence cap but cannot rewrite the trusted score. Recent execution
identifiers are deduplicated.

For trusted runtime reports, `evidence` may contain only these measured facts:

| Field | Meaning |
|---|---|
| `duration_ms` | Closed-loop wall-clock duration. |
| `step_count` | Number of workflow steps. |
| `total_attempts` | Execution attempts including retries. |
| `assertion_passed` | Whether the run's assertions passed. |
| `planner_model_calls_used` | Model calls used by the outer agent to plan this reuse path. |
| `model_calls_used` | Deprecated compatibility alias; not workflow-wide token use. |
| `model_call_scope` | Must be `planner` before legacy model-call evidence is treated as planner-scoped. |
| `selection_mode` | For example, `deterministic` or `model_selected`. |
| `workflow_hash` | SHA-256 workflow identity. |
| `executor_version` | Runtime evidence producer version. |

Unknown fields are discarded. The raw execution identifier is not stored in
the detailed sample; only its SHA-256 reference is retained. Community reports
cannot add detailed samples.

The response and list/search summaries include `evidence_card`. Its
`sample_count`, success rate, and Wilson 95% lower bound use trusted outcome
counters. Retry, assertion, duration, and model-call statistics use the latest
100 detailed samples. `zero_planner_model_call_count` means the host measured
`planner_model_calls_used=0`: the agent skipped re-planning. It says nothing
about model-backed workflow steps. `zero_llm_reuse_count` and
`zero_llm_reuse_rate` remain deprecated compatibility aliases and must not be
read as workflow-wide token totals.

### `export_blueprint(...)`

```python
engine.export_blueprint(
    blueprint_id,
    publisher="",
    claimed_tier=None,
    evidence=None,
    signing_key=None,
)
```

Returns an integrity-checked portable bundle and never uploads it. Export
rejects non-parameterized sensitive values in steps, compatibility metadata,
or verification evidence. Signing requires a publisher and a host-controlled
key of at least 16 bytes.

### `import_blueprint(bundle, trusted_keys=None)`

Validates format, digest, definition, and optional publisher signature before
persisting. Unsigned bundles, invalid signatures, and unknown publishers are
quarantined as `community`. Only a signature verified with a key in the
host-owned `trusted_keys` mapping preserves a higher claimed tier. Imported
usage and outcome counters always start fresh.

## Storage API

`StorageBackend` defines the persistence contract:

| Method | Contract |
|---|---|
| `load_all()` | Return raw blueprint dictionaries. |
| `save(id, data)` | Create or replace one blueprint. |
| `update(id, fields)` | Update selected fields. |
| `load_one(id)` | Return one blueprint or `None`. |
| `delete(id)` | Remove one blueprint. |
| `atomic_update(id, fn)` | Apply a read-modify-write function; `None` aborts. |

Implementations:

- `MemoryBackend`: process-local storage for tests and short-lived use.
- `SQLiteBackend`: local persistent storage with transactional updates.
- `FirestoreBackend`: Firestore collection storage with transaction support.

Import SQLite and Firestore implementations from their storage modules. The
package root exports only `MemoryBackend` and the abstract contract.

## Models

- `BlueprintArg` describes one typed, optionally required blueprint argument.
- `Blueprint` is the complete persisted pattern including steps, composition,
  score counters, detailed evidence samples, fingerprint, lifecycle, and
  source metadata.
- `BlueprintSummary` is the reduced list/search representation.

The engine accepts dictionaries at its boundary for direct compatibility with
YAML and Flyto2 Core workflow payloads. Pydantic models are available when an
integrator needs validation before calling the engine.

## MCP Tool Definitions

`flyto_blueprint.tools.get_blueprint_tools()` returns JSON Schema definitions
for:

- `list_blueprints`
- `use_blueprint`
- `save_as_blueprint`
- `report_blueprint_outcome`
- `export_blueprint`
- `import_blueprint`

These are tool definitions only. The host application binds them to engine
methods and remains responsible for authentication, tenant isolation,
authorization, execution evidence, signing keys, trusted publisher keys, and
transport. The model-facing export/import schemas cannot sign a bundle or
configure trust.

## Errors And Side Effects

- Search and list operations are read-only apart from cache refresh.
- Expand records use for learned blueprints.
- Learning and outcome reporting write when a storage backend is configured.
- Storage failures are returned as `ok: false` where the engine can recover;
  backend construction and direct backend calls may still raise provider
  exceptions.
