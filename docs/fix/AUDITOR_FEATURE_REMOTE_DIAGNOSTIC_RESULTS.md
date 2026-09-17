# Final Auditor A10 feature diagnostic

**REMOTE_BLOCKER_NOT_REPRODUCED**

All38 bounded forwards were finite and bitwise identical to their historical successful TRAIN-cache vectors. No fix or causal mechanism is established. No training retry is authorized by this result.

| Item | Verified result |
|---|---|
| Execution source | `f8dbcd12f9e06ff115081caac9565744192bdaf7`, following local investigation `459d694` |
| Instance | One Lambda `gpu_1x_a10`, `us-east-1`, `c76720de56ce4eb0995700ecc6a08604`; verified$1.29/hour |
| Bounds | $1 soft / $2 hard; one instance, no second launch;38 forwards over33 distinct TRAIN rows |
| Stage A | Row32 twice: finite `(3072,)`, bitwise-identical repeats and historical cache |
| Stage B | Rows30?33: all finite and bitwise identical to historical cache; row32 unchanged from Stage A |
| Stage C | Fresh model load and seed reset, then rows1?32 only: all finite and bitwise identical to historical cache; row32 unchanged after31 preceding forwards |
| First invalid boundary | None observed. Conditional layer tracing was not invoked because no stage failed |
| Forbidden work | Zero optimizer/backward steps, normalization, head fitting, HPO, DEV/challenge upload/access, protected test, Producer, full Shimmer or multi-round work |
| Estimated cost | **$0.241891** conservative elapsed-time upper bound, not an invoice;675.044seconds from launch request through independent empty-inventory confirmation |
| Teardown | Provider termination confirmed2026-09-17 15:19:58 UTC; independent empty inventory and provider/local temporary SSH removal confirmed15:20:03 UTC |

## Runtime and binding

The same provider image as the failed final run was used: `lambda-stack-24-04`, version `24.4.4-2141`, image `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0`. Observed Linux kernel6.8.0-1046-nvidia, glibc2.39, Python3.12.3, NVIDIA A10 compute capability8.6, driver**580.105.08**, CUDA runtime**12.1**, cuDNN**9.1.0**. All package pins passed: Torch2.5.1+cu121, Transformers4.51.3, PEFT0.15.2, bitsandbytes0.48.2, Accelerate1.10.1, NumPy2.0.2, tokenizers0.21.1, safetensors0.5.3, huggingface-hub0.30.2 and Jinja2 3.1.4.

Before inference, the payload/source hashes, frozen base/model/tokenizer assets, canonical step120 adapter and448 loaded adapter tensor hashes were checked. Both initializations matched prepared base-state hash `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18`. Base/model revision, serialized IDs, eager attention, BF16 autocast, inference mode, seed7, deterministic algorithms and disabled TF32 matched the failed extraction path. The unused frozen head was instantiated solely to reproduce the original loader's RNG consumption; it was never forwarded or fitted. Selected HPO values remain unchanged.

Every forward has a persisted receipt with input/mask hashes, raw/pooled/vector shape/dtype/device and finite summaries, adapter enabled/merged state, dropout, quantized compute dtype, autocast/inference state, RNG/settings and extraction-source hashes. All raw hidden tensors and vectors were fully finite. Row32 raw shape was `(1,781,3072)`, FP32 on `cuda:0`; its pooled vector was `(3072,)`, FP32. NaN/+Inf/-Inf counts were all zero. Sixteen loaded CUDA/Torch/bitsandbytes library files were hashed; all forwards reference the same library identity `d8c6e9df84f4b3f70072e675a83f65cf9345e728966120050a554aa1cea4a79e`.

## Vector comparisons

| TRAIN row | New cloud vs historical max absolute difference | New cloud vs local max absolute difference |
|---|---:|---:|
|30|0 (bitwise equal)|0.194811522961|
|31|0 (bitwise equal)|0.203556224704|
|32|0 (bitwise equal)|0.190534234047|
|33|0 (bitwise equal)|0.218060001731|

All38 new vectors match historical vectors bitwise. Every repeated cloud comparison, including row32 across stages A/B/C and a fresh model initialization, is also bitwise equal. The verified saved31-vector prefix from the FAILED final attempt still differs from this new prefix by up to **0.16882681846618652**. Thus neither that attempt's drift nor its row32 failure recurred. This does not explain why the earlier run differed.

The local/cloud differences are reproduced by the saved-vector comparison and remain attributable only to an unisolated runtime difference; this diagnostic does not identify which differing local package/device/kernel caused them. It does not establish that local drift and the original failed-cloud drift share a mechanism.

## Evidence, verification and limits

The56,638,008-byte archive was downloaded and SHA256-verified at15:18:36 UTC, before the15:18:42 UTC termination request. Archive SHA256: `f34a7f474e7cf8637e9c207db46fb57d96d0c8dabbebcfc68cb92f3e359704e6`. Execution-manifest SHA256: `48a2db56c85a8f0187d1bb025d787ee481dc881888d14fc3f8806b60aec51714`. Runtime-bundle SHA256: `ac218936a75cde655d713d7b72cbc38fedb9c88ebfb35eb37cf6304a1c69c2fd`.

Post-teardown verification independently recomputed source/payload/receipt/vector hashes, all historical/local/cloud comparisons, exact stage ordering, inference state, data-boundary counts and collection-before-termination chronology. All22 prelaunch contract tests passed. Bulk vectors, archive and frozen adapter remain locally retained; text evidence and their hashes are preserved in Git.

- [Recomputed results](auditor_feature_remote_run/RECOMPUTED_RESULTS.json)
- [Original failed-prefix comparison](auditor_feature_remote_run/FAILED_PREFIX_COMPARISON.json)
- [Runtime/GPU/driver identity](auditor_feature_remote_run/downloaded/evidence/hardware.json)
- [CUDA/library hashes](auditor_feature_remote_run/downloaded/evidence/libraries-d8c6e9df84f4b3f70072e675a83f65cf9345e728966120050a554aa1cea4a79e.json)
- [Row32 Stage A receipt](auditor_feature_remote_run/downloaded/evidence/A-00-row32.json)
- [Row32 after the32-row prefix](auditor_feature_remote_run/downloaded/evidence/C-31-row32.json)
- [Evidence manifest](auditor_feature_remote_run/EVIDENCE_MANIFEST.json)
- [Independent teardown confirmation](auditor_feature_remote_run/independent_inventory_confirmation.json)

The original failing tensor, its precise nonfinite/shape pattern and original transient driver/kernel/allocator state remain unavailable. Instrumented successful replays cannot reconstruct those missing facts. Order dependence did not appear in the authorized fresh-load32-row replay; it is not disproved for every possible transient execution state. There is no established cause, first invalid boundary or proven minimal repair.

The diagnostic is complete and its authorization is consumed. **Wait for operator authorization before any final Auditor training retry.** No automatic push or further cloud work follows. The defined next training stage remains the frozen1792-row/896-update final Auditor retry, with no intervening HPO/optimization stage. Producer Optuna HPO remains post-roadmap, after packaging.
