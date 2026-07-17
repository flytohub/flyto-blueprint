# Flyto2 Blueprint

[![PyPI](https://img.shields.io/pypi/v/flyto-blueprint.svg)](https://pypi.org/project/flyto-blueprint/)
[![Python](https://img.shields.io/pypi/pyversions/flyto-blueprint.svg)](https://pypi.org/project/flyto-blueprint/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Website](https://img.shields.io/badge/website-flyto2.com-8B5CF6)](https://flyto2.com)
[![Docs](https://img.shields.io/badge/docs-docs.flyto2.com-06B6D4)](https://docs.flyto2.com)

Self-evolving workflow pattern engine for [Flyto2](https://flyto2.com).
Blueprints turn repeated browser automation, API integration, data processing,
PDF/OCR, notification, monitoring, and AI-agent tasks into reusable YAML
patterns instead of one-off generated scripts.

In plain English: when an agent has solved the same kind of job before, it
should not ask the model to invent the workflow again. Flyto2 Blueprint lets the
agent reuse a known pattern, fill the missing arguments, and learn from the run.

AI agents use Flyto2 Blueprint to select a proven workflow pattern, fill in
validated arguments, learn from successful runs, deduplicate similar patterns,
and retire stale automations. This is the open-source blueprint layer used by
Flyto2 Core, Flyto2 AI, and Flyto2 Cloud.

Official links: [flyto2.com](https://flyto2.com) ·
[Docs](https://docs.flyto2.com/blueprint/) ·
[PyPI](https://pypi.org/project/flyto-blueprint/) ·
[flyto-core](https://github.com/flytohub/flyto-core) ·
[flyto-ai](https://github.com/flytohub/flyto-ai)

Good fit if you searched for:

- reusable AI workflow patterns
- workflow automation blueprint engine
- self-learning automation recipes
- YAML workflow templates for AI agents

## Install

```bash
pip install flyto-blueprint
```

## Try it in 60 seconds

```python
from flyto_blueprint import BlueprintEngine, MemoryBackend

engine = BlueprintEngine(storage=MemoryBackend())
result = engine.expand("browser_scrape", {
    "url": "https://example.com",
    "extract_selector": "h1",
})
print(result.workflow["steps"])
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

## Usage

Use Flyto2 Blueprint when an AI agent should reuse a known workflow shape
instead of generating a brand-new sequence every time. Typical use cases:

- Browser scrape, screenshot, and form-fill recipes.
- API integration workflows with typed arguments.
- PDF, OCR, image manipulation, and notification patterns.
- Learned workflow reuse for teams that run similar automations repeatedly.

## Storage Backends

- **MemoryBackend** — In-memory, great for tests
- **SQLiteBackend** — File-based persistence (default)
- **FirestoreBackend** — Google Firestore (for flyto-cloud)

## Testing

```bash
python -m pytest
python -m ruff check .
```

## Contributing

Open an issue or pull request for new blueprint categories, scoring behavior,
storage backends, docs, or examples. Security reports should go to
`security@flyto2.com`.

## License

Apache-2.0

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=flytohub/flyto-blueprint&type=Date)](https://star-history.com/#flytohub/flyto-blueprint&Date)
