# Flyto2 Blueprint Feature Reference

## Packaged Blueprint Catalog

The package ships browser, API, data conversion, file, image, OCR, PDF,
monitoring, and notification patterns plus reusable composition blocks. The
loader reads these package resources; user workflows do not need repository
paths at runtime.

## Search And Intent Matching

Deterministic search scores identifiers, names, descriptions, and tags. The
optional intent matcher adds query expansion, keyword candidates, embeddings,
and query tracking without changing the deterministic engine API.

## Expansion And Composition

Expansion resolves arguments recursively, expands named blocks, chains multiple
blueprints, deconflicts step identifiers, wires cross-blueprint references, and
reports unresolved placeholders. Resulting steps can be validated against
Flyto2 Core when the optional dependency is installed.

## Workflow Learning

Learning fingerprints successful workflows, abstracts concrete values into
parameters, deduplicates existing patterns, and records provenance and score
metadata. It does not train a remote model or upload workflow content by
itself.

## Outcome Scoring

Use, success, and failure reports update counters and scores. Duplicate recent
execution reports are rejected so retries do not distort ranking. Retirement
allows consistently poor learned patterns to disappear from list/search output.

## Storage Backends

Memory, SQLite, and Firestore backends implement the same persistence contract.
Applications choose storage explicitly; built-in blueprints remain package
resources and are not rewritten by learned data.

## MCP Integration

The package exposes four MCP-compatible JSON Schema tool definitions for list,
expand, save, and outcome reporting. The embedding host owns credentials,
tenant scope, tool authorization, and Flyto2 Core execution.

## Public API

The supported Python interface, return shapes, storage methods, model roles,
side effects, and error behavior are documented in [API.md](API.md).
