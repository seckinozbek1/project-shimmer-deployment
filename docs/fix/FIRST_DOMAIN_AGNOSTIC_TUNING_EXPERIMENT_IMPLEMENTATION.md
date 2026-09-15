# First domain-agnostic tuning experiment: implementation

`FIRST_TUNING_EXPERIMENT_IMPLEMENTATION_READY`

Implementation commit: `1225fc17924e86cd2883730b0447765cc0cc33d5`. Starting release: `a4e369fbfb18f1f547ab207334fe3698627b9d7b` after the clean V3 label freeze `aad0ec046d7f507d522bf094771b56ea16fd94c9`.

This is **local design, implementation and a no-model dry-run**. It is not training authorization, model-quality evidence, independent benchmark evidence, human validation or production acceptance.

## Starting readiness and immutable evidence

`PRODUCER_TUNING_COVERAGE_READY` and `BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_READY` remain the prior curation findings. `FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING`; actual human reviews remain **0**.

No historical curation artifact was changed. V1/V2 evidence, quarantined producer labels, V3 semantics/canonical targets, the auditor candidate pool, semantic-benchmark-v2, semantic-task-v1, historical A/B evidence and governance constraints remain intact. The 27 registered criteria, derived R07 and six catastrophic zero limits retain their exact acceptance-file hash. R06 retains exactly 114 non-TRAIN IDs: 40 DEV, 37 TEST, 37 public-adversarial (`sealed_adversarial` in the stored schema). TRAIN never contributes.

## Frozen datasets and access

All artifacts are under `tuning/first_domain_agnostic_v1/`. `experiment.json` is the top-level plan; each role has `dataset.json`, `experiment.json`, `train.json`, `dev.json` and `token_lengths.json`. `freeze.json` binds executable training source, dataset/config files and required production modules byte-for-byte.

| Role | TRAIN | DEV | Label origin |
|---|---:|---:|---|
| Producer | 32 | 32 | producer-semantic-policy-v3 / producer-target-renderer-v3 |
| Auditor | 46 | 24 | approved auditor-only subset of machine adjudication V2 |
| Combined | 78 | 56 | roles remain separate |

The approved balanced manifest's source-file hashes, exact allowed IDs and selected-row hashes were verified before export. No authored-only, disputed, quarantined, held-out, TEST, public-adversarial, extra-evaluation, regression, sealed/final or human-namespace label enters these files. Duplicate IDs across the four datasets are rejected. Auditor source files originally contain mixed roles; only their exact approved auditor IDs were exported. No new curation occurred.

The gradient loader explicitly rejects DEV/evaluation access and validates each role, split, ID and row hash. DEV enters only the evaluation runner. Input prompts contain the task packet; labels contain only compact semantic JSON. Python-owned provenance, offsets, identity and source reconstruction are not targets. Producer targets are re-rendered with the unchanged V3 renderer and checked for equality with the frozen canonical target. Every target passes the existing production compact contract, including valid refusal outcomes (which are not production semantic acceptance).

## Exact role configurations

