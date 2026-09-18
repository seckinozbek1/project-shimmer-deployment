# Ordinary final run v4: failed at fresh_directory by a defect in the controller correction

Status: **ORDINARY_FINAL_CLOUD_RUN_V4_FAILED_FRESH_DIRECTORY**. Stage C failed its own gate. The
one authorized instance ran for 6.6 minutes and was terminated; provider inventory is empty on
three independent readings; the temporary SSH registration and local key are removed; the
watchdog exited. **The sealed workload was never invoked**, so the decoding-policy correction has
still not been exercised on hardware. No second instance, no retry, nothing pushed. The
authorization bound to bundle v4 is consumed.

## The cause, precisely

The Stage A correction runs every remote phase detached under `<remote>/phases/`. Its launcher
begins with `mkdir -p <remote>/phases` so that the phase's script, output, pid and exit-code
files have somewhere to live. The controller's third remote phase has always been

```
fresh_directory:  test ! -e <remote> && mkdir -p <remote>/project
```

whose whole purpose is to refuse a remote root that already exists. The launcher created that
root two seconds earlier. The test failed with exit code 1, on a transport that worked
perfectly, and the controller did what a failed required phase must do: it tore the run down.

This is my defect, in the correction, not in the transport and not in the sealed runtime. The
mocked gate could not see it because its fake transport answers exit code 0 to every poll by
default, so a filesystem precondition inside a phase command is invisible to it; the Linux-shell
exercise ran probe commands through the launcher rather than the controller's own phase sequence.

## What the run did establish

The detached-phase mechanism behaved exactly as designed on the instance image. Every phase up to
and including the teardown phases completed on its first poll, with the remote wrapper's pid and
exit code recorded separately from the connection state, zero unreachable polls, and the
launch race guards (ignore HUP, wait for the started marker) returning a pid every time.

| Phase | Started after launch | Duration | Detached | Result |
|---|---|---|---|---|
| activation | 0 min | 3.5 min | | active |
| ssh_ready | 3.8 min | 2 s | no | ok |
| python_gate (3.12.3) | 3.8 min | 8 s | yes, 1 poll | ok |
| fresh_directory | 4.0 min | 8 s | yes, 1 poll | **exit 1** |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | 4.1 to 4.5 min | 8 s each | yes, 1 poll each | ok |
| evidence_download | 4.6 min | 6 s | no | ok |
| terminated, provider-confirmed | 6.6 min | | |
| independent confirmation | 6.9 min | | |

The collected archive is empty (no file existed on the instance yet: the failure preceded the
support transfer), and its hash verified. `FINAL_STATUS.json` was written by hand from the bundle
receipts because the analyzer needs the remote copy of the manifest, which was never
transferred; it records `pipeline_started: false`, zero receipts of every kind and
`quality_claim: null`.

## Bound identity, reverified before launch

Commit `a7bdd96`; manifest `dedaf7031dad7f6fd650c6d6ec593174d198e4761023c759dd386338cbc216a7`; seal
`e1dc6bd8c0b890e6d90e38488668aedfdd4aeb86a858f43a0c08274053752f4f`; project archive
`b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d` (identical to v3); assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` rebound from v3 by hard link.
The launch receipt (`operator_authorization.json`, `bound_controller_identity.json`) carries all of
them. Local reverification and live preflight both passed and are recorded in the bundle.

## Cost and teardown

Launch `1789722681.9`; provider-confirmed terminated at `1789723076.0` (billable upper bound
393.6 s, $0.141); independent confirmation at `1789723097.1`. Conservative estimate through that
confirmation: **$0.1486**, $0 model or API, not an invoice; well inside both limits.

## The correction this needs, not implemented here

Move the phase bookkeeping out of the remote root: a sibling directory such as
`<remote>-phases`, so the launcher never creates anything under `<remote>` and `fresh_directory`
keeps its meaning. Then make the Linux-shell check run the controller's actual early phase
commands, in the controller's order, through the launcher against a temporary root, asserting
exit code 0 for `fresh_directory` on a root that does not exist and exit code 1 on one that does.
The mocked transport should also model directory existence for that phase rather than answering
0 unconditionally. That is a small change to the operator-side controller and its checks only;
it awaits your instruction, and any further run needs a new authorization.
