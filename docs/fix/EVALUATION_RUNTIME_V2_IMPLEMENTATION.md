# Evaluation runtime V2: prospective, local-only release

**EVALUATION_RUNTIME_V2_READY**

This status means a separately authorized Producer checkpoint-120 evaluation-only experiment can be proposed. It does not authorize model execution, acquisition, cloud provisioning, retraining, other folds or protected access. The release contains execution mechanisms, deterministic admission tests and a frozen protocol; it deliberately contains no provider launcher or automatic model-loading CLI.

Historical pilot outcome remains `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE`; `FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`. No role selection exists. This release does not modify the training release with SHA-256 `bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d`.

## Release contents and mechanics

Directory: `tuning/second_tuning_eval_runtime_v2/`.

| Component | Purpose |
|---|---|
| `audit.py` / `audit_results.json` | Saved-output length/atom diagnostics, same-ID prefix comparisons, historical throughput, exact historical trace callback CPU probe |
| `source_evidence.json` | Source hashes, tested Git source references and pinned Transformers evidence; explicit unavailable PEFT-source limitation |
| `eval_runtime.py` | Scoped evaluation state, durable raw outputs, single-example generation mechanism, cache probes and fail-closed future session admission |
| `telemetry_worker.py` | Separate-process CPU/RSS/host/GPU resource sampling; no Torch or PEFT import |
| `boundary.py` | Executed dry-run audit hook denying network/subprocesses, model weights, protected/Auditor artifacts and historical writes |
| `protocol_builder.py` | Separate adapter byte-hash binding, then protected/weight/network-denying tokenizer-only dry-run |
| `prepared_dev.json` | Exact 60 ordered Producer prompts, token IDs and masks |
| `protocol.json` | Model/adapter/settings/population bindings, fixed controls, speed/equivalence gates and cost projection |
| `checks.py` / `test_results.json` | Local deterministic tests and effect proofs |
| `historical_preservation.json` | Byte hashes for 125 historical files |
| `adapter_binding.json` | Verified saved checkpoint-120 adapter/config hashes; no tensor loading |
| `freeze.json` | Prospective release file bindings and readiness; cloud/model/training authorization remains false |

The established avoidable mechanism is the historical global observer trace entering third-party Python calls throughout generation. The optimized core rejects ambient `sys.gettrace()`/`sys.getprofile()` callbacks and installs none. It uses explicit per-example boundary instrumentation, with raw-output persistence before scoring. It does not remove required observations to create a misleading throughput number.

The context records each module's training/checkpointing state, owned model/generation configuration objects and their identity, checkpoint function identity, parameter/device/dtype/requires-grad/version/gradient-buffer identity and active adapter state. It enters eval and inference mode, makes cache intent explicit, and restores state in `finally`, including mixed initial submodule modes. It verifies restoration and weight-version invariants. Actual weights are never merged, cast, copied or updated by the context.

**Checkpointing is not disabled/re-enabled.** In pinned Qwen2 the checkpointing branch requires training mode, so eval already makes it inactive. Removing hooks or changing checkpoint functions would be an unnecessary methodological change. Both model and generation cache configuration states are restored; effective `use_cache=True` is also supplied in unchanged frozen generation kwargs.

The core consumes prospectively bound input IDs. It performs one CPU tensor construction/device transfer per example, keeps batch size one and adds no padding. Two CUDA synchronizations bracket each generation, with one raw decode plus native-special-token decode after timing. It retains raw IDs, both text forms, stop reason, prompt/token hashes, model/adapter identity, generation wall and tensor preparation wall. TTFT/decode-only wall remain explicitly unavailable.

GPU utilization, process RSS, CPU and host RAM sampling move from a shared Python thread to a separate process at approximately one second. Allocated/reserved memory and CUDA high-water counters are captured at example boundaries outside the generation timer. This changes allocator time-series resolution from one-second sampling to boundaries; peaks remain observable via high-water counters. It is not described as an unchanged sampling grid. The generation thread does not wait for sampler polling or file flushing. Raw JSONL is flushed/fsynced once per completed example, before semantic scoring. A future harness must persist returned parsed/frozen metric records separately after raw capture and retain failure artifacts.

## Frozen semantics and identity

**Frozen semantics unchanged: yes.**

