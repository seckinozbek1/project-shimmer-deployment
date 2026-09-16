# Auditor canonical tuning results

`AUDITOR_TUNING_FAIL`

The one authorized fresh Auditor run completed all 120 optimizer updates and both fresh 60-row canonical DEV evaluations validly. Neither checkpoint passes all frozen gates. No Auditor adapter is selected. No automatic redesign or retraining follows; the permitted follow-up is local failure diagnosis only. The Producer branch remains closed and checkpoint168 was preserved without execution. No governed Producer+Auditor system test ran.

## Cloud and cleanup

Tested executor commit: `3dd892dcdb9c1be6d26cb1a4ba63d6acaaa81471`. Provider: Lambda Cloud; region: us-east-1; one A10 24 GB, x86-64; queried price: **$1.29/hour**. Launch-to-confirmed-termination upper bound: **2793.527254 seconds (46m 34s)**. Estimated upper-bound compute cost: **$1.001013933**, not a provider invoice.

Termination confirmed at `2026-09-16T18:14:45.289420+00:00`. Subsequent independent inventory was empty, the ephemeral SSH registration was absent, and local key material was removed. **Zero billable resources remain.** The evidence archive was downloaded and hash-verified before termination; all analysis below occurred afterward.

The $1.50 soft budget was not reached. At launch, soft/hard durations were 4186.047/8372.093 seconds, workload cutoff 7772.093 seconds, with 600 seconds reserved for collection and teardown. A detached operator watchdog had a hard-minus-60-second termination deadline. The conservative prelaunch estimate was 7308 seconds/$2.6187, assuming 900-second setup, ten-second updates, all 144 generations at the 192-token cap and six output tok/s, plus reserve. Six tok/s was a planning assumption, not an Auditor quality gate. Every measured durable-boundary remaining-work projection passed.

## Frozen release and scope

Source release: `second-domain-agnostic-v2`, freeze SHA-256 `bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d`. Original mixed-role dataset SHA-256: `0e7532aa9cbca8cffad99faae03656cbbdb0dbf3fc489b18d142b5a000dfbc12`. Auditor-only exact row export SHA-256: `ba5289a1273eb51692a22bcd3b2d5f325643ea15e0d70b7e65f4c6147f7f3ec9`. The original dataset/config/gates were not changed; the export is byte-bound through per-row canonical hashes and the source release. Canonical split SHA-256: `dc7760fbeb77e672d9ee8709b04763a39a82bae945d5370bf9ffedbc538ddb98`.

Auditor rows: 300, all marked substantive by the frozen corpus; 60 per relation class. Canonical TRAIN/DEV: 240/60, balanced 48/12 per class. Maintained Auditor tokenization, target-only labels, contract/semantic metric fixtures, canonical-plan and grouped leakage checks passed. All 300 sequences fit the frozen 1056-token ceiling (maximum 1052); maximum target length was 153, within the 192 generation cap. The legacy whole-release dry-run entry point was not called because it also enumerates Producer/noncanonical folds and opens protected metadata; its maintained Auditor primitives were exercised in isolation. Protected artifacts were checked through existing metadata receipts only.

Pinned base: `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`, weight SHA-256 `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`. Loaded architecture: **LlamaForCausalLM**, model_type **llama**. Config SHA-256: `efc10243cb105a2fbb4069d1686dcffe52cce4bcb5acf3ddf17dff415939aca2`. Model naming did not override the pinned runtime evidence.

Fresh seed-7 LoRA: rank8, alpha16, dropout0.05, bias none, CAUSAL_LM, q/k/v/o/gate/up/down projections, 14,942,208 trainable parameters; all initial LoRA-B tensors verified zero. No prior Auditor or Producer adapter was loaded. AdamW LR1e-4, betas0.9/0.999, epsilon1e-8, weight decay0, linear scheduler, one warmup update, clipping1, microbatch1/accumulation4, two complete passes remain unchanged. The objective is equal-weight per-example mean assistant-target-plus-native-termination cross entropy. BF16, eager attention, gradient checkpointing, NF4/double quantization and deterministic algorithms were retained; TF32 was off.

