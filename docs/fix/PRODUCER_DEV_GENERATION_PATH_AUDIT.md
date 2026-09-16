# Producer DEV generation path and token-efficiency audit

Local-only audit, 2026-09-16, starting from `886dc78a89c8c3162c2f0e5195ca502b053117b9`.

**GENERATION_PATH_DIAGNOSIS_COMPLETE**

Primary execution diagnosis: **TELEMETRY_OVERHEAD**, specifically the V2 global Python observer trace. Its unnecessary execution overhead is established by source and a CPU-only intervention. It is the leading supported explanation for the additional run-1-to-V2 slowdown; its exact contribution to GPU generation wall time remains unmeasured. This is not a measured GPU ablation or an exclusive attribution of every lost second.

Output-length diagnosis: **REFUSAL_TO_SUBSTANTIVE_SHIFT**. On the same 42 IDs, 28 refusal-to-non-refusal transitions account for **99.8628%** of net additional tokens. There is no observed prose or duplicate-atom drift.

The historical result remains **SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE**, with `FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`. No checkpoint was selected, no missing output generated, and no historical metric/verdict file changed. A 125-file historical SHA-256 baseline, including the retained adapters/archive, passes preservation verification.

## Measured speed classes and timing definitions

| Path | Outputs | Output tokens | Generation wall, seconds | Output tokens/second |
|---|---:|---:|---:|---:|
| Earlier bounded compact Producer | 1 | 259 | 12.3505 | 20.9708 |
| Earlier bounded source-copy reference | 1 | 273 | 12.6981 | 21.4993 |
| Earlier bounded serial Producer | 1 | 259 | 12.1222 | 21.3658 |
| Run 1 Producer step 8 | 32 | 4,287 | 484.3801 | 8.85049 |
| Run 1 Producer step 16 | 32 | 4,194 | 471.0020 | 8.90442 |
| Run 1 Producer combined | 64 | 8,481 | 955.3821 | 8.87708 |
| V2 Producer step 60 | 60 | 1,787 | 953.4479 | 1.87425 |
| V2 Producer step 120 — **PARTIAL_PREFIX_ONLY** | 42 | 5,945 | 3,162.2144 | 1.88001 |

These are **prefill-inclusive aggregate output tokens / generation wall**, not isolated decode throughput. None has measured TTFT or separate prefill/decode wall. Tokenization occurs outside these generation timers. Run 1 synchronizes before starting its timer and after generation; V2 starts its timer just before the pre-generation synchronization. The bounded wrapper lacks explicit synchronization at its timer boundaries, although generation's own token decisions synchronize as needed. That smaller timing-definition difference prevents treating all speed ratios as controlled benchmarks.

Run 1/V2 prefix aggregate ratio is about **4.72x**. The bounded path differs in prompt population, adapter/preparation, attention defaults, dtype arguments, output cap and time stop; its approximately 21 tok/s is a contextual speed class, not an expected tuned-model guarantee. V2 prompts contain 563–743 tokens (mean 653.217); the bounded examples contain 482 or 610. Longer final-checkpoint answers explain greater per-example wall, but throughput stayed almost constant between V2 checkpoints. That distinguishes the two axes.

Historical evidence: `remote_short_burst_secure_20260915/evidence/probe/probe.json`; run-1 Producer `dev-8.json` and `dev-16.json`; V2 `producer_events.json` and `producer_raw_dev.jsonl`. Run 1 was not rescored; only recorded timing/token counts were summed.

## Source-level generation-path comparison

The bounded wrapper was inspected from actual tested Git commit `c342033e5d09654cdbaaf283879a9ee37764146b`, not assumed equal to current HEAD. Run-1 train/evaluation source matches tested commit `a704fe8ca04032932981f32643aebad98ef2f619`. V2 is the preserved `a818d43` executor/envelope. Exact file/function hashes and line spans are in `tuning/second_tuning_eval_runtime_v2/source_evidence.json`.

