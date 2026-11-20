# Table tool switch: measurement plan (D-811)

Lane `lane/table-tool-measure`, from `lead/night-20261119` at ca5c63d6, 20 November 2026. Plan and launch folders
only: nothing is launched, no request is written, no answer key or benchmark data was opened, no figure exists.
This file is the bar, committed before any read.

D-811: "the tool is measured on the fresh table set; it stays in v1.0 only if that measurement holds."

**Amendment of 20 November (D-825 KARAR 2, option (b)), made before any read.** Seckin chose the small form: 30
tables, no pilot step, about 19.84 USD, not launched before his cap decision (KARAR 3). At the time of this
amendment no table has been split, built, staged, sealed, run or scored, and the set's look counter is still 0, so
no figure of any kind existed. The pilot part and its steps are removed (sections 3, 5, 6); the form check that
replaces the pilot's is in section 5; the bar (section 8) is unchanged word for word. D-789 asks for a pilot set
beside the validation set; for this fix Seckin's own choice of option (b) waives it, and the first-shard form check
takes the pilot's place.

## 1. The set

"The fresh table set" is `semtabfacts_aux_val` (D-798 item 4): SEM-TAB-FACTS dev and test, frozen by role B in
session BSTF2 on 19 November (16:05): 104 tables from 57 articles, 1,209 statements (524 supports, 461 refutes,
224 not enough info, counts only, from FOR_SECKIN), digest 04ed80a2, look counter 0, no overlap with SciTab. This is
the panel's "bilgi yetersiz ... Donduruldu: 104 tablo". Declaration: `config/semtabfacts_aux_val.json`; adapter:
`benchmark/adapters/semtabfacts/adapter.py`; report: `docs/loop/stages/SEMTABFACTS_ADAPTER_REPORT.md`.

It is the only table set built and frozen after the switch was written and never read: the SciTab sets are the gate
set (held, order 6), G1 halves A and B (read many times), the quick subset (read), the held v1.1 set (D-792 (2), never
touched) and `scitab_val2c` (D-798 (1), two-class, so it cannot show the not-enough-info class the tool's NONE reply
bears on).

## 2. Step 1: is reading it now allowed?

Yes, under the split in section 3.

- **Order 6** ("the fresh set is not read until the system passes both bars on clean development items") protects
  the gate's fresh read: the frozen gate set of GATE-SET-A, whose full read D-766 moved to v1.1. This set is not
  that set. Its declaration says `"side": "development"`, "validation material, never a gate set", never merged
  with SciTab (`never_with: ["scitab"]`).
- **Order 13** ("every held-out read is an opening, committed before the read, at alpha 0.05/2^k") covers held-out
  reads: `gate_score.claim_read_number` counts only `gate-claim-set` rows of HELDOUT_OPENINGS.md. A validation set
  is not held out, so no opening row and no alpha spending apply. The spirit of the order is kept anyway: this plan,
  with its bar, is committed before the first read, and the read moves the set's look counter from 0 to 1 for the
  tables read only.
- **D-789** (Seckin's standing rule: every fix on its own fresh validation and pilot sets, opened only for that
  check, sizes and looks recorded) is the binding constraint. The set was frozen before the switch existed (16:05
  against 0872ce14 at about 23:00 on 19 November), so it is fresh for this fix. But D-798 item 4 built it for the
  not-enough-info question (2c, D-590, D-642 (c)), which still needs its own fresh set. Reading all 104 tables here
  would leave none. So this measurement takes about a third of it, by a seeded, label-blind rule, and keeps the rest
  unread (section 3).
- **LAW-IV, keys.** The gold types stay with role B. The lead receives keyless staged workloads (STAGE-A), sends
  role B the extracted runs, and gets back counts and figures only.

Not allowed and not done: any read of the reserve, any pooled or averaged figure with SciTab, any use of the
validation figures to choose a threshold.

## 3. Split (seeded, label-blind, whole articles)

Run by role B with `external/s05/TABLE_TOOL_MEASURE/split_rule.py`, which reads only `split_rows` (table ids and
their article), never a gold type or a statement.