Generation remained greedy, batch1, use_cache=true, max_new_tokens=192, EOS [32000,32007], and the pinned tokenizer pad ID. The scoped evaluation/state/cache mechanisms were tested against the unchanged V2.1 AST/bytes and passed real-object preflight. No ambient trace/profile or historical traced reference was used. V2 had no Auditor control IDs: before launch, one first-in-DEV-order ID per relation class was fixed and duplicate optimized passes required exact prompt/input/output/decoded/semantic/stop identity. Full DEV generations were separate and fresh.

## Training and runtime verification

| Measure | Value |
| --- | --- |
| TRAIN / DEV | 240 / 60 |
| Updates / example exposures | 120 / 480; each TRAIN example exactly twice; zero DEV gradients |
| Training wall excluding DEV | 562.803953 s / 9.380066 min |
| First / final update loss | 2.625045270 / 0.012163954 |
| Update time median / p95 | 4.710068 / 5.007321 s |
| Peak allocated / reserved VRAM | 4046895616 / 4469030912 bytes (3.768965 / 4.162109 GiB) |
| Training GPU utilization mean / median / p95 | 98.653285% / 100% / 100% (548 samples) |
| Overall GPU utilization mean / median | 40.575730% / 20% (2192 samples) |
| Training CPU utilization mean | 101.606387% (100% is one logical CPU) |
| Peak sampled RSS / host RAM used | 1551097856 / 3393527808 bytes |

Loss endpoints use different training examples and are descriptive, not held-out loss comparisons. Separate-process telemetry avoided the per-token generation path. Exact optimizer order/LR, checkpoint schedule, no update after120, fresh initialization, adapter/config identities and state/RNG restoration at both checkpoints passed local verification. Restoration covered weights, gradients, optimizer, scheduler, training flags/counters, adapter activation, nullable configs and checkpointing state; step61 followed the midpoint restoration check.

## Checkpoints

Checkpoint 60 adapter SHA-256: `35ce71004edea139719c9e945469fe0a20fd6efedb008b51d82507acb30f1bcc`.

Checkpoint 120 adapter SHA-256: `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`.

Shared adapter-config SHA-256: `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6`. Initialization adapter SHA-256: `e32f8ce5d7f7fcae83e7ce7de8591749d9617bc7b411017277e676e9228f49d3`.

| Measure | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- |
| Fresh complete DEV | 60/60 | 60/60 |
| Deterministic control pairs | 5/5 identical | 5/5 identical |
| Control pass1 / pass2 tok/s | 7.370339 / 7.254653 | 7.238776 / 7.139149 |
| DEV generation wall seconds | 755.150717 | 623.218277 |
| DEV aggregate output tok/s | 7.169430 | 7.251071 |
| DEV output tokens | 5414 | 4519 |
| Every frozen gate passed | FAIL | FAIL |

Timing includes prefill and synchronized generation, excluding controls/cache probes from full DEV totals. Decode-only speed and TTFT were not measured. Both actual cache preflights passed; all 144 raw outputs were persisted before scoring and independently decoded/rescored afterward.

| Frozen metric | Required | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- | --- |
| contract_validity | 1.0 | 1.000000000 | 1.000000000 |
| macro_relation_f1 | >=0.75 | 0.377043741 | 0.434965986 |
| accepted_semantic_outcomes | >=0.70 | 0.316666667 | 0.466666667 |
| evidence_f1 | >=0.85 | 1.000000000 | 1.000000000 |
| refusal_precision | >=0.90 | 1.000000000 | 1.000000000 |
| refusal_recall | >=0.80 | 1.000000000 | 1.000000000 |
| over_refusal_rate | <=0.05 | 0.000000000 | 0.000000000 |
| substantive_non_refusal_coverage | >=0.90 | 1.000000000 | 1.000000000 |

Accepted outcomes: **19/60** at step60 and **28/60** at step120; the threshold is **42/60**. Evidence precision/recall/F1 are **1/1/1** at both checkpoints (104 correct evidence atoms, zero false/missing atoms). All contract outputs are valid, but validity and correct evidence references do not establish a correct relation or justification.

## Confusion and per-class metrics

Confusion matrices use expected classes as rows and predicted classes as columns. Every class has support12. No invalid/unknown predictions occurred.

### Checkpoint 60

