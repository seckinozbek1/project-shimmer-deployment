# Classifier adapter initialization compatibility

**AUDITOR_CLASSIFIER_LORA_STABILIZED_READY** — local preparation only, no cloud authorization and no measured real-model parity claim.

This report supersedes the fresh-zero-B design in `AUDITOR_CLASSIFIER_LORA_STABILIZATION.md`. The prior report, sealed package, interrupted run and historical results remain untouched. Source implementation/seal commits are recorded in the new package's `seal.json`.

## Compatible initializer

The previous head was fit on base + historical step120 features. Removing that adapter by starting a zero-B LoRA did not establish the same starting representation. An exact copy of step120 supplies the compatible initializer while preserving a separate classifier identity. This is a classifier-specific fork trained exclusively by four-way classification; it is not checkpoint121 or continuation of generative Auditor training.

Historical source: `docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120/`.

Isolated destination: `tuning/auditor_classifier_lora_fork/classifier_adapter_init/`.

| Artifact | SHA-256 |
| --- | --- |
| Historical adapter AND classifier-fork initial adapter | `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6` |
| Historical AND copied adapter config | `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6` |
| Trained head, weights and bias | `e3e40fd922714d08832f24d7eb1860a622408ac0c0f3c53b3a3b2457a2ac9dbe` |
| Fixed TRAIN mean | `f71da5c61dcfe6186bc49146e24a1aa25029e7ce03b1aab93d903f01dcbd1c54` |
| Fixed TRAIN std | `d78e727198c4d15a86f7293c31ff4a5c20238dba148831cd5e1e88e246793794` |

All **448 tensors / 14,942,208 parameters** match exactly: names, shapes, FP32 dtypes and raw value bytes. The complete files are byte-identical. `adapter_copy.json` records per-tensor digests and source-to-fork provenance. The destination is a distinct file, not a link to the source; preexisting mismatched files or overlapping paths fail closed. The historical files were opened only for reading and their hashes remain unchanged. The local-only weight copy is excluded from Git; metadata and config are tracked.

Adapter tensors were not deserialized or loaded into a model: the local audit reads safetensors headers and hashes each raw tensor byte range. Cached head/feature arithmetic uses NumPy. No real model, base weights, Torch execution, inference or training occurred.

The previous 2,040-row cached parity evidence is retained: 1,792 TRAIN, 200 external DEV, 48 historical DEV; maximum error against 248 saved DEV logits 5.7220458984375e-6, independent all-row reference 9.5367431640625e-6, identical argmax and saved metrics. Original per-row TRAIN predictions were not persisted: the new baseline predictions are reconstructed from preserved cached features with the bound head, and their aggregate metrics equal saved evidence.

## Mandatory real-GPU update0 gate, implemented but not executed

The future loader must enforce the pinned base revision/weight identity from `experiment.json` and load exactly two adapter slots: `historical_reference` and `classifier_fork`. Artifact hashes are checked before loading; `remote_preflight` additionally checks actual loaded adapter tensor identities and head/normalization values. Both adapters and head remain frozen in eval/inference mode throughout preflight. Dropout is disabled. The copied `inference_mode=true` config is preserved byte-for-byte; trainability is enabled explicitly only after successful preflight.

1. Run the existing **16 TRAIN controls** under reference, then under candidate, using the same bound prompt tokens. No adapter stacking.
2. Require finite FP32 hidden states, standardized features and logits; compare each with **rtol=1e-4, atol=2e-4**. Require identical argmax; CE uses the same tolerance. Compare candidate control logits/predictions and CE against the previously bound cached control expectations too.
3. Recheck source/artifact identities, delete the historical reference slot, and verify that no reference parameters or dual-adapter active path remain.
4. Evaluate all **1,792 TRAIN rows**, no gradients, with the fork. Require exact bound IDs/tokens/labels, all reconstructed expected TRAIN predictions, identical saved metrics, and mean CE within **[0.07847234845161438, 0.08005764842033386]**, centered on **0.07926499843597412**. Control CE is separately bound at **0.12840551137924194** with its previous 1% interval.
5. Enable only candidate LoRA and head parameters, recheck optimizer membership, then create AdamW and admit the unchanged numerical HealthGate. Optimizer creation before successful parity/baseline, duplicate creation, reference retention or unauthorized trainable base parameters is rejected.

