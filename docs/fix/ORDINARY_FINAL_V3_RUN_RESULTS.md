# Ordinary final run v3: transport failure before the workload, authorization consumed

Status: **ORDINARY_FINAL_CLOUD_RUN_V3_TRANSPORT_FAILURE_NO_WORKLOAD**. The one authorized
instance ran for 74 minutes and was terminated; provider inventory is empty on three independent
readings; the temporary SSH registration and local key material are removed; the watchdog exited.
**The sealed workload was never invoked.** The decoding-policy correction that this run was meant
to exercise on real hardware remains validated only locally. No second instance was launched, no
retry was attempted, nothing was pushed.

## Bound identity and pre-launch reverification

- Sealed source commit `e4b52e6`; manifest `a2a8be14f3d9822fcf5dd2b5beb50bfd6e6586f78d5c1dc0aa219534a3d88bd7`;
  seal `7638c3503f82607747cc744af27f8dc245f950a181d31afc42ef558409aeb8fc`; project archive
  `b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d`; assets archive
  `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6`, rebound from v2 by hard link.
- Launch tooling: `tools/ordinary_final_v3_cloud.py` binds the unchanged controller to exactly these
  digests and refuses on any difference; `tools/ordinary_final_v3_reverify.py` and
  `tools/ordinary_final_v3_preflight.py` produced the two pre-launch receipts. Committed as `c158131`.
- `AUTHORIZED_LOCAL_REVERIFICATION.json`, no model, no provider: manifest, seal and both archives at
  the authorized digests; the project archive an exact tree of 160 members; 151 archived runtime files
  byte-identical (LF-normalised) to `git show e4b52e6:<name>`; HEAD (`57fc0b2`) differs from the sealed
  commit only under `docs/fix`, so the sealed archive that launched is e4b52e6's runtime; the decoding
  policy resolved from the archived declaration and both archived protocols equals the manifest's
  record, digests included; the three Hub refs inside the asset archive are exactly 40 bytes of the
  admitted revisions; controller, support and preparation sources still hash to the manifest.
- `authorized_live_preflight.json`, read-only provider calls: inventory empty; `gpu_1x_a10` x86_64 with
  capacity in us-east-1 at $1.29/hour, equal to the authorized ceiling; image `gpu-base-24-04`
  `24.4.4-2141` (`9211995d-2377-4ea8-94d2-18eea01ec3f6`) still offered. Nothing launched.
- The controller repeated the inventory, capacity, rate and image checks at `launch_preflight.json`
  immediately before launch, with the same results.

## What happened

One instance, `4d7fbfb35c284f42bb093bf57163fb2c`, named `shimmer-ordinary-final-8d46fe9`, active after
194 s at $1.29/hour. The permit bound it to the manifest, seal, source commit and the $5 soft / $7 hard
budget; the watchdog armed at PID 3264 with a live heartbeat.

| Phase | Started after launch | Duration | Result |
|---|---|---|---|
| ssh_ready, python_gate (3.12.3), fresh_directory | 3.2 min | 2 s each | ok |
| support_transfer | 3.3 min | 34 s | ok |
| assets_transfer (13,149,972,480 bytes) | 3.9 min | 2240 s | ok |
| archive_integrity (remote sha256sum of both archives) | 41.2 min | 14 s | both OK |
| extract_payload, create_environment | 41.5 min | 10 s, 8 s | ok |
| install_pinned_wheels | 41.8 min | 1800 s | **transport deadline** |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash, evidence_download | 71.8 min | 2 to 7 s each | ok |
| terminate_instance, provider-confirmed terminated | 71.9 min | | at 73.7 min |
| independent post-controller confirmation | | | at 74.0 min |

Every remote phase up to and including the wheel install completed on the instance. The install did
not complete for the controller: its `ssh` process, kept open for the duration of the remote command,
never received the channel close, and after the phase's 30-minute deadline the controller raised
`Transport deadline exceeded` and entered its designed teardown, which succeeded in full over fresh
connections.

Two read-only inspections from the operator machine with the run's temporary identity, taken at
24.5 and 26.7 minutes into the phase and recorded in `install_phase_transport_stall_observation.json`,
established the state of the instance at the time:

- no pip or python process existed; the one-minute load average was 0.00; `site-packages` held 189
  entries, the newest being `peft`, `sentence_transformers` and `accelerate`, with 38,013 files written
  under the virtual environment since the install lock was transferred: the install had finished;
- the controller's `sshd` session (elapsed 25:42) had no child process left: the remote shell and pip
  had exited and the session was only waiting to deliver its final bytes;
- that session's TCP connection held 1396 bytes unacknowledged toward the operator machine, while the
  inspection sessions from the same machine connected and exchanged data normally.

