# Remote short-burst feasibility pass, 15 September 2026

## Result

**CLOUD_FULL_RUN_INDETERMINATE**

The authorized single-instance attempt stopped before model loading. The probe
launcher selected the image's default Python 3.10.12, although this repository
uses Python 3.12 f-string syntax. Importing `agent_wrapper` reached
`scripts/finding_record.py:395` and failed with `SyntaxError`. This was an
experiment-launcher preparation error, not evidence of an inference or model
quality limitation. The earlier deployment profile explicitly required Python
3.12.3; the bounded launcher failed to preserve that requirement.

No inference latency, semantic quality, concurrency or ordinary-run feasibility
claim can be made from this attempt. No second instance was provisioned. The
full pipeline and multi-round were not run. No paid inference API was used.

## Source and experimental record

Source tested: `c514d5b68a13a18858608ee176f308d922236541`. Tracked files were clean;
the existing untracked `SHIMMER_HANDOFF.md` and `durable/` were preserved.
Production source was not modified. This is a new bounded measurement; the
14 September evidence and its non-benchmark classification remain unchanged.

The [manifest](remote_short_burst_20260915/manifest.json) records the source,
generation limits, model pins, probe definitions, topology and budget before
provisioning. The [artifact hashes](remote_short_burst_20260915/artifact_hashes.json)
cover the preserved evidence. Full local controller logs and the collected
archive remain in `output/remote_short_burst_20260915/`.

Configured models, unchanged from HEAD:

| Role | Checkpoint | Revision |
|---|---|---|
| Producer | unsloth/Qwen2.5-7B-Instruct-bnb-4bit | bdd404162d94997f390efbfa660eb3f21cbbc81d |
| Auditor | unsloth/Phi-3.5-mini-instruct-bnb-4bit | 5c20803aa197416f43fb455e55c85178775320cb |

Both pinned snapshots were fetched. Their configured Qwen/Phi separation was
preserved; runtime family verification was not reached. No new quantization,
serving engine, model or generation budget was introduced. Planned limits were
384 output tokens and 25 seconds, deterministic generation with seed 7, matching
the preceding bounded local validation. These probe limits are narrower than
the ordinary optimized PROCESSOR partition ceiling of 1536 tokens.

Planned topology: ordinary `report_optimized`, one `cuda:0` owner, two resident
model slots, multi-round false. The probe blocked socket connections during
inference and selected only local model backends. That inference boundary never
reached a generation call.

## Hardware, pricing and setup

Lambda instance `95bbd0c1a9e64361b80c0ff8011b84a3`, `gpu_1x_a10`, `us-east-1`.
Quoted price: **$1.29/hour**. The $0.69/hour RTX 6000 and $1.09/hour A6000 had no
available regions; the A10 was the cheapest available single-GPU option in the
recorded inventory. A100 capacity cost $1.99/hour. Soft target $1; hard ceiling
$2, with a 180-second termination reserve and an independent local watchdog.

| Observation | Measured value |
|---|---:|
| GPU | NVIDIA A10, 23,028 MiB exposed VRAM |
| CPU | 30 vCPUs, Intel Xeon Platinum 8358 |
| RAM | 200 GiB provider specification; 238,546,464,768 bytes reported by OS |
| Idle used host RAM | 1,120,792,576 bytes |
| Available storage | 1,430,083,432,448 bytes |
| NVIDIA driver / CUDA capability | 570.148.08 / 12.8 |
| Actual Python / PyTorch | 3.10.12 / 2.7.0, CUDA 12.8 |
| Transformers installed | 4.52.3 |
| Provisioning through SSH readiness | 198.446 s |
| Source transfer | 1,264,923 bytes in 3.946 s |
| Remote preparation before probe invocation | 29.277 s |
| Dependency installation | 10.279 s |
| Model acquisition subprocess | 13.945 s |
| Failed probe process | 1.719 s |

CUDA arithmetic succeeded. No provider filesystem cache existed, and both model
snapshots were absent before acquisition. Producer fetch took 7.513 s; auditor
fetch took 6.176 s. Acquisition is infrastructure preparation, not model hydration
or marginal inference. No weights were hydrated into a model instance.