| Expected / predicted | MATCH | DIVERGENCE | OMISSION | ADDITION | INSUFFICIENT_EVIDENCE |
| --- | --- | --- | --- | --- | --- |
| MATCH | 1 | 2 | 9 | 0 | 0 |
| DIVERGENCE | 0 | 3 | 9 | 0 | 0 |
| OMISSION | 0 | 1 | 11 | 0 | 0 |
| ADDITION | 0 | 2 | 10 | 0 | 0 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 0 | 0 | 12 |

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| MATCH | 1.000000000 | 0.083333333 | 0.153846154 | 12 |
| DIVERGENCE | 0.375000000 | 0.250000000 | 0.300000000 | 12 |
| OMISSION | 0.282051282 | 0.916666667 | 0.431372549 | 12 |
| ADDITION | 0.000000000 | 0.000000000 | 0.000000000 | 12 |
| INSUFFICIENT_EVIDENCE | 1.000000000 | 1.000000000 | 1.000000000 | 12 |

Macro precision / recall / F1: 0.531410256 / 0.450000000 / 0.377043741.

### Checkpoint 120

| Expected / predicted | MATCH | DIVERGENCE | OMISSION | ADDITION | INSUFFICIENT_EVIDENCE |
| --- | --- | --- | --- | --- | --- |
| MATCH | 5 | 0 | 0 | 7 | 0 |
| DIVERGENCE | 0 | 2 | 0 | 10 | 0 |
| OMISSION | 2 | 0 | 0 | 10 | 0 |
| ADDITION | 1 | 1 | 0 | 10 | 0 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 0 | 0 | 12 |

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| MATCH | 0.625000000 | 0.416666667 | 0.500000000 | 12 |
| DIVERGENCE | 0.666666667 | 0.166666667 | 0.266666667 | 12 |
| OMISSION | 0.000000000 | 0.000000000 | 0.000000000 | 12 |
| ADDITION | 0.270270270 | 0.833333333 | 0.408163265 | 12 |
| INSUFFICIENT_EVIDENCE | 1.000000000 | 1.000000000 | 1.000000000 | 12 |

Macro precision / recall / F1: 0.512387387 / 0.483333333 / 0.434965986.

Every class must have recall >=0.60. Step60 fails MATCH, DIVERGENCE and ADDITION; step120 fails MATCH, DIVERGENCE and OMISSION. Diagnostic precision is shown as zero when a class has no predictions (step60 ADDITION, step120 OMISSION); this reporting convention does not alter any frozen F1, recall or eligibility gate.

## Refusals and catastrophic failures

| Refusal diagnostic | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- |
| expected | 12 | 12 |
| predicted | 12 | 12 |
| correct | 12 | 12 |
| false | 0 | 0 |
| missed | 0 | 0 |
| over_refusal_rate | 0.0 | 0.0 |

All five classes have zero false refusals at both checkpoints; no class is affected by false refusal. The historical refusal-collapse pattern did not recur in this canonical DEV run. Short correct refusal outputs are separated from substantive successes in efficiency reporting.

| Frozen catastrophic category | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- |
| invented_evidence | 0 | 0 |
| invented_rule | 0 | 0 |
| confident_wrong_match_divergence | 5 | 4 |
| truncation | 0 | 0 |
| producer_source_copy | 0 | 0 |
| governance_violations | 0 | 0 |

The **5 / 4 confident wrong MATCH-or-DIVERGENCE findings** independently disqualify the respective checkpoints. Categories retain the frozen scorer definitions; they are not a broader safety assessment.

## Measured failure pattern

Step60 predicts OMISSION on 39/60 rows, including 28 incorrect OMISSION predictions, and predicts ADDITION on none. Step120 shifts to ADDITION on 37/60 rows, including 27 incorrect ADDITION predictions, and predicts OMISSION on none. Required refusals remain exact at both steps. Relation accuracy is 27/60 and 29/60, respectively. Of those relation-correct rows, 8 at step60 and 1 at step120 fail the frozen reasoning requirement, leaving 19 and 28 accepted outcomes.

These observations establish unstable substantive relation classification despite perfect contract/evidence/refusal results. They do not isolate a causal explanation or justify changing labels, prompts, rank, learning rate or gates. No new data, runtime refusal hack, redesign, rescue or retraining was performed. Any Auditor redesign is a separate local task.

## Output efficiency

