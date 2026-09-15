# Report Recommendations implementation

Local implementation and bounded evidence, 15 September 2026.
Starting source: `69dce11`. The current item explicitly supersedes the older
locked-roadmap handoff. Operator-owned untracked `SHIMMER_HANDOFF.md` and
`durable/` were preserved.

The bounded inference continuation after `f3e8424` / `ec276cb` is recorded in
section 14. It supersedes the earlier OpenMP blocker: a verified process-local
repair works, but producer loading reached the RAM guard and the standalone
auditor returned incomplete output at its time limit. Status remains
`LOCAL_TARGET_INDETERMINATE`.

## 1. Starting evidence

The recovered 14 September run used `15d0721fbc24cd38fdaa6bc4969d7b18ad66387e`,
ordinary Review, DAG selection, one CUDA worker and two resident models.
Its original controller remains ABORTED/NON-BENCHMARK. Recovery and termination
were independently verified in the preserved records. No historical record was
rewritten or promoted into a clean benchmark.

Observed cold wall was 2413.046 s, native wall 2408.265 s and generation
2378.756 s (98.58% of cold wall). The preserved baseline wall was 1958 s;
the recovered run was about 23% slower. All 20 calls returned, but only 16
outputs were accepted. ARCHIVIST, VERIFIER, FACT_CHECKER and EDITOR_CLERK violated
contracts. Eighteen calls contacted their caps, compared with five previously.
The semantic critical path traversed all 20 tasks, with 2384.658 s service time
and measured maximum concurrency one. Median GPU use was about 40%, peak
sampled VRAM 12.86 GiB, scheduler/barrier waits zero, dependency wait about zero,
and worker idle 23.254 s.

Three amendments, location recall 3/5 and no observed false positives or
distractor hits do not establish semantic quality equivalence. Setup took
1213.562 s to first generation, including 1122.506 s transfer/integrity/dependency
preparation and 44.995 s model hydration. The 5.30 GB upload dominated setup.
The approximately $2.20 instance estimate is not steady-state inference cost.

Sources are the recovered JSON/JSONL under
`output/cloud_collected/a100_optimized_retry_20260914`, current source,
README, runtime reference, handoff, topology report and the research conclusions
quoted in the operator task. No separate Deep Research report/source attachment
was found in the supplied attachments or repository. No external research or
provider access was substituted for that missing source.

## 2. Root causes actually established

* `Runtime.attach` held a lock across a complete call and submitted singleton
  scheduler batches. Every admission also depended on the preceding call.
  The gather adapter awaited local work in order. Adding idle lanes alone could
  not expose overlap.
* Recent bus receipts affected subsequent prompts, even for empty or failed
  responses. This was a real prompt dependency, but several sibling consumers
  had no typed-result dependency on one another.
* PROCESSOR generated source text again in `draft_text`. The local 8192 allowance
  did not solve this repeated output or prove completeness.
* Both local inference paths tokenized raw prompts without native instruction
  chat templates. This is proved from the loader, not a measured explanation of
  all observed errors.
* The old cap test incorrectly asserted that EOS always precedes the cap.
  EOS on the last allowed token is now distinguished from a length stop.
* Existing paired findings already contain Python's numbers, attribution and
  a deterministic explanation renderer. An unconditional, cited, computed
  numeric defect need not ask a model to restate that comparison.

The change from 5 to 18 cap contacts has no isolated causal ablation. New briefs,
response repetition, raw-template behavior, payload differences and model EOS
behavior remain hypotheses. New prompt hashes, native-template flags, finish
reasons, cap contact and acceptance evidence make a later bounded A/B probe
possible. Matching location recall is not used as evidence of equivalence.

## 3. Architecture changes made

`report_optimized` is an explicit local ordinary-Review topology. Reference serial
and the earlier DAG remain available. The optimized path is not made the default
before real-model quality validation. It rejects Draft, multi-round and provider
profiles. It checks cached model configuration to establish different producer
and auditor model families, without loading weights or changing model choices.

The live path now has:

1. A lossless source ledger that reuses `pairing_map.split_units` identity/index
   and adds exact offsets for all text, including preambles and table surrounds.
   Blank separators attach to the preceding span. Full content hashes and
   runtime-owned span item IDs avoid cross-partition supersession collisions.
2. Bounded PROCESSOR requests, up to four spans of 1200 characters per request.
   The model returns short offset aliases instead of copying source text. Python
   reconstructs `draft_text` exactly, while claims, questions, uncertainty,
   extraction method and supplied references remain semantic output.
3. Complete ownership checks, source-order merge and conflicting-duplicate
   refusal. Context-only neighbours cannot become owned extraction. Exact
   duplicate items coalesce; missing spans refuse the partition. A valid empty
   extraction response to nonempty owned source remains incomplete, not success.
4. At most one retry of each technically failed partition. Successful partitions
   are not regenerated. Empty/refusal-shaped responses are not retried as a
   strategy for obtaining agreement. No whole-document retry or JSON continuation.
5. Explicit sibling waves for corpus producers, per-document producers, the
   draft-audit pair and independent paired questions. Every sibling sees the same
   initial bus snapshot. All receipts, including refusals, publish in logical
   order after the wave drains. Dedicated existing workers still own models.
6. Exact, unconditional, cited numeric-comparison plans use the existing Python
   finding and reason renderer. Conditional, uncomputable and semantic absence
   judgments retain model review. This is typed-proof eligibility, not a word list.
7. Native local chat templates on the optimized path. Existing model families,
   checkpoint choices, quantization and governance checks remain in place.
8. A four-entry in-memory cache of immutable deterministic ledgers, keyed by the
   entire source, document identity and partition bound. No semantic conclusion
   is reused across runs or rounds. The recorded input fingerprint is explicitly
   not a complete semantic-cache reuse key.

Synthesis and amendment rendering were already substantially deterministic.
No extra synthesis generation was introduced. Human-facing reasons remain.
Audit-only institutional and citation obligations were retained, not discarded
because a deliverable lacks a direct reader. Editorial rank escalation and legal
deepening remain conditional; no rank is pre-run for speed.

The common observation file is `logs/generation_observation.jsonl`. It separates
backend success, response completeness, contract validity and accepted semantic
output. It records IDs, counts, requested/actual tokens, stop reason, cap contact,
generation/call wall, retry, native template use, prompt hash, wave/lane and
resource-event linkage. Useful token attribution and TTFT remain null when not
measured. Contract validity is not claimed as semantic truth. Concurrent call
ledger appends now have a write lock. An optimized incomplete semantic result
prevents `run_completion.json` from claiming completed, even after output writing.

## 4. Call graph before and after

[dependency_graph.json](report_recommendations/dependency_graph.json) classifies
every recovered call, consumer, required field class and predecessor edge.
It contains an explicit scheduling counterfactual, not a fabricated optimized run.

| Shape for the recovered single-document task | Calls | Semantic waves |
|---|---:|---:|
| Historical observed chain | 20 | 20 |
| Same calls, new sibling grouping only | 20 | 5 |
| Actual optimized path, before retries | 19 + P - C | 5, plus conditional work |

P is the number of bounded PROCESSOR partitions and C the number of proven
eligible exact-comparison calls removed. Both depend on the actual input and
planner; neither is inferred from the benchmark answer key. Initial legal
findings can add deepening waves. Editorial escalation can add rank waves.
Multiple documents retain ordered phase traversal, so five is not a universal
whole-run upper bound. The historical run had no legal deepening.

The five groups are corpus analysis, document production, draft audits, paired
review and editorial entry after deterministic synthesis. Corpus inventory to
its consumers, PROCESSOR to its auditors, parent finding to deepening, complete
findings to synthesis, and rank to conditional escalation remain serial. Sibling
receipt-only edges are removed. The phase-5 to phase-5.5 boundary still preserves
completed audit visibility and ordered reference/coverage preparation; it is a
conservative remaining boundary, not a required typed finding input to every
paired question. This pass does not claim a fully validated 2-to-4-wave system.

## 5. Truncation and output result

