# Training method audit against D-505 and D-506

Written 12 November 2026 on lane/train-audit, cut from the loop tip (d07d9358). Read-only lane: no GPU, no
role folder, no benchmark key, no sealed or held-out data was opened, and nothing was run. Every statement
below comes from committed records (DECISIONS.md, LESSONS.md, the stage files, `docs/fix/AUDITOR_*`,
`tuning/*` file names and keys). Figures are quoted from those records, not re-measured. The `external/`
result files were not opened; where a claim rests on one, the record that cites it is named.

Status words: DONE (the step was done as written, with a record), PARTLY (something close was done, the gap is
named), MISSING (no record of it). "L-n" is docs/loop/LESSONS.md; "D-n" is docs/loop/DECISIONS.md.

## 0. The seven steps and the D-506 additions (D-505 at DECISIONS.md:5391, D-506 at :5405)

1. Data balanced, no overlap with any test or held-out set, proven with the leakage tool.
2. Data split into parts; training starts on the first part.
3. Measure on development items never trained on.
4. Analyse errors by kind.
5. Edge-case stress set built from those kinds, tested separately.
6. Next part chosen from the weak kinds.
7. Repeat until the development score stops rising; only then any gate or sealed test.

D-506: (H) a working half and a held-back half with the openings counted; (E) every tuning step follows the
same loop; (P) a power analysis per half.

## 1. Summary table

| Step | Judge (T, 2e) | Producer (attempt 1; attempt 2 prepared) | Auditor rule check (attempt 1, 2) | Auditor relation classifier (Auditor896 line) |
|---|---|---|---|---|
| 1 balance | DONE | PARTLY | DONE | DONE |
| 1 leakage tool | MISSING (text filter only) | MISSING (text filter only) | MISSING (by construction only) | MISSING (grouped checks only) |
| 2 parts | MISSING | MISSING | MISSING | PARTLY (HPO inner split only) |
| 3 dev unseen | PARTLY | DONE | DONE | DONE |
| 4 errors by kind | PARTLY | PARTLY | DONE | PARTLY |
| 5 stress set | MISSING | PARTLY | MISSING | PARTLY |
| 6 next part from weak kinds | MISSING | MISSING | PARTLY | MISSING |
| 7 repeat to plateau, then gate | MISSING | PARTLY | PARTLY | MISSING |
| H halves and openings | MISSING | DONE (never opened) | DONE | PARTLY |
| P power per half | PARTLY | PARTLY | MISSING | MISSING |

Gate and sealed separation, the second half of step 7, held in every training: none of them was tuned on gate
or sealed items, and D-422 (DECISIONS.md:4317) plus GATE_ATTEMPTS.md section 3 item 6 (line 189 onward) make it
a written rule. That part of step 7 is DONE everywhere. What is missing is the repeat-until-flat loop before it.

The pattern across all four: the loop ran as attempts separated by days and a bill, not as rounds of one
loop. Each attempt trains once, reads once and writes a lesson. There is no part-by-part training (step 2),
no stress set (step 5) and no part chosen from error kinds (step 6) anywhere.

## 2. The judge (T attempt 1, then 2e)

Records: L-2, L-3, L-4, L-11 (LESSONS.md:12, 19, 26, 75); D-294 (DECISIONS.md:2787); D-370 (:3603); D-371 (:3615);
D-373 (:3646); `docs/loop/stages/TRAIN_JUDGE_DATA.md`; `docs/loop/stages/C_BAR.md`.

