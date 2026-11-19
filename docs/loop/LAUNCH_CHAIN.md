# Launch chain

Seckin, 18 November 2026 13:40 ("Bekletilmesin"): nothing ready may wait, and that is a mechanism, not a rule.
`tools/loop/launch_chain.py` runs every 3 minutes (task ShimmerLaunchChain). It reads a declared plan file,
`chain.json`, placed beside `launch.py` in each launch folder under `external/s05/<FOLDER>/` (outside git), and
launches every step whose prerequisites are done, in the same move that finishes the step before it. A folder with
no `chain.json` is ignored. The 15-minute watchdog (`tools/loop/mechanism_watchdog.py`) checks the chain: any step
ready for more than 5 minutes with no launch writes ALERT.md and starts one chain pass. Check 517 proves each rule
below on fixture folders, each proof neutralised, failed, restored and passed.

## What the chain does in one pass

- Takes its own lock (an operating-system lock on `docs/loop/private/launch_chain.lock`; a pass that finds it held
  writes a `locked` trace line and launches nothing; a dead pass frees it with its process; the file is never
  deleted).
- For each folder (one folder's fault is traced, alerted and does not stop the others): runs `launch.py status`,
  reads the budget ledger, the admission file and the trace, and gives each step a state: `done`, `running`,
  `failed`, `launching` (a `launch_started` line of the chain, or a launch_intent or launch line in the ledger for
  the step's purpose with no termination, not yet in the status), `unconfirmed` (begun over 10 minutes ago and
  never seen; held until `--clear FOLDER:STEP`), `held` (a failed launch, a GuardRefusal or a failed preflight
  under 10 minutes ago), `waiting` (a prerequisite not met) or `ready`. A step in `launching` or `unconfirmed` is
  never launched again.
- For each ready step, in plan order: `launch.py preflight STEP` (the step named, so launch.py holds that step
  kind's laptop RAM floor through `tools/loop/launch_floors.py` and `config/launch_ram_floors.json`, LAUNCH-FLOORS-A;
  a failure traces, writes ALERT.md and launches
  nothing); then the status and the ledger are read again, and a step no longer `not launched`, or with a launch in
  flight for its purpose (the lead may have launched it meanwhile), is not launched (`already_launched`); then a
  `launch_started` trace line, then `launch.py <step>`.
- One launch at a time: before a launch the budget ledger lock (`budget_ledger.jsonl.lock`) must be gone; after a
  ledger step the chain waits until the lock is gone and the status leaves `not launched`. A GuardRefusal counts
  only in the step's own `controller_logs`, in bytes written after this launch began. The guard raises it when it
  cannot take the ledger lock (`tools/loop_budget_guard.py` acquire_lock), before its decision, before the
  launch_intent line and before any machine is created. A refused step is held 10 minutes and alerts after 3
  refusals in a row.
- A request waits, right before its call (after preflight and the fresh reading), until the ledger is quiet (no
  lock, no launch or launch_intent line and no chain launch in the last 60 seconds) and is written in the
  foreground; its seal starts at once with nothing between. Before the call the chain writes its marker
  `request.launch_chain.json` beside the request folder with the call's window (start, and end once it returns),
  and retires it (`done_at`) once the done file is there. A request folder is the chain's only when the marker
  names it and the folder was created inside that window; only such a folder is ever renamed aside
  (`request_stale_<HHMM>`, never deleted): when it exists without its done file and the marker is not retired, or
  when the seal exits non-zero saying its read copy is stale (an exit 0 never counts). Any other request folder,
  even one made by hand after an old marker, is left alone and alerted. Three stale refusals in a row alert. One
  request at most a pass.
- A ledger launch call that exits non-zero or times out after `launch_started` is held as `unconfirmed` until
  `--clear`, with an alert: a detached controller may still be waiting for an instance type (up to 30 minutes)
  before it writes any intent line. It is never retried on a timer.
- No link or junction is followed: a launch folder that is one, and a controller log reached through one, are
  skipped. `requires.repo` must be the main checkout or one of its worktrees (`git worktree list`).
- No process blocks another (Seckin, 18 November 2026 20:37): `launch.py admit` starts the admission detached and the
  pass goes on at once; the parts are launched by the first reading that finds the admission file showing `admitted`
  equal to `requests` (the same pass when it is already there, else a later pass). The admit counts as `launching`
  while its staging folder exists or `admit.log` was written in the last 15 minutes, else for `admit_wait_minutes`
  after its launch; after that, with no full admission, it is `unconfirmed` (held, with an alert, until `--clear`).
- A ledger step with `watch` true gets `watch.py <step>` started detached beside it.
- The pass budget is checked before each reading and each launch: after 50 minutes no new step is begun, except
  the seal that follows the request this pass just wrote. The longest step begun just before that is a request and
  its seal at their timeouts, 99 minutes (the arithmetic is in the launch_chain.py docstring); the worst pass is
  about 152 minutes, under the task's 180-minute limit.
- It never raises a cap, never edits `launch.py`, and never deletes anything. A step that ended with a non-zero
  `workload_return` exit code is `failed`: ALERT.md once, the steps after it wait for the lead.
- One trace line per action in `docs/loop/private/mechanism_trace.jsonl` (mechanism `launch_chain`), and one `ok`
  summary a pass. First readiness times are kept in `docs/loop/private/launch_chain_state.json`, written only under
  the chain lock (a real pass, or the watchdog when no pass holds the lock). `--dry-run` writes nothing.

## The file format (template)

```json
{
 "chain": 1,
 "note": "the README command order this follows",
 "steps": [
  {"step": "request", "kind": "request", "done_when": {"exists": "request/seal_request.json"}},
  {"step": "seal", "kind": "ledger", "after": ["request"], "watch": true,
   "controller_logs": ["request.run/controller_detached.log"]},
  {"step": "admit", "kind": "admit", "after": ["seal"], "admission": "admitted/admission.json", "admit_wait_minutes": 20},
  {"step": "partA", "kind": "ledger", "after": ["admit"], "watch": true,
   "controller_logs": ["admitted/BUNDLE_A/controller_detached.log"]},
  {"step": "partB", "kind": "ledger", "after": ["admit", {"step": "partA", "state": "launched"}], "watch": true,
   "purpose": "my-run-partb", "controller_logs": ["run_partB/BUNDLE_B*/controller_detached.log"],
   "requires": [
    {"file": "C:/path/to/a/role/hand-back.json"},
    {"commit": "3ca7fe8e", "ref": "HEAD"},
    {"folder": "ROUTE_GATE_90588740", "step": "part", "state": "done"}
   ]}
 ]
}
```

- `step`: the argument `launch.py` takes (for a ledger step, a key of its PURPOSES; `launch.py status` prints a line
  for it). Steps are listed in order; a prerequisite must name an earlier step.
- `kind`: `request` (foreground; done when `done_when.exists`, a path relative to the folder, exists), `admit`
  (done when the admission file, default `admitted/admission.json`, has `admitted` equal to `requests`), or
  `ledger` (seal or part: done when status says `ended` with `workload_return` exit code 0; running while it has a
  ledger launch line and no termination). A batch part, one whose `plan.json` `bundles[step]` (or a literal
  `BUNDLES` in launch.py) names more than one bundle, writes no `workload_return`: it is done when its phase is
  `terminated_and_cleaned` with `TERMINATION_VERIFIED` and no `controller_failure`, and `admitted/<first>/batch/`
  holds one `NN_*/collected_evidence.tar.gz` per bundle whose `evidence/result.json` has `pipeline_exit_code` 0;
  otherwise failed, the reason naming the count (e.g. "7 of 10 batch evidences").
- `purpose` (ledger steps, required): the ledger purpose, of the form `[a-z0-9][a-z0-9-]{0,39}`; by default read
  from `launch.py` PURPOSES as a literal (never run). A ledger step with none is refused.
- `controller_logs` (ledger steps): the step's own controller_detached.log paths (globs allowed), where a
  GuardRefusal is looked for; a seal right after a request defaults to `request.run/controller_detached.log`;
  a ledger step after admit must declare them. The GuardRefusal alert quotes the refusal line it found.
- `after`: prerequisite steps of the same folder. A plain name must be `done`; `{"step": X, "state": "launched"}`
  is met once X has a ledger launch line (running, done or failed), for steps that may run beside each other.
- `requires` (optional): external prerequisites, all of which must hold: `file` (an absolute path with no `..`
  that must exist, for example a role hand-back), `commit` (7 to 40 hex digits, an ancestor of `ref`, default
  `HEAD` of the main checkout, that is on the lead tip; `repo` may name a worktree of the main checkout), `folder` plus `step`
  (a step of a sibling launch folder, by name, in `state` done or launched).
- Every folder path (`done_when.exists`, `admission`, `controller_logs`) is relative to the folder; `..` and
  absolute paths are refused, and the whole chain.json with them.
- `watch` (ledger steps, default true): start `watch.py <step>` detached after the launch.
- `"template": true` (top level, OPEN_ITEMS 159): the folder is a template copied by hand; the chain never plans
  or launches it (its copies carry no marker).
- `admit_wait_minutes` (admit, default 20): how long after its launch an admit with no visible work still counts
  as launching; the chain never waits on it.

## Commands

```
py -3.12 -X utf8 tools/loop/launch_chain.py --dry-run            # every step's state and what would launch; writes nothing
py -3.12 -X utf8 tools/loop/launch_chain.py                      # one real pass
py -3.12 -X utf8 tools/loop/launch_chain.py --clear FOLDER:STEP  # release a held step (an existing step, under the lock)
powershell -NoProfile -ExecutionPolicy Bypass -File tools\loop\register_mechanism_tasks.ps1   # registers ShimmerLaunchChain
```
