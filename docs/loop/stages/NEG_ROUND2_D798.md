# Negotiation round 2 on the D-798 validation set (D-843, D-845, D-846, D-848)

20 November 2026, 14:55 +0300, lane/neg-round2-d798 (from lead/night-20261119 at a7f02e71; code at fea8347d, the bound commit of every folder below). Prepared only: nothing
launched, sealed, requested or started, nothing spent. No key, label, card, role folder or benchmark/keys opened.
Read: code, prompts config, the C4 prompts files' items (system input) and the C4 step records, by form only.

## 0. What the prompt and the answer hold now, and what round 2 adds (D-846, D-848)

"Now" is the chain C4 ran (stepwise, choice_first, compare); lines at a7f02e71 unless marked at this lane's commit.
The C4 items are the 64 of c4pilot_1 and c4val_1 (their prompts files, counted by form).

| # | Input or output | In the prompt or answer now | Do the C4 items carry it | Round 2 adds | Measured by |
|---|---|---|---|---|---|
| 1 | Comments, explanatory notes, parties' rationales | Partly. No notes or comment field reaches the chain. A position's own quote, which often holds its reason ("because ..."), is shown one position at a time in the compare step (`neg_advisor_prompt.json:54`, `{quote}`). Document layers (comments, footnotes) have a reader path (`neg_advisor.py:432` `layers_from_reader`), but only for read documents | No notes field. Positions hold id, party, round, article, proposal, quote and source only (647 positions). 0 layers in 64 items. Rationales exist only inside quotes | #310 `party_frame` shows every advised-party quote and the article's other quotes, with their reasons, before every question. #311 `reason_field` asks for the mechanism and the effect, resting on that shown text. No notes field is invented | Not measured. The reason field is recorded and counted by form (refused `no_mechanism`, `no_effect`), never a bar figure |
| 2 | Earlier rounds: who proposed what, what closed, what fell, which concession | Partly. The compare step shows the position's round and the item's round (`neg_advisor_prompt.json:54`, `{position_round}`, `{round}`). The previous round's index reaches only the plain prompt (`neg_advisor_prompt.json:7`), not the chain. Closed (`agreed`) and fallen articles never reach the chain | Rounds yes: 225 of 647 positions are from an earlier round. `previous_index` is in 49 of 64 items. `agreed` is on every article. Who proposed a text is not declared. Earlier rounds' texts are not in the items | #310 history (the overlap the lead names): rounds on record per article with the parties in each, articles agreed, articles that fell from the previous round's text, and the advised party's trades on record (its concessions) | M3 (article state) is set by Python's step, not by these inputs. Their effect is read only through M4, M10 and M1. No own measure |
| 3 | Cross-issue trades, a give for a get. Clause bound by an earlier concession | Plain prompt only: it shows the trades on record and asks for trades (`neg_advisor_prompt.json:7`, `:8`). The stepwise reply always held `"trades": []` and `"state": {}` (`neg_advisor.py:1737` at a7f02e71), so C4 and round 2 as built never offered a trade or a binding state | 21 of 64 items declare one trade on record. In c4pilot_1 all 7 have both proposals on the table | #3 `trade_read` (`neg_advisor.py:1138` at this lane's commit): each declared trade of the advised party with both proposals on the table is read once (keep or drop, CHOICE-A). A kept trade goes into `trades`. Binding stays Python's (`binding_possible`) | `trade_checks` (`tools/score_neg_advisor.py:757`): valid trades, trades given, trades on record carried. Reported, not a bar line (G3 is for games) |
| 4 | Red lines and bargainable points up front. Operator red lines (#278) | Partly. Red lines marked on the record are asked one by one by the red_line step (`neg_advisor.py:1632`, `neg_advisor_prompt.json:26`). No step shows the mandate up front or apart. One source only (`neg_advisor.py:97`, `RED_LINE_SOURCES` "from the document"). No operator red lines | Yes, marked red lines: 36 red_line steps in c4pilot_1. Operator red lines: none | D-848 `mandate_split`: the mandate block before every question, red lines with their source apart from bargainable points. Operator red lines (#278, `neg_advisor.py rebuild --operator-red-lines`, source "given by the operator") are shown and asked by the red_line step of every proposal, a yes a conflict. `neg_advisor.party_red_lines(item)` (`neg_advisor.py:387`) gives #309 the same list. Reading red lines out of texts stays in the beta | M1 and its conflict floor (red line route). AM-2 red lines held/not held (reported). No own bar line |

Round 2's six switches, all false as shipped, all on in the part 1 prompts: R3 `room_fate`, R3b `changes_id_echo`
(NEG_ROUND2_M4_M10.md), `party_frame` (#310), `reason_field` (#311), `trade_read` (#3), `mandate_split` (D-848).
Checks: 686 (R3, R3b), 688 (party_frame, reason_field, trade_read, mandate_split with operator red lines), 687 (the
split), each with neutralise, fail, restore and pass on the fixture with a scripted model.

**Extra time and cost of #310, #311, #3 and D-848**, from the C4 step timings (c4pilot_1: changes 3.3 s and wording
3.5 s a step, choice steps 0.22 to 0.24 s; about 26 steps and 6 proposals an item; 39 s an item in all):
- the reason step adds about 3.5 s a proposal, about 21 s an item;
- the frame and mandate blocks add about 300 to 600 prompt tokens a step, about 0.2 s of prefill each, about 5 s an
  item;
- the trade read adds about 0.3 s an item;
- under R3 the wording may be asked of every proposal, up to about 10 s an item more.

Total: at most about 75 s an item against 39 s, about 1.9 times the workload. Part 1 (about 35 items) is about 45 to
50 min of workload, one launch. The forecast cost rises by about 0.5 USD per part launch (actual about 0.3).

## 1. The pool and the split (D-843)

- **Pool:** validation_strata (104 built: two_singles 37, teams 32, one_vs_coalition 35) and validation (53 built, 49
  kept by its screen; three_or_more 51, two_singles 1, teams 1), about 153 to 157 items before deduplication. Both
  unused: no look, not labelled, not selected.
- **Rule** (`config/neg_synth.json` `split.parts_rule`, frozen at this lane's commit, before any run):
  - `select` keeps every built item no screen dropped (`neg_synth.select_all`, no target cap).
  - `neg_synth.py split-parts` splits the pool into max(4, pool // 35) parts, the last part the spare. Part 1 is
    round 2, part 2 round 3, part 3 round 4.
  - Each structure with n items goes to its first min(parts, n // 5) parts. A structure with under 5 items goes to the
    spare and is named.
  - Within a structure, items are ordered by record kind and then by SHA-256 of "843020:<item id>", and dealt
    round-robin from a start that moves on by each structure's count.
  - Each part's digest is the SHA-256 of its sorted ids. Seed 843020.
  - Role S runs it right after selection. The ids go to role N; the lead gets counts and digests only, and logs each
    part's digest in NEG_ITERATION_LOG.md before any run.
- **Expected sizes:**
  - About 130 to 145 survive deduplication and the label-compare screen. That gives 4 parts of about 33 to 36: per
    part about 9 two_singles, 8 teams, 9 one_vs_coalition and 11 three_or_more. Every part but the spare holds all
    four structures with at least 5 each.
  - If fewer than 80 survive, there are still 4 parts, of at most 20 each. A structure with fewer than 20 survivors
    sits on fewer parts (n // 5), so part 1 keeps every structure that has at least 5.
  - Record-kind cells per structure per part are about 4 to 5. Under 5, a cell reports its count alone; the bar reads
    each kind pooled over structures.
- **Same sessions:** `validation` rides the same B, C, D, E and F sessions as validation_strata (one more set name in
  each). That adds about 5 min to B, about 45 min to D (53 more items), about 5 min to F, and about 0.6 USD expected in
  D. The embed stays one 15-chunk part.

## 2. Steps, who, start file, waits on, minutes, USD

USD columns: forecast from `tools/loop/step_cost.py` (asset copy, A10 1.29 USD an hour, x1.3); expected from the C4
actual rates (seals 0.45 to 0.47, C4 parts 0.56 to 0.75 for 15 min of workload, embed seal 0.43 and embed 0.49).

| # | Step | Who, start file or folder | Waits on | Min | Forecast | Expected |
|---|---|---|---|---|---|---|
| 0 | code bundle to roles S, V, B and N (this lane's commit) | lead | this commit | 10 | 0 | 0 |
| A | label sheets for `validation` (validation_strata's exist) | role S, start_s7.cmd | the bundle | 15 | 0 | 0 |
| B | Part A: export the pool's candidates with every earlier set, the embed pass file | role B, start_b_d798dedup_a.cmd | the bundle | 25 | 0 | 0 |
| C | embed: seal, admit, embed, then `launch.py after` | lead, external/s05/D798_DEDUP_EMBED | B's D798DEDUP_A_HANDBACK.json | 70 | 0.70 + 0.92 | 0.43 + 0.49 |
| D | blind OLMo labels of both sets, constrained (D-799) | role V, start_v_d798lab.cmd (launch folder V_D798LAB from V_C4LAB) | A, the bound worktree | 150 to 195 | about 3.2 | about 1.6 |
| E | Part B: merge, check against both fingerprints, within | role B, start_b_d798dedup_b.cmd | C's evidence | 20 | 0 | 0 |
| F | label-compare, cue screen, select (whole pool), split-parts | role S, start_s8.cmd | D and E | 30 | 0 | 0 |
| G | build part 1 under the R2 copy (all six switches), dry-run freeze | role N, start_n_r2p1b.cmd | F's parts.json | 40 | 0 | 0 |
| P | form check: the development pilot c4pilot_1 under all six switches | lead, external/s05/NEG_r2_devpilot | none (lane-built prompts) | 90 | 0.98 + 1.26 | 0.45 + 0.8 |
| V | second development set (D-710): c4val_1 halves under all six switches | lead, external/s05/NEG_r2_devval | P's R2_PILOT_OK.json | 90 | 0.98 + 2 x 1.12 | 0.47 + 2 x 0.7 |
| H | part 1: seal, admit, run, then `launch.py after` | lead, external/s05/NEG_r2_part1 | G's R2P1_HANDBACK.json, P's R2_PILOT_OK.json | 120 | 0.98 + 1.82 | 0.45 + 1.0 |
| J | score part 1 (look 1, the bar), and c4pilot_1 and c4val_1 (D-710 development) | role N, start_n_r2s.cmd | H's, P's and V's MANIFEST.json | 45 | 0 | 0 |

- **Totals:** forecast 13.1 USD, expected about 7.1 USD. The expected figure fits D-840's 9 to 12; the forecast is
  about 1 USD above 12. Without V (the second development set) the forecast is 10.8 and the expected 4.8, but D-710 then
  has one development set only.
- **#278 trial** (operator red lines, two runs, about 6.6 USD forecast as a measured round: AFTER_V1_PLAN.md row
  v1.05, about 2.5 to 3 USD expected at C4 rates): with it the expected total is about 10 USD (still inside 9 to 12)
  and the forecast about 19.7 USD (above it).
  - Its items need operator red lines declared (no file exists), so it cannot start before the operator writes one.
  - If started by 18:00 beside D, its two runs (about 60 to 90 min each) end before H; otherwise it pushes past 23:30.
  - **The lead should ask Seckin.**

**Pilot counts bars** (NEG_r2_devpilot launch.py R2_BARS, written before any run, counts only; R2_PILOT_OK.json only
when all hold): the room fate refused at most 3/1306; kept, changed and removed each top at least once; the room fate's
declared mass median at least 0.89; changes refused at most 10 percent; open point asked 0 times; reason steps refused
at most 10 percent; trade reads refused at most 10 percent.

**What role N scores on part 1:**
- the bar of NEG_BAR.md on both record kinds and on every structure part 1 holds (D-711, D-715): M1 and the conflict
  floor, M10 and the movable floor, M4 with the kept, changed and removed floors, M7, M8 and the drop share by reason;
- M2, M3, M5, the trades (`trade_checks`) and the reason field's counts beside them;
- c4pilot_1 and c4val_1 as the D-710 development reading.

The reason steps' refusals are step refusals and enter the drop share: report line 5 with and without them.

## 3. Critical path from now (14:55)

| Time | Step |
|---|---|
| 15:15 | this lane's commit fea8347d (every launch folder's COMMIT). Lead merges or keeps it; frees about 1.7 GiB of disk (10.79 GiB free at 14:58; LAPTOP-DISK-A) |
| 15:25 | bundle to roles. Arm NEG_r2_devpilot. Start A (role S) and B (role B) |
| 15:50 | B hands back. C requested |
| 15:45 to 16:00 | A done. D starts (role V) |
| 16:55 | P done (R2_PILOT_OK.json); V starts |
| 17:00 | C done. E starts, 17:20 E done |
| 18:30 to 19:15 | D done (the long pole) |
| 19:15 to 19:45 | F: select and split, part digests logged |
| 20:25 | G done |
| 22:25 | H done |
| 23:10 | J: part 1's figures (V done since about 18:30) |

Slack against 23:30 is about 20 minutes. A RAM or disk hold, or D running long, moves it past 23:30. The alpha's last
day is 21 November 23:59 (D-843), so a slip goes to tomorrow, not to the beta.

## 4. Hand commands, in order

```
# P (now): NEG_r2_devpilot, the form check
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_r2_devpilot\chain.json.ready chain.json
# V (armed now, waits on R2_PILOT_OK.json)
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_r2_devval\chain.json.ready chain.json
# C (armed now, waits on role B's Part A hand-back)
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\D798_DEDUP_EMBED\chain.json.ready chain.json
# H (armed now, waits on role N's R2P1 hand-back and R2_PILOT_OK.json)
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_r2_part1\chain.json.ready chain.json
# after each ends, by hand, from its folder:
py -3.12 -X utf8 launch.py after
# role starts (D-793: add each to ALLOWED_STARTS.json first; role_start_check.py PASS):
py -3.12 -X utf8 tools/loop/role_starter.py start start_s7.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_b_d798dedup_a.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_v_d798lab.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_b_d798dedup_b.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_s8.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_n_r2p1b.cmd
py -3.12 -X utf8 tools/loop/role_starter.py start start_n_r2s.cmd
```

## 5. Role requests (drafts; the lead places them in the exchange folders)

- **S7 (role S):** "Write the label sheets of `validation` (`neg_synth.py label-sheets --set-dir <validation set dir>
  --out _xfer/S_to_V/sheets_validation.json`); counts only to the lead. Code: the bundle to this lane's commit
  (`neg_synth_label_pass.SET_NAME` now takes `validation` and `validation_strata`)."
- **B D798DEDUP (role B), Part A:** "Export the candidates of validation and validation_strata with every earlier
  synthetic set's (dev_1, pilot_1, c4pilot_1, c4val_1), as C4DEDUP Part A, into `_xfer/B_to_lead_dev/D798DEDUP/part01/
  replay_prompts.json` with D798DEDUP_A_HANDBACK.json (pass_file_sha256, prompts, rows)."
- **B D798DEDUP, Part B:** "Merge `_xfer/lead_to_B/d798_dedup/evidence`; run check and within against both
  fingerprints; write one dropped-ids file per pool set to `_xfer/B_to_S`; counts to the lead; stop with CROSS if a pool
  item pairs with an earlier set's item."
- **V D798LAB (role V):** "Label `sheets_validation_strata.json` and `sheets_validation.json` blind, constrained (D-799),
  through the V_D798LAB launch folder (V_C4LAB's, COMMIT set to this lane's commit, set names validation and
  validation_strata); labels to role S; counts to the lead."
- **S8 (role S):** "Run label-compare and the cue screen on both sets. Then run `select` for each (it keeps every item
  no screen dropped under split.parts_rule). Then run `neg_synth.py split-parts --select validation=<kept>
  validation_strata=<kept> --out _xfer/S_to_N/d798_parts.json --counts-out _xfer/S_to_lead/D798_PARTS_COUNTS.json`.
  Ids to role N only; counts and digests to the lead."
- **N R2P1B (role N):**
  1. "Build part 1 of `_xfer/S_to_N/d798_parts.json` as the set d798_part1."
  2. "Run `neg_advisor.py build --set <d798_part1> --form advice --groups system_advice --config
     neg_advisor_prompt_r2.json --out NR_r2_part1_prompts.json`, using the copy at
     external/s05/NEG_r2_part1/inputs, SHA-256 in its launch.py."
  3. "Dry-run freeze it with its digest and a look counter at 0."
  4. "Hand back `_xfer/N_to_lead/R2P1/R2P1_HANDBACK.json` ({prompts: {d798_part1: {file, sha256, items}}}) and the
     prompts file beside it. Parts 2 to 4 are not built."
- **N R2S (role N):** "Score part 1 (look 1, logged first) with `score_neg_advisor.py score` and the bar per kind and
  structure. Also score c4pilot_1 and c4val_1 from `_xfer/lead_to_N/R2DEV` (D-710 development) against their C4
  figures. Report line 5 with and without reason steps. Figures and counts only to the lead."

Start file drafts (text, for docs/loop/private/role_starts, written by the lead from the C4 ones by name):
`start_s7.cmd` and `start_s8.cmd` from start_s5.cmd and start_s6.cmd; `start_b_d798dedup_a.cmd` and
`start_b_d798dedup_b.cmd` from start_b_c4dedup_a.cmd and start_b_c4dedup_b.cmd; `start_v_d798lab.cmd` from
start_v_c4lab.cmd; `start_n_r2p1b.cmd` and `start_n_r2s.cmd` from start_n_c4b.cmd and start_n_c4s.cmd. Each keeps its
precheck line and changes only the request file name and the waited-for hand-back file to the names above.

## 6. Blocking

- Disk: 10.79 GiB free at 14:58 (12.13 at 14:09). Every request needs 12 GiB and the bound worktree 12.45 GiB: free about 1.7 GiB first (RESOURCE-ALERT-A applies to the lead).
- Role V's launch folder must bind this lane's commit: the old SET_NAME refused `validation` and
  `validation_strata` (OPEN_ITEMS 164).
- Not checked from here: whether role B's dedup code accepts these set names (it sits in role B's tree).
- The #278 trial needs an operator red lines file that does not exist yet.