So the failure sits in the transport between the operator machine and the instance: the established
connection carrying the install phase stopped delivering in the return direction, and the local
client did not disconnect on its own despite `ServerAliveInterval=15` and `ServerAliveCountMax=2`
(OpenSSH 9.9p1 client). Why the client did not detect the dead connection is **not established** from
the retained evidence; the remote side's completion is. This is not a startup, admission, model,
decoding or workload failure. No file on the instance was written and no process signalled during
the inspections; the operator machine's public address is withheld from the record.

## What was, and was not, tested

Tested on real hardware: the offline cache refs (both archives verified remotely, the payload extracted
cleanly), the pinned environment (created; 189 packages installed from the sealed wheels with hash
checking, as far as the instance shows), and the controller's failure path (collection, termination,
cleanup and independent confirmation all succeeded after a mid-run transport failure).

Not tested: everything from `pip check` onward. The runner never started, so there is no `RUN_CLAIMED`,
no `evidence/` directory, no admission receipt, no decoding-policy admission on the remote, no model
load, no call receipt, no stop reason and no cap-hit state. The collected archive holds only the four
manifest files that existed at the top level. The analyzer's `FINAL_STATUS.json` records
`pipeline_started: false`, zero Producer168 and Auditor896 receipts, and `quality_claim: null`. Known
Auditor limitations are unchanged and unmeasured: external macro F1 about 0.8010, historical about
0.4576, historical OMISSION recall 1 of 12.

## Why the controller was not bypassed

At 24.5 minutes into the stalled phase there were about five minutes to the deadline. The only way to
still run the workload on this instance would have been to kill the controller before it timed out
and drive the remaining phases by hand over new sessions, including the single workload invocation,
evidence collection and termination. That would have replaced the validated controller and its
cleanup path with an improvised procedure under time pressure on a billed instance, and the
authorization named one run under the controller with no retry and no second instance. The designed
teardown was left to run.

## Cost and teardown

Launch epoch `1789716350.104`; provider-confirmed terminated at `1789720771.159`; independent
post-controller confirmation at `1789720791.248`. Conservative estimate through that confirmation:
**$1.5914** infrastructure, $0 model or API, not an invoice. Both the $5 soft and $7 hard limits were
respected. No persistent storage was created. `cleanup.json`, `independent_inventory_confirmation.json`
and `operator_post_cleanup_confirmation.json` each record an empty inventory, the temporary
registration absent and the local key material absent. Watchdog PID 3264 was confirmed exited.

## Evidence

Directory `docs/fix/ordinary_final_cloud_run_v3`. Pre-launch: `AUTHORIZED_LOCAL_REVERIFICATION.json`,
`authorized_live_preflight.json`, `launch_preflight.json`. Launch and permit: `LAUNCH_INTENT.json`,
`launch.json`, `operator_authorization.json`, `v3_controller_identity.json`, `activation.json`,
`WATCHDOG_ARMED.json`, `watchdog_process.json`. Per phase: `<phase>.log` and `<phase>_timing.json`.
The stall: `install_phase_transport_stall_observation.json`, `install_pinned_wheels_timing.json`,
`controller_failure.json`. Collection and teardown: `collection_integrity.json`,
`remote_collection_manifest.json`, `collected_evidence.tar.gz` (four members, extracted under
`downloaded/`), `termination_requested.json`, `TERMINATION_VERIFIED.json`, `instances_after.json`,
`cleanup.json`, `independent_inventory_confirmation.json`, `operator_post_cleanup_confirmation.json`,
`cost.json`, `FINAL_STATUS.json`, `analysis/`, `controller_console.log`.

## Minimal proposed correction, not implemented

The controller keeps one `ssh` process open for the whole of every remote phase and treats that
process's exit as the phase's completion. A dead client-side connection therefore consumes a phase
whose remote work has already finished, and the same design governs the workload phase, whose
deadline is the remaining budget: a connection dropping during a multi-hour run would time the run
out and terminate a healthy workload with its evidence still on the instance.

The correction belongs to the operator-side controller (`tools/ordinary_final_cloud.py`), not to the
sealed runtime, models, workload, routing or telemetry: run every remote phase longer than a few
seconds detached on the instance, writing its output and exit code to files, and poll for the exit
code over short, fresh connections until the phase's existing deadline. The single-invocation
guarantee is unchanged, because the remote runner's `RUN_CLAIMED` file still refuses a second
invocation; the budget deadlines, evidence collection and teardown are unchanged. The controller's
existing mocked-transport checks should gain a case where the phase connection dies after the remote
command completes and the phase must still succeed. This needs a separate authorization; nothing
here launches or authorizes a run, and the authorization bound to bundle v3 is consumed.
