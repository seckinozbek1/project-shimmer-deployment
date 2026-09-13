# Local speed-optimization audit, 2026-09-13

Decision: retain the unchanged dense runtime. No candidate established a
deployment-worthy material speedup with the required quality and memory evidence.
The audit does not claim that a faster optimized-dense build was achieved.
No speculative runtime change is shipped. The fresh offline host gate passes;
baseline and operator preservation are verified. Closure is documentation only.

The operator explicitly allowed rejection of unsafe, unjustified or too-weak
optimizations. Consequently no expensive full pipeline comparison was justified:
there is no accepted candidate configuration to compare. The final dense
configuration is the baseline configuration, not a new measured faster build.
No new full-run wall time, phase deltas, quality score or speedup is invented.

## Decisions

| Candidate | Evidence and invariant | Decision |
| --- | --- | --- |
| First-envelope or repetition-only stopping | Real parser selects the same result while four distinct saved reviewer items disappear; preservation guard fails and restores | Reject, substantive loss despite parser equivalence |
| A: scoped inference mode | Both models' matched 192-token outputs and scores agree; timings and closer ABBA drift substantially | Reject as insufficiently established material gain; no full-response quality claim |
| B: one CPU intra-op thread | A/B and A+B preserve sampled outputs; no clear independent benefit; process-global thread state adds concurrency risk | Reject; no thread change shipped |
| C: expanded immutable weight scales | All 420 layers across both models dequantize identically; real consumer effect and no-op proofs pass; modest Qwen gain costs 389 MiB, Phi costs 216 MiB | Reject the deployment tradeoff, especially Phi's 7.87 GiB reserved VRAM; no numerical regression was observed |
| Legal batching or reordering | Live loop posts each response before the next context is assembled; retrieval and bus context vary | Reject a naive batch or reorder; preserving serial semantic dependencies remains mandatory |
| Prompt-prefix/KV reuse | Stable sections exist, but call-dependent context and cache lifetime must remain distinct; prefill is a small component in the sampled long-output workload | No implementation justified by measured material savings; no context removed |
| Static/quantized KV cache or alternate precision/kernel | Existing SDPA and last-token logits already active; static cache preallocates capacity, quantization/precision can alter arithmetic | Reject speculative changes under the memory and quality constraints; not generation-tested |
| Compiler-based execution | No Triton package was found in the installed host package inventory; new backend/toolchain and numerical validation would be needed | Not pursued; no package or driver change |
| Embedding/reference memoization | All encoding is only 55.4 s of 5,054.4 s; warm store already 0.143 s; reference rows recur in two semantic voters | Too little demonstrated end-to-end headroom for a new cache/invalidation and batch-numerics change; five voters unchanged |
| Model-load avoidance | Three actual loads total 34.4 s; 23 resident hits; avoiding editorial reload saves at most its 12.2 s before tradeoffs | Reject scheduling or dual-residency changes for weak savings |
| Tokenization, parser, deterministic Python and I/O caching | All generation tokenization 0.559 s; deterministic components similarly small | Reject as too weak for this objective |

These are individual decisions, not a blanket rollback. No runtime optimization
was committed or retained and then removed. A+B was measured separately from A
and B. C passed its causal work-removal proof but failed deployment acceptance;
combining that rejected memory tradeoff with A was not justified. No proof of
one candidate is used to certify another.

## Authoritative before and after

The authoritative baseline is the unchanged synthetic clinical_reference Normal
paired workload: 26 model calls, 5,054.4 seconds wall, 4,947.4 seconds generation.
The saved-run quality baseline is 3/5 location recall, zero amendment false
positives, zero clean-item flags and 3/3 operator attribution. Reason-level
scoring is unavailable. BIRCH's correct typed lower bound conflicts with its
rendered model prose. The two misses, two contract violations, 12 caps, 24
recovered accepted outputs and unmeasured quality dimensions remain qualifications.
See [LOCAL_PERFORMANCE_DIAGNOSTIC.md](LOCAL_PERFORMANCE_DIAGNOSTIC.md) for the
authoritative detail; neither evidence nor benchmark definitions may be changed.

