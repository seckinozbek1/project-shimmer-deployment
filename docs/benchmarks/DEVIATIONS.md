# Deviation log: external benchmarks

## Purpose

This file records every change to the benchmark design after the preregistration (`docs/benchmarks/PREREGISTRATION.md`) was first drafted, and every change to the code a benchmark result depends on (the adapters, the mapping, the scorer, or the pipeline behaviour an arm runs). Section 7 of the preregistration requires that each deviation is entered here before the change is applied, with a timestamp, its reason, and whether any holdout result had been seen. An entry is never edited after it is written; a later correction is a new entry that names the one it corrects.

Entries made before the freeze are part of the design that is frozen. Entries made after the freeze are reported beside every result they touch, with the result under both the frozen and the changed code where both were run (section 7).

## Fields

Each entry has these fields, in this order:

- **Id**: `DEV-NNN`, numbered from 001 in the order entered, never reused.
- **Entered**: date and time (system clock, with its offset) and the loop stage.
- **Decision**: the record in `docs/loop/DECISIONS.md` that made the choice.
- **What changes**: the preregistration sections and the code (files and functions) affected, and the arms.
- **Why**: the reason, in plain words.
- **Decided from**: what the choice was read from. Gold-free counts, a development score, a holdout result, or nothing measured.
- **Holdout result seen**: yes or no. Before S8 this is always no.
- **Development scores existing when decided**: which arms had development scores when the choice was made, and whether the choice read them.
- **Status**: `draft` (text written, not yet attacked by the final preregistration checker), `applied` (in the frozen text and code), or `deferred` (with the reason and what settles it).

## Entries

### DEV-001. A semantically incomplete B3 run is labelled from its records

- **Entered**: 2026-10-29 (system clock, +0300), loop stage S5, adapter lane `lane/s05-defect`.
- **Decision**: D-066 (`docs/loop/DECISIONS.md`).
- **What changes**: preregistration section 0 (run failure; the new term "semantically incomplete run"), section 3.5, section 4 (sensitivity list), section 5.1 (line 1, line 5 with its item-level exception, the paragraph "Incomplete documents", S-6, the counts the report gives), section 7 (reported), section 12 item 11 (the exception depends on it). Code: `benchmark/adapters/common/mapping.py` (`semantically_incomplete_end`, `read_run`, `completeness`, `read_rule_map`, `item_calls_failed`, `classify`, `sensitivity_s6`, the counts), `benchmark/adapters/common/records.py` (`envelope_agent` on bus records), `benchmark/adapters/common/cli.py` (S-6 in the label output). Arms: B2, B3, B4 (B0 and B1 unchanged).
- **Why**: before this, a run that reached its end with exit code 0 but marked its semantic work incomplete (`state` `stopped`, `semantic_complete` false) counted as a run failure, so every item of the document was ABSTAIN although the run had posted records; every B3 development run so far was in that state or a genuine failure. All-ABSTAIN on such a document discards what the run did and treats B3 more harshly than B1, whose failed call costs only its own item. Labelling from the records alone could credit silence as CLEAR where failed work was on the deciding path, so the change comes with an item-level exception (`item_calls_failed`), completeness counts per document and arm, and S-6 (the old reading, every item of such a document ABSTAIN) reported beside the primary result.
- **Decided from**: gold-free counts (completion states and judging-call outcomes of the development runs); no score of any arm was read for it.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores existed; D-066 changes the run-failure rule, not the order of the mapping lines, and did not read them.
- **Status**: draft. The item-level exception is built but not applied until preregistration section 12 item 11 (registry id to operator id) is settled (`mapping.RULE_ID_MAP_ADOPTED` False); until then the label output marks every row it would affect.

### DEV-002. A model's answer where Python could compute nothing is kept as a model's record

- **Entered**: 2026-10-29 (system clock, +0300), loop stage S5, lane `lane/s05-defect`.
- **Decision**: D-067 (closed: measure B3 as it is, fix the defect before the freeze under conditions) and D-068 (the fix).
- **What changes**: pipeline behaviour of B3 and B4, phase 5.5 paired review (`scripts/pipeline.py`, `_paired_convention_review`, recorded through the pinned-baseline path; `scripts/paired_review.py`, `judging_call_record`, `judged_item_refusal`, `reply_kept_reason`, `reply_items`, `stamp_from_plan`). Preregistration section 4 (B3's review mode stated: `paired`), section 5.1 (CUAD's absent class corrected; line 5 qualified), section 9 (three limitations), section 12 items 3 and 7. The run output format (`docs/OUTPUT_FORMAT.md` sections 5.2, 5.5, 5.6, 6.1, 8.1, 9). The run analyser (`tools/analyze_ordinary_final_run.py`: the counts per run).
- **Why**: the defect class, stated without naming a test: where Python's checks produce no comparison for a unit and a rule, the paired review asked a model and then discarded its answer, so a rule that only reading can decide had no answer anywhere in the run. The project had recorded this as a known, unfixed defect before any benchmark existed (`docs/PRODUCTIZATION_STATE.md`; `docs/fix/STEP_CONVASSIGN_3_REPORT.md`). The answer is now kept as a model-written record: stamped by Python (unit and rule from the plan, never from the reply), after the existing quote check and judged-answer refusals; never promoted to an amendment (check 269); never a Python record; posted once, as the paired review already posts a judged absence's stamped copy. A failed or refused reply keeps nothing and says why. No prompt and no rule template changed.
- **Decided from**: gold-free counts (every development judging call on the benchmark claims had outcome `advisory_not_kept`; 187 on ContractNLI, 174 on FinDVer, all on ContraDoc and SciTab) and the project's own earlier defect record. No benchmark development output was used to shape it.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores, and B3 development labels that equal B0's on four benchmarks; neither was read to shape the fix.
- **Status**: draft. Proven on fixtures (gate check 290, check 269, check 278; no model). Its first run with a model is to be on tests that are not benchmarks (the device-log twins' uncomputable calls and the clinical sheet), clean-twin false alarms counted, before the freeze. If S5's re-forecast cannot pay for that run, the change is deferred under the loop's rule P9 (b) and recorded in `docs/fix/OPEN_ITEMS.md` and the operator's notes, and this entry gets a successor saying so.
