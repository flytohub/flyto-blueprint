# flyto-blueprint

Self-evolving workflow pattern engine for [Flyto](https://flyto.app).

Blueprints are pre-built workflow patterns (YAML) that encode domain knowledge. The AI selects a blueprint and fills in arguments instead of building workflows from scratch. Learned blueprints are scored, deduplicated, and auto-retired.

## Install

```bash
pip install flyto-blueprint
```

## What's New in v0.2.0

- **33 builtin blueprints** (up from 10) — covering browser automation, API calls, data processing, image manipulation, notification, monitoring, PDF, and OCR workflows
- **Synonym-expanded search** — blueprint matching now expands synonyms and uses word-level scoring for more accurate results (e.g., "grab" matches "scrape", "picture" matches "screenshot")
- **Intent matcher** — dynamically derives `context_key` values for the credential vault, so blueprints can auto-fill site-specific credentials without hardcoded mappings
- **Query tracker** — records query-to-blueprint mappings after successful executions, enabling learning and analytics over time

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
