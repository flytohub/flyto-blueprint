# Continuous Blueprint learning and sharing

Date: 2026-07-26

Summary:

- Added repository/runtime compatibility-aware learning and semantic import
  deduplication.
- Preserved retry and assertion execution contracts through learning and
  expansion.
- Added explicit portable export/import with canonical digest, optional
  host-controlled publisher HMAC, sensitive-metadata rejection, and community
  quarantine.
- Split trusted outcome scores from capped, confidence-weighted community
  observations.
- Added six MCP schemas; model-facing tools cannot supply signing or trusted
  publisher keys.

Trust boundary:

- The library never uploads Blueprint data.
- Only the embedding host owns transport, tenant authorization, publisher keys,
  and trusted execution evidence.
- Unsigned, invalid-signature, or unknown-publisher imports remain community
  content until locally verified.

Verification:

- Run `python -m pytest -q`.
- Run `python -m ruff check .`.
- Run `python3 scripts/generate-reference.py --check`.
- Run Flyto2 Indexer strict verification before release.