| Concern | Earlier bounded path | Run 1 DEV | V2 pilot DEV |
|---|---|---|---|
| Load | Shared resident `_load_qwen`, pinned cached snapshot, device 0 | One load per role, exact pinned base, local files only | One load per role, exact local snapshot path and weight hash |
| PEFT wrapping | None | `prepare_model_for_kbit_training(True)` then `get_peft_model(LoraConfig)` | Same preparation/wrapping |
| Adapter | None | Active in-memory LoRA, separately saved checkpoints | Active in-memory LoRA, separately saved checkpoints; no reload per item |
| Gradient checkpointing | No training preparation | Enabled for training; flag not disabled for DEV | Same |
| Train/eval | Loader inference state; no training phase | `model.eval()` before DEV; `model.train()` next update | Same explicit transitions |
| Gradient context | `torch.no_grad()` | `torch.inference_mode()` | `torch.inference_mode()` |
| `model.config.use_cache` | Snapshot true; no training mutation | False during training, true before DEV | False during training, true before DEV |
| `generation_config.use_cache` | Inherited true default | No persistent mutation; explicit generation kwarg true | Same explicit generation kwarg true |
| Cache implementation | Default; no explicit static/offload cache | Default cached generation | Default cached generation |
| Attention | No explicit override; actual backend not logged | Explicit eager | Explicit eager |
| Dtype arguments | Prequantized loader has no explicit `torch_dtype`; checkpoint quantization governs compute | BF16 load, then k-bit preparation and LoRA | Same |
| Inputs | CPU tokenizer tensors moved once per item to model device | Same | Same |
| Tokenizer | Resident shared tokenizer | Loaded once per role, exact asset hashes | Same |
| Template/tokenization | Native template on each dispatch | Render/tokenize each DEV item, repeated at next checkpoint | Same |
| Padding | Single-example, no padding requested | Same | Same |
| Generation batch | 1 | 1 | 1 |
| Greedy/sampling | `do_sample=False` on generation config | Explicit frozen greedy kwargs | Explicit `do_sample=False`, `num_beams=1` |
| Cap/stops | 384 new tokens plus 25-second max-time setting; inherited EOS set | Frozen role cap/native terminal IDs | 288 new tokens; explicit EOS `[151645]`, tokenizer pad ID |
| Synchronization | No explicit timer synchronization | One before and one after each generate | One before and one after each generate; first sync inside timer |
| Resource telemetry | Same-process background Python thread, subprocess `nvidia-smi` | Same-process background thread at about 1 second | Same-process background thread at about 1 second |
| Observer instrumentation | Explicit call-boundary records | Load/optimizer/module/adapter wrappers | Load/optimizer/generate wrappers **plus global `sys.settrace`** |
| Score collection | After generation, fixture-specific checks | After generation, frozen row metrics | After generation, frozen row metrics |
| `output_scores` / return dictionary | Not requested | Not requested | Not requested; tensor result |
| Logits processors | Library defaults from inherited config | Frozen greedy config/default processors | Same task; inherited sampling-only fields warn but do not enable sampling |
| CUDA cleanup | `del inputs,out` and `empty_cache()` after `call_local` generation timer | No per-item empty-cache call | No per-item empty-cache call; process/GPU cleanup after role |
| Python callbacks during tokens | Normal Transformers/PyTorch execution | Normal Transformers/PEFT execution and any preparation hooks | Those same calls enter the **global observer trace callback** |
| Raw persistence | Call-level JSON after generation | Final DEV JSON after checkpoint evaluation | Flush/fsync JSONL per completed example, before scoring, outside generation timer |

Relevant application entry points: `scripts/agent_wrapper.py:_load_qwen/call_local`, `tools/remote_short_burst_probe.py`, `tuning/first_domain_agnostic_v1/train.py:train`, `evaluation.py:LocalGenerator.__call__`, `tuning/second_domain_agnostic_v2/train.py:execute`, and `tools/second_tuning_remote.py:train`.

## KV-cache, autograd and state lifecycle

The cache-disabled hypothesis is **not supported**. Both frozen Producer specs explicitly supply `use_cache=True` to `generate`; this takes precedence over generation-config defaults. V2 also sets `model.config.use_cache=True` before DEV. The pinned generation-config file omits `use_cache`, whose Transformers default is true. Its `do_sample=True` is overridden by the frozen explicit `do_sample=False`; native EOS `[151645,151643]` is overridden by frozen `[151645]`. These distinctions are retained in the new protocol.

Pinned Transformers 4.51.3 `generation/utils.py` applies kwargs last in `_prepare_generation_config`, prepares a default DynamicCache when supported and cache is enabled, and passes effective `use_cache` into model kwargs. Pinned `Qwen2Model.forward` turns cache off only under `self.gradient_checkpointing and self.training and use_cache`. Its checkpointed-layer branch similarly requires `self.training`. Otherwise, cache is created when enabled and absent. Tests execute those exact source AST branches with stand-ins: eval + checkpointing flag + cache true creates the cache; training + checkpointing disables it.

