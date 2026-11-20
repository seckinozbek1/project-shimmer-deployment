# GNN_TRAIN_6f48d5ed: why the paid training launch stopped, the fix, and the relaunch

Lane lane/gnn-train-archive-fix, 19 Nov 2026 (evening, +0300). Nothing was launched, sealed or spent by this lane.

## What happened

The D-800 GNN training step (launch folder external/s05/GNN_TRAIN_6f48d5ed, bound commit 6f48d5ed, bundle
GNN6F48_TRAIN) ran its seal and its training launch. The training workload ended with exit 2:
workload.stderr.log holds one line, `replay stopped: FileNotFoundError: ... /home/ubuntu/shimmer-ordinary-final/project/tools/ontology_training_graphs.py`;
result.json gives exit_code 4 for checkpoint train, reply_records 0, reasons `b1_checkpoint_failed:train`,
`b1_reply_record_missing:train`, `b1_reply_record_count:train`. No weights and no measurement came back.

Spent (docs/loop/private/budget_ledger.jsonl, terminations):

| Launch | Purpose | Time (+0300) | USD |
|---|---|---|---|
| seal (route S) | gnn-train-6f48-seal | 18:20:45 to 18:44:08 | 0.516 |
| training (B1) | gnn-train-6f48-train | 20:05:08 to 20:23:21 | 0.4085 |
| total | | | 0.9245 |

D-800 approved 5.81 USD for the step in all, so 4.8855 USD remain.

## Cause

The project archive the instance gets is built by the sealer from a fixed rule, not from what the workload uses:

- tools/prepare_ordinary_final_run.py:67-68 at 6f48d5ed: `RUNTIME_PREFIXES = ('scripts/', 'config/', 'corpus_ingest/')`
  and `RUNTIME_FILES = ('requirements.txt', 'genesis.md', 'tools/run_local_demo.py', 'tools/score_corpus.py')`;
  `archive_names` (:75-84) keeps only those plus `ARCHIVE_EXTRAS` (:62, benchmark/adapters/ and
  benchmark/baselines/), `runtime_source` (:87-100) archives that list from `git archive` of the bound commit, and
  :1196-1197 add two named tools helpers. Nothing else under tools/ travels.
- The training code reads two tools files at run time:
  - scripts/ontology_train.py:83 puts `tools/ontology_training_graphs.py` in `CODE_FILES`; `train` hashes it into
    every weights record at :525 (and again at :530); scripts/ontology_training_set.py:98 names the same builder.
    This is the FileNotFoundError: the record is built after the first seed's training, so the launch paid for
    boot, install and one seed, then stopped.
  - scripts/ontology_train.py:399-407 (`_leakage_features`, called by `structural_overlap` at :534) imports
    `tools/ontology_training_leakage.py`. It would have failed next.

The file was in commit 6f48d5ed (`git cat-file -t 6f48d5ed:tools/ontology_training_graphs.py` is a blob); it was
left out by the rule. The sealed manifest confirms it: execution_manifest.json project_files (312 files) holds
exactly four tools files (auditor_classifier_lora_stable.py, auditor_linear_core.py, run_local_demo.py,
score_corpus.py). No check before the seal or the launch compared what the workload reaches with what the
archive holds; checks 605 and 606 ran the pass from the full repository, where both files exist.

Every other file the training pass reaches is inside the archive (traced with the new preflight below from
benchmark/baselines/replay_prompts.py and benchmark/baselines/ontology_train_pass.py: 65 files followed on the
sealed manifest; the only other names are tools/cloud_run_common.py, imported inside a try at
scripts/ontology_train.py:448 with a fallback, and tools/build_auditor_training.py, reached only through the
auditor training pass, not this one).

## Fix (lane/gnn-train-archive-fix)

1. Commit 65dbeb4a, tools/prepare_ordinary_final_run.py: `RUNTIME_FILES` adds `tools/ontology_training_graphs.py`
   and `tools/ontology_training_leakage.py` (a listed file the bound commit does not hold is not carried). This
   is a bound controller file (the sealer): every bundle needs a re-seal at a commit holding it, and the relaunch
   below is a fresh seal at the new commit.