| Metric | Authoritative dense baseline | Final audit state |
| --- | --- | --- |
| Workload | clinical_reference, one target, six units, five conventions, Normal paired Review | Same runtime/configuration; no new full run |
| Wall / generation | 5,054.4 / 4,947.4 s, 97.9% generation | No new comparable wall or generation measurement |
| Production / convention / verification / editorial | 38.73 / 16.49 / 15.55 / 12.43 min | No measured phase changes |
| Producer / auditor | 13 calls / 3,040.1 s; 13 calls / 1,907.3 s | Models, roles and firing policy unchanged |
| Input / output tokens | Qwen 55,137 / 33,787; Phi 91,844 / 7,055 | No new dense token totals |
| Median output throughput | Qwen 13.03; Phi 3.65 tokens per generation second | Component rates below are not replacement dense rates |
| Loads and reuse | Qwen 12.843 s first, 12.163 s reload; Phi 9.423 s first; 23 cache hits | Loader and eviction policy unchanged |
| Memory | 6.67 GiB peak process RSS; 115.5 MiB minimum available RAM; 7.51 GiB peak VRAM | New component memory observations only |
| Utilization | Producer GPU median 82%, auditor 34%; process CPU median 94.8%, system 16.4% | Host variability remains a confounder |
| Completion | Native exit 0, completed, reached_end true, 26 calls, three amendments | Original completion evidence preserved |
| Quality | ALDER/BIRCH/ELDER found; 3/5 location recall; 0 amendment FP; 0 clean flags; attribution 3/3 | Same saved-run evidence, no new quality result |

FIRTH remains an automated miss with EVIDENCE_PRESENT_IN_MODEL_PAYLOAD through
neighbor exposure. Sheet counts remain EVIDENCE_ABSENT_FROM_CORPUS in the scorer,
despite source/reference/PROCESSOR/rejected-VERIFIER evidence; this is the known
classifier limitation, not source absence. All five review states remain unknown,
so asked recall is unavailable. The key has no typed claims: reason-confirmed,
RIGHT PLACE WRONG REASON and reason-unverifiable metrics remain unavailable.

The three accepted comparisons have correct units, figures, operator IDs,
reference-table support and DOCX anchors. BIRCH's model prose still names 5.0 as
the lower bound while its typed/computed bound is 3.5. The mismatch was inspected
at the model-explanation consumer and retained as a defect, not corrected with
handcrafted semantic rules or counted as a speedup. Rejected verifier reasoning
includes both the real sheet discrepancy and false clean-item claims. Nothing
is promoted from rejected output into a scorer hit. Caps/recovery remain risk
indicators, not proof of substantive correctness.

## Saved editorial suffix

`output/dense_optimization/replay_suffix.py` executes the current balanced-JSON
scanner and actual EDITOR_CLERK contract against the saved response. It validates
49 envelopes with six distinct normalized contents. Forty-three are duplicates;
the suffix is not exclusively repetition. Later envelopes introduce a potassium
concern, raise it to serious_concern, combine it with other observations, and
contradict earlier judgments. Some notice an inconsistency but propose the wrong
bound. Parser selection of the first valid populated envelope does not establish
substantive completion. First-envelope stopping is rejected: it would discard
distinct reviewer reasoning. No stopping or budget change was implemented.

`prove_suffix_rejection.py` independently inventories five distinct valid items;
the first envelope retains one. Neutralizing the preservation guard's input to
that prefix loses four, makes the check fail, and restores/pass. A parser-only
observation remains identical, so effect_proof refuses it as NO_OBSERVED_EFFECT.
A distinct saved judgment placed after a duplicate prefix is still discovered.
Empty-wrapper skipping and skipping a candidate missing required rationale also
pass through the real parser; neither behavior was weakened.
This is a rejection proof, not an accepted stopping implementation.
The alternate envelopes are an inventory of saved raw reasoning, not five
accepted board items. The existing parser selects only the first populated
valid envelope; this audit does not change that selection or promote the rest.

## Runtime screening

Installed host versions remain torch 2.5.1+cu121, transformers 4.52.3 and
bitsandbytes 0.48.2. The unchanged cached configurations select bfloat16 4-bit
compute. Qwen samples; Phi uses greedy decoding. Both request KV caching.
Transformers already sets logits_to_keep=1 for supporting models. Initial Phi
inspection reports SDPA attention and float16 non-quantized parameters. No
alternate kernel, precision, checkpoint or model has been selected.

Candidate A is scoped inference_mode in place of no_grad, to reduce inference
bookkeeping. Candidate B is scoped intra-op thread count during CUDA generation,
to test CPU overhead; any global-thread interaction risk must be resolved before
shipping. Screening uses matched seeds, token IDs and processed-score hashes,
reversed trial order, synchronized prefill/decode timing and resource sampling.
These are component probes, not quality acceptance or a dense speedup claim.

An initial setup attempt used the wrong contract-map level and was stopped;
`attempt_contract_phi*` is retained but excluded. The corrected synthetic VERIFIER
probe used the actual contract and returned EOS after three tokens in all trials.
All token IDs and processed scores matched. This short output cannot establish
decode throughput. Follow-up work reconstructs the saved verifier task through
the current phase and context consumers, keeping prompt text in memory only.

The first reconstruction omitted dispatch's two-newline separator. Its 64-token
trials are screening only, retained as `probe_phi_saved*`. Version 2 invokes real
dispatch and matches baseline prompt-section lengths and input token counts:
VERIFIER 25,956 characters / 9,243 tokens; EDITOR_CLERK 14,876 / 4,096. Original
prompt bytes were not persisted, so size/token parity alone is not a claim of
independently verified byte identity with the historic prompt. A/B prompts are
byte-identical to each other and their hashes are recorded.

