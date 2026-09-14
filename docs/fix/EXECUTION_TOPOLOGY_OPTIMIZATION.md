# Execution topology implementation, 2026-09-14

Baseline: `804afa57537a7d80b8df9622fc884fc065b4a4ba`. Implementation and
deterministic validation only. No provider call, cloud provisioning, model load,
GPU inference, or optimized benchmark was performed during this item. No push.
Multi-round remains inactive by default.

The scheduler and device-resident worker infrastructure are implemented. The
current local Review graph is deliberately conservative: **its semantic calls
remain chained by rolling-bus visibility**. This is a substantive limit on the
optimization, not evidence of a production concurrency speedup. Independent
fixture tasks overlap; no current semantic sequencing edge was removed.

The next locked item is **Optimized current-version cloud composite experiment**.
This does not rewrite the historical canonical roadmap or complete the earlier
cloud composite experiment. The preserved A100 evidence remains authoritative.

## Preserved evidence and entry

Entry was clean on main at 804afa5, matching the locally recorded origin/main.
The prior twelve commits and tracking state were inspected without a fetch.
Operator `SHIMMER_HANDOFF.md` and `durable/` were preserved. A separate validation
directory records hashes of all 325 prior smoke evidence files; none changed.

The A100 cold baseline remains 1,958 s native wall, 20 model calls, 1,920.789 s
generation (98.18%), median GPU utilization 41%, peak VRAM 8.23 GiB, and no
meaningful RAM/storage pressure. It used one A100-SXM4 40 GB, 30 vCPUs, advertised
200 GiB RAM at $1.99/hour. Model loading was only a few seconds. See
[the preserved smoke report](A100_CURRENT_VERSION_SMOKE.md) for accounting and
termination evidence; this item did not re-query Lambda.

Quality remains unverified: location recall 3/5, zero amendment false positives,
attribution 3/3, the typed/prose contradiction and source misattribution, and
VERIFIER/FACT_CHECKER contract failures are not fixed here. Five capped calls
remain baseline observations. No output budget, stopping rule, model, checkpoint,
precision policy, prompt, activation rule, or semantic judgment was reduced.

## Selecting a topology

`--execution-topology reference_serial` is the default. The preserved pipeline
function bodies remain in place behind no-op adapters. The name refers to the
local cloud-hosted baseline; historical provider-profile gather behavior is also
unchanged when this reference option is selected.

`--execution-topology dependency_dag` explicitly enables the new scheduler for
ordinary Review. `--topology-config config/execution_topology.example.json` supplies
lane capabilities. These are CLI options, not a server/UI activation change.
Backend profile and dense/sparse activation remain separate options. Draft and
multi-round combinations are rejected as unsupported by this adapter; the
multi-round implementation and its independent opt-in remain available in the
reference mode. No flag implicitly enables case positioning.

Use a fresh process for DAG execution. A live reference model cache is refused
rather than copied, evicted behind another run, or mixed with worker residency.
The sample enables only one primary CUDA device and a residency limit of one.
Secondary and remote-reserved auxiliary lanes are disabled.

## Dependency audit

`AgentWrapper.run_task` assembles context at call time. Both local producer and
auditor receive 500-token bus budgets. `_render_bus` incorporates recent messages
and counts older dropped traffic. Advisory paired replies also post receipts,
even when their items are withheld. Therefore even an empty/advisory result can
change the next prompt. Freezing the bus, omitting these receipts, or guessing
that a message will be irrelevant would change the semantic workload.

| Task boundary | Classification and reason to wait |
| --- | --- |
| Corpus producers | Semantic: each later call reads earlier bus traffic. Their results also build structural inventory. |
| Per-document producers | Structural inventory/reference inputs plus semantic rolling-bus dependency, including across documents. |
| Legal initial analysis to deepening | Conditional and semantic: follow-up existence, finding identity and retrieved references depend on accepted parent output. |
| Legal follow-up to next follow-up | Semantic: the same wrapper reads the bus after the previous call posts. Common parent does not establish independence. |
| PROCESSOR to VERIFIER/FACT_CHECKER | Structural and semantic: typed draft, source excerpts, availability notes and accumulated bus context. |
| VERIFIER to FACT_CHECKER | Semantic in the local reference order: the latter sees the earlier receipt, including a failure receipt. |
| Paired plans and polish | Conditional/structural routing and semantic rolling context; plan order, computed findings and advisory receipts remain unchanged. |
| Production/audit/convention review to synthesis | Barrier: complete results, latest revisions, absence/refusal records and governance state feed synthesis. |
| Synthesis to amendments/readable master | Barrier/structural: retain accepted finding identity, references and generation/merge order. |
| Master to editorial entry; rank to rank | Barrier, then conditional semantic escalation using accumulated lower-rank observations and governing authority. |