2. Commit e008c744 (and the follow-up on the same branch), ARCHIVE-CLOSURE-A: tools/loop/archive_closure.py.
   Before any seal or launch it follows each request's workload from its entry files (arm G: the gate; B1 replay:
   replay_prompts.py and the pass module whose SCHEMA* constant names the pass file's schema; B1: bare_model.py;
   otherwise the pipeline) through imports, config-declared `module:function` names and literal `.py` paths,
   reading only the parts of each file that run, and refuses (exit 1, each missing file named) when one lies
   outside the archive: the sealed manifest's project_files when the folder holds one, else the bound commit's
   sealer rule read from its constants. An import inside a try is listed and not refused; a file reached only
   through another pass is latent and not refused. tools/loop/launch_chain.py runs it after `launch.py preflight`
   for every folder with requests.json and launch.py and launches nothing on a refusal; the relaunch folder's own
   `launch.py preflight` runs it too. Gate check 660 (tools/loop/archive_closure_checks.py), run alone: PASS
   (fixture repository refused at the first commit naming exactly the two absent files, complete once the sealer
   carries them, optional and latent apart, an import in an uncalled function not followed; on HEAD the constants
   rule equals the sealer's archive_names and the GNN pass closure is complete; neutralised, failed; restored,
   passed). Check 517 (launch chain) run alone after the hook.

## Proof

- On the failed folder's sealed manifest: `archive_closure.py folder external/s05/GNN_TRAIN_6f48d5ed` gives
  REFUSED, naming tools/ontology_training_leakage.py (imported from scripts/ontology_train.py) and
  tools/ontology_training_graphs.py (named by path from scripts/ontology_train.py and
  scripts/ontology_training_set.py), and nothing else. It would have stopped this launch before the seal.
- At the fix commit, `archive_closure.py commit 65dbeb4a --entry benchmark/baselines/replay_prompts.py --entry
  benchmark/baselines/ontology_train_pass.py`: COMPLETE, 312 archived files, 69 files followed.
- On the relaunch folder external/s05/GNN_TRAIN_R2: COMPLETE (in its `launch.py preflight`).
- Other folders, read-only, 19 Nov evening: external/s05/ROUTE_GATE_e958ecc4 (sealed and admitted, arm G from the
  whole tree): COMPLETE, 10666 files, 421 followed. shimmer-roles/_xfer/lead_to_V/syn_label/V_SYNLAB2 (not yet
  sealed, rule at 5674e3aa): COMPLETE, 302 files, the label pass neg_synth_label_pass.py found by its SCHEMA_V2,
  59 followed.

## Relaunch (prepared, not armed)

Folder external/s05/GNN_TRAIN_R2, bundle GNNR2_TRAIN, purposes gnn-train-r2-seal and gnn-train-r2-train, bound to
the tip of lane/gnn-train-archive-fix (the commit holding this file), worktree .claude/worktrees/gnn-train-archive-fix
detached at it, the frozen model files hard-linked after a SHA-256 check. Same signed set, validation block, bar and
opening byte for byte; the pass file rebuilt at the new commit (only code_commit and written_at change). The
running total counts the first folder's 0.9245 USD against D-800's 5.81 USD.

The opening (declared/open_train_d800.json) expires 2026-11-20T15:36:00+03:00. After that the lock refuses and a
new opening from Seckin and a rebuilt pass file are needed.

Steps (from the folder, py -3.12 -X utf8): `launch.py preflight` (includes the archive closure), `launch.py check`,
optionally `launch.py inventory` (read-only, no spend), then rename chain.json.ready to chain.json (the chain runs
request, seal with watch, admit, train with watch), then `launch.py result` by hand.

Forecast (tools/loop/step_cost.py on step_seal.json and step_train.json with inputs/provider_inventory.json, A10
gpu_1x_a10 at 1.29 USD an hour, x1.3):

| Step | Minutes | USD with measures | USD without |
|---|---|---|---|
| seal | 30 | 0.84 | 0.84 |
| train | 45 (asset copy) | 1.26 | 1.37 |
| both | 75 | 2.10 | 2.21 |

Left under D-800: 4.8855 USD; after the forecast 2.79 USD would remain. Each step is under the 5 USD per-step
pre-approval; at the guard's 1.5x cap the worst case is 1.26 + 1.89 = 3.15 USD, still inside what is left. The
first launches ran 23.4 min (seal) and 18.2 min (training, stopped early), inside these forecasts.

## Merge note

lane/gnn-train-archive-fix is based on 0989d296 (lane/v105-c4-train-launch: lead tip da3c8055 plus lane/v105-c3b
and the training pass). Merging it into lead/night-20261119 also brings that lineage (which is why
tools/ontology_training_graphs.py is not on lead/night today). Check 660 is numbered above lead/night's 652;
renumber if another lane took it.
