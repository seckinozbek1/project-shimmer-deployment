# Auditor classifier LoRA stabilization — local-only audit

**AUDITOR_CLASSIFIER_LORA_STABILIZED_NOT_READY**

The prepared package binds the requested initialization, numerical checks and unchanged experiment. A compatibility requirement remains unresolved: the saved classifier was trained on base + historical step120 LoRA representations, whereas fresh zero-B classifier LoRA starts from the base-only function. Reusing its affine head and normalization does not restore the removed adapter. Cached-function parity passes; parity for the proposed fresh representation has not been measured or established. This is not evidence of a measured mismatch. The historical adapter remains excluded. No alternate architecture or initializer is substituted.

The interrupted run remains `AUDITOR_CLASSIFIER_LORA_INDETERMINATE` / `RELATION_ADAPTATION_INDETERMINATE`: three completed updates, attempted-update-4 failure, no quality checkpoint evaluation. Historical evidence and adapters are unchanged. V2 remains `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`; HOLDOUT remains unconsumed.

## Failure audit

**NUMERICAL_FAILURE_SOURCE_NOT_ISOLATED**. Executed source and parameter inventory, rather than a hypothetical dtype fix, determine the following trace:

| Boundary | Historical dtype/evidence |
| --- | --- |
| Prompt token IDs | int64 |
| Frozen quantized base | NF4 packed uint8; BF16 compute/autocast; nonquantized tensors cast FP32 by k-bit preparation |
| Fresh rank-8 LoRA parameters | FP32, recorded inventory |
| Final normalized hidden | Activation dtype not logged. FP32 is code-derived from pinned LlamaRMSNorm arithmetic and recorded FP32 final norm weight; not a measured activation claim |
| Head input | Explicit `hidden.float()` |
| Head weights, matmul, logits | FP32; head call outside base-forward BF16 autocast |
| CE / regularization / total loss | FP32; regularization is .001 times mean squared head weight |
| Accumulation | FP32 loss divided by four before backward |
| Backward | FP32 parameter-gradient storage expected; individual gradient dtypes not logged |
| Clipping | Combined norm limit 1; only returned pre-clip norm recorded |
| Optimizer | AdamW, FP32 parameter groups; no per-step parameter-finiteness telemetry |

Completed-update CE was 1.3862943649, 58.2680702209, 53.6806771755. Attempted update 4 failed the CE-plus-regularization finite assertion before that microbatch's backward. The first offending tensor and microbatch are unknown. No post-update weights were saved. The zero-head/head-LR=.01 joint configuration demonstrably became unstable; these observations do not isolate initialization, learning rate, activations, kernels, gradients or optimizer state as the unique cause. The old head was already FP32. Explicit FP32 enforcement is prospective instrumentation, not a proven root-cause repair.

## Exact initializer and parity

Source results commit: `8a116698d2048315a254e8e1a07438ca2263a88a`. Artifacts reside under `docs/fix/auditor_v2_diagnostic_run/downloaded/evidence/`.

| Artifact | SHA-256 |
| --- | --- |
| head-200.safetensors (weight and bias) | `e3e40fd922714d08832f24d7eb1860a622408ac0c0f3c53b3a3b2457a2ac9dbe` |
| mean.npy | `f71da5c61dcfe6186bc49146e24a1aa25029e7ce03b1aab93d903f01dcbd1c54` |
| std.npy | `d78e727198c4d15a86f7293c31ff4a5c20238dba148831cd5e1e88e246793794` |

Option A is implemented: `z = (h.float() - mean) / std`, then `W z + b`, all FP32, no L2 normalization. Mean/std are fixed saved TRAIN-only values, population std with minimum 1e-6; recomputation only verifies their identity and does not fit or accept a new transform. W is 4x3072, bias 4; class order MATCH, DIVERGENCE, OMISSION, ADDITION.

All 2,040 preserved feature rows were checked: 1,792 TRAIN, 200 external DEV, 48 historical DEV. Against the 248 saved DEV logits the maximum absolute error is **0.0000057220458984375**. Against an independent per-row FP32 computation across all 2,040 rows it is **0.0000095367431640625**. Tolerance is rtol=1e-4, atol=2e-4. Argmax predictions are identical; saved TRAIN and evaluation metrics are identical. Per-row TRAIN logits were not saved, so TRAIN checks use independent recomputation and saved aggregate metrics, not an invented historical logits file. DEV parity never enters gradients.

## Frozen prospective configuration

Pinned base `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`, weight hash `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`. Fresh rank-8 classifier LoRA: 14,942,208 trainable parameters; pretrained head: 12,292; total **14,954,500**. Frozen base has zero trainable parameters. Historical step120 adapter is excluded.