On an authored four-span fixture containing 2218 source characters, the cached
producer tokenizer measured 620 tokens for the source-copying envelope and 221
for the compact wire envelope, a 64.4% reduction. Runtime reconstruction retained
all 2218 characters exactly and all four items. These are output tokenization
measurements, not model-generated responses or quality scores.

The 1536-token partition ceiling is provisional capacity for at most four compact
items. The measured empty-question wire needs 221 tokens; the remainder permits
semantic fields. Richer claims/questions may still saturate it. The implementation
refuses incomplete work and records it; it does not assert that all attempted
model calls now have zero truncation. Other call-family budgets are unchanged.
No 12000/16000-token ceiling was introduced.

The mechanism fixture deliberately injects one capped partition and proves only
that partition retries, accepted partitions survive, and merged source order is
exact. All accepted fixture partitions are complete. Malformed, unknown-complete,
missing-span and conflicting results cannot become complete extraction.
Schema validation and native templates are implemented; grammar-constrained
sampling is not claimed. There was no safe installed-stack generation experiment
that justified adding a constrained-decoding dependency.

## 6. Short-burst measurements

[probe.json](report_recommendations/probe.json) stores exact measurements and
resource boundary samples. Ledger/reconstruction took less than 1 ms on this
fixture. Four injected 30 ms calls took about 123 ms at concurrency one, 62 ms at
two, and 32 ms at four. These timings demonstrate fixture scheduling only.
They measure single-burst wall as well as per-call latency and throughput.
The adapter stops escalation on output mismatch, unknown equivalence, resource
pressure or latency regression. It does not submit the shared Transformers model
from concurrent threads.

GPU boundary samples were idle with no model VRAM. The probe process used about
35 MiB RSS; available system RAM was approximately 3.8 GiB at these samples.
Boundary samples are not a sustained-load peak guarantee. See the artifact for
CPU/system RAM samples. No model load, swap, decode duration or real GPU scaling
is inferred from this fixture.

A separate minimal host-Python import probe failed with duplicate OpenMP runtime
initialization, Error 15, before model loading. The alternate Python 3.9 virtual
environment lacks Transformers and tokenizers. No unsupported duplicate-runtime
override, environment rebuild, download or CPU inference fallback was used.
Real generation, TTFT, real contract rates and semantic quality are unmeasured.

## 7. Full-run projection

[projection.json](report_recommendations/projection.json) explicitly reports
PROJECTION_NOT_BENCHMARK and null local wall/critical-path duration. Missing
measurements include representative real call latencies, safe model concurrency,
deterministic full-input stage times, cold/warm load times and retry overhead.
Current `input/context` and `input/operational` contain no selected review
workload, so a new ordinary call count is also not asserted.

The deterministic projection engine supports an explicit DAG, latency ranges,
capacity, warm/cold overheads and retry cost. It rejects cycles, missing parents,
duplicate IDs and invalid ranges. It reports calls, waves, critical path,
truncation/refusal inputs, resources, assumptions and uncertainty. Unknown
measurements never silently become zero. The input artifact can be populated
from a later bounded model probe without invoking the pipeline.

With the recovered A100 generation times held unchanged, the sibling-wave
counterfactual gives about 2379 s at capacity one, 1696 s at two, and 1547 s at
four, excluding setup and CPU overhead. Those are diagnostic-service simulations,
not local projections and not hardware measurements. Sum-of-event generation
intervals differ from the recovered summary by about 0.007 s because their timing
boundaries differ; neither source was altered. PROCESSOR and editorial decoding
remain dominant. Scheduling alone does not approach 120 seconds.

## 8. Local target assessment

**LOCAL_TARGET_INDETERMINATE**

The source/contract mechanisms pass and bounded CPU work is small. However,
<10-minute local wall, model memory pressure, zero attempted-call truncation and
near-perfect semantic quality cannot be established from tokenization and
synthetic service times. The real inference environment must first initialize
safely, followed by bounded semantic A/B tests. A full local run remains a later,
explicitly authorized validation step.

## 9. Eventual 120-second / $0.10 path

