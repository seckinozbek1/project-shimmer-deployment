# Final stabilized classifier-fork run

**AUDITOR_CLASSIFIER_LORA_INDETERMINATE**

The one authorized attempt stopped with **NO_GO before optimizer creation**. The historical reference and classifier fork matched each other exactly on all16 controls, but both differed from the historical cached classifier function. The sealed cached-control gate rejected this difference. No optimizer updates, full-TRAIN baseline, update20 gate or DEV evaluation occurred. No retry or configuration change was made.

## Cloud execution and cleanup

Tested implementation: `23f6271d8401ab068c23747fa994130db3825dd2`, following fork implementation `9928d08` and seal `6ff591f`. Authorization attachment: `6234692b-4bf4-495e-952f-5d48d5219d6c`.

Exactly one Lambda A10 24GB, one GPU, x86-64, us-east-1; instance `e5124f2fb1cb40368a9de4dfe1d47836`. Live rate **$1.29/hour**; initial inventory empty. Soft budget $2.50 =>6976.744 seconds; hard ceiling $3.50 =>9767.442 seconds. Ten-minute collection/teardown reserve; workload cutoff9167.442 seconds; independent watchdog termination cutoff9647.442 seconds. Upper projected workload8400 seconds/$3.01 fit before provisioning. Runtime budget checks included remaining preflight, training and mandatory evaluations.

Launch epoch1789639830.1013813; termination verified **2026-09-17T10:18:23.745845Z**. Conservative billable wall **473.644 seconds (7m53.644s)**; estimated upper-bound cost **$0.16972260**, not an invoice. Workload was stopped, evidence archived/downloaded and SHA-256 checked before termination. Provider state was polled until absent; two subsequent inventory queries were empty. Temporary SSH registration and both local key files were removed. **Zero billable resources remain.**

Archive SHA-256: `0d7c7ac66df8a6d92e183d1f58f43b64c5457d6f6123bbcb5125341716f02be8` (56,276,679 bytes). Runtime bundle SHA-256: `784bcdcbac6c0ec0a0db45ee9528c4f3ac19cfae33bfd9b80672a9e7e004bfed`.

## Update0 observed evidence

The pinned model/dependency checks and actual loaded adapter/head/normalization identity checks passed. Both adapter slots and head were frozen during eval/inference-mode control observations. The 32 saved observations are the same16 bound TRAIN prompts run first under reference and then fork.

| Check | Observed result |
| --- | --- |
| Reference/fork controls | 16/16 PASS |
| Maximum hidden error | 0.0 |
| Maximum normalized-feature error | 0.0 |
| Maximum logit error | 0.0 |
| Maximum CE error | 0.0 |
| Reference/fork argmax identity | 16/16 identical |
| Candidate vs cached control maximum logit error | **2.514272689819336**, FAIL at rtol1e-4/atol2e-4 |
| Candidate vs cached control argmax matches | **13/16** |
| Actual16-control mean CE | **0.33491623401641846** |
| Expected cached16-control mean CE | **0.12840551137924194** |
| Full1,792-row TRAIN CE/baseline | **NOT RUN**, stopped before this stage |

The exact exception was `NumericalStop: update0_logits_parity`, raised by the unchanged cached-control check after all direct reference/fork comparisons. The compact protocol event records `preflight_exception`; `status.json` and traceback preserve the specific failing gate. These are finite but different logits, not an observed NaN/Inf training failure. The control mean is not a full-TRAIN CE estimate. The full-TRAIN gate remains unmet, not a measured full-TRAIN failure.

The source/fork copy is functionally identical under this runtime on the tested controls. The mismatch is against the older cached-feature baseline. This attempt does **not isolate why** the historical cached function and current runtime differ. No tolerance was relaxed, normalization refit, dtype changed, or further model experiment executed. This result must not be interpreted as a classifier quality FAIL or evidence that the source-family confound is harmless.

## Training, checkpoints and selection

Optimizer creation was not reached. Updates completed **0/896**. First/final training CE, median/p95 update time and training GPU allocation statistics are unavailable. The20-update numerical gate was **NOT RUN**. Historical reference removal was also not reached: cached-control validation precedes removal in the sealed protocol. Both slots remained frozen until process teardown; there was no dual-adapter gradient path and no backward call.

Expected future trainable counts were fork14,942,208 plus head12,292 =14,954,500, with base0 and reference0. The authoritative post-preflight trainable inventory was **not reached**. A saved finite partial-state artifact contains exactly the expected fork/head14,954,500 values. Raw tensor-byte comparison verifies all448 fork tensors and both head tensors unchanged from their initializers. This is an artifact inventory, not a claim that a training inventory ran.

Partial-state SHA-256: `aae5bb0d89a879accee765aba5baf7ece669d396464072a2913ffcbae356c951`.

There were17 GPU telemetry samples across model loading and preflight: mean utilization38.8824%, p95 utilization100%, peak device memory4193MiB (~4.095GiB). These are whole-workload samples, not training performance.

Checkpoint448: **NOT REACHED**; external/SHORTER/LONGER/historical metrics and fork/head checkpoint hashes unavailable.

Checkpoint896: **NOT REACHED**; all corresponding metrics and hashes unavailable. No saved DEV logits exist to recompute for either checkpoint; none were fabricated or borrowed from prior runs.

Passing checkpoints: none evaluated. Selected checkpoint: **none**. Selected fork/head hashes: **none**. This is INDETERMINATE because a complete valid quality experiment does not exist.

## Preservation and local verification

The source adapter remains SHA-256 `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`; config remains `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6`. Bound head/normalization, previous seals and historical results also match preservation hashes. The base was prepared frozen and no optimizer existed. An initial base-state hash was saved, but no final base-state comparison was reached; do not claim an independently verified final base hash.

53 deterministic local tests passed before provisioning, followed by packaged scope validation. After termination, the analyzer verified archive/source hashes, rechecked preservation, recomputed observed control argmax/CE from saved logits, and compared raw partial-state tensor bytes to initializers. No local real-model inference or training was used for analysis.

`docs/fix/auditor_classifier_lora_stabilized_run/RECOMPUTED_RESULTS.json` is the machine-readable result. `EVIDENCE_MANIFEST.json` binds retained text evidence and local-only binaries. Historical interrupted-run and corpus verdicts remain unchanged.

`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`

`HOLDOUT_STATUS=UNCONSUMED`

`PRODUCER_STATUS=PRESERVED_UNEXECUTED`

Exactly one instance/GPU was used. No training occurred, including explanation/refusal training. No generation, new data, HOLDOUT, Producer, protected access, full pipeline, governance, multi-round execution, retry, paid inference API or push occurred. No integration validation or another optimization experiment was started. This authorization is consumed; any further run requires a separate decision.