`PreTrainedModel.gradient_checkpointing_enable` sets checkpointing flags/functions; the inspected implementation does not write `config.use_cache=False`. The **trainer itself** makes that assignment on every optimizer update. PEFT 0.15.2 is not installed or present in the accessible local wheel cache, and no network fetch was made. Its preparation and forwarding internals therefore were **not directly source-verified locally**. Whether its helper additionally mutates cache cannot honestly be asserted from local evidence. This does not establish a disabled DEV cache: the trainer later restores config true and passes an explicit true kwarg. Actual cache objects were not logged historically; future first-two-forward cache observations are mandatory rather than claiming they were measured.

| Point | Training flag | Checkpointing flag | Model config cache | Effective generation cache | Grad context |
|---|---|---|---|---|---|
| Update 60 | True | Enabled | False | Not generating | Training/autocast |
| DEV 60 | False via `eval()` | Remains enabled; Qwen branch inactive in eval | True | Explicit true | Inference mode |
| After DEV, before next update | Remains eval | Enabled | True | No live generation call | Inference block exited |
| Update 61 | True via `train()` | Enabled | False explicitly before forward | Not generating | Training/autocast |

The historical normal step-60-to-step-61 transition is coherent. An exception does not restore a live training context through a `finally`, but the bounded historical worker terminates instead of resuming; that is not evidence of training-mode generation. The new context restores state on normal return, exception and early termination without rewriting historical training.

Both tuned paths run in inference mode; there is no source evidence that autograd graphs were built for DEV. LoRA `requires_grad` flags and the most recent training `.grad` buffers remain until the next `zero_grad`; retaining buffers is memory state, not graph construction. Input IDs/masks are integer tensors, not gradient-requiring floating inputs. An input-embedding require-grad hook can remain from preparation; Transformers' implementation sets an embedding-output flag. The historical presence of that hook was not separately logged, and PEFT source is unavailable locally. Inference mode still precludes the ordinary backward graph. The prospective runtime does not remove/reinstall those hooks or change parameter dtypes; it asserts state restoration and relies on a future pinned-runtime effect check.

## Observer, telemetry, synchronization and I/O findings

V2 calls `sys.settrace(trace)` around the **entire** frozen executor, including every DEV generate. The callback compares each Python frame filename with `str(BASE/'train.py')`. Returning `None` for other frames suppresses their line tracing, but **does not avoid the global call event**. Both filename comparisons construct/format a Path on every non-target Python call. Transformers, PEFT and Torch Python dispatch therefore enter this observer repeatedly inside autoregressive generation. Run 1 has no corresponding global trace.

A local intervention compiled the exact historical trace callback AST and ran the same 30,001-call scalar workload five times with/without tracing. Median CPU wall was **0.004917 s untraced versus 0.783308 s traced**, a **159.32x synthetic slowdown**; results were identical. A separate deterministic test observed the actual callback enter a foreign function. This proves unnecessary observer overhead, **not a 159x model speedup**. It does not measure callback counts per generated token or isolate GPU wall attribution.

During saved generation intervals, historical telemetry shows:

| Interval | Samples | Median GPU utilization | Mean GPU utilization | Median process CPU |
|---|---:|---:|---:|---:|
| Step 60 | 929 | 5% | 8.04% | 99.7% |
| Step 120 — **PARTIAL_PREFIX_ONLY** | 3,089 | 5% | 6.42% | 99.7% |

One CPU core near saturation with low GPU utilization is consistent with the traced Python path. It is supporting evidence, not a controlled causality experiment. Device placement is pinned to GPU 0; there is no configured CPU offload path in this trainer.

The sampler is asynchronous but **in-process**, not out-of-process. It launches `nvidia-smi`, reads psutil/CUDA allocator counters, flushes a line and waits about one second. The generation thread does not join or await it per token; both share the Python GIL. This sampler architecture also exists in run 1 and is not by itself an isolated explanation for the new 4.72x difference.

