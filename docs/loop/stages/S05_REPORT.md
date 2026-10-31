# S5 report: development runs on Lambda

Stage S5 of the autonomous loop of 27 October 2026, on branch `loop/s05`, created from the loop branch at `ea1c0d5` (S2, S3 and S4 merged and tagged). The lead worked in `.claude/worktrees/s05-lead`. Opus, medium effort from 28 October 2026 (Annex D, D-S11). Every run in this stage is a development run on exposed material (Annex B.1): every analyser report carries the purpose on line 1 and "Exposed test, development only." on line 2. Two things are noted apart under "Purpose line" below: the session-level review appendices (`RUN_REPORT.md` of L2, L3e, L4a, L4b and L5v, which are not analyser reports), and L6, which has no analyser report because the operator stopped the laptop at 18:15 +0300 and its end-of-session inventory was never written. The lead session changed once: session 757d835b led S5 until it stopped at 05:11 +0300 on 29 October after an automatic compaction; session f3d23d40 took the released lock at 11:00 +0300 and ran a restart check (14 items, D-071, D-072). The operator stopped the laptop once, at about 18:15 +0300 on 29 October (D-079). On the branch, counted at `7c74028` (the loop/s05 tip when checker round 1's records were written, the commit of this report): 91 commits after `ea1c0d5`, 77 files changed, 14,378 lines added and 458 removed (`git rev-list --count ea1c0d5..7c74028`, `git diff --shortstat ea1c0d5..7c74028`). The checker-round commits after `7c74028` change only records and are not in these counts.

## What was done

### Launches (all A10 in us-east-1 at 1.29 USD an hour, read live; all asset copies MATCH from L1 on)

| Launch | Content | Forecast (USD) | Actual minutes | Actual (USD) | Outcome |
|---|---|---|---|---|---|
| L1 | smoke: the clinical sheet | 1.54 | 23 | 0.49 | first measured MATCH (no 37-minute upload); execution passed |
| L2 | ContraDoc 5, SciTab 5, B3 then B1 (five passes) | 5.62 | 148 | 3.18 | every B3 entry failed (out of memory once, a crash, eight semantically incomplete); every B1 entry passed |
| L3e | the E evidence run (D-061, D-062) | 2.77 | 157 | 3.38 | E missed its declared threshold; option A adopted (D-063) |
| L4a | ContraDoc 2, SciTab 2, ContractNLI merged 1, B3 under A, B1 base and tuned | 6.04 | 121 | 2.60 | no out-of-memory; B3 semantically incomplete; B1 passed |
| L5v | D-068 verification: the clinical sheet and the device-log pair, B3 only | 1.27 (1.258 unrounded; actual 104 percent of it) | 61 | 1.31 | D-068 kept (D-070), see the limitation below item 8 |
| L4b | ContractNLI merged band A and band B, FinDVer band D, B3 and B1 | 7.60 | 204 | 4.39 | band B refused at 6.8 minutes (INC-019, fixed by D-076); B1 full-length memory fits (D-063 point measured) |
| L6 | the five L4a documents under D-068, ContractNLI band B under D-076, the synthetic and the negotiation multi-round cases, B3 only | 6.96 | 174 | 3.74 | entries 1 to 6 done (ContractNLI band B completes under D-076 in 81.8 minutes); the operator stopped the laptop at 18:15 +0300 during entry 7; the cleanup terminated the instance (D-079) |
| L6s | ContractNLI span parts on one agreement, ended by the workload stop | 1.40 | 0 | 0.00 | never launched (the 18:15 stop); resealed as L6s2 after the hidden-window change (D-079) |
| L6m | the two multi-round cases, resealed after D-079, B3 only | 2.78 | 46 | 0.99 | both cases refused at the multi-round phase (INC-023); round 2 of the synthetic case reused 8 of 11 units (D-082) |
| L6s2 | the L6s bundle resealed at `ee8fa6a` | 1.40 | 26 | 0.56 | span-part B3 run out of GPU memory after 9.1 minutes of workload; trigger undecided, merged-part route applies (D-083) |

S5 spend: 20.64 USD of 24 (ledger; L1 0.49, L2 3.18, L3e 3.38, L4a 2.60, L5v 1.31, L4b 4.39, L6 3.74, L6m 0.99, L6s2 0.56). 3.36 USD is unused and is the only money S6 may spend (IV.3, D-083). No overrun reached the reserve.

After the reopening (D-S12 to D-S18): S5 spend is 60.89 USD of instances in all by the ledger's terminations (20.64 before D-S12, then L11 4.11, L7 1.38, L10 2.69, L8 5.83, R1 2.06, L12 13.12, R2a 2.69, R2b 0.60, R2c 1.51, L12b 6.28: 40.25 after D-S12), against the D-092 and D-115 allocations and, from D-133, the D-S18 order (v1 work, the parallel track 30, the sealed evaluation at least 60, the moved steps). The 3.36 USD sentence above is the first close's and is superseded by the 200 USD budget (D-091). The reaper reading at the close and BUDGET.md's S5 closing line are in "Stage boundary".

### Items of the S5 specification

1. **Smoke run (L1).** Every model reply saved (`audit/model_replies/`, outcomes appended), the honest deliverables, the 11.12 report fields, the budget guard, the ledger lines and the `shimmer-loop-` name, and the asset copy: MATCH, measured, so later forecasts dropped the upload (overhead 15.4 minutes measured against 48.3 with the upload).
2. **First real multi-round run (L6m).** The synthetic family 4 case of three rounds (`f4_s4103_vqjj`) and the negotiation case of three offers (anonymised material only, H6), B3. In L6 the synthetic case was in its archive check at the 18:15 stop; both ran in L6m. Both reached the multi-round phase with activation `activated` and were refused there (`agent_output_unavailable`, pipeline exit 8): the phase's reading-agent call got a 15,795-token prompt and ran to its 4,096-token cap in 944 seconds, outside the two-turn shape the checkpoint was evaluated on (INC-023). `audit/round_reuse.json` of the synthetic case: round 1 computed 11 units, round 2 reused 8 and computed 3 (the do-not-recompute rule holds on real execution), round 3 computed all 11 (why every unit counted as changed in round 3 is not yet read; it is to be read in S6a, open item 35). The health criterion (outcome `reviewed`) is not met: deferred to S6a with open item 35 (D-082, P9 b).
3. **Regression on the existing exposed tests.** The clinical sheet (L1, L5v) and the device-log flawed document and clean twin (L5v) on current code, scored with `tools/score_corpus.py`: clinical location 5 of 5, reason confirmed 4 of 5, false positives 0 (L5v); device log location 3 of 10, reason confirmed 2 of 10, false positives 0; clean twin false positives 0. These false-positive counts are counted by the scorer over amendments only, so they cannot show a false alarm made by a model-written record: the clean twin's model-written records and model-only relations are in the limitation below item 8 (open item 36). The catalogue test and both negotiation comparisons were cut by the spend order (D-077, P9 b; FOR_SECKIN.md).
4. **The development suite.** B3 on the suite was cut (D-073). B2 ran every bundle on the laptop at no cost (84 bundles, 0 failures; location and reason-confirmed recall: family 1 tests 24 of 28, probes 92 of 112; family 2 24 of 36, 90 of 144; family 3 22 of 22, 80 of 88; family 5 22 of 22, 82 of 88; family 6 22 of 26, 88 of 104; 0 false positives on every bundle; every twin 0). Family 4 (multi-round) is not measurable by B2 (R4, open item 28). The scorer's twin comparison cannot read a B2 run (open item 32).
5. **Adapter dry runs and baseline proofs.** On current code (after D-068): ContraDoc 2, SciTab 2, ContractNLI 3 merged agreements, FinDVer 1, CUAD 0 (D-073), below five documents per benchmark (a recorded cut, P9 b). L6 re-measured B3 on the five L4a documents under D-068 and on ContractNLI band B under D-076. L2's ten documents ran under earlier code and count for cost only. B1 ran on every dry-run item with both checkpoints; at full length on FinDVer it fits (18.6 and 20.9 GiB allocated of 24) but gave no parseable label. B2 ran on every built development bundle on the laptop. Labels and the official metrics are computed by the adapters on development items only (`external/s05/labels/`, ignored).
6. **Fix and re-run.** INC-011 to INC-023 (private). Product fixes in S5: D-061 (general fixes from L2), D-063 (sdpa one shot for the producer and B1), D-066 (scoring a semantically incomplete run), D-068 (model answers on uncomputable plans kept as model-written records; verified by L5v, D-070), D-076 (a phase above the scheduler bound runs as waves; INC-019; re-run in L6), D-078 (adapters: section 5.3's over-context exclusion with S-7, the rule-id map adopted), D-079 (every child process on the controller path starts with no window; check 292). Test-infrastructure: checks 229 and 233 (INC-017), check 222 restores the launcher byte for byte (INC-022). Not fixed in S5: INC-023 (open item 35).
7. **Diagnostics.** (a) The clean twin draws more records than the flawed document because the model answers uncomputable plans (D-068 path), not because of a computed finding: in L5v the twin has 0 Python records and 10 model-written records (8 of them answers kept under D-068, of 32 judging calls), all marked and none an amendment. (b) Empty extractions: the compact extraction contract accepts a claim only by an id written in the span, and no real document carries one, so every reply that wrote a claim was refused (open item 30). (c) The classifier gave one label on the clinical sheet because every extraction it saw was empty; it is not a classifier fault. (d) Check 232's two items verified on saved replies: the deepening cap holds (never reached: at most one finding per run) and every amendment keeps its typed record (10 of 10). Side finding: amendments with no REF id raise validator errors (open item 31).
8. **Model-text review** (sample fixed before reading; correct, partly, wrong, empty, unverifiable): L1 1, 2, 7, 0, 0; L2 1, 9, 6, 4, 0; L3e 3, 1, 7, 2, 2; L4a 1, 3, 10, 1, 0; L5v 0, 3, 11, 0, 1; L4b 2, 2, 10, 1, 0; L6 1, 3, 11, 0, 0 (15 of 584 reply records; all three answers kept under D-068 were wrong: a sum relation on a unit with no figures, open item 34; L6 has no analyser report, so its verdicts live in its `MODEL_TEXT_REVIEW.md`); L6m 0, 2, 0, 0, 0 (both replies truncated at the output cap); L6s2 4, 0, 2, 4, 0 (D-086). The repeated pattern: the base PRACTICE_AUDITOR model answers VIOLATION on units that do not address the rule and ignores a rule's instruction to answer UNCERTAIN; under D-068 those answers are kept as model-written records, and the benchmark reader lets a model record decide an item, so B3 carries model-driven false flags. B3 is therefore also reported without model-written records (sensitivity S-8, D-080). The tuned B1 replies quote the source and were right or nearly right in the samples. **Seed deviation (D-080):** the plan derives each seed as int(SHA-256 of "<run folder name>:text-review") mod 2^63. The rule's value for the L4a folder name, which the L6 session folder shares, is 876901642167781849. L4a's recorded seed (6304522431124753139) came from the previous lead session (757d835b), and how it was derived is not recorded. The L6 review reused L4a's seed by the current lead's error, not by a choice. Both samples were fixed and recorded before any record was read, so each is a seeded random sample; they are kept, not redrawn (D-080, D-086).

**Limitation the S8 report must carry (S5 checker round 1, D-086; bound forward by open item 36 and D-087).** D-069's acceptance test for D-068 could not fail on the thing it was meant to catch: it asked whether a D-068 record on the clean twin was scored as a false positive, but `tools/score_corpus.py` counts false positives over amendments only, and a D-068 record is never an amendment, so the criterion was blind to D-068 records. Read by the benchmark reader instead (which lets a model-written record decide an item), the clean twin in L5v carried 10 model-written records (8 answers kept under D-068, of 32 judging calls) and 20 model-only relations (missing_field 11, sum_mismatch 9; D-070), each a false alarm on a document with no planted flaw, and the L6 review found all 3 sampled kept answers wrong. D-070's "verified" therefore means only that clinical recall did not fall and that no amendment changed; it does not show that D-068 records are right. Sensitivity S-8 (B3 and B4 with every model-written record absent, D-080, DEV-012) is the control for this. The frozen preregistration is not edited; the S8 report states this limitation beside the primary B3 result.
9. **Measurements.** Tables below.
10. **C0 and the frozen preregistration.** Section 12 settled from development outputs (D-078): the main reading agent pinned in VERSIONS.md, the rule-id map adopted, B1's checkpoint tuned by the written rule, B1 at full length fits, and item 14 (section 5.3's exclusion, now applied by the adapters). The B1 checkpoint rule read development scores (the parse rates tied, and the pooled development headline broke the tie), and D-066 settled how a semantically incomplete run is scored after B1 development scores already existed; both are disclosed (D-066, D-078, DEVIATIONS.md). CUAD (D-073) and FinDVer (D-078) left the S8 priority list; ContractNLI, SciTab and ContraDoc stay on the list, but S8 has one external benchmark, the ContractNLI pilot, plus B's three synthetic tests (D-081). Section 2 filled by the S4e item 2 rule (D-081): B's synthetic tests first (about 10.4 USD), then ContractNLI as a pilot of 12 to 13 documents; SciTab and ContraDoc get no sample. The span-part trigger is undecided and merged parts apply (D-083, DEV-013). Sensitivity S-8, B3 and B4 without model-written records (D-080, DEV-012). The final attack (D-084): a fresh checker, 1 CRITICAL, 7 SERIOUS, 7 MINOR, every item closed before the freeze; B's synthetic tests got preregistered scoring and an adapter, and one setup-failure rule covers B1 and B3. C0: run 1 agreed on every label set it could check; run 2 (with the B2 run folders run 1 lacked) agreed fully on ContractNLI, ContraDoc and SciTab, primary and S-1 to S-8; run 3, the last allowed, on the preregistration at `fc02e1d`, agreed fully on ContractNLI (476 items), ContraDoc (62) and SciTab (198), primary and S-1 to S-8, and on B's synthetic scoring (309 items) (D-085). Freeze at `1392d00`, recorded in VERSIONS.md: preregistration SHA-256 `f759527572ab7c9eca8bad2a5d8fd9100281387e5834a28c0b217d43f2f033f7`; C's scorer `049ae32b1a837e9bc4ecaf1947e32da19d465422ac845eec1641b9dd864b2a7f`; `docs/OUTPUT_FORMAT.md` read by C0 `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150`; `ROLE_C0.md` `5804490377df6ec9932744c8af022c2969bf4867c333e01df8f638ce2a6b861d`. DEVIATIONS.md holds DEV-001 to DEV-020. Section 4's smallest detectable difference cannot be computed from two or three development documents per benchmark; it is computed from the holdout sample.

   **C0 inputs (from each input folder's `MANIFEST.json`; the three manifests are kept, byte for byte, in the private records as `docs/loop/private/c0_manifests/c0_run1.json`, `c0_run2.json` and `c0_run3.json`, whose SHA-256 values are the manifest hashes below; counts only).** Each folder held the preregistration, `docs/OUTPUT_FORMAT.md` (SHA-256 `07eea8f7...4150` in all three), the three metric texts (`METRIC_contractnli.md`, `METRIC_contradoc.md`, `METRIC_scitab.md`), the adapters' development labels (`adapter_labels/`, 94 files in 3 benchmark folders) and the run outputs (`outputs/`). Run 1 (manifest SHA-256 `4717aec0...ac8b`): preregistration SHA-256 (LF) `90e91e5c...e2ef`; 137 run folders in 47 groups: B1 ContractNLI 6, ContraDoc 33, SciTab 29; B2 15 per benchmark (5 documents, 3 folders each); B3 ContractNLI 5, ContraDoc 10, SciTab 9; `outputs/` 1,843 files. Run 2 (manifest `2b1873f8...53de`): the same preregistration hash (`90e91e5c...e2ef`); 127 run folders in 41 groups: B1 and B3 as run 1; B2 as the laptop run, the L4a subset and the second dry-run work folder (ContractNLI 11, ContraDoc 12, SciTab 12), the B2 run folders run 1 lacked; `outputs/` 2,018 files. Run 3 (manifest `2e163127...74f1`): the frozen preregistration hash `f7595275...33f7` (`fc02e1d`); the same 127 run folders as run 2; added `docs/INPUT_FORMAT.md` (`47904fae...6e4e36`), `DEVIATIONS.md`, `SYNTHETIC_README.md` and `synthetic/` (870 files: the development suite, 10 tests, 60 bundles, 60 B2 run folders, 288 items, the 4 family 4 tests excluded; L5v, 3 tests, 3 keys, 3 B3 run folders of 186 files, 21 items; 55 synthetic adapter commands, 0 failed). Runs 1 and 2 carried a draft preregistration (`90e91e5c...`), run 3 the frozen one.

   **C0 hash records (S5 checker round 3, D-088).** After each C0 run the lead read `_handoff/C0_PREREG_SHA256.txt`, the preregistration hash C0 wrote: run 1 `90e91e5c...e2ef` (expected `90e91e5c...e2ef`), run 2 `90e91e5c...e2ef` (expected the same), run 3 `f7595275...33f7` (expected the same, the frozen hash); all three matched. The exit code of each C0 process was not captured: the start scripts kept no process handle. Each process was seen to end, and `_handoff/C0_DONE.json` said `completed` each time.

### Item 9: measurements (development, exposed; one run each)

Sources: billed minutes and cost from the ledger (`BUDGET.md`); workload minutes from each entry's `batch_workload_<n>_timing.json` (or `ordinary_workload_timing.json` for a single bundle); peak GPU memory in use and peak process memory from each B3 entry's `logs/model_telemetry.jsonl` (decimal GB); B1 peak allocated memory from `b1_summary.json` (GiB); reply records counted in `audit/model_replies/` (`.json` files; `outcomes.jsonl` not counted). L6m and L6s2 were extracted and analysed at checker round 1 (analyser reports of 2026-10-29 22:30 +0300); their figures come from each entry's `analysis/model_telemetry_summary.json` (peak `vram_used_bytes` and `process_rss_bytes`, the same measures as the other rows).

**Per launch.**

| Launch | Billed min | Workload min (all entries) | Billed minus workload | USD | Peak GPU memory, B3 (GB) | Peak process memory, B3 (GB) | B3 reply records |
|---|---|---|---|---|---|---|---|
| L1 | 23 | 7.6 | 15.4 | 0.49 | 16.5 | 7.2 | 20 |
| L2 | 148 | 103.1 (B3 43.7, B1 59.4) | 44.9 | 3.18 | 23.6 (entry 00, out of memory) | 7.8 | 124 |
| L3e | 157 | 137.6 (FinDVer B1 did not start) | 19.4 | 3.38 | 11.6 | 7.0 | 456 |
| L4a | 121 | 89.2 | 31.8 | 2.60 | 16.5 | 5.1 | 262 |
| L5v | 61 | 38.8 | 22.2 | 1.31 | 18.0 | 7.3 | 153 |
| L4b | 204 | 178.2 | 25.8 | 4.39 | 22.4 (the refused band B entry) | 7.0 | 603 |
| L6 | 174 | 150.5 (entries 1 to 6) | 23.5 | 3.74 | 22.4 | 6.8 | 584 |
| L6m | 46 | 29.6 (16.2 and 13.4) | 16.4 | 0.99 | 16.3 | 1.5 | 2 (one per case) |
| L6s2 | 26 | 9.1 | 16.9 | 0.56 | 23.3 (out of memory) | 5.4 | 105 |

Billed minus workload is the session overhead plus each entry's transfers and checks. B3 judging calls on ContractNLI: about 12.5 seconds a call (L4a, D-073) and 14.6 seconds a plan (L4b, D-077).

**Controller phases per launch** (minutes, summed over the session and its entries from every `<phase>_timing.json`; a phase's `_start` and `_collect` sub-steps are inside it and not added again; sums of unrounded seconds, so the workload can differ from the table above by up to 0.3 minutes). Setup is the archive integrity hash, payload extract, environment, dependency closure, pinned wheels and the GPU and directory checks. Per-entry checks are each batch entry's transfer, extract, integrity, park, evidence pack, hash and download. The rest of the billed time is boot, SSH and termination, which no phase file times.

| Launch | Support transfer | Asset copy probe and use | Setup | Workload | Per-entry checks | Stop and collection | Sum of phases | Billed minus sum |
|---|---|---|---|---|---|---|---|---|
| L1 | 1.1 | 3.5 | 2.7 | 7.6 | 0.0 | 0.7 | 15.7 | 7.3 |
| L2 | 0.6 | 3.5 | 2.7 | 102.8 | 30.4 | 0.7 | 140.8 | 7.2 |
| L3e | 0.9 | 3.4 | 2.9 | 137.6 | 4.3 | 0.8 | 149.9 | 7.1 |
| L4a | 1.0 | 3.3 | 3.0 | 89.2 | 16.9 | 0.8 | 114.1 | 6.9 |
| L5v | 1.3 | 4.3 | 3.0 | 38.8 | 4.6 | 0.8 | 52.9 | 8.1 |
| L4b | 0.6 | 4.9 | 2.8 | 178.3 | 8.8 | 0.7 | 196.1 | 7.9 |
| L6 | 0.8 | 2.6 | 2.9 | 150.5 | 9.9 | 0.3 (no session collection: stopped) | 167.1 | 6.9 |
| L6m | 0.6 | 3.3 | 2.6 | 29.7 | 1.8 | 0.7 | 38.6 | 7.4 |
| L6s2 | 0.6 | 3.2 | 2.6 | 9.1 | 0.0 | 0.6 | 16.2 | 9.8 |

**Pipeline phases in B3** (minutes, summed over a launch's B3 entries, from the recorded `phase_latencies` in each entry's telemetry summary; L6 from the downloaded run folders, since L6 has no analyser output). Phases before 3 (start, ingestion, roles) are not recorded as phase latencies.

| Launch | B3 entries | 3-4 content production | 5 audit | 5.5 convention review | 6 synthesis | 6.5 editorial review |
|---|---|---|---|---|---|---|
| L1 | 1 | 4.1 | 1.7 | 0.2 | 0.0 | 0.5 |
| L2 | 10 | 28.9 | 2.0 | 4.3 | 0.1 | 2.1 |
| L3e | 2 | 48.7 | 1.8 | 57.6 | 0.0 | 0.5 |
| L4a | 5 | 12.4 | 2.0 | 47.6 | 0.0 | 1.4 |
| L5v | 3 | 16.3 | 3.2 | 15.4 | 0.0 | 1.3 |
| L4b | 3 | 45.9 | 3.4 | 80.3 | 0.0 | 0.7 |
| L6 | 6 | 16.4 | 3.8 | 122.6 | 0.1 | 2.1 |
| L6m | 2 | none recorded: both cases refused at the multi-round phase | | | | |
| L6s2 | 1 | 6.9 | 0.9 | not recorded (the run ended out of GPU memory) | not recorded | not recorded |

Phase 5.5 (the judging calls on uncomputable plans, D-068) is the largest line from L3e on.

**Model calls by agent in B3** (telemetry `model_call` rows in each entry's `logs/model_telemetry.jsonl`; B1 is outside the pipeline and makes one call per item per checkpoint). Others: ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER, LEGAL_ANALYST, VERIFIER and EDITOR_CLERK together.

| Launch | EMBEDDING | PROCESSOR | PRACTICE_AUDITOR | AUDITOR896 | Others | Total |
|---|---|---|---|---|---|---|
| L1 | 30 | 4 | 1 | 7 | 8 | 50 |
| L2 | 141 | 29 | 19 | 12 | 64 | 265 |
| L3e | 18 | 107 | 175 | 160 | 14 | 474 |
| L4a | 161 | 14 | 198 | 16 | 34 | 423 |
| L5v | 119 | 24 | 75 | 31 | 23 | 272 |
| L4b | 188 | 116 | 293 | 172 | 22 | 791 |
| L6 | 251 | 23 | 487 | 32 | 42 | 835 |
| L6m | 0 | 2 | 0 | 0 | 0 | 2 |
| L6s2 | 71 | 37 | 0 | 61 | 7 | 176 |

**B1 seconds per call** (B1 entry minutes over both checkpoints' calls, model load included, so an upper bound): ContractNLI 15.2, 12.9 and 16.8 seconds (17 items, 34 calls each); SciTab 42 and 39; ContraDoc 36 and 42 (one or eight items, load dominates).

**Disk.** Recorded: the sealed asset archive, 13,149,972,480 bytes (13.1 GB) at every launch (`assets_transfer_archive.json`); the instance's free disk at hardware admission, about 1,410 GB (`hardware_admission.json`); and the run folder each B3 entry wrote, as downloaded (largest entry): L1 0.9 MB, L2 0.8, L3e 20.4, L4a 10.8, L5v 3.3, L4b 20.4, L6 17.8, L6m 0.6, L6s2 2.4; collected evidence archives per launch together: L1 1.3 MB, L2 24.9, L3e 15.2, L4a 13.7, L5v 5.7, L4b 14.0, L6 11.8, L6m 3.5, L6s2 1.5. Not recorded: the peak disk in use on the instance during a run (environment, wheels, model cache and run folder together); D-086 recorded it under P9 (e), corrected at checker round 3 to reason (b), bound to S6 by open item 37 (D-088).

**Per document, current code** (B3 from L6, ContractNLI band A from L4b; B1 from L4a and L4b, both checkpoints in one entry). Minutes per document as preregistration section 2 counts them: B3 plus half the two-checkpoint B1 entry (tuned only) plus about 2 minutes per batch entry for each arm. USD at 1.29 USD an hour, without the 1.3 margin and without session overhead.

| Benchmark | Band | Document | B3 min | B3 peak GPU (GB) | B1 min (two checkpoints) | B1 peak, tuned (GiB) | Min per document | USD per document | Decisions | USD per decision |
|---|---|---|---|---|---|---|---|---|---|---|
| ContractNLI (merged) | A | `e42dff968be2` | 28.9 | 12.4 | 8.6 | 8.42 | 37.2 | 0.80 | 17 | 0.047 |
| ContractNLI (merged) | B | `04f58368963d` | 51.3 | 17.0 | 7.3 | 8.76 | 59.0 | 1.27 | 17 | 0.075 |
| ContractNLI (merged) | B | `5db65ebc6ba5` | 81.8 | 22.4 | 9.5 | 9.21 | 90.6 | 1.95 | 17 | 0.115 |
| SciTab | A | `406b855fc91c` | 2.4 | 10.5 | 1.4 | 7.61 | 7.1 | 0.15 | 1 | 0.15 |
| SciTab | A | `f0ed2e1a4be4` | 4.7 | 11.6 | 10.4 | 8.04 | 13.9 | 0.30 | 8 | 0.037 |
| ContraDoc | A | `c7f1d5f10f35` | 3.8 | 11.2 | 1.2 | 7.77 | 8.4 | 0.18 | 1 | 0.18 |
| ContraDoc | B | `077164cc8a97` | 6.5 | 12.7 | 1.4 | 8.55 | 11.2 | 0.24 | 1 | 0.24 |
| FinDVer (left the list) | D | `e61777d6327c` | 97.7 (void, section 5.3) | 10.8 | 26.7 | 20.86 | not computed | not computed | not computed | not computed |

Minutes per scored decision (section 2's second key): SciTab 2.3, ContraDoc 9.8, ContractNLI 3.7 (D-081). A band with no measured document is not measured; at S8c it takes the highest measured band's minutes (section 2, "Sizing from S5"). (Dated note, 2026-10-30, D-093: that holds for a band with development documents but no measured one; a band with no development document follows the preregistration's clarification 4, scaled by median words, which gives ContractNLI's band C about 270.7 minutes in version 2.) CUAD: not measured (D-073).

**Exposed tests (L5v, B3 workload minutes):** clinical sheet 6.1, device log 17.2, clean twin 15.5; about 15 minutes a bundle with its entry (D-073). Cost per verified finding (findings that pass the scorer with reason confirmed): L1 0.49 USD over 4, about 0.12 USD; L5v 1.31 USD over 6 (clinical 4, device log 2), about 0.22 USD. For the benchmarks (correct FLAG items) it is not recorded: S5 computed no development score for that purpose (D-086 recorded P9 e; corrected at checker round 3 to reason (c), bound to S8 by open item 40, D-088). The time in the pipeline's phases before phase 3 and the L6m phase latencies are bound the same way: open item 38 (S6, reason c) and open item 39 (S6a, reason b).

### Purpose line (Annex B.1)

Every analyser report of an S5 launch has the purpose on line 1 (`Purpose: <purpose>`) and "Exposed test, development only." on line 2: checked on all 47 analyser reports (L1; every batch entry of L2, L3e, L4a, L5v and L4b; the L6m session and its two entries; L6s2; L6m and L6s2 analysed at checker round 1). The reading recorded (D-086): two lines at the head of the report satisfy Annex B.1's "at the top". S5's own text asks for more: "Every report's first line states its purpose (Annex B.1) and 'exposed test, development only'." That sentence is met by the same reading: lines 1 and 2 together are the report's first line in the sense the sentence uses (its head, before any content), so the purpose and the exposed statement sit apart on lines 1 and 2 rather than on one line. This is recorded as a reading under P2 (allowed and recorded visibly; it guards no hard limit, role boundary, person's data or money), not as a departure (S5 checker round 3, D-088). One gap found in the check: the session-level `RUN_REPORT.md` of the batch launches L2, L3e, L4a, L4b and L5v is not an analyser report; it holds only the model-text review section (written by the review step, the full review being `MODEL_TEXT_REVIEW.md` beside it) and has no purpose line. The purpose and exposed lines of those launches are in each entry's report. L6 has no analyser report: it was interrupted by the 18:15 stop before its session collection (D-079); its entries' evidence is used from the downloaded run folders.

### Usage at each launch (launch gate: five-hour below 70 percent, seven-day below 95 percent)

| Launch | Launched (+0300) | Five-hour (percent) | Seven-day (percent) | Read at (UTC) | Source |
|---|---|---|---|---|---|
| L1 | 28 Oct 12:51 | 6 | 1 | 28 Oct 09:51, in the command that started the controller; reaper's last run 09:46:59 | the previous lead's session transcript (S5 checker round 2); the handoff `HANDOFF_20261028-1231.md` holds the earlier 09:31 reading (2 and 1) |
| L2 | 28 Oct 14:53 | 13 | 4 | 28 Oct 12:23, in the command that started the controller; reaper's last run 12:22:00 | the previous lead's session transcript (S5 checker round 2); the handoffs `HANDOFF_20261028-1345.md` to `HANDOFF_20261029-0417_state.md` repeat the 09:31 UTC reading unchanged |
| L3e | 28 Oct 19:24 | 10 | 8 | 28 Oct 16:24, in the command that started the controller; reaper's last run 16:22:00 | as L2 |
| L4a | 28 Oct 23:19 | 10 | 12 | 28 Oct 20:19, in the command that started the controller; reaper's last run 20:17:00 | as L2 |
| L5v | 29 Oct 03:04 | 6 | 15 | 29 Oct 00:12, 9 seconds before the command that started the controller; reaper's last run 00:11:59 | as L2 |
| L4b | 29 Oct 11:38 | 2 | 16 | 29 Oct 08:37 | the current lead's session |
| L6 | 29 Oct | 15 | 20 | 29 Oct 12:21 | the current lead's session |
| L6s | not launched | | | | |
| L6m | 29 Oct | 8 | 23 | 29 Oct 16:30 | the current lead's session |
| L6s2 | 29 Oct | 10 | 23 | 29 Oct 17:18 | the current lead's session |

Every reading is far below both limits. Correction at S5 checker round 2 (S2, D-087): the previous lead did read usage and the reaper's last run at each of L1 to L5v, in the same shell command that started the controller (or 9 seconds before it, L5v), and each launch intent in the private ledger follows its reading by under a minute (L1 09:52:10, L2 12:24:21, L3e 16:24:34, L4a 20:20:01, L5v 00:13:12 UTC); each reaper run was under 5 minutes old. Those readings were kept only in the previous lead's session transcript, outside the loop's record files, which is why round 1 found none; they are copied here. The "Launched" column repeats the times on `BUDGET.md`'s forecast rows; the ledger's launch intent times are the ones above (L2's is 31 minutes after its forecast row's time: two earlier starts of its controller, at 12:20 and 12:21 UTC, were refused before any launch intent, each after its own usage reading of 13 and 4). Whether the usage status file was itself under 10 minutes old at each reading is shown only for L2 (its own time, 12:20:32 UTC, was printed 3.5 minutes before the launch command); the status line rewrites it every minute while the session runs.

## Brought back under D-S12 (30 October 2026)

The operator's decision D-S12 (Annex D, revised at 00:20 on 30 October) reopened S5 after its first merge (`2dea80f`, unpushed; D-090, D-091): a 200 USD budget, the work S5 had left for lack of money done in S5, a look-back sweep, and the order of item 7. Each item below has its D-number.

### Order of work (D-S12 item 7)

1. Budget 200 USD, reaper hard stop 199 USD: ledger line 2026-10-29 21:26:33 UTC; reaper proof step 6 runs 49, 69, 199 on the mocked provider, neutralised and restored (D-091).
2. First look-back sweep (private `sweep_01_s5.md`): **83 found, 14 brought back, 18 decided, 46 kept, 5 to Seckin** (D-092).
3. Allocation (D-092): spent 20.99; S5 brought-back work 70.81; S6 5.74; S9 and S10 0; smoke runs 3.12; reserve 10; S8 89.34 USD.
4. Preregistration version 2 (D-093 to D-095): S4e item 2's unchanged rule with A = 89.34 USD gives ContractNLI 30 documents and SciTab 30 documents (both qualify; H1 tested on both) and a ContraDoc pilot of about 17; two fresh checker attacks (the first on a draft for a superseded allocation, rejected; the second closed in D-094); C0 run 4 in full agreement; version 2 frozen (LF SHA-256 `0c1884fb...`, scorer `2df0a673...`). A draft for 60 USD was withdrawn (D-091).
5. The brought-back work (below), then this stage's checks, report and merge.

### Items

- **Open item 35** (the multi-round phase's call ran to its cap): the case records are computed in Python, no model asked; the round signature reads only the labels each paired rule names (round 3 recomputed all 11 units before). Settled on real execution in L7: all nine multi-round entries reached `reviewed` and `activated` (D-100). The runner's model-call requirement then failed them (`required_telemetry_missing`); fixed so a declared multi-round run is held by its own evidence (D-101), and the nine were re-run in L12, all nine passing (D-112, D-128).
- **Open item 37** (peak disk on the instance): runner and evidence-packer readings (D-098 lane s05-meas, check via the controller gate). Read in L7: 45.24 GB in use before the first workload on a 1,455 GB filesystem, about 0.28 GB more per entry, 48.33 GB after the twelfth (D-100). Closed.
- **Open item 38** (phases before phase 3): four spans in `phase_latencies` (check 294). Read in L7's catalogue run: start 0.28 s, ingestion and roles 0.06 s, boot and index 21.75 s, phase 1 0.003 s (D-100). Closed.
- **Open item 39** (multi-round step times): a multi-round run has no topology runtime, so its own timings are recorded in `audit/multi_round.json` (D-101); read on L12's nine re-runs and closed (D-128).
- **Open item 40** (cost per correct FLAG item, development only, after version 2's freeze; D-096, extended with L11): see the cost table below.
- **Open item 17** (the repository scorer's three key parts): closed (D-098, check 293, attacked and fixed before merge).
- **S5 cuts of D-073 and D-077**: CUAD's B3 output and cost (L10), the development suite on B3 (L8, then re-run in L12 and L12b; the 56 probes of L9a and L9b moved after v1 by D-S18 item 3, not run), the catalogue regression and both negotiation comparisons and the negotiation multi-round case (L7), dry runs to five documents (L11).

### Launches after D-S12

| Launch | Purpose | Sealed at | Entries | Billed min | USD (forecast) | Integrity |
|---|---|---|---|---|---|---|
| L11 | dry runs to five documents (ContraDoc, SciTab, ContractNLI) | d50b299 | 16 (8 B3, 8 B1) | 191 | 4.11 (5.53) | B1 8 of 8; B3 2 of 8 |
| L7 | multi-round cases, catalogue regression, negotiation comparisons, family 4 tests and twins | 55f1dd1 | 12 B3 | 64 | 1.38 (10.62) | 1 of 12 (nine reviewed multi-round runs failed the runner's model-call rule, D-100) |
| L10 | CUAD, one development contract | 55f1dd1 | 2 (B3, B1) | 125 | 2.69 (4.11) | B1 passed; B3 semantically incomplete |
| L8 | development suite: 20 tests and twins | 55f1dd1 | 40 (20 B3, 20 B1) | 271 | 5.83 (15.09) | B1 20 of 20; B3 1 of 20 |
| R1 | replay proof of contract-shaped decoding (136 producer prompts, two paths) | cd498a3 | 1 B1 replay | 96 | 2.06 (3.13) | rules A to D met; 52 of 52 failing partitions valid (D-116) |
| L12 | re-run of the 37 failed B3 entries after the D-S14 fixes | 2b585af | 37 B3 | 610 | 13.12 (13.98) | 24 of 37 (L7 11/11, L11 5/6, L8 8/19, L10 0/1) |
| R2a | cloud proof of the envelope constraint (82 auditor prompts, two paths; D-129, D-130) | 7cb979e | 1 B1 replay | 125 | 2.69 (3.63) | passed; A, B, C hold; 12 of 22 failing calls now pass the validator (D-132) |
| R2b | the same for ARCHIVIST (14 prompts, two paths), beside R2c on a second instance | abd288c | 1 B1 replay | 28 | 0.60 (1.12) | passed; A to D hold; 2 of 2 fixed (D-134) |
| R2c | VERIFIER at a 4,096-token allowance (8 capped prompts, informational) | abd288c | 1 B1 replay | 70 | 1.51 (2.10) | passed; 4 of 8 end within 4,096 (D-134) |
| L12b | second re-run of the 13 still failing, two sessions on two instances | d6ce19a | 13 B3 | 178 + 114 | 6.28 (11.18) | 10 of 13 (D-138) |


### Results (development, exposed; no inference)

- **L11, dry runs on current code** (8 development documents, B3 and B1 tuned; private `an_l11_report.md`). Every run reached its end; B1 tuned passed on all eight (7.67 to 9.03 GiB); six of eight B3 runs semantically incomplete (PROCESSOR contract violations in 3, EDITOR_CLERK `items[0].kind` in 3, PRACTICE_AUDITOR in 2 on ContractNLI band B). All 408 B3 judging plans uncomputable: 101 answers kept as model-written records, 293 refused, 2 reply failed, and 12 neither kept nor refused (counted as dropped in the L11 analysis; the analyser records no reason). ContractNLI band B's 272 plans ran in waves (D-076). Headlines, B3 against B1 tuned: ContractNLI 9 of 34 against 18 of 34 (B3 under S-8 21 of 34); SciTab macro-F1 0.375 against 0.475 (S-8 0.222); ContraDoc 2 of 3 each. Every B3 FLAG label on ContractNLI and SciTab came from a model-written record. Model-text review (seed 2016037227976882296, 15 of 526): 1 correct, 5 partly correct, 9 wrong; all five kept D-068 records partly correct or wrong (open item 34).
- **L7, ordinary entries** (private `an_l7_report.md`). Catalogue regression (TCR-006): still 0 of 5 located, no false positives: three planted absences never reach a judge (no `[scope:]`/`[requires:]`, the TCR-012 mechanism), the vocabulary defect has no Finding relation, the closed-record defect was refused for naming the wrong field. Negotiation r2 to r3 (TCR-001): 6 of 6, bands 3 of 3, as before; one kept model record (wrong) and one false Python `missing_field` amendment on the summary table. Negotiation r3 to r4 (TCR-002): 13 of 13 on the records (the scorer's 12 of 13 is one hyphenated label), bands 2 of 2 attributed, Python's false band records 5 to 0. TCR-012 confirmed on the runs. Both comparisons semantically incomplete (PROCESSOR partitions). Every negotiation amendment sits at document level with no REF id (the document under review is indexed twice under one id; open item 31). Text review: 30 texts, 8 correct, 9 partly correct, 13 wrong; all 3 kept D-068 records wrong `below_band` answers on figures inside their bands.
- **L10, CUAD** (contract `527255a5c970`; private `an_l10_report.md`). B3 semantically incomplete (7 of 10 PROCESSOR partitions refused: malformed contracts, one truncated at 1,536 tokens); phase 5.5 86.8 of 98.9 minutes, 410 plans in two waves at about 12.7 seconds a plan; all 410 uncomputable answers refused for one reason, an absence claim with no quote, so B3 records nothing and labels all 41 categories present. B1 tuned passed (41 of 41 parsed, 14.2 seconds a call, 9.73 GiB). Macro-F1 B3 0.146 against B1 tuned 0.593; correct FLAG (absent) B3 0 of 34, B1 tuned 24. Cost 112.6 minutes, 2.42 USD a document, 0.059 USD a decision (the allocation forecast 21.76 USD for a mean contract). Text review: 15 of 433, 10 correct, 3 partly correct, 1 wrong, 1 empty.
- **Cost per correct FLAG item** (open item 40, development; D-096 extended with L11): ContractNLI B3 2.57 USD (2 correct), B1 tuned 0.51 (1); SciTab B3 0.061 (7), B1 tuned 0.061 (4); ContraDoc B3 none (0 correct), B1 tuned 0.09 (1); CUAD B3 none, B1 tuned 0.0087 (24). Under S-8, B3 has no correct FLAG item on any benchmark.
- **Minutes per scored decision with the brought-back documents**: ContractNLI 3.67 (band A 2.31, B 4.57), SciTab 2.22, ContraDoc 10.11, CUAD 2.75. These are development measurements after version 2's freeze; they change no size (D-093, D-095).

### Measurements after D-S12 (item 9)

All A10 in us-east-1 at 1.29 USD an hour; every asset copy MATCH (`asset_copy_receipt.json` state MATCH, `used: true`, `seeded: false`, all eleven sessions).

**Per launch.** For a replay (R1, R2a, R2b, R2c) there is no B3 pipeline: the GPU figure is the replay's own torch peak allocated memory (GiB, `replay_measurement.json`), not `vram_used_bytes`, and is marked so; the records are replay records, not B3 reply records.

| Launch | Billed min | Workload min (all entries) | Billed minus workload | USD | Peak GPU memory, B3 (GB) | Peak process memory, B3 (GB) | B3 reply records |
|---|---|---|---|---|---|---|---|
| L11 | 191 | 154.0 (B3 135.0, B1 19.0) | 37.0 | 4.11 | 18.1 (ContractNLI `01c9504b9c28`) | 7.8 | 526 |
| L7 | 64 | 28.7 (the nine multi-round entries 0.5 each) | 35.3 | 1.38 | 12.0 (catalogue) | 5.9 | 88 (the nine multi-round entries wrote none) |
| L10 | 125 | 108.6 (B3 98.9, B1 9.7) | 16.4 | 2.69 | 14.2 | 4.1 | 433 |
| L8 | 271 | 197.4 (B3 146.7, B1 50.7) | 73.6 | 5.83 | 23.7 (entry 34, ended out of GPU memory) | 7.8 | 795 |
| R1 | 96 | 83.0 (replay, 136 prompts, two paths) | 13.0 | 2.06 | not applicable, B1 replay: 7.88 GiB allocated on both paths | not applicable (no B3) | none (272 replay records) |
| L12 | 610 | 498.8 | 111.2 | 13.12 | 18.2 (CUAD) | 8.5 | 2,045 |
| R2a | 125 | 110.3 (replay, 82 prompts, two paths) | 14.7 | 2.69 | not applicable, B1 replay: 20.38 GiB allocated on both paths | not applicable | none (164 replay records) |
| R2b | 28 | 12.7 (replay, 14 prompts, two paths) | 15.3 | 0.60 | not applicable, B1 replay: 9.89 GiB allocated on both paths | not applicable | none (28 replay records) |
| R2c | 70 | 55.2 (replay, 8 prompts, constrained path only) | 14.8 | 1.51 | not applicable, B1 replay: 20.38 GiB allocated | not applicable | none (8 replay records) |
| L12b-a | 178 | 155.9 | 22.1 | 3.83 | 17.8 (CUAD) | 7.9 | 679 |
| L12b-b | 114 | 90.6 | 23.4 | 2.45 | 16.2 (suite entry `f2_s2101_sxwc`) | 8.8 | 401 |
| L12b (both) | 292 | 246.6 | 45.4 | 6.28 | 17.8 | 8.8 | 1,080 |
USD from the ledger, unrounded: L11 4.1065, L7 1.376, L10 2.6875, L8 5.8265, R1 2.064, L12 13.115, R2a 2.6875, R2b 0.602, R2c 1.505, L12b-a 3.827, L12b-b 2.451. These eleven sum to 40.248 USD.

**Controller phases per launch** (minutes, same groups as the existing table; the sum also holds `ssh_ready_*` and `watchdog_receipt_transfer*`, shown in brackets, which the existing table does not show apart; a replay is one bundle, so it has no per-entry checks).

| Launch | Support transfer | Asset copy probe and use | Setup | Workload | Per-entry checks | Stop and collection | Sum of phases | Billed minus sum |
|---|---|---|---|---|---|---|---|---|
| L11 | 0.5 | 3.1 | 2.7 | 154.0 | 22.1 | 0.7 | 183.9 (SSH and watchdog 0.9) | 7.1 |
| L7 | 0.6 | 5.1 | 2.7 | 28.7 | 18.0 | 0.7 | 56.2 (0.7) | 7.8 |
| L10 | 0.5 | 3.7 | 2.7 | 108.6 | 1.7 | 0.7 | 118.0 (0.1) | 7.1 |
| L8 | 0.9 | 3.3 | 2.7 | 197.4 | 57.8 | 0.7 | 264.7 (2.1) | 6.3 |
| R1 | 0.6 | 2.7 | 2.7 | 83.0 | none (one bundle) | 0.7 | 89.7 (0.1) | 6.4 |
| L12 | 0.7 | 7.0 | 2.9 | 498.8 | 91.2 | 0.7 | 603.4 (2.2) | 6.6 |
| R2a | 0.7 | 3.7 | 2.7 | 110.3 | none (one bundle) | 0.7 | 118.1 (0.1) | 6.9 |
| R2b | 0.6 | 3.3 | 2.7 | 12.7 | none (one bundle) | 0.7 | 19.9 (0.1) | 8.1 |
| R2c | 0.6 | 4.7 | 2.7 | 55.2 | none (one bundle) | 0.7 | 63.8 (0.1) | 6.2 |
| L12b-a | 0.8 | 3.5 | 2.7 | 155.9 | 7.4 | 0.7 | 171.3 (0.3) | 6.7 |
| L12b-b | 0.5 | 4.1 | 2.7 | 90.6 | 9.1 | 0.7 | 108.0 (0.4) | 6.0 |

Unrounded values are in `measure.json` (`phases_min`); the L10 row equals `an_l10_report.md`'s table (117.95, billed minus sum 7.05).

**Pipeline phases in B3** (minutes, summed over the launch's B3 entries that recorded `phase_latencies`). From L7 on, the telemetry also records the spans before phase 3 (open item 38, check 294); they are given in the last column so the existing columns stay as they are. Replays: not applicable (no pipeline).

| Launch | B3 entries | 3-4 content production | 5 audit | 5.5 convention review | 6 synthesis | 6.5 editorial review | Before 3 (start, ingestion and roles, boot and index, phase 1) |
|---|---|---|---|---|---|---|---|
| L11 | 8 | 23.2 | 6.1 | 97.1 | 0.1 | 2.5 | not recorded: sealed at `d50b299`, before the four spans were added |
| L7 | 3 of 12 (the nine multi-round entries record no phase latencies; their step times are in `audit/multi_round.json`, D-101) | 9.6 | 2.4 | 8.0 | 0.0 | 1.2 | 1.1 |
| L10 | 1 | 9.3 | 0.8 | 86.8 | 0.0 | 0.3 | 1.2 |
| L8 | 18 of 20 (entries 00 and 04 stopped at document dating, K1); phases 5.5 to 6.5 in 8 (ten entries ended out of GPU memory in phase 5, K2) | 96.5 | 25.2 | 7.7 | 0.1 | 3.1 | 4.1 |
| L12 | 28 of 37 (nine multi-round entries as in L7) | 151.1 | 51.4 | 256.2 | 0.4 | 11.2 | 9.5 |
| L12b-a | 6 | 30.2 | 19.9 | 98.3 | 0.1 | 2.5 | 2.1 |
| L12b-b | 7 | 47.8 | 16.9 | 17.8 | 0.1 | 3.0 | 1.6 |

Phase 5.5 is the largest line wherever a ContractNLI or CUAD document ran (L11, L10, L12, L12b-a); on the suite (L8, L12b-b) phase 3-4 is.

**Model calls by agent in B3** (Others: ARCHIVIST, INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER, LEGAL_ANALYST, VERIFIER, EDITOR_CLERK together). Replays: not applicable (no pipeline; R1 and R2b keep their own `logs\model_telemetry.jsonl` beside the replay).

| Launch | EMBEDDING | PROCESSOR | PRACTICE_AUDITOR | AUDITOR896 | Others | Total |
|---|---|---|---|---|---|---|
| L11 | 291 | 26 | 408 | 32 | 60 | 817 |
| L7 | 130 | 12 | 37 | 15 | 24 | 218 |
| L10 | 175 | 10 | 410 | 6 | 7 | 608 |
| L8 | 448 | 235 | 33 | 399 | 128 | 1,243 |
| L12 | 1,038 | 293 | 962 | 574 | 216 | 3,083 |
| L12b-a | 298 | 66 | 439 | 129 | 45 | 977 |
| L12b-b | 219 | 92 | 72 | 182 | 55 | 620 |

Per-agent counts in `measure.json` (`model_calls`).

**B1 seconds per call** (entry workload seconds over calls, model load included, so an upper bound; one tuned pass per entry after D-S12, so one checkpoint, not two). L11: ContractNLI 20.9 and 17.4 (17 items each); SciTab 25.9, 45.7, 15.9 (4, 2, 8 items); ContraDoc 55.8, 55.9, 55.7 (one item each, load dominates). L10: CUAD 14.2 (41 items). L8 (development suite, per family, summed over its four B1 entries): family 1 37.4 (20 items), family 2 30.6 (28), family 3 40.9 (16), family 5 21.3 (20), family 6 29.6 (12). Replays, per replayed prompt and path (load included): R1 18.3 (272), R2a 40.4 (164), R2b 27.2 (28), R2c 414 (8 VERIFIER prompts at a 4,096 allowance). B1 peak allocated, tuned: L11 7.67 to 9.03 GiB, L10 9.73, L8 7.99 to 8.64.
**Disk.**

| Launch | Sealed asset archive (bytes) | Free disk at admission (GB) | Peak disk in use on the instance (GB, of 1,455) | Largest B3 run folder, downloaded (MB) | Collected evidence archives together (MB) |
|---|---|---|---|---|---|
| L11 | 13,149,972,480 | 1,410 | not recorded: the runner's and packer's readings (open item 37) came after L11's seal at `d50b299`; no `disk_usage.json` or `disk_after_evidence.json` in any entry | 16.7 (ContractNLI `01c9504b9c28`) | 24.0 |
| L7 | 13,149,972,480 | 1,410 | 48.33 (after evidence, entry 11; the first reading, D-100) | 2.0 | 15.3 |
| L10 | 13,149,972,480 | 1,410 | 45.56 | 25.1 | 8.3 |
| L8 | 13,149,972,480 | 1,410 | 56.22 (after the last entry) | 2.1 | 51.0 |
| R1 | 13,149,972,480 | 1,410 | 45.25 | not applicable (no B3) | 1.2 |
| L12 | 13,149,972,480 | 1,410 | 55.50 | 25.8 (CUAD) | 60.2 |
| R2a | 13,149,972,480 | 1,410 | 45.25 | not applicable | 1.6 |
| R2b | 13,149,972,480 | 1,410 | 45.24 | not applicable | 1.1 |
| R2c | 13,149,972,480 | 1,410 | 45.24 | not applicable | 1.2 |
| L12b-a | 13,149,972,480 | 1,410 | 46.70 | 26.1 (CUAD) | 15.5 |
| L12b-b | 13,149,972,480 | 1,410 | 46.95 | 2.5 | 11.8 |

Peak disk in use is the larger of the sampled `disk_usage.json` peak (every 15 s, "not a continuous maximum") and `disk_after_evidence.json` (`measure.json`, `disk_peak_GB` and `disk_after_evidence_max_GB`; the two agree to 0.01 GB in every launch that has both). The filesystem is 1,455 GB (`total_bytes`), so the largest session (L8, 40 entries) used 3.9 percent of it.

**Per document, brought-back documents** (S5 item 9 method: minutes = B3 + B1 tuned + 2 minutes per batch entry for each arm; USD at 1.29 an hour, no 1.3 margin, no session overhead; B1 is one tuned pass, not halved). Rows copied from `an_l11_report.md` (lines 99 to 108) and `an_l10_report.md` (section 3), whose sources are `X\L11\...` and `X\L10\...` and `X\labels\<bench>\B3\L11\items.json` for decisions; checked here against `measure.json` (B1 peaks and workloads agree).

| Benchmark | Band | Document | B3 min | B3 peak GPU (GB) | B1 min (tuned only) | B1 peak, tuned (GiB) | Min per document | USD per document | Decisions | USD per decision |
|---|---|---|---|---|---|---|---|---|---|---|
| ContractNLI (merged) | A | `0d98d9131a5b` | 31.6 | 12.6 | 5.9 | 8.52 | 41.5 | 0.89 | 17 | 0.052 |
| ContractNLI (merged) | B | `01c9504b9c28` | 74.5 | 18.1 | 4.9 | 9.03 | 83.4 | 1.79 | 17 | 0.105 |
| SciTab | A | `09b24267b75a` | 4.1 | 11.1 | 1.7 | 7.84 | 9.8 | 0.21 | 4 | 0.053 |
| SciTab | A | `0e7ff50baa5f` | 3.1 | 10.7 | 1.5 | 7.67 | 8.6 | 0.19 | 2 | 0.093 |
| SciTab | A | `26937b278860` | 5.5 | 11.1 | 2.1 | 7.88 | 11.6 | 0.25 | 8 | 0.031 |
| ContraDoc | A | `01015e47de8a` | 4.9 | 11.7 | 0.9 | 7.96 | 9.8 | 0.21 | 1 | 0.212 |
| ContraDoc | A | `027002a77443` | 3.9 | 11.6 | 0.9 | 7.83 | 8.9 | 0.19 | 1 | 0.190 |
| ContraDoc | B | `06cd776dcc1a` | 7.3 | 11.7 | 0.9 | 8.15 | 12.2 | 0.26 | 1 | 0.263 |
| CUAD | B (D-097) | `527255a5c970` | 98.9 | 14.2 | 9.7 | 9.73 | 112.6 | 2.42 | 41 | 0.059 |

The same documents' B3 re-runs on the D-S14 code (`entries.txt`; B3 workload minutes, peak GPU GB, integrity), for reading beside the rows above, not replacing them: L12 ContractNLI `0d98d9131a5b` 36.3, 12.6, passed; `01c9504b9c28` 90.7, 13.9, passed; SciTab `0e7ff50baa5f` 3.4, 10.7, passed; ContraDoc `01015e47de8a` 7.9, 11.7, passed; `027002a77443` 3.8, 11.6, passed; `06cd776dcc1a` 8.7, 11.9, failed, then L12b-a 5.5, 11.9, passed; CUAD `527255a5c970` L12 114.3, 18.2, failed, L12b-a 109.2, 17.8, failed. On ContractNLI band B the D-S14 code took 90.7 minutes against L11's 74.5 and used less GPU memory (13.9 against 18.1 GB); on CUAD 114.3 and 109.2 against L10's 98.9. SciTab `09b24267b75a` and `26937b278860` passed in L11 and were not re-run.

**Exposed tests and comparisons (B3 workload minutes, `entries.txt`):** catalogue regression 9.1 (L7); negotiation r2 to r3 6.3 (L7), 7.1 (L12); r3 to r4 8.5 (L7), 10.0 (L12); each multi-round case 0.5 (L7) and 0.6 (L12), Python only, no model call. Development suite B3 per bundle on the D-S14 code: L12 19 suite entries 4.9 to 17.1 minutes, mean 11.1; L12b 11 suite entries 6.3 to 19.9.

Not recorded, each with its reason: L11's peak disk in use and its phases before 3 (the code sealed at `d50b299` did not write them); pipeline phase latencies of the multi-round entries in L7 and L12 (a multi-round run has no topology runtime; its own step times are in each entry's `audit/multi_round.json`, read and closed in D-128, not summed here); B3 peak process memory for the replays (no B3 pipeline ran).

### Model-text reviews of L8, L12 and L12b (item 8)

Rule (S5 plan item 8, D-080, D-086): seed = int(SHA-256 hex of "<run folder name>:text-review", 16) mod 2^63; population = every `.json` reply record under `downloaded\evidence\run\audit\model_replies\` of the session's B3 entries, sorted as path strings; sample = `random.Random(seed).sample(population, 15)`. `seed_draw.py` first reproduced L11's recorded draw exactly (526 records, the same 15), then derived each seed and drew each sample, writing `<launch>_text_review_sample.json`, before any record's text was read. Each sample was judged by a fresh general-purpose subagent (one per launch) against the unit's own text in the record's payload (and the staged workload document where needed), joined to the pairing map's judging-call entry by call id; none opened a key, answer, gold, labels or items file.

| Launch | Run folder | Seed | Population | Sample | Correct | Partly correct | Wrong | Empty | Unverifiable |
|---|---|---|---|---|---|---|---|---|---|
| L8 | `f1_s1101_vxnf_B3` | 7172554169477582575 | 795 (18 of 20 B3 entries hold records; 00 and 04 stopped at dating before any call) | 15 | 4 | 0 | 9 | 2 | 0 |
| L12 | `contradoc_01015e47de8a_B3` | 2016037227976882296 | 2,045 (28 of 37 B3 entries; the nine multi-round entries make no model call) | 15 | 4 | 5 | 6 | 0 | 0 |
| L12b | `contradoc_06cd776dcc1a_B3` (L12b-a), population both sessions | 696316031219208063 | 1,080 (all 13 B3 entries: a 679, b 401) | 15 | 2 | 1 | 12 | 0 | 0 |

Two seed facts, stated before the draws and to be carried with the counts:
- L12's session folder has the same name as L11's (`contradoc_01015e47de8a_B3`), so the rule gives L12 the same seed as L11 (2016037227976882296). The populations differ (L11 526 records, L12 2,045), so the samples differ; the rule was applied as written, not changed to avoid the repeat.
- L12b ran as two sessions, so the rule names no single folder. Chosen and recorded in `seed_draw.py`'s docstring before the draw: the population is the union of both sessions' B3 records, and the seed is the rule's value for the first-launched session's folder (L12b-a, `contradoc_06cd776dcc1a_B3`). L12b-b's folder (`f1_s1101_vxnf_B3`) has the same name as L8's, so using it would have repeated L8's seed.

Per agent:
- L8: AUDITOR896 (final) 10: 1 correct, 9 wrong; PROCESSOR (final) 3: 3 correct; VERIFIER (base) 1: empty (the call ran out of GPU memory, K2); LEGAL_ANALYST (final) 1: empty (a deepen call returned no item). No sampled record was a paired judging call, so no D-068 disposition applies.
- L12: PRACTICE_AUDITOR (base) 8: 1 correct, 3 partly, 4 wrong (7 of the 8 refused under D-068 as absence claims with no quote: 0, 3, 4; the 8th was a computed plan whose figures Python held, restated correctly); PROCESSOR (final) 3: 3 correct; AUDITOR896 (final) 2: 2 wrong; INST_FINDER (final) 1: partly; LEGAL_ANALYST (final) 1: partly. No sampled record was a kept D-068 record.
- L12b: PRACTICE_AUDITOR (base) 8: 1 partly (the computed-plan note: right verdict, wrong arithmetic in its sentence), 7 wrong (all on the CUAD contract, all refused under D-068); AUDITOR896 (final) 5: 5 wrong; PROCESSOR (final) 2: 2 correct.

The pattern across the three (counts only): the base PRACTICE_AUDITOR still answers VIOLATION with `missing_field` on units that do not address the rule (ContractNLI hypotheses, CUAD categories), as in L1 to L11; after the D-S14 fixes every such sampled answer was refused under D-068 rather than kept, so in these samples none reached a model-written record (16 sampled PRACTICE_AUDITOR records: 14 refused under D-068, 2 notes on computed plans, 0 kept). New against the earlier reviews: the classifier AUDITOR896 is the largest wrong group (16 of 17 sampled records wrong over the three launches), labelling a faithful empty extraction OMISSION, in most samples with a byte-identical reply (the reviewers' reading: the producer correctly extracts `empty` where a span carries no claim id or stated gap, so MATCH is the faithful relation). The producer's compact extractions were right in all 8 sampled (empty, correctly). Development, one run each; these are reviewer judgments on 15 records a launch.

Review files: private `analysis/L8_MODEL_TEXT_REVIEW.md`, `analysis/L12_MODEL_TEXT_REVIEW.md` and `analysis/L12b_MODEL_TEXT_REVIEW.md` (they describe replies without quoting them).
- Samples with seeds: `...\s5close_meas\L8_text_review_sample.json`, `L12_text_review_sample.json`, `L12b_text_review_sample.json`. The extracted record dumps the judges read (`rev_L8\`, `rev_L12\`, `rev_L12b\`) hold reply and payload text and must not be copied into any committed file.

Excluded: R1 and R2 (R2a, R2b, R2c) replayed saved prompts (their replies are replays of prompts already in L7, L8, L10, L11 and L12, measured for byte identity and contract validity in D-116, D-132 and D-134), so they are not reviewed as model text. L7, L10 and L11 were reviewed earlier (S5 report).

Suggested item 8 line for the S5 report: "L8 4, 0, 9, 2, 0; L12 4, 5, 6, 0, 0; L12b 2, 1, 12, 0, 0 (seeds by the rule; L12's equals L11's because the session folder names are equal; L12b's from its first-launched session over both sessions' records; R1 and R2 excluded as replays of saved prompts)."

### D-S14: every development run must complete (D-111 to D-116, D-128)

First runs of L7, L8, L10 and L11: 37 failed B3 entries (D-112 counted 33 with L8 read at 14:20, before it ended; 37 in L12's rerun record) by kind (private s5_diag_b3.md): dating `ValueError` 2 (K1), VERIFIER out of GPU memory 10 (K2), the producer's compact contract 52 of 283 partitions in 15 entries (K3 to K7), EDITOR_CLERK `kind` 4 (K8), rarer agent shapes in 5 (K9 to K11), the runner's model-call rule on nine multi-round runs (K12). Fixed: K1 (four-digit years), K2 (VERIFIER shown no runtime identifiers), K3 to K7 (contract-shaped decoding, validator unchanged, proven by R1), K8 (declared single kind stamped), K12 (D-101). After the fixes, L12 re-ran all 37 that had failed: 24 pass; no out-of-memory, no `ValueError`, no telemetry failure and no producer violation remain. The 13 left fail on PRACTICE_AUDITOR (9), VERIFIER (8) and ARCHIVIST (1) envelopes: 6 of the 13 are predicted cleared by extending the constraint to those agents (D-129, proof R2); the other 7 fail because VERIFIER lists one item per reference until its 2,048-token output allowance ends, which no constraint shortens; an informational pass at 4,096 tokens (R2c) informs the run-setting decision. R2 runs as three launches (no B1-only batch form, D-130); two loop instances at once are merged and proven (D-S17 item 1, D-131).

On the A10 (R2, D-132, D-134): the constraint changed no valid reply of the three agents (72 valid prompts byte-identical, 0 interventions, equal GPU memory) and 14 of 24 failing calls now pass the validator (9 PRACTICE_AUDITOR replies missing their explanation, 3 unclosed envelopes, 2 of them VERIFIER and 1 PRACTICE_AUDITOR, and 2 ARCHIVIST replies without confidence); "pass the validator" says the shape is right, not that the forced text is right, which the seeded review of intervened replies reads (item 8). One more PRACTICE_AUDITOR reply missing its explanation (`p0030`) ran to 768 under the constraint (open item 47). The VERIFIER lists that ran to the 2,048-token cap are a budget, not a shape: at 4,096, 4 of 8 end and pass, so VERIFIER's allowance became 4,096 (a run setting, D-134); the other 4 repeat one item per reference past 4,096 and are recorded with that cause.

L12b (D-136, D-138) re-ran the 13 that still failed, on VERIFIER's 4,096 allowance and the envelope constraint, as two sessions on two instances at once (292 billed minutes in all, 6.28 USD): 10 pass. Of the 37 B3 development entries that first failed integrity, 34 now pass. The 3 left, each with its cause and an open item: `f1_s1101_cvjx`, two PRACTICE_AUDITOR replies the constraint kept open for their required explanation, which then ran to 768 tokens (open item 47); `cuad_527255a5c970` and `f3_s3102_vwmj`, VERIFIER lists that run to 4,096 (open item 48). Under D-S18 item 2a they are recorded and do not hold v1 back.

## Decisions

`docs/loop/DECISIONS.md`, D-055 to D-139 (D-089 onward after the reopening):

- D-055: S5 plan decisions DS5-1 to DS5-12 and revisions R1 to R25, after plan check 1.
- D-056: B1 on sdpa with a pinned memory-efficient backend (option A, amended, ten conditions).
- D-057: re-forecast after L1 (overhead without upload 15.4 minutes) and L2's content.
- D-058: the producer to sdpa, conditional on L2's evidence, thresholds (90 and 95 percent) declared before reading it.
- D-059: unused (D-071).
- D-060: L2 gave 18 of 21 byte-identical (85.7 percent), so A did not take effect; E (chunked prefill under eager) replaced it.
- D-061: E made buildable, the general fixes from the L2 diagnosis, and a correction of INC-015's scope.
- D-062: L3e's content and forecast; the chunked gate at `c2173bf`.
- D-063: E missed its threshold (8 of 12); option A adopted for the producer and B1 (12 of 12).
- D-064: re-forecast after L3e, attacked; L4a first.
- D-065: Annex D, D-S10 item 8 (how remaining and eta are computed).
- D-066: how a semantically incomplete B3 run is scored; sensitivity S-6.
- D-067: B3 kept no answer on text-only claims; closed: measure as it is, fix the defect before freeze under conditions.
- D-068 (written out in D-071): a model's answer on an uncomputable plan kept as a model-written record.
- D-069: L5v, D-068's verification run, and its acceptance declared before it.
- D-070: D-068 verified; it stays.
- D-071: D-068 given its own entry; D-059 stays unused.
- D-072: restart of 29 October: disk below 30 GB, merged worktrees removed, the restart check's plan items.
- D-073: re-forecast after L5v; cuts (CUAD, suite B3, regression in part, dry runs below five).
- D-074: Annex D, D-S10 item 9 (idle time is a pause; heartbeat).
- D-075: S7's first pass starts during S5; more merged worktrees removed; the pip cache left alone.
- D-076: INC-019 fixed: a gather above the scheduler bound runs as waves.
- D-077: L6 and L6s content from L4b's actual; regression cut.
- D-078: preregistration section 12 settled; FinDVer leaves the priority list; the adapters apply section 5.3.
- D-079: the operator's restart at 18:15: L6 state, and the hidden-window rule.
- D-080: sensitivity S-8; the two review seeds that did not follow the rule.
- D-081: preregistration section 2 filled: a ContractNLI pilot, no SciTab or ContraDoc sample.
- D-082: the first real multi-round runs refused at the phase; the fix deferred to S6a.
- D-083: L6s2 out of memory; the merged-part route; S5 spend closed at 20.64 USD.
- D-084: the final preregistration attack accepted; synthetic-test scoring built; C0 run 3.
- D-085: C0 run 3 in full agreement; the preregistration frozen.
- D-086: S5 checker round 1's record items: D-069's blind acceptance criterion and the S8 limitation; the FinDVer estimate labelled; the review seeds; the purpose-line reading; the item 9 figures not recorded (P9 e).
- D-087: S5 checker round 2's record items: the cloud-run baseline pair at the S5 base, the usage readings at L1 to L5v, the A1 limitation bound forward (open item 36), the side gates' commit and the merges between.
- D-088: S5 checker round 3's record items: the item 9 deferrals bound to S6 and S8 as open items 37 to 40 (reasons corrected from P9 e), the C0 hash records, INC-024, the units of the clean twin's model records, the logs not kept, the final-integration errors named, the purpose-line reading under P2.
- D-089: Tie-break on the section 13 attack (IV.4 step 5): two confirmed, record fixes; the freeze stands
- D-090: D-S12 applied: S5 reopens for open items 37 to 40, the budget is 100 USD, and S8 is re-sized with 60 USD
- D-091: D-S12 as revised at 00:20 replaces D-090: 200 USD, parked work brought back, a look-back sweep, and the order of item 7
- D-092: The first look-back sweep, what is brought back, and the allocation of D-S12 item 4
- D-093: Preregistration version 2: S4e item 2's rule with A = 89.34 USD
- D-094: The attack on preregistration version 2 closed
- D-095: C0 run 4 in full agreement; preregistration version 2 is frozen
- D-096: Open item 40 settled: cost per correct FLAG item on the development benchmarks
- D-097: The brought-back launches: staging, run modes, and order
- D-098: Open item 17 closed: the repository scorer reads the three key parts; the input format draft's scorer sentences
- D-099: Disk for the brought-back launches: worktrees removed, identical archives hard-linked, sealing just in time
- D-100: L11 and L7 read: open items 35, 37 and 38 settled on real execution; the runner's model-call requirement fails a multi-round run
- D-101: A declared multi-round run is assessed on its own evidence; open item 39's step times recorded
- D-102: The measurement lane merge (open items 37 and 38) and what it bound
- D-103: Open item 35: the multi-round case records are computed in Python and no model is asked
- D-104: Open item 40 extended with L11 and L10 (development)
- D-105: CUAD measured (L10) and kept off the S8 list
- D-106: The regression of the catalogue test and both negotiation comparisons (L7)
- D-107: Departures and record corrections after the D-S12 checker of the work so far
- D-108: Second reading of version 2's late fixes; how S8c packs sessions; no version 3
- D-109: D-S13 applied: items 1, 4, 5 and 12 now; item 10's question; where the other items go
- D-110: D-S13 item 3: the four large disk users found out, nothing deleted; items 7 to 9 started
- D-111: D-S14 applied: every development run must complete; L8 runs on, L9a and L9b held, the causes diagnosed first
- D-112: D-S14: the failure causes found, and the fixes chosen
- D-113: D-S13 items 8 and 9: CUAD as a claim check is a secondary arm; the benchmark scoring mode merged
- D-114: D-S14 fixes merged and proven on the laptop; contract-shaped decoding adopted only if its cloud re-measure meets rules A to C
- D-115: D-S13 item 7 merged, and the allocation redone for the D-S13 and D-S14 work
- D-116: R1 read: contract-shaped decoding meets rules A to D and is adopted
- D-117: FinDVer's B1 candidate adopted for development measurement; L13 staged
- D-118: What may be read from L13 before preregistration version 3 is frozen
- D-119: D-S15 applied: disk read, deferrals into FOR_SECKIN, item 6d named, LOOP_STATE corrected
- D-120: D-S15 items 4 and 5 applied: issues in step, the ledger of Seckin's requests
- D-121: The first records consistency check (D-S15 item 7): 25 found, 25 fixed
- D-122: D-S16 received: the order of its application
- D-123: D-S13 items 6b and 6c: the launcher's quoting defect, and where each install runs
- D-124: D-S16 item 1: the ledger has its two columns and a checking script that proves itself
- D-125: D-S16 item 3: GitHub as a second witness; the stage gate defined
- D-126: Preregistration version 3 drafted; its ten open points decided before any L12 or L13 figure is read
- D-127: D-S17 applied: two loop instances (in a lane, proven first), the S5 launch order, S12 out of the loop
- D-128: L12 read: 24 of 37 re-runs pass; the producer's failures are gone; three agents' envelopes remain
- D-129: The envelope constraint for VERIFIER, PRACTICE_AUDITOR and ARCHIVIST merged; R2's rule; VERIFIER's output cap
- D-130: R2 as three launches; the records consistency check before R2a: 21 found, 21 fixed; the twoinst merge after R2a
- D-131: Two loop instances merged and proven (D-S17 item 1); PROGRESS.json recomputed in full (D-S17 item 4)
- D-132: R2a read: the envelope constraint adopted (rules A, B and C hold); 12 of 22 failing auditor calls fixed
- D-133: D-S18 applied: v1 by Monday 2 November 12:00 +0300; the order of work; money
- D-134: R2b and R2c read; VERIFIER's output allowance raised to 4,096 (a run setting)
- D-135: The records consistency check before L12b: 22 found, 22 fixed; memory floors for checks and for two instances
- D-136: VERIFIER's output allowance merged (4,096; FACT_CHECKER keeps 2,048); L12b sealed on it
- D-137: The parallel track's first two patches received; when and how they merge; the constitution amendment is the operator's to apply
- D-138: L12b read: 10 of 13 pass; 34 of the 37 first failures now pass; the 3 left and their causes

## Bound controller files and pinned functions changed in S5

- **Controller lane** (B1 arm, B3-only batches, per-entry evidence past the soft budget, the sealed B1 argument check): `tools/ordinary_final_run.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`. The L1 bundle was sealed and launched before this merge.
- **B1 attention lane and the join lane** (B1 kernel, B1 passes, staging): `tools/ordinary_final_run.py`. D-061 and D-063 changed it again (PREFILL-E).
- **Hidden-window lane** (D-079, HIDDEN-A, check 292): six of the 11 bound names: `tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`, `tools/lambda_experiment_provider.py`, `tools/run_remote_experiment.py`.

Every bundle sealed before each of these merges refuses with `Controller source changed` and must be resealed (CONTROLLER-BINDING); L6m and L6s2 were resealed after the hidden-window merge. Pinned pipeline functions: in the first part of S5 one reference amendment, recorded in both `benchmark/fixtures/multi_round_baseline_contract.json` and `benchmark/fixtures/topology_reference_contract.json` (`reference_amendments`, 2026-10-29, D-068): `_paired_convention_review` from `c849c3bc...` to `ea86ffc1...`. The waves fix (D-076) left `scripts/pipeline.py` unchanged. After the reopening, two more, recorded the same way in both baseline contracts: `main` on 2026-10-30 (`9060797f...` to `ac1e96b4...`, open item 38, D-102) and `phase_5_audit` on 2026-10-31 (`6d994ae0...` to `95d3a868...`, VERIFIER's 4,096 allowance, D-136). Bound controller files changed after the reopening: `tools/ordinary_final_run.py` and `tools/ordinary_final_cloud.py` (open item 37, D-102; the multi-round assessment, D-101; the replay path `sdpa_constrained`, D-116), `tools/ordinary_final_cloud.py`, `tools/loop_budget_guard.py` and `tools/loop/instance_reaper.py` (two instances, D-131); every bundle was sealed after the change it ran on.

## Checkers

**Round 1 (2026-10-29 about 22:30 +0300).** No CRITICAL. Adversarial: 3 SERIOUS (A1 D-069's acceptance could not detect D-068 records, because the scorer counts false positives over amendments only; A2 side gates not recorded for the merges `8ac7a60`, `8c2392d` and `70596c6`; A3 pinned-function amendment completeness to be shown by `test_reference_ast_contract` at the loop/s05 tip) and 6 MINOR (A4 the B1 checkpoint rule read development scores and D-066 came after B1 scores; A5 S8 has one external benchmark; A6 the FinDVer figure is an estimate; A7 the review seeds; A8 the commits where check 256 failed; A9 this section). Completeness: 8 gaps (C1 no model-text review of L6m and L6s2; C2 and C3 item 9 figures not tabulated; C4 C0 inputs not recorded; C5 the purpose line and the unanalysed L6m and L6s2; C6 usage readings per launch; C7 BUDGET.md actuals, the L6s row, the closing line and stray cells; C8 the close). Claims: 4 MINOR (H1, the same as C7; H3 L5v forecast rounding; H4 a format-hash row in the wrong VERSIONS table; H5 this report's commit counts). Closed in the records: A1 (limitation below item 8, D-086), A4, A5 (item 10), A6 (D-086, SELECTION.md note), A7 (item 8, D-086), A8 (Gate), C2 and C3 (item 9 tables; the figures not recorded in D-086 under P9 e), C4 (item 10), C5 (the reading; L6m and L6s2 analysed), C6 (usage table), C7 and H1 (BUDGET.md), H3 (BUDGET.md, launch table), H4 (VERSIONS.md: the row moved, content unchanged), H5 (top of this report). A2, A3 and C1 closed in D-086 (the lead's closures: the side gates and the merges between, see Gate; `test_reference_ast_contract` ok at the tip; L6m and L6s2 reviewed, item 8). C8 is the close itself.

**Round 2 (2026-10-29 about 22:55 +0300).** No CRITICAL. Items S1 to S3, M4 to M10, C1, C3 and C4, all closed in the records (D-087): S1 the cloud-run baseline pair checked at `ea1c0d5` (Gate); S2 the usage readings at L1 to L5v found in the previous lead's session transcript (usage table); S3 the A1 limitation bound forward (open item 36, a dated note in `docs/benchmarks/DEVIATIONS.md`); M4 VERSIONS.md restored and a corrected row appended; M5 a dated note on DEV-011; M6 the count line; M7 item 8 and this section; M8 the purpose-line wording at the top; M9 the side gates' commit and the merges between (Gate); M10 one reaper reading here and in BUDGET.md, and L6's variance; C1 the hash abbreviation in item 10; C3 check 01 in the side gates (Gate); C4 the C0 manifests kept (item 10).

**Round 3, the last (2026-10-29 about 23:20 +0300).** No CRITICAL. Items SER1, SER2, G1, G3 to G5, M1 to M6. Closed in the records (D-088): SER1 the four item 9 deferrals made open items 37 to 40, each bound to S6 or S8 with its P9 reason corrected (D-086 had named reason e, but each names an in-loop way to settle it), listed in FOR_SECKIN.md, and the count line and its "not now" header fixed; G1 the C0 hash records (item 10); G3 INC-024 for L6s2's out-of-memory failure; G4 open item 35 names round 3's full recomputation as a thing to read; G5 the LOOP_STATE issues list to cover the open items from 27 on; M1 the clean twin's units, "8 answers kept, 10 model-written records", in item 7 (a), the limitation below item 8, open item 36 and a dated note in `docs/benchmarks/DEVIATIONS.md`; M2 "measurements recorded" in part (count line); M3 the logs not kept (Gate); M4 the final-integration errors named (Gate); M5 the purpose-line reading under P2 (Purpose line); M6 the qualifier on item 3's clean-twin false positives. SER2 (preregistration section 13 and the synthetic B1 prompt, never attacked by a fresh checker) is handled by a separate fresh checker; its result is recorded in D-088.

## Gate

Per-commit chunked gates in the lead worktree (the gate's own CHECKS in foreground chunks, INC-016), each compared with the worktree baseline: at each recorded gate the non-pass set was the worktree baseline, apart from the check 256 flake below (D-062, D-064, INC-017, INC-021); the checks S5 added (285 to 292) pass in their lanes and at the lead's gates. The server checks ran in the loop venv. Check 256 fails now and then inside a long run and passes alone (INC-013, INC-021, open item 33; traced in S6a). In S5's chunked gates it failed ("sensitive health imported a model probe while inactive") three times, each inside the long chunk that holds it, and passed alone each time: at `8c2392d` in the chunk 200 to 277, then PASS alone and in the range 200 to 256 (logs `gate_logs/s05_8c2392d/c2.log`, `c256.log`, `c200_256.log`); at `ee2f1ed` in the chunk 200 to 277, then PASS alone right after (recorded in INC-021's recurrence note; the solo log was not kept); at `2b50067` in the chunk 190 to 260, then PASS alone (`gate_logs/s05_2b50067/c2.log`, `c256.log`). It passed inside the chunk at `18eee21`, `70596c6`, `ee8fa6a` and `fc02e1d`. Earlier, in S5's full gate at `1c4daac`, it failed once and passed alone (INC-013). INC-022 is fixed: check 222 restores `shimmer.sh` byte for byte, so the gate no longer changes the tree. INC-017 (checks 229 and 233 after D-068) closed at `cbcceac`. The merge gate on the loop branch runs at the stage close.

**Side gates (S5 checker rounds 1 and 2).** The six side gates recorded in D-086 (logs `gate_logs/s05_close_side/`: `execution_topology.log`, `report_recommendations.log`, `localization.log`, `final_integration.log`, `cloud_run.log`, `controller.log`) ran at 22:31 to 22:38 +0300 on 29 October in the lead worktree, on the code of `7c74028` with the round 1 record edits not yet committed (they became `cdc6fc3` at 22:43, records only). The execution topology, report recommendations and localization gates each end with a subset of the main gate whose check 01 FAILs ("missing required dirs: input/context, input/operational, durable/governance"): that is the worktree baseline (a worktree holds tracked files only; GATE_BASELINE.md, environment 2), the same line as in the S3 side-gate logs `gate_logs/s03_5ac15f3_side_execution_topology_no_generation_gate.log`, `..._report_recommendations_...` and `..._localization_...`. The cloud-run checks fail on the pair `test_full_bundle_reproducible_and_readiness_last` (AssertionError, "False is not true" at the `ready_to_provision` assertion) and `test_preparation_refuses_existing_evidence` (FileNotFoundError). GATE_BASELINE.md's environment 2 records FileNotFoundError for both; at round 2 the cloud-run checks were run at `ea1c0d5` (the S5 base, in a temporary detached worktree, removed after) and at the S5 tip `cdc6fc3`, in the same environment: the same two tests fail with the same kinds and the same message at both (88 tests at `ea1c0d5`, 92 at the tip), and the S3 side-gate log `gate_logs/s03_5ac15f3_side_cloud_run_checks.log` already shows the AssertionError. It is not an S5 regression: the baseline's record of the kind is out of date, not the code (D-087). Those two round 2 cloud-run runs, at `ea1c0d5` and at `cdc6fc3`, were not written to a log file; their results stand only in D-087 (S5 checker round 3, D-088). The final-integration gate (`final_integration.log`) ends with 152 tests, 0 failures and 3 errors, and the log does not name them. The waves lane names the same three errors at 148 tests before its change and at 152 after (`s5_lane_waves_report.md`): `test_ordinary_final_admission_requires_valid_pair_contract`, `test_preserved_artifacts_match` and `test_startup_requires_runtime_artifacts_and_contract`, each `RuntimeError: Missing frozen producer adapter`. The frozen producer adapter's weights are an untracked file that only the main checkout holds, so a worktree cannot load them; this is environmental, not an S5 regression. The merge gate in the main checkout, which holds the adapter, will show the result of these three tests at the stage close.

**The merges between `ea1c0d5` and the tip.** `8ac7a60` (lane/s05-defect, D-068 and D-066): side gates run by the lane at its tip before the merge (adapter checks 58 cases, baseline checks 26, execution topology, report recommendations, localization, final integration 148 tests and the controller gate 92 tests, each passing; the cloud-run checks are not in the lane's list), recorded in the lane's report to the previous lead (session transcript of 28 October, 23:30 UTC; no lane report file was saved, and no log of those side gates was kept, so their results stand only in that transcript and in D-087); main gate at `889d682` (the merge plus `CLAUDE.md`), in chunks (`gate_logs/s05_889d682_chunk1.log` to `chunk4.log`): the worktree baseline apart from checks 229 and 233 (INC-017, fixed at `cbcceac`). `8c2392d` (lane/s05-waves): main gate in chunks at the merge (`gate_logs/s05_8c2392d/`) and the lane's side gates (`s5_lane_waves_report.md`). `70596c6` (lane/s05-hidden): main gate in chunks and the controller gate at the merge (`gate_logs/s05_70596c6/`, `ctl.log`) and the lane's side gates (`s5_lane_hidden_report.md`).

## Count line

21 named (spec items 1 to 10 and the 11 exit criteria), 13 done, 7 not now (P9 reasons b and c), 1 at close. S5 checker round 2 moved item 9 to "not now, in part" (it was counted done); round 3 moved the exit criterion "measurements recorded" with it, and corrected item 9's reason from (e) to (b) and (c) (D-088).

- **Done.** Items 1, 6, 7, 8, 10. Exit criteria: smoke run; regression scored (with the recorded cut); development suite and adapter dry runs (B2 only and the recorded cuts); B1 and B2 proven; every failure classified; spend within 24 USD; C0 in full agreement; preregistration frozen.
- **Not now (P9 reasons b and c; each in DECISIONS.md, FOR_SECKIN.md and, where it is bound forward, an open item).** Item 2 and its exit criterion (b): the multi-round health criterion (outcome `reviewed`) is not met (D-082, open item 35, S6a). Item 3 in part (b): the catalogue test and both negotiation comparisons (D-077). Item 4 in part (b): B3 on the development suite (D-073). Item 5 in part (b): CUAD with no output and fewer than five current-code documents per benchmark (D-073). Item 9 in part and the exit criterion "measurements recorded" in part (D-086, corrected in D-088): the peak disk in use on the instance (b, open item 37, S6), the time in the pipeline's phases before phase 3 (c, open item 38, S6), the L6m phase latencies (b, open item 39, S6a) and the cost per verified finding on the benchmarks (c, open item 40, S8) are not recorded; every other measurement is in the item 9 tables.
- **At close.** Checkers closed, stage merged, tag `loop-s05-v1`.

## Stage boundary

No loop instance is running: the reaper's reading at 19:56:59 UTC on 29 October (`reaper_status.json`, the same reading as in `BUDGET.md`'s S5 closing line) listed 0 instances, with total spend 20.99 USD (20.9904; instances 20.64, storage share 0.35). No role session and no lane runs. The asset copy `shimmer-filesystem` stays as the operator created it. The system disk had 37.6 GB free at 22:14 +0300, above the 30 GB floor.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