Each model's eight version-2 trials produces identical 192-token sequences and
processed-score hashes across baseline, inference, one thread and both variants.
Phi baseline wall rises 18.910 to 24.140 seconds; Qwen 17.421 to 25.599 seconds.
Those 27.7% and 46.9% drifts dominate small candidate differences. Both probes
reach 87 C and median GPU utilization 92%, unlike the historic auditor median
34%. A read-only snapshot explicitly reports software thermal slowdown active,
P0/675 MHz, 92% utilization and 65.71 W. CPU performance was 103.2% of nominal
at another snapshot. These are observations, not a proof of the earlier low
CPU clock's cause or a software speedup. A closer inference-mode ABBA gives Qwen
walls of 17.480 / 16.840 / 18.374 / 22.240 s, then 24.242 / 24.749 / 26.283 /
27.805 s (baseline / inference / inference / baseline). It does not supply a
stable material benefit. In the second quartet inference's mean wall is only
about 1.9% below the two bracketing baselines, within continuing host drift.
All sequences and processed scores still match. A/B invariance is limited to
these generated prefixes; it does not certify complete editorial reasoning.

The 24-token Qwen CPU/CUDA profile attributes 18.0% of self CPU time to
bitsandbytes::dequantize_blockwise, with 4,704 calls. This includes prefill and
has profiler overhead; it is not an 18% end-to-end savings estimate. Installed
gemv_4bit and dequantize_4bit expand the same nested weight scales each call.
Candidate C reuses their exact float32 expanded scales in a temporary in-memory
quantization-state view. Quantized weights, codebook, block size, compute dtype
and all model tasks remain identical in the component test. Extra VRAM, state
lifetime, restoration, consumer counts and exact output equality were measured.
No checkpoint is rewritten and no library package is patched on disk.

## Scale-cache ablation and rejection

`scale_candidate.py` prepares shallow state views with exactly the float32
scales that the installed native consumers compute. It keeps original states
and restores their identities after each trial and an injected exception.
Every dequantized matrix matches bit-for-bit: 196 Qwen and 224 Phi layers.
Preparation including this comparison takes 0.432 / 0.242 seconds respectively.
New persistent experiment allocations are 407,830,528 / 226,492,416 bytes.

`scale_proof_qwen.json` and `scale_proof_phi.json` execute a real Linear4bit
consumer: baseline optimized observation has zero scale expansions, neutralized
observation has one, output hashes remain identical, the check fails, then
restoration returns zero and passes. A no-op neutralizer is explicitly refused
as NO_OBSERVED_EFFECT. This proves work elimination, not a material wall gain.

| Matched 192-token trials, seconds | Baseline before | Cache A | Cache B | Baseline after |
| --- | ---: | ---: | ---: | ---: |
| Qwen first quartet | 17.373 | 18.306 | 23.127 | 26.856 |
| Qwen later quartet | 26.986 | 26.214 | 26.224 | 27.799 |
| Phi quartet | 24.362 | 24.961 | 30.023 | 35.396 |

All token IDs and processed scores match within each model. Qwen's 37,632 and
Phi's 43,008 expansions per trial become zero. The later Qwen quartet's mean
wall improves 4.28%, decode 5.53%, relative to the bracketing baselines; this is
a small component signal, not an 84-minute-run speedup. Its memory cost is
388.94 MiB. A producer-only deployment was considered but not retained for
this weak demonstrated dense contribution and added memory/lifetime complexity.

Phi adds 216 MiB. PyTorch peak reserved memory is 7.873 GiB, and sampled device
use reaches 8,009 MiB of 8,192 MiB. No OOM occurred, but this leaves little
headroom before proving full-length outputs and the dense workload. Its large
baseline drift prevents a trustworthy causal time estimate. Qwen's scale probe
sampled device use reaches 7,015 MiB; minimum available host RAM during that
probe, including load, is 0.507 GiB (Phi 3.593 GiB). Short successful inference
is not a guarantee of safe dense peak memory. The memory price and weak or
uncertain speed evidence justify rejection without spending a full run.

Both baseline and cache trial arms retain the prepared scales in memory so
their residency is controlled. The additional-allocation numbers above, rather
than an equal arm-to-arm peak, express the cost versus the unmodified runtime.
No full-response quality regression is alleged, and no full-response quality
preservation is claimed. Rejection is a deployment decision, not a failed
numerical-equivalence test.

## Other execution paths and remaining uncertainty

