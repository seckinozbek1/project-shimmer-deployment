# Current-version Lambda A100 smoke, 2026-09-14

One cold synthetic Review completed. The A100 environment is usable, but this is
not the requested 10-20-run composite baseline, a warm SLO result, or broad quality
equivalence. Do not launch the A10 on this evidence. No multi-round workload ran.
The current-version cloud composite item remains incomplete; the later multi-round
cloud experiment and final minimum remote specification remain unstarted.

## Source, workload and isolation

Source: `d15b544e02de3b9530d96d5627a37cd754a92201`, main, initially matching the
locally recorded origin/main. Pre-multi-round behavioral baseline:
`47c63aca09603ab5c7ad662753d647397a623ce8`. No fetch or push occurred.
Only selected tracked runtime/configuration/support files, synthetic fixtures and
the preserved diagnostic observer were hydrated. Existing operator inputs,
`SHIMMER_HANDOFF.md`, `durable/`, ontology state and prior local evidence were not
copied or modified. The remote project used fresh experiment-only state.

The unchanged `clinical_reference` corpus has one target, `result_sheet.md`,
grounding in `analyte_reference_ranges.md`, five declared conventions and six units.
The explicit operator target/grounding manifest matches the local diagnostic.
The held-out key was used only by the scorer after execution, not placed in input.

Launch defaults were made explicit in the copied diagnostic observer:

```text
--backend-profile local --activation-profile dense --review-mode paired
--task review --non-interactive --skip-confirmation
--sensitivity-layer-inactive-override --no-redaction-override
```

`--output-dir` and `--sample-file` identify the isolated run and memory evidence.
Here Local means the current local-model backend running on the remote A100,
not commercial model-provider APIs. Prompts, models, generation settings,
governance, ordinary routing and semantic responsibilities were unchanged.
No new suppression, concurrency or model-residency policy was introduced.

The real argument parser and all three entry expressions were executed without
importing or running the pipeline. `multi_round=False`, manifest absent:

| Source line | Guard | Result |
|---|---|---|
| pipeline.py:3918 | args.multi_round or args.multi_round_manifest | false |
| pipeline.py:3972 | multi_manifest is not None | false |
| pipeline.py:4228 | multi_record is not None | false |

The remote no-generation gate passed 27 checks and skipped one optional-directory
check (18 dedicated fixture checks, 9 legacy passes). This includes the pinned
ordinary-pipeline AST comparison, establishing that no case prompt/context branch
enters the chosen path. These fixtures are not real multi-round execution or
semantic-quality evidence. The full model-loading gate was not run.

Raw hydrated pipeline SHA-256:
`b85212483aea6ebab724b05a7f3f099df78be60e2f862070c7369cb63ebbfec1`.
Prelaunch and postrun inventories match every selected source file. Postrun checks
found zero multi-round artifacts and zero multi-round task calls among 20 call
evidence rows. No case artifact was required for ordinary completion.

## Provider, runtime and storage

Authenticated `curl.exe` requests using Bearer authentication returned HTTP 200
for `/instances` and `/instance-types`. The prior urllib/Basic 403 responses were
client/request-path failures, not evidence of a bad account or key. The credential
was passed through stdin, never argv, a file or output; redirects were not enabled.
Only the named Lambda credential was evaluated from the external local config.
SSH used the operator's passphrase-protected key through the working agent.

| Property | Verified smoke configuration |
|---|---|
| Instance | a100-shimmer, 8b54dae81752493f817ed09bf1fd5017 |
| Region / type | us-east-1 / gpu_1x_a100_sxm4 |
| GPU | 1 x NVIDIA A100-SXM4-40GB |
| API host specification | 30 vCPUs, 200 GiB RAM, 512 GiB storage |
| Guest observation | About 216 GiB RAM reported by Linux; 472 GB free root disk initially |
| Verified aggregate price | $1.99/hour before tax |
| Driver | 580.105.08; nvidia-smi advertised CUDA capability 13.0 |
| Shimmer environment | Python 3.12.3, torch 2.5.1+cu121, CUDA runtime 12.1 |
| Other direct dependencies | requirements.txt pins, plus measurement-only psutil 7.0.0 |
| Host environment | Existing torch 2.7.0/CUDA 12.8 retained intact |

The changed Python/platform substrate differs from historical local Python 3.9.13.
An isolated venv preserves the project's ML pins instead of modifying Lambda
Stack. `pip check` passed. No broad system upgrade was run. Existing host torch
2.7.0 was used only for the shipped safe embedding-weight conversion; execution
used pinned torch 2.5.1. The conversion preserves tensors in safetensors format.
This is a deployment-format adjustment, not a model or inference-setting change.

Exact revisions match the preserved local cache refs:

| Model | Revision | Remote hydration seconds |
|---|---|---:|
| BAAI/bge-m3 | 5617a9f61b028005a4858fdac845db406aefb181 | 4.414 |
| unsloth/Qwen2.5-7B-Instruct-bnb-4bit | bdd404162d94997f390efbfa660eb3f21cbbc81d | 14.051 |
| unsloth/Phi-3.5-mini-instruct-bnb-4bit | 5c20803aa197416f43fb455e55c85178775320cb | 7.074 |

