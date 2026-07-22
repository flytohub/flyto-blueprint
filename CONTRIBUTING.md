# Contributing To Flyto2 Blueprint

Install the development dependencies from the repository root:

```bash
python -m pip install -e '.[dev]'
pytest
```

Changes to a packaged blueprint need expansion coverage. Changes to learning,
scoring, fingerprinting, or storage need focused tests for deterministic output
and duplicate handling. Public API changes must update `docs/API.md`,
`docs/FEATURES.md`, the documentation manifest, and the changelog.

Do not commit workflow credentials, customer data, learned production patterns,
Firestore service accounts, or generated local databases.
