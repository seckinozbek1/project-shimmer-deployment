# S5 report: development runs on Lambda

Stage S5 of the autonomous loop of 27 October 2026, on branch `loop/s05`, created from the loop branch at `ea1c0d5` (S2, S3 and S4 merged and tagged). The lead worked in `.claude/worktrees/s05-lead`. Opus, medium effort from 28 October 2026 (Annex D, D-S11). Every run in this stage is a development run on exposed material: its purpose line and "exposed test, development only" head its report (Annex B.1). The lead session changed once: session 757d835b led S5 until it stopped at 05:11 +0300 on 29 October after an automatic compaction; session f3d23d40 took the released lock at 11:00 +0300 and ran a restart check (14 items, D-071, D-072). The operator stopped the laptop once, at about 18:15 +0300 on 29 October (D-079). On the branch: 90 commits after `ea1c0d5`, 76 files changed, 14,238 lines added and 458 removed (`git diff --stat ea1c0d5..HEAD`).

## What was done

### Launches (all A10 in us-east-1 at 1.29 USD an hour, read live; all asset copies MATCH from L1 on)

| Launch | Content | Forecast (USD) | Actual minutes | Actual (USD) | Outcome |
|---|---|---|---|---|---|
| L1 | smoke: the clinical sheet | 1.54 | 23 | 0.49 | first measured MATCH (no 37-minute upload); execution passed |
| L2 | ContraDoc 5, SciTab 5, B3 then B1 (five passes) | 5.62 | 148 | 3.18 | every B3 entry failed (out of memory once, a crash, eight semantically incomplete); every B1 entry passed |
| L3e | the E evidence run (D-061, D-062) | 2.77 | 157 | 3.38 | E missed its declared threshold; option A adopted (D-063) |
| L4a | ContraDoc 2, SciTab 2, ContractNLI merged 1, B3 under A, B1 base and tuned | 6.04 | 121 | 2.60 | no out-of-memory; B3 semantically incomplete; B1 passed |
| L5v | D-068 verification: the clinical sheet and the device-log pair, B3 only | 1.27 | 61 | 1.31 | D-068 kept (D-070) |
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
8. **Model-text review** (sample fixed before reading; correct, partly, wrong, empty, unverifiable): L1 1, 2, 7, 0, 0; L2 1, 9, 6, 4, 0; L3e 3, 1, 7, 2, 2; L4a 1, 3, 10, 1, 0; L5v 0, 3, 11, 0, 1; L4b 2, 2, 10, 1, 0; L6 1, 3, 11, 0, 0 (15 of 584 reply records; all three answers kept under D-068 were wrong: a sum relation on a unit with no figures, open item 34). The repeated pattern: the base PRACTICE_AUDITOR model answers VIOLATION on units that do not address the rule and ignores a rule's instruction to answer UNCERTAIN; under D-068 those answers are kept as model-written records, and the benchmark reader lets a model record decide an item, so B3 carries model-driven false flags. B3 is therefore also reported without model-written records (sensitivity S-8, D-080). The tuned B1 replies quote the source and were right or nearly right in the samples. **Seed deviation (D-080):** the plan derives each seed as int(SHA-256 of "<run folder name>:text-review") mod 2^63. L4a's recorded seed (6304522431124753139) does not match that rule for its folder name (876901642167781849), and the L6 review, whose session folder has the same name, was given L4a's seed. Both samples were fixed and recorded before any record was read, so each is a seeded random sample; they are kept, not redrawn.
9. **Measurements.** Tables below.
10. **C0 and the frozen preregistration.** Section 12 settled from development outputs (D-078): the main reading agent pinned in VERSIONS.md, the rule-id map adopted, B1's checkpoint tuned by the written rule, B1 at full length fits, and item 14 (section 5.3's exclusion, now applied by the adapters). CUAD (D-073) and FinDVer (D-078) left the S8 priority list; ContractNLI, SciTab and ContraDoc stay. Section 2 filled by the S4e item 2 rule (D-081): B's synthetic tests first (about 10.4 USD), then ContractNLI as a pilot of 12 to 13 documents; SciTab and ContraDoc get no sample. The span-part trigger is undecided and merged parts apply (D-083, DEV-013). Sensitivity S-8, B3 and B4 without model-written records (D-080, DEV-012). The final attack (D-084): a fresh checker, 1 CRITICAL, 7 SERIOUS, 7 MINOR, every item closed before the freeze; B's synthetic tests got preregistered scoring and an adapter, and one setup-failure rule covers B1 and B3. C0: run 1 agreed on every label set it could check; run 2 (with the B2 run folders run 1 lacked) agreed fully on ContractNLI, ContraDoc and SciTab, primary and S-1 to S-8; run 3, the last allowed, on the preregistration at `fc02e1d`, agreed fully on ContractNLI (476 items), ContraDoc (62) and SciTab (198), primary and S-1 to S-8, and on B's synthetic scoring (309 items) (D-085). Freeze at `1392d00`, recorded in VERSIONS.md: preregistration SHA-256 `f759527572ab7c9eca8bad2a5d8fd9100281387e5834a28c0b217d43f2f033f7`; C's scorer `049ae32b1a837e9bc4ecaf1947e32da19d465422ac845eec1641b9dd864b2a7f`; `docs/OUTPUT_FORMAT.md` read by C0 `07eea8f738c08ab4b7fd2efbf0e345ff0852c9c175c842e8054481108e014150`; `ROLE_C0.md` `5804490377df6ec9932744c8af022c2969bf4867c333e01df8f638ce2a6b861d`. DEVIATIONS.md holds DEV-001 to DEV-020. Section 4's smallest detectable difference cannot be computed from two or three development documents per benchmark; it is computed from the holdout sample.

