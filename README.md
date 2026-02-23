# flyto-blueprint

Self-evolving workflow pattern engine for [Flyto](https://flyto.app).

Blueprints are pre-built workflow patterns (YAML) that encode domain knowledge. The AI selects a blueprint and fills in arguments instead of building workflows from scratch. Learned blueprints are scored, deduplicated, and auto-retired.

## Install

```bash
pip install flyto-blueprint
```

## Quick Start

```python
from flyto_blueprint import BlueprintEngine, MemoryBackend

engine = BlueprintEngine(storage=MemoryBackend())

# List available blueprints
blueprints = engine.list_blueprints()

# Expand a blueprint with arguments
result = engine.expand("browser_scrape", {
    "url": "https://example.com",
    "extract_selector": "#content",
})

# Learn from a successful workflow
engine.learn_from_workflow(workflow_dict, name="My Pattern", tags=["browser"])

# Report outcomes to evolve scores
engine.report_outcome("my_pattern", success=True)
```

## Storage Backends

- **MemoryBackend** — In-memory, great for tests
- **SQLiteBackend** — File-based persistence (default)
- **FirestoreBackend** — Google Firestore (for flyto-cloud)

## License

Apache-2.0