- Unit: the article (the adapter's `split_key` and `cluster`, the source file stem).
- Order: SHA-256 of `D-811 table tool measure 20261120:` + article, ascending.
- Validation: articles in that order until at least 30 tables. (Before the D-825 amendment a pilot of at least 6
  tables came first; it is removed, and the validation part now starts at the first article.)
- Reserve: the rest (about 74 tables). Not staged, not sent to the lead, not scored; kept for the not-enough-info
  fix and later per-fix sets.

## 4. The two arms

Switch on and switch off on the same tables, the same system otherwise, one bundle per table, exposed B3,
`compare: cells`, development side.

| Arm | Commit | Bound worktree | request_tools |
|---|---|---|---|
| on | 1277050c (lead tip; full gate ROUTE_GATE_1277050c ended exit 0) | `.claude/worktrees/gate-1277050c` | the twelve registry tools |
| off | 26d13e31 (lane/grouped-reseal) | `.claude/worktrees/gate-26d13e31` | none |

**Off by declaration, not by a code edit.** The config does not allow a per-bundle switch: JUDGE's contracts are read
only from the project root's `config/agent_contracts.json` (`scripts/orchestrator.py:105`, `judge_agent.CONTRACTS_PATH`,
`pipeline.py:5556`), and the sealer has no config overlay. A sealed bundle takes its config from its bound tree. So
the off arm is sealed from a commit whose tree does not declare it. 26d13e31 is that commit: `git diff 26d13e31
1277050c` touches one runtime file, `config/agent_contracts.json`, by exactly the `request_tools` line; every other
change is check modules (`cell_selection_checks.py`, `table_tool_checks.py`, `tool_audit_checks.py`), `tools/loop/
archive_closure*.py` and docs, none reached by a B3 workload. No controller-bound file differs (CONTROLLER-BINDING
holds for both). Each `launch.py preflight` checks that its bound tree declares the switch as its arm needs. A stated
limit: the full gate ran on 1277050c, not on 26d13e31; the lane table-tool-on ran the same 22 table checks with the
declaration removed (all pass, TABLE_TOOL_ON.md).

The alternative, a new commit from 1277050c with the line removed, is a config edit and needs a fresh gate; it is
not used.

## 5. Order and stop rules

1. Role B: split, build the full set with the semtabfacts adapter at either commit (the adapter is identical in
   both), stage only the validation tables with `tools/stage_workload.py`, return them keyless with
   `set_ids_for_lead.json` (request REQUEST_ROLE_B_TTM.md in `_xfer/lead_to_B/table_tool_measure/`).
2. The lead: `import_staged.py`, `make_plan.py --arm on` and `--arm off`, preflight and `archive_closure.py folder`
   on both, LEAD_GO.txt in both (only after KARAR 3), rename `chain.json.ready` to `chain.json`.
3. Each arm: request, seal, admit, then the validation shards V1..Vn.
4. **First-shard form check** (replaces the pilot's; keyless, no quality figure read):
   - Mechanical, by the chain: V2 waits for V1 to be *done*, and the chain calls a batch done only when every table
     of it has its evidence archive with `pipeline_exit_code` 0 and the instance is terminated and cleaned. A V1
     table that fails therefore holds V2 and every later shard of that arm.
   - Read by the lead from V1's keyless evidence while V2 runs (counts only, from each run's `audit/pairing_map.json`
     and boot log): no `[table-tool-request] STOP`; on the on arm `request_failed` under 10 percent of the requests
     made (`requests`; skipped requests, where no shown tool applies, are counted apart and are not failures), or,
     if the counters are not on the saved rows, a request reply read (`cited_cells` present) on at least 90 percent
     of the cell rows; minutes a table within 1.5 times the section 6 basis.
   - Any of these failing: the lead stops the later shards of both arms (`launch.py stop`, `chain.json` renamed back
     to `chain.json.ready`), traces the cause and reports; slower timing alone means the later shards are re-planned
     and re-sealed before they run. The V1 tables stay in the validation part either way; nothing is scored before
     every shard of both arms has ended.
5. Role B scores the validation part with `score_paired.py` (section 7).

## 6. Forecasts (tools/loop/step_cost.py, inventory 19 November 23:48 UTC, A10 1.29 USD an hour, x1.3)

