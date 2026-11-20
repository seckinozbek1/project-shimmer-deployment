# The C4 measurement, prepared to launch (D-789, D-806; NEG_CONFLICT_FIX_REPORT.md section 5)

19 November 2026, 19:29 +0300, lane/neg-c4-measure-prep (from lead/night-20261119 at 3632f1f7). Prepared only:
nothing was launched, sealed, requested or started, nothing was spent, no role session was started, no answer key,
benchmark/keys, card, item or role folder content was read (the exchange folders were written, never read, except the
`*_to_lead` hand-backs' counts). The lead's part after this note is one start command per role request, arming three
chains by renaming a file, and three `launch.py after` commands.

## 1. What exists, and what C4 can be drawn from

**Real items: none unused.** The lead's record holds 24 real-pilot items (set 6a8af3c7..., 18 INB headline items and 6
LLM-Deliberation games), all development since D-695 and looked at three times (NEG_ITERATION_LOG.md). The real-item
count of 16 November found no other admitted source (FOR_SECKIN 16 Nov 14:45: "real items only 24, the pilot";
NEG_FINAL_ITEMS_METHOD.md section 1: INC, BBNJ, OEIGWG and UNODC not recorded). Role B's BCOUNT1 and BDRAW1 counted and
drew ContraDoc and SciTab only. So "real items first" gives 0 items, and no role B real draw or freeze is requested.

**Synthetic sets (config/neg_synth.json, role S hand-backs S_SESSION1 to S_SESSION3):**

| Set | State | Used by a look |
|---|---|---|
| dev_1 (65 items) | drawn, built, cue-screened (S2); labels in role V's merge | development |
| pilot_1 (31 items) | drawn, built, cue-screened (S2); labels in role V's merge | pilot (read once, then development) |
| validation (D-798; 80 drawn, 53 accepted, target 40) | drawn and built (S3, 17:00); not deduplicated, labelled or selected | the D-798 validation set, excluded from C4 |
| validation_strata (top-up of validation, 30) | role S session 4 drawing now (started 18:49, held for RAM at 18:50) | joins validation, excluded from C4 |
| dev_2, dev_3, pilot_2 | declared, never drawn | none |
| c4val_1, c4pilot_1 | declared by this lane (fix sets, below), never drawn | none |

No set is frozen: none has a FREEZE.json, none has a look counter. The three never-drawn declared sets are free, but
dev_2 and dev_3 are development sets by declaration and pilot_2 has no strata, and the plan allows exactly one
validation set; so C4 gets its own declared sets instead (D-789: "its own fresh validation and pilot sets").

**Built here (commit 018e39fa):** a fix set (`fix`, `fix_decision`; `split.fix_rule`; `tools/neg_synth.py check_fix`)
is one fix's own fresh validation or pilot set, never a top-up, never counted as the plan's one validation set or a
pilot, at most one of each purpose per fix. Declared: **c4val_1** (validation, 40, 10 of each of the four party
structures, 120 seeds, offset 12,000) and **c4pilot_1** (pilot, 24, plain draw, 64 seeds, offset 22,000). Both ranges
overlap no other set, so neither set can share a seed or a card with the old pilot, dev_1, pilot_1 or the D-798
validation set; role B's `within` and both fingerprints guard the text (section 2, B). The names are of the label
pass's set-name form (`neg_synth_label_pass.SET_NAME`, `^[a-z][a-z0-9]*_[0-9]+$`). Proof 6 of check 644, neutralised,
failed, restored, passed; 644 with 455 to 459, 472 to 474, 504, 510, 520, 522 to 524, 22 and 174 run alone: PASS 17.

**Should C4 wait for role S session 4?** C4 uses none of session 4's items (validation_strata tops up the D-798
validation set), so its figures do not wait for them. Its generation does wait for session 4 to end: one role S
session at a time, the same seed base and card folders, and session 4's commit (34d7bfea) is the base of the S5 code
bundle. Start S5 the moment `_xfer/S_to_lead/S4_DONE.json` exists; its precheck refuses before that.

## 2. The order, its prerequisites, times and costs