Legal deepening remains six independent calls in the baseline, 1,104.4 seconds.
The current loop retrieves per-finding references, builds an independent payload,
awaits its call, and posts to the bus before the next call. Stable agent context
can repeat, while retrieval and recent bus context vary. Batching cannot assume
the calls are independent of prior bus updates; it would need to preserve that
dependency as well as per-task attribution, contracts and recovery. Suppression,
budget cuts and activation changes are outside this audit.

All tokenization across 26 calls cost 0.559 seconds in the diagnostic. Parsing,
rendering and deterministic work are similarly small. Model-load avoidance has
limited headroom (34.4 seconds total); the resident cache already works. Embedding
work is secondary at 55.4 seconds, with warm store reuse already proved. No
speculative changes have been made to these paths.

The installed dynamic cache concatenates growing K/V tensors each step. The
shape-derived fp16 cache size is 393,216 bytes/token for Phi, about 3.385 GiB at
9,243 tokens, versus Qwen's 57,344 bytes/token. This explains a substantial
portion of context memory, not all transient allocation or clock variation.
StaticCache allocates maximum capacity up front in the installed implementation;
it was not substituted speculatively near this device's limit. Quantizing cache
or changing dtype would add numerical-quality risk. Qwen's profile gives all
aten::cat operations only 0.78% of self CPU time; that profile cannot establish
Phi's cache-copy fraction. No unsupported cross-model extrapolation is made.

SDPA is already selected for both actual loaded models. Last-token logits and
native EOS stopping already work. Replacing kernels or changing precision was
not tested or accepted. The profiler also shows tensor copies/conversions and
prefill matrix multiplication; removing those by dtype changes would change
arithmetic, unlike exact scale reuse. No deterministic substitute for substantive
model judgment is introduced.

The five-voter encoder still batches candidate/reference rows. Reference-only
memoization would need identity/version/normalization and batch-numerics proofs,
not simply fewer model calls. Given the total 1.1% wall ceiling for all encoding,
no such cache was shipped. The existing warm-store effect proof remains valid.

Observed thermal flags, 87 C temperatures and clocks as low as 510 MHz establish
thermal limitation during inspected intervals. They do not establish the cause
of every slow interval, historical CPU-performance variation, scheduler behavior
or residual time. CPU process utilization near one core does not alone prove
CPU submission was the sole bottleneck. The unmodified Phi probe can reach
92% median GPU utilization while the full historic run had 34%; that difference
is not attributable to software changes. No power, clock, BIOS, firmware, driver
or TDR setting was altered.

## Operational evidence

All new evidence is ignored under `output/dense_optimization/`. Original baseline
and quality manifests were verified, including the 275-file operator/baseline
snapshot. One GPU workload runs at a time; probes forbid network requests and use
only shipped synthetic material. No provider call, hardware change or push.
Runtime source remains unchanged. The same registry, contracts, models, budgets,
legal deepening, convention routing, editorial escalation, attribution and
five-voter consumers are preserved by source/config hash parity. This is source
preservation, not a claim that fresh model judgments were evaluated end to end.
The baseline's source/figures/units/citations/anchors and governance evidence
remain intact. Short probe cap counts are experimental lengths, not new dense
contract-violation or truncation metrics.

No private operator document, provider or paid API call, VM or remote execution
was used. Representative generation-probe logs record zero blocked network
attempts. The original diagnostic's one blocked metadata attempt remains part
of its immutable history. All new instrumentation and experimental mutations
live in ignored output files; no third-party installation was changed.

Read-only/adversarial review caught the two probe-setup issues above and excluded
their results from representative evidence. It also rejected parser equivalence
as semantic completeness, separated causal work removal from speed acceptance,
and checked the cache memory tradeoff and sampled-prefix quality limitation.

Fresh offline host gate: **254 PASS, 0 WARN, 4 SKIP, 0 FAIL/ERROR, TOTAL 258**,
native exit **0**. Skips are optional local directories (01), live DDG (15), cold
embedding download (38), and missing contamination fixture (145). That last skip
cannot rule out contamination. The prior startup image remains unchanged, with
its previously recorded unmounted result of 246 PASS, 0 WARN, 10 SKIP and two
missing-input FAILs (28/31), exit 1. No new image run is claimed.

The audit manifest freezes 36 representative 192-token A/B trials, consumer
proofs, profiler and host evidence. Original diagnostic/quality manifests,
275 baseline/operator files and 399 source/state files match. The canonical
roadmap block matches its pre-audit text. All probe/gate processes exited.
Closure is the local commit titled `Record local speed optimization audit and rejected candidates`;
its hash is reported in the operator handoff after commit. No image
rebuild or README behavior correction is owed for this documentation-only result.
There is no final optimized-dense run to score; re-scoring the unchanged baseline
would not create new evidence of optimization. The canonical roadmap is untouched.
The operator-directed next locked handoff is **Conditional agent activation &
sparse routing audit**. It has not begun. Nothing is pushed; the operator pushes.
