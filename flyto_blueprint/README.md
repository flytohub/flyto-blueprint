# Flyto2 Blueprint Package

`flyto_blueprint` implements reusable workflow discovery, scoring, composition,
validation, learning, storage adapters, MCP tools, and the packaged blueprint
catalog.

Use these references when changing the package:

- [Architecture](../ARCHITECTURE.md) explains the engine and storage boundaries.
- [Feature map](../docs/FEATURES.md) maps supported behavior to source and tests.
- [Python implementation reference](../docs/reference/python-api.md) lists every
  class, function, nested function, and method with an exact source link.
- [Blueprint catalog](../docs/reference/blueprint-catalog.md) inventories shipped
  YAML patterns and their module dependencies.
- [MCP tools](../docs/reference/mcp-tools.md) defines the integration surface.
- [Security](../SECURITY.md) defines execution and contribution boundaries.

Run `python3 scripts/generate-reference.py` from the repository root after
changing Python declarations or packaged blueprints. CI uses `--check` to reject
reference drift.