| Setting | Producer | Auditor |
|---|---|---|
| Model | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` |
| Revision | `bdd404162d94997f390efbfa660eb3f21cbbc81d` | `5c20803aa197416f43fb455e55c85178775320cb` |
| Actual architecture | Qwen2ForCausalLM / qwen2 | LlamaForCausalLM / llama |
| Tokenizer | Qwen2TokenizerFast | LlamaTokenizerFast |
| Max sequence | 928 | 800 |
| LoRA rank / alpha / dropout | 8 / 16 / 0.05 | 8 / 16 / 0.05 |
| Adapter parameters | 20,185,088 | 14,942,208 |
| Learning rate | 0.0001 | 0.0001 |
| Microbatch / accumulation | 1 / 4 | 1 / 4 |
| Effective batch | 4 | 4; final group per pass is 2 |
| Updates per pass | 8 | 12 |
| Maximum updates | 16 | 24 |
| DEV/checkpoint steps | 8, 16 | 12, 24 |
| Deterministic seed | 7 | 7 |
| Generation ceiling | 288 new tokens | 128 new tokens |

Both use bias=none, unchanged pinned NF4/double-quantized 4-bit bases, BF16 compute, gradient checkpointing, eager attention, AdamW (betas 0.9/0.999, epsilon 1e-8), weight decay 0, one warmup update, linear decay and gradient clipping 1.0. TF32 is disabled and deterministic algorithms are required. No fallback, augmentation, sweep or adaptive extension is defined. Two deterministic shuffled passes are the full update budget; the final smaller auditor accumulation group is normalized by its actual size.

Targets are `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`. Installed Transformers source was parsed to confirm these are Linear assignments in both actual architectures. Manifests enumerate all **196 producer / 224 auditor** full module paths. The future loaded model must resolve that exact set before PEFT is applied. Embeddings and LM head are excluded; optimizer parameters must all be LoRA parameters, with the exact expected count.

The auditor name does not determine its architecture: its pinned config explicitly declares **Llama**, not Phi3. Producer/auditor family separation is preserved.

## Native templates, token boundaries and loss

Only the cached assets at the exact pinned revisions were loaded. Their config/tokenizer file hashes are recorded. No model weight was read. The local Python 3.12.3 tokenizer process uses Transformers 4.51.3, tokenizers 0.21.1, huggingface-hub 0.30.2 and Jinja2 3.1.4. Torch/TF/Flax are disabled in this process; the initial combined Torch/tokenizer import hit a local duplicate-OpenMP initialization error, so tokenizer-only execution avoids that dependency entirely.

For each row, the native prompt tokens must be an exact prefix of the native assistant-completed conversation. All prompt labels are `-100`; assistant JSON and its native terminal tokens receive loss. Padding labels are also `-100`. Tokenization adds no second set of special tokens. The suffix must contain exactly one native EOS and decode to the exact target followed by its terminal. Producer terminal: `<|im_end|>` plus newline. Auditor terminal: `<|end|><|endoftext|>`. Sample decoded boundaries and label indices are preserved in `dry_run_evidence.json`.

No truncation is enabled. Max sequence is `ceil((observed_max + 32)/32)*32`: 869 becomes 928; 750 becomes 800. Oversized rows fail instead of being cropped. Target token counts below include native termination.

| Role | Tokens | Min | Median | p90 | p95 | Max |
|---|---|---:|---:|---:|---:|---:|
| producer | raw_input | 106 | 184.5 | 208 | 212 | 216 |
| producer | rendered_prompt | 550 | 628.5 | 652 | 656 | 660 |
| producer | target | 91 | 130.0 | 207 | 210 | 253 |
| producer | total | 666 | 763.0 | 790 | 861 | 869 |
| auditor | raw_input | 172 | 262.0 | 305 | 340 | 378 |
| auditor | rendered_prompt | 467 | 557.0 | 600 | 635 | 673 |
| auditor | target | 13 | 77.0 | 84 | 87 | 89 |
| auditor | total | 530 | 633.5 | 686 | 707 | 750 |

Separate TRAIN/DEV distributions and all 134 per-example lengths are in the two `token_lengths.json` files. **134/134 target contracts and native token boundaries pass; zero truncated rows and zero prompt tokens receive loss.**

## DEV selection and overfit controls

Each role uses its own data, adapter, checkpoint directories, DEV outputs and selection freeze. Selection is fixed in advance:

1. Require zero counts for all six registered catastrophic categories.
2. Require 100% valid DEV contracts.
3. Maximize the role's arithmetic mean semantic score.
4. Break ties by the earliest optimizer step, then adapter hash.

Producer per-example score is the mean of claim F1, typed-gap F1, typed-uncertainty F1, evidence F1 and semantic completeness. Auditor per-example score is the mean of relation correctness, evidence F1, refusal correctness and measurable reason correctness. Correct expected refusals receive the corresponding relation/reason credit. An exact frozen machine-curated rationale is measurable; alternative rationale prose remains **unassessed**, scores zero for that component and is counted explicitly. Lexical similarity is never treated as truth. These are DEV selection rules, not replacements for the frozen acceptance criteria.

No checkpoint is selected if every checkpoint fails a gate. Training loss is a diagnostic only; its trace is retained beside DEV evidence for train/DEV divergence assessment. Neither protected results nor training accuracy may drive checkpoint choice. Small adapter capacity, two passes, fixed checkpoints, deterministic shuffle, no augmentation and no post-hoc widening limit overfit opportunities.

Every DEV record preserves prompt, raw decoded output, full output including special tokens, token IDs, parsed JSON, contracts, semantic/evidence metrics, latency, token counts, stop reason, generation settings and adapter/base identity. TTFT is explicitly unavailable in the fixed non-streaming evaluator. Selection verification re-scores the saved raw outputs, checks exact DEV membership and validates each adapter's hash, base model and revision. Selection freezes use exclusive creation.

## Protected BASE versus tuned boundary

Both role selections must exist and verify before a protected source is opened. An exclusive one-shot access receipt is written **before** reading targets. A failed protected attempt remains consumed. No new selection or training is allowed after protected access. BASE and tuned use the same loaded base, native tokenizer, prompts and greedy generation settings; BASE disables the adapter, tuned enables it.

Protected source hashes were copied from historical freeze manifests without opening authored target files. `protected_population.json` freezes the original R06 metadata; the separate `protected_eval.py` checks component/source hashes and evaluates only those 114 non-TRAIN IDs. It preserves role/domain/template/family breakdowns, all 27 criteria, R07, six catastrophic limits, evidence integrity, contracts and truncation. Human-review metrics remain zero and final acceptance remains false. Registered DEV overlap is honestly development-inclusive; this is not an independent blind-final claim. Legacy authored target comparisons remain diagnostic and cannot change V3 labels or feed selection.

Protected code/metadata and target sources are **not in the training bundle**. They must be staged as the separate post-selection control phase of a later authorized experiment. No protected model evaluation ran here.

## Runtime and reproducibility

The exact core dependency lock is `dependency_lock.json`: Python 3.12.3 / Linux x86-64 / CUDA 12.1; torch 2.5.1+cu121, Transformers 4.51.3, tokenizers 0.21.1, PEFT 0.15.2, Accelerate 1.10.1, bitsandbytes 0.48.2, safetensors 0.5.3, huggingface-hub 0.30.2, NumPy 2.0.2, Jinja2 3.1.4. PEFT is not installed locally; it is pinned for the future runtime. No new training framework or package was installed. The future runtime must verify all pinned versions/imports, CUDA, BF16 support, source hashes and exactly one visible GPU before opening model weights. This lock does not claim that CUDA kernels were exercised locally.

Set `PYTHONHASHSEED=7`, `CUBLAS_WORKSPACE_CONFIG=:4096:8`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `TOKENIZERS_PARALLELISM=false` before launching the future job. Model acquisition is a separate authorized setup phase using only the exact pinned snapshots; training itself uses local-files-only and trust_remote_code=false. All source subprocesses must use the resolved Python 3.12.3 executable.

Local validation command:

```text
<resolved Python 3.12.3> -B tuning/first_domain_agnostic_v1/dry_run.py
```

Future, **not executed**, separately authorized entries:

```text
<resolved Python 3.12.3> -B tuning/first_domain_agnostic_v1/train.py --role producer --authorization /secure/operator-authorization.json
<resolved Python 3.12.3> -B tuning/first_domain_agnostic_v1/train.py --role auditor --authorization /secure/operator-authorization.json
<resolved Python 3.12.3> -B tuning/first_domain_agnostic_v1/protected_eval.py --authorization /secure/protected-authorization.json
```

Authorization files must bind the action, experiment, permitted roles and exact `freeze.json` hash with explicit operator authorization. None is created for real execution. Fresh output directories are required under `runs/first-domain-agnostic-tuning-v1/<role>/`; no silent resume. Each contains checkpoints, DEV evidence, loss diagnostics, runtime evidence and `SELECTION_FREEZE.json`.

## Executed local validation

**19 grouped checks + 9 counterfactual effect proofs passed.** These counts describe grouped assertions; all 134 rows were also checked individually. The real bounded training orchestration ran against inert model/optimizer substitutes: producer 16 synthetic steps / 64 forward calls; auditor 24 synthetic steps / 92 forward calls. Synthetic checkpoints and outputs were deleted with their temporary workspaces. No optimizer updated real parameters.

Effect proofs cover DEV exclusion, held-out exclusion, assistant mask, prompt-loss exclusion, preselection protected denial, role separation, adapter binding, bundle exclusion and R06 TRAIN exclusion. Each guard was neutralized in memory, its proof failed, and the restored guard passed. Additional checks cover gate-first selection and tie-breaking, one-shot consumption, adapter toggling, exact population, family separation, module-resolution failure, native templates, dynamic padding and missing authorization.

The standalone archive was extracted into a clean temporary directory. A fresh isolated Python process loaded and validated all 134 targets without access to repository modules. No broad historical target-reading regression was run. Dry-run access telemetry: **0 authored/protected target reads, 0 model-weight reads, 0 network calls**. Real generation calls **0**, real optimizer updates **0**.

## Minimal future training bundle

`training_bundle.zip`: **22 files, 88,146 bytes**, SHA-256 `155b6b539d9d924bc56d473fd5fcc34dcacab5379554c91b351fc4f535f48a70`. The archive is deterministic, membership is allowlisted and each extracted file is hash-verified. It contains only required code, exact role TRAIN/DEV inputs/labels, configs, pins and hash manifest. No model weights, protected labels, administrative maps, authored comparisons, unrelated review history, credentials, operator documents or durable state. Nothing was uploaded. New artifact/ZIP-entry credential and leakage scans returned zero findings; `security_scan.json` lists exact paths/counts.

## TRAINING_MEMORY_PROJECTION

One **A10 24 GB class**, sequential roles, is the first reasonable candidate based on static estimates and the prior 23,028 MiB observed capacity. No inventory or price lookup was performed. Training memory is estimated separately from the prior inference result.

| Component (GiB) | Producer | Auditor |
|---|---:|---:|
| Quantized linear weights + scale allowance | 3.403 | 1.890 |
| FP32 embeddings and output head allowance | 4.061 | 0.734 |
| Adapter parameters, gradients, Adam states | 0.301 | 0.223 |
| Checkpointed activations | 2?5 | 1.5?4 |
| CUDA workspace / allocator reserve | 2?4 | 2?4 |
| **Projected peak total** | **11.76?16.76** | **6.35?10.85** |

Plan 16?32 GiB host RAM. These are engineering allowances, not measured peaks. Stop on OOM or kernel incompatibility; do not automatically enlarge hardware or alter the experiment. A single 40 GB class is the next capacity option only after revised authorization, if needed.

## Projected runtime and cost

| Phase | Projected minutes |
|---|---:|
| setup including model acquisition hydration | 5?15 |
| producer training | 4.17?12.89 |
| producer dev evaluation | 2?8 |
| auditor training | 3.37?10.9 |
| auditor dev evaluation | 1?4 |
| protected base evaluation | 5?16 |
| protected tuned evaluation | 5?16 |
| teardown | 1?3 |

Projected rental/GPU minutes and wall: **26.54?85.79 minutes**. At the historical **$1.29/hour** reference rate, projected one-time experiment cost: **$0.57?$1.84**. This is not a hard cost guarantee or a benchmark. Training throughput assumptions are 80?250 sequence tokens/s for producer, 120?400 for auditor; decoding assumptions 20?60 and 30?90 respectively. The measured local sequence counts determine the workload; these speed assumptions are unmeasured. Download speed, kernel readiness, generated lengths and protected evaluation can widen the range. A future operator must separately approve its budget and termination reserve.

The eventual ordinary inference goal remains $0.00?$0.10/run and <=120 seconds/run. One-time training cost is separate; this task supplies no new evidence of those inference targets.

## Future sequence and next action

After separate explicit authorization: provision one suitable instance; resolve/runtime/source preflight; acquire exact pinned snapshots; train producer with its two DEV checks and freeze selection; end its process and release memory; train auditor with its two DEV checks and freeze selection; stage the locked protected control phase; run the one-shot BASE/tuned comparison; collect/hash evidence; terminate and verify provider-side termination. Never run roles concurrently or turn this into the full Shimmer pipeline.

Implementation readiness is established for that bounded plan. Actual CUDA/PEFT training compatibility and quality are deliberately unmeasured. Stop here and retain the plan for operator review; a later explicit authorization is required before cloud or training.

Confirmed: no cloud/search/provisioning, no paid API, no Shimmer generation, no real training/LoRA/SFT, no target-model weight updates, no model/revision/quantization changes, no full pipeline, no multi-round, no push, no independent-test claim and no false human-review claim.
