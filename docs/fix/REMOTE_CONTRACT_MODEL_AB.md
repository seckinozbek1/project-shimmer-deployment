# Remote producer/auditor contract A/B — 15 September 2026

## Decision

**REMOTE_CONTRACT_MODEL_AB_FAIL**

**DOMAIN_AGNOSTIC_TUNING_RECOMMENDED=true — producer and auditor.**

Both revised calls reached EOS without truncation. Neither produced an acceptable
contract response. The producer omitted the required information gap and contradicted
the status rule; the auditor appended unsolicited prose and gave a partly incorrect
account of the missing date. The serial handoff was correctly withheld. Exactly four
model calls ran; no retries, concurrency, training or full pipeline ran.

This is a new evidence layer after [local deterministic readiness](COMPACT_CONTRACT_AB.md).
It does not rewrite the closed [secure feasibility measurement](REMOTE_SHORT_BURST_SECURE_FEASIBILITY.md).
Deterministic readiness was necessary, but did not establish model compliance.

## Execution and local gates

- Tested commit: **`54df6a48e8646cf721d6d2e2f2ecb60125a92bef`**.
- Starting HEAD: `9f2b275`; compact-contract implementation: `1991060`.
- Narrow controller change before cloud: $0.50 soft / $1 hard budget, four A/B calls,
  at most one auditor handoff over the actual accepted producer output, an explicit
  raw-hash-bound semantic admission decision, and no concurrency branch.
- 139 security/runtime/controller/transport/bundle checks plus 85 compact and relevant
  regression checks passed: **224 checks**, four compact mutation proofs, both pinned
  tokenizer profiles. One existing optional-directory coverage skip remained.
- `REMOTE_RETRY_LOCAL_GATES_PASS=true` was recorded before provisioning. Current old/new
  rendered hashes and cached-tokenizer budgets passed; exact source and bundle were reviewed.
- Bundle: **172 files / 1,283,791 bytes**; only tracked source, three required config
  files and hash manifest. No operator input/state, credentials or laptop model weights.
  Archive SHA-256: `8ddefc807e7fc6a3e7ed17047d66db20bd2f1c995a290ce7a920f849ebfad254`.
  Source-manifest SHA-256: `0dbeb8f59ad9bffb2068258cbbdf0dfce8850e75c3c1eee2c6d918dfd466688a`.

## Hardware, runtime and fixed conditions

One fresh **A10, 24 GB class / 23,028 MiB observed**, `gpu_1x_a10`, **us-east-1**,
**$1.29/hour**. Current safe inventory was queried; this was the cheapest suitable
available x86-64 single-GPU candidate. Instance ID:
`81bd56e1becb4fa7abc56fe0884e5bdf`.

30 vCPUs, Intel Xeon Platinum 8358 @ 2.60 GHz. Provider plan reports 200 GiB RAM;
`free` observed 238,546,337,792 bytes. Root filesystem: 1,455,042,297,856 bytes,
1,430,394,884,096 available at readiness. No swap. Driver 580.105.08 reports CUDA
compatibility 13.0; PyTorch is **2.5.1+cu121**, compiled CUDA **12.1**. Transformers
**4.52.3**, tokenizers **0.21.4**, bitsandbytes **0.48.2**, accelerate **1.10.1**.

Python **3.12.3**, resolved absolute executable
`/home/ubuntu/shimmer-contract_model_ab_20260915/.venv/bin/python`, was used consistently.
Source integrity, compilation of 155 Python files, critical imports and pinned dependency
recheck all passed before `PRE_INFERENCE_CHECKPOINT.json` and model acquisition.

| Role | Fixed model | Revision | Actual config family |
|---|---|---|---|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | `bdd404162d94997f390efbfa660eb3f21cbbc81d` | qwen2 |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | `5c20803aa197416f43fb455e55c85178775320cb` | llama |

No model, revision, quantization or serving change. Seed **7**, deterministic decoding,
**384 output tokens**, **25 seconds** maximum generation time. Multi-round false.
Inference network connections were blocked; local model backends were explicitly routed.
Both pinned snapshots were absent initially and acquired on the instance.

## Paired OLD / NEW measurements

All rows below are real calls from this experiment, not imported historical latency.
TTFT was unavailable for every call. Latency is dispatch wall; generation time is
reported separately in the machine-readable observations.

| Call | Prompt tokens | Output tokens | Wall s | Generation s | Output tok/s | Stop | Contract | Accepted |
|---|---:|---:|---:|---:|---:|---|---|---|
| Producer OLD | 610 | 259 | 12.423 | 12.408 | 20.874 | EOS | invalid | no |
| Producer NEW | 333 | 84 | 3.973 | 3.970 | 21.156 | EOS | invalid | no |
| Auditor OLD | 1,875 | 384 | 18.176 | 18.169 | 21.135 | length cap | invalid | no |
| Auditor NEW | 488 | 350 | 16.325 | 16.323 | 21.442 | EOS | invalid | no |

Producer NEW reduced prompt tokens **45.41%**, output tokens **67.57%** and wall
**68.02%** (8.449 s). Auditor NEW reduced prompt tokens **73.97%**, output tokens
**8.85%** and wall **10.18%** (1.851 s). These are efficiency improvements of rejected
answers, not accepted-work speedups. Decode throughput remains approximately 21 tok/s.

Rendered prompt SHA-256 values matched the reviewed controls/revisions exactly:

| Arm | Hash |
|---|---|
| Producer OLD | `8e9e24361119625e6dad41616c38d8371794a1d79dfbd23ed5d49f64856d155e` |
| Producer NEW | `b0cd3c1f6eb687992910475667fabed4ded130ca8cb06f443521ec52c45658a1` |
| Auditor OLD | `9a77d7299564580be380f2b823bdde6f2b4413e2e3694bba128eb57dcc0ce57e` |
| Auditor NEW | `c9172df69079406656d40d2d753641d8179bbbc68c6690df39955290e11d0f7c` |

## Semantic adjudication, separate from parsing

The authorized original contains planned and reported capacities with their own labels
and refs, and explicitly states that the reporting date is unavailable. The authored
extraction preserves all of that text and adds the missing-date question. Expected
fidelity judgment is MATCH; no equality/compliance rule was routed.

### Producer OLD

Repeated the former failure: two prose-copy items claim one owned alias; missing-date
question omitted. Claim IDs and both refs appear across the raw items. Existing hydration
refuses it. No response repair occurred.

### Producer NEW

Improved to one correct `s0` alias, no copied source prose, both claim IDs and both refs.
However, it emitted markdown fences, empty `questions`/`uncertainty`, and **status `empty`
despite populated claims**. Missing-information extraction failed. Strict whole-response
JSON rejected the fences. Even merely reading the displayed JSON fields shows the status
contradiction and omitted gap; stripping fences would not make it semantically correct.

No source reconstruction was accepted for this model response. Raw claim/ref observations
are diagnostic facts, distinct from the parser's empty/failed accepted result.

### Auditor OLD

Repeated the wrong within-original comparison, called movement irregular, invented
`CONV-001`, cited only REF-0001 and truncated inside a duplicated record. Wrong task,
incomplete evidence, invalid contract and no semantic acceptance.

### Auditor NEW

Emitted **MATCH and both refs**, with no rule attribution or numeric-governance relation.
The initial fidelity statement is correct. The reason then calls the already-absent date
an extraction discrepancy/omission, and its extra prose says the gap was not addressed
in extraction. In fact the extraction preserves the absence and explicitly asks about it.
Reason correctness is therefore **partial, not passed**: the judgment is right, but its
explanation still confuses pre-existing missing information with extraction loss.

A substantial unsolicited explanation follows the complete JSON prefix. The whole response
is not one JSON object. Strict rejection is correct; no prefix recovery was used for acceptance.
The call reached configured EOS **32000** before the cap. This does not support a runtime
turn-end/EOS defect as the explanation for the failure. The 350-token output is far above
the authored 71-token valid answer despite having no capacity requirement to be that long.

### Totals and serial gate

Four calls, **one truncation (OLD auditor), zero NEW truncations, zero contract-valid
responses, zero semantically accepted responses**. Both NEW raw responses emitted both
required refs; neither produced accepted evidence-bearing output. OLD auditor hallucinated
a rule; **neither NEW response did**. No genuine refusal was emitted.

The raw-hash-bound semantic decision rejected both NEW calls, so **serial handoff was not
admitted**. Accepted serial critical-path latency is **unmeasured**. No concurrency calls
ran, and no <=120-second full-run projection or eligibility promotion is made.

## Resources and residency

Producer cold load **4.038 s**, auditor **0.723 s**. Each loaded once; both were present
in the resident model registry after auditor load. No CPU/disk offload, reload or swap.
Allocated VRAM after loads: 5,290.65 MiB and 7,458.22 MiB. Sampled process/GPU use peaked
at **10,315 MiB / 23,028 MiB**. Process RSS peak **1.829 GiB**; host used RAM peak **4.058 GiB**.

GPU utilization during actual call windows: mean **41.28%**, median **42%**; per-arm means
44.92%, 56.50%, 42.17%, 33.75% respectively. Active-window CPU mean **3.49%** of host;
overall sampled CPU peak 16.1%. One-second sampling gives 12/4/18/16 samples per call.
Idle adjudication samples are excluded from typical active GPU/CPU figures.
No dedicated switch-penalty probe ran; accepted serial switching latency remains unmeasured.
Hardware capacity was not the demonstrated blocker.

## Timing, cost and teardown

| Component | Seconds |
|---|---:|
| Launch to provider active | 209.828 |
| SSH readiness after active | 1.872 |
| Source transfer | 3.937 |
| Missing pinned dependency installation | 84.284 |
| Dependency recheck | 5.340 |
| Model acquisition stage | 25.995 |
| Combined model hydration | 4.762 |
| Sum of actual generation times | 50.870 |
| Sum of four dispatch walls | 50.897 |
| Launch to first call (includes provisioning/setup/producer load) | 361.246 |
| Last call to recorded admission rejection/probe finish | 72.015 |
| Probe finish through collection and provider termination confirmation | 91.989 |
| Termination request to provider-confirmed absence | 70.963 |
| **Total billable upper bound** | **576.878** |

Component windows overlap and must not be summed indiscriminately. The maintained
`bounded_inference` subprocess stage took 136.275 s including startup, loads, calls and
semantic-admission wait; it is not 136.275 s of model generation. Setup and admission
overhead are not hidden inside an accepted inference latency.

Estimated prorated cost upper bound: **$0.20671457**, below both $0.50 soft and $1 hard
limits. No second instance was launched. The model responses were preserved first;
no source/prompt changes or resampling were performed while billing.

Workloads stopped, process-state inspection completed, and evidence archive SHA-256 was
verified remotely and after download:
`0ac22013231042fa58c31c4ea77a0bcf9334e27f757340b0334b18ab4e512008` (13,035 bytes).
Termination confirmed **2026-09-15 10:52:20.890272 UTC**. A second provider query at
**10:53:04.306875 UTC** confirmed the instance absent, zero billable experiment instances,
and zero account nonterminated instances. Temporary provider SSH registration and local
key pair were removed. No billable resource remains from this experiment.

## Tuning decision and limits

The revised contracts were internally consistent, much shorter, had all input evidence,
passed deterministic fixtures, and admitted representative valid answers far below 384
tokens. Runtime, source integrity and adapter checks passed; actual prompt hashes matched.
No demonstrated transport, missing-evidence or insufficient-capacity defect explains the
new failures. The parsers correctly enforced the intended strict formats.

Classify producer failures primarily as **model/task semantic capability and instruction
following** (gap omission, status consistency, fences). Classify auditor failures primarily
as **instruction following/output efficiency**, with a **semantic reason error**. Evidence
selection and invented rule attribution improved in both NEW arms. No tiny controller
correction could restore the producer's omitted semantics, so the optional repair/retry
allowance was not used. This is not another prompt-revision loop.

Recommendation targets **task semantics across domains**, not domain vocabulary or facts.
See [future data/evaluation design](DOMAIN_AGNOSTIC_TASK_TUNING_DESIGN.md). This recommends
a next roadmap task, not immediate training. One authored fixture and one deterministic
draw per arm do not establish broad prevalence, near-perfect quality, or tuning efficacy.

Evidence lives in [contract_model_ab_20260915](contract_model_ab_20260915/), including raw
and parsed outputs, separate semantic adjudication, structured error records, tuning
decision, all prompt artifacts, timing/resource records, local gates, security scan and
provider termination proof. New artifacts and archive members have zero credential hits.

**No full pipeline, full benchmark, multi-round, paid inference API, model training,
concurrency/serving migration, model/pin/quantization change, ceiling increase or push.**