The source archive used the source-layer manifest mechanism and was verified
remotely by SHA-256. The old 5.30 GB bundle was not transferred. An existing
protected SSH key had no active agent, so a temporary key was registered. Its
local permissions were restricted before connection. The temporary provider
registration and local key files were removed after verified shutdown.

## Probe outcomes

| Probe / requirement | Outcome |
|---|---|
| 0: hardware and runtime readiness | Hardware and CUDA checked; Python compatibility check was missing before probe import |
| 1: cold producer initialization | Not reached |
| 2: compact PROCESSOR and source-copy comparison | Not reached |
| 3: independent auditor | Not reached |
| 4: producer to auditor serial dependency | Not reached |
| 5: concurrency 1 versus 2 | Not reached |
| 6: concurrency 4 | Not admitted |
| Generation / contract attempts | 0 / 0 |
| Contract-valid responses | 0 of 0; no success rate is defined |
| Truncation / semantic fixture result | Unmeasured |
| TTFT, tokens/sec, latency, stop reasons | Unmeasured |
| Model residency, offload, reload or swap | Unmeasured |
| Inference GPU/CPU/RAM utilization or peaks | Unmeasured |

The only GPU sample was readiness: 0 MiB used and 0% utilization. It is not an
inference resource envelope. The authored fixture's local deterministic source
reconstruction passed, as did 17 recommendation mechanism checks. Neither is
evidence of real-model semantic quality.

Source inspection establishes an additional restriction for a future pass:
`Worker` has one execution thread, and topology configuration permits one owner
per CUDA device. Jointly admitting two independent calls therefore does not
establish GPU overlap. This attempt did not measure that restriction's latency
impact and does not report a synthetic concurrency speedup.

## Ordinary-run projection and eligibility

The existing `run_projection.project` engine was executed with new
[projection inputs](remote_short_burst_20260915/projection_input.json) and
[outputs](remote_short_burst_20260915/projection_output.json). No historical
service latency or synthetic timing populated a measurement field.

The preserved structural template has 20 nodes and five semantic waves. It is
not a measured call count for a selected ordinary workload. The optimized
architecture's workload-dependent formula remains `19 + P - C`, with bounded
PROCESSOR partitions P and eligible deterministic comparison removals C.

| Projection | Result |
|---|---|
| Marginal warm ordinary wall / critical path / inference time | Unknown |
| Measured safe concurrency | Unknown |
| Expected retries / contract-refusal risk / truncation | Unknown |
| `marginal_cost_per_accepted_run` | Unknown |
| Cold/full-loaded ordinary wall | Unknown |
| `fully_loaded_cost_per_accepted_run` | Unknown |

Measured setup is recorded separately and cannot turn a nonexistent accepted
run into a per-accepted-run cost. No inference bottleneck was measured. The
largest established blocker is runtime compatibility in the experiment launcher.

The next bounded attempt should preserve the existing Python 3.12.3 runtime
requirement, explicitly select that interpreter, and compile/import the probe
dependency graph before downloading models. Verify the runtime/image layer
locally before provisioning; do not change production syntax merely to support
an accidentally selected older interpreter. No full-run authorization follows
from this result.

## Shutdown, integrity and cost

The controller independently inspected the remote process list and found no
remaining `setup.py` or `probe.py` workload, collected the evidence archive, and
requested termination. Local gzip CRC validation succeeded; extracted artifact
hashes were recorded. Collection succeeded before shutdown.

* Termination requested: **2026-09-15 07:15:49.468119 UTC**.
* Provider confirmed absence from its active-instance list:
  **2026-09-15 07:17:18.016016 UTC**.
* Instance ID: **95bbd0c1a9e64361b80c0ff8011b84a3**.
* Conservative billable-duration upper bound: **340.349401 s**.
* Estimated total instance-cost upper bound: **$0.1219585353**.

Cost uses launch-request start through completion of the first provider absence
confirmation, at $1.29/hour. It is an elapsed-time estimate, not a provider
invoice. The watchdog's original cost field used the query start; the summary
conservatively includes the final response latency. Both records are preserved.
See [termination proof](remote_short_burst_20260915/TERMINATION_VERIFIED.json) and
[summary](remote_short_burst_20260915/summary.json).

No billable experiment instance remains. No push was performed.
