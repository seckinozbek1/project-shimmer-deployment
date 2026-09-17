# Auditor V2 expanded-data classification diagnostic

**AUDITOR_V2_DIAGNOSTIC_FAIL**

**RELATION_REPRESENTATION_STILL_INSUFFICIENT**

This is a one-off diagnostic on quarantined data. V2 remains `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`. The PAWS/WikiAtomic source-family confound remains unresolved; this result does not admit V2 or select/deploy an Auditor.

## Cloud and tested implementation

- Tested implementation: `12a08e89d27195d384c9565b9bd93cb829df98d1`.
- Lambda Cloud / us-east-1 / exactly one A10 24GB / x86-64 / one GPU.
- Live hourly rate: $1.29; soft budget $0.75; hard ceiling $1.50.
- Launch-to-confirmed-termination upper bound: 990.380 seconds (16.51 minutes).
- Estimated compute-cost upper bound: $0.354886; this is a duration estimate, not an invoice or tax calculation.
- Termination confirmed: 2026-09-17T05:10:56.242556+00:00. Independent final inventory is empty; temporary SSH registration and local key material were removed.
- Initial automatic approval review blocked launch; the operator subsequently approved the exact destination, payload and budget directly. The single instance was created only after that confirmation.

## Features and normalization

- TRAIN 1,792/1,792; external DEV 200/200; historical substantive DEV 48/48; total 2,040 vectors of 3,072 FP32 values.
- Frozen backbone plus frozen checkpoint-120 LoRA, eval/no-grad, final normalized hidden state at the last prompt token, before assistant generation. All row/feature hashes verified locally.
- Mean/std fitted only on the 1,792 TRAIN vectors; ddof=0; std clamp=1e-6. Local recomputation exactly matches saved statistics.
- Model load and initial frozen-state check: 10.492s; feature wall: 453.098s; input tokens: 1,138,245; input tokens/sec: 2512.14.
- Peak allocated/reserved VRAM: 3.559/3.730 GiB. GPU utilization, CPU and RAM samples are in `downloaded/evidence/telemetry.jsonl`.

- Telemetry: 459 samples; mean/max GPU utilization 93.97%/100%; peak process RSS 2.676 GiB; peak host RAM used 3.149 GiB. Mean process CPU 129.84% (psutil multicore scale, so values may exceed 100%).

## One linear head

- Exactly 12,292 trainable parameters, W=(4,3072), b=(4,), FP32, zero initialization, seed=7. No hidden layer, dropout, calibration, class weighting, scheduler or early stopping.
- Exactly 200 full-population Adam updates; lr=.01, betas=(.9,.999), epsilon=1e-8, weight decay=0; cross entropy + .001*mean(W**2). Only final update200 evaluated.
- Training wall: 0.266169s; updates/sec: 751.40; initial/final CE: 1.38629448/0.07926498.
- TRAIN accuracy: 0.99665179; macro F1: 0.99664928.
- Initial zero weights, final head, all 200 losses, normalization, feature arrays and logits are preserved. Frozen backbone/LoRA state hashes match before and after; neither has trainable parameters.

## External DEV

Complete: 200/200; accuracy 0.73500000; macro precision 0.73088017; macro recall 0.73500000; macro F1 **0.73210813**.

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| MATCH | 0.58695652 | 0.54000000 | 0.56250000 |
| DIVERGENCE | 0.70588235 | 0.72000000 | 0.71287129 |
| OMISSION | 0.81250000 | 0.78000000 | 0.79591837 |
| ADDITION | 0.81818182 | 0.90000000 | 0.85714286 |

Confusion matrix: rows are gold; columns are predictions.

| Gold / predicted | MATCH | DIVERGENCE | OMISSION | ADDITION |
|---|---:|---:|---:|---:|
| MATCH | 27 | 12 | 5 | 6 |
| DIVERGENCE | 11 | 36 | 1 | 2 |
| OMISSION | 7 | 2 | 39 | 2 |
| ADDITION | 1 | 1 | 3 | 45 |

Principal gate (macro F1 >= .75, every recall >= .60): FAIL. External including both challenges: FAIL.

