# Auditor final-training failure: independent root-cause analysis

## Executive finding

**ROOT_CAUSE_UNRESOLVED. RETRY_NOT_YET_JUSTIFIED. REMOTE_DIAGNOSTIC_REQUIRED** for further causal discrimination; no remote resource was launched.

The strongest new finding is a precise change in the saved output sequence: **rows 1–10 are bitwise identical to the historical TRAIN cache; rows 11–31 each differ in all 3,072 coordinates.** The original aggregate maximum concealed this boundary. Row 11 has 727 tokens, fewer than the previous maximum of 738. Row 24 has the same length (735) as previously exact rows 5 and 6, yet differs. Thus neither a uniform output conversion from startup nor a simple new-maximum-length threshold explains the observations.

This establishes an output divergence boundary, not a proven internal state transition: different rows were supplied at each step. The evidence cannot distinguish a history-dependent change from an input-dependent kernel path. It also cannot prove that finite drift and the subsequent guard failure share one cause. Calling this a transient GPU glitch, an allocator bug, or a fixed issue would exceed the evidence.

The later diagnostic establishes successful mathematical extraction under its own execution conditions. It does not replay the failed process lifecycle exactly. Stage C creates a fresh model in an already-used Python/CUDA process; the helper changes input inference-tensor status, output-storage lifetime, head lifetime, and instrumentation/synchronization. These are verified differences, not causal fixes.

No production code, training settings, frozen HPO parameters, or data were changed. New work consists only of this analysis, a saved-evidence auditor, a synthetic CPU probe, and their JSON results. No training, HPO, model inference on real data, DEV/HOLDOUT/protected-data access, or cloud operation was performed in this investigation.

## Evidence and chronology

The four requested reports were read completely before changes. Their claims were checked against source, manifests, saved TRAIN arrays/receipts, package-install logs, and analyzer logic. The new auditor does not execute the old analyzers: some successful-run branches open evaluation data. Archive inventories and Python members were inspected without extracting evaluation contents.

| Execution | Identity | Relevant result |
|---|---|---|
| Historical current-runtime extraction | `ceabb0afda9c87812e2461fd70c505fb6f9e4b9a` | 1,792 fresh TRAIN vectors; immutable historical comparison cache |
| HPO | `ea2b72373a384e29a6344c762b8b7d12ef450741` | Reuses that cache, admits live TRAIN compatibility with tolerances; not another fresh cache-generation run |
| Failed final attempt | `b4f7e8247391e2278a7b7a1ba84f6b5915c56ced`; results `b00e00a` | 31 saved finite vectors; attempted row 32 hits combined shape/finite guard; zero optimizer updates |
| Local bounded investigation | results/source bindings `459d694` | Rows 30–33 finite and locally repeatable; different Windows/GPU/native runtime |
| Remote diagnostic | execution `f8dbcd12f9e06ff115081caac9565744192bdaf7`; results `c2e1c46` | 38 forwards, all bitwise historical; Stage C follows six earlier forwards in the same process |
| This investigation | based on `c2e1c46` | Independent source/vector audit and synthetic CPU lifecycle tests; no real-model forward |

Recomputed results are in [audit.json](auditor_failure_forensics/audit.json), [runtime_inventory.json](auditor_failure_forensics/runtime_inventory.json), and [cpu_probe.json](auditor_failure_forensics/cpu_probe.json).

### What the failed vectors actually show

All 31 saved-vector hashes match their original feature receipts. Each corresponding historical vector also matches its receipt; the complete historical NPY matches SHA-256 `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287`. Row IDs, indexes, receipt token hashes, and recomputed TRAIN-only payload token hashes agree. Unwritten rows of the failed 1,792-row memmap were not treated as observations.

| Rows | Comparison with historical |
|---|---|
| 1–10 | Exact, all coordinates |
| 11 | First differing row, document-012, 727 tokens; max absolute difference 0.13879960775375366; RMS 0.0325396137426542 |
| 11–31 | All 3,072 coordinates differ on every row; RMS approximately 0.0264–0.0369; no monotonic growth established |
| 26 | Largest maximum absolute difference: 0.16882681846618652 |
| 32 | Document-038, 781 tokens; offending shape/values absent; cannot assert NaN versus Inf versus wrong shape |

The traceback reaches the original `require` after conversion to a NumPy vector. It is not a recorded Python CUDA OOM, indexing exception, or backward error. The expected architecture makes nonfinite values more plausible than a dimension change, but the combined guard cannot prove which condition failed.