Offline tokenizer/package readiness passed. Models and hot input/state were on
Lambda storage before execution; no WAN reads or provider dispatch occurred
during the run. Archives and collected evidence remain on the local SSD. No
persistent Lambda filesystem or second instance was provisioned by this session.

Lambda guest agent 1.0.0 was installed using the
[official documented installer](https://docs.lambda.ai/public-cloud/guest-agent/).
The service was active/running with ExecMainStatus=0 before and after the run.
The dpkg before/after comparison contains only the added guest-agent package;
the venv package inventory is unchanged. Console dashboard delivery was not
inspected. Guest metrics are supplemental, not the source of the figures below.

## Complete run ledger and latency

All controlled attempts are represented: exactly one, no retries or warm runs.

| Run ID | State | Native UTC start / end | Cold native wall | Observer wall | Calls |
|---|---|---|---:|---:|---:|
| 70e6b6e6f09543e8aa338a5509ce35f9 | completed, reached_end=true, exit 0 | 11:23:56 / 11:56:34 | 1,958 s | 1,956.350 s | 20 |

Native timestamps have one-second resolution. The monotonic observer excludes
some process startup/exit overhead. The pipeline completion interval itself was
11:24:01.721715 to 11:56:33.345291 UTC. There was one reviewed document and three
amendments. All 20 dispatch/generation/cost/evidence records reconcile; no span is
left open, no generation exception occurred, and no measurement hook was missing.

The single cold observation's mean, median, minimum and maximum are all 1,958 s;
that identity is not a distribution estimate. Percentiles are not informative.
Warm latency, warm throughput and warm-idle cost are UNMEASURED. The <=120-second
warm SLO was not demonstrated. ARCHIVIST's generation alone took 254 s, excluding
loading, so the prior 110-190 s engineering estimate is not supported here.

| Recorded phase | Seconds |
|---|---:|
| Production, 3-4 | 958.225 |
| Verification, 5 | 254.766 |
| Paired convention review, 5.5 | 203.871 |
| Synthesis, 6 | 0.721 |
| Editorial, 6.5 | 514.412 |
| Audit synthesis, 7 | 0.002 |

These existing phase durations exclude some startup/finalization time. Raw phase
markers and all remaining spans are in the archived events. Overall generation
was 1,920.789 s, 98.18% of observer wall. Non-generation was 35.561 s, including
7.223 s for three generation-model loads and 20.492 s inclusive embedding encode.
These nested measurements must not all be added together. File read/write wrapper
times are small; they are not OS storage-service or WAN-transfer measurements.
Scheduler idle/wait and synchronization were not independently instrumented;
residual time is not claimed as idle. No network attempt or provider attempt was
recorded by the workload's offline guards.

| Agent | Calls | Generation seconds |
|---|---:|---:|
| ARCHIVIST | 1 | 254.294 |
| INST_FINDER | 1 | 34.405 |
| CITATION_RESOLVER | 1 | 127.233 |
| PROCESSOR | 1 | 401.446 |
| SPEECH_ACT_TAGGER | 1 | 128.656 |
| LEGAL_ANALYST | 1 | 7.218 |
| VERIFIER | 1 | 119.944 |
| FACT_CHECKER | 1 | 133.473 |
| PRACTICE_AUDITOR | 11 | 201.746 |
| EDITOR_CLERK | 1 | 512.372 |

The observed serial execution path is corpus preparation/agents, document
production, verification, paired review, synthesis and editorial review. Long
generation on that path is the main measured bottleneck. CPU launch overhead
versus GPU kernel time within generate was not separately profiled. No semantic
dependency was removed. The 20 calls versus the original local 26 include six
missing legal follow-ups after an empty legal result under the existing gate;
this is not newly saved routing work or a controlled hardware-only speedup.

## Resources and cost

653 independent resource samples have a median three-second interval. Whole-run
GPU utilization median was 41%; samples during Qwen generation had median 41%,
Phi 50%. Both had sampled maxima of 100%, which do not imply sustained saturation.
Peak VRAM was 8,425 MiB (8.23 GiB). Qwen made 7 calls, generated for 1,465.625 s,
and had median output throughput 15.988 tokens/s. Phi made 13 calls, generated for
455.163 s, and had median output throughput 15.076 tokens/s.

Qwen loaded in 3.990 s, Phi in 1.236 s, then Qwen reloaded in 1.998 s for editorial.
The other 17 lookups were resident hits. The existing loader pins generation to
GPU 0 and evicts the other generation model. No multi-GPU occupancy, lane balance,
second-node queueing or inter-node synchronization measurement is claimed.

Peak process RSS was 6.023 GiB; minimum guest available RAM was 210.401 GiB.
Process CPU median was 100% (one core on this scale), with a brief 2,963.5% peak;
system CPU median was 3.4%, maximum 98.9%. GPU temperature peaked at 56 C. Sampling
does not demonstrate a CPU bottleneck, and no sustained memory pressure appeared.
The provider advertises 200 GiB while the guest reports about 216 GiB; guest
available-memory figures should not be subtracted from the advertised capacity.

Local RTX 3070 auxiliary task count was zero. No local contribution, network
overhead, saved latency or cost benefit was tested. The local machine carried
control and archival work, not the main runtime CPU/RAM/inference workload.

At $1.99/hour, the single cold execution costs $1.082 excluding preparation and
idle time. 3,600/1,958 gives 1.839 runs/hour as a reciprocal of this observation,
not measured sustained or warm throughput. Operator-confirmed conservative
billing start is 10:55 UTC. Control-plane absence was verified at 12:00:01.922 UTC:
estimated total instance cost is $2.157 before tax, about $2.19 allowing minute
rounding. Actual invoice duration, tax and any egress charge remain unverified.
No storage product was added. Setup, access troubleshooting, observation, evidence
collection and teardown latency account for the cost outside the single run.
Model hydration was timed above; dependency installation and SSH/provisioning
were not captured by a unified operational timer. These manual elapsed intervals
must not be presented as precise cold operational startup measurements.

The smoke had a 2,400-second timeout and a separate local API watchdog for 12:30
UTC. Neither limit was reached. Normal collection verified the archive hash before
API termination. The watchdog was disarmed after verified termination. No guest
shutdown was used; no resource is intentionally left billable by this experiment.

## Quality, governance and anomalies

Unchanged scoring: 3/5 location recall, zero amendment false positives, zero clean
distractor hits, attribution 3/3. ALDER, BIRCH and ELDER remain the hits; FIRTH and
the sheet-level defect remain misses. All five review states remain unknown;
reason scoring is unavailable. The scorer's sheet absence classification retains
its known parsed-unit limitation and is not proof that the source lacks evidence.

The three typed comparisons have the expected figures, units and supporting
REF-0007 table. Three DOCX comments are present. Manual inspection confirms the
known BIRCH contradiction persists in the master and DOCX comment: typed lower
bound 3.5 versus model prose calling 5.0 the lower bound. No layout certification
was performed. PROCESSOR produced 40 items but its first result-sheet extraction
cites REF-0001, which belongs to the reference handbook. This source-misattribution
issue was already observed in the activation comparison and prevents a grounding
equivalence claim. Its self-described extraction_method is model output, not
evidence of a real regex implementation.

18 model outputs were accepted through recovery; none establish strict canonical
JSON generation. Two contract violations were preserved: VERIFIER and FACT_CHECKER.
The original dense run instead failed CITATION_RESOLVER and VERIFIER. Thus the
unchanged aggregate failure count hides a changed failing consumer; FACT_CHECKER
lost an accepted output and broad quality/governance equivalence is NOT established.
Five calls hit caps: ARCHIVIST, CITATION_RESOLVER, SPEECH_ACT_TAGGER, FACT_CHECKER,
EDITOR_CLERK. Empty INST_FINDER, SPEECH_ACT_TAGGER and LEGAL_ANALYST outputs remain
visible. The clerk called the amendments sound despite the BIRCH contradiction.

Governance and contract enforcement stayed active; malformed replies were refused,
not promoted for speed. No governance bypass or source/config change was made.
The recorder also saw expected failed file probes and JSON parsing attempts
(168 FileNotFoundError, 20 JSONDecodeError, one JSON-load TypeError in VERIFIER).
These are handled instrumented spans, not 189 model failures; terminal completion
and the separate contract/generation counts remain authoritative.

## Evidence, decision and remaining work

Evidence root: `output/a100_smoke_20260914/`. It includes the selected source
archive/manifest, exact preparation and observer scripts, API metadata, dependency
and guest-agent inventories/logs, isolation proofs, all run artifacts, 11,153
structural observer events, per-call/per-agent/per-model summaries, scorer output,
two early checkpoints, final metrics and termination receipts.

Final collected archive SHA-256:
`c8a4cb2e80169b9f93ab79712e90f466d55563bc0754dfd4df27e7de4d18a85d`.
The local archive matched the remote hash before termination and was safely
extracted with required artifacts verified. Bulk evidence is intentionally ignored
by git; this report and the handover/ledger preserve its interpretation durably.

Do not launch A10 yet. Current source has neither a validated second-node worker
path nor a measured benefit from one; GPU residency savings here are only seconds,
while serialized generation is minutes. Adding paid capacity alone does not
address this execution path. Resolve the output-contract/grounding problems and
validate any proposed lane or serving change against the same semantics before
claiming quality-preserving acceleration. No alternate engine, precision, prompt
budget or model change is accepted by this smoke.

Remaining current-version work includes controlled warm measurements, a validated
composite execution path, local auxiliary usefulness and missing scheduler/transfer
measurements. Future multi-round topology cannot responsibly be finalized from
this cold single-node smoke. Do not start that experiment or finalize the minimum
reasonable remote specification. This stage closed without a push.
