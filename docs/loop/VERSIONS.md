# Loop versions

One row per tag (IV.1): tag, commit, stage, product version, gate result against the baseline of its environment, checker verdicts, Lambda spend so far. Also the SHA-256 of each frozen format, of the preregistration and of the scorer when they are fixed. Append-only.

## Tags

| Tag | Commit | Stage | Product version | Gate result | Checker verdicts | Lambda spend (USD) |
|---|---|---|---|---|---|---|
| `loop-base` | `f31eff4` | start (fallback point for S0) | 0.1.0.dev0 (no `VERSION` file yet at this commit) | main checkout baseline: PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28; six side gates pass | none (starting point) | 0.00 |
| `loop-s00-v1-open` | `5e844ed` | S0 Start, attempt 1 | 0.1.0.dev0 | equal to baseline at `7c6d132` (later commits change only `docs/loop/`) | reading check 3 rounds closed; completeness 2 rounds; tie-break confirmed 3 items unmet this session (status line and hooks registration, checker definitions, deny rules by canary) | 0.00 |

## Frozen hashes

| What | Version | SHA-256 | Recorded |
|---|---|---|---|
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` | `1875bf8e576f28ec10f3abfe722460027234cb8df44e3ad6e24aa01046b62f26` | 2026-10-27 09:46 +03:00, loop/s03 (D-018) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (after the code-blind check) | `991c25f6a6a121be6cccd9d39392f1e0ebb13576085b453d1909195016352f92` | 2026-10-27 10:16 +03:00, loop/s03 (D-020) |