All 38 later A10 saved vectors independently compare bitwise equal to the corresponding historical vectors. The failed local-overlap rows do not match the Windows outputs either: failed-versus-local maxima are 0.18599724769592285 and 0.21983540058135986 for rows 30 and 31. Their error-direction cosines relative to historical are only 0.2505 and 0.1399. Similar error magnitudes do not identify a shared mechanism. Repeatability on Windows establishes within-runtime repeatability, not equivalence to cloud or correctness of the failed run.

## Exact execution-path comparison

The comparison below follows startup through persistence. Source references are commit-bound by the new audit, rather than assuming current working-tree code was executed historically.

### Startup, launch, imports, and process identity

All three cloud launchers create a project virtual environment and invoke its absolute Python executable with `-B -u`, with a project-specific working directory. The historical path is `/home/ubuntu/shimmer-auditor-classifier-current`, failed final is `/home/ubuntu/shimmer-auditor-final`, and diagnostic is `/home/ubuntu/shimmer-auditor-feature-diagnostic`. Scripts import sibling project modules through their tools directory. There is no explicit inference-path `sys.path` overlay in these cloud scripts; the local probe deliberately uses an overlay.

The launchers obtain the same explicit environment from `tuning/first_domain_agnostic_v1/experiment.json`: seed 7, CUBLAS workspace `:4096:8`, offline flags, tokenizer parallelism disabled, plus HF telemetry disabled. The historical workload sets its offline environment before importing Torch; failed `runtime()` also sets CUBLAS before importing Torch. The diagnostic calls `preflight()` inside `execute()` before that update, importing Torch and querying CUDA first. Its launcher already supplies CUBLAS, so this is an initialization-order difference, not proof that the setting was missing.

Historical scope loads the old combined records/challenges before extraction, then imports Torch/NumPy/Transformers/PEFT/safetensors, installs a network audit hook, configures deterministic execution, and seeds. This historical fact comes from source inspection; those evaluation records were not opened in this investigation. A separate telemetry subprocess samples the main PID. Budget calculations maintain CPU timing history and write progress/timeline files.

Failed final installs its access boundary, validates TRAIN-only scope and authorization, checks package metadata/platform, sets environment, initializes CUDA, sets deterministic/TF32 flags, and seeds. It subsequently imports PEFT, safetensors, fork/current/stable, HPO helpers, and FinalBackend before loading. Its budget object installs a signal handler and writes progress. These imports do not call the optimizer or fit a head before extraction.

Diagnostic performs preflight and scope twice along its call chain, then installs the data boundary, deterministic settings, and backward/optimizer prohibitions. It records hardware/build metadata, loads comparison arrays, and uses `reset()` to clear references, collect garbage, empty the CUDA allocator cache, reseed, and load. The comparison arrays are used after live extraction for comparison; source inspection shows no historical-vector substitution into the returned result.

### Model construction and pre-forward state

All use the pinned model revision `5c20803aa197416f43fb455e55c85178775320cb`, weight digest `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`, and actual `LlamaForCausalLM` architecture with hidden size 3072. The model name is not an architecture guarantee; the explicit config check is relevant.

The constructor arguments agree: local files only, remote code disabled, device map `{'': 0}`, BF16 requested dtype, eager attention. The bound config specifies NF4, double quantization, UINT8 storage, BF16 quantized compute, attention dropout zero, and LongRoPE with original context 4096. Loading is from the historical acquisition cache path versus a project `base_model` directory; acquisition/asset checks bind the intended bytes.

