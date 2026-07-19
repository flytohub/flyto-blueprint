# Contributing

Read `PROJECT.md`, `ARCHITECTURE.md`, `STATE.md`, and `DECISIONS.md` before
changing blueprint matching, storage backends, packaging, or public docs.

Use flyto-indexer `search` and `impact` or `task(action='plan')` before editing.
Before opening a PR, run:

```bash
python -m pytest
python -m ruff check .
python -m build
flyto-index verify . --full-scan --json
```

Security issues go to `security@flyto2.com`.
