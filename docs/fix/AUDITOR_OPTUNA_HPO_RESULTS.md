# Clean Auditor Optuna HPO results

**AUDITOR_OPTUNA_HPO_CANDIDATE** ? trial11 selected under the frozen eligibility and ranking rules. This is an INNER_VAL tuning candidate, not final Auditor acceptance or evidence of out-of-source generalization. Its objective and macro F1 are below the starting clean-head baseline. No full896-update run was performed or authorized by this study.

## Frozen selection

Exactly four values are frozen in [SELECTED_HYPERPARAMETERS.json](auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json):

| Parameter | Exact value |
|---|---:|
| classifier-LoRA peak LR | 1.2943234833221302e-06 |
| head LR | 0.0009721418411547451 |
| LoRA warmup updates | 10 |
| LoRA dropout | 0.05 |

Selected trial11 completed80 optimizer updates without a numerical prune. INNER_VAL360 (90/class) accuracy=0.741666666667, macro F1=0.744266564484, minimum recall=0.677777777778, mean CE=1.281814183836. Frozen objective .75*macroF1+.25*minimumRecall=0.727644367807. Eligibility was stable80, macroF1>=.60 and every recall>=.45; all four completed trials were eligible. Selection considered completed trials only. No pruned checkpoint was promoted.

Recall in MATCH/DIVERGENCE/OMISSION/ADDITION order: .700000000 / .677777778 / .811111111 / .777777778. Confusion matrix, true rows and predicted columns in that order: `[[63,6,10,11],[22,61,6,1],[10,2,73,5],[11,1,8,70]]`.

## Baseline comparison and limits

| Same INNER_VAL population | Accuracy | Macro F1 | Minimum recall | Mean CE | Objective |
|---|---:|---:|---:|---:|---:|
| Frozen clean initializer, cached affine scoring | .763888889 | .764495785 | .655555556 | .785779037 | .737260728 |
| Selected trial11 at80, live scoring | .741666667 | .744266564 | .677777778 | 1.281814184 | .727644368 |

Macro F1 changed by -0.020229220882, minimum recall by +0.022222222222, and objective by -0.009616360106. CE also worsened. Candidate qualification therefore does **not** establish improvement over the clean initializer. Baseline metrics are the already-frozen information-only cached-feature measurements; the successful live compatibility pass supports this comparison, but no extra live baseline validation pass was added.

INNER_VAL was adaptively used by HPO and is not an independent final test. The new head/normalization were fitted only on INNER_TRAIN1432. The required historical-step120 adapter retains its historical training exposure; this study does not erase that history. The PAWS/WikiAtomic source-family confound remains unresolved. The historical verdict **AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY** is unchanged. No generalization-success conclusion is made.

## Execution and trial results

Executed approved source `ea2b72373a384e29a6344c762b8b7d12ef450741`; approved seal SHA-256 `4fe9b330440b4559732d1880f3c267eb8f0937b776faa42e36d7cf27e9095c1b`. One sequential Optuna4.5.0 study, TPE(seed7, startup10), frozen SuccessiveHalvingPruner(min_resource20, reduction_factor2, min_early_stopping_rate0, bootstrap_count0). Exactly15 trials,584 completed optimizer steps,25 INNER_VAL evaluations,95 paired diagnostic checkpoints. Four trials completed80; nine were pruned by successive halving and two by the predefined numerical CE gate. No retry, fallback, second study or instance occurred.

All searches stayed within LoRApeakLR1e-6?1e-4(log), headLR1e-4?1e-3(log), warmup[0,5,10,20,40], dropout[0,.05]. Data, base, architecture, rank8, target modules and other optimizer settings were unchanged. Every trial used the frozen80-update INNER_TRAIN schedule with microbatch1/accumulation4. At most320 distinct INNER_TRAIN IDs contributed gradients per trial under that bounded schedule. INNER_VAL360 was scored only at the completed predefined20/40/80 checkpoints. The one1792-row compatibility pass was read-only; its CE baseline used1432 INNER_TRAIN labels exclusively.

Table metrics are the last scheduled INNER_VAL result for each trial; partial pruned results are not80-update candidate results.

| Trial | Completed updates | State | Macro F1 | Minimum recall | Objective | Reason |
|---:|---:|---|---:|---:|---:|---|
| 0 | 80 | COMPLETE | 0.718183 | 0.522222 | 0.669193 | eligible80 |
| 1 | 20 | PRUNED | 0.594067 | 0.333333 | 0.528883 | successive_halving |
| 2 | 3 | PRUNED | n/a | n/a | n/a | mean_update_ce_explosion |
| 3 | 20 | PRUNED | 0.537620 | 0.155556 | 0.442104 | successive_halving |
| 4 | 40 | PRUNED | 0.531514 | 0.133333 | 0.431969 | successive_halving |
| 5 | 1 | PRUNED | n/a | n/a | n/a | mean_update_ce_explosion |
| 6 | 40 | PRUNED | 0.755981 | 0.522222 | 0.697541 | successive_halving |
| 7 | 40 | PRUNED | 0.716556 | 0.411111 | 0.640195 | successive_halving |
| 8 | 40 | PRUNED | 0.733670 | 0.433333 | 0.658586 | successive_halving |
| 9 | 20 | PRUNED | 0.606139 | 0.266667 | 0.521271 | successive_halving |
| 10 | 80 | COMPLETE | 0.730800 | 0.644444 | 0.709211 | eligible80 |
| 11 | 80 | COMPLETE | 0.744267 | 0.677778 | 0.727644 | eligible80 |
| 12 | 80 | COMPLETE | 0.713209 | 0.588889 | 0.682129 | eligible80 |
| 13 | 20 | PRUNED | 0.650521 | 0.555556 | 0.626780 | successive_halving |
| 14 | 20 | PRUNED | 0.649593 | 0.555556 | 0.626084 | successive_halving |