| Step | Status | Evidence |
|---|---|---|
| 1 balanced | DONE | Label share per (padded, length band) cell equal within rounding, and a source table with the quarter rule on benchmark-family share (21.1 percent): TRAIN_JUDGE_DATA.md:259-291. Pair Yes is 20 percent by design (:237). |
| 1 leakage | MISSING | Overlap was a text filter: 8-word runs against the development files and the 47 moved ContraDoc documents, 0 shared (TRAIN_JUDGE_DATA.md:292-295). The same file states "Overlap with test splits is still not checked, by rule" (:295, and :9-12). GATE-LEAKAGE-A did not exist for this build (D-S102); no `check` result on the 2e mix exists. D-392 lists training sets missing from the leakage list (DECISIONS.md:3887). D-510 shows the 2e mix is in the fingerprint scan (DECISIONS.md:5449), which is the start of proof, but no overlap result against the gate set is recorded. |
| 2 parts | MISSING | One run of 710 updates over one file; "Checkpoints .5 and 1" are two stops of one pass, not two data parts (the "Unchanged from T" list, TRAIN_JUDGE_DATA.md:400-404). |
| 3 dev unseen | PARTLY | Half A (30 ContraDoc documents, 15 SciTab tables) was never a training row, but it is the half used for thresholds, selection and the success rule, so it is labelled IN-SAMPLE by the file itself (TRAIN_JUDGE_DATA.md:359-366). A 592-row in-distribution held-out loss exists (:277-290), which cannot see text shape (:83-85). |
| 4 errors by kind | PARTLY | L-11 and L-3 give causes by kind (claim rows moved SciTab; ContraDoc capped by what the pair proposer reaches, 5 of 13 reachable; more right flags came with more false ones). No per-kind error table for 2e is recorded. `tools/miss_diagnosis.py` classifies misses of runs, not of a training. |
| 5 stress set | MISSING | The figure-changed twins are training rows (TRAIN_JUDGE_DATA.md:237-245). No separate stress set was built or tested. |
| 6 next part from weak kinds | MISSING | L-11's "Next changed" names harder same-document No pairs, a kind-based choice, but the next recorded attempt, 2f, is a calibration procedure, and it never ran (D-371, :3626; D-373, :3646). |
| 7 repeat to plateau | MISSING | L-11 says "held-out accuracy was still rising at 710 updates, so the run was not trained to saturation". The stop was the pre-written in-sample success rule, not a plateau. The separation from the gate held (D-422). |
| H halves and openings | MISSING | "No held-out part exists for the judge": half B was read once for T (D-294) before the ledger existed and shaped 2e's recipe, so it is spent (TRAIN_JUDGE_DATA.md:336-346); HELDOUT_OPENINGS.md:14 says so. The 2e success is in-sample only and its confirmation is the system's fresh read (:361-366). |
| P power | PARTLY | Power is said in words: a .05 SciTab margin is two to three claims, no significance claimed (TRAIN_JUDGE_DATA.md:384-388); L-4 records the out-of-sample effect of about one document and power .40 to .47 on 100 documents (LESSONS.md:26-31). No per-half simulation was run for the judge; `docs/loop/stages/gate_set_power/` and D-372 (power .17 and .27 for the interim set) cover the gate set, not the working and held-back halves. |

### What the next judge round must adopt

1. Build a new, never-read development reserve first. Half B is spent, so a new working half and a new held-back
   half must come from benchmark material not reserved for the gate or sealed tests, checked with
   `gate_leakage.check` (D-506 item 3). Name both files by digest in a commit before any training.
2. Run the leakage tool on the training mix itself (`fingerprint` of the mix, `check` against the gate set,
   the quick subset and the fresh set), and record counts. Replace the 8-word text filter as the only proof.
3. Train in parts: part 1 is a share of the 2e mix balanced by label and source; read the working half after
   it; do not train the whole 710 updates first.
4. After each part write the error table by kind on the working half only: pair Yes missed, pair No flagged,
   claim holds, not met and cannot-be-settled, by length band and by source family. Make it a tracked tool
   output, not a lesson paragraph.
5. Build the stress set from those kinds (figure-changed pairs that truly do not contradict, same-document
   No pairs, claims whose selected cells omit the deciding row, not-enough-info claims) and test it separately.
   It is never a training row.
6. Choose part 2 from the weak kinds only, and say which kinds in the commit that names it.
7. Stop when the working half rises by less than the pre-written minimum for two parts in a row, then open the
   held-back half once and count the opening. If the working half rose and the held-back did not, report
   fitting, not progress (D-506 item 1).
8. State a power figure for each half with the simulator, at the step size one round gives and at the gate's
   10-point and 5-point margins; enlarge the reserve if either half cannot detect them.

## 3. The producer (attempt 1; attempt 2 prepared, held)

Records: L-12 (LESSONS.md:82); D-370 (DECISIONS.md:3603, :3607); D-372 (:3637); `docs/loop/PRODUCER_TRAINING_PLAN.md`
sections 3, 4, 8 (here, on the loop branch) and section 9 (lane/producer, bab93c5c). Attempt 2 is a replay-only
test of attempt 1's half checkpoint and, in the records read, was sealed-held and had not run (D-385 and
D-S105 items at DECISIONS.md:3834 and :3854); I found no record of it running.

