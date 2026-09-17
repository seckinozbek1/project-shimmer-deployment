# Final Auditor feature-extraction blocker investigation

Status: **ROOT CAUSE UNRESOLVED; diagnostic instrumentation preserved.** This is not a blocker-fix or training-readiness claim. Starting checkout: `b00e00a`; failed execution: `b4f7e8247391e2278a7b7a1ba84f6b5915c56ced`.

The original row32 tensor was not retained. Its actual shape and NaN/Inf pattern remain unknowable from the existing artifact. The prior 31-vector drift establishes a representation difference, not a cause. No hyperparameter, dataset, architecture, optimizer, or HPO change was made.

## Explicit extraction-path comparison

The downloaded executed Python sources were checked against each run's execution manifest. All inspected hashes matched. See [machine-readable comparison](auditor_feature_blocker/source_comparison.json). The successful current-runtime cache extraction and failed final extraction use the same mathematical forward and pooling expression.

| Item | Successful current-runtime / HPO path | Failed final-training path and finding |
|---|---|---|
| 1. Base model/revision | `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`; actual architecture `LlamaForCausalLM`, hidden size3072 | Same model, revision, all8 asset hashes and weight SHA256 `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`. Both saved prepared base-state hashes are `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18`. |
| 2. Canonical adapter/tensors | Step120 file SHA256 `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`; config `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6` | Same. `verify_adapter` verifies all448 loaded FP32 tensors, shapes and byte hashes against the safetensors inventory before extraction. Inventory digest `f4717343a66d6f84fe76253b9ca6151da402b0825d0cd573324ce38ae1d16b82`. |
| 3. Activation/enabled state | Cache extraction loads only `historical_reference`; asserts active adapter each row. HPO explicitly selects reference then fork for admission. No disabling or merging call. | Loads the same sole reference, no disabling or merging call. Missing per-row activation assertion is an observability/guard difference, not demonstrated adapter deactivation. Historical layer enabled flags were not saved; new telemetry captures them. |
| 4. Train/eval | `freeze_slots` freezes parameters and calls `model.eval(); head.eval()`. HPO observe repeats eval. | Same freeze/eval helper before feature pass; no intervening train call. Historical per-module flags were not saved. |
| 5. Dropout | Canonical LoRA config has0.05; eval disables dropout. HPO selected dropout is installed after cache admission, on `classifier_fork`. | Canonical dropout0.05 loaded in eval. Selected0.05 is installed by `backend.set_dropout(.05)` only AFTER the1792-row extraction, normalization,200-step head fit and fork/parity work. It cannot have affected failed initialization. No hyperparameter alteration is justified. |
| 6. Dtypes | NF4 base loaded with `torch_dtype=bfloat16`; `prepare_model_for_kbit_training` promotes nonquantized parameters toFP32; adapter verified FP32. Vector explicitly converted toFP32. | Same loading/preparation/conversion. Historical raw hidden dtype was not recorded, so it is not inferred from autocast. New guard records raw/extracted/vector dtypes and quantized-layer compute state. |
| 7. Autocast | Cache: CUDA BF16 autocast inside inference mode. HPO observe: CUDA BF16 autocast inside no_grad. | Cache and final extraction both use inference mode and CUDA BF16 autocast. HPO no_grad is an explicit contextual difference from both extraction loops, not a difference between successful and failed extraction. |
| 8. Device | Linux x86_64, single NVIDIA A10, all base layers device0; IDs and all-ones mask CUDA | Same runtime gates and placement. Actual failing tensor device and driver-level state were not retained. |
| 9. Attention | Explicit eager attention, cache disabled, gradient-checkpoint preparation with reentrant=True; eval feature pass | Identical. No flash/SDPA selection introduced. Exact GPU library/driver build equivalence is not established by package-version equality. |
| 10. Tokenizer | Pinned tokenizer assets; preparation uses chat template with generation prompt, then `add_special_tokens=False` | Same frozen assets and precomputed IDs. No tokenizer is instantiated in either feature-extraction loop, so tokenizer settings cannot change IDs during those loops. |
| 11. IDs/masks | Serialized TRAIN IDs; one unpadded example per forward; `ones_like(ids)` attention mask | All1792 ID/order/hash receipts match the TRAIN-only final records. Row32 has781 tokens, hash `8373a53cbba09703d6a0a6ae162cb33437dcc2f1c7bfd8f44e2440d50f794fdc`. Masks constructed identically. |
| 12. Length/padding | Preparation asserts length<=1056; tokenizer call has no truncation/max_length/padding override | No runtime re-tokenization, truncation, padding or resize. Final validates existing ID lists and <=1056 ceiling. |
| 13. Layer | Decoder output `.last_hidden_state` | Same final decoder hidden state, not embedding/intermediate layer or LM logits. |
| 14. Pooling | `[0,-1]`, then `.float().cpu().numpy().copy()`; HPO uses `[:,-1,:]` and returns row0 | Cache and failed final extraction expressions identical. HPO result is the same last-token vector convention. |
| 15. Shapes | Expected raw `(1,L,3072)`, pooled `(3072,)`; HPO intermediate `(1,3072)` | Previous cache and31 final saved vectors pass `(3072,)`. Original row32 raw AND pooled shapes were not retained. New guard explicitly records/refuses a wrong raw shape before indexing. |
| 16. RNG/determinism | Seed7 for Torch/CUDA/NumPy; deterministic algorithms enabled; TF32 disabled; launcher `PYTHONHASHSEED=7`, `CUBLAS_WORKSPACE_CONFIG=:4096:8` | Same. Final also sets CUBLAS in runtime before Torch import. Both create an unused random head before extraction; eval dropout is off. RNG state at failing forward was not captured. New telemetry hashes RNG states without changing seeds. |
| 17. Packages/runtime | Python3.12.3; Torch2.5.1+cu121, CUDA12.1, Transformers4.51.3, PEFT0.15.2, bitsandbytes0.48.2, Accelerate1.10.1, NumPy2.0.2, tokenizers0.21.1, safetensors0.5.3, HF hub0.30.2, Jinja2 3.1.4 | Cloud pins/preflight match; final and HPO runtime-contract objects are identical. Matching versions do not prove identical kernel behavior, driver state, quantized compute state or transient hardware behavior. None of those is established as the cause. |