This implementation removes repeated source decoding, eligible comparison prose
calls and several sibling ordering edges. It supplies an A/B path instead of a
serving-engine migration. The unchanged-time counterfactual rejects scheduling
alone as a sufficient solution. Real native-template and compact-extraction
quality/latency measurements must determine the remaining generation reduction.

The worker/dispatch boundary and injected short-burst harness allow later serving
adapters to be measured. Continuous batching, prefix/KV reuse, chunked prefill,
Paged/Radix attention, CUDA graphs and speculative decoding remain secondary
hypotheses. Aggregate throughput is not a single-run latency claim. No vLLM,
SGLang or TensorRT stack was installed. Existing prequantized checkpoints were
retained; this task did not choose a new 4-bit policy. A future 24 GB-class device
is a candidate, not a selected or proven topology.

The cost function separates marginal and fully loaded accepted-run cost,
provisioning, preparation, inference, idle/teardown and storage/network assumptions.
At the supplied $1.99/hour, 120 billed seconds are about $0.0663 before overhead.
That arithmetic establishes neither acceptance probability nor feasibility.

`tools/prepare_source_layer.py` produces a content-addressed source-layer manifest
and changed-file list against a prior manifest. This checkout has about 4.21 MB
of selected source files, excluding dependencies and runtime configuration.
It excludes models, wheels,
operator data, runtime configuration and credentials. It is not a complete
standalone deployment package. Existing Docker dependency/weight-before-source
ordering is retained. Source-only updates over prebuilt layers and prepositioned,
pinned model caches are the later deployment path; no image was rebuilt or sent.

## 10. Quality and governance assessment

The ordinary safe gate passed 49 checks, with one optional-directory skip and no
failures. It includes 17 new mechanism checks, 23 existing topology checks and nine
safe legacy checks. Fifteen explicit mutation trials each failed their unchanged
assertion under neutralization and passed after restoration, with no execution
errors or uninvoked mutations. Two further checks use the repository effect-proof
protocol directly. [validation.json](report_recommendations/validation.json) and
[mutations.json](report_recommendations/mutations.json) record the scope.

Directly tested: lossless source coverage and order, unit identity, duplicate and
context exclusion, selective retry, complete/valid distinctions, native-template
wiring and EOS-at-cap using fake model objects, different-family configuration,
immutable-cache invalidation, deterministic numeric reason/claim/citation/rule
fields, ordered bus publication including refusals, actual worker overlap,
incomplete-run status, and projection arithmetic. Existing scheduler failure,
barrier, residency and dependency tests pass. Original pinned reference-function
hashes still pass after reversing only the named optimized adapters; historical
baselines were not regenerated from edited code.

Not established: semantic recall/precision, reason correctness for arbitrary model
outputs, near-perfect quality, whole-workload equivalence, real refusal frequency,
real zero truncation, GPU concurrency or end-to-end privacy certification. No
benchmark key contents were opened. Constitution, privacy rules, role authority,
model selection and editorial decisions were not weakened or amended. Human
reasoning and audit-only obligations were not dropped to improve a score.

The full legacy verification gate contains model-loading checks and was not run.
The safe subset avoids multi-round execution. Image rebuild/runtime image parity
also remains untested in this strictly local source pass.

## 11. Cloud work deliberately not performed

No cloud instance, cloud query, paid API, provider inference, full cloud test,
remote deployment, benchmark promotion or push. No full pipeline run, complete
model run or multi-round model run. Historical recovery and termination records
were read locally, not re-queried remotely.

## 12. Decisions made autonomously

* Preserve reference defaults: semantic equivalence is not yet measured.
* Retain roles and escalation: reducing audit depth would violate the task.
* Use aliases with exact reconstruction: avoid generating text Python owns.
* Keep complete span coverage mandatory: missing extraction must stay visible.
* Freeze sibling context and order posts: expose concurrency without races in
  shared findings or accidental completion-order provenance.
* Keep one residency owner per CUDA device: no unsafe model duplication on 8 GiB.
* Restrict deterministic bypass to typed, unconditional, cited numeric proofs:
  semantics and conditional requirements still need judgment.
