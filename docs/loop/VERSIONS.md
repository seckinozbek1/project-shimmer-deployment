# Loop versions

One row per tag (IV.1): tag, commit, stage, product version, gate result against the baseline of its environment, checker verdicts, Lambda spend so far. Also the SHA-256 of each frozen format, of the preregistration and of the scorer when they are fixed. Append-only.

## Tags

| Tag | Commit | Stage | Product version | Gate result | Checker verdicts | Lambda spend (USD) |
|---|---|---|---|---|---|---|
| `loop-base` | `f31eff4` | start (fallback point for S0) | 0.1.0.dev0 (no `VERSION` file yet at this commit) | main checkout baseline: PASS 243, WARN 1, SKIP 3, FAIL or ERROR 28; six side gates pass | none (starting point) | 0.00 |
| `loop-s01-v1` | `cef0294` | S1 hygiene, replies saved, INST_FINDER switch, readiness, attempt 1 | 0.1.0.dev1 | loop branch after merge: main PASS 247, WARN 1, SKIP 3, FAIL or ERROR 27 (baseline minus 112; new 275 to 277 pass); six side gates pass | three rounds; no CRITICAL or SERIOUS left; 70 named, 66 worked, 4 deferred (reason c) | 0.00 |
| `loop-s02-v1` | `3b802a1` | S2 honest outputs, multi-round enablement, run controller, attempt 1 | 0.1.0.dev2 | loop branch after merge: main PASS 250, WARN 1, SKIP 3, FAIL or ERROR 27 (the baseline's 31 non-pass checks; new 278 to 280 pass); six side gates pass | three rounds plus three reader-check rounds and two tie-breaks; no CRITICAL or SERIOUS left; open items 20 and 21 recorded | 0.00 USD instances; storage share 0.05 USD |
| `loop-s00-v1-open` | `5e844ed` | S0 Start, attempt 1 | 0.1.0.dev0 | equal to baseline at `7c6d132` (later commits change only `docs/loop/`) | reading check 3 rounds closed; completeness 2 rounds; tie-break confirmed 3 items unmet this session (status line and hooks registration, checker definitions, deny rules by canary) | 0.00 |
| `loop-s03-v1` | `d65e59e` | S3 input and output formats, synthetic generators, development suite, long-range corpus, attempt 1 | 0.1.0.dev3 | loop branch after merge: main PASS 252, WARN 1, SKIP 3, FAIL or ERROR 27 of 283 (the baseline's 31 non-pass checks; new 281 and 284 pass); six side gates pass (controller gate 75 tests) | plan check, three rounds and one tie-break (2 SERIOUS confirmed narrower and fixed, 1 MINOR fixed); no CRITICAL or SERIOUS left; open items 14, 16, 17, 22 to 26 recorded | 0.00 USD instances; storage share 0.16 USD |
| `loop-s04-v1` | `87c2ff5` | S4 external benchmarks: selection, adapters, baselines, preregistration draft, attempt 1 | 0.1.0.dev4 | loop branch after merge: main PASS 254, WARN 1, SKIP 3, FAIL or ERROR 27 of 285 (the baseline's 31 non-pass checks; new 282 and 283 pass); six side gates pass (controller gate 75 tests) | plan check, three rounds, tie-break (5 SERIOUS not confirmed, 2 MINOR fixed), one post-tie-break completeness check (1 SERIOUS, an S2 regression in checks 186 to 189, and 2 MINOR, all fixed); no item open | 0.00 USD instances; storage share 0.16 USD |
| `loop-s05-v1` | `c4c2339` | S5 development runs on Lambda, reopened under D-S12 to D-S19 and closed for v1 (R2, L12b, L12c; 33 of 37 first failures pass, 4 recorded as open items 47 and 48) | 0.1.0.dev5 | loop branch after the second merge (`9b03f5c`): main PASS 267, WARN 1, SKIP 3, FAIL or ERROR 27 of 298, the non-pass set exactly the first S5 merge's; every side gate exits 0 (D-151) | three-role checkers and an attack at the close (adversarial 15: 9 SERIOUS, 6 MINOR; completeness 22; claims 14; all fixed or recorded, D-139, D-140), sweep 2 (38 found), outside audit (6 found, 4 fixed, 2 the operator's, D-149) | 63.23 by the reaper (instances 62.59); row added late, at the S7 close (sweep after D-158) |
| `loop-s07-v1` | `b2a98db` | S7 console and launchers (views of S1 to S5 data, sealed filtering, token routes, launchers to their menus, arm L; 6a, 6b for `shimmer.bat`, 6c done; 6d's draft and 6e's plain-language mode moved to S10, INC-031, D-162) | 0.1.0.dev6 | loop branch at the merge: PASS 270, WARN 1, SKIP 12, FAIL or ERROR 29 of 312, the non-pass set exactly S7's baseline at `02fae41`; every side gate exits 0 (D-162) | three rounds (round 1: adversarial 13 with 1 CRITICAL, completeness 13, claims 6; round 2: 3, 7, 12; round 3: 1 SERIOUS and 5 MINOR, 17, 8), sweep 3 (16 found), consistency check (26 found, 26 fixed); all fixed or recorded; no tie-break | 64.72 by the reaper (instances 64.01) |
| `loop-s10-v1-open` | `a12c8f8` | S10 fresh-clone test: the launcher retirement, the draft call through its own backend (INC-031), `shimmer.sh` under Git Bash (INC-030), the chat window's messages, the image's code part, no local-profile path builds a cloud client (check 313); both launchers' own installs; open: the final fresh-clone proof and baseline, the image and its container gate (D-168) | 0.1.0.dev7 | PASS 272, WARN 1, SKIP 12, FAIL/ERROR 29 of 314, equal to S10's tip set at 6f69323 apart from check 256 (it fails in every run of the traced runner and passes alone; open item 70); side gates all seven exit 0, no tracked change left | three rounds (round 1: completeness 13, adversarial 1 SERIOUS and 5 MINOR, claims 7, sweep 17, late S7 audit 4; round 2: 2 SERIOUS, 5 MINOR, 5 claims; round 3: 1 SERIOUS, 3 MINOR, 11 claims), all fixed or recorded; outside audit 3 found, 3 handled | 66.63 by the reaper |
| `loop-s11-v1-open` | `1444618` | S11 release readiness: the README and the results page read against the code, with the measured reason for the public-benchmark gap (outside audit); CITATION.cff held to VERSION (check 314); no web under the local profile (check 316); the issue deferral check (check 315, D-S24); ten v1 honesty issues fixed (D-182 to D-184); open: the image and five v1 issues | 0.1.0.dev8 | PASS 276, WARN 1, SKIP 11, FAIL/ERROR 29 of 317 (traced runner), no failure the a12c8f8 gate lacked (check 1 failed only for an empty untracked folder the cleanup had removed; with it back it skips as at a12c8f8), check 256 passing; side gates all pass (the five no-generation gates, cloud_run_checks, the controller gate with 119 tests) | three rounds (round 1: completeness 17, adversarial 6 SERIOUS and 5 MINOR, claims 9, sweep 23; round 2, one combined checker: 1 SERIOUS, 4 MINOR, 3 claims; round 3: 2 SERIOUS, 5 MINOR, 6 claims), all fixed or recorded; outside audit 2 found, 2 fixed | 66.63 by the reaper |

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
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (S3 round 3) | `e20eebf032c3b885d18fbf5239b7edd40f96548e256c1f3d50911ea381afe8dd` | 2026-10-27 18:34 +0300, loop/s03 (D-050) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S3 round 3) | `bdd31b284caa17c127a28b69223579ad41868e4a44ed351888af29ad0c4c0167` | 2026-10-27 18:34 +0300, loop/s03 (D-050) |
| `docs/INPUT_FORMAT.md` | `input-format-v1-draft` (S3 tie-break) | `47904fae96b9e692d5860467e64e553fb6a35ab140cea6f54bdafcdff76e4e36` | 2026-10-27 18:56 +0300, loop/s03 (D-051) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S3 tie-break) | `2e65a790d105a43da04ab4b2decc9488131184e2f08489cd729a5e00295c0448` | 2026-10-27 18:56 +0300, loop/s03 (D-051) |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S5: D-066 incomplete runs and D-068 model-written records on uncomputable plans; row added late, at 2026-10-29 15:34 +0300, by the restarted lead under R14) | `c00b47c884382fa8aa74c2d5e501b302f450166c43260c0551cdf8f64bf0ae9e` | changed in `d18cf93` (2026-10-29 02:29 +0300), loop/s05 (D-068) |

