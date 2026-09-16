# Auditor classification-first linear-probe results

**AUDITOR_LINEAR_PROBE_FAIL**

Historical canonical `AUDITOR_TUNING_FAIL` and its adapters/evidence remain unchanged. Historical step120 is still an ineligible standalone Auditor. This run is a separate head-only experiment bound to design commit `25f7dc0cb1bd11d652debbec52940f84e9d64193`.

## Cloud and cleanup

| Item | Value |
| --- | --- |
| Tested implementation commit | 05ce2a0dcbfc619be6e273777ef824355f992139 |
| Provider / region / GPU | Lambda Cloud / us-east-1 / A10 24 GB |
| Actual hourly rate | $1.29 |
| Instance | 4f88b80b8ea74ba6acf4db8ebb784ae4 |
| Launch to provider-confirmed termination | 1047.457 seconds |
| Estimated cost upper bound | $0.375339 |
| Termination UTC | 2026-09-16T19:31:19.054360+00:00 |
| 55-minute limit met | True |
| Remaining billable instances | 0; provider inventory checked |
| Temporary SSH registration / key | Removed |

Prelaunch projection: 3255 seconds including 300 seconds cleanup; $1.166375 at the confirmed rate. Minute50 cost $1.075; minute55 cost $1.1825. No second instance or fallback. Evidence archive downloaded and hash-verified before termination; long local analysis occurred afterward.

## Execution and evidence boundaries

The classifier used citation-normalized original input fields only. Local checks passed alias invariance for all 300 rows and exact refusal-prefix recognition for all 60 saved historical DEV outputs. No saved output was used as a fresh inference lookup. Local feature/autograd and optimizer protocol checks used synthetic stand-ins, not an experimental head or a local backbone run.

Native features are the final normalized decoder hidden state at the last unpadded prompt token; base/LoRA are frozen. The feature matrix has one stored vector per unique row. Fresh feature identity checks in controls/DEV are separately part of evaluation work. TRAIN-only FP32 population mean/std, clamped at 1e-6, standardize features. W and b alone are optimized.

Reason generation ends at the first unescaped quote; same-token structural spill is recorded, not treated as reasoning. Full assembled output token count includes the forced prefix, serialized suffix and deterministic native termination. Model throughput counts generated tokens only. Invalid reason or overflow is a failed output; an incomplete run cannot produce a quality PASS/FAIL.

## Features and head training

| Measure | Result |
| --- | --- |
| Unique features / dimension | 300/300 × 3072 |
| TRAIN / DEV | 240 / 60; 48 / 12 per class |
| Standardization | TRAIN only; no DEV fitting |
| Feature wall | 86.103620 s |
| Feature input tokens / second | 2639.564 |
| Trainable parameters | 15,365; backbone and LoRA: 0 |
| Updates | 200 |
| Head wall | 0.462148 s |
| Updates / second | 432.762 |
| Initial CE | 1.609437346458435 |
| Final CE after update200 | 0.00017073829862285412 |
| Final regularization contribution | 4.297304432839155e-06 |
| TRAIN accuracy | 1.0 |
| TRAIN macro F1 | 1.0 |
| Head SHA-256 | 040bef09af89ba255d859645bbc13c76e9f8a53bf8e7c795c29e01afbe6b7c23 |

Initial and update200 heads are preserved separately. Only update200 is a candidate. Objective: full-batch softmax CE + 0.001 × mean(W²), Adam FP32 LR0.01, betas0.9/0.999, epsilon1e-8, weight_decay0, seed7, zero W/b, 200 updates, no scheduler or early stopping. Log CE is pre-update; final CE above is recomputed after update200.

## Raw five-way head DEV

Complete 60/60. Accuracy 0.683333333; macro precision 0.787301587; macro recall 0.683333333; macro F1 0.679320473.

| Expected / predicted | ADDITION | DIVERGENCE | INSUFFICIENT_EVIDENCE | MATCH | OMISSION |
| --- | --- | --- | --- | --- | --- |
| ADDITION | 12 | 0 | 0 | 0 | 0 |
| DIVERGENCE | 4 | 7 | 0 | 0 | 1 |
| INSUFFICIENT_EVIDENCE | 0 | 0 | 12 | 0 | 0 |
| MATCH | 6 | 0 | 0 | 5 | 1 |
| OMISSION | 5 | 2 | 0 | 0 | 5 |

