# Full phase-sequence rehearsal of the ordinary final controller

Status: **REHEARSAL_PASSED_LOCALLY**. Local only: no cloud, no instance, no model weights. The
operator-side controller and its checks changed; the sealed runtime, decoding policy, weights,
HPO settings, pairing contract, telemetry architecture, workload and routing did not.

## Why

Two authorizations were consumed by phase-sequence defects before the workload ever started: v3
by a dead connection the controller treated as a phase failure, v4 by the corrected launcher
creating the remote root that the controller's own `fresh_directory` check requires to be absent.
The existing gates proved the polling mechanism, not the phases' preconditions, because the
mocked transport answered exit 0 to every poll by default and the Linux-shell exercise ran probe
commands rather than the controller's sequence.

## What changed

- **The launcher creates nothing under the remote root.** Phase bookkeeping (script, output,
  exit code, pid, started marker) now lives in a sibling directory, `<remote>-phases`, so the
  `fresh_directory` check keeps its meaning. `phases_dir()` in `tools/ordinary_final_cloud.py`.
- **A missing progress file never fails a status poll.** The workload poll's informational tail is
  followed by `|| true`, so the status line is always the poll's result.
- **The mocked transport now models the precondition it used to mask.** Every directory a launch
  command creates is recorded, and the `fresh_directory` poll answers from that record: exit 1 if
  anything under the remote root exists, otherwise exit 0. Two new checks cover both polarities,
  and a third neutralize/fail/restore/pass proof restores the v4 layout (phase files under the
  root) and shows the run failing exactly as v4 did (18 neutralised invocations).
- **A rehearsal harness runs the real controller against a local Ubuntu.**
  `tools/ordinary_final_rehearsal.py` executes the controller's own `execute()`, with its own
  command strings, in its own order, through its own detached-phase transport, against WSL Ubuntu
  24.04.1 (Python exactly 3.12.3, `nvidia-smi` present). Every `ssh host cmd` becomes `bash -c cmd`
  on that Ubuntu, one shell layer as sshd runs it; every `scp` becomes a copy across the Windows
  and Linux mounts; the provider is mocked; the watchdog is a local heartbeat thread; the
  temporary ssh identity is real. The sealed project archive, runner, observer, install lock and
  all 92 sealed wheels are the real ones. The asset archive is a rehearsal build with the same
  wheels and 40-byte Hub refs but no model weights (3,067,351,040 bytes, 131 members).

## What rehearsed, in the controller's order

Absent remote root, receipt `docs/fix/ordinary_final_rehearsal/rehearsal.json`:

| Phase | Exit | Detached | Polls |
|---|---|---|---|
| ssh_ready | 0 | | |
| python_gate (asserts 3.12.3) | 0 | yes | 1 |
| fresh_directory | 0 | yes | 1 |
| support_transfer | 0 | | |
| assets_transfer (local copy of the rehearsal archive) | 0 | | |
| archive_integrity (remote sha256sum of both archives) | 0 | yes | 2 |
| extract_payload | 0 | yes | 2 |
| create_environment (`python3.12 -m venv`) | 0 | yes | 2 |
| install_pinned_wheels (92 wheels, hash-checked, offline) | 0 | yes | 12 |
| dependency_closure (`pip check`) | 0 | yes | 1 |
| gpu_metadata | 0 | yes | 1 |
| watchdog_receipt_transfer | 0 | | |
| ordinary_workload | 1, by design | yes | 4 |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | 0 | yes | 1 each |
| evidence_download, hash verified | 0 | | |
| terminate, cleanup, independent confirmation | mocked provider | | |

Zero unreachable polls. The workload phase invoked the sealed runner, which passed its manifest
and exact-tree verification, the permit and authorization, the watchdog receipt, the single claim,
the Hub cache admission of the three refs and the weight-free snapshots, the installed-runtime
admission of every package and file hash, the frozen adapter and pairing-contract admissions, the
decoding-policy admission and `verify_runtime` (CUDA, BF16 and CUDA 12.1 through WSL), and then
refused at `hardware_admission` with `RuntimeError: A10 memory admission`, because this GPU is not
an A10. That refusal is the designed boundary of the rehearsal. The controller recorded exit 1 as
evidence without retry, collected and hash-verified the evidence, and tore down.

## Preconditions exercised in both polarities

| Precondition | Positive polarity | Negative polarity |
|---|---|---|
| `fresh_directory`, remote root absent or present | exit 0, run proceeds | exit 1, controller refuses before any transfer, tears down |
| `archive_integrity`, intact or corrupted archive | exit 0 | one byte altered: exit 1 |
| single workload claim (`RUN_CLAIMED`) | first invocation claims | second invocation refused, exit 1, `FileExistsError` |
| temporary key path absent or present | run starts | `Temporary key path occupied`, zero launches |

The rehearsal was run twice: once before the poll-tail robustness change and once after it, so the
strings rehearsed are the strings committed. 434 s. The Linux target was cleaned afterwards.

## What the rehearsal exposed

1. The v4 defect, reproduced before the fix by the mocked gate's new precondition model and by the
   rehearsal's present-root polarity, and absent after it.
2. A poll whose informational progress tail failed (file not yet written) was classified
   unreachable; harmless but noisy, now fixed and pinned by a check.

## What remains unrehearsed, and why

- Provider actions (launch, instance state, terminate, ssh-key registration): mocked; they need
  the provider.
- The 13 GB asset upload over scp: replaced by a local copy of the rehearsal archive; the real
  upload needs the provider.
- Model weights, their remote hashing and model loading: left out by design; the runner refused at
  hardware admission before any load.
- Hardware admission on an A10: this GPU is not an A10; the refusal there is the boundary.
- The ssh and scp transports themselves: a local shell and file copies stand in; the polling and
  detached-phase code paths are the controller's own.
- The real watchdog process: a local heartbeat thread stands in; the watchdog has its own checks.
- The instance image's `sshd` session teardown: the Linux-shell exercise showed the launch race and
  its guards on Ubuntu's `dash` and `bash`; the run itself shows it on the image.
