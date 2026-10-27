# Loop versions

One row per tag (IV.1): tag, commit, stage, product version, gate result against the baseline of its environment, checker verdicts, Lambda spend so far. Also the SHA-256 of each frozen format, of the preregistration and of the scorer when they are fixed. Append-only.

## Tags

| Tag | Commit | Stage | Product version | Gate result | Checker verdicts | Lambda spend (USD) |
|---|---|---|---|---|---|---|
| `loop-base` | `f31eff4` | start (fallback point for S0) | 0.1.0.dev0 (no `VERSION` file yet at this commit) | main checkout baseline: PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28; six side gates pass | none (starting point) | 0.00 |
| `loop-s01-v1` | `cef0294` | S1 hygiene, replies saved, INST_FINDER switch, readiness, attempt 1 | 0.1.0.dev1 | loop branch after merge: main PASS 247, WARN 1, SKIP 3, FAIL or ERROR 27 (baseline minus 112; new 275 to 277 pass); six side gates pass | three rounds; no CRITICAL or SERIOUS left; 70 named, 66 worked, 4 deferred (reason c) | 0.00 |
| `loop-s00-v1-open` | `5e844ed` | S0 Start, attempt 1 | 0.1.0.dev0 | equal to baseline at `7c6d132` (later commits change only `docs/loop/`) | reading check 3 rounds closed; completeness 2 rounds; tie-break confirmed 3 items unmet this session (status line and hooks registration, checker definitions, deny rules by canary) | 0.00 |

## Frozen hashes

| What | Version | SHA-256 | Recorded |
|---|---|---|---|