Basis: DEV_scitab_rerun measured 2.95 + 0.072 minutes a claim a table (15 tables, max 4.35 minutes), switch off.
Kept with margin: 4.5 + 0.15 x statements (off) and 4.5 + 0.35 x statements (on, one generated request of at most 96
tokens a claim). A shard adds 25 minutes (boot, asset copy, install, return); shards hold at most 85 workload minutes,
so every guard cap (1.5 x forecast) is under the 5 USD step approval (D-708). Provisional, at the set's mean of 11.6
statements a table; `make_plan.py` recomputes from the real statement counts once the tables are staged.

| Step | off (26d13e31) | on (1277050c) |
|---|---|---|
| seal (30 bundles; the 36-bundle seal forecast kept, safe side) | 43 min, 1.20 USD | 43 min, 1.20 USD |
| V shards (30 tables) | 107 + 107 + 50 min, 2.99 + 2.99 + 1.40 USD | 3 x 103 + 51 min, 3 x 2.88 + 1.43 USD |
| arm total | 8.58 USD | 11.26 USD |

Total forecast 19.84 USD in 9 steps (D-825 option (b); recomputed by `make_plan.py` and step_cost.py after the
amendment), each at most 2.99 USD (caps at most 4.49 USD). Before the amendment: 23.76 USD in 11 steps, with the two
P1 steps (1.76 and 2.15 USD), whose step files are kept in each arm's `set_aside_pilot_0915/`. The forecast is the
IV.3 figure; DEV_scitab_rerun spent about 60 percent of its forecast. Not launched before Seckin's cap decision
(D-825 KARAR 3).

## 7. Readings and measures (GATE-SCORE-A)

Three readings of each arm, on the same claims:

- **argmax** (primary): each cell decision's saved answer probabilities read at the top answer (the
  DEV_scitab_rerun reading, `argmax_labels.py`; no threshold, nothing fitted). Needed because the bound trees
  declare no `cell_claim` threshold (`config/semantic_thresholds.json` choice_decision is empty since 19 November):
  every cell decision in both arms stays unsettled (`cells_no_threshold`), so the normal labels cannot differ.
- **no_leaning**: argmax, but a decision the declared TABLE-AUTHORITY-A rule would lower (a request reply read that
  cites no cell, or cites a cell the table lacks) counts as "cannot be settled", as a leaning scores without
  leanings (D-646). The off arm has no citations, so its no_leaning is its argmax.
- **normal**: the adapter's own labels, reported, never deciding.

Measures, each in each arm and as on minus off, with one paired cluster bootstrap by article (2000 draws, seed
20261109, 95 percent percentile intervals; a validation read, so no alpha spending):

- `macro_f1_3`: the set's declared measure, 3-class macro-F1 over supports, refutes, not enough info (its
  `report_line`), reported on its own line, never with SciTab.