| Step | Status | Evidence |
|---|---|---|
| 1 balanced | PARTLY | Source shares are stated and capped: v3 336, GovReport 140, BillSum 100, QASPER 40, TAT-QA 40, FinQA 20; benchmark-family share 14.79 percent against the quarter rule (PLAN section 3 and 5a, lines 36-64, 108-118). Refusals 64 of 676. No balance statement over reply status or span count per source is recorded as a gate. |
| 1 leakage | MISSING | A carrier paragraph sharing an 8-word run with any test item is dropped, and `producer_train.check` refuses a training payload inside a test prompt (PLAN section 3 and the end of 8.1). GATE-LEAKAGE-A was not applied; D-392 lists checkpoint 168's set as missing from the leakage list (DECISIONS.md:3887). |
| 2 parts | MISSING | 676 rows, two passes, one run. The half checkpoint at update 169 is a stop of the same run (PLAN section 9.3). |
| 3 dev unseen | DONE | DEV-84, the 52 saved failing partitions and 100 fresh spans, none a training row (PLAN section 4 and 8.1 table). DEV-84 and the 52 had been read before; the plan says so. |
| 4 errors by kind | PARTLY | D-370 traced 168's 9 invalid DEV rows into 5 correct refusals and 4 wrongful ones, and the candidate's 4 into 3 exactly right (DECISIONS.md:3607; L-12). That is one analysis, on one read, not a recurring table. Overfitting to the constructed form is inferred from loss .0018 and rows trading 11 to 9. |
| 5 stress set | PARTLY | The 52 failing partitions (R1) and the 180-prompt roles file act as a failure set and a regression set, but they were built from earlier failures of 168, not from the candidate's error kinds (PLAN 8.1 table). |
| 6 next part from weak kinds | MISSING | Attempt 2 was chosen from the overfitting reading (test the half checkpoint), not as a new data part from weak kinds (L-12 "Next changed"). |
| 7 repeat to plateau | PARTLY | A success rule and a real-progress rule exist before any attempt (PLAN 8.2, 8.3), and the held-out part stays unopened until a tuning pass. There is no rule that repeats rounds until the working score stops rising. |
| H halves and openings | DONE | Fifty-two partitions and 100 fresh spans split by document: partitions 17 documents 6 and 11, fresh 70 documents 35 and 35, 0 on both sides (PLAN 8.1). Held-out opening is refused unless the committed HELDOUT_OPENINGS line exists (PLAN 8.1 "The held-out pass is built"). A held-out digest guard found and dropped one leaked partition (DECISIONS.md:3675). No opening has happened. What is not written: the rule that a working-half rise with no held-back rise is fitting; the plan reports pass or fail only (PLAN 8.2). |
| P power | PARTLY | `producer_score.smallest_passes` gives the smallest passing counts per alpha, for example (7,0), (9,1) at .0125 (PLAN 8.2 table), and the plan says a 26 to 52 row half shows only a large gain, "not shown at this size". These are minimum-margin counts, not a simulation of the gain one round gives. A partition half later fell to 25 rows (DECISIONS.md:3675). |

### What the next producer round must adopt

1. Apply the leakage tool to the training rows and the carriers, and record counts against the gate set, the
   quick subset and the fresh set, beside the existing 8-word filter.
2. Add a balance table over status (extracted, empty, refused), spans per request and source family, with a
   dominance limit written first.
3. Train in parts (for example three of about 225 rows) and read the working half (`partitions_tune`,
   `fresh_tune`) after each, instead of two passes over everything followed by one read.
