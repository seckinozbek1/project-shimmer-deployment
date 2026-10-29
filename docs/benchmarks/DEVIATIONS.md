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

### DEV-003. DEV-001's status: the item-level exception is now applied (corrects DEV-001's status line)

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a, lane `lane/s05-prereg`.
- **Decision**: D-078 (`docs/loop/DECISIONS.md`), section 12 item 11.
- **What changes**: nothing beyond DEV-001 and DEV-008. DEV-001's status line says the item-level exception `item_calls_failed` is not applied until section 12 item 11 is settled (`mapping.RULE_ID_MAP_ADOPTED` False). That is stale: item 11 is settled, and the exception is applied from commit `5716d90` (D-078). DEV-001 is left as written, because an entry is never edited; this entry replaces its status line.
- **Why**: the adapter lane `lane/s05-adapt2` adopted the rule-id map (DEV-008).
- **Decided from**: gold-free counts (DEV-008).
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 and B3 development scores; not read.
- **Status**: draft. DEV-001's status is now: draft, with the item-level exception applied from `5716d90` (D-078).

### DEV-004. B1 and B3 run the producer under sdpa, prefilled in one shot; general fixes from the L2 diagnosis

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a. Entered late: the changes were made on 28 October (D-061, D-063) and had no entry here (D-078).
- **Decision**: D-061 (the general fixes, and E made buildable) and D-063 (D-061's declared fallback: option A).
- **What changes**: what B1 and B3 run. The producer in B3 and the model in B1 use sdpa attention pinned to the memory-efficient backend, with the prompt prefilled in one shot (sealed settings `SHIMMER_PRODUCER_ATTENTION` and `SHIMMER_PRODUCER_PREFILL_CHUNK`; `final_models.generate_with_prefill`; `benchmark/baselines/bare_model.py`). The models `agent_wrapper._load_qwen` loads run sdpa pinned the same way. Chunked prefill under eager (E) stays built as a measurement path. General fixes (D-061): `auditor_pairs` records a VERIFIER reply that is not an object as a contract failure, not a crash; the runner's assessment reports `semantic_incomplete` as its own reason; the contract retry is skipped under deterministic decoding (`retry_skipped_deterministic`). Preregistration sections 4, 9 and 12 item 13. Arms: B1, B3, B4.
- **Why**: one-shot eager did not fit the instance's memory on long prompts (INC-015). E missed its declared threshold (8 of 12 replies byte-identical to one-shot eager, 5 of 9 on long prompts, against 90 percent); sdpa one shot was byte-identical on 12 of 12 and 9 of 9, so D-061's declared fallback chose it. The producer was trained and evaluated eager; that is a section 9 limitation. Under greedy decoding a contract retry can only repeat itself (9 of 9 identical in L2).
- **Decided from**: gold-free measurements (byte identity of replies, GPU memory, prefill time) on development items, under a rule declared before the comparison was read.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores from L2; not read for the choice.
- **Status**: draft. Built and merged (`5452a76`, `72df4c2`).

### DEV-005. DEV-002's change was verified with a model and kept

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a. Successor to DEV-002.
- **Decision**: D-069 (the verification run L5v, with its acceptance declared before it), D-070 (verified: D-068 stays), D-071 (D-068's own entry, merge `8ac7a60`).
- **What changes**: nothing beyond DEV-002. DEV-002's status said its first run with a model was still to come. That run (L5v) used tests that are not benchmarks: the clinical sheet, the device-log flawed document and its clean twin. Clinical sheet: location recall 5 of 5, reason confirmed 4 of 5, false positives 0 (L1: 4 of 5, 4 of 5, 0). Clean twin: false positives 0. D-069's declared acceptance held, so D-068 stays.
- **Why**: DEV-002 required this run before the freeze.
- **Decided from**: the scorer's counts on tests that are not benchmarks, against an acceptance declared before the run. No benchmark output was read.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores; not read.
- **Status**: draft. DEV-002 is verified; its change stays (merge `8ac7a60`).

### DEV-006. CUAD leaves the design; which development outputs count; the ContractNLI span-part trigger route

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a. Entered late (D-078).
- **Decision**: D-073 (re-forecast of S5) and D-077 (L6 and L6s content).
- **What changes**: (1) CUAD leaves the S8 priority list (preregistration section 2). (2) B3 development outputs made before D-068 (merge `8ac7a60`: L2, L3e, L4a) count for cost, not for labels. C0 receives every development output, each labelled with its commit and whether it predates D-068; C0's mapping check counts only current-code outputs. S8 sizing uses only current-code runs. (3) The ContractNLI span-part trigger (section 2) is decided from L6s's measured B3 cost per agreement with span parts, run as its own launch: a complete measurement, or a measured lower bound that decides the trigger only if it passes 0.46 USD; otherwise the trigger is recorded as undecided, and section 2 says which. Arms: all.
- **Why**: CUAD has no B3 or B1 development output and no measured cost, so it cannot be sized and C0 has nothing to check on it; S5's money did not pay for it after the earlier items (DS5-4: least fitting, then costliest). D-068 changed what B3 writes on text-only claims, so earlier B3 labels are not labels of the current code. A batch cannot stop one entry early, so the span-part agreement runs alone.
- **Decided from**: cost and budget, and the commit of each output. No score was read.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores and pre-D-068 B3 labels; not read.
- **Status**: draft. The trigger outcome is written into section 2 by the lead.

### DEV-007. B3 and B4 run an over-bound phase as waves

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a. Entered late (D-078).
- **Decision**: D-076 (INC-019).
- **What changes**: pipeline behaviour of B3 and B4. A gather with more planned calls than the scheduler bound (`max_pending`) used to refuse the run; it now runs as consecutive waves of at most `max_pending` calls sharing one snapshot and one parent set (merge `8c2392d`, gate check 291). A gather at or below the bound runs exactly as before. Arms: B3, B4.
- **Why**: a phase with more planned calls than the scheduler admits refused the run (ContractNLI band B in L4b; all of CUAD is above the bound too). An arm that cannot finish a class of documents is a fault in the evaluation, not a cost.
- **Decided from**: the refusal in L4b (run health, no score) and fixtures.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores; not read.
- **Status**: draft. Built and merged; verified on fixtures, and on a second document class in L6 (the ContractNLI band B re-run).

### DEV-008. The registry-id map is adopted; `item_calls_failed` is applied

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-078, section 12 item 11.
- **What changes**: preregistration section 5.1 (line 5's exception; the per-arm counts) and section 12 item 11. Code: `benchmark/adapters/common/mapping.py` (`RULE_ID_MAP_ADOPTED` True, `read_rule_map` returning a status, `names_rule`), with checks in `scripts/adapter_checks.py` (commit `5716d90`). A judging call and a pairing-map refusal are matched to an item through the run's own `audit/convention_assignment.json`; where the map is missing, unreadable or not one to one, the exception is not applied on that document, the row says why and the document is counted. Arms: B2, B3, B4.
- **Why**: every B3 development run folder (20 of 20) holds a one-to-one map, so the switch can be turned on.
- **Decided from**: gold-free counts. On every development output the exception applied to 0 items, so no development label changed.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 and B3 development scores; not read.
- **Status**: draft.

### DEV-009. B1's checkpoint pool is the three benchmarks that stay

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-078, section 12 item 12.
- **What changes**: preregistration section 12 item 12. Its rule named the pool as the five benchmarks, or those that survive C0. The pool is now ContractNLI, ContraDoc and SciTab, the benchmarks left on the S8 priority list after CUAD (D-073) and FinDVer (D-078) left it. The choice is tuned. Over the four benchmarks pooled before FinDVer left: parse rates tied (72 of 73), headline tuned 0.305 against base 0.233. Over the three that stay: headline tuned 0.407 against base 0.311. FinDVer's 0 of 1 parse is outside the pool now. Arms: B1.
- **Why**: a benchmark that is not run in S8 cannot be in the pool that chooses B1's checkpoint for S8.
- **Decided from**: the benchmarks' removal, for cost (CUAD) and for context and the parse floor (FinDVer), not for a score. The pool was narrowed after B1 development scores existed; both readings choose the same checkpoint.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 development scores for both checkpoints, read by item 12's rule as that rule requires; the pool change did not read them.
- **Status**: draft.

### DEV-010. B3 documents with a call over the model's context are excluded, and S-7

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-078, section 12 item 14.
- **What changes**: preregistration section 4 (S-7 in the sensitivity list), section 5.1 (the per-arm counts), section 5.3 (the exclusion read from reply records; comparisons with B3 on documents excluded for neither arm; S-7), section 12 item 14. Code: `benchmark/adapters/common/mapping.py` (`read_over_context`, `OVER_CONTEXT_ARMS`, basis `over_context_excluded`, `sensitivity_s7`, `scored_view`, `over_context_excluded`, `restrict`) and `benchmark/adapters/common/cli.py` (`score --paired-with`), with checks (commit `5716d90`). Arms: B3 (B4 is not checked).
- **Why**: section 5.3 already excluded such documents from B3, but the adapters did not apply it: FinDVer `e61777d6327c` had three calls over the context in L3e and in L4b and was scored. Those two B3 figures are void and are not reported.
- **Decided from**: counts of over-context calls in the reply records, with no score read.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 and B3 development scores, including the two void B3 FinDVer scores; not read.
- **Status**: draft.

### DEV-011. FinDVer leaves the S8 priority list

- **Entered**: 2026-10-29 15:54 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-078.
- **What changes**: preregistration section 2 (the priority list holds ContractNLI, ContraDoc and SciTab) and section 12 item 12 (DEV-009). Arms: all.
- **Why**: (1) B3 runs over its model's context on long filings: whole-document agents add their own text to a document cut to about 30,500 tokens, so section 5.3 excludes such documents, and 209 of 255 development filings are cut (inferred from one filing, not counted). (2) B1 failed the 95 percent parse floor at full length (both checkpoints reached the output allowance, 0 of 1). Section 5.4 would then require a prompt revision chosen after both checkpoints' scores are known, measured by a B1 run that S5's money no longer pays.
- **Decided from**: counts and cost, by section 12's rule for an item that cannot be settled. No FinDVer score enters it.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1 and B3 development scores; not read.
- **Status**: draft. Five benchmarks were selected; three stay, the minimum S8 aims for.

### DEV-012. Sensitivity S-8: B3 without model-written records

- **Entered**: 2026-10-29 18:53 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-080.
- **What changes**: section 4's sensitivity list gains S-8. Arms: B3 and B4. Primary analysis unchanged.
- **Why**: under D-068 a model's answer on an uncomputable plan is kept as a model-written record, and section 5.1 lets a model-written record decide its item. Every development model-text review since (L4a, L5v, L4b, L6) found the base auditor model answering VIOLATION on units that do not address the rule; in L6 all three kept answers sampled were wrong (a sum relation on a unit with no figures). S-8 scores every item whose deciding record was written by a model as if that record were absent (the next record in section 5.1's order, else silence), so B3's result is also shown on Python's records alone.
- **Decided from**: the model-text reviews (verdicts on model texts, no gold label), not from a score.
- **Holdout result seen**: no.
- **Development scores existing when decided**: B1, B2 and B3 development scores exist; the primary analysis is not changed.
- **Status**: draft; the adapters compute it before C0 (lane), and C implements it from this text.

### DEV-013. The ContractNLI part rule after the span-part measurement

- **Entered**: 2026-10-29 20:45 (system clock, +0300), loop stage S5 item 10a.
- **Decision**: D-083.
- **What changes**: preregistration section 2, the trigger: recorded as undecided (the span-part run failed out of memory after 9.1 minutes; no complete cost and no lower bound above 0.46 USD), so the merged-part fallback applies, by the route the S5 plan declared before the measurement (R17). Arms: all.
- **Decided from**: run health and cost of one development agreement; no score.
- **Holdout result seen**: no.
- **Status**: draft.
