# Final model integration and telemetry

## Pre-change integration map (38bc131)

Recorded before implementation, from executable source:

* `pipeline._resolve_local_models` maps local roles to base repository IDs from
  `config/local_models.json`; absent/unreadable configuration falls back to the
  full precision IDs. `_build_wrapper` constructs the governed agent wrapper.
* `AgentWrapper.call_local` calls `_load_qwen`. Both `_load_qwen` and the separate
  `execution_topology.resident_model` loader instantiate AutoModelForCausalLM.
  Neither loads a PEFT adapter, classification head or normalization. Thus no
  step120, clean head, Trial11, or final896 classifier is currently wired here.
* `phase_3_4_content_production` returns PROCESSOR envelopes. Optimized waves
  partition source spans, bind `compact_contracts.producer`, hydrate source and
  merge complete partitions. The reference path retains its existing envelope.
* `phase_5_audit` looks up PROCESSOR by document and agent, rejects failed drafts,
  removes prose through `_typed_for_agent`, and passes source plus typed draft to
  VERIFIER and FACT_CHECKER. VERIFIER currently generates relation labels as part
  of findings. There is no ordinary four-way classifier invocation to replace.
* `AgentWrapper.run_task` performs activation/governance, dispatch, parsing,
  contract validation and bus posting. `compact_contracts.auditor` requires a
  relation **and** selected source refs, reasoning, severity and confidence.
  A four-way prediction alone cannot satisfy that contract or semantic refusal.
* `pipeline._items_for` selects successful envelopes and current item revisions;
  synthesis consumes these findings. Paired convention review has separate typed
  arithmetic/evidence gates; editorial and strategic auditors have other tasks.
  Those tasks must not be redirected into a four-way fidelity classifier.
* `generation_observation.observe` records wrapper timing/token/acceptance data.
  `call_evidence` records structural source identifiers. The scheduler records
  admission, dependencies, lane assignment, dispatch/generation/load intervals.
  Its existing critical-path summary explicitly excludes queue gaps. Completion
  and cost records are separate; no unified full-run resource summary exists.

## Finding and status

`FINAL_MODELS_INTEGRATED_TELEMETRY_READY`

The operator-approved pairing contract resolves the blocker from `093afce`.
Auditor896 now runs on explicit Producer-item/source pairs and supplies advisory
typed context to ordinary VERIFIER. VERIFIER retains its rich finding contract,
independent judgments, zero/one/multiple findings, and refusal behavior. There is
no equality gate and no classifier-label broadcast to findings.

See [Auditor pairing contract](AUDITOR_PAIRING_CONTRACT.md) for the source-level
bridge, fixtures, effect proofs and current validation. Readiness means the
implementation and deterministic gates pass; no real model or cloud performance
claim is made. The next full cloud run requires separate authorization.

## Producer168 integration

`AgentWrapper.call_local` selects `final_models.resident('producer', ...)` when
`SHIMMER_MODEL_MODE=final` is explicitly requested. It verifies the configured base
ID, the frozen adapter/config bytes, all pinned base assets and the pinned runtime.
Loader failure returns the existing backend failure; it never invokes the base
loader as recovery. A mocked dispatch test proves selection and absence of fallback.
The loader uses the existing lane residency budget, or the reference resident cache,
and exposes model/revision/checkpoint/hash/engine metadata.

The default is explicitly recorded `base` mode. Ordinary pipeline startup with
`SHIMMER_MODEL_MODE=final` verifies the artifact set, pinned runtime and executable pairing-contract
self-check, then admits ordinary Review. Thus this commit does not misrepresent an ordinary base
run as tuned, or admit a Producer-only approximation of the requested final pair.
No Producer prompt, generation budget or typed extraction semantics was changed.
Producer168 did not pass every historical V3 quality gate; its use here follows the
operator's frozen selection, not a new quality or performance claim.

## Auditor896 preparation and preserved admission