Each sets `use_cache=False`, then calls `prepare_model_for_kbit_training` with checkpointing enabled and reentrant mode. That preparation freezes parameters and casts non-quantized FP16/BF16 parameters to FP32, with input-gradient/checkpointing setup. Matching prepared-state hashes support matching serialized prepared tensors, not every runtime attribute. [PEFT 0.15.2 implementation](https://raw.githubusercontent.com/huggingface/peft/v0.15.2/src/peft/utils/other.py).

Each loads the canonical adapter as `historical_reference`, `is_trainable=False`, creates an unused FP32 CUDA Linear(3072,4), calls `freeze_slots` (all parameters frozen, model/head eval), verifies adapter tensors/config, and computes the prepared base hash. Historical inventories the adapter before PEFT loading; failed and diagnostic inventory it afterward. The historical and failed unused heads remain local variables alive across extraction; the diagnostic's head is local to `reset()` and is not retained in `holder`, so it is released on return. Its creation reproduces RNG consumption but not allocation lifetime (12,292 FP32 parameters, 49,168 bytes).

The source contains no adapter switch, merge, disable, training-mode activation, selected-dropout installation, normalization, head fitting, or optimizer update between rows 1 and 32. Target-module names and all 448 adapter parameter bindings are checked; the config requires rank 8, alpha 16, dropout .05, no bias/DoRA/RsLoRA/pattern overrides, and the expected target set. Dropout is inactive under eval in the intended path. Checkpointing configuration does not imply that checkpointed backward work occurs during inference.

The initial base digest is `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18`; the adapter-file digest is `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`. Neither digest authenticates the entire running Python object graph. Failed execution does not retain per-forward active/disabled/merged flags, compute state, nonpersistent buffers, or a post-failure full hash.

### Forward call and persistence

| Detail | Historical fresh extraction | Failed final extraction | Later remote diagnostic |
|---|---|---|---|
| Earlier forwards before first prefix row | None in workload source | None in workload source | Stage C follows A/B in same process, then reloads model |
| Input construction | Long CUDA tensor inside inference mode | Same | IDs and explicit all-ones mask constructed outside inference mode |
| Per-row checks | TRAIN, active reference, parameters frozen | Budget then extraction | TRAIN plus optional full state snapshots |
| Context | Inference mode; BF16 CUDA autocast | Same | Same numerical contexts for model call |
| Model call | `get_base_model().model`, IDs, all-ones attention mask, no cache, return dict | Same | Same |
| Token handling | Serialized IDs, no runtime tokenization/padding/truncation | Same | Same bounded serialized IDs |
| Pooling | `last_hidden_state[0,-1]` inside autocast | Same | Full raw tensor retained; shape validated; same slice outside autocast |
| Copy | FP32 CPU NumPy copy | Same | Same |
| Previous output storage | Last-token view retains prior full hidden storage into next forward | Same | Helper locals released when function returns |
| Extra observation | Vector norm/hash and CPU persistence | Vector norm/hash and CPU persistence | Full raw/pooled FP64 CPU summaries, state/RNG snapshots, library-map identity, vector comparisons |
| Persistence | 1,792x3,072 FP32 memmap, flush each row, JSONL receipt | Same size and flush; different receipt/budget bookkeeping | Separate vector NPYs and detailed JSONs, retained comparison dictionaries |

The old loops already synchronize through CPU copies; they are not wholly asynchronous. The diagnostic adds further transfers, reductions, RNG copies, filesystem work, and allocation changes. Moving indexing outside autocast does not itself round or change a view's numeric contents. The synthetic probe confirms identical pooled arithmetic while demonstrating different storage lifetimes and input inference flags. This does not show a use-after-free or uninitialized read.

### HPO is a distinct path

HPO reads historical features and the clean head/normalization, loads reference and candidate adapters, restores the head, selects adapters for 16 paired controls, removes reference, then checks all 1,792 live TRAIN rows. `ReuseAdmission` uses `allclose(rtol=1e-4, atol=2e-4)` for hidden/standardized/logit arrays and prediction checks. Its observer uses eval/no-grad and batch-preserving last-token slicing. It does not establish bitwise raw-cache regeneration across all rows. Its success is relevant compatibility evidence, with different adapter and allocation history; later optimization cannot cause the earlier final-run failure.

### Local bounded path

The saved local probe binds four extraction/helper source hashes to `459d694`; the new audit verifies each against Git bytes. It uses Windows, an explicitly verified conda Torch overlay, CUDA 11.8, RTX 3070 Ti Laptop GPU, bitsandbytes 0.49.2, Accelerate 1.13.0, and NumPy 1.26.4. Cloud used CUDA 12.1/A10, bitsandbytes 0.48.2, Accelerate 1.10.1, and NumPy 2.0.2. The helper shares mathematical extraction with the final code but changes the original inline lifetime. Local deterministic success cannot falsify a cloud-specific native execution problem. No further real-model probe was warranted merely to reproduce this known mismatch.

## Runtime and execution verification: what is demonstrated

The new source audit compares manifest-bound ZIP Python bytes with Git blobs, downloaded files when retained, and Python members present in the evidence archive. It also compares ASTs. All **9 historical, 11 failed-final, and 8 remote-diagnostic** manifest Python files match Git byte-for-byte, not merely semantically. No generated-source discrepancy was found in those sets. Four historical auxiliary files lack standalone downloaded copies; their bundle/Git identities remain checked. See per-file archive coverage in `audit.json` rather than assuming every file was retained everywhere.

HPO has 13 Python members. Twelve are Git-bound; `tools/auditor_optuna_hpo_launch_support.py` is absent from its stated execution commit, although its payload/downloaded bytes are manifest-bound. The launcher builder reads this helper from the working tree. Its inspected role is preflight/acquisition in separate processes; the HPO inference entry point is Git-bound. This is a real provenance exception, not evidence that it caused final-run drift.

No `.pyc` members occur in the inspected bundles or evidence archives. `-B` inhibits bytecode writing, not loading. Neither the old nor later artifact set is a complete capture of site-packages, startup customization, `sys.path`, module `__file__`/`__spec__.origin`, loaded Python code objects, or external temporary files. File hashes and traceback paths strongly support intended source execution, but are not instruction-level attestation. There is no positive evidence of shadowing/stale bytecode; it is unlikely, not categorically disproven.

Install logs report identical native dependency versions across the three relevant cloud runs, including cuBLAS 12.1.3.1, CUDA runtime 12.1.105, cuDNN 9.1.0.70, cuSPARSE 12.1.0.106, nvJitLink 12.9.86, NCCL 2.21.5, and Triton 3.1.0. Thus a casually assumed transitive package-version drift is contradicted by actual logs. Exact loaded shared-object identity is a different claim.

The later diagnostic records driver 580.105.08, Linux 6.8.0-1046-nvidia, glibc 2.39, CUDA 12.1, cuDNN 90100, and selected mapped library hashes. Failed/historical runs lack equivalent loaded-library maps and driver/kernel state at the divergence. The same A10 class/image/pins do not prove identical loaded files, algorithm selection, allocator state, environment inherited outside the explicit whitelist, CUDA stream history, or physical GPU health. Even the later map is a selected-file inventory rather than a trace of which kernel executed which operation.

The base audit covers `state_dict()` entries other than LoRA, including serialized quantization state where supplied by module serialization. It omits nonpersistent buffers and ordinary Python attributes. The adapter check covers named parameter bytes/config, not independently enabled/merged state on every forward. For example, LongRoPE's `inv_freq` is explicitly nonpersistent; changing such a buffer need not change this base hash. Ordinary LongRoPE long-context switching is not a fit here: the short prefix never approaches 4096 tokens. [Transformers 4.51.3 RoPE implementation](https://raw.githubusercontent.com/huggingface/transformers/v4.51.3/src/transformers/modeling_rope_utils.py).

bitsandbytes 0.48.2 stores compute dtype/state as attributes and performs a one-time type choice only when not already set. The pinned config requests BF16 from construction. There is no source-level “switch after ten rows” in that logic; asserting one would be speculation. Its quantization state serialization is stronger evidence than merely hashing packed weights, but cannot capture every runtime flag or future kernel behavior. [bitsandbytes 0.48.2 Linear4bit](https://raw.githubusercontent.com/bitsandbytes-foundation/bitsandbytes/0.48.2/bitsandbytes/nn/modules.py).

The final analyzer independently verifies archive/source/receipt/vector integrity but retains only aggregate prefix drift, concealing its onset. The HPO analyzer's manifest loop conditionally checks files only if present; missing files can therefore escape that loop. The new audit records missing files explicitly. Neither analyzer reconstructs absent failing tensors or old runtime state. The later analyzer's detailed successful receipts establish that later run's state, not the failed run's state.

## Ranked causal hypotheses and falsification

Ranking reflects fit to preserved observations, not a probability estimate. No specific mechanism is strongly supported enough to qualify as established.

| Rank / candidate | Support | Contradiction / attempted falsification | Expected observation and existing-testability | Verdict |
|---|---|---|---|---|
| 1. History/allocation-sensitive native forward behavior | Ten exact rows followed by 21 differing rows; original and diagnostic have demonstrably different lifetimes and warmup | Historical inline path succeeds; no allocator/kernel trace, sanitizer error, or invalid access captured. A shorter row starts drift | Divergence under exact cold original path but parity under diagnostic; possible state-dependent recurrence. Source/CPU can prove lifecycle difference, not CUDA causality | **Plausible**, mechanism untestable from preserved evidence |
| 2. Unrecorded model runtime/buffer change | Initial hashes precede failure and omit nonpersistent buffers/flags; sustained later drift fits a changed state | No application mutation in loop; first ten exact; normal LongRoPE threshold and first-forward compute-type initialization do not fit row 11 | A buffer/flag changes between known-good and bad forwards, or parameter hash differs afterward. Required old snapshots absent | **Plausible**, not established |
| 3. Input-dependent native path or actual loaded-runtime difference | Later/cloud versus Windows show execution environment can matter; exact old library maps absent | All reported native package versions match; first ten exact; differing row 24 shares length with exact rows 5/6. Simple length-only or uniform-version explanation fails | A content/shape/path distinction with same weights, or a differing mapped build/driver; output-only evidence cannot localize it | **Plausible** for unrecorded execution identity/path; simple package-version drift **unlikely** |
| 4. Hardware error or transient corruption | Could affect later state and nonfinite results without source change | No supporting ECC/Xid/driver fault evidence; 21 fully differing vectors precede failure, so a row-32-only glitch cannot explain both observations | Correlated device fault or corrupted state near onset. Relevant old health/kernel logs absent | **Untestable from preserved evidence**; no basis to prefer “transient GPU glitch” |
| 5. Wrong adapter, train/dropout state, merge/disable from startup | Old live flags incompletely logged | Tensor/config checks, explicit eval/freeze, and ten exact outputs strongly contradict a constant wrong state; no row-11 switch in source | Early/repeated divergence or recorded mode change. No failed-run repeat exists; saved later repeats only test later state | **Unlikely**; a later unexpected mutation belongs to rank 2 |
| 6. Different checkpoint, tokens, source math, or persistence mix-up | General potential explanation for drift | Manifest/Git/archive identity; prepared-state/adapter checks; exact IDs/token hashes; each saved row matches contemporaneous hash; later live outputs reproduce historical | Digest/order mismatch, wrong pooling, conversion signature. Direct audit finds none | **Ruled out within recorded byte/hash scope**; runtime execution attestation remains limited |
| 7. Pure output FP16/BF16 conversion or simple long-context threshold | Low-precision systems can differ numerically | Neither final-output FP16 nor round-to-nearest-even BF16 casting reproduces differing vectors; onset at 727 tokens, below earlier max and 4096 threshold | Exact cast signature or threshold crossing. Saved arrays/config directly test this | **Ruled out** for these specific mechanisms, not all internal precision effects |
| 8. Head fitting, optimizer, selected HPO settings, evaluation | None before failure | All lie after extraction; zero updates; no fit/normalization/checkpoint created | A call before row 32 would be required; source and phase receipts exclude it | **Ruled out** |

Shape failure and nonfinite failure remain separate possibilities. The drift and terminal failure may share a cause, but any proposed mechanism must explain both rather than infer the missing row-32 contents from its error string.

## New deterministic/local probes and changes

`tools/forensic_auditor_feature_failure.py` reads selected Python source and saved TRAIN artifacts, checks Git/payload/archive identities, reports coverage gaps, verifies vector receipt/token bindings, locates drift per row, compares all 38 later outputs, tests pure output conversions, and compares local error directions. It records installed native package versions and archive bytecode inventory. It scans staged content without displaying it before every subsequent Git operation. It never imports the old training entry points or opens evaluation records.

`tools/probe_auditor_extraction_lifecycle.py` runs a synthetic CPU model with Torch 2.5.1+cpu, using the real extraction helper. It confirms:

- At second forward entry, prior hidden storage survives in the original inline pattern and is released in the helper pattern.
- Original IDs are inference tensors; helper IDs are ordinary tensors, despite inference mode during both model calls.
- The synthetic pooled vectors remain identical.
- Changing train/dropout state and a nonpersistent buffer leaves `FrozenAudit.hash()` unchanged.

The probe's initial fixture used a dynamically created class holding the tensor as a class attribute, which introduced an artificial reference cycle. That fixture was corrected to a plain namespace before assertions passed; the retained result tests tensor storage lifetime, not that fixture artifact. No CUDA defect is inferred from this CPU test.

Reproduce from repository root with `python tools/forensic_auditor_feature_failure.py` and `.venv/Scripts/python.exe tools/probe_auditor_extraction_lifecycle.py`. The evidence auditor requires retained run archives/bundles/arrays and local Git history; these large artifacts are not duplicated in this commit. No causal production fix or failure regression test was added because no causal mechanism was established. The probe is a test of diagnostic coverage/lifecycle only.

## Root-cause and retry-readiness verdicts

**ROOT_CAUSE_UNRESOLVED.** The audit narrows the observed divergence to after row 10/before persistence of row 11 and eliminates several concrete explanations. It does not narrow the cause to one small proven subsystem: kernel/path behavior, unrecorded runtime state, and device corruption cannot be distinguished. Therefore `ROOT_CAUSE_NARROWED` would overstate causal localization.

**RETRY_NOT_YET_JUSTIFIED for the current final-training path.** A later 38-forward success, plus historical/HPO success, is encouraging evidence of a viable model/runtime. It is not evidence that the original failure is fixed or that finite drift cannot recur. The current final path uses the helper with `record_success=False`; it records startup state and failing summaries, but it does not compare its finite prefix against historical vectors before normalization/head fitting. The failed run already admitted 21 finite divergent rows. Existing later parity checks compare the fresh cache against itself/reference-fork results after head fitting; they are not a historical-prefix admission check.

This readiness judgment is separate from requiring a fully proven root cause. A bounded operational admission could make a future retry reasonable without claiming a fix: retain exact execution/native provenance, admit a live prefix against established historical parity before any fitting, fail closed on unexpected drift, and retain first-divergence/failure state. That would be a safety gate, not a causal repair, and needs explicit design/validation rather than silently changing the frozen workflow here. No such production patch was made.

## Single smallest discriminating remote experiment

**REMOTE_DIAGNOSTIC_REQUIRED** to test the strongest remaining actionable distinction. This is a proposal only; no resource launch or training authorization is implied.

Use one pinned A10 environment and **two fresh, sequential Python processes**, with at most 32 TRAIN forwards each (maximum 64 total, no A/B warmup rows, no training). Both get the same original TRAIN-only scope/asset inputs and pinned runtime. Stop each arm at its first nonfinite/shape failure or first historical mismatch. The matching arm may continue to row 32. The lower bound of 32 is needed to cover the original terminal failure; stopping at row 11 alone cannot test it.

- Arm O preserves the failed startup/import/load order, unused-head lifetime, inline loop, IDs inside inference mode, mask construction, 1,792-row memmap allocation and original per-row persistence. Restrict iteration to rows 1–32 without changing their preceding allocations or adding warmup. Preserve the selected raw output handle only for terminal evidence, without cloning/interposing reductions on successful GPU forwards.
- Arm D differs only in using the current diagnostic extraction helper with successful receipt instrumentation; retain the same surrounding cold startup/head/memmap scope so the tested contrast is extraction lifetime/instrumentation rather than many unrelated loader changes.

Perform vector equality checks on the CPU copy already produced by each original forward, before another forward. Do not add layer hooks, full GPU hashes, allocator snapshots, or raw-tensor scans to successful Arm O forwards. At first divergence/failure, stop and retain the vector/raw tensor, shape/dtype, active/disabled/merged/mode/compute flags, all buffers including nonpersistent ones, RNG and parameter hashes, loaded module origins, library maps, allocator summary, and device fault diagnostics. Capture known explicit environment and package/source provenance outside the hot loop without printing arbitrary environment values. Observe process identity to establish genuinely fresh processes; a model reload or `empty_cache()` is insufficient.

| Outcome | Discrimination |
|---|---|
| O diverges, D matches | Supports extraction lifecycle/instrumentation sensitivity; still not proof which allocation/operator is causal |
| Both diverge | Weakens extraction-helper-only explanation; preserved first bad boundary allows targeted model/runtime investigation |
| O matches, D diverges | Contradicts the helper as a sufficient remedy; investigate its distinct path |
| Both match through 32 | Another nonreproduction; reduces reproducibility concern but leaves original cause unresolved |

No unbounded retries, parameter sweeps, additional instance, or automatic layer replay is part of this experiment. Capturing the first *finite divergence* is essential; waiting only for row-32 nonfiniteness would again lose the earlier boundary. The original process is gone, so even a successful discriminating experiment cannot retroactively prove its exact internal state.

## Remaining unknowns

The original row-32 shape and NaN/Inf counts; the earliest internal bad tensor; whether drift and failure share one mechanism; runtime state before/after row 11; nonpersistent buffer contents; actual mapped old native binaries/driver state; allocator/stream/kernel history; and device-health evidence at the event remain unavailable. They are the reason for the unresolved verdict, not permission to invent a cause.