### Item 9: measurements (development, exposed; one run each)

Sources: billed minutes and cost from the ledger (`BUDGET.md`); workload minutes from each entry's `batch_workload_<n>_timing.json` (or `ordinary_workload_timing.json` for a single bundle); peak GPU memory in use and peak process memory from each B3 entry's `logs/model_telemetry.jsonl` (decimal GB); B1 peak allocated memory from `b1_summary.json` (GiB); reply records counted in `audit/model_replies/`. L6m and L6s2 evidence was not extracted from its archive, so their memory and call figures are not recorded here.

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
| L6m | 46 | 29.6 (16.2 and 13.4) | 16.4 | 0.99 | not recorded | not recorded | not recorded |
| L6s2 | 26 | 9.1 | 16.9 | 0.56 | not recorded | not recorded | not recorded |

Billed minus workload is the session overhead plus each entry's transfers and checks. L1's phase timings: workload 7.6, asset-copy probe 3.2 and use 0.3, wheels 1.3, support transfer 1.1 minutes; the other launches' phase split is not tabulated. Model calls by agent, disk per run and seconds per B1 call are not tabulated (reply records stay in the run folders). B3 judging calls on ContractNLI: about 12.5 seconds a call (L4a, D-073) and 14.6 seconds a plan (L4b, D-077).

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

**Exposed tests (L5v, B3 workload minutes):** clinical sheet 6.1, device log 17.2, clean twin 15.5; about 15 minutes a bundle with its entry (D-073). Cost per verified finding (findings that pass the scorer with reason confirmed): L1 0.49 USD over 4, about 0.12 USD; L5v 1.31 USD over 6 (clinical 4, device log 2), about 0.22 USD. For the benchmarks (correct FLAG items) it is not recorded: S5 computed no development score for that purpose.

## Decisions

`docs/loop/DECISIONS.md`, D-055 to D-085:

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

## Bound controller files and pinned functions changed in S5

- **Controller lane** (B1 arm, B3-only batches, per-entry evidence past the soft budget, the sealed B1 argument check): `tools/ordinary_final_run.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`. The L1 bundle was sealed and launched before this merge.
- **B1 attention lane and the join lane** (B1 kernel, B1 passes, staging): `tools/ordinary_final_run.py`. D-061 and D-063 changed it again (PREFILL-E).
- **Hidden-window lane** (D-079, HIDDEN-A, check 292): six of the 11 bound names: `tools/cloud_run_common.py`, `tools/cloud_run_watchdog.py`, `tools/ordinary_final_cloud.py`, `tools/ordinary_final_bound_cloud.py`, `tools/lambda_experiment_provider.py`, `tools/run_remote_experiment.py`.

Every bundle sealed before each of these merges refuses with `Controller source changed` and must be resealed (CONTROLLER-BINDING); L6m and L6s2 were resealed after the hidden-window merge. Pinned pipeline functions: one reference amendment in S5, recorded in both `benchmark/fixtures/multi_round_baseline_contract.json` and `benchmark/fixtures/topology_reference_contract.json` (`reference_amendments`, 2026-10-29, D-068): `_paired_convention_review` from `c849c3bc...` to `ea86ffc1...`. The waves fix (D-076) left `scripts/pipeline.py` unchanged.

## Checkers

[filled at close]

## Gate

Per-commit chunked gates in the lead worktree (the gate's own CHECKS in foreground chunks, INC-016), each compared with the worktree baseline: at each recorded gate the non-pass set was the worktree baseline, apart from the check 256 flake below (D-062, D-064, INC-017, INC-021); the checks S5 added (285 to 292) pass in their lanes and at the lead's gates. The server checks ran in the loop venv. Check 256 fails now and then inside a long run and passes alone (INC-013, INC-021, open item 33; traced in S6a). INC-022 is fixed: check 222 restores `shimmer.sh` byte for byte, so the gate no longer changes the tree. INC-017 (checks 229 and 233 after D-068) closed at `cbcceac`. The merge gate on the loop branch runs at the stage close.

## Count line

21 named (spec items 1 to 10 and the 11 exit criteria), 15 done, 5 not now, 1 at close.

- **Done.** Items 1, 6, 7, 8, 9, 10. Exit criteria: smoke run; regression scored (with the recorded cut); development suite and adapter dry runs (B2 only and the recorded cuts); B1 and B2 proven; every failure classified; measurements recorded; spend within 24 USD; C0 in full agreement; preregistration frozen.
- **Not now (P9 b, each in DECISIONS.md and FOR_SECKIN.md).** Item 2 and its exit criterion: the multi-round health criterion (outcome `reviewed`) is not met (D-082, open item 35, S6a). Item 3 in part: the catalogue test and both negotiation comparisons (D-077). Item 4 in part: B3 on the development suite (D-073). Item 5 in part: CUAD with no output and fewer than five current-code documents per benchmark (D-073).
- **At close.** Checkers closed, stage merged, tag `loop-s05-v1`.

## Stage boundary

No loop instance is running: the reaper's reading at 19:11:59 UTC on 29 October listed 0 instances, with total spend 20.99 USD (instances 20.64, storage share 0.35). No role session and no lane runs. The asset copy `shimmer-filesystem` stays as the operator created it. The system disk had 37.6 GB free at 22:14 +0300, above the 30 GB floor.

## Effort

Opus, medium effort from 28 October 2026 (Annex D, D-S11).
