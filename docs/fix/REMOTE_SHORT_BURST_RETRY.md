# Runtime-gated remote retry, 15 September 2026

## Result

**CLOUD_FULL_RUN_INDETERMINATE**

One fresh Lambda A10 was provisioned, then emergency-terminated after a temporary
Jupyter access token was accidentally displayed from its provider metadata.
SSH readiness had not completed. No source was uploaded, no remote runtime gate
completed, and no model was acquired, loaded or called. This attempt establishes
no inference performance, quality, concurrency or resource result.

The operator authorized this bounded cloud experiment, then explicitly authorized
the reviewed source archive after automatic approval review blocked export.
After the incident, the operator authorized local redaction and this report,
without another instance. No second instance was launched.

## Source and preparation

Runtime-hardening base: `60a55af`. Intended tested source:
`d3ebb060b14333fb2e0a54e7a134c54463bfc73b`.
The small local change persists preparation-stage durations/results and writes
`PRE_INFERENCE_CHECKPOINT.json` before model acquisition. Its new deterministic
test verifies that dependency and source proof exist before acquisition begins.
**26 runtime tests and 83 cloud checks passed**, with cloud-test networking blocked.

The canonical contract remains Python `>=3.12,<3.13` for experiments and exactly
`3.12.3` for sealed reference runs. The selected image was Lambda Stack 24.04,
version `24.4.4-2141`, image ID `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0`.
The provider documents Python 3.12 for this image family, but no remote interpreter
was measured in this attempt. [Provider image documentation](https://docs.lambda.ai/public-cloud/on-demand/)

The controller was configured to use the maintained resolver and
`tools/prepare_remote_experiment.py --execute --install-missing`, with its
compile/import/dependency gates before model downloads. It never reached them.
The archived failing setup script was not used. The new controller is preserved
as incident evidence in `controller_executed.txt`; it is **not a supported retry
entrypoint** and must not be reused without addressing its metadata defect.

The [manifest](remote_short_burst_retry_20260915/manifest.json) records unchanged
Qwen producer and Phi auditor model IDs/revisions, `multi_round=false`, the
384-token/25-second ceilings, at most nine calls, quality-gated concurrency,
budget, source commit, and hardware policy before launch.

The reviewed archive contained 162 files: tracked source, three required tracked
configurations, and a generated hash manifest. It excluded credentials, operator
data, the ignored convention registry, documents and model weights.
Prepared archive: **1,258,520 bytes**. Actual transfer: **0 bytes**.

## Measurements and missing evidence

| Item | Result |
|---|---|
| Provider / region | Lambda / `us-east-1`, Virginia |
| Instance | `c981f11ebc5849928826f716f72c6149` |
| Type / quoted GPU | `gpu_1x_a10` / A10 24 GB |
| Quoted host resources | 30 vCPU, 200 GiB RAM, 1,400 GiB storage |
| Hourly rate | $1.29 |
| Provisioning to provider `active` | 209.177 seconds |
| SSH readiness / complete setup | Not reached / unknown |
| Runtime, compilation, critical imports, dependency readiness | Not reached remotely |
| NVIDIA driver, CUDA, PyTorch, Transformers | Not observed remotely |
| Source-transfer duration | Not performed |
| Acquisition / producer load / auditor load | Not performed |
| Producer / auditor latency, TTFT, tokens/s | Unknown; zero calls |
| Mandatory producer-to-auditor serial latency | Unknown |
| Concurrency 1 vs 2 / 4 | Not run / not admitted |
| GPU overlap / utilization, VRAM, CPU/RAM samples | Unknown |
| Model residency, reload, offload, switch penalty | Unknown |
| Truncation / valid-contract counts / semantic assessment | Not observed; no outputs |

Current inventory had no RTX 6000 or A6000 capacity. A10 was the cheapest
available suitable single-GPU x86-64 option. Hardware above is provider metadata,
not a measured safe model-residency envelope.

## Incident and containment

The experiment controller persisted the raw provider instance object, bypassing
the repository's existing `safe_metadata` allowlist. A subsequent status read
displayed the object's temporary `jupyter_token` and token-bearing URL. This was
an assistant/controller handling error. The provider account API key was not
displayed. Neither the token nor its URL is included in the retained report.

The experiment controller was stopped and provider termination was explicitly
submitted. Provider status progressed to `terminating`, then the instance was
confirmed absent. SSH had never become ready, so there is no remote process-list
or model-process shutdown observation; provider termination ended the instance.

With operator approval, the token was removed from the local metadata file and
all files in the new experiment folder were checked for further occurrences.
The token-bearing metadata fields were removed entirely. The temporary SSH public
registration was deleted and its absence verified; its local key pair was removed.
Already displayed conversation output cannot be retracted. See the
[redaction record](remote_short_burst_retry_20260915/incident_redaction.json).

## Projection

The existing deterministic projection engine was run with the existing ordinary
workload graph: **20 planned calls and five semantic waves**. These are graph
properties, not measured executed work. All new service-time fields remain null;
no historical A100 or laptop timings were imported.

Warm ordinary wall, critical-path time, inference time, retries, truncation,
contract-refusal risk and resource envelope remain **unknown**. Both
`marginal_cost_per_accepted_run` and `fully_loaded_cost_per_accepted_run` remain
**unknown**: there was no accepted run or representative call.
The engine's local-target label is not used to claim cloud eligibility.

The known provisioning cost is a one-time setup observation. A future warm,
pre-positioned deployment could amortize setup and acquisition; an instance per
run would pay them each time. Neither deployment's accepted-run cost can be
estimated from this attempt. See [projection inputs](remote_short_burst_retry_20260915/projection_input.json)
and [outputs](remote_short_burst_retry_20260915/projection_output.json).

## Shutdown, cost, integrity and next step

First provider-confirmed termination: **2026-09-15 08:55:04.019863 UTC**.
A second query confirmed absence and **zero active instances**.
Conservative duration from launch-request start to the first confirmation:
**376.213599 seconds**. Estimated instance-cost upper bound: **$0.1348098731**,
below both the $1 soft target and $2 ceiling. This is an elapsed-time estimate,
not a provider invoice. See [termination proof](remote_short_burst_retry_20260915/TERMINATION_VERIFIED.json).

Redacted local evidence has an [artifact hash manifest](remote_short_burst_retry_20260915/artifact_hashes.json).
All 33 files in the first 15 September historical evidence directory match the
pre-retry hashes. Neither that report nor the 14 September evidence was rewritten.
Operator-owned `SHIMMER_HANDOFF.md` and `durable/` remain untouched.

No measured inference bottleneck was identified. The immediate blocker was the
metadata disclosure and resulting emergency stop; SSH readiness was still pending.
Before any separately authorized retry, use the existing metadata allowlist at
every provider-response boundary, test that secret-bearing fields cannot enter
artifacts or status output, and preserve SSH-readiness diagnostics safely. Then
repeat only this runtime-gated bounded experiment with fresh cloud approval.
No serving-engine migration or full run is justified by this result.

**Full pipeline NOT run. Multi-round NOT run. Paid inference API NOT used.
Instance terminated and verified. No push.**