| Class | Precision | Recall | F1 | Support |
| --- | --- | --- | --- | --- |
| ADDITION | 0.444444444 | 1.000000000 | 0.615384615 | 12 |
| DIVERGENCE | 0.777777778 | 0.583333333 | 0.666666667 | 12 |
| INSUFFICIENT_EVIDENCE | 1.000000000 | 1.000000000 | 1.000000000 | 12 |
| MATCH | 1.000000000 | 0.416666667 | 0.588235294 | 12 |
| OMISSION | 0.714285714 | 0.416666667 | 0.526315789 | 12 |

## Refusal routing

| Measure | Result |
| --- | --- |
| Frozen prefix correctness | 60/60 |
| Raw-head refusals | 12 |
| Frozen-veto refusals | 12 |
| Final refusals | 12 |
| Refusal precision | 1.0 |
| Refusal recall | 1.0 |
| Over-refusal | 0.0 |
| Raw versus routed disagreements | None |

## Explanation and integrated Auditor

| Measure | Result |
| --- | --- |
| Generated substantive reasons | 48 |
| Fresh integrated DEV | 60/60 |
| Full DEV wall | 366.428520 s |
| Refusal-probe wall, DEV | 68.522570 s |
| Reason generation wall, DEV | 279.556286 s |
| Generated reason tokens | 1904 |
| Reason tokens / second | 6.810793016479827 |
| Contract validity | 0.9666666666666667 |
| Macro relation F1 | 0.6793204731285226 |
| Accepted outcomes | 32/60 |
| Evidence F1 | 1.0 |
| Refusal precision / recall | 1.0 / 1.0 |
| Over-refusal | 0.0 |
| Substantive non-refusal coverage | 0.9583333333333334 |

| Class | Recall |
| --- | --- |
| ADDITION | 1.0 |
| DIVERGENCE | 0.5833333333333334 |
| INSUFFICIENT_EVIDENCE | 1.0 |
| MATCH | 0.4166666666666667 |
| OMISSION | 0.4166666666666667 |

| Catastrophic category | Count |
| --- | --- |
| confident_wrong_match_divergence | 2 |
| governance_violations | 0 |
| invented_evidence | 0 |
| invented_rule | 0 |
| producer_source_copy | 0 |
| truncation | 0 |

Frozen gates: contract1, macro relation F1≥0.75, every class recall≥0.60, acceptance≥0.70, evidence F1≥0.85, refusal precision≥0.90, refusal recall≥0.80, over-refusal≤0.05, substantive non-refusal coverage≥0.90, all catastrophes0. No gate or historical scorer was changed.

| Additional non-regression requirement | Passed |
| --- | --- |
| evidence_f1 | True |
| over_refusal_rate | True |
| refusal_precision | True |
| refusal_recall | True |
| substantive_non_refusal_coverage | False |

## Performance

| Measure | Result |
| --- | --- |
| Peak allocated VRAM | 3.558658 GiB |
| Peak reserved VRAM | 3.730469 GiB |
| Mean sampled GPU utilization | 40.798095238095236 |
| Mean sampled process CPU percent | 135.51790476190476 |
| Peak process RSS | 1.666180 GiB |
| Peak host RAM used | 3.206207 GiB |

GPU/CPU/RAM sampling spans the remote execution process; CPU percent can exceed 100% across cores. The full-DEV timing includes fresh feature identity checks, routing, generation, fsync and scoring; reason/probe timings isolate generation calls. Controls are excluded from DEV throughput figures.

## Diagnosis and selection

**CLASSIFIER_FAILURE**

Diagnostic rule: full success; otherwise refusal/evidence routing regression if those metrics regress; otherwise explanation failure when raw-head relation gates pass; otherwise classifier failure. Contract-invalid explanations can lower valid non-refusal coverage without changing refusal routing. That coverage gate still fails; it is not hidden or renamed. Raw-head relation requirements use macro F1≥0.75 and all five recalls≥0.60. The diagnostic label does not replace the integrated verdict.

Failed required gates:

```json
[
  {
    "actual": 0.5333333333333333,
    "gate": "accepted_semantic_outcomes",
    "minimum": 0.7
  },
  {
    "actual": 0.9666666666666667,
    "gate": "contract_validity",
    "minimum": 1.0
  },
  {
    "actual": 0.6793204731285226,
    "gate": "macro_relation_f1",
    "minimum": 0.75
  },
  {
    "actual": 0.5833333333333334,
    "gate": "recall_DIVERGENCE",
    "minimum": 0.6
  },
  {
    "actual": 0.4166666666666667,
    "gate": "recall_MATCH",
    "minimum": 0.6
  },
  {
    "actual": 0.4166666666666667,
    "gate": "recall_OMISSION",
    "minimum": 0.6
  },
  {
    "actual": 2,
    "gate": "confident_wrong_match_divergence",
    "maximum": 0
  },
  {
    "actual": 0.9583333333333334,
    "gate": "nonregression_substantive_non_refusal_coverage"
  }
]
```

No passing integrated Auditor is selected. The only candidate completed and failed required gates. No second head, parameter search, pooling change or classifier-specific LoRA fallback is authorized.

### Local failure diagnosis only

28 nonaccepted rows: 19 wrong relations and 9 correct relations with nonmatching reasons. These are unchanged frozen-scorer outcomes, not a semantic rescore.

The head fits TRAIN perfectly but generalizes incompletely to canonical DEV. Relative to historical step120, raw relation accuracy rises from 29/60 to 41/60 and macro F1 from 0.434966 to 0.679320. Integrated acceptance rises only from 28/60 to 32/60. Prediction counts are MATCH5, DIVERGENCE9, OMISSION7, ADDITION27, INSUFFICIENT_EVIDENCE12: all five classes appear, but ADDITION remains overpredicted. This single run does not establish a causal explanation for the generalization gap or justify automatically adapting the backbone.

All 48 substantive rows receive reasons; no head/veto routing disagreement occurs. Rows137 and142 fail the unchanged contract with “Unselected citation in fidelity reason”: row137 mentions context-only REF-9999, and row142 mentions REF-40566, which is not supplied for that row. Their serialized ref_ids are still exactly correct. Thus evidence-ID F1 remains1 while contract validity is58/60 and valid substantive coverage is46/48. The frozen invented_evidence catastrophe checks ref_ids, not free-text citations; its count remains0. No reason or citation is repaired.

The two confident-wrong catastrophes are rows052 and162, both OMISSION→DIVERGENCE. Among the nine correct-class reason rejections, row046 gives a semantically aligned shorter quotation but fails the exact expected-reason string; rows156 and161 reverse replacement direction; rows047,050,272,275,277,282 identify wrong, structural or incomplete content. This annotation is descriptive and changes no score.

Full per-row expected/generated reasons and failure flags are in [FAILURE_DIAGNOSIS.json](auditor_linear_probe_run/FAILURE_DIAGNOSIS.json). Stop here. The classifier-specific LoRA fallback and governed system test remain unauthorized.

## Independent verification and next action

Local recomputation uses saved feature/head tensors and raw intermediate outputs, not model generation. It checks feature hashes and TRAIN-only statistics; zero initial head and 200-update logs; frozen-weight state hashes and parameter-state receipts; raw/scored identity; deterministic controls; logits/classes; refusal/reason parsing; assembled token accounting; frozen metrics and non-regression gates. Historical Auditor and Producer evidence text hashes remain unchanged; Producer binary preservation uses metadata only.

For FAIL: stop and diagnose locally only. For INDETERMINATE: address only the recorded invalidating issue in a future authorized action. For PASS: no automatic governed system test. No fallback execution.

`PRODUCER_STATUS=PRESERVED_UNEXECUTED`

`PROTECTED_RECEIPT_STATUS=UNCONSUMED`

One cloud instance and one GPU only. No new data, Producer execution/training, protected access, folds1–4, paid inference API, full pipeline, governed Producer+Auditor run, multi-round, second candidate, fallback or push. No backbone or LoRA update. Zero billable resources remain.

Evidence: [recomputed results](auditor_linear_probe_run/RECOMPUTED_RESULTS.json); [handoff](auditor_linear_probe_run/HANDOFF.md). Binary features and head artifacts remain local and are hash-bound in the evidence manifest.