- Base: `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision `bdd404162d94997f390efbfa660eb3f21cbbc81d`, frozen base-weight SHA-256 `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`.
- Saved checkpoint-120 adapter SHA-256: **`3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6`**, verified by byte hashing.
- Adapter config SHA-256: `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507`.
- Exact same tokenizer/config assets, prompt strings, prompt token IDs, 60 canonical DEV IDs/order, BF16/eager/quantization/runtime pins and deterministic settings.
- Same active LoRA state; no merge, disable-adapter comparison, inference-only recast or base substitution.
- Same kwargs: `do_sample=False`, `num_beams=1`, `use_cache=True`, `max_new_tokens=288`, `eos_token_id=[151645]`, `pad_token_id=151654`.
- Same strict contracts, frozen row scoring, aggregate metrics and prospective selection gates. No repaired outputs, alternative rationales, cap reduction or altered logits processors.

All 60 rebuilt prompt hashes match the historical step-60 evidence. Both tokenizer rendering paths produce the same input IDs for every DEV row. The new complete evaluation must use these exact identities. It reports checkpoint-120 gates as a **new evaluation protocol result**, not an edit to the interrupted pilot or an automatic role selection. Auditor is still unexecuted.

Removing a Python trace and moving telemetry should preserve the mathematical greedy task. No real token-equivalence measurement was made here. Loader/preparation state, GPU numerical execution or future changes in call order could still change a token near an argmax tie. A fixed exact-token control is therefore mandatory. No byte-identical generation or actual speedup is claimed from local tests.

## Fixed future control and admission sequence — NOT EXECUTED

1. Obtain a **new explicit authorization** binding action `producer-checkpoint120-evaluation-only`, this runtime freeze/protocol, exact adapter hash, Producer, canonical split and checkpoint 120. `EvaluationSession` rejects missing/mismatched scope. No historical permit is reused.
2. Before any weight access, validate the new release, original V2 binding, dependencies, fresh process, deterministic environment, single BF16 GPU, price/budget and absence of protected receipts. Acquire/load only the exact base and saved adapter under that future authorization. No current cloud price/capacity query was made.
3. Reproduce the historical pinned model load and k-bit preparation/LoRA wrapping, then load the saved adapter with complete key, shape, dtype, device and hash checks. Do not invoke the training loop or create an optimizer. The future harness must implement and verify this integration before control admission; it is not an automatically runnable cloud workflow in this release.
4. Run a separately costed cache preflight on the **first fixed control ID**, once with the historical-observer reference and once optimized. `cache_probe` observes pinned Qwen2Model below PEFT: first/second forward input length, effective cache flag, training/grad flags and incoming/returned cache length. Require a prefill cache, a one-token incremental input and a cache length increment of one. Missing/contradictory evidence is NO_GO. Hooks are removed in `finally` and never run during speed trials.
5. Run the six controls below, in order, **reference then optimized for each ID**, on the same resident base/adapter. The historical-safe reference uses the exact historical observer callback AST over generate; it does not rerun training or claim to recreate training-resident gradient buffers. Both use the same mathematical generation task, current model instance, tensors, timing boundary and raw-output handling. Keep all speed-trial observations; no result-dependent warmup deletion or sample replacement.
6. Require identical prompt/input IDs, exact generated token sequences and frozen row metrics, plus the frozen speed criteria below. Any mismatch or missed speed gate is **NO_GO**. Do not redefine equivalence, lower the speed threshold, repeat controls to obtain a favorable result, change weights or switch to full DEV.
7. Only after admission, generate **all 60 DEV rows afresh, from item 1 through 60**, in one new exclusive output directory. Neither historical rows nor control/preflight rows count as final DEV. Any partial run stays partial; the session disallows automatic resume or a second full attempt.
8. Persist all raw/parsed outputs and metrics, hash evidence, terminate any future cloud resource before local report work. No Auditor, protected evaluation, other fold, retraining or full-pipeline continuation follows automatically.

Fixed positions are zero-based **0,10,20,30,40,50**, selected by position rather than observed quality. IDs:

| Position | Producer canonical DEV ID |
|---:|---|
| 0 | `shimmer2-producer-document-045` |
| 10 | `shimmer2-producer-document-055` |
| 20 | `shimmer2-producer-document-140` |
| 30 | `shimmer2-producer-document-150` |
| 40 | `shimmer2-producer-document-160` |
| 50 | `shimmer2-producer-document-275` |

### Exact speed rule

Require optimized prefill-inclusive aggregate output rate **>= 4.438538339317307 tok/s**, and optimized/reference paired aggregate rate ratio **>= 2.0**. Also require exact token, prompt and metric identity on all six IDs. Invalid/nonfinite/nonpositive timing evidence fails closed.

The absolute floor is **one half of the observed run-1 Producer aggregate rate (8.8770766786 tok/s)**. The paired doubling criterion additionally requires a material same-input improvement rather than relying on a different historical population. Together they require recovering a meaningful part of the observed approximately 4.7x regression while allowing considerable overhead relative to run 1. They are prospective admission criteria, not a promised benchmark or thresholds tuned on future control results.

PEFT 0.15.2 internals were not directly inspectable in the local environment. The future pinned installation must record source hashes and demonstrate actual device/activation/cache behavior before speed control. This uncertainty is not bypassed by assuming that a model config flag proves a live cache.

### PROJECTION, not measurement or authorization

At exactly the speed floor, use the unchanged cap rather than extrapolating unseen semantic outcomes:

| Allowance | Seconds |
|---|---:|
| Full 60 DEV, at most 17,280 output tokens | 3,893.17 |
| Six reference controls at historical 1.88001 tok/s | 919.14 |
| Six optimized controls at the speed floor | 389.32 |
| Additional cache-probe reference + optimized pair | 218.08 |
| Setup allowance | 600 |
| Teardown/evidence reserve | 600 |
| Total projected | **6,619.71 / 110.33 minutes** |

At the **historical**, unqueried-current A10 rate of $1.29/hour, this projects **$2.3721**. This is conditional planning arithmetic, not a guaranteed upper bound on wall time: prefill varies by prompt, setup can exceed its allowance, controls may fail and actual future prices may differ. At the floor the full generation phase alone is 64.89 minutes. Faster recovery toward run-1 throughput would shorten it, but is unmeasured. A new authorization must set actual budget/watchdog limits and revalidate economics before provisioning; this task spends nothing on cloud or APIs.

## Batching and merging

Batching is **design-only and not adopted**. Any later batch design must use decoder-appropriate padding and masks, preserve each prompt boundary and stop rule, extract per-example raw token IDs and score each row independently. EOS padding must not be mistaken for generated content. Variable lengths and a batch-wide cap can change token extraction and floating execution order; an independently frozen equivalence protocol would be required. The current release fixes batch size at one.

Adapter merging is not implemented or proposed as a shortcut. Quantized-base merging/requantization can change numerical weights and would require a separate rigorous equivalence design. The saved adapter is already available; no repetition of the 120 training updates is justified by this runtime audit.

## Local validation and limitations

**50 deterministic tests pass**: 37 runtime/control effect tests, 10 diagnostic metric/parser tests and 3 historical artifact/evidence tests. They cover normal/exception/early-termination restoration; mixed module flags and shared config identities; actual pinned Qwen cache-guard AST behavior; exact historical callback dispatch into a foreign function; raw durability before scoring and on scoring failure; fixed synchronization count; memory-counter retention; independent telemetry process; authorization/role/fold/cap/prompt/token/adapter mismatches; no-control/no-cache/no-stitch/no-resume gates; and filesystem/network/weight/protected/Auditor denial.

The tokenizer-only dry-run separately verifies 60 prompt hashes and both tokenization paths, with an executed boundary denying model-weight opens and network/process calls. Adapter byte hashing and historical archive hashing are explicit separate read-only phases, not tensor/model loads inside the dry-run. The original protected receipts remain absent, and no protected file was read by a denial test.

Torch 2.5.1 import in this local Anaconda installation aborts with duplicate Intel OpenMP initialization, including isolated/no-site attempts. An MKL sequential-setting trial also failed. No `KMP_DUPLICATE_LIB_OK` override, dependency installation, DLL mutation or model load was used. Inference-mode lifecycle tests use a clearly named stand-in; they do not certify the real local Torch binary or future CUDA behavior. The separately inspected pinned Transformers source and future preflight/control requirements remain explicit.

Useful local commands (read the freeze note before regenerating evidence):

```text
python -B tuning/second_tuning_eval_runtime_v2/checks.py
python -B tuning/second_tuning_eval_runtime_v2/release.py verify
```

`audit.py` and `protocol_builder.py` generated the release evidence before freezing. Re-running the CPU timing probe or regenerating prospective protocol files after freeze may change bytes and must not silently create a replacement release. The historical pilot files are never regeneration targets.

No cloud, training, real Qwen/Phi generation, weight change, protected access, Auditor execution/redesign, folds 1–4, paid API, full pipeline, multi-round or push occurred. Runtime READY authorizes none of these actions.