The concrete dynamic graph assigns `task-000000`, etc., in reference call order.
Every call after the first has a documented completion edge to its predecessor,
`rolling_bus_visibility_and_governance_order`. This transitive chain conservatively
contains the structural dependencies above. A completion edge allows existing
pipeline refusal handling to continue after a failed contract; it does not invent
an accepted finding. Success edges in the generic scheduler block descendants.
The existing phase barriers emit required-task lists and entry/exit state.
Initial extraction/boot and nonsemantic post-processing remain in the original
orchestrator. Inactive sensitivity/redaction paths were not executed or certified
as distributed work by this item.

Legal parent item IDs and task sequence are recorded in scheduler metadata, not
added to prompts. The existing deepening returned-result revision rewrite versus
bus-stamped ID gap is preserved and remains a known audit limitation. No legal
fan-out was authorized by the dependency audit. A future independent follow-up
can use common-parent success edges, as the fixture scheduler demonstrates, only
after its context independence is established.

## Scheduler and workers

`execution_scheduler.py` has a bounded ready admission (default 256 tasks),
explicit dependency reasons, stable task sequence, priority, dedicated one-thread
lanes and exactly-once admission. Duplicate/missing/cyclic or non-topological
identities are rejected before work starts. Oversized admission raises
`Backpressure` before accepting any task. Each lane has at most one submitted
action, so executor queues cannot grow without bound. No automatic retries.

Actions may overlap; accepted results commit through one coordinator in logical
sequence. Consumers wait for their required parents' committed results. Failed
commits block success-dependent children. An unrelated failure does not erase
other results. Synthetic fixtures prove concurrent execution and reduced wall
time with two workers compared with capacity one.

Cancellation is cooperative and drains running actions. Timeouts are measured
from assignment, not queue admission, and also drain before device reuse. Staged
commit callbacks never publish a cancelled/timed-out result. An arbitrary action
with its own side effects cannot be rolled back or forcibly killed by a Python
thread. The current pipeline adapter consequently configures no semantic task
timeouts and awaits the complete call transaction. Hard process termination still
leaves incomplete evidence, as before. Scheduler interruption drains all workers
and marks unfinished admissions interrupted. Worker shutdown occurs before the
outer completion recorder can mark the run completed.

`execution_topology.py` owns local residency by lane and explicit `cuda:N`/`cpu`
device. Loading is lazy on the dedicated worker thread; cache hits reuse the
model. `resident_limit` controls retained models, with eviction/reload evidence.
A single GPU and one resident at a time remain valid; retaining producer and
auditor together requires an explicit larger limit and measured headroom. Models
are task replicas, not tensor parallel shards. Global GPU-0 prewarming is disabled
in DAG mode. Runtime CUDA availability/index and memory are observed at loading.

Checkpoint loading remains local-only and uses the same safe path resolver.
Prequantized checkpoints retain their own compute dtype, without replacement
quantization options. The existing nonprequantized NF4/fp16/double-quant fallback
and CPU fp16 policy remain. Initialization failure marks the worker unhealthy;
no smaller model, precision fallback, provider fallback or automatic retry occurs.
Shutdown releases each cache on its owning thread and drains every executor.

Routing filters compatible model IDs, enabled/healthy lanes, required memory and
auxiliary eligibility; it ranks available lanes by explicit preference, family
affinity and residency. Busy lanes wait instead of accumulating executor work.
Model names and device capabilities come from configuration, never GPU marketing
names. Empty `models` permits any unchanged configured model; explicit allowlists
can isolate producer/auditor lanes. `memory_gib=0` means no declared capability,
not unlimited verified memory. Task memory requirements can be supplied by the
registry's optional `execution_memory_gib`; absent estimates remain unknown and
must not be presented as an OOM guarantee.

The optional `remote_reserved` transport is a disabled auxiliary boundary, not
an implemented network inference service. It is rejected if enabled. Main runtime
correctness requires no workstation CPU/RAM or remote auxiliary availability.
Actual remote transport, network synchronization and local GPU benefit remain
unverified; this implementation must not be described as a working two-node
deployment.

## CPU overlap and instrumentation

The generic scheduler supports independent CPU preparation on CPU lanes while a
GPU lane runs, and joins preparation plus semantic output before context assembly.
A barrier fixture proves that overlap. **The current Review adapter does not
precompute rolling context or overlap its mutable reference/registry consumers.**
No safe production preparation edge was removed in this item; CPU overlap here
is infrastructure validation, not a measured application speedup.