Exactly one configuration: LoRA LR 1e-4, head LR 1e-3, AdamW betas .9/.999, epsilon 1e-8, weight decay zero, no scheduler, combined clip norm 1. Microbatch 1, accumulation 4, effective batch 4. Head LR is reduced tenfold because the initialized head is trained and its input representation will move; this is not an optimized-hyperparameter claim. Classifier hidden cast, normalization, head, logits, CE, regularization and accumulation loss are FP32 with classifier autocast disabled. The whole model is not cast FP32.

Exact existing record, challenge and 896-update two-pass schedule files are referenced by SHA-256 in package binding files. TRAIN 1,792; external DEV 200; historical substantive DEV 48; SHORTER/LONGER 75 each. Prompts, labels and class order remain unchanged. Both 448 and 896 evaluations are mandatory for a final quality verdict. External macro F1 >=.75 and every recall >=.60; SHORTER and LONGER macro F1 >=.70; co-primary historical macro F1 >=.70 and every recall >=.60.

## Update-0 and numerical admission

`update0_controls.json` binds 16 TRAIN IDs, four per class selected by ascending SHA256 of a fixed seed string plus ID, independent of loss/prediction. It binds labels, logits and predictions. Future controls must have finite representations/logits, matching IDs/order/argmax and logits within rtol=1e-4, atol=2e-4, before any update. Failure is NO_GO. This does not claim that the fresh representation will pass.

Cached full-TRAIN mean CE is **0.07926499843597412**, with expected interval +/- max(1e-4, 1%). Control mean CE is **0.12840551137924194**, with its own +/- max(1e-4, 1%) interval. Small remote controls cannot establish full-TRAIN CE.

The prospective mean-update CE ceiling is **13.862943611198906 = max(10*ln(4), 20*cached TRAIN CE)**. A microbatch ceiling of **55.45177444479562** permits ordinary isolated stochastic variation while the accumulated update ceiling rejects the prior 50+ mean CE. This is deliberately generous (ten times uniform four-class CE and over 170 times cached mean), not a tuned quality threshold.

Every microbatch checks hidden, standardized hidden, logits, CE, regularization and total loss before backward, logging the first failed stage. Gradient finiteness is checked after backward and before/after clipping; invalid gradients block optimizer steps. Every step checks LoRA/head parameter finiteness and unauthorized changes. Compact telemetry includes dtype/finite flags, hidden and standardized norm min/mean/max, logits extrema/max-absolute, losses, separate and combined gradient norms, pre/post-clip norms and parameter norms. Norm telemetry uses FP64 reductions to avoid diagnostic overflow; classifier arithmetic remains FP32.

Exactly 20 completed updates with all checks passing and no skips are required before continuing the same schedule. No DEV at 20. Failure latches STOP: no LR change, rollback, reinitialization or retry. Frozen parameter versions are checked each step, with full base hash comparisons at 20/448/896. Future failure evidence must be persisted before teardown. Repeated numerical failure returns to runtime diagnosis; completion without a passing checkpoint stops this base/task formulation, without an automatic new experiment.

## Local validation and limits

23 deterministic no-model tests pass. They cover artifact tampering, normalization algebra, cached parity receipts, FP32 numeric reference, optimizer groups/LRs, NaN hidden/weights, invalid std, changed control logits/IDs, stage ordering, blocked backward/optimizer, invalid/clipped gradients, nonfinite parameters, unauthorized mutations, sticky failure, exact update20 admission, CE explosion and ordinary variation, schedule/checkpoints, TRAIN-only access, denied HOLDOUT/Producer/protected paths and absence of generation/model-loading calls.

The actual Torch/GPU hooks were not executed. Validation combines NumPy numerical fixtures, callback ordering, fake optimizer-group construction and source checks; it is not a GPU integration or stability claim. The package contains no cloud launcher or model loader. Future runner integration must wire update0 admission, durable telemetry/failure snapshots, frozen-state checks and teardown and be reviewed separately; existing cloud controllers must not bypass NOT_READY.

No base or LoRA model weights were loaded. The explicitly requested saved linear-head numerical artifact was read with safetensors.numpy, as were cached features and normalization arrays. No Torch import, model inference, generation, real training, new data, HOLDOUT, Producer, protected access, cloud/network access or push occurred.

## Projection and source seal

The prior three completed updates averaged 3.067390451 seconds, extrapolating to **45.81 minutes** for 896 updates. Historical Auditor p95 update timing plus 20% instrumentation allowance gives **89.73 minutes**. These are weak planning evidence, not completion guarantees. Allow **65–120 minutes total**, including setup, controls, two 248-row evaluations, hashes/evidence and teardown: **$1.3975–$2.58 at historical $1.29/hour**. No live price/capacity query occurred. Future authorization and verified pricing are required.

Parent source is interrupted-results commit `3a7e708e0b5734667e7dbd3bac4cd874949d561d`; original classifier implementation is `550b9144ab53cb540a7ced460f0be77429caab81`. `tuning/auditor_classifier_lora_stable/seal.json` records the exact tested implementation commit and file hashes in a subsequent seal commit, avoiding a self-referential source hash. This local preparation grants no cloud authorization.
