# Instrumented ordinary final cloud run preparation

Status: **ORDINARY_FINAL_CLOUD_RUN_READY_FOR_AUTHORIZATION**.
Preparation only. No instance provisioned, paid execution, model forward, protected-data access or multi-round execution occurred. Nothing was pushed. A new operator authorization is required; all prior authorizations remain consumed and inapplicable.

## 1. Exact execution identity

Ordinary runtime source: `2f0d0f706fd0b68f757f664cb19d1956e69c27a1` (the completed pairing integration).
The preparation/support tools are committed with this report, separately hash-bound in the manifest. No ordinary runtime source, routing rule, model weight, training/HPO setting or dataset was changed. The archive preserves that source with LF-normalized text, the explicitly selected input and the frozen inference artifacts. It contains 156 files; each has a SHA-256 in `ordinary_final_cloud_run/execution_manifest.json`.

- Execution manifest SHA-256: `dcc3aa913b2e59ca2831bc92009b9f888ca0a23e617f4a8d02acb0761876f223`
- Seal SHA-256: `93d2c5b2fe371f19143abe536569fe7bf15bcf9307b3136826b6440e028a4916`
- Project archive SHA-256: `4867e1db33e656117844028d647744a6316f2a6b8154949cde9087a1f08c138a`

The seal says `PREPARED_NOT_AUTHORIZED`; it is not a launch permit. The generated archive stays local and ignored (130,873,143 bytes). The small manifest, seal, tests and report are committed. Model and wheel files stay in their existing local caches. `tools/prepare_ordinary_final_run.py` reproduces the archive/manifest using the immutable runtime source and separately bound support code; resealing invalidates any previous authorization.

## 2. Selected workload

The established historical ordinary reference corpus is `benchmark/corpora/clinical_reference`. The operator explicitly selected the existing **report_optimized** topology for this first final-model run. Dense activation is retained; this is not a smaller corpus or a new routing policy.

| Role | File | SHA-256 (transferred LF bytes) |
|---|---|---|
| Review target | `context/result_sheet.md` | `d0f332c85d4a1ef419adfa7b18355f28ff129fffeefaeecc8bf2a4c9a4b368a2` |
| Grounding | `context/analyte_reference_ranges.md` | `1a002bbdb62c96739a6d1796b8273b268433feb579f55372be4dd970bd49e19b` |
| Convention | `conventions/lab_conventions.md` | `c1ad7b5f132acd9b62a44accb273338967955c19e13c7731132274444c1fc985` |

Two source documents, one operational review target, one convention document. An explicit `_review_targets.json` selects the target/grounding roles, with no prior documents. It is also hash-bound. All config files, including constitution, agent registry/contracts, review scope and vocabulary, are bound individually. No answer key was read or included. Historical base-run timings are context only, not measurements of this tuned optimized run.

## 3. Final model set

| Component | Exact identity |
|---|---|
| Producer168 | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision `bdd404162d94997f390efbfa660eb3f21cbbc81d` |
| Producer adapter | `8354d6545272399ea6771f1a6b560309e882fd7348f5c2be9cbd1bab01160703` |
| Producer config | `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507` |
| Auditor896 | `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb` |
| Auditor adapter | `0ec8212f5288e5960f1e816d93c9c7e1206eed7c380b45cf355ae0825ecc1b5e` |
| Auditor config | `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6` |
| Head | `6a2fcf89d3e843d5364443c20add30f0542e9dfbf00ff3b0e4d78ede397fdc3a` |
| Mean | `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5` |
| Std | `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a` |

All local artifact/base file hashes were verified, not inferred from names. The Auditor checkpoint has a Llama architecture under its preserved public Phi model ID, hidden size 3072. Its canonical NF4/BF16, eager-attention, FP32 head/statistics and immutable base-state checks remain unchanged. Head/normalization are inference-only saved statistics; no fit or training is performed by the new support code.

The actual full path also needs the **unadapted generative Auditor base** for VERIFIER and other existing local_auditor roles. Auditor896 remains advisory and cannot generate rich findings. BGE-M3 (`5617a9f61b028005a4858fdac845db406aefb181`) serves retrieval on CPU with its already-preserved safetensors file. Those files are independently hash-bound, too. No old step120, HPO Trial11, checkpoint448 or HPO normalization is transferred.