4. After each part write the error table by kind (wrongful refusal, invented CLM id, dropped key, neighbouring
   span's ref, runaway list, wrong status) on the working half, from the saved replies, with the validator's
   own reasons.
5. Build the stress set from those kinds, from public carriers not used in training, and keep it out of
   training. Keep the 52 and the roles file as regression sets.
6. Choose the next part's rows from the weak kinds and write which in the commit.
7. Write the stop rule: the working half rises by less than a stated count for two parts in a row; then open
   the held-back half once (opening counted at .05 / 2^k), and state "working rose, held-back did not" as
   fitting.
8. Run a power simulation per half at the actual 25 to 35 row sizes, and enlarge the development material from
   public validation splits if a half cannot show the margins in section 8.2 (the unused public carriers in
   PLAN section 3 are the source).

## 4. The auditor rule check (AUD_TRAIN5, attempts 1 and 2)

Records: L-10 (LESSONS.md:68); D-366 (DECISIONS.md:3565); D-367, D-368 (:3574, :3584); `docs/loop/stages/AUDITOR_RULE_CHECK_SUCCESS.md`;
`AUDITOR_RULE_CHECK_ATTEMPT_2.md`; HELDOUT_OPENINGS.md:12.

| Step | Status | Evidence |
|---|---|---|
| 1 balanced | DONE | Two mixes of 12,000 balanced NLI rows each (MultiNLI, WANLI, TabFact), balanced by answer and short (ATTEMPT_2.md, "The lesson of attempt 1"; D-366). Balanced training rows against an unbalanced measured part (158, 146, 94) is the cause the lesson found, so the balance step existed and also created the prior mismatch. |
| 1 leakage | MISSING | The held-out questions are ContractNLI development, and no training row comes from ContractNLI, by construction (SUCCESS.md:54-60); `auditor_train.check` refuses a question that is a training row (:30). The leakage tool was not run. The same file states the limit: halves share the 17 rules and the boilerplate (:54-60). |
| 2 parts | MISSING | Two mixes, each read at half and at full checkpoint of one run (D-366). |
| 3 dev unseen | DONE | Half A: 398 questions, 31 documents, split by document by SHA-256, every choice made on half A alone (SUCCESS.md:25-52). |
| 4 errors by kind | DONE | Per class: not_met F1 .42 to .62-.65, met recall .37 to .26-.32, 273 to 285 Unclear against 158 gold, mix and size ruled out (ATTEMPT_2.md, L-10). This is the best example of the step in the repository. |
| 5 stress set | MISSING | Nothing built from the met-into-Unclear kind. |
| 6 next part from weak kinds | PARTLY | Attempt 2 was chosen from the error kind, a calibration change (log-probability offsets), with no new training (L-10 "Next changed"). It is kind-driven but it is a decision-rule change, not a data part. |
| 7 repeat to plateau | PARTLY | Two attempts ran, attempt 2 after attempt 1's read. The stop was the half-B opening, not a plateau on half A. Attempt 2's half-A gain (.125) was in-sample, fitted where it was measured; the cross-validated figure was .115 (ATTEMPT_2.md:56-60; D-367). |
| H halves and openings | DONE | Half A and half B by document, half B digest named, read once, opening counted at k 1, alpha .025 (HELDOUT_OPENINGS.md:12; D-367, D-368). Half B failed. That is exactly the D-506 item 1 signal: the working half rose to .709 to .715 and the held-back half did not follow. It was read as "A's estimate did not generalise" (D-368). |
| P power | MISSING | "No out-of-sample effect exists yet, so no power figure is claimed" and "a real gain of about .05 may fail criterion 2" (SUCCESS.md:101-104). Half B is 30 documents, 391 questions. No simulation. |

### What the next auditor rule-check round must adopt

1. Run the leakage tool on the NLI mixes and on both halves against the gate set, quick subset, fresh set and
   the other half, and record counts. Do not rely on "no ContractNLI row" by construction.
2. Replace by-document-only halves by a split that also separates the 17 rules in part of the reserve (the file
   weighed and refused this for size, SUCCESS.md:54-60); the enlarged reserve in D-506 item 3 is what makes it
   affordable. A new held-back half of different agreements and rules is needed because half B is opened once
   already (k 1 spent, k 2 at .0125).
3. Train in parts and give the mix the measured part's answer prior as a stratum, so the trained argmax is not
   fitted to the wrong prior (the L-10 cause), instead of repairing it after by offsets.
4. Write the per-class error table (the L-10 analysis) after every part as a tool output.
5. Build the stress set from the weak kind: met answers that fall to Unclear, long sections, boilerplate-only
   sections, hypotheses with a negation. Test it separately.
6. Fit any offsets or thresholds on half A of the working part only, with 2-fold cross-validation reported
   beside the in-sample figure, and write the offsets before reading the held-back half.
7. Add a power figure per half before the next opening, at the stated .05 margin and at the part's own step.

## 5. The auditor relation classifier (the `tuning/auditor_*` line, Auditor896)

Records: `docs/fix/AUDITOR_CANONICAL_TUNING_RESULTS.md`, `AUDITOR_LINEAR_PROBE_RESULTS.md`, `AUDITOR_CLASSIFIER_LORA_RESULTS.md`,
`AUDITOR_OPTUNA_HPO_RESULTS.md`, `AUDITOR_FINAL_RETRY_RESULTS.md`, `AUDITOR_FAILURE_ROOT_CAUSE_ANALYSIS.md`,
`AUDITOR_EXTERNAL_RELATION_DATA_V1.md`, `AUDITOR_EXTERNAL_RELATION_DATA_V2.md`; `tuning/auditor_*` (experiment, split,
challenges, gates). These predate the loop (September 2026), so they cannot be faulted for missing a rule written
in November, but they are the auditor's own training history and D-505 names it.

| Step | Status | Evidence |
|---|---|---|
| 1 balanced | DONE | 448 per class, 1,792 TRAIN rows; length-matched bins, class-balanced selection units; a source-confound check that refused admission: "source identity still separates the two class families" and a provenance oracle reaching 75 percent, so V2 stayed `NOT_READY` (EXTERNAL_RELATION_DATA_V2.md:3-5, 30-45). |
| 1 leakage | MISSING | Grouped leakage checks and canonical-plan checks passed (CANONICAL_TUNING_RESULTS.md); the shared leakage tool did not exist, and D-392 lists "Auditor896's records" among the sets missing from the leakage list (DECISIONS.md:3887). |
| 2 parts | PARTLY | An HPO inner split (INNER_TRAIN 1432, INNER_VAL 360, seed 7, `tuning/auditor_optuna_hpo/split.json`), and checkpoints 448 and 896 of one run. Not sequential data parts. |
| 3 dev unseen | DONE | External DEV 200 and historical substantive DEV 48 (CLASSIFIER_LORA_RESULTS.md "Bound architecture and data"; `tuning/auditor_classifier_lora/experiment.json` gates). |
| 4 errors by kind | PARTLY | Per-class recall tables per checkpoint and population, OMISSION recall 1 of 12 on historical DEV, false-MATCH counts 29 of 200 and 10 of 48 (FINAL_RETRY_RESULTS.md:66 onward and :148). Root-cause work was spent on a numerical failure of the extraction, not on error kinds (FAILURE_ROOT_CAUSE_ANALYSIS.md). |
| 5 stress set | PARTLY | SHORTER and LONGER challenge subsets with their own gates (`challenge_gates` .7 in `tuning/auditor_classifier_lora/experiment.json`), built from a known length confound before training, not from the model's error kinds. |
| 6 next part from weak kinds | MISSING | "No further tuning ... was started" (FINAL_RETRY_RESULTS.md:7). |
| 7 repeat to plateau | MISSING | The plan fixes 896 updates, then a selection rule between two checkpoints; `quality_failure_stops_training` is false (`tuning/auditor_final/experiment.json`). Checkpoint 896 was selected although historical DEV failed (macro F1 .4576) because the rule is a tie-break among two (FINAL_RETRY_RESULTS.md:5, "Why896"). No protected test was run, which is correct. |
| H halves and openings | PARTLY | INNER_VAL "was adaptively used by HPO and is not an independent final test" (OPTUNA_HPO_RESULTS.md:3, 25); HOLDOUT and protected data were not opened. No opening ledger for this line, and no working half separate from the tuning half. |
| P power | MISSING | Not stated in any of the results files read. |

### What the next relation-classifier round must adopt

1. Run the leakage tool over the TRAIN, INNER_VAL, DEV and challenge rows against the gate and fresh sets, and
   record counts.
2. Replace the single fixed 896-update plan with parts and a development read after each, with a plateau stop.
3. Split the DEV material into a working half and a held-back half, with openings counted in HELDOUT_OPENINGS.
4. Build the stress set from the error kinds the model shows (OMISSION missed as MATCH, false MATCH) as well
   as the length challenge, and test it separately.
5. Choose the next part from the weak class: OMISSION data for the weak OMISSION recall, from material that
   passes the source-confound check.
6. State power per half; the 48-row historical DEV cannot show a class recall change of 8 points (1 of 12
   is one row).

## 6. Non-training tuning steps (D-506 item 2)

The same loop applies to prompts, evidence choice, thresholds, calibration and decoding settings. Each below is
read as one tuning step, with the steps that were done.

| Tuning step | Records | 3 dev unseen | 4 kinds | 5 stress | H halves | P power | Verdict |
|---|---|---|---|---|---|---|---|
| K1 thresholds, pairs .9 and cells .6 | D-477 (DECISIONS.md:5143); GATE_ATTEMPTS.md section 6 (:282-353); D-371 (:3615) | PARTLY | MISSING | MISSING | PARTLY | MISSING | Chosen by C_BAR's rule on G1 half A (30 documents, 45 claims), in sample; D-477 states the error rates are in sample (10 flagged, 9 right, 1 false; cells 10 flagged, 10 right) and that "half B did not confirm the pair value" (GATE_ATTEMPTS.md:336-337). No not-enough-info claim sits in half A (:334-335). It is run on the quick subset only, as steering, not as a claim (D-477; section 3 item 6, :189-233). D-371 had rejected the same thresholds as not coming from a calibration record, and the code gap that would refuse this is logged, not closed (DECISIONS.md:3627; D-478 finding 6, :5160). |
| Judge calibration 2f | D-371 (:3626-3627), D-373 (:3646) | MISSING | MISSING | MISSING | MISSING | MISSING | Written before it runs (procedure only); the first calibration "failed on a code defect, not on the judge" because order-control rows were fed in (D-373). It then waited for the gate set. Never ran. |
| D-S45 "either base + reason" | L-4 (LESSONS.md:26-31); D-297 (:2819); D-316 (:2991) | MISSING | MISSING | MISSING | PARTLY | PARTLY | The effect was chosen on the data that measured it: 6 wins, 2 losses of 30 in sample, out-of-sample about one document, power .40 to .47 on 100 documents. This is the case that created the power rule, and it is a clear example of what D-506 item 1 is for. |
| Contract-shaped decoding (DECODING-B) and VERIFIER's allowance | D-116 (:1011), D-132 (:1135), D-134 (:1157); CLAUDE.md DECODING-B | PARTLY | PARTLY | PARTLY | MISSING | MISSING | Developed on the failing saved prompts (the 52 partitions, the 22 failing auditor calls, the 8 VERIFIER prompts) and judged on the same prompts plus the 84 DEV rows (no interventions). The allowance 4,096 was chosen by replaying exactly the 8 prompts that failed at 2,048. This was read from the decision headings and the CLAUDE.md summary, not each decision in full. |

Cell selection (`config/cell_selection.json`), passage-pair selection (`config/passage_pairs.json`), the claim
tools block and the judge prompt forms were not audited here; each is a tuning step under D-506 item 2 and
needs the same table.

### What every later tuning step must adopt

1. A tuning step names its working half and its held-back half before any figure is read, in a commit, with the
   leakage result for both against the gate, quick subset and fresh sets.
2. A threshold or offset is fitted on the working half only, written down with its in-sample and
   cross-validated figures, and the held-back half is opened once per step with the opening counted. A
   threshold with no calibration record is refused in code (the gap D-371 and D-478 finding 6 name); build
   that refusal first.
3. After each tuning step, write the error table by kind and build the stress set from it. A prompt or
   evidence-choice change is tested on the stress set as well as the working half.
4. State power per half for the change the step is expected to make. Where a half is too small, enlarge the
   development set under D-506 item 3 before opening the held-back half.
5. Keep D-422: no configuration is chosen on the claim set or the sealed set; K1-style adoption is a separate
   decision on development evidence.

## 7. Items found and not fixed by this audit

- The record of whether the 2e training mix was run through `gate_leakage.fingerprint` or `check` was not
  found. D-510 shows it is among the scanned records. If a `check` result exists under `external/`, this audit
  could not read it (read-only lane, no `external/`).
- No record shows producer attempt 2 running. The records read end at its seal being held (DECISIONS.md:3854);
  later state is in the lane's branch, not on the loop tip.
- The older Auditor896 history is summarised from the results files' headers and tables, not from each of the
  roughly 25 `docs/fix/AUDITOR_*` documents. The verdicts above would not change on those files' known
  verdicts (`AUDITOR_TUNING_FAIL`, `AUDITOR_LINEAR_PROBE_FAIL`, `AUDITOR_CLASSIFIER_LORA_INDETERMINATE`,
  `AUDITOR_OPTUNA_HPO_CANDIDATE`, `AUDITOR_FINAL_COMPLETE` with checkpoint 896), but the per-line evidence is
  a sample.
