# Controller correction: remote phases detached from any one connection

Status: **CONTROLLER_TRANSPORT_CORRECTED_LOCALLY**. Operator-side controller only. No cloud
compute, no model, no change to the sealed runtime, decoding policy, weights, HPO settings,
pairing contract, telemetry architecture, workload or routing.

## Why

Run v3 (2026-09-18, `docs/fix/ORDINARY_FINAL_V3_RUN_RESULTS.md`) lost its one authorized
invocation without ever starting the workload. The pinned wheel install finished on the
instance, but the controller kept a single `ssh` process open for the whole phase and treated
that process's exit as the phase's completion; the connection carrying it stopped delivering in
the return direction, the client never disconnected, and the phase reached its 30-minute
deadline. The workload phase had the same shape with the remaining budget as its deadline, so a
dropped connection mid-run would have terminated a healthy workload and stranded its evidence
on a billed instance.

## What changed, in `tools/ordinary_final_cloud.py` only

- Every remote phase now runs **detached** on the instance: the command is stored as a script,
  started under `setsid nohup` with its output and exit code written to files under
  `phases/`, and the short launching connection returns at once with the wrapper's pid.
- Completion is **polled over fresh short connections** (first after 2 s, then every 10 s) until
  the phase's existing deadline. Each poll reports `RC=<code>`, `RUNNING` or `DEAD`.
- A poll whose connection fails or hangs is classified **unreachable** and retried; it is never a
  phase result. The phase completes when a poll reads the exit code, fails when the wrapper has
  vanished without one (`DEAD`), and times out only when the remote work itself has not finished
  by the deadline, which is now named `Phase deadline exceeded` rather than a transport error.
- The remote work's liveness and the connection's health are recorded as **two separate facts**
  in `<phase>_status.json` and `phase_status.json` (`remote_work`, `connection`, `polls`,
  `unreachable_polls`, `deadline_epoch`, `exit_code`), updated on every poll.
- During the workload phase each poll also fetches the tail of the run's own progress stream
  into `workload_progress.log`, through the same credential scan every transport output passes.
- The phase's output is collected afterwards over a fresh connection into `<phase>.log`, and
  `<phase>_timing.json` records the exit code, poll counts and whether the phase was detached.
- Unchanged: the budget deadlines and termination reserve, the soft-budget refusal, the single
  workload invocation (the remote runner's `RUN_CLAIMED` still refuses a second), the failure
  teardown, evidence collection and hash check, termination, credential removal and the
  independent inventory confirmation.

## Proof, all mocked, no network, no instance

`tools/ordinary_final_controller_checks.py` runs the real `execute()` end to end against fake
provider, ssh, scp, ssh-keygen, watchdog and clock, so the phase sequence, polling, teardown and
cleanup are the controller's own code paths. `tools/ordinary_final_controller_gate.py` runs it with
the network denied and records `docs/fix/ordinary_final_transport_fix/controller_validation.json`.

| Check | Result |
|---|---|
| Poll classification: connection failure is unreachable, never a result; RC, RUNNING, DEAD, garbage | pass |
| Launch and poll commands round-trip the exact phase command and report liveness | pass |
| **The v3 case: install completes remotely while three consecutive connections die** | completed, run proceeds through the workload, torn down cleanly |
| Connection lost five polls in a row during the workload while it keeps running | polling continues, progress recorded, exit code read, torn down cleanly |
| Remote work dies without an exit code | phase fails, workload never started, torn down cleanly |
| Remote work outlives the phase deadline | `Phase deadline exceeded`, torn down cleanly |
| Real remote failure before the workload | torn down, credentials removed, second launch refused |
| Nonzero workload exit | recorded as evidence, no retry, torn down cleanly |

Neutralize, fail, restore, pass: with `poll_outcome` replaced by the pre-correction reading
(a failed connection is the phase's result), the v3 case fails with
`Execution phase failed: install_pinned_wheels`, exactly the shape of the real failure, and the
mid-workload case fails the same way; the neutralised branch ran 10 and 14 times respectively;
restored, both pass. 8 tests, 0 failures.

## The launch race, found on a real Linux shell

The generated launch and poll strings were then run through exactly one shell layer on a local
Ubuntu (WSL, `bash -c` over dash), which is how `ssh host cmd` runs them. One launch in four died
at once with no output: the session's hang-up reached the detached child between fork and exec,
before `setsid` and `nohup` had taken effect. That race is as possible over SSH as it was there.
Two guards now close it: the launching shell ignores HUP before forking, which the child inherits
across fork and exec, and the launcher does not return until the wrapper has written a started
marker; a wrapper that never starts fails the launch itself, at once, rather than surfacing later
as DEAD. With the guards, `test_generated_commands_run_detached_on_a_real_linux_shell` launches
twelve phases in a row, all detach and finish with their own exit codes, the collected output is
the command's own, the progress tail arrives, and a wrapper killed without an exit code reads
DEAD. The check runs whenever a local Linux shell exists and is recorded as skipped otherwise.
9 tests, 0 failures.

## Boundary

The mocks prove the controller's reading of poll results and its sequencing; the Linux-shell
exercise proves the remote command strings on Ubuntu's `dash` and `bash`. Neither reproduces the
instance image's `sshd` session teardown exactly; the next authorized run's per-phase status
files show that directly, and its launch phase now fails fast if a wrapper does not start.
