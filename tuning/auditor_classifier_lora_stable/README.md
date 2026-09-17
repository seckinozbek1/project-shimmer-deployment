# Local-only classifier LoRA stabilization package

**AUDITOR_CLASSIFIER_LORA_STABILIZED_NOT_READY**

This package preserves the interrupted run. It contains cached-feature parity evidence, fixed initializer identities, one prospective numerical configuration, compact telemetry helpers, fail-closed update0/update20 gates and no-model tests. It contains no cloud launcher or model loader. The real Torch hooks are defined for future review and were not executed locally.

The blocking distinction is mathematical: the head/mean/std were trained using features from base + historical step120 LoRA. A fresh zero-B classifier LoRA produces the base-only function initially. Reusing the old affine classifier does not restore a removed nonlinear adapter. Local parity on historical cached features is proven; fresh-backbone update0 parity is not. The historical adapter stays excluded as requested. No alternative architecture or initializer was substituted.

`experiment.json` freezes LoRA LR 1e-4, head LR 1e-3, fixed FP32 historical mean/std (no L2), pretrained head, original rank8 configuration, rows/gates/schedule, and the prospective CE ceiling. `update0_controls.json` binds 16 TRAIN controls and original-function logits. Actual future update0 mismatch must stop before any training. `source_bindings.json` identifies the preserved numerical artifacts. Data/schedule/challenge binding files reference exact existing files rather than duplicate or change them.

Run `python tools/prepare_auditor_classifier_lora_stable.py` for NumPy cached-feature parity only. Run `python -m unittest discover -s tools -p test_auditor_classifier_lora_stable.py` for no-model tests. Neither command loads base/LoRA weights, imports Torch, performs model inference, fits a new head, launches cloud, or accesses HOLDOUT.

The prospective hooks explicitly cast classifier hidden values, normalization, logits and loss to FP32 with autocast disabled. They gate each pre-backward stage, gradients before and after clipping, and parameters after each step. Failure is sticky. Twenty complete stable updates are required before continuation; no DEV evaluation occurs at update20. Quality checkpoints remain 448 and 896. A future reviewed runner must wire frozen-state hashes, durable failure snapshots, cleanup and separate authorization; no existing cloud controller should be repurposed to bypass this package's NOT_READY status.