Any parity/baseline failure is sticky NO_GO before training, with compact failure-stage evidence and no retry. Local artifact identity makes this a compatible initialization design; only the future actual GPU gate can establish model-function parity. No such measurement is claimed here.

## Unchanged stabilization and quality contract

The fixed FP32 transform is `z=(h.float()-mean)/std`, followed by `Wz+b`, with no L2 normalization and no newly fitted statistics. Rank8, alpha16, dropout .05 and seven projection targets remain unchanged. Adapter LR **1e-4**, head LR **1e-3**, AdamW betas .9/.999, epsilon1e-8, weight decay0, clipping1, no scheduler. Microbatch1, accumulation4, effective batch4. Trainable total **14,954,500** including the 12,292-parameter head.

All existing FP32 loss arithmetic, pre-backward stage checks, gradient checks before/after clipping, post-step parameter checks, hidden/logit/loss/gradient/parameter norm telemetry, frozen-state checks and sticky no-retry behavior are retained by importing the unchanged stabilization module. The prospective mean-update CE ceiling remains **13.862943611198906**, microbatch ceiling **55.451774444795625**. Exactly the first 20 completed stable updates are required before continuation; no skips and no DEV at20.

Same bound rows, prompts, labels, schedule and gates: TRAIN1792, externalDEV200, historicalDEV48, SHORTER75, LONGER75. Two passes /896 updates; both checkpoint448 and896 evaluations mandatory. External F1>=.75 and every recall>=.60; SHORTER/LONGER F1>=.70; co-primary historical F1>=.70 and every recall>=.60. External success alone remains insufficient. V2's historical dataset verdict remains NOT_READY; HOLDOUT remains unconsumed.

Future stop rules: update0 mismatch => NO_GO; numerical instability => INDETERMINATE and stop; completed896 with neither checkpoint passing => FAIL and stop this base/task formulation. No automatic retry, LR/rank changes, rollback, CV, additional head/LoRA or new data.

## Validation and projection

**41 deterministic no-model tests pass:** 23 retained stabilization tests plus18 fork tests. New fixtures exercise exact copy/isolation, invalid-source rejection, frozen reference and fork-only optimizer membership, reference removal, dual-adapter denial, token/label/ID changes, nonfinite representations, each reference/fork boundary mismatch, full-TRAIN prediction/CE/metric failure, sticky failure, optimizer-before-preflight and duplicate-optimizer rejection. Existing normalization, numerical gates, schedule, quality thresholds and prohibited-scope tests remain passing.

Actual Torch/PEFT hooks are not executed locally. Their future integration requires the existing pinned loader, durable telemetry callback, base-state checking, budget watchdog and teardown controller. READY refers to the requested local artifact/protocol criteria, not cloud execution readiness or a claim of numerical stability on GPU.

Training-only planning remains **45.81–89.73 minutes**, based on the prior three-update mean and historical Auditor p95 plus instrumentation allowance. Add full-TRAIN update0 inference (1,792 rows), 32 control forwards, setup, both checkpoint evaluations and evidence collection: **75–140 minutes total**, **$1.6125–$3.01 at the historical $1.29/hour rate**. Added preflight allowance is 10–20 minutes, unmeasured. Pricing/capacity were not queried. The upper estimate does not establish fit under the previous $3 ceiling; future budget approval and preflight are separate.

No cloud, model training, model inference, generation, new data, HOLDOUT, Producer, protected access, historical-adapter modification or push occurred. Earlier cloud approvals do not authorize this fork experiment.