- `table_acc`: the task's official form (per-table micro-F1 over the three classes, which is per-table accuracy,
  ABSTAIN wrong, averaged over tables); for the paired difference only, never compared with published figures
  (the adapter report's scoring note).
- `nei_recall`: the correct refusal rate on gold "not enough info".

## 8. The bar: what "holds" means

The switch **holds** for v1.0 when all three are true on the validation part:

1. **Form.** At least 90 percent of validation tables end with `pipeline_exit_code` 0 and an evidence archive in
   both arms (a table failing in either arm leaves both and is counted), and no boot refusal.
2. **Non-inferiority.** On the argmax reading, the 95 percent paired cluster interval of on minus off 3-class
   macro-F1 has its lower bound at or above -0.05.
3. **Same sign on the official form.** The same holds for `table_acc` (lower bound at or above -0.05).

Otherwise it does not hold, and the switch goes off for v1.0 (D-811), with the figures recorded. An interval too
wide to clear the margin counts as not holding: the burden is on the tool.

**Why non-inferiority, and why 5 points.** D-681 adds the tool for grounding and audit (one batched request, every
call in the audit trail, D-681 items 1 and 2; cell-grounded verdicts, D-642 (d)), not as a claimed accuracy gain;
D-811 keeps it "only if that measurement holds", that is, only if it does not make the table verdicts worse. 5
points is the largest loss the project already accepts against a reference (GATE-SCORE-A bar (b),
`gate_score.BAR_BELOW_CLOUD = 0.05`, D-S99, D-376). A gain is called only when the lower bound is above 0, and is
reported as a development-side indicator, never as a gate figure.

**Reported beside the bar, not deciding.** The no_leaning reading's difference: if it falls below -0.05 while the
bar holds, the NONE-reply consequence (TABLE_TOOL_ON.md "For the measurement": whether a column or figure id should
count as a citation) goes to Seckin with these counts, since changing the rule is his (D-715 item 2). nei_recall
in both arms. Minutes a table in both arms (the tool's speed cost).

## 9. Counts reported (TABLE_TOOL_ON.md "For the measurement")

Per arm, from `score_paired.py` (counts only): claims, tables, articles; labels by class; cell rows; on the on arm
rows with a request reply read (`cited_cells` present), replies citing no cell (NONE), replies citing a missing
cell; rows the rule would lower, by `no_cell_cited` and by `cited_cell_missing`; "not met" decisions the rule would
keep as records under argmax (would-be `claim_not_met`); and what the run itself did: leanings by `no_cell_cited`,
leanings by `cited_cell_missing` and settled "not met" records. The last three are expected to be 0 in both arms
while no threshold is declared (`leaning_of` returns no leaning for an unsettled decision whose reason is not
`below_threshold`); a non-zero count is reported as a finding. Per tool and per refusal reason from
`audit/judge_tools.jsonl` (counts only).

## 10. What this does not show

- About 30 validation tables (around 17 articles): the interval may be wide; a narrow margin is not claimed.
- The argmax reading is a reading of saved probabilities, not the shipped decision rule; the shipped v1.0 output,
  with no threshold, settles nothing in either arm.
- The cell threshold, when one is measured, is measured on its own development items, never on these.
- SEM-TAB-FACTS tables are not SciTab tables; the figure is never a SciTab score.
- One machine type (A10) in both arms; a cross-type comparison is refused (FACTORS-A).

## 11. Preparation readings (20 November, before any read)

- First readings (before D-825): `archive_closure.py folder` refused every B3 request of both arms on
  `tools/build_auditor_training.py` (also at 2a090652, so a closure finding for every B3 bundle). Fixed by
  lane/b3-closure (c36f589b on lead); nothing in this lane.
- After the D-825 amendment (provisional plan, 30 placeholder tables an arm):
  - `launch.py preflight`, both arms: worktree at its commit and clean, the bound tree declares `request_tools` as
    the arm needs, controller files LF, frozen model files present, ledger free, every guard cap under 5 USD, free
    RAM 3.8 GiB, free disk 12.76 GiB. Open only: the provisional plan (30 placeholder workloads, staged 0) and
    LEAD_GO.txt.
  - `tools/loop/archive_closure.py folder` (main checkout at e06ec26d), both arms: exit 0, 30 of 30 COMPLETE
    (304 archived files, 111 followed from `scripts/pipeline.py`).
- Role B's Part A (split, build, stage, return): request `_xfer/lead_to_B/table_tool_measure/REQUEST_ROLE_B_TTM.md`
  with the code bundle `shimmer_e958ecc4_to_1277050c.bundle` (279,530 bytes, SHA-256 ae7ea43a..., `git bundle
  verify` ok, prerequisite e958ecc4, head 1277050c on `refs/heads/ttm-b-head`), `split_rule.py`, `score_paired.py`
  and `argmax_labels.py`; start file `docs/loop/private/role_starts/start_b_ttm_a.cmd`, role_start_check PASS (5
  guards, 3 files, 7 request commands ALLOWED). Not started and not on ALLOWED_STARTS.json: the lead does both.

## 12. Folders (outside git)

- `external/s05/TABLE_TOOL_MEASURE/`: README.txt, split_rule.py and score_paired.py (role B), import_staged.py and
  make_plan.py (the lead), argmax_labels.py (copied from DEV_scitab_rerun), ROLE_B_REQUEST_DRAFT.md (superseded by
  the placed request), staged/ (empty).
- `external/s05/TABLE_TOOL_MEASURE_ON/` and `_OFF/`: launch.py and watch.py (from DEV_scitab_rerun), plan.json,
  requests.json, step_*.json and step_*.cost.json (provisional, V shards and seal only), inputs/ (inventory and lock
  copies), chain.json.ready (request, seal, admit, V1, V2 after V1 done, later shards in turn; only LEAD_GO.txt
  required), set_aside_pilot_0915/ (the first plan's P1 step files, kept). No LEAD_GO.txt, no chain.json, no request.