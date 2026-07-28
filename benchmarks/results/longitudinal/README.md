# Does Blueprint really learn, or does it only say it learned?

These files answer that with a real SQLite lifecycle, not a mocked storage
object:

1. Learn a three-step workflow and persist it.
2. Submit trusted successes and watch its score rise.
3. Expand and reuse it 20 times without relearning.
4. Submit trusted failures and watch every score transition fall.
5. Cross the retirement threshold below 10.
6. Confirm the same running Engine rejects expansion immediately.
7. Start a new Engine on the same SQLite file and confirm the pattern does not
   return.

Both evidence files passed: one on Apple Silicon and one inside the independent
GitHub benchmark workflow. Each file contains metrics, transitions, checks, a
database SHA-256 digest, and its own evidence digest. It contains no workflow
output, prompt, credential, or database file.

Verify either file:

```bash
python scripts/run_longitudinal_evidence.py verify \
  --evidence benchmarks/results/longitudinal/local-longitudinal.evidence.json
```

Create a new versioned run with a fresh database path:

```bash
python scripts/run_longitudinal_evidence.py run \
  --database /tmp/blueprint-lifecycle.sqlite3 \
  --repository-commit "$(git rev-parse HEAD)" \
  --run-id local-lifecycle-YYYYMMDD \
  --output benchmarks/results/longitudinal/local-lifecycle-YYYYMMDD.evidence.json
```

The runner refuses to overwrite an existing database or output. CI verifies
every committed `*.evidence.json` file, so an edited transition or failed check
cannot silently become documentation.