Explicit CUDA synchronizations occur only at example boundaries, not per token in the observer. Output `.tolist()` / decode happen after the measured interval; frozen scoring and per-example JSONL/fsync also happen afterward. The wrapper additionally decodes/converts a result that the frozen executor converts/decodes again. That duplicate post-generation work is avoidable but excluded from the reported generation time. There is no observer per-token JSON write, `.item()` loop or resource-poll callback; the global trace still runs on Python calls within the token loop. Normal Transformers token decisions and stopping logic have their usual synchronizations in all paths.

The log contains 837 checkpointing-argument warnings and 103 each of temperature/top-p/top-k warnings under greedy generation. Their timestamps are not retained, so the checkpoint warnings cannot be assigned to DEV. The sampling warnings occur at generation setup, not evidence of sampling or per-token prose/logging. No warning suppression or sampling setting change is introduced.

Tokenizer/model reloads are not performed per DEV row. Prompt construction and tokenization repeat once per row and again at the second checkpoint; there is no immutable-prefix token cache. Tensor transfer is once per row to the fixed device. Row scoring and growing event JSON writes add end-to-end cost, but their exclusion from the generate interval prevents using them as an explanation for its entire low tok/s measurement. Separate tokenization/prefill/decode timings were not instrumented historically.

## PEFT findings and limits

Both tuning runs prepare the same quantized base and attach active LoRA modules once. No adapter switch, disk reload, merge/unmerge or repeated weight materialization appears in the DEV application loop. PEFT adds normal adapter forwarding work; the earlier untuned bounded path has none. That and attention/dtype/prompt differences can contribute to the bounded-to-run-1 gap, but their costs were not isolated. The same PEFT version/preparation in both tuned runs does not establish a PEFT-specific regression explaining the V2-only slowdown.

The new runtime does not merge adapters, recast them, bypass PEFT, change attention implementation or drop hooks. A future loader must reproduce historical k-bit preparation and exact adapter state/dtypes, not use an unverified inference-only load shortcut. PEFT source/activation/device verification is a required future preflight because it could not be completed against a local installation. No byte-identical real-model output claim is made.

## Output lengths: separate populations

Every statistic in the right column is **PARTIAL_PREFIX_ONLY (42/60)**; it is not a full checkpoint metric or selection result.

| Statistic | Step 60, all 60 | Step 120 — PARTIAL_PREFIX_ONLY |
|---|---:|---:|
| Min / median / mean tokens | 10 / 10 / 29.7833 | 10 / 161.5 / 141.5476 |
| p90 / p95 / p99 | 143.2 / 183.1 / 192.51 | 197 / 198.9 / 201.36 |
| Maximum | 199 | 203 |
| EOS before 288 cap | 60/60, 100% | 42/42, 100% |
| Cap contact | 0/60 | 0/42 |
| Contract-valid | 60/60 | 42/42 |
| Semantically complete / accepted, observed rows only | 12/60 | 26/42 |
| Refusals | 49 | 5 |
| Refusal median / mean tokens | 10 / 10 | 10 / 10 |
| Non-refusal count | 11 | 37 |
| Non-refusal median / mean tokens | 145 / 117.9091 | 164 / 159.3243 |
| Trailing prose / second JSON / code fences / commentary before / commentary after | All 0 | All 0 |
| Outputs with duplicate atoms | 0/60 | 0/42 |

Quantiles use linear interpolation at `(n-1)*q`. Token denominators use preserved generated IDs, including EOS; these are not re-tokenized raw strings. Prose detection describes boundaries without repairing outputs. Duplicate detection counts exact per-span claims/gaps/uncertainty/refs and additional equality after canonical JSON-object serialization of typed atoms. No fuzzy matching or cross-span conflation is used. Each of the four atom categories has **zero exact and zero additional canonical duplicates**, hence a 0% duplicate-output rate in both saved populations.

### Accepted-output token cost

Only contract-valid, accepted outputs enter `accepted_output_token_cost`.

| Population | n | Median | Mean | p95 | Max |
|---|---:|---:|---:|---:|---:|
| Step 60 accepted, including correct refusal/empty controls | 12 | 27 | 68.8333 | 192.95 | 199 |
| Step 60 accepted with nonempty required content | 4 | 167 | 169.5 | 197.35 | 199 |
| Step 120 accepted — **PARTIAL_PREFIX_ONLY** | 26 | 161.5 | 144.9615 | 199 | 203 |
| Step 120 accepted with nonempty content — **PARTIAL_PREFIX_ONLY** | 22 | 169 | 167.9545 | 199 | 203 |

