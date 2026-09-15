# First real domain-agnostic LoRA/SFT feasibility experiment

`FIRST_TUNING_EXPERIMENT_COMPLETED`

The two authorized bounded training plans completed on one Lambda A10. **Producer selection failed**, so protected evaluation was correctly not admitted. Auditor step 24 was selected mechanically under the frozen gates, but its outputs collapsed to refusal on every DEV example. No BASE-versus-tuned protected conclusion is available.

- Producer tuning signal: `INDETERMINATE`.
- Auditor tuning signal: `INDETERMINATE`.
- `BALANCED_TUNING_FOLLOWUP_RECOMMENDED=false`.
- `FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING`; actual human reviews **0**.

COMPLETED describes execution of the fixed training/DEV plan and all **permitted** evaluation. It does not mean semantic success, protected acceptance, production readiness or an infrastructure-invalid run. The absence of protected comparison makes the role-level tuning signals indeterminate.

## Frozen source, authorization and local gates

Tested repository release: `a704fe8ca04032932981f32643aebad98ef2f619`, containing implementation `1225fc1`. Both commits were verified present/ancestral. Starting tracked files were clean; unrelated `SHIMMER_HANDOFF.md` and `durable/` were untouched.

Experiment freeze SHA-256: `f65aaf808012357c1563299304dd274449164901e0fb1911e8d2798bb700c727`.

Unchanged training bundle SHA-256: `155b6b539d9d924bc56d473fd5fcc34dcacab5379554c91b351fc4f535f48a70`; **22 files / 88,146 bytes**. Exact TRAIN/DEV populations remained producer **32/32**, auditor **46/24**. No protected label was in that bundle. The release/freeze, bundle membership, ID/row bindings, model pins and unused launch authorization were verified before provisioning. The maintained **19 grouped no-model checks + 9 effect proofs** passed again, as did provider metadata-security and runtime-contract tests. The pre-provision and post-run checks did not alter historical evidence.

Operator authorization is the attached request `3f71a5ae-a9e5-422a-b729-582035f6f794`. Ephemeral runner permits bound the exact freeze, roles, one-instance limit and $2/$3 budgets. Runner action strings (`train`, `protected_evaluation`) and its hyphenated experiment identifier were explicitly mapped to the operator's task wording. Only safe permit hashes/provenance remain; the permits were removed. `LAUNCH_INTENT.json` permanently records consumption for this run.

The added controller/telemetry envelope did not edit the frozen training/evaluation code or configurations. Its source is preserved with the downloaded evidence. `signal_policy.json` was written before launch; its hash and pre-launch filesystem time are recorded in `GOVERNANCE_AUDIT.json`. No post-hoc effect threshold was added.

## Cloud, budget and verified shutdown

| Item | Observed |
|---|---|
| Provider / region | Lambda / us-east-1 |
| Instance | `43eba68e83e74ef7ae595a1c04918a51` |
| GPU | One NVIDIA A10, 23,028 MiB |
| Rate | $1.29/hour, current inventory queried before launch |
| CPU / RAM | 30 provider-reported vCPUs; 238,546,350,080 OS-reported RAM bytes |
| Activation wait | 260.40 s |
| Training bundle + helper/permit transfer | 4.84 s |
| Torch installation | 58.90 s |
| Other pinned dependencies | 15.79 s |
| Runtime preflight | 7.55 s |
| Pinned snapshot acquisition, controller wall | 338.16 s |
| Evidence download | 41.60 s |
| Conservative billable wall | **2,076.46 s / 34.61 min** |
| Estimated cost upper bound | **$0.7441** |
| Provider-confirmed termination | **2026-09-15T21:53:47.924445Z** |
| Follow-up inventory | **Empty; zero instances** |

A10 was the cheapest available suitable x86-64/BF16 choice. A6000 was unavailable; A100 was available but more expensive. The $2 soft point was 93.02 min; the $3 ceiling 139.53 min. An independent watchdog reserved the final 10 min, with workload cutoff at 129.53 min. Actual cost stayed below both budgets. The estimate conservatively starts at launch request and ends at provider-confirmed absence, not merely activation-to-stop; it is not a provider invoice.

After workload stop, the GPU process list was empty. Evidence downloaded and verified before termination; the provider then confirmed absence and a second inventory query was empty. Temporary provider SSH registration, local private/public key material and both authorization files were removed. No billable resource remains.

## Runtime and models

Python **3.12.3**, Linux x86-64, one visible BF16-capable GPU, torch **2.5.1+cu121**, Transformers **4.51.3**, tokenizers **0.21.1**, PEFT **0.15.2**, Accelerate **1.10.1**, bitsandbytes **0.48.2**, safetensors **0.5.3**, huggingface-hub **0.30.2**, NumPy **2.0.2**, Jinja2 **3.1.4** all passed before acquisition. CUDA runtime **12.1** was usable; the exact driver version string was not captured. Absolute interpreter: `/home/ubuntu/shimmer-first-tuning-20260916/.venv/bin/python`.

Source hashes/compilation, critical imports, CUDA/BF16, RAM and disk gates passed before downloading weights. The pre-acquisition checkpoint explicitly records that no model acquisition had yet begun. Training used local-files-only, trust_remote_code=false and the frozen deterministic environment; external Python socket connections were blocked during model work. No paid inference backend was used.

| Role | Pinned repository / revision | Actual family | Snapshot bytes / acquisition |
|---|---|---|---|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` @ `bdd404162d94997f390efbfa660eb3f21cbbc81d` | Qwen2ForCausalLM / qwen2 | 5,563,135,394 / 259.17 s |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` @ `5c20803aa197416f43fb455e55c85178775320cb` | LlamaForCausalLM / llama | 2,266,650,814 / 76.83 s |

Weight SHA-256 values: producer `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`; auditor `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`. Config/tokenizer hashes matched the frozen asset manifests. No alternative snapshot, quantization or architecture was substituted.

## Exact training and module proofs

Both roles retained rank **8**, alpha **16**, dropout **0.05**, bias none; the same seven attention/MLP projection targets; AdamW lr **1e-4**, betas **0.9/0.999**, epsilon **1e-8**, weight decay **0**, clip **1**; microbatch **1**, accumulation **4**; BF16, gradient checkpointing, eager attention, deterministic algorithms, TF32 disabled, seed **7**, one warmup update and linear decay. No augmentation, sweep, extra epoch, repeated trial, offload workaround or serving migration occurred.

Producer used ceiling **928**, generation cap **288**, checkpoints **8/16**, and exactly **16 optimizer updates** over 64 example visits (two passes of 32). Auditor used ceiling **800**, generation cap **128**, checkpoints **12/24**, and exactly **24 updates** over 92 visits (two passes of 46; final accumulation group of each pass has two examples).

Runtime resolved **196 producer / 224 auditor** exact target-module paths and **20,185,088 / 14,942,208** trainable parameters. Only LoRA parameters entered the optimizer; embeddings, LM head and base weights stayed frozen. The producer process ended and an empty GPU process query was recorded before auditor load. Models were trained sequentially.

## Training, telemetry and loss

| Measurement | Producer | Auditor |
|---|---:|---:|
| Model load | 6.08 s | 4.81 s |
| Total role wall, including DEV | 1050.59 s | 164.25 s |
| DEV generation wall | 955.38 s | 79.33 s |
| Non-generation role remainder | 95.21 s | 84.92 s |
| Ordinary training-step median | 5.468 s | 3.414 s |
| Loss first ? last | 0.934644 ? 0.006419 | 2.850550 ? 0.968331 |
| Peak allocated VRAM | 10.192 GiB | 3.559 GiB |
| Peak reserved VRAM | 11.605 GiB | 3.902 GiB |
| NVIDIA peak memory | 12233 MiB | 4345 MiB |
| GPU utilization mean / max | 36.82% / 100% | 65.83% / 100% |
| Peak process RSS | 4.454 GiB | 1.405 GiB |
| Peak host RAM used | 5.168 GiB | 5.101 GiB |
| Process CPU mean / max | 108.07% / 2697.2% | 143.91% / 2524.4% |
| Approximately 1 s resource samples | 1028 | 160 |

CPU percentages use per-process multicore accounting and can exceed 100%. Ordinary-step medians exclude initialization and the step after DEV, whose inter-step interval includes evaluation. The non-generation remainder also includes loading, tokenization/checkpointing and overhead; it is not a pure forward/backward measurement. Forward/backward time and TTFT were not separately instrumented. No expensive profiler ran.

Producer DEV generation consumed **90.9%** of its role wall. Low training loss did not imply complete semantics or a selectable producer. Auditor's short responses likewise did not imply good fidelity judgment.

## DEV results and exact selection

| Role / step | DEV contracts | Semantic score | Truncations | Accepted outcomes | Selection |
|---|---:|---:|---:|---:|---|
| producer / 8 | 10/32 | 0.24479167 | 1 | 2/32 | Rejected: contract/catastrophic gate |
| producer / 16 | 31/32 | 0.70250000 | 0 | 10/32 | Rejected: contract/catastrophic gate |
| auditor / 12 | 23/24 | 0.35416667 | 0 | 8/24 | Rejected: contract/catastrophic gate |
| auditor / 24 | 24/24 | 0.33333333 | 0 | 8/24 | Selected |

All six catastrophic counts were zero at producer step 16 and both auditor checkpoints. Producer step 8 had exactly **one truncation**; its other five counts were zero. All raw outputs, token IDs, native-special-token output, parsed results, metrics, stop reasons and adapter bindings were preserved. Local recomputation exactly matched every saved checkpoint's metrics.

Producer step 16's remaining invalid example was `v2-chronological_events-catalogue-primary`: strict JSON parsing rejected **extra data after the first JSON value**. No repair was applied. Neither checkpoint met the frozen catastrophic/100%-contract gates, so no producer selection freeze or selected-adapter hash exists. Step 16 is **not** silently promoted to a selected checkpoint.

Producer step 16 micro metrics (precision / recall / F1):

- Claims: **1.0000 / 0.9836 / 0.9917**.
- Typed gaps: **0.4865 / 0.3273 / 0.3913**.
- Typed uncertainty: **0.8214 / 0.8846 / 0.8519**.
- Evidence: **1.0000 / 0.9836 / 0.9917**.
- Semantic completeness and accepted outcomes: **10/32**.

Auditor step 12 failed contract validity (one invalid fidelity judgment), even though its arithmetic score exceeded step 24. Step **24** was the only admissible checkpoint and was selected exactly as frozen. Selected adapter identity SHA-256: `7e7d69cfe4b88200ccde7aa323e4c191a5069a0287de7527ced53a442463af05`. `SELECTION_FREEZE.json`, both underlying adapters, exact DEV IDs/raw-output hashes and recomputed metrics verify locally.

**Auditor step 24 refused all 24 DEV examples; only 8 expected refusal.** Thus 8/24 accepted outcomes and 8/24 correct refusal decisions; 16/24 are over-refusals. Evidence TP=0, FP=0, FN=29: recall/F1=0; precision is undefined rather than fabricated as perfect. There are no correct substantive relation judgments or measurable correct rationales. The 16 non-refusal cases remain unassessed for reason correctness. The selection gate was obeyed, but this is not useful auditor semantic acceptance.

| Checkpoint | Generation wall | Output tokens | Aggregate output tok/s | Stops |
|---|---:|---:|---:|---|
| Producer 8 | 484.38 s | 4,287 | 8.850 | 31 EOS / 1 length |
| Producer 16 | 471.00 s | 4,194 | 8.904 | 32 EOS |
| Auditor 12 | 42.54 s | 337 | 7.922 | 24 EOS |
| Auditor 24 | 36.79 s | 288 | 7.828 | 24 EOS |

Throughput divides output tokens by synchronized generation wall, including prefill; it is not isolated decode throughput. Backend completion/EOS is not contract or semantic success.

## Protected evaluation and frozen acceptance

`BOTH_ROLE_SELECTIONS_FROZEN=false` (producer false, auditor true). Consequently:

- Protected control/data bundle: **not created or uploaded**.
- Protected one-shot receipt: **not consumed**.
- Protected generations: **0**; BASE **0**, tuned **0**.
- Original population: **114 non-TRAIN** (40 DEV / 37 TEST / 37 public-adversarial), unchanged and unopened.
- Protected BASE/tuned contracts, semantic scores, evidence, truncations, catastrophic counts, role/domain/template/family variability: **NOT MEASURED**.
- All **27 frozen acceptance criteria**, protected R06 and protected R07: **NOT MEASURED**, not passing by default. Human criteria remain factually pending/zero.

`PROTECTED_NOT_ADMITTED.json` records each criterion's unavailable status. No protected result influenced selection, and there was no post-protected training, reselection or repeated evaluation. No historical evidence was rescored or rewritten. V1/V2/V3 curation releases and all model/config/criterion pins remain immutable.

Both role signals are therefore **INDETERMINATE**, not NEGATIVE claims about an unperformed BASE comparison. The observed DEV failures are reported directly. The predeclared follow-up condition is false because neither role has a valid protected comparison.

## Evidence integrity and security

Downloaded archive: **259,371,338 bytes**; SHA-256 `450f21fab7e1646c673ea2ea48b1465b521a7e7a44de00d898035aab30ed73ea`. The remote hash matched the local archive before teardown. Safe extraction rejects escaping paths and links. Checkpoint weights remain locally preserved in the archive and extracted run directories; their exact hashes are committed, without adding hundreds of megabytes of adapter weights to Git.

Provider responses passed through the existing safe allowlist. No raw provider object, Jupyter credential/URL, API key, private SSH material or password was retained. Artifact scanning includes the extracted archive members, adapter bytes and all new text/code/report artifacts; results are in `ARTIFACT_SECURITY_SCAN.json` and the final scan manifest. **Zero credential findings**. Authorization values were not printed as tokens. No protected label leakage occurred.

Recompute command (no models, no generation):

```text
<resolved local Python 3.12.3> -B tools/analyze_first_real_tuning.py
```

## Limitations and next action

This is one tiny machine-curated feasibility run. It provides real training/runtime and DEV evidence, not a valid protected BASE/tuned effect estimate. Producer formatting still fails one contract and gap semantics remain weak; auditor over-refusal dominates its selected output. The largest measured time cost was producer DEV generation, not optimizer steps. No threshold, label, rank, LR, batch, ceiling or update budget was changed to rescue the run.

Next action is a **local review of the preserved formatting/gap and over-refusal failure modes** before designing any separately authorized experiment. No automatic training retry or balanced tuning follow-up is recommended by this run. Human review remains pending.

Confirmed: exactly one instance; no second instance; no paid inference API; no model/revision/quantization changes; no hyperparameter sweep or extra training; no protected access or post-protected retraining; no full Shimmer pipeline; no multi-round; no push; provider-confirmed termination and zero billable resources remaining.
