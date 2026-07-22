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

### `list_blueprints()`

Returns non-retired summaries ordered by score. Stored blueprints are refreshed
after the internal cache TTL.

### `search(query)`

Matches a query against blueprint identifiers, names, descriptions, and tags.
An empty query returns the same set as `list_blueprints()`.

### `expand(blueprint_id, args)`

Substitutes arguments, expands composition blocks, validates the resulting
steps against Flyto2 Core when available, and returns a result object:

```python
{"ok": True, "data": {"steps": [...]}, "warnings": []}
```

Unknown identifiers return `{"ok": False, "error": ...}` instead of raising a
lookup exception. Learned blueprint use counters are updated through storage.

### `learn_from_workflow(...)`

```python
engine.learn_from_workflow(
    workflow,
    blueprint_id=None,
    name=None,
    tags=None,
    verified=False,
)
```

Abstracts concrete workflow values into reusable arguments, fingerprints the
structure, boosts an existing match when deduplicated, and persists a new
blueprint when storage is configured.

### `learn_from_execution(workflow, name=None, tags=None)`

Convenience method for a successful execution. It delegates to
`learn_from_workflow(..., verified=True)` and starts the learned pattern with a
verified score.

### `report_outcome(blueprint_id, success, execution_id="")`

Records success or failure, updates score counters, and deduplicates recent
reports when an execution identifier is supplied. The method returns a result
object describing whether the report was accepted.

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
  score counters, fingerprint, lifecycle, and source metadata.
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

These are tool definitions only. The host application binds them to engine
methods and remains responsible for authentication, tenant isolation,
authorization, and execution evidence.

## Errors And Side Effects

- Search and list operations are read-only apart from cache refresh.
- Expand records use for learned blueprints.
- Learning and outcome reporting write when a storage backend is configured.
- Storage failures are returned as `ok: false` where the engine can recover;
  backend construction and direct backend calls may still raise provider
  exceptions.