Classification wall: 0.006490s.

## Historical canonical substantive DEV — co-primary

Complete: 48/48; accuracy 0.58333333; macro precision 0.63146998; macro recall 0.58333333; macro F1 **0.56649958**.

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| MATCH | 0.71428571 | 0.41666667 | 0.52631579 |
| DIVERGENCE | 0.66666667 | 0.33333333 | 0.44444444 |
| OMISSION | 0.66666667 | 0.66666667 | 0.66666667 |
| ADDITION | 0.47826087 | 0.91666667 | 0.62857143 |

Confusion matrix: rows are gold; columns are predictions.

| Gold / predicted | MATCH | DIVERGENCE | OMISSION | ADDITION |
|---|---:|---:|---:|---:|
| MATCH | 5 | 0 | 2 | 5 |
| DIVERGENCE | 1 | 4 | 2 | 5 |
| OMISSION | 0 | 2 | 8 | 2 |
| ADDITION | 1 | 0 | 0 | 11 |

Historical co-primary gate (macro F1 >= .70, every recall >= .60): FAIL.
Previous saved-probe four-way macro F1: 0.5991505914; new-minus-previous delta: **-0.0326510091**. Baseline predictions were not regenerated.

Classification wall: 0.001699s.

## External challenges

| Challenge | Evaluated | Three-class macro F1 | Gate >= .70 |
|---|---:|---:|---|
| LONGER | 75/75 | 0.67461541 | FAIL |
| SHORTER | 75/75 | 0.69549514 | FAIL |

SHORTER uses MATCH/DIVERGENCE/OMISSION; LONGER uses MATCH/DIVERGENCE/ADDITION; 25 rows per supported class. Predictions outside the supported classes still count as errors. Full precision/recall/F1 and confusion matrices for each challenge are in `RECOMPUTED_RESULTS.json`.

## Interpretation and boundaries

Both DEV sets are co-primary. Success requires external macro F1 >= .75, each external recall >= .60, both challenge macro F1 >= .70, historical macro F1 >= .70, and each historical recall >= .60. No thresholds were lowered. No statistical-significance claim is made.

Under this one predeclared configuration, expanded labeled data did not support the generalization hypothesis: external MATCH recall was .54, historical MATCH/DIVERGENCE recalls were .4167/.3333, and historical macro F1 declined by .03265. Both principal gates and both challenges failed despite near-perfect TRAIN performance. This does not establish that every possible head or representation would fail.

Only prompt token IDs entered the model. Provenance, source family, split, gold label, ID and row position were outside the prompt. Textual source inferability has not been ruled out. External scores alone cannot establish generalization.

`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`  
`HOLDOUT_STATUS=UNCONSUMED`  
`PRODUCER_STATUS=PRESERVED_UNEXECUTED`

No backbone, LM-head or Auditor LoRA updates; no explanation or refusal generation/retraining; no new data, HOLDOUT access/evaluation, Producer execution, protected-data access, paid inference API, full pipeline, governance run, folds 1–4, multi-round, second candidate or second instance. Execution consumed the bound records without reopening the mixed V2 corpus. Historical reports/manifests and HOLDOUT receipt identities remain unchanged. No push. Zero billable resources remain.

## Evidence and local verification

The downloaded archive SHA-256 matched the remote archive before teardown. After confirmed termination, local NumPy recomputation verified every feature identity, TRAIN-only normalization, final-head logits and metrics, both co-primary gates, both challenges, baseline delta, 200 updates and frozen-state equality. No local model inference or training was used.

Key artifacts in `docs/fix/auditor_v2_diagnostic_run/`: `execution_manifest.json`, `training_authorization.json`, `DIRECT_OPERATOR_CONFIRMATION.json`, `collection_integrity.json`, `TERMINATION_VERIFIED.json`, `final_inventory_confirmation.json`, `cleanup.json`, `RECOMPUTED_RESULTS.json`, `preservation_after.json`, and `EVIDENCE_MANIFEST.json`. Bulk arrays/adapters/archives remain local; text evidence is committed after secret scanning.