Per-run `audit/execution_topology.jsonl` records queue, ready, assignment,
task start/end, dispatch start/end, actual generation start/end, load/residency/
eviction/reload, device memory, phase barriers, commit and shutdown events. It
includes monotonic high-resolution and UTC time, task/agent/document/phase IDs,
parent finding, edge reasons, call ID at dispatch, queue depth, concurrent count,
dependency wait, scheduler wait and worker idle intervals. Payloads, prompts,
raw responses and credentials are never copied to topology telemetry.

`audit/execution_topology.json` reports the observed task-service-weighted longest
dependency path and terminal states. It excludes queue gaps and is explicitly
not a speedup estimator. Generation intervals permit separate generation path
analysis; phase entry/exit and task ready intervals expose barriers and CPU gaps.
Per-worker assigned intervals record idle time before each assignment; terminal
idle tails can be derived through the final shutdown timestamp. Existing Shimmer
call, cost, activation, bus and contract records remain independent and join by
call ID. External guest-agent/GPU samples remain supplemental.

## Adversarial race audit

| Surface | Decision |
| --- | --- |
| Append-only bus and recent context | Existing bus instance lock plus one current-run semantic writer; no concurrent live-bus context transactions. Generic independent results use coordinator commits. |
| Latest revisions/findings | Stable sequence at commit and existing `current_items`; reversed physical completion fixture proves one post per task and newest revision consumption. No deepening semantic rewrite. |
| Call-evidence JSONL | Remains a single writer in this adapter. No unnecessary global lock added. Concurrent independent integrations must stage this write or provide their own scoped writer. |
| Cost tracker | Existing tracker lock retained; same tracker and per-wrapper call IDs. Fixture joins actual cost/call/scheduler records. |
| Activation evidence | Existing audit lock retained; mutable per-wrapper observation is never concurrently reused. |
| Model caches | Worker-owned caches, one task per owning thread, no shared generation objects between lanes; no legacy cache mixing. |
| Registries/reference caches | Preparation and consumers keep reference order; no shared mutable registry is concurrently rewritten. |
| Synthesis/amendments/editorial | Original barrier, rank, escalation and merge bodies retained. Generic scheduler does not bypass these consumers. |
| File snapshots/run rename | Run-scoped coordinator writes; topology path rebound on existing run rename. No persistent open log handle crosses rename. |
| Contract failure artifacts | Isolated deterministic fix: DAG task ID appended to second-resolution filename. Reference names unchanged; fast same-agent failures cannot overwrite each other in DAG mode. |
| Completion/exceptions | Drain before completion; original call exceptions re-raised, error type only in scheduler log; shutdown failure test rejects a completed record. |

Independent actions that directly share arbitrary mutable files are not made safe
by this scheduler. Their API contract requires staged coordinator commits or
application-scoped synchronization. This is why live Shimmer semantic calls are
not submitted as an unjustified parallel batch.

## Validation and limits

Run `python scripts/execution_topology_no_generation_gate.py`. It blocks model/
provider imports and socket connections, uses only authored envelopes and fake
model objects, then runs the established safe gate. The full verification suite
contains model/GPU workloads and was deliberately not run.

Topology fixtures cover overlap, dependencies, barriers, failure/refusal and
unrelated success, ordered attribution/revisions, cancellation/timeouts/drain,
capacity one, synthetic speedup, model/family affinity, unavailable fallback,
single-device execution, memory filtering, health/initialization failure,
backpressure, duplicate/lost tasks, single bus posting, CPU overlap, loader device/
precision arguments, residency reuse, independent defaults and no-op protection.
The actual success-dependency predicate is neutralized, the unchanged oracle
fails, then restoration passes. An inert runtime adapter also fails its oracle.

The baseline fixture pins all 87 pipeline function AST hashes to 804afa5. Only
the explicitly enumerated decorators, CLI additions, rename hook and prewarm
guard are removed for comparison. The original pre-multi-round 47c63ac contract
still passes as well. Baselines were not regenerated from edited source.

Final safe gate: **49 PASS / 2 SKIP / 0 FAIL** (23 topology fixtures,
17 existing fixture tests, nine safe legacy checks). Skips: unavailable FastAPI
HTTP integration and optional local directory coverage. Log:
`output/execution_topology_validation/gate.txt`. Credential scan and whitespace
checks passed; all 325 prior smoke evidence hashes match.

Real CUDA loading/generation, substantive quality equivalence, <=120 seconds,
A100+A10 benefit, local RTX 3070 benefit, multi-GPU scaling, warm performance,
network transport and cost/run improvement are all **UNMEASURED / UNVERIFIED**.
With present bus dependencies, the semantic critical path can still equal the
sum of generation calls. The next experiment must report that limitation rather
than attribute a hypothetical parallel speedup to these fixtures.
