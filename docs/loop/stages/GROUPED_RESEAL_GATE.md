# Grouped re-seal gate (lane/grouped-reseal), lane report

Written 19 November 2026 on branch `lane/grouped-reseal` (from lead/night-20261119 5a4c43db, a fast-forward of the
lead tip; later the lead tip 406d5cdc merged in). No seal, no launch, no spend, no push, no merge into the lead branch.

## What the commit holds

The lead tip 5a4c43db plus exactly these cherry-picks, everything that waits for a re-seal (CONTROLLER-BINDING):

| Lane commit | Source | What |
|---|---|---|
| 6ff16ade | lane/reply-count-derived 8889257f | D-810: the replay reply count includes the derived prompts the pass declares (`tools/ordinary_final_run.py`, bound runner) and its controller test (`tools/ordinary_final_controller_checks.py`) |
| 21cb2530 | lane/gnn-train-archive-fix 65dbeb4a | the sealer's `RUNTIME_FILES` carries `tools/ontology_training_graphs.py` and `tools/ontology_training_leakage.py` (`tools/prepare_ordinary_final_run.py`, bound sealer); a listed file the commit does not hold is not carried, so on this commit nothing changes in the archive until those files arrive |
| d03812f1 | lane/gnn-train-archive-fix e008c744 | ARCHIVE-CLOSURE-A: `tools/loop/archive_closure.py`, `tools/loop/archive_closure_checks.py`, check 660, the launch chain's closure preflight (`tools/loop/launch_chain.py` `archive_problems`) |
| 00cef04e | lane/gnn-train-archive-fix 1a2726d7 | `docs/loop/stages/GNN_TRAIN_6F48_FAILURE.md`; archive_closure finds a pass by any `SCHEMA*` constant |

Not brought in: the lane/v105-c3b lineage under lane/gnn-train-archive-fix (7dec7a2d and below, 6f48d5ed, 0989d296),
so no checks 600 to 606 or 616 to 619 and no GNN training pass.

Conflicts, resolved by hand in d03812f1: `scripts/verify_session1.py` (the lead's check 585 kept; only the check 660
function and its CHECKS row added, none of 600 to 606) and `docs/CLAUDE_REFERENCE.md` (the lead's LAUNCH-CHAIN-A
text with the chain admit retry of 02d1da49 kept, the ARCHIVE-CLOSURE-A sentence appended). `tools/loop/launch_chain.py`
merged cleanly beside the admit retry.

## Checks run alone (the whole gate is never run on the laptop)

- Check 660 (`archive_closure_checks.run_group(660)`): PASS, 7.8 s. Fixture refused the two absent tools files
  (exit 1), optional and latent apart, complete once carried, the constants rule equals the sealer on HEAD, HEAD
  holds no GNN training pass; neutralised, failed, restored, passed.
- Check 517 (`launch_chain_checks.run_all()`): PASS, 330 s, 38 proofs (the admit retry proofs among them), each
  neutralised, failed, restored, passed, no provider call.
- D-810 controller tests, network denied as `tools/ordinary_final_controller_gate.py` runs them: the new
  `test_a_replay_pass_counts_the_derived_prompts_it_declares_and_a_short_set_still_fails`, the R19 (v) B1
  assessment test and the D-061 replay test pass; their 5 neutralisation proofs (`b1_observation`, two
  `replay_derived`, `is_replay`, `replay_error`) each pass, fail with the mutant called, restore, pass.

## The table tool switch (D-681 item 6, D-811): on, from lane/table-tool-on 0872ce14