**Known limitation:** external macro F1 approximately 0.8010, historical macro F1 approximately 0.4576, historical OMISSION recall **1/12**. The historical quality gates did not pass. No improvement, latency target, zero-truncation result or ordinary-pipeline quality equivalence is claimed by this preparation.

## 4. Single-instance selection and live facts

Read-only Lambda API observation: **2026-09-17 20:05:10 UTC**, saved in `ordinary_final_cloud_run/provider_inventory.json`. Inventory was empty. A10 capacity was available in us-east-1 and us-west-1. Select exactly one `gpu_1x_a10` in **us-east-1**, at **$1.29/hour maximum**.

| Candidate | GPU VRAM | vCPU / RAM / storage (account API) | Rate/hour | Capacity at observation | Decision |
|---|---:|---|---:|---|---|
| RTX 6000 | 24 GB | 14 / 46 GiB / 512 GiB | $0.69 | None | Unavailable; also not the canonical BF16 Ampere path |
| A6000 | 48 GB | 14 / 100 GiB / 200 GiB | $1.09 | None | Unavailable |
| A10 | 24 GB | 30 / 200 GiB / 1400 GiB | $1.29 | us-east-1, us-west-1 | Selected |
| A100 SXM4 | 40 GB | 30 / 200 GiB / 512 GiB | $1.99 | us-east-1, us-west-2 | More capacity than justified for this first bounded corpus |

GH200 uses arm64 and fails the pinned x86_64 runtime requirement; H100/B200 do not justify their higher rate for this preparation. No capacity reservation or launch was made. Selected image: `gpu-base-24-04`, version `24.4.4-2141`, ID `9211995d-2377-4ea8-94d2-18eea01ec3f6`, us-east-1. Verify Python 3.12.3, driver/CUDA compatibility and BF16 before workload execution; image labels alone do not prove runtime parity.