* Keep bounded budgets and one partition retry: prevent giant ceilings/retry storms.
* Leave real-model probing unavailable after reproducible initialization failure:
  no unsafe OpenMP override or unbounded environment repair.
* Implement deterministic reuse only: no stale semantic cache or multi-round change.
* Retain the two flagged synthetic test strings: no live credential was established.

## 13. Unresolved evidence and next validation

The inference environment must initialize safely before the representative
native-template/source-span A/B probe, independent audit quality fixture and
GPU concurrency/residency measurement can run. Those missing measurements are
explicit projection inputs. Broader output bounding for other call families,
the remaining cross-phase boundary and serving acceleration require those
quality/latency observations before default promotion. No final latency, cost or
near-perfect quality target is claimed by this implementation report.

## 14. Local inference environment and bounded real-model continuation

### Root cause and safe runtime selection

The host is Conda CPython 3.12.3. Its PyTorch directory is mixed: Conda records
PyTorch 2.5.1 CUDA 11.8, while `torch-2.7.0.dist-info` and bundled Intel OpenMP
DLLs not owned by the Conda PyTorch package are also present. Torch-only import
reproduces OpenMP Error 15, including with `-I` and a minimal PATH. NumPy or
scikit-learn import is therefore not necessary to trigger this failure.
Tracing finds the bundled `torch/lib/libiomp5md.dll` loaded before failure in
`torch._C`; PE imports show `torch_cpu.dll` depends on Conda MKL threading and
Intel OpenMP. The bundled and Conda DLLs have different SHA-256 hashes, retained
in `report_recommendations/local_inference/summary.json`. The precise installation
history is unknown; no claim is made about which installer last changed it.

The exact repair is process-local selection of the existing pristine Conda
PyTorch package cache ahead of host site-packages, before importing torch.
`tools/local_inference_runtime.py` verifies all 12,500 torch package files against
the cache manifest, refuses ambiguous records or duplicate-runtime suppression,
and sets two CPU threads and offline flags. The full inference import stack then
loads exactly one Intel runtime, `anaconda3/Library/bin/libiomp5md.dll`. CPU and
CUDA matrix arithmetic checks pass. A standalone integrity check took 49.12 s;
this is startup verification overhead, not model generation time.

The authoritative runtime for these probes is host Python plus this verified
Conda PyTorch 2.5.1 overlay. Host Transformers 4.51.3, NumPy 1.26.4,
scikit-learn 1.5.1, bitsandbytes 0.49.2 and accelerate 1.13.0 remain installed
unchanged. `.venv` uses Python 3.9.13 and lacks Transformers/tokenizers, so it was
not selected. Normal unmodified host `import torch` is still broken: this is an
explicit safe launch path, not a global package repair. Cache removal or an
integrity mismatch fails closed. No DLL was deleted, replaced or suppressed;
no dependency, model, wheel or environment was downloaded or rebuilt.

### Executed probes and resource admission

The harness calls the real `agent_wrapper._load_qwen` and `AgentWrapper.call_local`.
It blocks socket connections, uses only an authored 139-character fixture,
limits each generation to 384 new tokens and 25 seconds, and supervises its own
child process. Two consecutive samples below 1.25 GiB available RAM, 85 C GPU
temperature, or a phase timeout terminate that child. Model generation is greedy
with seed 7 in this harness; this is not an A/B result for production defaults.
Resource samples are approximately once per second plus sensor latency, not
instantaneous peaks. Process CPU percentages use psutil's one-core basis.

