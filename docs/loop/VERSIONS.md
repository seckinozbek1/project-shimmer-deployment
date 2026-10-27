# Loop versions

One row per tag (IV.1): tag, commit, stage, product version, gate result against the baseline of its environment, checker verdicts, Lambda spend so far. Also the SHA-256 of each frozen format, of the preregistration and of the scorer when they are fixed. Append-only.

## Tags

| Tag | Commit | Stage | Product version | Gate result | Checker verdicts | Lambda spend (USD) |
|---|---|---|---|---|---|---|
| `loop-base` | `f31eff4` | start (fallback point for S0) | 0.1.0.dev0 (no `VERSION` file yet at this commit) | main checkout baseline: PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28; six side gates pass | none (starting point) | 0.00 |
| `loop-s01-v1` | `cef0294` | S1 hygiene, replies saved, INST_FINDER switch, readiness, attempt 1 | 0.1.0.dev1 | loop branch after merge: main PASS 247, WARN 1, SKIP 3, FAIL or ERROR 27 (baseline minus 112; new 275 to 277 pass); six side gates pass | three rounds; no CRITICAL or SERIOUS left; 70 named, 66 worked, 4 deferred (reason c) | 0.00 |
| `loop-s02-v1` | `3b802a1` | S2 honest outputs, multi-round enablement, run controller, attempt 1 | 0.1.0.dev2 | loop branch after merge: main PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27 (the baseline's 31 non-pass checks; new 278 to 280 pass); six side gates pass | three rounds plus three reader-check rounds and two tie-breaks; no CRITICAL or SERIOUS left; open items 20 and 21 recorded | 0.00 USD instances; storage share 0.05 USD |
| `loop-s00-v1-open` | `5e844ed` | S0 Start, attempt 1 | 0.1.0.dev0 | equal to baseline at `7c6d132` (later commits change only `docs/loop/`) | reading check 3 rounds closed; completeness 2 rounds; tie-break confirmed 3 items unmet this session (status line and hooks registration, checker definitions, deny rules by canary) | 0.00 |

## Frozen hashes

| What | Version | SHA-256 | Recorded |
|---|---|---|---|
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` | `1875bf8e576f28ec10f3abfe722460027234cb8df44e3ad6e24aa01046b62f26` | 2026-10-27 09:46 +03:00, loop/s03 (D-018) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (after the code-blind check) | `991c25f6a6a121be6cccd9d39392f1e0ebb13576085b453d1909195016352f92` | 2026-10-27 10:16 +03:00, loop/s03 (D-020) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (after the generators' 13 questions) | `c2723037d73a3f855721c48a8b6f67831db6afae277aa37b0aad414a9deb982f` | 2026-10-27 11:34 +0300, loop/s03 (D-025) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (section 1 test archive and working folder; section 12 multi-round case) | `3f4a50776168b592d88ca8635445f8437918fd1f92b72313353ed99fc443c0f9` | 2026-10-27 15:46 +0300, loop/s03 (D-041) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (first draft) | `dcce00dd05aa11d69a6042656f6a91d7c98b3ce645680dcd7f39d732dfc173c9` | 2026-10-27 15:46 +0300, loop/s03 (D-041) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (section 6: the possible-successor refusal) | `58bb6f4ce21eda578bb081059eaeecc0cde4eafa90336b97df6b217883f39c3c` | 2026-10-27 15:56 +0300, loop/s03 (D-041) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (S3 round 1: multi-round keys, expected refusals, text fixes; D-042) | `451e5c9b9a8312e7877d0d3c3c90ae95c3fe50eccb0c3af0c01d7a5b9580dc45` | 2026-10-27 17:00 +0300, loop/s03 (D-047) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S3 round 1: reason_kind table, review-mode inference) | `b0f293befd45d33601ba81a224effc15c73e1a08d181202329880a11afb5dff3` | 2026-10-27 17:00 +0300, loop/s03 (D-047) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (S3 round 2) | `a1837a9cd82a3d013f85276f7d1aea79d17bef56e8cdf030ebd4a477b5dfa09a` | 2026-10-27 17:51 +0300, loop/s03 (D-049) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S3 round 2) | `895237fee1a75ba54042b66b2bc76f96045cdea57e57fd39d65914034147b10d` | 2026-10-27 17:51 +0300, loop/s03 (D-049) |