| Output-token statistic | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- |
| min | 12.000000 | 12.000000 |
| median | 97.000000 | 85.000000 |
| mean | 90.233333 | 75.316667 |
| p90 | 137.800000 | 99.000000 |
| p95 | 160.050000 | 103.100000 |
| max | 175.000000 | 163.000000 |

Both checkpoints: EOS-before-cap100%; cap-hit0%; trailing prose0; second JSON0; code fences0; duplicate refs0; duplicate finding items0. Quantiles use linear interpolation at (n-1)q. Quality overrides token efficiency.

| Efficiency | Checkpoint 60 | Checkpoint 120 |
| --- | --- | --- |
| Correct evidence atoms / all output tokens | 0.019209457 | 0.023013941 |
| Accepted-output token cost mean / median | 46.105263 / 12.000000 | 57.107143 / 85.000000 |
| All attempt tokens / accepted outcome | 284.947368 | 161.392857 |

| Accepted group | Checkpoint | Count | Total tokens | Mean / median / p95 |
| --- | --- | --- | --- | --- |
| correct_refusals | 60 | 12 | 144 | 12.000000 / 12.000000 / 12.000000 |
| correct_refusals | 120 | 12 | 144 | 12.000000 / 12.000000 / 12.000000 |
| substantive_successes | 60 | 7 | 732 | 104.571429 / 96.000000 / 136.400000 |
| substantive_successes | 120 | 16 | 1455 | 90.937500 / 85.000000 / 101.250000 |

Evidence density uses all generated DEV tokens as denominator. Accepted-output cost conditions on correctness; all-attempt token cost also includes rejected outputs. Small accepted subgroups have descriptive tail quantiles only. Full distributions, per-row errors, confusion counts and gate failures are preserved in the JSON evidence.

## Selection, preservation and next action

Eligible checkpoints: none. Selected checkpoint: none. Selected adapter SHA-256: not applicable. Frozen quality eligibility rejects both checkpoints before applying macro-relation-F1, accepted-outcome, earlier-step and adapter-identity-hash tie-breaks. A failing adapter was not selected or promoted.

`PRODUCER_STATUS=PRESERVED_UNEXECUTED`  
`PROTECTED_RECEIPT_STATUS=UNCONSUMED`

Historical V2 release hashes and Producer V3 result text hashes passed. Historical Producer archives/adapters were checked by size and the existing preservation metadata, without loading Producer tensors; no Producer inference or training occurred. Producer V3 FAIL remains unchanged and the branch remains closed. No protected target was opened or uploaded, no protected evaluator ran, and no receipt was consumed.

Exactly one cloud instance and one GPU were used; no second GPU, Producer execution/training, protected access, folds1-4 execution, paid inference API, full Shimmer pipeline, governed system test, multi-round run, or push. Zero billable resources remain.

Archive SHA-256: `e8d8b45ab44ddfa56ddcee6e9a9c99d2105c56d718d9ca8a81662ac712176613`; size 136,498,916 bytes. The archive and initial/midpoint/final adapter binaries remain preserved locally outside Git. Their hashes and all reviewable text evidence are committed. Copy those binaries separately when migrating; the full local verifier also needs pinned tokenizer assets.

Evidence: `auditor_canonical_tuning_run/RECOMPUTED_RESULTS.json`, `RECOMPUTED_PER_ROW.json`, `POST_RUN_VERIFICATION.json`, `EVIDENCE_MANIFEST.json`, cleanup/inventory receipts, and `downloaded/evidence/`. Frozen execution artifacts are in `tuning/auditor_canonical_execution/`; canonical source artifacts remain unchanged. Run-specific HANDOFF.md records the stop decision without editing historical handoffs.

Verification: `python -B tools/analyze_auditor_canonical.py` recomputed 144 outputs (120 DEV, 20 duplicate controls, 4 cache), all metrics/gates, confusion/refusal diagnostics, adapter/config hashes, exact120-update order/LR and no DEV gradients. `python -B tools/auditor_canonical_checks.py` passed all nine integration checks. Text credential scans found zero keys.

**Next action: local failure diagnosis only; no automatic Auditor retraining.** A Producer168 + selected Auditor + existing governance/re-fire system test is not admitted because no Auditor checkpoint passed, and would require separate authorization in any case.

