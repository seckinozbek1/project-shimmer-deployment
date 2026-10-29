# S5 report: development runs on Lambda

Stage S5 of the autonomous loop of 27 October 2026, on branch `loop/s05`, created from the loop branch at `ea1c0d5` (S2, S3 and S4 merged and tagged). The lead worked in `.claude/worktrees/s05-lead`. Opus, medium effort from 28 October 2026 (Annex D, D-S11). Every run in this stage is a development run on exposed material: its purpose line and "exposed test, development only" head its report (Annex B.1). The lead session changed once: session 757d835b led S5 until it stopped at 05:11 +0300 on 29 October after an automatic compaction; session f3d23d40 took the released lock at 11:00 +0300 and ran a restart check (14 items, D-071, D-072). The operator stopped the laptop once, at about 18:15 +0300 on 29 October (D-079). On the branch, counted at `7c74028` (the loop/s05 tip when checker round 1's records were written, the commit of this report): 91 commits after `ea1c0d5`, 77 files changed, 14,378 lines added and 458 removed (`git rev-list --count ea1c0d5..7c74028`, `git diff --shortstat ea1c0d5..7c74028`). The checker-round commits after `7c74028` change only records and are not in these counts.

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

### Items of the S5 specification

1. **Smoke run (L1).** Every model reply saved (`audit/model_replies/`, outcomes appended), the honest deliverables, the 11.12 report fields, the budget guard, the ledger lines and the `shimmer-loop-` name, and the asset copy: MATCH, measured, so later forecasts dropped the upload (overhead 15.4 minutes measured against 48.3 with the upload).
2. **First real multi-round run (L6m).** The synthetic family 4 case of three rounds (`f4_s4103_vqjj`) and the negotiation case of three offers (anonymised material only, H6), B3. In L6 the synthetic case was in its archive check at the 18:15 stop; both ran in L6m. Both reached the multi-round phase with activation `activated` and were refused there (`agent_output_unavailable`, pipeline exit 8): the phase's reading-agent call got a 15,795-token prompt and ran to its 4,096-token cap in 944 seconds, outside the two-turn shape the checkpoint was evaluated on (INC-023). `audit/round_reuse.json` of the synthetic case: round 1 computed 11 units, round 2 reused 8 and computed 3 (the do-not-recompute rule holds on real execution), round 3 computed all 11 (why, to be read in S6a). The health criterion (outcome `reviewed`) is not met: deferred to S6a with open item 35 (D-082, P9 b).
3. **Regression on the existing exposed tests.** The clinical sheet (L1, L5v) and the device-log flawed document and clean twin (L5v) on current code, scored with `tools/score_corpus.py`: clinical location 5 of 5, reason confirmed 4 of 5, false positives 0 (L5v); device log location 3 of 10, reason confirmed 2 of 10, false positives 0; clean twin false positives 0. The catalogue test and both negotiation comparisons were cut by the spend order (D-077, P9 b; FOR_SECKIN.md).
4. **The development suite.** B3 on the suite was cut (D-073). B2 ran every bundle on the laptop at no cost (84 bundles, 0 failures; location and reason-confirmed recall: family 1 tests 24 of 28, probes 92 of 112; family 2 24 of 36, 90 of 144; family 3 22 of 22, 80 of 88; family 5 22 of 22, 82 of 88; family 6 22 of 26, 88 of 104; 0 false positives on every bundle; every twin 0). Family 4 (multi-round) is not measurable by B2 (R4, open item 28). The scorer's twin comparison cannot read a B2 run (open item 32).
5. **Adapter dry runs and baseline proofs.** On current code (after D-068): ContraDoc 2, SciTab 2, ContractNLI 3 merged agreements, FinDVer 1, CUAD 0 (D-073), below five documents per benchmark (a recorded cut, P9 b). L6 re-measured B3 on the five L4a documents under D-068 and on ContractNLI band B under D-076. L2's ten documents ran under earlier code and count for cost only. B1 ran on every dry-run item with both checkpoints; at full length on FinDVer it fits (18.6 and 20.9 GiB allocated of 24) but gave no parseable label. B2 ran on every built development bundle on the laptop. Labels and the official metrics are computed by the adapters on development items only (`external/s05/labels/`, ignored).
6. **Fix and re-run.** INC-011 to INC-023 (private). Product fixes in S5: D-061 (general fixes from L2), D-063 (sdpa one shot for the producer and B1), D-066 (scoring a semantically incomplete run), D-068 (model answers on uncomputable plans kept as model-written records; verified by L5v, D-070), D-076 (a phase above the scheduler bound runs as waves; INC-019; re-run in L6), D-078 (adapters: section 5.3's over-context exclusion with S-7, the rule-id map adopted), D-079 (every child process on the controller path starts with no window; check 292). Test-infrastructure: checks 229 and 233 (INC-017), check 222 restores the launcher byte for byte (INC-022). Not fixed in S5: INC-023 (open item 35).
7. **Diagnostics.** (a) The clean twin draws more records than the flawed document because the model answers uncomputable plans (D-068 path), not because of a computed finding: twin 0 Python records and 10 model records, all marked and none an amendment. (b) Empty extractions: the compact extraction contract accepts a claim only by an id written in the span, and no real document carries one, so every reply that wrote a claim was refused (open item 30). (c) The classifier gave one label on the clinical sheet because every extraction it saw was empty; it is not a classifier fault. (d) Check 232's two items verified on saved replies: the deepening cap holds (never reached: at most one finding per run) and every amendment keeps its typed record (10 of 10). Side finding: amendments with no REF id raise validator errors (open item 31).
8. **Model-text review** (sample fixed before reading; correct, partly, wrong, empty, unverifiable): L1 1, 2, 7, 0, 0; L2 1, 9, 6, 4, 0; L3e 3, 1, 7, 2, 2; L4a 1, 3, 10, 1, 0; L5v 0, 3, 11, 0, 1; L4b 2, 2, 10, 1, 0; L6 1, 3, 11, 0, 0 (15 of 584 reply records; all three answers kept under D-068 were wrong: a sum relation on a unit with no figures, open item 34). The repeated pattern: the base PRACTICE_AUDITOR model answers VIOLATION on units that do not address the rule and ignores a rule's instruction to answer UNCERTAIN; under D-068 those answers are kept as model-written records, and the benchmark reader lets a model record decide an item, so B3 carries model-driven false flags. B3 is therefore also reported without model-written records (sensitivity S-8, D-080). The tuned B1 replies quote the source and were right or nearly right in the samples. **Seed deviation (D-080):** the plan derives each seed as int(SHA-256 of "<run folder name>:text-review") mod 2^63. The rule's value for the L4a folder name, which the L6 session folder shares, is 876901642167781849. L4a's recorded seed (6304522431124753139) came from the previous lead session (757d835b), and how it was derived is not recorded. The L6 review reused L4a's seed by the current lead's error, not by a choice. Both samples were fixed and recorded before any record was read, so each is a seeded random sample; they are kept, not redrawn (D-080, D-086).

**Limitation the S8 report must carry (S5 checker round 1, D-086).** D-069's acceptance test for D-068 could not fail on the thing it was meant to catch: it asked whether a D-068 record on the clean twin was scored as a false positive, but `tools/score_corpus.py` counts false positives over amendments only, and a D-068 record is never an amendment, so the criterion was blind to D-068 records. Read by the benchmark reader instead (which lets a model-written record decide an item), the clean twin in L5v carried 8 kept model-written records and 20 model-only relations (missing_field 11, sum_mismatch 9; D-070), each a false alarm on a document with no planted flaw, and the L6 review found all 3 sampled kept answers wrong. D-070's "verified" therefore means only that clinical recall did not fall and that no amendment changed; it does not show that D-068 records are right. Sensitivity S-8 (B3 and B4 with every model-written record absent, D-080, DEV-012) is the control for this. The frozen preregistration is not edited; the S8 report states this limitation beside the primary B3 result.
9. **Measurements.** Tables below.
10. **C0 and the frozen preregistration.** Section 12 settled from development outputs (D-078): the main reading agent pinned in VERSIONS.md, the rule-id map adopted, B1's checkpoint tuned by the written rule, B1 at full length fits, and item 14 (section 5.3's exclusion, now applied by the adapters). The B1 checkpoint rule read development scores (the parse rates tied, and the pooled development headline broke the tie), and D-066 settled how a semantically incomplete run is scored after B1 development scores already existed; both are disclosed (D-066, D-078, DEVIATIONS.md). CUAD (D-073) and FinDVer (D-078) left the S8 priority list; ContractNLI, SciTab and ContraDoc stay on the list, but S8 has one external benchmark, the ContractNLI pilot, plus B's three synthetic tests (D-081). Section 2 filled by the S4e item 2 rule (D-081): B's synthetic tests first (about 10.4 USD), then ContractNLI as a pilot of 12 to 13 documents; SciTab and ContraDoc get no sample. The span-part trigger is undecided and merged parts apply (D-083, DEV-013). Sensitivity S-8, B3 and B4 without model-written records (D-080, DEV-012). The final attack (D-084): a fresh checker, 1 CRITICAL, 7 SERIOUS, 7 MINOR, every item closed before the freeze; B's synthetic tests got preregistered scoring and an adapter, and one setup-failure rule covers B1 and B3. C0: run 1 agreed on every label set it could check; run 2 (with the B2 run folders run 1 lacked) agreed fully on ContractNLI, ContraDoc and SciTab, primary and S-1 to S-8; run 3, the last allowed, on the preregistration at `fc02e1d`, agreed fully on ContractNLI (476 items), ContraDoc (62) and SciTab (198), primary and S-1 to S-8, and on B's synthetic scoring (309 items) (D-085). Freeze at `1392d00`, recorded in VERSIONS.md: preregistration SHA-256 `f759527572ab7c9eca8bad2a5d8fd9100281387e5834a28c0b217d43f2f033f7`; C's scorer `049ae32b1a837e9bc4ecaf1947e32da19d465422ac845eec1641b9dd864b2a7f`; `docs/OUTPUT_FORMAT.md` read by C0 `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150`; `ROLE_C0.md` `5804490377df6ec9932744c8af022c2969bf4867c333e01df8f638ce2a6b861d`. DEVIATIONS.md holds DEV-001 to DEV-020. Section 4's smallest detectable difference cannot be computed from two or three development documents per benchmark; it is computed from the holdout sample.

   **C0 inputs (from each input folder's `MANIFEST.json`, kept in the lead session's scratch space; counts only).** Each folder held the preregistration, `docs/OUTPUT_FORMAT.md` (SHA-256 `07eea8f7...4150` in all three), the three metric texts (`METRIC_contractnli.md`, `METRIC_contradoc.md`, `METRIC_scitab.md`), the adapters' development labels (`adapter_labels/`, 94 files in 3 benchmark folders) and the run outputs (`outputs/`). Run 1 (manifest SHA-256 `4717aec0...ac8b`): preregistration SHA-256 (LF) `90e91e5c...e2ef`; 137 run folders in 47 groups: B1 ContractNLI 6, ContraDoc 33, SciTab 29; B2 15 per benchmark (5 documents, 3 folders each); B3 ContractNLI 5, ContraDoc 10, SciTab 9; `outputs/` 1,843 files. Run 2 (manifest `2b1873f8...53de`): the same preregistration hash (`90e91e5c...e2ef`); 127 run folders in 41 groups: B1 and B3 as run 1; B2 as the laptop run, the L4a subset and the second dry-run work folder (ContractNLI 11, ContraDoc 12, SciTab 12), the B2 run folders run 1 lacked; `outputs/` 2,018 files. Run 3 (manifest `2e163127...74f1`): the frozen preregistration hash `f7595275...f7f3` (`fc02e1d`); the same 127 run folders as run 2; added `docs/INPUT_FORMAT.md` (`47904fae...6e4e36`), `DEVIATIONS.md`, `SYNTHETIC_README.md` and `synthetic/` (870 files: the development suite, 10 tests, 60 bundles, 60 B2 run folders, 288 items, the 4 family 4 tests excluded; L5v, 3 tests, 3 keys, 3 B3 run folders of 186 files, 21 items; 55 synthetic adapter commands, 0 failed). Runs 1 and 2 carried a draft preregistration (`90e91e5c...`), run 3 the frozen one.

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

**Disk.** Recorded: the sealed asset archive, 13,149,972,480 bytes (13.1 GB) at every launch (`assets_transfer_archive.json`); the instance's free disk at hardware admission, about 1,410 GB (`hardware_admission.json`); and the run folder each B3 entry wrote, as downloaded (largest entry): L1 0.9 MB, L2 0.8, L3e 20.4, L4a 10.8, L5v 3.3, L4b 20.4, L6 17.8, L6m 0.6, L6s2 2.4; collected evidence archives per launch together: L1 1.3 MB, L2 24.9, L3e 15.2, L4a 13.7, L5v 5.7, L4b 14.0, L6 11.8, L6m 3.5, L6s2 1.5. Not recorded: the peak disk in use on the instance during a run (environment, wheels, model cache and run folder together); D-086 records it under P9 (e) with what would settle it.

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

Minutes per scored decision (section 2's second key): SciTab 2.3, ContraDoc 9.8, ContractNLI 3.7 (D-081). A band with no measured document is not measured; at S8c it takes the highest measured band's minutes (section 2, "Sizing from S5"). CUAD: not measured (D-073).

**Exposed tests (L5v, B3 workload minutes):** clinical sheet 6.1, device log 17.2, clean twin 15.5; about 15 minutes a bundle with its entry (D-073). Cost per verified finding (findings that pass the scorer with reason confirmed): L1 0.49 USD over 4, about 0.12 USD; L5v 1.31 USD over 6 (clinical 4, device log 2), about 0.22 USD. For the benchmarks (correct FLAG items) it is not recorded: S5 computed no development score for that purpose (D-086, P9 e).

### Purpose line (Annex B.1)

Every analyser report of an S5 launch has the purpose on line 1 (`Purpose: <purpose>`) and "Exposed test, development only." on line 2: checked on all 47 analyser reports (L1; every batch entry of L2, L3e, L4a, L5v and L4b; the L6m session and its two entries; L6s2; L6m and L6s2 analysed at checker round 1). The reading recorded (D-086): two lines at the head of the report satisfy Annex B.1's "at the top". One gap found in the check: the session-level `RUN_REPORT.md` of the batch launches L2, L3e, L4a, L4b and L5v is not an analyser report; it holds only the model-text review section (written by the review step, the full review being `MODEL_TEXT_REVIEW.md` beside it) and has no purpose line. The purpose and exposed lines of those launches are in each entry's report. L6 has no analyser report: it was interrupted by the 18:15 stop before its session collection (D-079); its entries' evidence is used from the downloaded run folders.

### Usage at each launch (launch gate: five-hour below 70 percent, seven-day below 95 percent)

| Launch | Launched (+0300) | Five-hour (percent) | Seven-day (percent) | Read at (UTC) | Source |
|---|---|---|---|---|---|
| L1 | 28 Oct 12:51 | 2 | 1 | 28 Oct 09:31, 20 minutes before the launch | the previous lead's `docs/loop/private/handoff/HANDOFF_20261028-1231.md` |
| L2 | 28 Oct 14:53 | not recorded at launch | not recorded at launch | | the previous lead's handoffs `HANDOFF_20261028-1345.md` to `HANDOFF_20261029-0417_state.md` repeat the 09:31 UTC reading unchanged |
| L3e | 28 Oct 19:24 | not recorded at launch | not recorded at launch | | as L2 |
| L4a | 28 Oct 23:19 | not recorded at launch | not recorded at launch | | as L2 |
| L5v | 29 Oct 03:04 | not recorded at launch | not recorded at launch | | as L2 |
| L4b | 29 Oct 11:38 | 2 | 16 | 29 Oct 08:37 | the current lead's session |
| L6 | 29 Oct | 15 | 20 | 29 Oct 12:21 | the current lead's session |
| L6s | not launched | | | | |
| L6m | 29 Oct | 8 | 23 | 29 Oct 16:30 | the current lead's session |
| L6s2 | 29 Oct | 10 | 23 | 29 Oct 17:18 | the current lead's session |

Every recorded reading is far below both limits. For L2 to L5v no reading taken at the launch is recorded; the last one recorded before each (2 and 1 percent) was then hours old.

## Decisions

`docs/loop/DECISIONS.md`, D-055 to D-086:

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

## Bound controller files and pinned functions changed in S5

- **Controller lane** (B1 arm, B3-only batches, per-entry evidence past the soft budget, the sealed B1 argument check): `tools/ordinary_final_run.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`. The L1 bundle was sealed and launched before this merge.
- **B1 attention lane and the join lane** (B1 kernel, B1 passes, staging): `tools/ordinary_final_run.py`. D-061 and D-063 changed it again (PREFILL-E).
- **Hidden-window lane** (D-079, HIDDEN-A, check 292): six of the 11 bound names: `tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`, `tools/lambda_experiment_provider.py`, `tools/run_remote_experiment.py`.

Every bundle sealed before each of these merges refuses with `Controller source changed` and must be resealed (CONTROLLER-BINDING); L6m and L6s2 were resealed after the hidden-window merge. Pinned pipeline functions: one reference amendment in S5, recorded in both `benchmark/fixtures/multi_round_baseline_contract.json` and `benchmark/fixtures/topology_reference_contract.json` (`reference_amendments`, 2026-10-29, D-068): `_paired_convention_review` from `c849c3bc...` to `ea86ffc1...`. The waves fix (D-076) left `scripts/pipeline.py` unchanged.

## Checkers

**Round 1 (2026-10-29 about 22:30 +0300).** No CRITICAL. Adversarial: 3 SERIOUS (A1 D-069's acceptance could not detect D-068 records, because the scorer counts false positives over amendments only; A2 side gates not recorded for the merges `8ac7a60`, `8c2392d` and `70596c6`; A3 pinned-function amendment completeness to be shown by `test_reference_ast_contract` at the loop/s05 tip) and 6 MINOR (A4 the B1 checkpoint rule read development scores and D-066 came after B1 scores; A5 S8 has one external benchmark; A6 the FinDVer figure is an estimate; A7 the review seeds; A8 the commits where check 256 failed; A9 this section). Completeness: 8 gaps (C1 no model-text review of L6m and L6s2; C2 and C3 item 9 figures not tabulated; C4 C0 inputs not recorded; C5 the purpose line and the unanalysed L6m and L6s2; C6 usage readings per launch; C7 BUDGET.md actuals, the L6s row, the closing line and stray cells; C8 the close). Claims: 4 MINOR (H1, the same as C7; H3 L5v forecast rounding; H4 a format-hash row in the wrong VERSIONS table; H5 this report's commit counts). Closed in the records: A1 (limitation below item 8, D-086), A4, A5 (item 10), A6 (D-086, SELECTION.md note), A7 (item 8, D-086), A8 (Gate), C2 and C3 (item 9 tables; the figures not recorded in D-086 under P9 e), C4 (item 10), C5 (the reading; L6m and L6s2 analysed), C6 (usage table), C7 and H1 (BUDGET.md), H3 (BUDGET.md, launch table), H4 (VERSIONS.md: the row moved, content unchanged), H5 (top of this report). A2, A3, C1 and C8 are the lead's.

**Round 2** [pending]

## Gate

Per-commit chunked gates in the lead worktree (the gate's own CHECKS in foreground chunks, INC-016), each compared with the worktree baseline: at each recorded gate the non-pass set was the worktree baseline, apart from the check 256 flake below (D-062, D-064, INC-017, INC-021); the checks S5 added (285 to 292) pass in their lanes and at the lead's gates. The server checks ran in the loop venv. Check 256 fails now and then inside a long run and passes alone (INC-013, INC-021, open item 33; traced in S6a). In S5's chunked gates it failed ("sensitive health imported a model probe while inactive") three times, each inside the long chunk that holds it, and passed alone each time: at `8c2392d` in the chunk 200 to 277, then PASS alone and in the range 200 to 256 (logs `gate_logs/s05_8c2392d/c2.log`, `c256.log`, `c200_256.log`); at `ee2f1ed` in the chunk 200 to 277, then PASS alone right after (recorded in INC-021's recurrence note; the solo log was not kept); at `2b50067` in the chunk 190 to 260, then PASS alone (`gate_logs/s05_2b50067/c2.log`, `c256.log`). It passed inside the chunk at `18eee21`, `70596c6`, `ee8fa6a` and `fc02e1d`. Earlier, in S5's full gate at `1c4daac`, it failed once and passed alone (INC-013). INC-022 is fixed: check 222 restores `shimmer.sh` byte for byte, so the gate no longer changes the tree. INC-017 (checks 229 and 233 after D-068) closed at `cbcceac`. The merge gate on the loop branch runs at the stage close.

## Count line

21 named (spec items 1 to 10 and the 11 exit criteria), 15 done, 5 not now, 1 at close.

- **Done.** Items 1, 6, 7, 8, 9, 10. Exit criteria: smoke run; regression scored (with the recorded cut); development suite and adapter dry runs (B2 only and the recorded cuts); B1 and B2 proven; every failure classified; measurements recorded; spend within 24 USD; C0 in full agreement; preregistration frozen.
- **Not now (P9 b, each in DECISIONS.md and FOR_SECKIN.md).** Item 2 and its exit criterion: the multi-round health criterion (outcome `reviewed`) is not met (D-082, open item 35, S6a). Item 3 in part: the catalogue test and both negotiation comparisons (D-077). Item 4 in part: B3 on the development suite (D-073). Item 5 in part: CUAD with no output and fewer than five current-code documents per benchmark (D-073).
- **At close.** Checkers closed, stage merged, tag `loop-s05-v1`.

## Stage boundary

No loop instance is running: the reaper's reading at 19:11:59 UTC on 29 October listed 0 instances, with total spend 20.99 USD (instances 20.64, storage share 0.35). No role session and no lane runs. The asset copy `shimmer-filesystem` stays as the operator created it. The system disk had 37.6 GB free at 22:14 +0300, above the 30 GB floor.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