The step-60 tail estimates have very small samples and are descriptive interpolations, not reliable population tail estimates. Short failed refusals do not enter accepted-output cost. Correct refusal/empty controls are reported separately from nonempty semantic successes so their short length cannot hide omission failures.

### Correct semantic atoms per generated token

For each step-60 output, correct atoms are the exact frozen true-positive `(span,value)` sets for claims, gaps, uncertainty and evidence. Duplicates cannot add true positives. Refusal/status correctness is not invented as a content atom. The diagnostic does not alter acceptance: a concise incomplete output still fails.

| Step-60 per-example diagnostic | Mean | Median | p10 | p90 |
|---|---:|---:|---:|---:|
| All correct atoms / output token | .00550855 | 0 | 0 | .03544208 |
| Correct claims / token | .00201390 | 0 | 0 | .01064097 |
| Correct typed gaps / token | .00101063 | 0 | 0 | .00054645 |
| Correct uncertainty / token | .00047012 | 0 | 0 | 0 |
| Correct evidence refs / token | .00201390 | 0 | 0 | .01064097 |

The four accepted nonempty step-60 outputs average .04825379 correct atoms/token (median .05133343). The all-output zero median reflects content omissions/refusals, not high efficiency. Full per-row diagnostics are retained in `audit_results.json`. Prefix diagnostics are explicitly scoped and do not call the full-checkpoint aggregator or selector.

## Same-ID length drift — PARTIAL_PREFIX_ONLY

Paired population: exactly the 42 IDs saved at both checkpoints, in frozen DEV order.

- Mean length: **37.4524 → 141.5476**; median: **10 → 161.5**.
- Per-ID token difference: mean **+104.0952**, median **+147**, range **−40 to +193**.
- Ratio of total tokens: **3.77940x**. Median per-ID ratio: **15.7x**; these are different estimands because many denominators are ten-token refusals.
- Transitions: **28 refusal→non-refusal**, **9 non-refusal→non-refusal**, **5 refusal→refusal**, **0 non-refusal→refusal**.
- Net extra tokens: **4,372**. Refusal→non-refusal accounts for **4,366 (99.8628%)**; the nine persistent non-refusals add only **6** total tokens; persistent refusals add none.
- Parsed atom totals change: claims **20→58**, gaps **13→71**, uncertainty **5→22**, refs **20→58**. These are generated atom counts, not an assertion that every atom is correct.
- All paired outputs end at EOS before the cap. No paired prose or duplicate drift is observed.

The main length increase is movement from short refusals into substantive structured outputs with more gap and uncertainty arrays. No evidence supports calling it verbose/repetitive deterioration. Some prefix outputs still fail semantics; the 26 observed accepted outputs cannot establish a complete checkpoint result. The unseen 18 outputs remain unassessed.

## Generation cap and future scope

There is no observed cap contact. Among successful outputs, step-60 max is 199 and prefix max is 203; prefix accepted p95/p99 are 199/202. These finite observations do **not** prove a smaller cap safe for all 60 IDs or future data. The 288 cap remains frozen. Lowering it would be a separate experiment-design decision, not a runtime optimization.

The new runtime release is described in [EVALUATION_RUNTIME_V2_IMPLEMENTATION.md](EVALUATION_RUNTIME_V2_IMPLEMENTATION.md). It preserves exact base/adapter/prompts/token IDs/settings and introduces no batching or merge. A future evaluation-only proposal must regenerate all 60 outputs from item 1 after a fixed control/cache/speed gate. Historical 42 + new 18 stitching is forbidden; no retraining is proposed.

**EVALUATION_RUNTIME_V2_READY** means locally reviewed, prospectively frozen mechanics and a separately authorizable proposal only. It is not a GPU benchmark or authorization. The local Torch import aborts with an Anaconda duplicate-OpenMP error even in isolated trials; no unsafe override was used. Lifecycle tests therefore use declared stand-ins, alongside actual source-branch, tracing, filesystem/network-denial and separate-process effect proofs. Future Linux/CUDA preflight remains mandatory.

Auditor was neither trained, evaluated nor redesigned. Protected labels/evaluator were never opened; access-denial tests intercepted attempts before reads. Protected receipts remain absent/unconsumed. No cloud, real model generation, training, weight mutation, paid API, other fold, full pipeline, multi-round or push occurred.
