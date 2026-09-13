# Local performance diagnostic

Status: **complete**, 2026-09-13. Measurement design was recorded before instrumentation.
Baseline source: `5b72b16c67b02890ffc8be39096b5bad10e1c05c`.
Scope: diagnosis only. The next locked item is **Local speed-optimization audit**.

The [dense quality-baseline addendum](#dense-quality-baseline-addendum-2026-09-13)
below scores this same saved run under separate post-run authorization. It records
3/5 location recall, the manual correctness qualifications and the quality invariant
for the next item. The original performance measurement did not read the answer key.

## Result and reproducible baseline

The controlled native run took **5,054.4 seconds (84 min 14.4 s)**. Actual
`model.generate` calls account for **4,947.4 s, 97.9%** of that wall time.
Generation model loading accounts for only **34.4 s, 0.68%**. This baseline is
dominated by serialized inference, with important output-consumption and host
performance variability findings below. No optimization was implemented.

| Baseline property | Recorded value |
|---|---|
| Workload | Shipped `clinical_reference`; 3 input files, 5,265 bytes; unchanged |
| Target | `context/result_sheet.md`, 1,088 bytes; 1 document, 6 units |
| Grounding | `context/analyte_reference_ranges.md`, 2,089 bytes |
| Conventions | `conventions/lab_conventions.md`, 2,088 bytes; all 5 rules compiled |
| Role/mode | Existing explicit target/grounding manifest; standalone Normal Review, default paired mode |
| Backend | Local producer/auditor profile; flag and environment both local |
| Native start / exit | 2026-09-13 08:50:49.611 / 10:15:03.996 UTC; native exit 0 |
| Pipeline start / finish | 08:50:56.916 / 10:15:00.852 UTC |
| Completion | `completed`, `reached_end=true`, 1 document, 3 amendments |
| Run identity | `758b17f33e6344f4902024e53d4b38e1` |
| Calls | 26 dispatches, 26 generations, 26 cost rows, 26 evidence rows; all 26 joined |
| Coverage status | 11 selected pairs judged, 1 rejected, 18 undecided/refused out of 30 possible; no absence path exercised |
| Editorial status | `REVIEWED`; only EDITOR_CLERK, 0 escalation rounds, 1 consolidated observation; `failed=null` |

The run completed, but this is **not a quality certification**. Twelve calls hit
their output cap: nine producer and three auditor calls. Two contract-violation
dumps were written, for CITATION_RESOLVER and VERIFIER. No generation raised an
error, and no timing spans remain open. A successful generation, a recovered
contract, a reviewed board and complete substantive coverage are different facts.
No answer key was opened or scored. The board's `terminal_cap_reached=false`
describes board escalation, not whether the individual generation hit its token cap.

The ignored harness command was `py -3.9 -X utf8 output/local_performance/diagnostic.py`.
It ran the unchanged copied `tools/run_local_demo.py` and `pipeline.main` with
`--backend-profile local --non-interactive --skip-confirmation
--sensitivity-layer-inactive-override --no-redaction-override`, an isolated
`--output-dir` and the existing wrapper's `--sample-file`. No model-check bypass,
document limit, prompt reduction or token-budget change was used. The normal
human launcher was traced, not timed interactively. Do not rerun the harness over
this evidence root: a future authorized comparison needs a new isolated root.

Hardware was an RTX 3070 Ti Laptop GPU with 8 GiB VRAM, NVIDIA driver 616.56,
15.71 GiB system RAM, Intel Family 6 Model 154 Stepping 3, 14 physical / 20 logical
CPUs and 14 PyTorch threads. Windows build 26200; Python 3.9.13 at the established
Visual Studio Python39_64 interpreter. Installed versions: torch 2.5.1+cu121,
CUDA 12.1, transformers 4.52.3, sentence-transformers 4.1.0, bitsandbytes 0.48.2,
psutil 7.0.0. No dependency, driver or machine setting was changed.

## Ranked wall costs and phases

This non-overlapping partition uses event boundaries. When spans nest or a
sampler write overlaps inference, the higher-priority consumer owns the interval:
generation, generation load, embedding load/encode, tokenize/decode, I/O/render,
deterministic work, setup/import, residual. It sums to native process wall time.
The underlying inclusive timings remain available separately.

| Wall category | Seconds | Share |
|---|---:|---:|
| Generation, including prefill | 4,947.36 | 97.883% |
| CPU embedding encode, including its tokenization | 55.42 | 1.096% |
| Producer + auditor first loads | 22.27 | 0.441% |
| Producer reload for editorial board | 12.16 | 0.241% |
| Embedding loader, first use + reuse | 2.63 | 0.052% |
| Generation tokenization + decode | 0.63 | 0.012% |
| I/O, serialization and rendering outside higher-priority consumers | 0.77 | 0.015% |
| Timed deterministic consumers outside the above | 0.77 | 0.015% |
| Diagnostic setup | 4.57 | 0.090% |
| Pipeline import | 2.27 | 0.045% |
| Other / unattributed | 5.54 | 0.110% |
| Waiting / idle | Not independently measured | Unknown |

The residual includes interpreter startup, shutdown and unwrapped work. It is not
an idle estimate. The recorder spans 5,051.24 s; native startup before it is 0.086 s
and shutdown after it about 3.06 s. The observer captured native process exit.
Instrumentation changes import timing and adds recording/sampling overhead; there
was no expensive uninstrumented repeat to estimate that overhead as a percentage.

| Phase, ranked | Existing phase duration | Model calls |
|---|---:|---:|
| 3-4: content production + legal deepening | 2,323.846 s / 38.73 min | 12 |
| 5.5: convention review | 989.536 s / 16.49 min | 11 |
| 5: verification | 933.051 s / 15.55 min | 2 |
| 6.5: editorial board | 745.626 s / 12.43 min | 1 |
| 0: population/boot/ensemble, marker boundary | 50.601 s | 0 |
| 6: synthesis | 0.916 s | 0 |
| 8/end, marker to final recorder event | 0.391 s | 0 |
| 7: audit synthesis | 0.017 s | 0 |
| 1: deliberation, marker boundary | 0.013 s | 0 |
| 9: Normal redaction-skip bookkeeping | Less than 0.001 s | 0 |

Existing phase milliseconds are authoritative where present. Marker intervals
include boundary bookkeeping, so they should not be expected to match nested
function timers exactly. The pre-phase-0 startup interval was 7.23 s.

## Model and agent performance

Producer is `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`; auditor is
`unsloth/Phi-3.5-mini-instruct-bnb-4bit`. Embeddings use `BAAI/bge-m3` on CPU by
the existing local-profile policy, not an unexpected generation fallback.

| Model | Calls | Generation | Input / output tokens | Median output tokens/s | Capped calls |
|---|---:|---:|---:|---:|---:|
| Qwen producer | 13 | 3,040.09 s / 50.67 min | 55,137 / 33,787 | 13.03 | 9 |
| Phi auditor | 13 | 1,907.26 s / 31.79 min | 91,844 / 7,055 | 3.65 | 3 |

Throughput divides output tokens by whole generation time, including prefill.
Different prompts, output lengths and changing host conditions prevent a fair
model-to-model speed comparison from those medians alone. All 26 generations
received CUDA tensors, and every loaded generation model reported `cuda:0` with
device placement only `0`. No generation CPU offload was observed.

| Loader/cache effect | Actual observation |
|---|---|
| Producer first load | 12.843 s; 5,311 MiB allocated, 5,330 MiB reserved after load |
| Producer reuse | 11 resident hits, each about 0.3-0.5 ms |
| Auditor first load | 9.423 s, including 1.091 s producer eviction; 2,168 MiB allocated, 2,978 MiB reserved |
| Auditor reuse | 12 resident hits, about 0.35-2.50 ms |
| Producer return | One reload at editorial board, 12.163 s; 5,330 MiB allocated |
| Eviction | 3 invocations including initial empty-cache call; 2 actual evictions, 1.463 s inclusive total |
| Embedding first use | 2.628 s; CPU model, then 22 resident loader hits |
| Tokenizer loads | 4: producer twice, auditor once, embedding once; 2.133 s nested inside model loading |

Every generation-loader return reported exactly one resident generation model.
Observed allocation fell from about 5.3 GiB producer weights to about 2.2 GiB
auditor weights. This is measured reuse and eviction, not only a source inference.
Models were not loaded once per agent or redundantly duplicated in the resident
cache. Avoiding the one producer reload alone could recover at most about 12 s
in this run before considering changed scheduling or memory costs.

| Agent, ranked by generation | Calls | Generation seconds | Output tokens |
|---|---:|---:|---:|
| LEGAL_ANALYST | 7 | 1,262.56 | 12,196 |
| PRACTICE_AUDITOR | 11 | 984.02 | 2,959 |
| EDITOR_CLERK | 1 | 733.38 | 8,192 |
| VERIFIER | 1 | 482.24 | 2,048 |
| FACT_CHECKER | 1 | 441.00 | 2,048 |
| PROCESSOR | 1 | 391.74 | 4,793 |
| ARCHIVIST | 1 | 314.32 | 4,096 |
| INST_FINDER | 1 | 153.20 | 2,048 |
| CITATION_RESOLVER | 1 | 153.07 | 2,048 |
| SPEECH_ACT_TAGGER | 1 | 31.82 | 414 |

Six legal-deepening follow-ups used about 1,104.4 s (18.4 min), beyond the initial
LEGAL_ANALYST call. That is a large auditable cost, not proof the calls are
redundant. Eleven PRACTICE_AUDITOR calls correspond to the eleven selected pairs;
the measured pairing evidence does not establish duplicate pair dispatch.
PROCESSOR used 4,793 of its unchanged 8,192-token allowance and was not capped.
VERIFIER saw 9,243 input tokens, illustrating why a small target can still create
a large accumulated audit context. Per-call IDs, phases, task types, tokens,
budgets, load/reuse, devices, truncation and throughput are in `inference_calls.json`.

## Resource behavior

There are 1,682 samples, with a median interval of 3.006 s. Process RSS peaked at
**6.67 GiB**. System RAM use peaked at **15.60 of 15.71 GiB**; available memory
fell to **115.5 MiB** at 10:02:44 UTC during the producer reload for editorial.
That is severe system memory pressure, though RSS alone does not identify paging
or every allocation. No out-of-memory error occurred.

Process CPU peaked at 1,062.5% (about 10.6 logical CPUs), with a median of 94.8%
(about one CPU). System CPU peaked at 65.2%, median 16.4%. There is no evidence
of sustained saturation of all 20 logical CPUs. CPU execution rate varied:
Windows `% Processor Performance` was 59.1% of nominal overall at 09:55:59 UTC,
then 101.6% at 10:07:40. The installed counter definition was captured: this
measures performance while executing instructions, not an idle-weighted CPU-use
percentage. Snapshots cannot establish the cause or whole-run duration of that change.

Peak NVIDIA board VRAM was **7,691 MiB (7.51 GiB of 8 GiB)**. During generation,
producer GPU utilization had a median of 82% across 1,013 samples; auditor median
was 34% across 634 samples. Both reached 100%. Producer sampled VRAM peaked at
6,715 MiB, auditor at 7,691 MiB. The auditor's low weight allocation does not mean
low inference footprint: long-context generation approached the board limit.
These readings do not separately allocate KV cache, activations and driver memory.

Peak power was 116.7 W and temperature 87 C. Early producer work sustained high
GPU use with NVIDIA software thermal slowdown active at two snapshots, 08:56:56
and 09:03:45 UTC. Later work often ran around 20-45% utilization, P3/615 MHz and
35-50 W at 59-71 C; a later snapshot showed no thermal/power-cap slowdown flags.
During editorial generation, GPU activity recovered to about 90% and about 88 W.
The last legal follow-up took 501.8 s at the same 2,048 output cap as earlier
roughly 150 s calls. Prompt and host conditions also differed.

AC was connected, battery 100% at 09:24:42. A later process inventory found only
the owned benchmark as an NVIDIA compute process. Windows GPU memory counters
for that PID showed about 7,691 MiB dedicated and 82 MiB shared memory, which
does not support a claim of massive shared-memory spill at that snapshot.
Host CPU execution rate is a plausible contributor to later GPU underutilization;
the evidence is correlational. Do not attribute all slow periods to thermal
throttling, CPU fallback or another GPU workload. Desktop load was not controlled;
no other applications were inspected or closed, and no settings were changed.

## Non-generation work and caches

These are **inclusive consumer timings**, which overlap the partition above and
one another. They must not be added to generation as independent wall costs.

| Consumer | Calls | Inclusive time |
|---|---:|---:|
| Embedding encode | 35 | 55.422 s |
| Semantic ensemble decisions | 5 | 48.445 s |
| Embedding store queries | 19 | 7.987 s |
| New derived store build, 11 passages | 1 | 1.989 s |
| Generation tokenization / decode | 26 / 26 | 0.559 / 0.070 s |
| Embedding tokenization batches | 59 | 0.098 s |
| Convention parsing | 1 | 0.0019 s |
| Reference-index construction | 1 | 0.0031 s |
| Corpus loads / text extraction | 2 / 9 | 0.0015 / 0.0023 s |
| Pairing-map construction | 1 | 0.0026 s |
| Paired call planning / arithmetic checks | 1 / 22 | 0.1011 / 0.0080 s |
| Finding normalization / amendment construction | 3 / 1 | 0.00007 / 0.00013 s |
| Amendment deliverable writing | 1 | 0.244 s, including 0.241 s DOCX rendering |
| Ontology capture / graph / GNN update | 1 each | 0.019 / 0.035 / 0.215 s |
| `Path.read_text` / `Path.write_text` | 242 / 1,740 | 0.154 / 2.748 s |
| `json.dumps` / `json.loads` | 3,360 / 2,119 | 0.715 / 0.626 s |

The five semantic decisions contain 15 embedding encodes totaling 45.69 s.
Phase 0 includes one additional store encode, for 16 encodes and 47.44 s. Reference
embeddings are reused as model objects, but input embeddings are still repeatedly
computed. The five-voter semantics remain intact. A loaded model cache and a
cached encoded store are distinct mechanisms.

The baseline started with existing checkpoint files and an empty isolated derived
store. A separate post-run check exercised the actual saved-store consumer in
**0.143 s**, reusing all 11 passages with **zero model imports or loads** and an
unchanged cache hash. Forcing the stale decision independently reached the cold
import path and deliberately failed; restoring it reused the store again. This
proves the warm-store branch without a second expensive pipeline run. It does
not measure a fully warm second review.

All three models loaded from existing host snapshots with safetensors; no download,
conversion or cache clearing occurred. Snapshot identities were:

- Qwen: `bdd404162d94997f390efbfa660eb3f21cbbc81d`.
- Phi: `5c20803aa197416f43fb455e55c85178775320cb`.
- bge-m3: `5617a9f61b028005a4858fdac845db406aefb181`.

Reference indexing happened once and its index was saved twice. Corpus extraction
ran twice; repeated text extraction and parsing were cheap at this size. The
prior-comparison function ran only its empty-prior guard (0.00009 s), so it is
not a prior-version benchmark. GNN end-work used an isolated small graph; the
interactive candidate finder and a mature ontology were not exercised.
The process I/O counters increased by about 231.5 MiB read and 5.28 MiB written;
mapped model loads and OS cache behavior prevent interpreting that as physical
disk throughput. The 1,740 text writes include the existing peak sampler's
repeated writes, mostly overlapping generation. Disk I/O is not the dominant cost.
Docker and BuildKit did not participate in native startup; their caches were preserved.

## Serialized work and candidates for the next audit

All 26 actual generation intervals are non-overlapping. Boot convention/ensemble
work precedes production; six initial producers precede six legal follow-ups;
phase-5 verification precedes eleven pair reviews; synthesis precedes the board;
ontology capture, graph and GNN follow the review. The loader swaps producer to
auditor and back once. Current bus/context dependencies and the shared generation
cache make parallel model dispatch a behavioral change, not a free scheduling gain.

Immutable file parsing and independent rendering could theoretically overlap after
their inputs are fixed, as could telemetry, which already does. Measured parsing
and persistence outside inference are tiny. CPU embeddings might overlap only
where references and governance decisions are already fixed; CPU and RAM pressure
would need measurement. Placing bge-m3 on this GPU or retaining both generators
would have substantial memory risk given the 7.51 GiB observed peak. No overlap
or placement change was made.

| Rank / candidate | Likely impact | Diagnosis confidence | Implementation risk | Correctness / governance risk | Supporting measurement |
|---|---|---|---|---|---|
| 1. Audit generation beyond the selected structured envelope | High potential | High for discarded suffix; savings unmeasured | Medium | High | Clerk generated 8,192 tokens in 733.4 s; the accepted envelope ends after 112 retokenized tokens |
| 2. Explain host CPU/GPU clock and utilization variation | High potential | High observation, medium causal confidence | Medium | Low for measurement; settings changes need separate judgment | Auditor median GPU use 34%; CPU performance 59% then 102%; early thermal flags, later flags inactive |
| 3. Audit value and triggering of legal follow-ups | High conditional | High measured cost; redundancy unproven | Medium | High | Six follow-ups consumed 1,104.4 s; preserve policy and compare actual contribution |
| 4. Profile prompt prefill, accumulated context and memory | Medium potential | Medium | Medium | High | 9,243-token verifier prompt; auditor reaches 7.51 GiB; prefill/decode not separated |
| 5. Audit reuse of immutable ensemble/reference embeddings | Low for this baseline | High | Medium | Medium | All encoding totals 55.4 s, only 1.1% of wall; 35 encodes with shared model residency |
| 6. Avoid the producer reload if safe scheduling permits | Low | High | High | High | Only one 12.16 s reload; 23 resident generation hits already work |
| 7. Simplify repeated parsing, arithmetic or persistence | Very low | High at this size | Low to medium | Medium if deterministic coverage changes | Arithmetic 0.008 s, index 0.003 s; less than a second each of exclusive deterministic and I/O work |

The editorial finding was validated against the **actual contract map and the
saved runtime parsed result**, not merely a permissive replay. The real parser
selected the first populated valid balanced envelope: 1 item, ending at character
478 of 33,271. Its normalized result is identical when replaying only that prefix;
32,793 following characters do not reach the parsed result. Cached-tokenizer
retokenization gives 112 prefix tokens versus 8,192 full tokens, matching the
original generated count. No weights were loaded by this probe. Neutralizing
the selected wrapper changed the parser result; restoring it restored the result.

This is an output-consumption/coverage concern, not a timing-invalidating failure.
The board marked the recovered capped output `REVIEWED` and does not use the
generation's truncation flag as a success gate on this path. Forty-nine balanced
JSON candidates exist in the raw response, while only the first is consumed.
Later text may contain useful content or repetition; this diagnostic did not
classify it. A first complete envelope does not prove a complete review, and empty
wrappers must continue to be skipped. No exact seconds saved can be inferred:
time at the prefix boundary was not measured. No budget, stopping rule, parser or
board behavior was changed. The initial probe had the wrong contract-root mapping;
that fixture was corrected and required to match the saved runtime result before
this finding was accepted.

## Evidence, verification and closure

Machine-readable evidence is ignored under `output/local_performance/baseline/`:

- `events.jsonl`, `process_lifetime.json`: structural timeline, resource samples,
  actual consumers, native start/exit and guarded network events.
- `summary.json`, `spans.json`, `calls.json`, `inference_calls.json`,
  `reconciled.json`: phase/model/agent totals, non-overlapping partition, all joins,
  per-call budgets/tokens/devices and source/input preservation.
- `source_inventory.json`, `input_inventory.json`, `observed_workload.json`:
  before-run hashes and actual target/rule validity.
- `warm_store_result.json`, `editorial_prefix_result.json`: independently tested
  warm-cache reuse and actual output-consumer replay.
- Thermal, power, compute-process, Windows GPU memory and CPU performance
  snapshots, plus the installed CPU-counter definition.
- Existing `run/logs/cost_tracker.jsonl`, `call_evidence.jsonl`, and
  `run/audit/run_completion.json`, pairing and editorial artifacts remain the
  original pipeline evidence. Ordinary synthetic review artifacts contain their
  expected review text; the added diagnostic telemetry and report do not copy it.

The ignored helpers are `diagnostic.py`, `prepare.py`, `validate.py`, `analyze.py`,
`reconcile.py`, `wait_for_exit.py`, three fixture scripts and the two cache/parser
probes. `evidence_manifest.json` records local artifact hashes. They are retained
on this machine, not shipped or available in a fresh clone; use this report and
those exact artifacts for the next authorized comparison.

Instrumentation fixtures pass for real consumer effects, before/after outputs and
budgets, first-load/reuse, nested async spans, timestamp/call/phase attribution,
payload canaries, and neutralise/fail/restore/pass. The real Windows asyncio guard
fixture permits local IPC and rejects four external routes without saving addresses
or payloads. The post-run reducer fixture additionally covers failed generation
without tokens, unavailable GPU readings, interrupted dispatch, a trailing partial
JSONL record and overlapping-wall accounting. It exposed an ignored analyzer bug
that omitted a model when its generation failed inside an open dispatch; that
reducer was fixed and the fixture passes. It did not affect the completed baseline.
The recorded warm-store and corrected editorial-consumer proofs pass. A final
sandbox-only network-fixture invocation lacked the host `requests` dependency;
the host rerun used the existing installation. No package was installed.

All **128 staged runtime source files** and **3 synthetic input files** match
their initial hashes, including the isolated copied source. All **18 monitored
operator-state files** remain byte-identical, with no additions or missing files.
The provisional guard-failure attempt remains preserved separately. One metadata
HTTP API entry was intercepted in the successful baseline; local cache recovery
worked, with no provider dispatch or successful network egress. No paid API,
remote VM, private-document review or concurrent heavy GPU workload was used.

Not measured: truly cold download/OS disk cache, a fully warm repeated review,
human interaction latency, separate prefill/decode kernels, physical disk service
time, causality of clock changes, prior-version work, Sensitive/Draft, large or
mature ontology, and interactive candidate ranking. The laptop completed the run
without GPU failure, but throttling and clock variability limit repeatability.
README's historical clinical figure of 57.1 min is older code/conditions; it is
not a like-for-like comparison and establishes no speedup or regression here.

Tracked changes are this report, `RESUME.md` and the new `LEDGER.md` entry.
No shipped/runtime code changed, so the user-specified report-only exception
applies: **no new full host gate and no image rebuild were required or run**.
No README behavior debt was created. The previous startup host gate remains
256 PASS / 0 WARN / 2 SKIP / 0 FAIL, exit 0, as historical evidence only.
The unchanged `shimmer:startup` image is
`sha256:90ce701581520e4ec763d5d36d22d59f1120668200a76a820af156de0aca6356`;
its prior unmounted gate remains 246 PASS / 10 SKIP / 2 FAIL for absent intake
checks 28/31, exit 1. It was not relabeled green or retested for this item.

Entry `main` and local `origin/main` both resolved to `5b72b16c...`. This item
closes with a local documentation commit; no fetch, push or history rewrite.
Operator untracked handoff/durable state stays untracked. The locked roadmap is
unchanged; **Local speed-optimization audit** is next and has not started.

## Timing map from the current consumers

| Boundary | Actual consumer | Existing evidence | Diagnostic addition |
|---|---|---|---|
| Human startup | `start_shimmer.bat`, `desktop_launcher`, preflight, owned `desktop_server`, console, server `_run_job` | Readiness checks and job state | Trace only; benchmark starts at the local CLI wrapper |
| Local entry | `tools/run_local_demo.py`, `pipeline.main`, flag and environment both local | Wrapper wall clock, peak RSS and allocator VRAM | Native process wall clock and resource time series |
| Population and boot | `_populate_operational`, dating, role resolution, `_load_corpus`, orchestrator boot/adaptive spawn | Phase 0 and corpus counts | Nested consumer spans |
| Conventions and references | `parse_conventions`, assignment, `_build_reference_index`, `ReferenceIndex` | Rule/reference counts | Parsing, indexing and ensemble timings |
| Generation load | `agent_wrapper._load_qwen`, `_local_checkpoint_path`, tokenizer and causal model `from_pretrained` | Device, VRAM after load/eviction | First load, reload, resident reuse, tokenizer load, eviction |
| Embedding load/use | `embedding_store._load_model`, `_MODEL_CACHE`, `SentenceTransformer.encode`, `build_store`, `query_store` | Device, passage counts, store build/reuse messages | Load/reuse, encode, query and tokenization spans |
| Phase 1 | `orch.deliberation_round` | Progress and bus | Consumer timing |
| Phases 3-4 | `phase_3_4_content_production`, `_run_one`, optional legal deepening | Phase duration, progress, call evidence/cost | Joined call attribution and actual generation spans |
| Phase 5 | `phase_5_audit` | Phase duration, evidence/cost | Same |
| Phase 5.5 | `phase_5_5_convention_review`, `_paired_convention_review`, pairing map, `paired_review.plan_calls`/`compute_checks`, `_prior_comparison` | Phase duration, pairing plans/calls/refusals | Pairing, arithmetic, normalization and prior-path spans |
| Phase 6 | `phase_6_synthesis`, amendment construction, summary/render writers | Phase duration and deliverables | Construction versus rendering/persistence |
| Phase 6.5 | `phase_6_5_editorial_review`, `_dispatch_rank` | Phase duration, per-rank artifacts, evidence/cost | Per-rank model inference |
| Phases 7/9/8 and run end | Audit synthesis, conditional redaction, run summary, ontology capture/graph/GNN, completion | Phase events, cost totals, `run_completion.json` | End-work spans and terminal status |

Generation dispatch is `AgentWrapper.run_task -> dispatch -> call_local/call_qwen
-> _load_qwen -> tokenizer -> model.generate -> decode`. Cost duration includes
loading and generation, so it cannot alone separate those costs. Its call ID and
`call_evidence.jsonl` already provide structural attribution and will be reused.
The producer/auditor share a cache keyed by model ID, but loading another model
evicts the resident model. Tokenizers load alongside each new resident model.
Embedding instances have a separate cache; local profile deliberately puts bge-m3
on CPU. The semantic ensemble uses that same embedding loader. The GNN constructs
a small graph autoencoder and restores JSON weights if available. Draft's direct
provider dispatch and sensitive redactor prewarming are outside this Normal Review
baseline. No other generative load site is used by this path.

## Measurement design

Use the smallest shipped single-version reference/target corpus by eligible input
bytes: `clinical_reference`, three unchanged input files totaling 5,265 bytes.
The prior-version-specific `negotiation_r2_to_r3` is slightly smaller overall
(5,012 bytes in four files); this baseline instead exercises the standalone
reference-range/arithmetic path with a 1,088-byte target. Explicitly declare
`result_sheet.md` as the sole target and `analyte_reference_ranges.md` as grounding
with the existing role-manifest mechanism. Five shipped conventions remain intact.
No answer-key content is read, copied or scored. This covers arithmetic and
reference lookup with one target; it does not exercise prior-version changes,
sensitive redaction, Draft, or a mature ontology.

Run the existing local wrapper with host Python 3.9, local profile, default paired
mode, unchanged budgets, governance checks and scheduling. Use explicit Normal
declarations supported by the existing CLI. Stage only tracked runtime source and
the three benchmark files into a new ignored isolated root. Do not copy operator
input, durable assets, ontology, credentials, or `.env_path`. Existing host model
snapshots remain available and are not cleared. No Docker startup is involved.

Keep the diagnostic harness, its tests and all raw measurements under ignored
`output/local_performance/`. No shipped/runtime code changes are planned. The
harness wraps real consumers, records structural spans and joins existing call
IDs; it does not change inputs, output budgets, model selection or scheduling.
Sample host/process CPU, system RAM, RSS and NVIDIA board metrics every three
seconds. Bound telemetry to identifiers, counts, devices and timings. Reject
provider dispatch and count blocked HTTP/socket/DNS attempts without recording
addresses or payloads. Keep completed spans usable after interruption.

Distinguish nested inclusive timing from exclusive wall attribution. Report the
uncovered residual and sampling limits rather than calling all of it idle time.
Test consumer execution, attribution, timestamp ordering, aggregation, payload
exclusion and interrupted spans, including neutralise/fail/restore/pass proofs,
before the one measured baseline. No repetitions for averages and no optimizations.

## Instrumentation validation and measurement limits

The ignored fixture executes the real `AgentWrapper.dispatch` and `call_local`
consumers with tiny CPU tensors, before and after installing the hooks. Outputs,
token counts and budgets agree. The measured path distinguishes first load from
reuse and joins two distinct call IDs. Nested synchronous/asynchronous spans,
timestamp ordering, attribution failure, interrupted spans and payload canaries
are checked. Removing the hook leaves an independently observed consumer effect
without a timing span; restoring it restores both. Corrupting order or call
attribution fails validation, and restoring the original events passes.

A preliminary 62.2-second attempt reached no generation calls: the diagnostic's
initial external-network guard also rejected Windows asyncio's loopback socket
pair. Its complete trace, isolated root and original harness are preserved in
`output/local_performance/attempt_guard/`. This was a harness defect, not a
pipeline or GPU failure. The corrected guard passes an actual Windows asyncio
fixture, permits numeric-loopback IPC, and rejects external sockets, DNS and HTTP.
The baseline uses a new root and empty derived store; existing model caches remain.
The rerun is a corrected first baseline, not a repetition for an average.

One blocked Hugging Face metadata HTTP attempt occurred during the baseline's
embedding initialization, even with offline environment flags. The stack is
recorded as filenames/functions/line numbers only. The loader recovered from the
local cache. Thus this native run proves no successful egress, not zero attempted
requests. No provider dispatch or paid request is permitted. The prior image's
zero-attempt model probe remains a separate environment and a separate result.

Generation timing wraps the actual `model.generate` consumer and includes prompt
prefill. Output-token throughput is therefore end-to-end generation throughput,
not isolated decode throughput. No extra CUDA synchronization, warmup generation,
seed, scheduling change, shortened prompt or budget change is introduced.
Tokenizer and decode calls are separately timed. Model residency is observed by
cache hits/misses, load ordinals, actual devices, allocator readings and sampled
board VRAM. Board VRAM includes driver allocations and any other GPU processes.

Process CPU percentages use psutil's convention: 100% is one logical CPU. This
host has 20 logical CPUs. System memory includes other desktop applications;
process RSS is not total process commit and does not count all mapped/cache pages.
Three-second samples can miss short peaks. File-method timings include Python
overhead and OS cache effects; I/O counters are not physical disk service time.
Nested spans must not be added as independent wall costs. Uncovered residual time
cannot be labeled idle without further evidence. Instrumentation import/setup and
shutdown are kept visible. Interpreter startup before the recorder was 0.086 s;
an observer records native process exit separately.

The current laptop enters software thermal throttling during sustained producer
generation, confirmed by NVIDIA's active slowdown flag at 08:56:56 UTC. That is
an observed condition of this baseline, not a proposed runtime change. No machine
power, clock, cooling or timeout settings were changed.

## Dense quality-baseline addendum, 2026-09-13

This is a scoring addendum to the completed diagnostic, **not the start of Local
speed-optimization audit**. It uses the already-saved run
`758b17f33e6344f4902024e53d4b38e1`, 5,054.4 s and 26 calls. No pipeline rerun,
generation-model load, model generation, corpus staging or optimization occurred.
The operator explicitly authorized reading the committed answer key after the run.
No answer key, scorer, runtime source or historical artifact was changed.

### Provenance, preservation and commands

At addendum entry, main and origin/main both pointed to diagnostic closure
`0d2d152a1eb6d6dae0ccbe206253d7d465c543c2`; the operator had pushed it. The tracked
tree was clean; intentional untracked handoff/durable state was preserved.
All **54 artifacts covered by the existing closure manifest** still matched their
hashes, with none missing. That manifest did not individually cover every original
deliverable and bus file, so it cannot prove their entire pre-addendum history.
A new before/after inventory covers **275 files**, including the entire diagnostic
baseline tree, the key, scoring modules and operator state. All remain unchanged
during this addendum, with no additions or missing files in that inventory.

The working key was verified equal to its committed HEAD content after newline
normalization. Key LF-normalized SHA-256:
`309d3dba93907f5166da11c687f575c21c168dedab15cc30ec935532c68f2df8`.
Current `tools/score_corpus.py` SHA-256:
`00aa5e1a96d4f76f3bed5bf67c9ad3b78103836c1d87b81105dc1a531aedf215`.
The key has five planted entries, two clean results and **no typed `claim` on any
entry**. No claim was added after observing the run.

Commands from the repository root:

```powershell
py -3.9 -X utf8 tools/score_corpus.py --help
py -3.9 -B -X utf8 tools/score_corpus.py --corpus clinical_reference --run output/local_performance/baseline/run > output/quality_addendum/score_original.txt
py -3.9 -B -X utf8 output/quality_addendum/inspect_score.py > output/quality_addendum/inspection.txt
py -3.9 -B -X utf8 output/quality_addendum/snapshot.py --check
```

The scorer directly accepts the original run location. No relocated copy or path
patch was necessary. It exited 0, meaning scoring finished, not that quality passed.
The ignored inspection helper captures the current scorer's own result locals and
reproduces its original CLI output exactly, then reads saved evidence and applies
the existing typed-finding validator. It does not implement an alternative score.
No model-loading or pipeline-execution modules were imported by the helper.
`-B` prevents bytecode writes.

All artifacts required by this scorer exist and parse: completion, assignment,
pairing map, bus, call evidence and the document master. The reference index,
all six document deliverables including DOCX, the run summary, two contract dumps and editorial
artifacts also exist. Completion remains `completed`, `reached_end=true`, exit 0,
one document, three amendments. Complete artifact presence does not imply that
all necessary semantic evidence or assignment metadata was recorded.

### Automated results, unchanged current scorer

| Dimension | Dense baseline |
|---|---|
| Planted flaws | 5 |
| Raw/location recall | **3/5 (60%)**, location only |
| Bus evidence | 3 typed findings: two `above_band`, one `below_band` |
| Amendment evidence | 3 amendments; each independently matches a planted unit and operator rule |
| False positives | **0 amendments** on units unmatched to a planted entry |
| Clean items flagged | **0** amendments on RES-CEDAR or RES-DAMSON; 0/2 clean units flagged |
| Operator-rule attribution | **3/3 found entries**, all CONV-L01; 3/5 planted entries have an attributed hit |
| Asked recall | **Unavailable**, no resolvable `asked` entries; not 0% and not proof of no exposure |
| Review-state counts | `unknown=5`; `never_assigned=0`, `no_consumer=0`, `suspended=0`, `asked=0`, `assigned_not_asked=0` |
| Reason-confirmed / RIGHT PLACE WRONG REASON / reason-unverifiable counts | **Unavailable for this key**, not zero established cases |
| Master validator errors | 0 |
| Existing typed validator | 3/3 records pass with the saved registry IDs; structural validity only |

The scorer checks location and relation for bus matches; it also accepts an
amendment on the unit carrying the operator's rule ID. Here all three hits have
**both** forms of evidence, although the printed `matched via` column gives bus
precedence. Attribution is specifically the amendment's `source_convention_ref`,
not merely its generated CONV-001 registry ID. False-positive and clean-item counts
are amendment-based; they do not certify all generated or untyped bus prose.

| Planted entry | Operator rule / relation | Scorer outcome | Bus / amendment matches | Review state | Miss evidence class |
|---|---|---|---|---|---|
| RES-ALDER | CONV-L01 / `above_band` | Found, attributed | 1 / 1 | `unknown` | Not a miss |
| RES-BIRCH | CONV-L01 / `below_band` | Found, attributed | 1 / 1 | `unknown` | Not a miss |
| RES-ELDER | CONV-L01 / `above_band` | Found, attributed | 1 / 1 | `unknown` | Not a miss |
| RES-FIRTH | CONV-L02 / `missing_field` | Missed | 0 / 0 | `unknown` | `EVIDENCE_PRESENT_IN_MODEL_PAYLOAD` |
| sheet | CONV-L03 / `sum_mismatch` | Missed | 0 / 0 | `unknown` | `EVIDENCE_ABSENT_FROM_CORPUS` |

False-negative class totals: payload **1**, upstream-but-not-payload **0**,
absent-from-corpus **1**, UNKNOWN **0**. These are the original scorer results;
the qualifications below do not silently change either miss to a hit.

### Recorded exposure and false-negative mechanisms

All five saved assignment rows are `untagged`, with empty `consumer_agents`.
The current runtime has fallback routing for untagged rules, but the scorer
deliberately does not infer assigned consumers from unrelated calls or current
source. For the four result entries it therefore returns `unknown`; the sheet
entry additionally has no matching pairing-map unit. The zero counts for the other
states are counts of resolved labels, not proof of absent routing problems.

Call evidence nevertheless records rule-and-unit exposure, separately from that
assignment-based state: ALDER and BIRCH each have two focal and two neighboring
CONV-001 exposures; ELDER has two focal CONV-001 exposures. FIRTH is shown as the
following neighbor in ELDER's CONV-002 call
`557b1f5c45844b9abcba09b5151cb3f4`, an uncapped call with the rule rendered and
no recorded document/reference/convention clipping. That establishes the scorer's
payload class, **not a dedicated completeness judgment of FIRTH** or a proven
model reasoning failure. The narrow call's focal unit is ELDER.

FIRTH's saved unit fields omit `sample identifier`; the pairing map rejects its
CONV-002 pair with `unit lacks sample identifier`, precisely the missing field
that the planted completeness rule is meant to find. No computed or judged absence
was emitted. This is a coverage gap at the pairing/planning boundary despite
neighbor exposure, not evidence that the source lacked the relevant text.

The sheet's class needs an even stronger qualification. `fn_evidence.classify`
first matches the key's unit name against pairing-map unit IDs. None of the six
result-unit IDs contains `sheet`, so it returns `EVIDENCE_ABSENT_FROM_CORPUS`
before consulting other evidence. **The discrepancy is present in the supplied
source**: laboratory counts 4 + 3 = 7 versus declared total 6. REF-0018 preserves
those exact header lines, PROCESSOR accepted an extraction of them, and VERIFIER's
rejected raw output explicitly notices 7 versus 6. Thus this class describes a
missing parsed review unit on this path, not physical absence from the corpus or
a demonstrated faulty answer key. The classifier does not inspect source prose
or contract-failure text. Its original label is retained; no scorer fix or rescore
under a changed definition was performed.

Teaching the classifier about header/reference or rejected-response evidence would
change its evidence categories; it would not by itself create an accepted finding
or raise location recall. Inferring untagged fallback consumers would likewise
change review-state/asked-denominator semantics. Neither change is smuggled into
this baseline. The original results and the separate evidence qualification are
both retained for any later, explicitly scoped scorer work.

Coverage granularity also qualifies the earlier performance shorthand: the map
has 11 selected unit/rule pairs, 1 rejection and 18 undecided combinations. The
11 actual paired calls cover **8 distinct focal unit/rule combinations**, with
two CONV-001 calls each on ALDER, BIRCH and ELDER, and one CONV-002 call on each
of ALDER through ELDER. They are not 11 distinct pairs each receiving one call.
Zero `not_judged` and zero absence counts do not establish complete review coverage.
This addendum records that distinction without changing scheduling or call policy.

### Manual inspection, separate from automated scoring

All three typed findings and all three amendments were compared with the saved
target, supplied reference table and operator rules. These are source-level
observations, **not reason-confirmed scorer results**.

| Finding / amendment | Typed comparison and source check | Narrative inspection |
|---|---|---|
| ALDER | Sodium 148 mmol/L > upper bound 145 mmol/L; `above_band`, correct result and CONV-L01 | Correct figures and direction; no obvious source contradiction |
| BIRCH | Potassium 3.1 mmol/L < lower bound 3.5 mmol/L; `below_band`, correct result and CONV-L01 | **Incorrect prose:** calls 5.0 mmol/L the lower bound. The computed lead sentence and typed value_b correctly say 3.5 |
| ELDER | Total bilirubin 24 umol/L > upper bound 17 umol/L; `above_band`, correct result and CONV-L01 | Correct figures and direction; no obvious source contradiction |

All figures have matching units. All three `source_refs` and amendment `ref_ids`
resolve to REF-0007, the supplied reference-range table in
`analyte_reference_ranges.md`, which contains the actual supporting rows. The
typed unit IDs and original excerpts identify the correct target results.
DOCX comments 1/2/3 anchor to the corresponding ALDER/BIRCH/ELDER original excerpts.
The generic `location` field is the grounding REF-0007 for all three, so it is
not itself a unique target-location citation; target identity comes from the unit,
original excerpt and comment anchor. No dangling citation was found in these
three records. No patient diagnosis, prognosis or clinical interpretation is
asserted by their text; their `required` severity is the operator-rule priority.

The BIRCH contradiction survives into `review_data.json`, `review_findings.md`,
`reviewed_document.md`, `document_summary.md` and `tracked_changes.docx`'s
`word/comments.xml`. The source interval is 3.5 to 5.0: 5.0 is its upper bound.
Thus **3/3 typed comparisons are supported, but only 2/3 complete amendment
justifications are free of this observed bound error**. This manual finding does
not relabel BIRCH as automated RIGHT PLACE WRONG REASON; that metric is unavailable.

All scored records are posted with `backend=paired`, `model=python`, and their
amendments say `derived_from=computed_finding`. Their figures and relations are
computed; the model supplies explanatory prose. No scored hit exists solely as
a recovered or capped model finding. All paired model replies used recovery,
and one BIRCH CONV-001 reply hit its 768-token cap. The saved typed records do not
retain a one-to-one explanatory call ID, so attribution of the final BIRCH sentence
to the capped versus uncapped call is not established. Eleven advisory items are
explicitly withheld from bus findings by the existing projection, while their
call metadata and `items_withheld` counts remain recorded. Their full original
prose is not available there for retrospective quality certification.

Other accepted bus items are outside the scorer's typed-Finding definition.
LEGAL_ANALYST posted six broad findings and six follow-up items, including
unsupported assertions about conformity assessment, redress, post-market
monitoring, prohibitions and transparency obligations in this laboratory corpus.
One uncapped follow-up contains literal placeholder fields rather than analysis.
These do not appear as additional accepted amendments and are not counted in the
scorer's zero amendment false positives. FACT_CHECKER retained one capped,
recovered ALDER item, without a typed relation/figures. The capped recovered clerk
called the findings `sound` and praised accurate commentary, overlooking the
BIRCH contradiction. Its one observation is not independent quality certification.

### Contract and truncation qualifications

Of 26 model calls, **24 produced AGENT_OUTPUT through recovery**, not strict JSON
parsing, and **2 produced CONTRACT_VIOLATION**. ARCHIVIST, INST_FINDER and
SPEECH_ACT_TAGGER recovered empty envelopes. PROCESSOR recovered 21 extraction
items without hitting its cap, including the sheet-count header. Agent-contract
acceptance does not mean a typed Finding, substantive relevance or complete coverage.

CITATION_RESOLVER hit 2,048 tokens and left an incomplete JSON envelope containing
a growing citation list; no accepted citation-resolution output resulted. VERIFIER
hit 2,048 tokens and produced prose rather than the required canonical envelope.
Its dump includes the useful sheet-count discrepancy but also wrong relation
labels and false out-of-range assertions about clean CEDAR and DAMSON. The
contract refusal therefore lost potentially useful work **and** withheld erroneous
work. It is not safe evidence for accepting the raw output wholesale. Neither
its sheet observation nor its false clean-item assertions is promoted into the score.

| Capped agent | Capped calls | Output cap |
|---|---:|---:|
| ARCHIVIST | 1 | 4,096 |
| INST_FINDER | 1 | 2,048 |
| CITATION_RESOLVER | 1 | 2,048 |
| LEGAL_ANALYST | 5 of 7 | 2,048 |
| VERIFIER | 1 | 2,048 |
| FACT_CHECKER | 1 | 2,048 |
| PRACTICE_AUDITOR | 1 of 11 | 768 |
| EDITOR_CLERK | 1 | 8,192 |

Total capped calls remain **12/26**, with zero generation errors. The original
editorial state remains REVIEWED, one observation, no failed rank. No cap or
contract setting was altered during scoring.

### Quality invariant for the next locked item

This is the **dense quality baseline**, including its deficiencies and unknowns.
Speed alone cannot establish acceptance of an optimized-dense system.

| Dimension | Baseline and acceptance constraint |
|---|---|
| Recall / coverage of found defects | Retain the three named hits, not merely an interchangeable 3/5 aggregate; do not lose existing semantic coverage |
| Factual correctness | Preserve all three correct typed relations, figures and units; no new wrong claims. The BIRCH prose error is a known defect, not a behavior required to be retained |
| False-positive performance | No regression from zero unmatched/clean-unit amendments; inspect untyped and rejected outputs separately because this metric excludes them |
| Operator attribution | Preserve CONV-L01 on each existing hit, separately from CONV-001 registry identity |
| Grounding / citations | Preserve resolvable supporting ranges and correct target association, including rendered comment anchors; a citation count alone is insufficient |
| Amendment quality | Preserve supported ALDER/ELDER justifications and the correct typed BIRCH comparison; no degradation of action, figures, units, references or rendering |
| Contract validity | Do not trade accepted, useful consumer outputs for new contract failures or more incomplete output. Existing two violations and 12 caps are limitations, not quality goals |
| Review coverage | Preserve known rule/unit exposure and deterministic coverage; pair/call totals alone do not prove this. The five unknown assignment states and two misses remain explicit |
| Reason-level correctness / broader semantic coverage | Not established by this key. Future claims of preservation require adequate independent evidence; unmeasured never means preserved |

No new typed claims, benchmark definitions or runtime fixes were introduced to
make the baseline look better. The current scorer's unknown-state behavior and
parsed-unit-only absence classification remain documented limitations. Source-level
manual checks are bounded to this saved synthetic run; they are not a general
clinical, language or cross-corpus correctness evaluation.

New machine-readable analysis and logs are under ignored `output/quality_addendum/`:
`score_original.txt`, `score_verified.txt`, `quality_results.json`, `inspection.txt`,
`before.json`, `preservation.json` and the local read-only helper scripts. Original
diagnostic files remain untouched. Only this documentation, RESUME and a new LEDGER
entry change. No shipped/runtime or scorer change means no new full gate or image
rebuild; the existing startup image and historical gate results remain unchanged.
The addendum closes with a local documentation commit, never a push. The next
locked item is still **Local speed-optimization audit**, and it has not started.