The gate commit is now 0872ce14: lane/grouped-reseal fast-forwarded to lane/table-tool-on, one commit directly on
26d13e31 (verified a descendant, only that lane's commit). It declares the twelve registry tools as JUDGE's
`cell_claim` `request_tools` and makes the checks answer the request (docs/loop/stages/TABLE_TOOL_ON.md). The
"no longer becomes its finding" seen below is the declared rule, not a defect: a request answered NONE cites no
cell, so TABLE-AUTHORITY-A lowers the verdict to a leaning and a lowered "not met" writes no record; a judge that
cites cells keeps the finding as with the switch off. Expect fewer claim_not_met records with the switch on; D-811's
fresh-table measurement decides whether it stays in v1.0.

Run alone again on 0872ce14 by this lane: 388 to 394 and 420 to 424 PASS (394 and 424: 5 proofs each; boot reads
the ratified amendment INFRA-056, no refusal); 326 PASS (43 proofs) and 544 PASS (3 proofs). Binding:
`config/agent_contracts.json` is not controller-bound (no re-seal of existing bundles forced), but every bundle sealed
from 0872ce14 carries it, so its cell claim runs ask the table tool request.

The earlier attempts on this lane, kept for the record:

The switch is one config declaration: `request_tools` on JUDGE's `cell_claim` task in `config/agent_contracts.json`,
naming registry tools of `config/table_tools.json`. INFRA-056 (operator approved, `change.setting` names exactly that
declaration) covers it, so no new amendment and no constitution edit would be needed. Tried in this worktree with all
twelve registry tools declared, never committed:

- boot accepts it: `tool_registry.request_ratified()` returns INFRA-056, `startup_refusals('cell_claim', names)` is
  empty; check 388 (the boot refusal check, 8 proofs, on the real boot too) PASS; 389 to 393 PASS; 420 to 423 PASS.
- check 394 (G, "the table tool off is the measured run") and check 424 (E, "no shipped contract declares
  request_tools") fail at their baseline: both assert the shipped-off state.

Second try (the lead asked for the switch on, with 394 and 424 asserting the declared state): both checks were
rewritten so the off-path proofs stay on a fixture contract and the shipped declaration is held to JUDGE's
cell_claim alone, ratified, with no boot refusal (two new neutralisations each); 394 and 424 then passed their
baselines, 424 in full. All 38 gate checks that name a cell-claim module were run alone with the switch off (37
PASS, 325 the known red) and on: 326 and 544 then fail at their baseline. The real phase 5.5 now asks the table tool
request once per claim. On the fixture backend that call fails (`backend_failure`); with the fixture judge answering
NONE (the table tool checks' own stub), the decided "not met" claim at 0.9 no longer becomes its finding (row
not_met 0, kept 0, no not-promoted finding, no reader entry), against 1, 1, 1 with the switch off. That is a change
in what the product path keeps, not only in the checks' expectations; making 326 and 544 pass would weaken what they
protect, or needs the request path traced and fixed first. So the switch stays off, every change reverted; it needs
its own lane (the request path's effect on a decided claim, then 326, 394, 424 and 544 for an on state, the
TABLE-TOOL-A text, which tools to declare), gated, then measured on the fresh table set as D-811 requires.

Binding: `config/agent_contracts.json` is not a controller-bound file (not in the sealer's CONTROL_FILES), so it
forces no re-seal of existing bundles. It is in every project archive (`config/` is a runtime prefix), so a bundle
sealed from a commit with the switch on carries it and its cell claim questions change.

## The QUICKSCORE2 scoreboard row (G-20261119-2200)

The third Shimmer reading on quick subset 0127b080 (QUICKSCORE2, code 426ef44c, role B's score of 19 Nov 01:09,
HELDOUT_OPENINGS.md line 17) had no row in `docs/loop/private/GATE_SCOREBOARD.md`. Two benchmark lines were added at
the top (newest first) in the form of the others; the file is private, outside git, so this commit does not carry
it:

- ContraDoc: 55.0 [40.0, 70.0], n 40, VOID on integrity (26 of 40 undecided); (a) 7.5 points short, interval not
  above zero / (b) 30.0 points short; 403 machine minutes (four parts summed), 6.0 items an hour, 8.66 USD.
- SciTab 3 classes: 19.0 [14.2, 22.7], n 78, VOID on integrity (78 of 78 undecided); (a) 46.8 points short /
  (b) 57.7 points short; 86 minutes, 54.4 items an hour, 1.85 USD.
- Both: gpu_1x_a10 at 1.29 USD an hour, us-east-1; cumulative 295.58 USD after the run (budget ledger terminations
  summed, the convention that gives the 15 Nov row's 235.88); B1 and cloud as on the earlier lines; evidence
  external/s05/DEV_contradoc_full and DEV_scitab_dev (record).

The public progress page `docs/progress/index.html` lives only on public main, built in the push clone by
`tools/progress_charts.py` (a public-only kept file); its last push is 11 Nov, so standing order 8 already read
BROKEN (the 13 and 15 Nov rows are newer) and still does. The page built to a scratch folder with that script from
public main and the updated scoreboard shows both QUICKSCORE2 lines in its benchmark table, with no role folder path;
its self-test passes 61 of 61. Standing order 7 (metric, setting and interval on every row) holds: 7 rows. docs/RESULTS.md,
the README's results page, already gives both figures, "void on integrity, does not count, below both bars".

## The launch folder

`external/s05/ROUTE_GATE_0872ce14` in the main checkout (outside git), bound to 0872ce14, bundle G1119_0872_FULL,
purposes route-gate-0872ce14-seal and route-gate-0872ce14-part. The commit after it on lane/grouped-reseal changes
only this report (docs/loop/), so the gate does not cover it; push the gated 0872ce14 and let the report ride the
next push, or re-gate. ROUTE_GATE_eba76f56 and ROUTE_GATE_26d13e31 are SUPERSEDED (a SUPERSEDED.txt in each, never
armed). At build: inventory exit 0, preflight all checks hold (free RAM 2.96 GiB, free disk 23.23 GiB),
archive_closure COMPLETE (10692 files, 427 followed), chain.json.ready parsed with its file prerequisite present.
The general form: Modelled on ROUTE_GATE_e958ecc4: the same
launch.py, watch.py, step files, requests.json (arm G, full form, every check, the same eleven known reds), README;
bound to the branch tip through its own worktree `.claude/worktrees/gate-<short tip>` (detached at the tip, LF by
the repository's core.autocrlf false, the five untracked frozen model files hard-linked from the main checkout's own
copies and SHA-256 checked against config/final_models.json, no junction and no link into the main checkout; shared
folders through SHIMMER_MAIN_CHECKOUT). Purposes `route-gate-<short tip>-seal` and `route-gate-<short tip>-part`.
Its README records the inventory, preflight and archive closure output.

The plan file is `chain.json.ready`: the chain reads only `chain.json`, so nothing runs until the lead renames it.
Its first step (request) also requires the file
`external/s05/ROUTE_GATE_e958ecc4/run_part/G1119_E958_FULL/TERMINATION_VERIFIED.json` (absolute path in the file):
the e958 part has ended, green or red. A `folder`/`step` prerequisite would wait only for a green e958 part, and
`launched` would not wait at all. The e958 gate ended green on 19 Nov (467 PASS, only the eleven known reds), so
this prerequisite already holds.

The README audit fixes join this commit: the README push needs a green gate on its own commit. Merged as the lead
tip 406d5cdc (lane/readme-audit-fixes 253ed2a1 merged into lead/night-20261119) in c740d0a6, so the lead branch
fast-forwards to this branch. The README-reading checks run alone on this report's commit: see the README of the
launch folder.

## Forecast (tools/loop/step_cost.py, fresh provider inventory of 19 Nov, A10 at 1.29 USD an hour, x1.3)

| Step | Minutes | Without measures | With measures |
|---|---|---|---|
| seal | 25 | 0.70 USD | 0.70 USD |
| part | 60 (56 with the asset copy) | 1.68 USD | 1.57 USD |
| total | | 2.38 USD | 2.27 USD |

Each step is under the 5 USD per-step pre-approval (D-708, D-749); `CEILING_STOP_USD` 3.40 on the gate's running
total (cap 3.5), as in e958.

## Lead commands

Before arming: merge `lane/grouped-reseal` into the lead branch (a fast-forward while the lead tip is still
406d5cdc), so the main checkout's launch chain carries the archive closure preflight; if the lead tip has moved,
rebuild the folder on the merged tip instead (a new commit needs its own seal). If the e958 gate shows new reds the
lead accepts as known, change `--known-red` in requests.json before the request is written.

Arm (from the main checkout; `$t` is the short tip):

```
$t = '0872ce14'
$f = "external/s05/ROUTE_GATE_$t"
py -3.12 -X utf8 "$f/launch.py" preflight
py -3.12 -X utf8 tools/loop/archive_closure.py folder $f
py -3.12 -X utf8 tools/loop/launch_chain.py --dry-run
Rename-Item "$f/chain.json.ready" chain.json
```

The chain then waits for the e958 part's TERMINATION_VERIFIED.json and runs request, seal (watch), admit, part
(watch) one at a time; `launch.py status` shows each phase and the running total.

After a green result (execution integrity true, only the known reds failing, no unexpected check), the clean export
route of PUSH_RECORD (entries of 18 November) and D-783, only on Seckin's push word and with origin confirmed as
project-shimmer-deployment:

1. In the clean push clone `<USER_HOME>\local\shimmer-push-clone`, branch export-1115: fetch the gated commit,
   then `tools/loop/export_public_tree.py` from it with `--public-ref loop-v1 --cutoff loop-v1` and the four
   `--keep` paths, report to the lead's scratchpad (`export_<t>.json`); one snapshot commit of loop `<t>`.
2. Check the snapshot tree's delta equals the source delta from the last exported commit to `<t>`. Rebuild the
   progress page in the push clone (`tools/progress_charts.py --root <the loop worktree at t> --scoreboard
   docs/loop/private/GATE_SCOREBOARD.md --ledger docs/loop/private/budget_ledger.jsonl --item-sets <the item-set
   folder> --out docs/progress`, the private files named from the main checkout) so it shows the 13, 15 and
   19 Nov rows (G-20261119-2200), and commit it beside the snapshot; standing order 8 holds again only after that
   push.
3. Scans: precommit_scan of the delta, guard_secrets (staged and whole tree), added-line key patterns,
   credential-named literal assignments, rewrite rules, personal paths and emails, answer-key or held paths, em and
   en dashes.
4. Plain fast-forward push of main (the hook `tools/loop/public_pre_push.py` scans the added lines), annotated tag
   `code-2026-11-<dd>-<x>`, push the tag; `ls-remote` shows main and the tag peeling to it.
5. A PUSH_RECORD row ("the code snapshot of loop `<t>`"), so sync_watch counts the gate as pushed; then
   backup_records and backup_private.

A red result: no push; the reds go to a lane, as for 0acab665.