Times are expected durations from the measured rates (role S session 3: 80 generator calls in about 1.5 hours; the
improved run: 244 s a stepwise prompt; the dedup and labelling folders' forecasts); laptop RAM holds add to them.
Costs are `tools/loop/step_cost.py` figures with the asset copy (A10 1.29 USD an hour, inventory of 19 Nov 15:53 UTC);
every step is under the 5 USD per-step pre-approval (D-708) with its guard cap (1.5 x forecast) under 5 USD too.

| # | Step | Who, start file or folder | Waits on | Takes | USD |
|---|---|---|---|---|---|
| A | generate c4pilot_1 then c4val_1 (184 cards), candidates and sheets | role S, start_s5.cmd | S4_DONE.json | about 3.5 h | 0 |
| B | Part A: export every set's candidates, the embed pass file | role B, start_b_c4dedup_a.cmd | S5_DONE.json | 20 min | 0 |
| C | embed on Lambda: seal, admit, embed (chain), then `launch.py after` | lead, external/s05/C4_DEDUP_EMBED | B's C4DEDUP_A_HANDBACK.json | 70 min | 0.70 + 0.92 |
| D | blind OLMo labels, constrained (D-799), handover to role S | role V, start_v_c4lab.cmd | S5_DONE.json, the bound worktree (made by C's request) | 2.5 to 3 h | 1.26 + about 2.6 (`build` prints it) |
| E | Part B: merge, check against both fingerprints, within | role B, start_b_c4dedup_b.cmd | C's evidence, SYNDEDUP2's reference_N and reference_lead with sidecars | 20 min | 0 |
| F | label-compare, cue screen, select, kept sets to _xfer/S_to_N | role S, start_s6.cmd | D and E | 30 min | 0 |
| G | build, dry-run freeze, split c4val_1 into 20 + 20, the C4 prompts files | role N, start_n_c4b.cmd | S6_DONE.json | 40 min | 0 |
| H | pilot: seal, admit, run (chain), then `launch.py after` (counts check) | lead, external/s05/NEG_c4_pilot | G's C4B_HANDBACK.json | 2.5 h | 0.70 + 3.16 |
| I | validation: seal, admit, val_a and val_b (chain), then `launch.py after` | lead, external/s05/NEG_c4_validation | G, and H's PILOT_COUNTS_OK.json | 2.3 h (parts side by side) | 0.84 + 2.71 + 2.71 |
| J | score both sets, look 1 each | role N, start_n_c4s.cmd (once after H, again after I) | H's, then I's MANIFEST.json | 40 min each | 0 |

D runs beside B, C and E. Critical path from S4's end: A, B, C (D beside), E, F, G, H, I, J: about 13 to 15 hours of
elapsed time if nothing is held. Spend forecast: about 15.6 USD (C 1.62, D about 3.9, H 3.86, I 6.26), inside the D-749
cap; the D-798 negotiation labelling approval (about 2.5 USD) does not cover D, each step stands on D-708 alone.

**The pilot's counts check (H, written before any run; launch.py COUNT_BARS):** compare steps refused at most the stance
step's one-sided 95 percent bound in the improved run (0 of 1,306; 3/1306), at least one decision whose top answer is
`against`, and the compare answers' declared mass with a median of at least 0.89. Only when all three hold does
`launch.py after` write PILOT_COUNTS_OK.json, which I's chain and preflight wait for. Run on the improved run's saved
replies with stance in place of compare, the reader gives 1,306 asked, 0 refused, top 888 accept, 418 support, 0
oppose, mass 0.926 and 0.993 (the report's figures): that run would fail the second bar, as it should.

**The bound tree.** Every Lambda folder here binds `.claude/worktrees/neg-c4-3632f1f7` at 3632f1f7 (the lead tip holding
the merge of lane/neg-conflict-fix; it holds the arm64 image fix dd1aef72 and the constrained labeller 5674e3aa, whose
label files are byte for byte the same there). It is made once by the first request's preflight (`launch.py prepare`:
`git worktree add --detach`, LF, frozen model files hard-linked and held to config/final_models.json's SHA-256, never
a junction), after a LAPTOP-DISK-A check of 0.45 GiB plus the 12 GiB margin. If the lead tip moves with a
controller-bound change before H's request (the grouped re-seal, D-806 item 1, D-810), change COMMIT in the three
launch.py files and in V_C4LAB/launch.py to the new tip before arming.

## 3. Exactly what the lead runs

Once, now (no spend):

```
# D-793: allow the seven starts (append to docs/loop/private/role_starts/ALLOWED_STARTS.json):
#   start_s5.cmd, start_b_c4dedup_a.cmd, start_v_c4lab.cmd, start_b_c4dedup_b.cmd, start_s6.cmd, start_n_c4b.cmd, start_n_c4s.cmd
# and the supervisor checks docs/loop/private/role_settings_drafts/role_settings_V_C4LAB.json (V_SYNLAB2's, narrowed to V_C4LAB).
# Arm the three chains (each waits on its `requires` files, so arming early launches nothing):
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\C4_DEDUP_EMBED\chain.json.ready chain.json
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_c4_pilot\chain.json.ready chain.json
Rename-Item <USER_HOME>\local\shimmer-deployment\external\s05\NEG_c4_validation\chain.json.ready chain.json
```

Then, each when its prerequisite exists (the start file's precheck refuses earlier, writing `<tag>_precheck.txt`):

```
py -3.12 -X utf8 tools/loop/role_starter.py start start_s5.cmd           # after _xfer/S_to_lead/S4_DONE.json
py -3.12 -X utf8 tools/loop/role_starter.py start start_b_c4dedup_a.cmd  # after S5_DONE.json
py -3.12 -X utf8 tools/loop/role_starter.py start start_v_c4lab.cmd      # after S5_DONE.json and C's first request (the worktree)
py -3.12 -X utf8 external/s05/C4_DEDUP_EMBED/launch.py after             # after its embed ended with exit 0
py -3.12 -X utf8 tools/loop/role_starter.py start start_b_c4dedup_b.cmd  # after that and SYNDEDUP2's two fingerprints
py -3.12 -X utf8 tools/loop/role_starter.py start start_s6.cmd           # after _handoff/V_C4LAB_DONE.json and C4DEDUP_B_DONE.json
py -3.12 -X utf8 tools/loop/role_starter.py start start_n_c4b.cmd        # after S6_DONE.json
py -3.12 -X utf8 external/s05/NEG_c4_pilot/launch.py after               # after the pilot part ended with exit 0
py -3.12 -X utf8 tools/loop/role_starter.py start start_n_c4s.cmd        # the pilot's look (ends N_C4S_PILOT_DONE.json)
py -3.12 -X utf8 external/s05/NEG_c4_validation/launch.py after          # after val_a and val_b ended with exit 0
py -3.12 -X utf8 tools/loop/role_starter.py start start_n_c4s.cmd        # the validation's look (ends N_C4S_DONE.json)
```

Also: write 018e39fa into `_xfer/lead_to_S/CODE_COMMIT.txt` after S5 checks it out (the request leaves that file to
the lead), and one FOR_SECKIN line per start (D-793). Role S's first two runs (A, F) are the only long Claude-usage
items.

## 4. What was placed where (all outside git except this note and the code)

- `external/s05/NEG_c4_pilot/`, `NEG_c4_validation/`, `C4_DEDUP_EMBED/`: launch.py (prepare, preflight, request, seal,
  admit, parts, after, status, stop), watch.py, chain.json.ready, step_*.json with their step_cost.py outputs,
  README.txt, inputs (the dummy workload, items.json, and for the NEG folders the C4 config copy,
  `neg_advisor_prompt_c4.json`, SHA-256 9acd656d..., canonical config digest 2b51d620...). `status` and `preflight` run:
  preflight lists exactly the missing worktree, intake and inventory, and free disk 11.31 GiB under 12.
- `_xfer/lead_to_S/`: REQUEST_ROLE_S_S5.md, REQUEST_ROLE_S_S6.md, S5_code.bundle (34d7bfea to 018e39fa, 75,406 bytes,
  SHA-256 d66004e9..., `git bundle verify` ok).
- `_xfer/lead_to_B/c4_dedup/`: REQUEST_ROLE_B_C4DEDUP.md (Part A, Part B; the dedup code is SYNDEDUP2's a37ccd7f).
- `_xfer/lead_to_V/syn_label/`: REQUEST_ROLE_V_C4LAB.md and the launch folder V_C4LAB (from V_SYNLAB1_template:
  build, request, seal, admit, label, labels, handover; no supervisor review round, D-809).
- `_xfer/lead_to_N/C4/`: REQUEST_ROLE_N_C4B.md, REQUEST_ROLE_N_C4S.md, the C4 config copy, and
  shimmer_f1961c32_to_018e39fa.bundle (899,415 bytes, SHA-256 b066e5dc..., verify ok).
- `_xfer/S_to_N/` (new, empty): role S's hand-on of the kept sets to role N.
- `docs/loop/private/role_starts/`: the seven start files, each `role_start_check.py` PASS (every guard and every
  request command ALLOWED); `docs/loop/private/role_settings_drafts/role_settings_V_C4LAB.json`.

## 5. Open (OPEN_ITEMS 164)

- The label pass reads a sheets file only for a set name of the form `name_N`: `validation` and `validation_strata`
  do not match, so the D-798 validation set's labelling through build-pass will be refused as named. C4's names match.
- The C4 sets are frozen as a dry run (exact and 5-gram leakage, the set digest); the cosine rule ran in role B's
  deduplication against role N's embedded fingerprint. If the scorer refuses a dry-run freeze, role N stops with
  FREEZE_ROUTE and the embedded freeze needs one more rented-route step.
- `within` counts cross-set pairs but does not name the partner set; role B compares three pair counts and stops with
  CROSS if a C4 item pairs with an earlier item.
- The start files' prerequisite prechecks are Python one-liners role_start_check cannot evaluate (it checks existence
  guards only); they refuse at start time and write `<tag>_precheck.txt`.
- Role S's hand-on folder `_xfer/S_to_N` and role N's build of a synthetic set from it are new paths, untried.