## Bounded local reproduction

The local GPU is a GeForce RTX3070Ti Laptop, with Windows/Python3.12.3, verified Conda Torch2.5.1/CUDA11.8, bitsandbytes0.49.2, Accelerate1.13.0 and NumPy1.26.4. These differ from the cloud runtime. Other listed forward-related package pins match. PEFT0.15.2 was downloaded without dependencies into ignored `.tmp/auditor_feature_deps` solely to enable this diagnostic; no global package environment was changed.

The default Conda Torch import hit a duplicate OpenMP runtime error. The existing `local_inference_runtime.configure()` verified12,500 cached package files and selected the clean process-local Torch overlay, without suppressing the error. Early harness attempts stopped before model loading: the cloud data guard matched PyTorch's own benchmark source, sandbox access to the elevated PEFT install failed, and an elevated shell selected a different interpreter. The final probe uses an explicit interpreter, network-denial hook and project-scoped dataset boundary. No GPU model crash occurred, so a CPU fallback was unnecessary.

A standalone row32 run produced a finite `(3072,)` vector twice, with bitwise-identical repeats. Maximum difference from the corresponding historical vector was `0.19053423404693604`. All base asset hashes, the prepared base-state hash, and448 loaded adapter tensors matched. This proves local execution, not cloud equivalence. The initial standalone receipt sampled source hashes before a telemetry-only enhancement during startup; the final neighborhood receipt is the authoritative final-source validation.

Final-source neighborhood probe: all four rows produced finite `(3072,)` vectors and bitwise-identical repeats. The base remained unchanged. Row32 also matched its standalone local run bitwise. [Full receipt](auditor_feature_blocker/gpu_rows30_33/probe.json).

| TRAIN row | Tokens | Maximum absolute difference from prior cache |
|---|---|---|
| 30 | 776 | 0.194811522961 |
| 31 | 767 | 0.203556224704 |
| 32 | 781 | 0.190534234047 |
| 33 | 765 | 0.218060001731 |

Only4 distinct TRAIN examples and10 total forwards were evaluated across the standalone and neighborhood probes. No normalization, head fitting, backward pass, optimizer update or evaluation occurred. All recorded forbidden/evaluation accesses in successful probes are zero.

The entire original31-row prefix was not re-extracted. Its historical maximum drift remains `0.16882681846618652`; it has NOT been shown eliminated, reduced, or legitimately expected. Finite differences under the differing local stack are observations only, not an explanation of the failed A10 run.

## Preserved changes and checks

`auditor_feature_diagnostics.extract_train_vector` now serves both the live final initialization loop and the offline bounded probe. Successful forwards retain the original pooling and conversion. On failure it fsyncs strict JSON BEFORE raising, including row/index, prompt/input/mask hashes, raw and vector shapes, dtype/device, finite/total counts, bounded flat-index samples of NaN/+Inf/-Inf, finite min/max/mean/population-std/norm, train/eval and adapter enabled/merged state, dropout, quantized compute dtypes, actual autocast/inference state, RNG/settings, runtime metadata and extraction source hashes. An additional startup receipt records state before the first feature. The guard does not sanitize, resize, skip, or substitute a cache. Diagnostic-write failure also stops admission.

Seven guard tests pass with real Torch tensors: original finite pooling and arguments, nonfinite durable evidence, wrong shapes (including empty sequence), all-NaN bounded summaries, diagnostic I/O failure, TRAIN-only scope, and live wiring before cache writes. Neutralizing the finite predicate makes the nonfinite regression fail. The existing10 final workflow tests also pass. These tests establish fail-closed diagnostics; they do not claim to predict an unreproduced hardware/runtime failure before paid compute.

The helper is included in the future packaging tool list. The consumed launch marker, old sealed experiment, historical bundles/evidence, four selected hyperparameters and all authorizations remain unchanged. The historical seal intentionally no longer matches edited live source, and the existing consumed-attempt gate still prevents resealing/launch. No new seal, permit, resource or training run was created.

## Unresolved facts and minimum remote diagnostic (proposal only)

Unknown: original raw/vector shape; which values were nonfinite, if any; first layer/operator at which validity was lost; actual per-layer adapter/dropout/compute state; driver/library state; and whether failure requires the preceding31 forwards. The31-vector drift has no established cause. No correction to forward mathematics is justified by current evidence.

If separately authorized, the minimum remote diagnostic uses the exact pinned Linux/A10 runtime and canonical assets, no optimizer/head fitting/evaluation, and the new guard: row32 twice with source/model/adapter/runtime receipts, comparing only the corresponding historical TRAIN vector. Capture GPU driver/library identity as well. If it fails, use bounded per-layer finite summaries on that row to locate the first invalid boundary. If row32 alone passes, try rows30?33; only if needed to test execution-order dependence, replay the32-row prefix. Do not extract1792 rows. Stop after evidence collection; no automatic cloud retry is implemented or launched.

After an established repair, the next paid TRAINING stage remains a retry of the already defined1792-row/896-update final Auditor workflow with the frozen four HPO values. No tuning/optimization stage is inserted. Producer Optuna HPO remains post-roadmap, after packaging. DEV/challenges, protected test, Producer, full Shimmer and multi-round work remain untouched.