`final_models.load('auditor', device)` is the pair-scoped final-mode inference loader.
It binds the canonical LlamaForCausalLM base (despite the repository's Phi name),
NF4/BF16/eager execution, PEFT classifier_fork, saved FP32 head and fixed FP32
mean/std. It prepares the k-bit base as in final evaluation, freezes parameters,
uses eval mode, disables checkpointing for inference, disables the classifier
cache, and compares the immutable base-state hash using the existing FrozenAudit.
It performs no fitting or normalization-statistic computation.

`Classifier.predict` requires exact hidden shape, finite final-token vector,
finite normalized features and finite four-way logits. Mutation/numerical failure
latches admission closed. Available failing hidden vectors and a structural receipt
are retained under the supplied failure directory. The original TRAIN historical
feature admission implementation is unchanged. Old step120 TRAIN feature hashes
are not falsely used as an oracle for checkpoint896 on new inputs.

The loader has not been exercised with real model weights. CPU tests use a fake
backbone and small synthetic tensors only. The advisory ordinary integration is separately proven by mocked live-wrapper
fixtures; a classifier label never substitutes for the rich finding contract. Trial11,120,448 and mixed
head/normalization identities are rejected, including altered descriptor hashes.
There is no implicit checkpoint448 debug fallback.

## Exact artifact identities

`config/final_models.json` records relative paths, every base asset digest, pinned
revisions and runtime versions. Runtime code also binds the selected artifact
hashes, so editing a descriptor to Trial11/448 does not approve it.

| Artifact | SHA-256 |
| --- | --- |
| Producer168 adapter | `8354d6545272399ea6771f1a6b560309e882fd7348f5c2be9cbd1bab01160703` |
| Producer adapter config | `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507` |
| Auditor896 adapter | `0ec8212f5288e5960f1e816d93c9c7e1206eed7c380b45cf355ae0825ecc1b5e` |
| Auditor config | `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6` |
| Auditor head | `6a2fcf89d3e843d5364443c20add30f0542e9dfbf00ff3b0e4d78ede397fdc3a` |
| Mean | `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5` |
| Std | `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a` |

Producer base revision: `bdd404162d94997f390efbfa660eb3f21cbbc81d`;
weight: `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`.
Auditor base revision: `5c20803aa197416f43fb455e55c85178775320cb`;
weight: `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a`;
prepared state: `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18`.

The shared historical runtime is Python3.12.3, Torch2.5.1+cu121, CUDA12.1,
Transformers4.51.3, PEFT0.15.2 and bitsandbytes0.48.2, with remaining exact package
versions in the descriptor. `CUBLAS_WORKSPACE_CONFIG=:4096:8` must precede startup.
Base-path relocation may use `SHIMMER_PRODUCER_BASE_PATH` and
`SHIMMER_AUDITOR_BASE_PATH`; relocation never waives hashes. Otherwise resolution
uses the exact revision from the local Hub cache, without downloading.

## Known limitations retained

**Auditor896 external macro F1 is approximately 0.8010; historical macro F1 is
approximately 0.4576; historical OMISSION recall is 1/12.** Quality gates did not
all pass. This remains in runtime artifact metadata and belongs to the
post-roadmap optimization backlog. No tuning cycle, new score or performance
improvement is claimed. Historical HPO values remain provenance only: LoRA peak
LR1.2943234833221302e-6, headLR0.0009721418411547451, warmup10, dropout0.05.

## Raw telemetry schema and integration

Schema1 `logs/model_telemetry.jsonl` is the new common payload-free event path.
Existing generation observations, structural call evidence and scheduler evidence
are retained for compatibility. Raw events include pipeline start/end, model-call
receipts, backend invocations, generation intervals, physical backend receipts,
retention snapshots, resource samples and prepared frozen model lifecycle events.

Wrapper receipts include run/call/task/wave/agent/role/backend/model identities;
selected adapter/head/normalization identities when applicable; backend start/end,
completion and service duration; reported input/output budgets, stop/truncation,
prefill-inclusive generation throughput; transport success, contract validity,
observable completeness, emitted counts and failure category. Missing measurements
are null with reasons. EOS is not semantic completeness. TTFT and decode-only time
remain unknown on non-streaming generation. Physical fallback receipts have 1ms
resolution because the existing backend duration counter is integer milliseconds.

`_items_for` emits current-revision retention snapshots without changing returned
items; repeated reads replace counts rather than add them. Retention here means
retained by that consumer, **not necessarily included in the final deliverable**.
Advisory/computed findings and merged partition attribution still need their own
end-to-end consumer receipts before a comprehensive final-finding total is claimed.
Embedding-store and ensemble encodes use the same path with counts only, no text.
Embedding tokens, pinned revision and non-scheduler phase attribution remain unknown.

## Producer-to-Auditor coordination and critical path

Phase5 wrappers carry the Producer call ID or partition call IDs. Call receipts
join to scheduler task IDs and explicit dependency reasons. Handoff is child
service start minus parent service end; it is elapsed handoff, not an assertion
that all of it was caused by that parent. Scheduler ready/assigned events retain
separate dependency and resource waits. Explicit lane-order edges are added during
summary derivation so serialized residency is not mistaken for parallel capacity.

The summarizer follows the latest-finishing prerequisite and records service and
inter-node gaps separately. It returns path membership and role service on that
observed path, not a counterfactual speedup from removing a role. Interval unions
avoid double-counting parallel calls; per-agent/service totals intentionally retain
all work. Synthetic serial, parallel and gapped DAGs verify the distinction.

**Remaining coverage limit:** scheduler DAGs cover admitted tasks, not every CPU
operation or embedding dependency outside those tasks. The summary is an observed
semantic-task path, not a fully instrumented causal graph for the entire pipeline.
Reference-serial runs lacking scheduler events report that path as unavailable.
The pair bridge now records both handoffs, an explicit context-ready barrier,
per-wave intervals, and downstream phase consumer dependencies. The summary reports
observed completion-to-consumer gaps and path service separately; it does not infer
counterfactual avoidable wait or assign every CPU operation to a model.

## Resources, cost and derived summary

RunCompletion starts/stops a lightweight 2-second sampler. It records psutil
process/system CPU, RSS, RAM availability/usage and swap; nvidia-smi device identity,
utilization, used VRAM and power when available; and already-initialized Torch
allocated/reserved bytes. It does not import Torch or initialize CUDA. Unsupported
counters remain null. GPU samples retain per-device values; a multi-device aggregate
utilization scalar is not invented. Peaks/medians are sampled values, not continuous
maxima. Model loads/residency and scheduler activity use existing events. No sampler
performance benchmark was run; overhead remains unmeasured.

Derived `audit/model_telemetry_summary.json` is separate and recomputable:

```powershell
python scripts/model_telemetry.py <saved-run-directory>
```

It reports measured pipeline wall time, call/generation interval unions, process
CPU time, scheduler phase/task path, service totals, concurrency, handoffs, reported
tokens, truncations, contract and failure counts, measured retention, resource
statistics and available lifecycle/cost evidence. Process CPU time includes native
inference/telemetry and is **not** mislabeled deterministic non-model CPU time.
Unknown categories stay unknown, with measured-call counts on partial totals.

For infrastructure estimates, supply raw `audit/infrastructure_cost.jsonl` records
with event=`infrastructure_cost`, provider, instance_type, hourly_rate,
active_start_epoch and active_end_epoch. This commit does not provision or produce
those provider facts. Cost is elapsed seconds times rate divided by3600. Existing
`logs/cost_tracker.jsonl` supplies model/API estimates. Categories are separate;
combined cost is null if a category is missing (explicit zero is required for a
known zero). These are estimates, never invoices. No provider rate is hardcoded.

## Deterministic validation and effect proofs

`python scripts/final_integration_no_generation_gate.py`: 104 unittest checks pass,
plus the existing ordinary activation effect-proof suite. Model/provider imports
are blocked; Windows asyncio's local wakeup socketpair is permitted while external
connections are denied. The unused ontology-GNN module is stubbed for importing
ordinary phase fixtures. No model workload or multi-round gate is chained.

The checks cover actual frozen artifact hashes, requested Producer loader selection,
missing/wrong/mixed artifacts, checkpoint substitution refusal, the demonstrated
ordinary contract gap, untouched compact contracts, source identity, activation,
dense/sparse parity, truncation versus transport/contract success, retention,
DAG overlap/gaps/concurrency, cost conversion and recomputation.

Seven load-bearing controls pass neutralize/fail/restore/pass: frozen checkpoint
validation, interval-union accounting, valid pair-contract startup admission, source
ownership, stale revision exclusion, no-guess behavior, and no label broadcast.
See `final_model_integration/validation.json` and `no_generation_tests.log`.
Historical reference function AST hashes remain pinned: the comparison removes
only the explicitly named telemetry additions and final-mode admission block,
then compares against the existing historical hashes; no semantic baseline was
replaced to make the gate pass.

`.venv/Scripts/python.exe scripts/final_classifier_cpu_checks.py -v`: three tests
pass using Torch CPU tensors and a fake backbone: class order/final-token path,
shape/nonfinite/normalization stop with evidence preservation and sticky refusal,
and frozen-state mutation admission. No checkpoint is loaded. Python3.10 cannot
parse an existing PEP701 f-string in the broader runtime, so the broad suite uses
Python3.12; the isolated tensor tests use the CPU-only3.10 environment. Initial
gate failures from blocking Windows asyncio's self-pipe and unrecognized telemetry
AST additions were corrected in the harness without weakening production rules.

## Documentation changed

This report and `config/final_models.json` document the new prepared boundary.
Historical Producer/Auditor training reports remain unchanged: their scores and
runtime results describe past evaluation, not a future tuned ordinary run.

## Exact next action and stop boundary

Await separate authorization for the instrumented ordinary pre-multi-round full
cloud run. The former generic integration blocker is removed. Missing or mixed
artifacts, invalid runtime, and malformed pairing integration still fail startup.
No cloud resource, real model workload, protected test, training, HPO, multi-round,
performance benchmark, deployment, packaging or push was performed in this task.
The implementation, report and deterministic evidence are committed locally.
