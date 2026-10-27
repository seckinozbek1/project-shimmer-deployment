# Test change requests

This is the request log for **exposed** tests (Annex B.6 of the loop specification of 27 October 2026). An exposed test is one the builder has seen: every test under `benchmark/corpora/` is exposed, and so is every tuning dataset in this repository. Exposed tests are used for development and regression only, never as sealed evidence.

Nothing here changes a test. A test is never edited in place after a result has been seen (Annex A, 11.9). A request is decided later, by the operator, or during the 27 October loop by the loop under Annex B.9 (each such decision is recorded in `docs/loop/DECISIONS.md` and can be overruled). An approved change makes a new test version under a new name, or retires the old version in place with a `RETIRED.md` file; the folder never moves and its results stay as they were (Annex B.5). Requests about **sealed** tests never go here: they live in the scorer's own folder.

## Fields of an entry

- **Id**: `TCR-NNN`, never reused.
- **Date**: when the request was logged.
- **Test and version**: the folder, and the version or commit it refers to.
- **What was noticed**: one or two plain sentences.
- **Evidence**: file and line, or commit, that shows it.
- **Who noticed it**: the session or person.
- **From a run's output?**: yes or no. Under Annex B.6 a request about an exposed test may come from a run's output; it is then marked so.
- **Proposal**: keep, retire in place, or write a new version.
- **Decision**: empty until decided; then the decision, who made it, and the `DECISIONS.md` reference.

## Review of every test folder (2026-10-27, loop stage S1)

| Folder | Verdict |
|---|---|
| `benchmark/corpora/negotiation_r2_to_r3` | request TCR-001 |
| `benchmark/corpora/negotiation_r3_to_r4` | request TCR-002 |
| `benchmark/corpora/clinical_reference` | request TCR-003 |
| `benchmark/corpora/device_log_review` | request TCR-004 |
| `benchmark/corpora/device_log_review_clean` | request TCR-005 |
| `benchmark/corpora/catalogue_records` | request TCR-006 |
| `benchmark/producer_coverage_amendment_v1` | request TCR-007 |
| `benchmark/producer_coverage_amendment_v2` | request TCR-008 |
| `benchmark/machine_adjudication_v1` | request TCR-009 |
| `tuning/auditor_external_relation_v1` | request TCR-010 |
| `tuning/second_tuning_eval_runtime_v2` | request TCR-011 |
| `benchmark/producer_coverage_amendment_v3`, `benchmark/machine_adjudication_v2`, `benchmark/first_tuning_experiment_v1`, `benchmark/first_tuning_review_cohort_v2`, `benchmark/task_semantics`, `benchmark/task_semantics_v2`, `benchmark/fixtures`, and every other folder under `tuning/` | no request: current, or a frozen record of a past experiment with no defect found in this review |

## Requests

### TCR-001. `negotiation_r2_to_r3`: the key and the labels measure the corpus, not the capability (issue #14)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/negotiation_r2_to_r3`, as at commit `f31eff4`.
- **What was noticed**: an independent check found 2 of the 19 recorded comparisons false about the actual negotiation (one bonus is the earlier bonus plus a lump sum, so nothing was withdrawn and the same money is counted twice). One author wrote the labels in both documents, the mandate and the key, against a mechanism that compares exactly those labels. A probe that reworded only the later labels turned 13 records into 15, twelve of them false absences.
- **Evidence**: `docs/history/README_PRE_ROUTING_AUDIT.md`, around lines 2998 to 3011.
- **Who noticed it**: the operator's independent verification, recorded in that document; logged here by the loop lead.
- **From a run's output?**: partly (the probe result is a run output).
- **Proposal**: write a new version whose labels and key are prepared independently of the mechanism (or retire this version in place if no new version is made). It shares one document with TCR-002.
- **Decision**:

### TCR-002. `negotiation_r3_to_r4`: same defects as TCR-001, shared material (issue #15)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/negotiation_r3_to_r4`, as at commit `f31eff4`.
- **What was noticed**: it is built the same way as TCR-001 by the same author, and it shares the `2024_10_19` offer document with it, so the two are not independent tests.
- **Evidence**: the two `context/` folders hold a document with the same dated name; `docs/history/README_PRE_ROUTING_AUDIT.md` around lines 2289 to 2299 and 2998 to 3011.
- **Who noticed it**: the loop lead, from the repository records.
- **From a run's output?**: no.
- **Proposal**: decide together with TCR-001; if both are kept, count them as one test, never as two independent ones.
- **Decision**:

### TCR-003. `clinical_reference`: a convention was changed after results were seen (issue #16)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/clinical_reference`, the version used from run v8 on.
- **What was noticed**: the CONV-L02 scope declaration was added after the v7 results were seen, and the v8 result reflects it. Under Annex A 11.1 that path is now closed; the test is exposed in any case.
- **Evidence**: `docs/fix/ORDINARY_FINAL_V8_RUN_RESULTS.md`, around line 94; `docs/fix/ORDINARY_FINAL_V8_CORRECTIONS.md`, around line 106.
- **Who noticed it**: recorded in the 26 October evaluation (Annex A, 11.1); logged here by the loop lead.
- **From a run's output?**: yes (the change followed the v7 output).
- **Proposal**: keep as a development and regression test, with its version history stated wherever its results are quoted; no sealed use.
- **Decision**:

### TCR-004. `device_log_review`: edited in place after a run (issue #17)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/device_log_review`, as changed by commit `139083a`.
- **What was noticed**: after a run, CEDAR was declared out of a rule's scope and the key was corrected to the rule, in place.
- **Evidence**: `docs/fix/PROTOTYPE_CHECKPOINT.md`, around line 212 (commit `139083a`); `docs/fix/COST_AND_DURATION_ANALYSIS.md`, around lines 151 and 345.
- **Who noticed it**: recorded in the 26 October evaluation (Annex A, 11.1); logged here by the loop lead.
- **From a run's output?**: yes.
- **Proposal**: write a new version (or retire this one in place), so that the results before and after the edit are not read as one test.
- **Decision**:

### TCR-005. `device_log_review_clean`: the clean twin was edited in place after a run (issue #18)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/device_log_review_clean`.
- **What was noticed**: TEASEL's signature was added to the clean twin after a run.
- **Evidence**: `docs/fix/COST_AND_DURATION_ANALYSIS.md`, around lines 153 and 345.
- **Who noticed it**: recorded in the 26 October evaluation (Annex A, 11.1); logged here by the loop lead.
- **From a run's output?**: yes.
- **Proposal**: decide together with TCR-004; the flawed document and its clean twin change version together.
- **Decision**:

### TCR-006. `catalogue_records`: not run on current code since 10 September (issue #19)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/corpora/catalogue_records`.
- **What was noticed**: the last recorded run on it was on 10 September 2026, on code from before many later fixes; it scored 0 of 5 there.
- **Evidence**: `docs/fix/STEP_W0_REPORT.md`, around line 18 (run `20260910T215502Z`); `docs/history/README_PRE_ROUTING_AUDIT.md`, around line 3110.
- **Who noticed it**: the loop lead, from the repository records.
- **From a run's output?**: no.
- **Proposal**: keep; run it as a regression test on current code (the loop's S5 regression list includes it).
- **Decision**:

### TCR-007. `producer_coverage_amendment_v1`: superseded and recorded as NOT_READY (issue #20)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/producer_coverage_amendment_v1`.
- **What was noticed**: a tuning-curation dataset recorded as NOT_READY, with a reserve-selection governance failure; superseded by later amendments (v3 is the current one).
- **Evidence**: `docs/fix/RESUME.md`, around lines 74 to 91.
- **Who noticed it**: the loop lead, from the repository records.
- **From a run's output?**: no.
- **Proposal**: keep as a frozen record, and list it as superseded in a retired-tests register rather than adding a file inside a folder whose contents may be hash-bound.
- **Decision**:

### TCR-008. `producer_coverage_amendment_v2`: superseded, all labels quarantined (issue #21)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/producer_coverage_amendment_v2`.
- **What was noticed**: every candidate packet is quarantined because a target-reading regression ran before the label freeze; the record says not to use these labels for training.
- **Evidence**: `docs/fix/RESUME.md`, around lines 54 to 70.
- **Who noticed it**: the loop lead, from the repository records.
- **From a run's output?**: no.
- **Proposal**: as TCR-007.
- **Decision**:

### TCR-009. `machine_adjudication_v1`: superseded by v2 (issue #22)

- **Date**: 2026-10-27.
- **Test and version**: `benchmark/machine_adjudication_v1`.
- **What was noticed**: the first blinded machine review was recorded NOT_READY and was followed by a second review (v2).
- **Evidence**: `docs/fix/RESUME.md`, around lines 95 to 148.
- **Who noticed it**: the loop lead, from the repository records.
- **From a run's output?**: no.
- **Proposal**: as TCR-007.
- **Decision**:

### TCR-010. `tuning/auditor_external_relation_v1`: superseded by v2 (issue #23)

- **Date**: 2026-10-27.
- **Test and version**: `tuning/auditor_external_relation_v1`.
- **What was noticed**: a second version of the same external relation data exists (`tuning/auditor_external_relation_v2`, with its own report `docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V2.md`).
- **Evidence**: the two folders and the two data reports named in `.gitattributes`.
- **Who noticed it**: the loop lead, from the folder names and records; the reason for v2 was not re-read in this review.
- **From a run's output?**: no.
- **Proposal**: as TCR-007, after confirming from the v2 report that v1 is superseded.
- **Decision**:

### TCR-011. `tuning/second_tuning_eval_runtime_v2`: superseded by v2.1 (issue #24)

- **Date**: 2026-10-27.
- **Test and version**: `tuning/second_tuning_eval_runtime_v2`.
- **What was noticed**: a nullability fix produced v2.1 (`tuning/second_tuning_eval_runtime_v2_1`, `docs/fix/EVALUATION_RUNTIME_NULLABILITY_FIX.md`).
- **Evidence**: the two folders and the fix report named in `.gitattributes`.
- **Who noticed it**: the loop lead, from the records.
- **From a run's output?**: no.
- **Proposal**: as TCR-007.
- **Decision**:
