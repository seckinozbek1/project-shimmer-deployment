# Secure remote short-burst feasibility pass — 15 September 2026

## Decision

**CLOUD_FULL_RUN_NOT_ELIGIBLE**

The ordinary-only feasibility measurement is complete with a negative result.
The security and runtime gates passed, real producer/auditor inference ran, safe
evidence was recovered, and the single instance was terminated. This is no longer
a preparation-only result.

The current configuration fails necessary quality conditions: the compact
producer did not obey its source-reconstruction contract, and the independent
auditor hit the unchanged output ceiling, returned an invalid envelope, and
performed the wrong comparison. No representative output was semantically
accepted. Faster hardware and successful backend transport did not fix these
failures. A full run is not justified or authorized.

**Largest measured bottleneck:** the independent auditor call took **18.140 s**,
generated **384 tokens**, truncated, and failed both the required contract and
the fixture's comparison task. Model loading or VRAM capacity was not the blocker.

## Source, security closure and local go/no-go

* Executed source: **`c342033e5d09654cdbaaf283879a9ee37764146b`**.
* Security/controller implementation: **`6308374`**, followed by the tested
  single-GPU inventory projection correction **`c342033`**, both before renting.
* Post-run artifact refinement: **`545ca1d`** retains only package names/versions
  from pip reports; it was not part of the executed source.
* [Boundary audit](PROVIDER_METADATA_BOUNDARY.md): the public Lambda response
  boundary now returns only explicit allowlist projections. The controller,
  status polling, termination evidence, inventory, images, launch and SSH
  registration paths never serialize a raw provider object. Unknown nested
  fields drop automatically. Errors use safe fixed diagnostics.
* **135 pre-provision checks passed:** 11 metadata/controller/bundle tests,
  26 runtime tests, 83 cloud tests, eight transport tests and seven transfer tests.
  The load-bearing allowlist passed neutralise → fail → restore → pass.
  The artifact refinement also passed the 11 security and 26 runtime checks.
* Local Linux wheel/metadata validation established a **41-package pinned
  dependency closure**, without installation or model downloads. The installer
  validates its plan and refuses existing-package replacement or undeclared pins.
* [`LOCAL_GATES.json`](remote_short_burst_secure_20260915/LOCAL_GATES.json) records
  **`REMOTE_RETRY_LOCAL_GATES_PASS=true`** before the only launch.

The initial local inventory gate rejected an irrelevant CPU offer's descriptor.
The fix drops non-single-GPU offers before projection. This happened locally;
no extra instance was rented. The operator's explicit cloud and source-export
authorization covered the maintained controller and reviewed bundle.

## Hardware and preparation measurements

| Measurement | Result |
|---|---|
| Provider / region | Lambda / `us-east-1`, Virginia |
| Instance ID | `4871e6caa9b44b4288be5932ea6bb6ea` |
| Type / GPU | `gpu_1x_a10` / NVIDIA A10 |
| Quoted hourly price | **$1.29/hour** |
| Selection | Cheapest available suitable x86-64 single GPU; RTX 6000/A6000 unavailable |
| Image | Explicit Lambda Stack 24.04, `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0` |
| VRAM observed | **23,028 MiB** |
| CPU / RAM | 30 vCPU; 200 GiB quoted, 238,546,341,888 bytes host RAM observed |
| Storage | 1,400 GiB quoted; 1,430,394,974,208 bytes filesystem space available |
| NVIDIA driver / driver CUDA capability | **580.105.08 / 13.0** |
| PyTorch / its CUDA runtime | **2.5.1+cu121 / 12.1** |
| Transformers | **4.52.3** |
| Python | **3.12.3**, experiment constraint `>=3.12,<3.13` |
| Provisioning to provider `active` | **193.522 s** |
| SSH readiness after active | **1.913 s**; first attempt succeeded |
| Source transfer | **1,268,892 bytes / 165 files / 3.846 s** |
| Remote archive hash check and extraction | **1.848 s** |
| Bootstrap source compilation/import check | **2.696 s** including SSH |
| Explicit isolated environment creation | **4.277 s** |
| Missing pinned dependency installation | **84.150 s** |
| Dependency import/version recheck | **5.361 s** |
| Acquisition stage, including repeated runtime gates | **25.152 s** |
| Producer snapshot acquisition | **12.450 s**, 5,563,135,394 bytes, initially uncached |
| Auditor snapshot acquisition | **6.401 s**, 2,266,650,814 bytes, initially uncached |
| Bounded inference subprocess stage | **68.493 s**, including preflight/loads/cleanup |
| Evidence archive transfer | **147,520 bytes / 11.266 s** before metadata projection |
| Termination request to first verified termination | **80.084 s** |

The source-only bundle contained tracked code, three required tracked
configurations (`local_models`, `constitution`, `agent_contracts`) and its hash
manifest. Credentials, operator documents, durable state, ignored files, model
weights and unrelated history were excluded. Archive SHA-256:
`33b205c4b2ceec9f3aef3c67abf2b27a56284ea3f94cdc6b5590dbb0e63d7b2d`.
No historical 5.30 GB upload was repeated.

The verified image interpreter bootstrapped source checks and the explicitly
isolated environment. The final experiment executable was:
`/home/ubuntu/shimmer-secure_burst_20260915b/.venv/bin/python`.
All dependency, acquisition and probe Python subprocesses used that executable.
The exact 3.12.3 sealed reference remains distinct from the experiment's 3.12.x
compatibility rule. No production syntax or runtime pins were loosened.

Source integrity, real compilation of **148 Python files**, nine critical imports,
and dependency versions/importability passed. The
[pre-inference checkpoint](remote_short_burst_secure_20260915/evidence/PRE_INFERENCE_CHECKPOINT.json)
was persisted before acquisition. Preparation's `READY` marker means its stages
completed; it does not certify output quality or cloud eligibility.

## Models, residency and resource envelope

Configured checkpoints/revisions were unchanged:

| Role | Checkpoint | Revision | Cold load |
|---|---|---|---:|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | `bdd404162d94997f390efbfa660eb3f21cbbc81d` | **3.962 s** |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | `5c20803aa197416f43fb455e55c85178775320cb` | **0.697 s** |

The checkpoints' actual `AutoConfig.model_type` values were **`qwen2` and `llama`**.
They were distinct. The configured auditor repository is named Phi; the recorded
runtime architecture label is `llama`, and is preserved rather than relabeled.
No alternative checkpoint, new quantization policy or serving engine was used.

Both models stayed resident on `cuda:0`, each loaded **once**, with no CPU/disk
offload and no swap configured. A producer call after auditor loading reused the
producer. Loader allocation rose from **5,290.654 MiB** after producer load to
**7,458.223 MiB** with both models. The earlier progress shorthand of 5.29 GiB
should be read as 5,290.654 MiB (**5.17 GiB**).

From 59 approximately one-second samples:

* Peak GPU memory: **10,375 / 23,028 MiB (45.1%)**, including runtime allocations.
* GPU utilization: **48% median / 100% peak** across phases; producer-call median
  **48.5%**, auditor-call median **42.5%**.
* Host CPU utilization: **3.4% median / 16% peak**.
* Process RSS peak: **2.407 GiB**; total host RAM used peak **4.105 GiB**;
  available host RAM never fell below **216.109 GiB**.
* Producer RSS before/after load: **0.387 / 0.714 GiB**; auditor **1.288 / 1.309 GiB**.

These are sampled bounded-probe measurements, not guaranteed instantaneous peaks
or a full-run envelope. No load-phase GPU sample landed inside the sub-second
auditor load. The two-model design fits this hardware for these probes. No reload
penalty was observed; a separate transition-overhead measurement remains unknown.

## Inference and fixture quality

All calls used the real optimized Shimmer loader, dispatch boundary and worker,
seed 7, no sampling, **384 maximum output tokens** and the unchanged **25 s**
generation-time ceiling. Neither ceiling was raised.

| Call | Input / output tokens | Wall / generation time | Output tok/s | Stop | Contract | Semantically accepted |
|---|---:|---:|---:|---|---|---|
| Compact PROCESSOR | 610 / 259 | **12.365 / 12.350 s** | **20.971** | EOS | Invalid | No |
| One source-copy comparison | 482 / 273 | **12.702 / 12.698 s** | **21.499** | EOS | Valid | No |
| Independent auditor | 1,875 / 384 | **18.140 / 18.134 s** | **21.176** | Length cap | Invalid | No |
| Serial-path producer | 610 / 259 | **12.127 / 12.122 s** | **21.366** | EOS | Invalid | No |

TTFT is unavailable from this wrapper, which records it as null. Generation time
includes prefill; exclusive decode time was not separately measured. Output
tok/s above divides actual tokens by measured generation time.

**Four backend returns, three EOS-complete returns, one structural contract-valid
return, zero semantically accepted returns, one truncation.** The three optimized
calls had zero valid contracts. The source-copy comparison's two parsed items do
not count as accepted semantic content.

The representative fixture has two capacity claims (120/130 units with two
references) and explicitly says the reporting date is missing. Compact payloads
instructed one item per owned span, with `section_id` and `draft_text` set to the
same short span alias for Python reconstruction. Both compact calls instead
copied prose into two items and omitted the missing-date question. The real
hydration validator rejected them; this was not a compilation/runtime error.
The source-copy comparison also omitted the missing-date sentence/question and
failed exact source reconstruction despite structural contract validity.

The independent auditor received an authored complete extraction matching the
original. Expected finding: **MATCH**. It instead judged planned 120 versus
reported 130 as an irregularity, emitted an ungrounded `CONV-001` attribution,
provided only one reference in its completed fragment, and ended mid-envelope.
Typed task judgment, reasoning, reference completeness and contract validity
therefore failed. The remote environment did **not** solve the laptop's incomplete
auditor behavior. Different prompts/workloads prevent an apples-to-apples laptop
speedup claim. See [fixture assessment](remote_short_burst_secure_20260915/semantic_assessment.json).

## Mandatory serial path and concurrency

The serial-path producer was rejected, so its required auditor handoff was
correctly blocked. Combined accepted serial latency and transition overhead are
**unknown**, not the sum of unrelated calls. No invalid extraction was certified.

Concurrency 1-vs-2 was **not admitted** because both primary role quality gates
failed. Concurrency 4 was consequently not admitted. No synthetic sleeps,
duplicate models, extra roster calls or disguised full review were used.

The actual six worker tasks (two loads/four calls) ran sequentially on one CUDA
owner. **No GPU overlap was observed.** There is no measured capacity-2 speedup,
batching result or concurrent-wall comparison. The existing one-thread worker
architecture cannot be called useful parallel inference merely from admission;
this pass provides no reason to migrate serving engines before fixing quality.

## Projection and cost distinction

The existing deterministic engine was run on the unchanged ordinary graph:
**20 planned calls / five semantic waves**. Current rejected/truncated timings
are retained as observations. No old A100/laptop service time was imported, and
failed attempts were not substituted for accepted-service measurements.

Accepted-run critical path, warm wall range, inference/retry overhead, projected
truncation/refusal risk and full-run resource envelope remain **unknown**.
Both `marginal_cost_per_accepted_run` and `fully_loaded_cost_per_accepted_run`
remain **unknown** because there were zero accepted representative outputs.
This uncertainty does not change the negative verdict: observed truncation and
semantic/contract failures already violate necessary eligibility conditions.

A separate, explicitly conditional **failed-attempt capacity screen** uses only
this retry's role timings: seven producer-class and 13 auditor-class calls,
serialized, hypothetically of the same size as these fixtures. It gives:

| Conditional arithmetic, not accepted-run projections | Result |
|---|---:|
| Warm attempted graph service | **320.712–322.380 s** |
| Warm attempted graph instance cost | **$0.1149–$0.1155** |
| Observed non-call elapsed time, including all setup/collection/teardown | **451.790 s** |
| One-instance-per-attempt scenario | **772.502–774.170 s / $0.2768–$0.2774** |
| Setup amortized over ten otherwise identical attempted graphs | **$0.1311–$0.1317 per attempt** |

Other agent workloads are unmeasured, the auditor stopped at truncation, and an
actual full attempt could refuse early. These numbers are a capacity screen,
not a prediction of a successful ordinary run. A genuinely warm service would
amortize setup; accepted-run costs cannot be claimed from that arithmetic.
See [engine input/output](remote_short_burst_secure_20260915/projection_output.json)
and [screen assumptions](remote_short_burst_secure_20260915/capacity_screen.json).

## Recovery, security sweep and verified teardown

The controller stopped named workloads, found no remaining model/preparation
process in the final process check, collected and verified the archive, then
requested termination. First provider-confirmed termination:
**2026-09-15 09:29:29.821609 UTC**. A second safe provider query confirmed absence
and **zero active instances**. Temporary provider SSH registration and local
private/public key material were removed and verified.

Conservative duration, launch-request start through first termination confirmation:
**507.125 s**. Estimated total instance-cost upper bound: **$0.181719681**.
This is an elapsed-time estimate, not a provider invoice, and is below both budget
limits. No billable instance remains.

The final artifact sweep found **zero credential-pattern hits and zero forbidden
authentication fields**. One public Codecov badge query was embedded in a
third-party package README inside pip's report; no provider/account credential
was exposed. Unneeded package descriptions were projected out of local reports
and the retained archive. Original transfer hash and retained archive hash are
both recorded in [artifact projection](remote_short_burst_secure_20260915/artifact_projection.json).
Inference measurements were unchanged. The installer now retains only package
identities. [Artifact hashes](remote_short_burst_secure_20260915/artifact_hashes.json)
cover the retained safe evidence. All 55 checked historical artifacts still match;
the 14 September evidence and earlier reports were not edited.

## Roadmap disposition and next task

**Close the remote ordinary short-burst feasibility measurement as NOT ELIGIBLE.**
The next task is a narrowly scoped compact-extraction/auditor prompt-contract A/B,
with deterministic fixtures first, unchanged model pins and ceilings, and explicit
checks for alias reconstruction, missing information, MATCH judgment, reasoning
and both evidence references. Inspect the auditor checkpoint's reported runtime
architecture as recorded. Do not weaken validators or raise ceilings to mask the
failures. Any later cloud measurement needs its own authorization.

**Full pipeline NOT run. Multi-round NOT run. Paid inference API NOT used.
Instance terminated and provider-confirmed. No secrets retained in new artifacts.
No push.** Operator-owned `SHIMMER_HANDOFF.md` and `durable/` were preserved.


## Local compact-contract follow-up ? 15 September 2026

The local-only correction after `1aa4696` is complete in implementation/evidence
commit `1991060`. See [Compact extraction and auditor contract A/B](COMPACT_CONTRACT_AB.md)
and [current handoff](RESUME.md). Exact remote prompt hashes are reproduced; compact
producer ownership/reconstruction and scoped auditor fidelity contracts now pass
85 deterministic checks, 4 mutation proofs and both pinned-tokenizer budget profiles.
Readiness is **REMOTE_CONTRACT_AB_READY**, not a model reliability or full-run verdict.
The closed secure feasibility result remains **CLOUD_FULL_RUN_NOT_ELIGIBLE**.
No new cloud, inference, full pipeline, multi-round, serving change or push occurred.


## Subsequent real-model A/B ? 15 September 2026

The separately authorized measurement at `54df6a4` is complete:
[REMOTE_CONTRACT_MODEL_AB.md](REMOTE_CONTRACT_MODEL_AB.md).
**REMOTE_CONTRACT_MODEL_AB_FAIL**; both revised responses reached EOS but failed
strict contracts and semantic acceptance. The serial handoff was withheld.
**DOMAIN_AGNOSTIC_TUNING_RECOMMENDED=true** for both roles; see the bounded
[future task-data/evaluation design](DOMAIN_AGNOSTIC_TASK_TUNING_DESIGN.md).
One A10 was provider-confirmed terminated, cost upper estimate $0.20671457.
No concurrency, model training, full pipeline, multi-round, paid inference API or push.
This new evidence layer does not alter the historical results above.
