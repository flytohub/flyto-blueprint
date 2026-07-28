# Flyto2 Blueprint

[![PyPI](https://img.shields.io/pypi/v/flyto-blueprint.svg)](https://pypi.org/project/flyto-blueprint/)
[![Python](https://img.shields.io/pypi/pyversions/flyto-blueprint.svg)](https://pypi.org/project/flyto-blueprint/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Website](https://img.shields.io/badge/website-flyto2.com-8B5CF6)](https://flyto2.com)
[![Docs](https://img.shields.io/badge/docs-docs.flyto2.com-06B6D4)](https://docs.flyto2.com)

<p align="center">
  <strong>Most agent memory stores what was said. Blueprint stores what actually worked.</strong>
</p>

Flyto2 Blueprint is procedure memory for AI agents. It turns a successful
execution into a parameterized workflow that can be searched, run again, and
judged by its real history.

```text
successful execution
        ↓
parameterize what changes
        ↓
save steps + retries + assertions + compatibility
        ↓
reuse with new arguments
        ↓
record the outcome in an Evidence Card
```

It is closer to turning a good agent run into a tested function than adding
another chat-history or vector-memory layer.

Blueprint does not train model weights. It makes a verified procedure
executable again.

## Installation and first run

```bash
pip install flyto-blueprint
```

```python
from flyto_blueprint import BlueprintEngine, MemoryBackend

engine = BlueprintEngine(storage=MemoryBackend())
result = engine.expand("browser_scrape", {
    "url": "https://example.com",
    "extract_selector": "h1",
})
print(result["data"]["steps"])
```

## How this differs from a typical AI agent

| | Typical AI agent | Flyto2 AI + Blueprint |
|---|---|---|
| Repeated job | Ask the model to reason again | Reuse the verified workflow |
| “It works” | Often based on the model's answer | Based on execution outcomes and assertions |
| Token use | Grows again on each model-planned run | Exact reuse can skip the agent's planning call |
| Learning | Often stays in one chat | Becomes a parameterized, searchable Blueprint |
| Shared knowledge | Easy to trust too quickly | Imported bundles start quarantined unless the host verifies them |
| Bad patterns | May keep getting suggested | Failures lower trusted scores and can retire the pattern |

An individual Evidence Card stays deliberately narrow:
`planner_model_calls_used=0` means exact reuse skipped outer-agent planning; it
does **not** pretend an `llm.*` workflow step was free. The v3 benchmark goes
further by recording native planner and workflow counters separately, checking
their arithmetic, and making a full-usage claim only when both are observed.

## Proof, not vibes

Every Blueprint summary includes an Evidence Card. It shows the number of
trusted outcomes, observed success rate, Wilson 95% lower bound, retries,
assertion pass rate, p50/p95 duration, and measured zero-planner-call reuse. Detailed
samples keep only an allowlist of execution facts and are capped to the latest
100 entries; prompts, parameters, API keys, and raw results are not accepted.

An Evidence Card answers “did this procedure work?” The versioned
[effectiveness benchmark](docs/BENCHMARKING.md) answers the harder question:
“does Blueprint help an agent without making it less reliable?” It compares the
same tasks, model, environment, and random seeds across four modes, including
ordinary conversation, Traditional Chinese and Japanese negation, hostile
evidence, incompatible reuse, and a sealed holdout.

The published v3 result is 10 tasks × 20 trials × four paired modes across five
runs: 4,000 raw records, three model families, Apple Silicon and Linux x86-64,
and one independent GitHub runner. The workloads perform real Python file/test
execution, real loopback HTTP browser and API I/O, real filesystem persistence,
and real Ollama inference. No planner or workflow call is mocked.

Across all five runs, warm verified reuse kept benchmark and workload success
at 100%, with zero manual corrections and zero false reuse. Compared with
Flyto2 routing without Blueprint, total observed model tokens fell by
71.25–72.90%. Compared with the generic agent baseline, they fell by
84.80–85.78%. The paired 95% lower bound for the Blueprint-specific reduction
was 63.29–64.43%, so the result does not depend on the point estimate alone.

That is evidence for this controlled suite, these model bytes, and these hosts;
it is not a claim that every task gets 70% cheaper. Read the
[one-screen result story](benchmarks/results/blueprint-effectiveness-v3/README.md),
inspect the committed raw JSONL, or rerun the deterministic closure verifier.

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

## What it already does

- 33 built-in browser, API, data, image, notification, monitoring, PDF, and OCR patterns.
- Synonym-expanded search, so “grab” can find “scrape.”
- Repository/runtime compatibility, so similar-looking workflows do not get
  mixed across incompatible projects.
- Retry and assertion contracts that survive learning and expansion.
- Evidence Cards that expose reliability and zero-planner-call reuse.

## Learn, measure, and share

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

# Report a trusted runtime outcome with measured facts
engine.report_outcome(
    "my_pattern",
    success=True,
    execution_id="run-123",
    evidence={
        "duration_ms": 842,
        "step_count": 3,
        "total_attempts": 3,
        "assertion_passed": True,
        "selection_mode": "deterministic",
        "planner_model_calls_used": 0,
        "model_call_scope": "planner",
    },
)

# Share explicitly; the library never uploads on its own
bundle = engine.export_blueprint("my_pattern", publisher="my-team")
engine.import_blueprint(bundle["data"])
```

Unsigned or unknown-publisher imports are quarantined as `community`. A host
may sign exports and configure trusted publisher keys through the Python API;
signing keys are intentionally unavailable to model-facing tools.

## Usage

Use Flyto2 Blueprint when an AI agent should reuse a known workflow shape
instead of generating a brand-new sequence every time. Typical use cases:

- Browser scrape, screenshot, and form-fill recipes.
- API integration workflows with typed arguments.
- PDF, OCR, image manipulation, and notification patterns.
- Learned workflow reuse for teams that run similar automations repeatedly.

## API

The package facade, engine lifecycle, storage protocol, scoring behavior, and
complete declaration inventory are documented in [API](docs/API.md) and the
[generated Python reference](docs/reference/python-api.md). MCP consumers should
use the [generated tool reference](docs/reference/mcp-tools.md). Benchmark
hosts should start with the plain-language
[benchmark guide](docs/BENCHMARKING.md).

## Architecture

[Architecture](ARCHITECTURE.md) explains discovery, expansion, persistence,
learning, and trust boundaries. [Features](docs/FEATURES.md) maps each behavior
to its implementation and tests; [the whitepaper](docs/WHITEPAPER.md) explains
the design rationale and limits.

## Configuration

The library has no mandatory remote service. Storage-specific credentials and
runtime settings belong to the selected backend and deployment secret store;
never place them in blueprint YAML or committed examples.

## Storage Backends

- **MemoryBackend** — In-memory, great for tests
- **SQLiteBackend** — File-based persistence (default)
- **FirestoreBackend** — Google Firestore (for flyto-cloud)

## Testing

```bash
python -m pytest
python -m ruff check .
python scripts/benchmark-scorecard.py verify-results \
  --suite benchmarks/suites/blueprint-effectiveness-v1.yaml \
  --results-dir benchmarks/results
python scripts/benchmark-scorecard.py verify-results \
  --suite benchmarks/suites/blueprint-effectiveness-v2.yaml \
  --results-dir benchmarks/results/blueprint-effectiveness-v2
python scripts/benchmark-scorecard.py verify-results \
  --suite benchmarks/suites/blueprint-effectiveness-v3.yaml \
  --results-dir benchmarks/results/blueprint-effectiveness-v3
python scripts/run_longitudinal_evidence.py verify \
  --evidence benchmarks/results/longitudinal/local-longitudinal.evidence.json
```

## Contributing

Open an issue or pull request for new blueprint categories, scoring behavior,
storage backends, docs, or examples. Security reports should go to
`security@flyto2.com`.

## License

Apache-2.0