Trial2 stopped before optimizer update4: four-microbatch mean CE22.349295855 exceeded13.862943611. Trial5 stopped before optimizer update2: mean CE17.869196892 exceeded the same frozen ceiling. These are predefined numerical prunes, not failed states reused by later trials. There were2344 recorded training microbatches:2336 for584 completed steps plus8 from the two pre-step-pruned attempts.

## Compatibility, reset and numerical evidence

Exact-runtime/package/base checks passed, followed by16 reference/fork controls and **one** full1792-row raw-hidden compatibility pass. The clean1432-row baseline was accuracy1.0, macroF1=1.0, meanCE=.06518125160687067. No cloud normalization/head refit or second full feature pass occurred.

The executed reset implementation restores an immutable clean CPU parameter snapshot; verifies its byte hash; clears and verifies gradients; resets Python/NumPy/Torch/CUDA RNG to7; installs selected dropout; and creates a fresh empty AdamW state. Those assertions completed before every trial. Independently, saved update0 eval hidden/standardized/logit vectors are bitwise identical across all15 trials. Paired diagnostics assert no gradient or parameter mutation and restore RNG. Full historical optimizer state was neither loaded nor reused.

All584 completed-step records show finite, nonzero head and LoRA gradients and finite, nonzero deltas for both parameter groups. Actual group LRs match the frozen warmup formula and head constant LR. Combined post-clipping norms stay within1.00001. The log contains a Torch checkpoint warning that inputs did not require gradients during a call; active training gradients and parameter deltas demonstrate that joint training was not globally disabled. The log does not tag that warning to a precise call.

Trial11 update1: meanCE=.0388079080; head/LoRA gradient norms1.59629422/24.61177174; combined pre/postclip24.66348441/.99999994; head/LoRA parameter delta norms.107758049/.000498558; actual LoRALR1.2943234833221303e-7. Update80 meanCE=.3262453885, head/LoRA delta norms.020863947/.001064853. Maximum completed-step meanCE was4.884751648. This supports80-update numerical stability for the selected combination, not896-update stability or attribution to a single hyperparameter.

## Scope and preservation

Payload contained1792 original TRAIN records split1432/360, clean HPO-only initializers, required clean historical adapter/features, pinned runtime metadata and reviewed code. Classifier prompts exclude provenance/source metadata. External DEV, historical DEV, SHORTER, LONGER, V2 HOLDOUT and protected-data successful-access counters are **zero each**, with zero denied-open attempts. HOLDOUT remains `consumed=false`. No explanation/refusal generation, Producer, governance, full Shimmer, multi-round or paid inference API execution occurred.

Approved seal, all six bound source artifacts and the prior current-runtime evidence-manifest hash were verified unchanged after collection. Historical evidence was not rewritten. The HPO head/normalization are retained as HPO artifacts; only the four hyperparameters are selected for potential subsequent work. No trained trial adapter is promoted as a final model.

## Cost and teardown

Live provider inventory was empty before launch, and `gpu_1x_a10`24GB availability in us-east-1 plus$1.29/hour were verified before provisioning. Exactly one instance was provisioned. Classification/compatibility workload lasted4913.544seconds (81.892minutes). Launch-to-final-empty-inventory upper bound was5490.200seconds (91.503minutes), giving estimated compute cost **$1.967322**, below$7soft/$9hard. This is an elapsed-time estimate at the verified rate, not an invoice.

Evidence archive was downloaded and SHA-256 verified before termination. Instance termination was verified at2026-09-17T13:45:37Z; independent fresh provider inventory at13:46:06Z was empty. Temporary provider SSH registration and local private/public keys were removed and independently checked. **Zero billable resources remain.** The authorization is consumed; launch guards prevent reusing it.

## Local verification and evidence

The59 frozen preparation tests and packaged scope gate passed before launch. Saved-evidence verification checks archive identity, executed code identity, artifact preservation, SQLite's single study/15 states, exact training IDs and update prefixes, checkpoint evaluation populations, per-row CE aggregation, confusion-derived metrics/recalls/objectives, actual LRs/clipping, paired diagnostic-vector differences, drift tie-breaks, reset probes, frozen candidate selection and cleanup. No model forward, fitting or new training was used for post-run verification.

Main artifacts: [RECOMPUTED_RESULTS.json](auditor_optuna_hpo_run/RECOMPUTED_RESULTS.json), [TRIAL_SUMMARY.json](auditor_optuna_hpo_run/TRIAL_SUMMARY.json), [downloaded trials](auditor_optuna_hpo_run/downloaded/evidence/trials.json), [downloaded winner](auditor_optuna_hpo_run/downloaded/evidence/winner.json), [data access](auditor_optuna_hpo_run/downloaded/evidence/data_access.json), [independent inventory](auditor_optuna_hpo_run/independent_inventory_confirmation.json), and [EVIDENCE_MANIFEST.json](auditor_optuna_hpo_run/EVIDENCE_MANIFEST.json). Source: `tools/analyze_auditor_optuna_hpo_run.py`.

Archive SHA-256: `e2376ea9a10523da45226d720dff067f39f882da3d7ea5c8027fe96366068c2b` (13,899,713bytes). The manifest separates committed text evidence from retained local bulk/binary files. Full diagnostic vectors and per-forward tensor summaries are saved in events.jsonl. Per-row prediction labels/full logits for every validation row and per-coordinate Adam states are not saved; their reconstruction is not claimed. Confusion-derived verification validates the recorded metrics, not an independent model re-evaluation.

The separately authorized next stage, if any, must be decided later. This run stops after freezing four values. No full1792-row/896-update training, DEV evaluation, new paid-run preparation or push follows from this result.