| Probe | Measured result | Admission / quality result |
|---|---|---|
| Configured Qwen producer initialization | Stopped during load; 23.76 s sampled load interval; 2,805.9 MiB peak sampled process RSS; 3,559 MiB sampled VRAM; 1.152 GiB minimum available RAM | RAM guard; initialization not proved; no producer generation |
| Configured Phi auditor initialization | Real loader succeeded on CUDA; process-first loads 27.80 s and 26.69 s; model allocation 2,167.6 MiB | At most one resident model; no producer/auditor co-residency |
| First standalone auditor call | Backend generation returned; output recording then failed on a harness attribute error | Output/tokens/finish reason unavailable; not counted as a successful semantic probe |
| Corrected standalone native-template auditor | 25.37 s call wall, 25.35 s generation, 1,887 input / 68 output tokens, requested 384 | Incomplete JSON at the 25 s time budget; contract failed; no accepted semantic output |
| PROCESSOR monolithic vs compact | Not executed | Producer load RAM guard |
| Raw prompt vs native template | Not executed as an A/B | One native auditor call is not evidence of template improvement |
| Producer to independent auditor | Not executed | Auditor input was authored, not generated by Qwen |
| Concurrency | One auditor call at a time only | 2 and 4 not admitted after resource and output-validity failures |

The corrected auditor generation sampled up to 3,629 MiB total GPU memory,
968.9 MiB process RSS, 100% GPU utilization, 62 C GPU temperature, 39.1% system
CPU, and 101.5% process CPU (about one core). Available RAM stayed at least
3.579 GiB during that generation. Loading the auditor was more RAM-intensive:
2,749.4 MiB sampled RSS and 1.950 GiB minimum available RAM in the repeat.
These are phase-local samples, not a full-run resource envelope or sustained-load
certificate. There were no duplicate model copies. The auditor was loaded twice
only because the first harness recording failed; no producer reload was attempted
under insufficient headroom. No operator or operating-system process was stopped.

### Output inspection and truncation

The corrected output ends inside the `confidence` string and contains no complete
item, judgment, reasoning or evidence citation. Contract validation reports
`no JSON object found in output`. Semantic completeness and acceptance fail;
typed-claim and reason correctness cannot be assessed from this unfinished item.
There is no completed refusal to assess. Rule attribution is not applicable to
this source-fidelity fixture. No location-recall score was used.

The token cap was not contacted. The raw backend telemetry honestly records
`finish_reason=unknown` and `truncated=null`, since its existing EOS/count logic
does not label a time stop. Separately, fixture review records observed incomplete
output at the harness's 25-second bound as time-budget truncation. This must not
be reported as zero truncation. The first instrumentation-failed output is unknown.
No real PROCESSOR source reconstruction or semantic extraction result was obtained.

Configured model IDs remain unchanged. Their cached configs identify `qwen2`
and `llama` respectively (the latter belongs to the configured Phi-named
checkpoint). This proves distinct configured model types, not an executed
cross-family producer/auditor verification path or independent lineage audit.

### Projection and next evidence

The existing projection input now carries measured resource evidence and the
failed resource gate. Full-run wall-clock range, generation time, critical path,
truncation count, retry overhead and warm/cold totals remain null. An unfinished
139-character auditor fixture cannot supply latency estimates for all ordinary
roles. The graph still describes the historical 20-call, five-wave scenario;
actual call count depends on `19 + P - C`, retries and conditional work, where P
is the PROCESSOR partition count and C is eligible deterministic comparison work.
No unspecified input's call count is invented. Projection code now returns a null
critical path when latency inputs are missing instead of an arbitrary tied path.

Status: **LOCAL_TARGET_INDETERMINATE**. Neither <10 minutes, modest full-run
resources, zero expected truncation nor semantic equivalence is established.
The next measured blocker is producer-load RAM headroom; the next observed
generation problem is incomplete auditor output within the short time budget.
No broad refactor or speculative serving optimization is justified by these data.
Next work requires a quiet local memory baseline sufficient for guarded producer
loading, then a complete bounded semantic fixture before concurrency escalation.
Do not raise the safety limits merely to obtain a passing result.

Validation: eight new offline checks cover verified runtime selection, tamper and
ambiguity refusal, suppression refusal, import ordering, real CallResult recording
and unknown critical-path behavior. The ordinary no-generation gate passes
49 checks with one optional skip. Raw probe/resource evidence and a separate
quality review are under `report_recommendations/local_inference/`.
No cloud, paid API, remote deployment, full pipeline/model run, multi-round run,
benchmark answer-key access or push occurred.


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
