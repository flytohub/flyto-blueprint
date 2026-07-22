# Flyto2 Blueprint Whitepaper

## Abstract

Flyto2 Blueprint turns reusable workflow patterns into deterministic,
inspectable workflow steps. It combines packaged YAML blueprints, text and
intent search, argument expansion, composition, validation, outcome scoring,
and optional learned patterns behind a small Python API and MCP-compatible tool
schemas.

## Design Goals

- Make reusable automation patterns discoverable without hiding their steps.
- Keep template expansion deterministic and validate references before use.
- Separate retrieval and historical scoring from execution authorization.
- Support memory, SQLite, and Firestore persistence through one storage
  contract.
- Expose every callable and packaged contract through generated references.

## Processing Model

The loader reads packaged and learned records into typed models. Search ranks
deterministic text matches and can combine host-provided intent signals.
Expansion substitutes validated arguments, expands reusable blocks, rewrites
references, composes patterns, and validates the resulting steps. The library
returns workflow data; Flyto2 Core remains the execution and policy authority.

## Learning Model

Successful workflows can be fingerprinted, parameterized, deduplicated, and
stored as learned patterns. Outcome reports update bounded scores used for
future ranking. A historical success is evidence, not approval: callers must
still apply current permissions, safety rules, provider constraints, and
tests.

## Interfaces

[API.md](API.md) defines BlueprintEngine, storage, expansion, learning, and
tool interfaces. Generated references enumerate every Python declaration,
blueprint entry, and MCP input schema under
[the reference index](reference/README.md). The
[feature reference](FEATURES.md) maps each capability to source and tests.

## Security And Privacy

Blueprint arguments and learned records can carry sensitive workflow context.
Hosts must resolve secrets at execution time, scope persistent stores, and
sanitize learning inputs. MCP schemas describe inputs but do not grant
authorization. Firestore credentials and tenancy policy belong to the host.

## Verification And Limits

Unit and integration tests cover loading, search, expansion, composition,
fingerprints, learning, scoring, and storage. Generated-reference checks reject
source drift. The package does not run a scheduler, provide durable execution,
or claim semantic correctness for a selected pattern.

