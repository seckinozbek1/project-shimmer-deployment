# The gate on a rented machine (D-S75, D-329)

Built on `lane/eight` beside the eight-instance change and the declared type order (D-S78 item 2), so
one re-seal covers all three bound edits. Not yet run on a rented machine: the parity run comes first.

## What exists, and what is missing

The controller seals and runs three arms: B3 (the pipeline), B1 (the bare model, with replay
passes) and L (the launcher menu). Each is a loop launch: ledger, purpose, forecast, cap, reaper,
binding, the asset copy. None of them runs `scripts/verify_session1.py`. The gate runs only on the
laptop today, where it takes about two hours, with checks 321 and 325 the heaviest, and the side
gates about 20 minutes more (`gate_logs/s13b_post_side`, 10:16 to 10:34 for the six side gates and
the controller gate).

## The design

### 1. A fourth sealed arm, `G`

`arm` gains `G` (`ordinary_final_run.ARMS`). A G bundle is exposed only (it carries no test
material) and is never multi-round, never a protected test, and never in a batch, as arm L is
not; several gates are several launches, up to eight at once (D-S71 item 2).

The sealer (`tools/prepare_ordinary_final_run.py --arm G`) takes:

- `--gate-form full|side`. `full` runs the gate. `side` runs the side gates of
  `docs/loop/private/lead_tools/side_gates_at.sh`, declared as a fixed list in the sealer, not
  read from the private folder: `scripts/execution_topology_no_generation_gate.py`,
  `scripts/report_recommendations_no_generation_gate.py`, `scripts/localization_no_generation_gate.py`,
  `scripts/multi_round_no_generation_gate.py`, `scripts/final_integration_no_generation_gate.py`,
  `tools/cloud_run_checks.py` and `tools/ordinary_final_controller_gate.py`.
- `--gate-checks all|<n,n,...>` (full form only): the check numbers to run, each refused at sealing
  unless it is a check of the bound `CHECKS` list.
- `--known-red <n,n,...>`: the checks expected to fail, each a check of the bound list. Empty
  means none.

It seals a `gate` block in the manifest: the form, the checks, the known-red list, the exact argv,
and the digest of a `gate_source.tar` support file. That archive is `git archive` of the bound
commit, every tracked file (403 MiB at `594d3284`), so the gate runs on a fresh copy of the commit
under test, as D-S75 item 3 asks. Nothing untracked travels: no key, no `benchmark/keys`, no
`docs/loop/private`, no ignored local state.

### 2. On the instance

The runner (`tools/ordinary_final_run.py`) keeps every guard it has for the other arms, then:

- extracts `gate_source.tar` into its own folder and checks every member against the sealed list;
- points the model caches at the sealed asset archive (the asset copy MATCH, or the upload), with
  `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, as the B3 arm does;
- runs, in that folder, with the sealed runtime's Python: `python -X utf8 scripts/verify_session1.py
  --results <evidence>/gate/results.jsonl [--checks n,n]`. That is the laptop's command plus two
  flags (below). Network is not denied in this process, since checks 15 and 38 contact it on the
  laptop too; `--offline` is not passed, because the laptop does not pass it;
- for the side form, runs each declared side gate in turn the same way, one row per gate (name,
  exit code, seconds);
- brings back `gate/verify.log` (the full console output), `gate/results.jsonl` and
  `gate/summary.json` (the counts), through the evidence packer's existing credential scan.

### 3. Two flags on the gate, laptop and cloud alike

`scripts/verify_session1.py` gains, off by default so the laptop's run is unchanged:

- `--results PATH`: after each check, one JSON line with its number, title, status (PASS, WARN,
  SKIP, FAIL, ERROR, BADFIXTURE) and seconds, written as it goes, so a stopped gate still leaves
  what it finished;
- `--checks n,n`: run only those checks, in `CHECKS` order.

These change `scripts/verify_session1.py`, which is no bound controller file, and a check holds
both flags.

### 4. Integrity, and the report

`ordinary_final_run.assess_gate` passes integrity when the gate ran to its end and every check
outside the sealed known-red list is PASS, WARN or SKIP. A known-red check that passes is listed
as "now green" and does not fail the run. For the side form, every side gate exits 0. A check
that did not run (the session stopped) is `not_run`, and fails integrity.

The analyser (`tools/analyze_ordinary_final_run.py`) writes a `Gate` row: form, commit, checks run,
PASS, WARN, SKIP, FAIL with known red apart, now green, not run, instance type, minutes of the
gate itself and billed minutes. The row is never comparable with B3, B1 or L.

### 5. Everything else as every loop launch

Ledger, `--purpose`, `--forecast-minutes`, cap, reaper, the controller binding, the eight-instance
limit, the asset copy declaration and its receipt. A G launch runs no pipeline workload, and still
follows the money and reaper rules (D-S75 item 1).

### 6. Proofs, in the controller gate (`tools/ordinary_final_gate_arm_checks.py`)

- The sealed gate block and every refusal (unknown or empty checks, known red outside the bound
  list, an unknown form, a side form with checks, another source digest, a pin not in the lock, a
  field more, B1 fields, multi-round, a gate block in another arm); neutralised by admitting any
  block.
- The command is the laptop's with the sealed flags; neutralised by one that drops `--results`.
- The assessment; neutralised by one that reads every check as passed.
- The runner on a stand-in gate in a real child process, its environment clean, the chosen checks
  only, the side form, a tree member outside refused; neutralised by handing the runner's own
  environment to the gate.
- The gate's two flags on stand-in checks; neutralised by a gate that cannot tell checks apart.
- The sealer's reading of the bound gate's check numbers, and the analyser's Gate row.
- The declared type order (D-S78 item 2): faster types beyond the A10's price limit, more than one
  GPU, no poll, the first offered at its sealed rate, the GPU count the runner admits; neutralised
  by reading the declared order as the A10-first rule.

Not proven here: the sealer's archive of a whole commit (403 MiB, left to the first real seal for
disk) and the refusal of an arm G seal in a sealed run, which `prepare` checks before any work.

## What I do not know yet, and what the first cloud gate settles

- **Parity with the laptop.** A fresh copy of the commit lacks what the laptop has beside the
  tracked tree: ignored files, the generated `config/convention_registry.json`, untracked adapter
  weights (`tuning/auditor_final/canonical_adapter/adapter_model.safetensors` is untracked here),
  and models the gate may load that are not in the sealed asset archive. Some checks may FAIL or
  SKIP there for that alone. The first cloud gate runs on a commit the laptop has just gated, and
  its results are compared check by check before the cloud gate counts as the gate (D-S75 item 3
  says the same known-red list). Each difference is either fixed or declared, never absorbed.
- **The gate's own Python packages.** The sealed runtime lock serves the pipeline. The gate also
  imports what the laptop's environment has (fastapi and pypdf among them, and Node for the
  console proof). Either the gate's own pins from `requirements.txt` join the sealed wheels, or
  those checks are listed as known red on the cloud with the reason. I would add the pins, and
  measure.
- **The GPU.** Checks that load a model (the decoding gate in check 262, the embedding model)
  run on the A10's card instead of the laptop's 8 GB one, which should be faster but is not
  measured.

## Forecast

From the laptop's measured gate time, about 120 minutes, taken as the cloud time because nothing
faster is measured:

- full form: setup 20 minutes (asset copy MATCH, wheels, extraction) + gate 120 + evidence 10 =
  150 minutes on an A10 at 1.29 USD an hour = 3.23 USD, forecast 4.19 USD with the 1.3 factor, cap
  about 6.3 USD (1.5 times the forecast);
- side form: setup 20 + side gates 20 + evidence 5 = 45 minutes = 0.97 USD, forecast 1.26 USD.

The first runs measure both, and the next forecasts read the measured minutes.

## Order of the build

1. The gate's two flags and their check.
2. Arm G in the sealer, runner, assessment and analyser, the side form with it.
3. The proofs in the controller gate, neutralised.
4. CLAUDE.md (a new GATE-ARM-A line and CONTROLLER-BINDING), `docs/loop/stages/CLOUD_GATE_PLAN.md`
   updated to what was built.
5. The controller gate on exactly the changed files, then the lead's full gate.
