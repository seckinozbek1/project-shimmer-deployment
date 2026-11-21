# Negotiation round 2 on bar lines 2, 3 and 5 (D-840)

20 November 2026, 14:09 +0300, lane/neg-round2-m4-m10 (branch from e3a2d4c3). Prepared only: nothing was launched,
sealed, requested or started, nothing was spent, no role session was started. No answer key, gold label, card, role
folder or benchmark/keys was opened. Read: the code, the prompts config, and the system side of the C4 runs (the
saved step records of NR_C4_PILOT, NR_C4_VAL_A and NR_C4_VAL_B, counted by form only, never against a label).

## 1. Causes, from the system side

**M4 (stance matches fate) and M10 (open-point detection).** Under the chain C4 ran (stepwise, choice_first,
compare), Python sets the stance as `counter` when the open point step says yes, else `reject` on a conflict, else
`accept` (`benchmark/baselines/neg_advisor.py:1700` and `:1706` at 83e59061, the `choice_first` branch of
`stepwise_advice`; the open point asked at `:1622`). Two faults follow:

1. The open point question is blind. Its choice_first template (`neg_advisor_prompt.json`, `choice_first.open_point`)
   shows the proposal's text alone: no position, no other proposal, nothing about the room. Whether a text will be
   kept, changed or removed is the room's decision, so the answer cannot carry it: c4pilot_1 79 yes and 73 no, the
   halves 66/48 and 79/53, which is about what a coin gives. M10 reads movable from `counter` alone
   (`tools/score_neg_advisor.py:1154`, `open_point_prediction`), so M10's movable F1 sits at chance (0.469, 0.492).
2. `reject`, the only stance that matches `removed` (`tools/score_neg_advisor.py:1248`), needs both a persona
   conflict and that blind no. The key's `removed` is the room dropping the text (`fate()`, `score_neg_advisor.py:317`:
   no next text, or a share below the changed bar), most often one of several proposals on one article losing to
   another; the chain never shows a proposal its rivals and never asks what the room will do. So removed is hit
   only where a persona conflict and a no happen to coincide: 0.075.

**Line 5, the drop share.** Of the `changes` steps, 112 of 152 (c4pilot_1) and 176 of 246 (c4val_1, the C4 report's
176) were refused `not_in_the_proposal` (`_step_check`, `neg_advisor.py`, the `changes` branch). Counted by form:
111 of the 112 and 175 of the 176 are the proposal id the prompt showed, a colon, then a line that IS in the proposal
word for word. The `changes` template shows `{proposal_id}: {proposal}` (`neg_advisor_prompt.json:17`) and the model
copies the line as shown. The check refuses a correct answer for its form.

## 2. The change: two switches, both false as shipped

