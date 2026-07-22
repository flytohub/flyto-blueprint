# Flyto2 Blueprint State

## Current State

- Repository status: active open-source Python package, version 0.2.2.
- Stable package root exports `BlueprintEngine`, `StorageBackend`,
  `MemoryBackend`, and `get_engine`.
- The package ships 33 workflow blueprints, one composition block, four MCP
  tool schemas, and memory, SQLite, and optional Firestore storage.
- Generated reference covers 18 package modules and 95 class, function, and
  method declarations. CI rejects declaration, catalog, and MCP schema drift.
- Documentation contract maps five source areas and seven feature surfaces to
  durable docs and test evidence.
- Latest local verification on 2026-07-22: Ruff passed, 98 tests passed,
  sdist/wheel build passed, documentation audit passed with no warnings, and
  Flyto2 Indexer strict full-scan passed 17/17.

## Release Notes

- No repository-local release blocker is recorded.
- Publishing to PyPI and provider-side workflow success still require remote
  evidence; local verification cannot prove registry permissions.