## The main reading agent pinned for B1 and the cut rule (preregistration section 12 item 8; S5 plan item 0.1; D-078)

| Field | Value |
|---|---|
| Agent | PROCESSOR, backend `local_producer` (the sealed local final configuration); the registry's cloud model id is used by no arm |
| Model id | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` |
| Revision | `bdd404162d94997f390efbfa660eb3f21cbbc81d` |
| Weights SHA-256 (`model.safetensors`) | `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d` |
| B1 checkpoint (item 12, D-078) | tuned: adapter checkpoint 168, SHA-256 `8354d6545272399ea6771f1a6b560309e882fd7348f5c2be9cbd1bab01160703` |
| Context | 32,768 tokens |
| Output allowance | 2,048 tokens (`pipeline PRODUCTION_MAX_TOKENS`) |
| Decoding policy | `tuning/producer_v3/evaluation_protocol.json`, SHA-256 (LF) `51da77c94497ef74b5f913901c20abbe965101dbbb950cb0d5b62b4c16b3cc1a` |
| Attention and prefill (item 13, D-063) | sdpa pinned to the memory-efficient backend, prefilled in one shot |
| Recorded | 2026-10-29 15:34 +0300, loop/s05, before any holdout sample |
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S5: the reply record `context` row, D-078) | `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150` | 2026-10-29 16:06 +0300, loop/s05 (D-078) |

## Preregistration frozen (S5 item 10f, D-085)

| Item | SHA-256 | Recorded |
|---|---|---|
| `docs/benchmarks/PREREGISTRATION.md` (frozen; LF-normalised) | `f759527572ab7c9eca8bad2a5d8fd9100281387e5834a28c0b217d43f2f033f7` | 2026-10-29 22:09 +0300, loop/s05 at `fc02e1d`, before any holdout sample |
| C's scorer (C0 run 3, the last; `c-scorer-c0-3`; hash of SCORER_MANIFEST.txt) | `049ae32b1a837e9bc4ecaf1947e32da19d465422ac845eec1641b9dd864b2a7f` | 2026-10-29 22:09 +0300, from `_handoff/C_SCORER.json` |
| `docs/OUTPUT_FORMAT.md` read by C0 (draft `output-format-v1-draft`) | `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150` | 2026-10-29 22:09 +0300 |
| `docs/INPUT_FORMAT.md` read by C0 (draft `input-format-v1-draft`) | `47904fae96b9e692d5860467e64e553fb6a35ab140cea6f54bdafcdff76e4e36` | 2026-10-29 22:09 +0300 |
| `ROLE_C0.md` (runs 1 to 3, the same text) | `5804490377df6ec9932744c8af022c2969bf4867c333e01df8f638ce2a6b861d` | 2026-10-29 22:09 +0300 |

## Corrections (appended; rows above are never moved or edited)

Note (2026-10-29 about 23:10 +0300, S5 checker round 2, D-087): the `docs/OUTPUT_FORMAT.md` row of 2026-10-29 16:06 +0300 (`07eea8f7...4150`, D-078) was written by mistake inside the reading-agent table, after its "Recorded" row. At S5 checker round 1 it was moved into the frozen-hashes table, which broke this file's append-only rule; it is now back where it was first written, unchanged, and the row below records it again in the table it belongs to. Nothing in the row itself was wrong.

| What | Version | SHA-256 | Recorded |
|---|---|---|---|
| `docs/OUTPUT_FORMAT.md` | `output-format-v1-draft` (S5: the reply record `context` row, D-078; a format hash, recorded again here in a format-hash table) | `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150` | first recorded 2026-10-29 16:06 +0300, loop/s05 (D-078); this row 2026-10-29 about 23:10 +0300 (D-087) |

## Preregistration version 2 frozen (D-S12 item 5, D-095)

Version 1's rows above stay as they are. From this freeze, version 2's hash is the one S8 checks, and the scorer hash below replaces `049ae32b...` as the one B and C2 use.

| Item | SHA-256 | Recorded |
|---|---|---|
| `docs/benchmarks/PREREGISTRATION.md` version 2 (frozen; LF-normalised) | `0c1884fb3ec0d4373af750874da57c14d164ade4b0a0bf7bca0478e92a332dc3` | 2026-10-30 01:03 +0300, loop/s05 at `aee36aa`, before any holdout sample (checked 01:02:39: the shared hand-off folder holds only B-dev's, C0's and S0's files; the ledger holds development launches only; no S8 branch) |
| C's scorer (C0 run 4, the first on version 2; `c-scorer-c0-4`; hash of SCORER_MANIFEST.txt) | `2df0a673d45db03ca85c1a20a1a70ffc79056506df48c0a55b5c120702da1a8c` | 2026-10-30 01:03 +0300, from `_handoff/C_SCORER.json` |
| `docs/OUTPUT_FORMAT.md` read by C0 run 4 (draft `output-format-v1-draft`, unchanged) | `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150` | 2026-10-30 01:03 +0300 |
| `docs/INPUT_FORMAT.md` read by C0 run 4 (draft `input-format-v1-draft`, unchanged) | `47904fae96b9e692d5860467e64e553fb6a35ab140cea6f54bdafcdff76e4e36` | 2026-10-30 01:03 +0300 |
| `ROLE_C0_4.md` (run 4; the sections of run 1 to 3's text plus Annex D's D-S12) | `e3dc763fc1309f699f23ff21b5a31b68f1d85c66c0408afe8893d3f60a2fed25` | 2026-10-30 01:03 +0300 |

| `docs/INPUT_FORMAT.md` (draft `input-format-v1-draft`; only the repository scorer's sentences changed, D-098) | `5a0400fa9532bf69addd7ef71833e961f262032e98b0811065f184fc72c8a463` | 2026-10-30 02:3x +0300, loop/s05 at `260d466`; C0 run 4 read `47904fae...` |
| `docs/OUTPUT_FORMAT.md` (draft `output-format-v1-draft`; additions the scorer does not read, D-101) | `e81010ee8e72c2d288e5cbedc68fc2021e92acac15fff9d2c7bd7d8879fb0654` | 2026-10-30 12:1x +0300, loop/s05 at `9b62469`; C0 run 4 read `07eea8f7...` |
| `docs/OUTPUT_FORMAT.md` (draft; the multi-round record lines corrected to Python-written, D-103, D-107; the scorer reads none of them) | `17f326b02aa48851735788190a238de88ef97521a68aba8388d29c43d03ccc20` | 2026-10-30 12:3x +0300, loop/s05 |
| `docs/INPUT_FORMAT.md` (draft; a multi-round run's records computed in Python, the two-models rule only in the decision-support modes; S11 lane, D-171) | `8ffb417df32bb59f0e93f8aeec47863e67104dc094a38772d3724af335a849f4` | 2026-11-01 23:30 +0300, loop/s11 |
| `docs/OUTPUT_FORMAT.md` (draft; server statuses, exit codes 2 and 4, result reasons and report rows, B1 and b3_only batches, the scorer's twin and multi-round support described as the code writes them; S11 lane, D-171) | `047fb0a4e1aba7d02ab5ca5389227df16c2e6957a52a380c7562914d50a8e129` | 2026-11-01 23:30 +0300, loop/s11 |
| `docs/INPUT_FORMAT.md` and `docs/OUTPUT_FORMAT.md` put back byte for byte to `cf19d5d` (D-172): input `5a0400fa9532bf69addd7ef71833e961f262032e98b0811065f184fc72c8a463`, output `17f326b02aa48851735788190a238de88ef97521a68aba8388d29c43d03ccc20`; the two rows above name hashes no tracked file has | | 2026-11-02 00:14 +0300, loop/s11 |
| `docs/INPUT_FORMAT.md` (correction appended to the row above: the hash in its column; it supersedes `8ffb417d...`, the S11 lane's row of 1 November) | `5a0400fa9532bf69addd7ef71833e961f262032e98b0811065f184fc72c8a463` | 2026-11-02 00:50 +0300, loop/s11, D-174 |
| `docs/OUTPUT_FORMAT.md` (correction appended to the row above: the hash in its column; it supersedes `047fb0a4...`, the S11 lane's row of 1 November) | `17f326b02aa48851735788190a238de88ef97521a68aba8388d29c43d03ccc20` | 2026-11-02 00:50 +0300, loop/s11, D-174 |