- **R3 `room_fate`** (lines 2 and 3). Drops the blind open point step and asks one CHOICE-A question per proposal
  (`room_fate_text`): the proposal, the other proposals on its article (`{alternatives}`, Python's list by structure,
  or `room_fate_alone`), and each touched position with the label the chain's own compare step answered for it
  (`{room}`, or `room_fate_none`), over `room_fate_answers` kept, changed, removed. Each answer sets its declared stance
  (accept, counter, reject: the plan's M4 pairs, declared before any read, each stance exactly once). The wording is
  asked only for a counter. The conflict field (M1) is never written by it. The piece keeps `room_fate` marked
  inferred; a refused answer leaves no stance, counted. Not with `fate_forecast` (P2, built and never measured, asks a
  fate with raw article quotes after the blind open point and keeps the old stance by default). First tokens on the
  producer's tokenizer are whole words: kept 97920, changed 17353, removed 45756. WORDS-A: the model decides the
  meaning; Python lists by structure and maps declared labels.
- **R3b `changes_id_echo`** (line 5). A `changes` line that starts with exactly the shown proposal id and a colon is
  read without the id; the rest is checked word for word as before; the step is marked `id_echo`. A wrong id or a
  paraphrase is refused as before. Structural, no word list (ANSWER-FORM-A: no answer dropped for its form alone).
- **`neg_advisor.py rebuild --prompts --config --out`**: an existing prompts file built again under a switch copy (the
  same prompt ids, items and item ids, `rebuilt_from` its source's SHA-256), so role N's keys apply unchanged and no
  set is built again.

Check 686 (`tools/neg_round2_m4m10_checks.py`): 8 proofs, 2 neutralisations, fail, restore, pass, no model. Run with
the touched negotiation checks: 22, 174, 356, 450, 466 to 468, 490 to 494, 515, 516, 518, 531 to 533, 535, 539 to 543,
651, 652, 686, and for config/neg_synth.json 455 to 459, 472 to 474, 504, 510, 520, 522 to 524, 644: all PASS (468
first failed on a neutralisation that replaces `_step_check` with the old signature; the call is now the old one when
R3b is off). No controller-bound file is touched; the workload code travels in each bundle's tree, so a run needs its
own prompts files and seal from a commit holding 83e59061.

## 3. Sets

The rules: D-710 adopts a change only on at least two development sets; the bar is read on a validation set only,
once; D-789 gives every fix its own fresh validation and pilot sets, built before it is tried.

- **Development reading now (D-710):** c4pilot_1 (24) and c4val_1 (40, role N's halves c4val_1_a and c4val_1_b), both
  read once by C4 and development since (D-671). Their C4 prompts files (role N's, held in the C4 folders) are rebuilt
  under the R2 copy, so nothing is drawn, built or labelled again.
- **Bar reading (beta):** r2val_1 (validation, 40, 10 per structure, offset 13,000) and r2pilot_1 (pilot, 24, offset
  23,000), declared in config/neg_synth.json as fix R3 sets, overlapping no other range. Drawn, deduplicated, labelled,
  selected and frozen in the C4 order (NEG_C4_MEASURE_PREP.md section 2, steps A to G): about 13 to 15 hours from the
  start of role S's generation. D-789 says built before the fix is tried on them: start the generation now, beside the
  development runs, so the sets exist before any R3 figure is read.

## 4. Launch order (folders held: chain.json.ready, no LEAD_GO.txt)

| # | Folder, step | What | Forecast (step_cost.py, asset copy) | C4 actual |
|---|---|---|---|---|
| 1 | NEG_r2_devpilot seal | seal NR_R2DEV_PILOT at 83e59061 | 35 min, 0.98 USD | 0.45 |
| 2 | NEG_r2_devpilot pilot | c4pilot_1 under R3 and R3b, one A10 | 40 min, 1.12 USD (104 min, 2.91 without) | 0.69 |
| 3 | NEG_r2_devpilot after | evidence to role N, R2_COUNTS.json, R2_PILOT_OK.json if the bars hold | 0 | |
| 4 | NEG_r2_devval seal | seal NR_R2DEV_VAL_A and _B | 35 min, 0.98 USD | 0.47 |
| 5 | NEG_r2_devval val_a, val_b | the halves, val_b once val_a launched | 40 min, 1.12 USD each | 0.56, 0.75 |
| 6 | NEG_r2_devval after | evidence to role N, R2_COUNTS.json | 0 | |
| 7 | role N, two development looks | c4pilot_1 then c4val_1, D-710 | 0 | |

Forecast total 5.32 USD (actual at the C4 rates about 2.9 USD); every step and its guard cap (1.5 x forecast) under 5 USD.
The beta path adds the C4 cost lines for the fresh sets (embed 1.62, labelling about 3.9, two seals 1.96, pilot and two
halves 3.36: about 10.8 USD forecast, about 4 to 5 USD at the C4 actual rates), so both paths together forecast about
16 USD against D-840's 9 to 12; at the C4 actual rates about 8 USD.

**Pilot stop rule (counts by form only, written before any run; NEG_r2_devpilot launch.py R2_BARS):** the room fate
refused at most 3/1306 of asked; kept, changed and removed each the top answer at least once; the room fate's declared
mass median at least 0.89; changes refused at most 10 percent of changes asked; the open point asked 0 times. Only
when all hold does `launch.py after` write R2_PILOT_OK.json, which NEG_r2_devval's chain and preflight wait for. If a
bar fails, the halves are not launched and the lead decides.

**What role N scores (each set opened once more, logged first in NEG_ITERATION_LOG.md):** on c4pilot_1 and on c4val_1
(the halves as one set): M4 with the per-fate floors (kept, changed, removed), M10 with the movable floor, M1 and the
conflict floor (must not fall: R3 never writes the conflict field), M5, M2, M3, M8 and the drop share by reason
(ANSWER-FORM-A), per record kind and per party structure, set against the C4 figures on the same items (FACTORS-A: one
named factor, the two switches). Adoption (D-710): no bar figure lower beyond its interval on either set and at least
one higher. Counts and figures back to the lead only.

## 5. Timing against the 21:00 lock

- The lead merges 83e59061 (or keeps it as COMMIT: it is a commit of the shared repository) and arms
  NEG_r2_devpilot. Free disk now 12.13 GiB; making the bound worktree needs 0.45 GiB plus the 12 GiB margin
  (LAPTOP-DISK-A), so about 0.35 GiB must be freed first (tools/loop/disk_sweep.py).
- C4's pilot took 80 minutes from request to the part's end (09:03 to 10:23); the halves about the same. Armed at
  15:00: the pilot back about 16:20, the halves (after the gate) about 17:50, role N's two looks about 19:00.
- The bar cannot be read before 21:00: there is no unread validation set. c4val_1 was read once by C4 and is
  development now; r2val_1 needs 13 to 15 hours. **So round 2 cannot enter the alpha under D-709, D-710 and D-789; it
  goes to the beta.** By about 19:00 the development reading says whether R3 and R3b are worth the fresh sets. The one
  other way is the operator's: reading the bar on the D-798 validation set (the plan's one validation set, if it is
  labelled and frozen by then) would spend that set's single look on round 2.

## 6. Hand commands, in order

```
# after freeing about 0.35 GiB of laptop disk (LAPTOP-DISK-A), arm the pilot chain (or run the steps by hand):
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_r2_devpilot\chain.json.ready chain.json
#   by hand instead: from external/s05/NEG_r2_devpilot
py -3.12 -X utf8 launch.py request        # prepare (worktree neg-r2-83e59061, inventory, intake) then the seal request
py -3.12 -X utf8 launch.py seal           # then: py -3.12 -X utf8 watch.py seal  (background)
py -3.12 -X utf8 launch.py admit
py -3.12 -X utf8 launch.py pilot          # then: py -3.12 -X utf8 watch.py pilot (background)
py -3.12 -X utf8 launch.py after          # evidence to _xfer/lead_to_N/R2DEV/c4pilot_1, R2_COUNTS.json, R2_PILOT_OK.json
# the halves, armed any time (the chain waits on R2_PILOT_OK.json):
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_r2_devval\chain.json.ready chain.json
#   by hand instead: from external/s05/NEG_r2_devval: request, seal, admit, val_a, val_b, after (as above)
```

If the lead tip moves with a controller-bound change before a request, set COMMIT in both launch.py files to the new
tip (CONTROLLER-BINDING); the prompts digests stay as they are.

Round 3 (D-864) adds a fourth room fate answer setting counter and the `room_unanchored` switch: see
docs/loop/stages/NEG_ROUND3.md. Round 2 configs ask exactly as before.
