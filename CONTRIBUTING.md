# Contributing To Flyto2 Blueprint

Create the checkout's virtualenv and install the development dependencies from
the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]' 'ruff==0.15.15'
.venv/bin/python -m pytest
```

`.venv` is not optional: every check in `.flyto/coding.yaml` runs
`.venv/bin/python`, and without it the audited coding route fails closed before
it can report anything. Ruff is pinned to the version `.github/workflows/ci.yml`
installs. This repository declares no `[tool.ruff]` configuration, so Ruff runs
its defaults and its default rule set changes between releases — an unpinned
local Ruff reports hundreds of findings CI does not, and the disagreement looks
like a real regression.

Changes to a packaged blueprint need expansion coverage. Changes to learning,
scoring, fingerprinting, or storage need focused tests for deterministic output
and duplicate handling. Public API changes must update `docs/API.md`,
`docs/FEATURES.md`, the documentation manifest, and the changelog.

Do not commit workflow credentials, customer data, learned production patterns,
Firestore service accounts, or generated local databases.