Public [Lambda pricing](https://lambda.ai/pricing) and [instance specifications](https://docs.lambda.ai/public-cloud/on-demand/) also list A10 at $1.29/hour and 24 GB. Their advertised RAM/storage differ from this account's API response; use the saved API values (200 GiB/1400 GiB) for this manifest and reverify live before launch. Availability/pricing can change; there is no automatic instance substitution.

## 5. CPU, RAM, VRAM and storage envelope

`resource_identity.json` derives model-state bytes directly from safetensors headers and the exact configs, without loading a model:

| Resident component | Stored tensor GiB | Extra FP32 cast GiB | State plus saved FP32 adapter GiB |
|---|---:|---:|---:|
| Producer168 | 5.1661 | 2.0309 | about 7.2723 |
| Auditor896 | 2.1086 | 0.3673 | about 2.5317, plus negligible head/statistics |

These are accounting estimates of model state, not exact allocator peaks: quantization metadata, tensor sharing, allocator rounding, transient dequantization, CUDA workspaces and attention/generation buffers differ. NF4 bytes do not mean all tensors stay 4-bit: k-bit preparation casts nonquantized tensors to FP32. This is why the older 5.5 GB Producer figure alone is insufficient.

Producer BF16 KV cache: 57,344 bytes per token (0.4375 GiB at 8192 tokens); generative Auditor: 393,216 bytes per token (3 GiB at 8192). Auditor896 uses no KV cache. Batch-one eager attention has a single BF16 score tensor of `heads * sequence_length? * 2` bytes: Qwen 0.875/3.5/14 GiB at 4096/8192/16384 tokens; Auditor 1/4/16 GiB. FP32 softmax and intermediate tensors add memory. **A10 is not a guarantee for arbitrary maximum-context prompts.** No total peak can be proved from checkpoint sizes before generated downstream context exists.

A10 is technically reasonable for this small, fixed workload with one resident and bounded compact extraction (up to four 1200-character spans, 1536 output-token partition budget). It has substantial room above the largest model state; no evidence requires concurrent models or a larger card. Short prompts should fit; unusually long eager-prefill inputs can still OOM. An OOM is a recorded execution failure, not permission to shrink the workload, change attention/quantization, rent a second instance or retry. Full-run peak VRAM and latency remain measurements for the authorized run.

BGE CPU state is approximately 2.12 GiB plus embedding/runtime buffers. Plan for 32 GiB host working memory and at least 40 GiB free as an operational allowance, **not a measured peak or hard mathematical bound**; the selected 200 GiB comfortably exceeds it. There is no full-precision 7B download/staging step. Host CPU work includes retrieval, parsing, governance, rendering and the ordinary derived ontology machinery. No persistent local operator/durable state is imported; frozen Producer/Auditor weights are never trained or rewritten.

Exact payloads: model snapshots **10,123,020,635 bytes**; wheels **3,026,822,853 bytes**; project archive **130,873,143 bytes**. Expanded wheels total about **5.305 GiB**. Allow at least 30 GiB free storage, preferably 40 GiB, for snapshots, wheels, environment, extracted project and evidence. Provisioned 1400 GiB is ample. Do not create paid persistent volumes or object storage. Cache size here excludes redundant pickle/ONNX/BGE auxiliary weights, which are not needed or transferred.

## 6. Actual residency path

`pipeline` -> existing report_optimized semantic waves -> `execution_scheduler.Worker` -> `AgentWrapper`:

1. One CUDA lane, `cuda:0`, `resident_limit=1`; one thread owns its resident cache.
2. local_producer calls load/reuse final Producer168 through `final_models.resident`.
3. Ordinary VERIFIER preparation classifies each explicitly owned pair through final Auditor896. Producer is evicted before that load.
4. After advisory context is ready, the existing generative Auditor loader evicts the classifier and emits the unchanged rich VERIFIER contract.
5. Other eligible roles retain their existing Producer/generative Auditor selection. Future waves can reload the appropriate model, with cold/warm evidence.

Eviction deletes the cache reference, collects Python cycles and empties unused CUDA allocator blocks. Worker cleanup drains work and releases residency on its owner thread. There is no semantic-call overlap on the single lane and no concurrent access to a shared Transformers model. Graph-level waves remain observable; a wave does not imply physical overlap. CPU embedding has a separate cache. No requirement to keep both final models resident simultaneously was found. Real allocator release/residency timing remains observable rather than claimed from the mocks.

## 7. Runtime and exact flags

An isolated 92-wheel Linux CPython 3.12 environment is prepared. `runtime.candidate.lock` is the reviewed final-run lock despite its descriptive filename; `install.lock` binds the actual wheels by SHA-256. Offline validation covers Python/platform tags, exact versions and transitive dependency closure.

The old full-run lock conflicts with final admission. Only this isolated run lock substitutes the frozen pins: Transformers 4.51.3, PEFT 0.15.2, tokenizers 0.21.1, safetensors 0.5.3, huggingface-hub 0.30.2 and Jinja2 3.1.4. Torch remains 2.5.1+cu121, NumPy 2.0.2, bitsandbytes 0.48.2 and accelerate 1.10.1. Root requirements and historical locks are unchanged. Do not install root requirements afterward: they would replace the admitted Transformers version.

Installed importable package code, native libraries and package data are checked against **23,672 wheel-member hashes** before pipeline import. Generated pip RECORD/entrypoint scripts and wheel `.data` relocations are outside that check. Python/platform/CUDA/BF16, deterministic algorithms, TF32-off and CUBLAS workspace admission are retained. Actual GPU driver/build must be recorded remotely; no local evidence claims it already matched.

Manifest argv:

```text
--backend-profile local --activation-profile dense --review-mode paired
--task review --mode standalone --non-interactive --skip-confirmation
--sensitivity-layer-inactive-override --no-redaction-override
--execution-topology report_optimized --topology-config topology.json
--agent-briefs enabled --input-language auto --output-language en
```

The two sensitivity/redaction overrides are the existing synthetic reference-workload flags, not new exemptions. Conditional activation, evidence requirements, routing, rich findings and refusal stay in ordinary source. No multi-round flag or manifest exists in the input. Dormant multi-round Python/config definitions remain because ordinary source imports them; **no multi-round data or execution is included**.

The entry point clears inherited SHIMMER/HF/Transformers flags and credential variables, then applies only the sealed environment: final/local mode, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, offline HF/Transformers, no implicit hub credentials/telemetry, `PYTHONNOUSERSITE=1`, no bytecode writes and tokenizer parallelism off. HF paths resolve only to the fresh sealed cache. Outbound model/provider/search connections are denied during the run. The baseline local/offline review policy is preserved; no paid API is used.

## 8. Telemetry and summary coverage

| Area | Raw evidence and derivation |
|---|---|
| Pipeline | `logs/model_telemetry.jsonl` pipeline boundaries, per-phase scheduler events, semantic waves, DAG dependency/lane edges, concurrency and interval unions |
| Scheduler | `audit/execution_topology.jsonl`: ready dependency waits, assigned scheduler/resource waits, idle intervals, task start/end, consumer barriers |
| Producer | Model-call identity, service, generation interval, available tokens/throughput, cap/EOS/truncation, contract/empty/refusal, emitted counts and latest retention snapshots |
| Auditor896 | `auditor_pair`, unavailable/coverage events: eligible items, constructed pairs, attempted calls versus actual forwards, failures, relation distribution, classifier service and Producer handoff |
| VERIFIER | Separate backend call and pair join events; rich finding counts, empty/refused, explicit joins/unjoined and structurally comparable agreement/disagreement; classifier-to-VERIFIER handoff |
| Resources | Two-second psutil/nvidia-smi samples: GPU use/VRAM/power/device, Torch allocated/reserved when initialized, process/system CPU/RAM/swap; scheduler model load/eviction/residency |
| Cost | Verified rate and launch-to-confirmed-termination interval; explicit zero model/API cost; infrastructure and API estimates separate and combined; never an invoice |

`tools/ordinary_final_summary.py` supplements the existing deterministic summarizer with per-agent token/service/count/retention totals and distinct dependency/resource wait sums. Wait sums are task accounting, not wall-clock. Critical path uses actual task/lane dependencies and elapsed intervals, not summed agent durations. Report overlap/zero overlap honestly. The DAG covers semantic tasks, not every embedding/CPU operation; isolated deterministic nonmodel CPU time and unsupported TTFT stay null. Semantic completeness is not inferred from EOS, and sampled peaks do not claim continuous or sub-second measurement.

Recompute after collection and again after writing the confirmed infrastructure interval:

```text
python tools/ordinary_final_summary.py <collected-run-directory> --scripts scripts
```

This produces `audit/model_telemetry_summary.json` plus `audit/ordinary_final_summary.json`, leaving raw evidence unchanged. Infrastructure records use `event=infrastructure_cost`, provider, instance_type, hourly_rate, active_start_epoch and active_end_epoch. Cost equals seconds * hourly rate / 3600. Local model cost receipts supply zero API cost; if missing, record an explicit `api_cost` zero only after confirming all dispatches were local. Unknown costs remain unknown.

## 9. Integrity and completion-first interpretation

Before use: exact source/config/artifact/cache/wheel/runtime checks; no fallback checkpoint or base classifier. Final numerical/state/token/shape/finite checks remain intact. The advisory bridge preserves first numerical failure evidence and refuses that classifier; the run assessor cannot report an integrity pass when any pair failed. Existing VERIFIER continuation/refusal behavior is unchanged. Missing explicit ownership is an unavailable pair, not a fabricated finding or new refusal.

RunCompletion must report an actual completed end-of-work return. Ordinary required contract/governance/evidence gates stay active. Unrecovered contract/transport failures refuse integrity. The existing bounded PROCESSOR partition retry is retained; attempted failures remain in telemetry, while its terminal merged completeness controls whether recovery succeeded. No full-run automatic retry is permitted. Refusal, disagreement, unavailable ownership, slow service and cost/quality target misses are not new semantic rejection rules.

Targets of 120 seconds, $0.10, zero truncation and high quality are measurements to report, not tuning triggers. A completed run missing those targets preserves evidence and identifies bottlenecks. Actual incomplete required output remains incomplete under the existing contracts. No further HPO/optimization/benchmark/roadmap stage starts automatically.

## 10. Deterministic preparation validation

- Existing final integration gate: **104 checks PASS**, ordinary activation suite PASS, seven existing neutralize/fail/restore/pass proofs PASS. Re-run for this preparation with no model/provider imports, no full pipeline and no multi-round.
- New preparation suite: **14 checks PASS**: actual parser flags, exact tree/hash/seal rejection, no reused authorization, multi-round/protected-data flags, numerical/contract/transport failure assessment, preserved partition recovery, cost/reserves, named-instance watchdog, installed runtime byte admission, final-mode environment admission, hardware admission and summary unknown/retention behavior.
- Two new neutralize/fail/restore/pass proofs: exact-tree admission and manifest-bound authorization.
- The actual 156-file archive was extracted to a temporary local fixture and verified against its manifest. Exact input inventory contains only the three selected corpus files and role manifest; no answer key, other corpus, tuning dataset or durable state is available to that project.
- 92 local wheel hashes and platform/dependency closure passed. Base/model artifacts were read only for configs, safetensors headers and SHA-256.

Evidence: `ordinary_final_cloud_run/preparation_validation.json`, `validation.json`, `preparation_tests.log`, `no_generation_tests.log`, `resource_identity.json`, `wheel_manifest.json`, `transfer_plan.json`. These are deterministic preparation results, not GPU allocation/generation or full Linux pipeline execution results. No broad gate containing real-model checks was run.

## 11. Budgets

Propose **$5 soft / $7 hard**, all-in instance time, including provisioning/setup, transfers, cold loads, execution, collection and teardown. At $1.29/hour, $5 is 13,953.49 seconds (3.88 hours); $7 is 19,534.88 seconds (5.43 hours). This is a maximum authorization request, not a forecast. There is no latency measurement for this final optimized run from which to promise a smaller completion budget.

The operator-side watchdog cannot provision and terminates only the authorized instance. It signals workload-stop at hard-limit minus 900 seconds and requests provider termination at hard-limit minus 180 seconds. The remote entry also has a hard workload-stop timer at the 900-second reserve, preserving already-flushed raw evidence and refusing completion. The controller must collect earlier on projected overruns or soft-budget exhaustion without a credible completion margin. Stop/terminate sooner if the hard ceiling is threatened. Provider control-plane delays cannot be mathematically guaranteed away; retain the three-minute margin and verify independent inventory.

## 12. Exact transfer allowlist

Before execution, after authorization only:

1. `project.tar.gz` with the sealed runtime/config, three corpus files plus role manifest, and the seven frozen adapter/config/head/statistic files listed above.
2. Only the model snapshot members listed in the execution manifest, totaling 10.123 GB decimal; create exact `refs/main` pointers. This includes Producer base, shared Auditor base and CPU BGE safetensors/tokenizers/config.
3. The 92 hash-bound wheels (3.027 GB decimal), `install.lock`, `topology.json`, `execution_manifest.json`, `seal.json`, `ordinary_final_run.py`, `ordinary_final_summary.py`, `cloud_run_observer.py`.
4. After launch, a new operator authorization record naming this manifest/seal/source, one instance ID, actual rate, conservative active-start epoch and approved budget, plus a current watchdog receipt. Neither file contains credentials.

No API key/private SSH key, local credentials, protected final test, TRAIN/DEV/HOLDOUT, HPO data, benchmark answer keys, other corpora, multi-round data, Git history, old authorizations or local durable state transfers. No evaluation upload stage is needed. Generated outputs/durable state remain isolated to the disposable project and are collected as this run's evidence.

## 13. Exact commands and prelaunch sequence

No command in this section was executed against a cloud instance.

Reverify live inventory empty, exact A10 capacity/rate/image and all manifest/controller hashes immediately before provisioning. After explicit authorization, create one temporary SSH identity, register only its public key, record launch intent before requesting exactly one instance (no launch retry). Record the earliest launch-request epoch for conservative budgeting. Start the independent watchdog hidden on the operator machine, using the new authorization record:

```text
python tools/ordinary_final_watchdog.py --bundle docs/fix/ordinary_final_cloud_run --credential-file C:/Users/secki/local/api_keys/config.py --arm
```

The credential is loaded in memory by the existing provider adapter and never printed/transferred. Prepare `/home/ubuntu/shimmer-ordinary-final` with a fresh `project`, `hf_cache`, `wheels` and `venv`; reject leftover output/claims or extra project/cache files. Extract only the verified archive after SHA-256 verification. Verify Python exactly 3.12.3 and create the environment:

```text
/usr/bin/python3.12 -m venv /home/ubuntu/shimmer-ordinary-final/venv
/home/ubuntu/shimmer-ordinary-final/venv/bin/python -m pip install --no-index --find-links /home/ubuntu/shimmer-ordinary-final/wheels --require-hashes -r /home/ubuntu/shimmer-ordinary-final/install.lock
```

Verify installed dependency closure and GPU/CPU/RAM/disk identity; no model warmup or extra inference probe. The entry point additionally refuses anything except one A10 with at least 20 GiB free VRAM, 30 logical CPUs, 190 GiB total/40 GiB available RAM and 30 GiB free disk, recording the observed hardware values. Copy the watchdog's latest `WATCHDOG_ARMED.json` immediately before the remote command (it must be less than 30 seconds old and bind the instance and manifest). The exact single-run command is:

```text
/home/ubuntu/shimmer-ordinary-final/venv/bin/python -B /home/ubuntu/shimmer-ordinary-final/ordinary_final_run.py --bundle /home/ubuntu/shimmer-ordinary-final --execute
```

Omitting `--execute` verifies only the sealed project. Execution requires a new permit and an exclusive `RUN_CLAIMED` file; re-entry refuses. Pipe stdout/stderr into the evidence collection scope without printing environment/config secrets. The pipeline receives the manifest argv plus the absolute output path and topology path. No second invocation, warmup, parameter sweep or automatic retry is authorized by this preparation.

## 14. Collection and teardown

Collect available run logs/audit/outputs, first-failure admission evidence, project-local generated ontology/durable outputs, runtime/GPU metadata, setup logs, workload result and all controller/cost records. Include failed/stopped runs. Generate a remote SHA-256 inventory, download, and independently verify every collected file. Do not wait for expensive optional analysis if budget is threatened. Partial evidence must be marked partial; a killed process is never promoted to completed.

Request termination regardless of workload result by creating the local `TERMINATE_REQUEST` for the independent watchdog or calling the existing termination-only provider client for the named instance. Verify terminated status, then use a separate provider inventory query to confirm zero instances. No persistent storage is provisioned. Remove the temporary provider SSH registration and both local private/public SSH files; do not remove the operator's preexisting API credential. Verify no resources or temporary credential registration remain. Final infrastructure cost runs through confirmed termination, not merely workload end. Recompute summaries with that cost record and record any unverified resource/billing fact explicitly. Budget safety takes priority over collecting a complete artifact set.

## 15. Remaining uncertainty and authorization text

There is no demonstrated source/artifact/contract preparation blocker. The exact Linux process, live driver, end-to-end peak memory, tuned full-run latency and semantic quality remain unmeasured until authorized execution. The A10 selection is a justified first-run envelope, not proof of arbitrary-context fit. A changed provider/runtime/artifact fact blocks launch rather than triggering substitution.

Required operator text (bind it to the preparation commit and the manifest/seal hashes above):

> I authorize exactly one Lambda gpu_1x_a10 (24 GB) in us-east-1, at the reverified rate of $1.29/hour or lower, for exactly one instrumented ordinary report_optimized clinical_reference run using SHIMMER_MODEL_MODE=final, Producer168 and advisory Auditor896. I approve only the manifest-listed source/config, model/adapter/head/statistic, wheel and synthetic workload transfers, with a $5 soft budget and $7 hard ceiling including setup, collection and teardown. Multi-round and protected data are excluded. No second instance, automatic full-run retry, tuning, HPO, model replacement, workload substitution or subsequent roadmap work is authorized. Preserve evidence, terminate regardless of outcome, independently confirm empty inventory, remove temporary SSH credentials, commit results locally and do not push.

Stop here for the operator. This report and its seal do not themselves authorize provisioning.
