# The output side's development measurement (D-672, sweep step 4; written 15 November 2026 20:24 from date)

A plan for the lead to approve and launch. Nothing here has run; this lane launches nothing.

## What it measures

Whether the output side built in 4e33a1d2 removes the answers the readers drop for their form, on Shimmer's own
advisor groups only:
- system_advice (the tuned producer) under the schema constraint;
- validate (Phi-4) under the schema constraint;
- system_audit (Phi-3.5) and judge (Phi-4) as choice decisions.
B1 and the cloud reference do not run (D-671: no bare-model or cloud runs until after v1.1).

## The choice threshold is provisional

CHOICE-A decides at a measured threshold. None is measured for the judge's or the auditor's choices, so
the threshold 0 declared in 4e33a1d2 (`choice_threshold` in neg_advisor_prompt.json: the top answer, a tie
unsettled) is PROVISIONAL (lead, 15 November). It holds for this development measurement only. A threshold
is set from the top-answer mass distribution this measurement reports, by a decision, before any scored use
of these choices. Until then no score reads a choice decision under threshold 0.

## Items (revised 16 November 2026, lane contradoc-d652)

Development items only. Since D-695 and D-707 the old pilot's 24 items are development, and D-710 asks for at least
two development sets behind any adopted change. So: **12 items, from two sets**, named with their SHA-256 by role N
before the run (this lane chooses no item and opens no key):
- **Set 1: 8 of the old pilot's items** (development since D-695). Their free-generation replies are saved from
  the pilot's pass, so their "before" pass is not run again when the saved records' model ids and checkpoint
  digests equal the after pass's (checked first; any difference runs the before pass for them too). Reading their
  saved replies again for drop counts is no new opening of the set for scoring; it is counted on the set's look
  counter (D-671 item 8).
- **Set 2: 4 items of another development set** (the 6-item list, track A's development part or the synthetic
  development set of D-707, synthetic items marked and reported apart). Both passes run for them.
The judge's choice decisions on the counters of all 12 items also feed the judge's calibration
(NEG_JUDGE_CALIBRATION.md, D-656), excluding the pilot's items there: set 1's counters are read here for drops and
never calibrate the judge.

## Two passes, one session

1. **Before:** the configuration at cfcaa0b9 (free generation for every group, the bound text before D-672), its
   prompts built from that commit's neg_advisor_prompt.json; set 2 only, unless the digest check above fails.
2. **After:** the configuration at 4e33a1d2 (choice decisions and schema constraint), all 12 items.
Both passes' saved replies are read by `tools/reread_replies.py advisor` (the score-time reader, the same for
both), so the only difference between the two counts is the output side. The two answers files and the after
pass's folder are then read by `tools/output_side_read.py` (check 487), which writes every figure below and the
bar's lines; exit 2 when a bar line is not met.

A preflight first, tokenizer only, no generation: `choice_decision.bind` on each choice form's answers for
Phi-3.5 and Phi-4 (each surface's first token distinct and not joined to the prompt). A refusal stops the
session before any generation and the lead is told; the surfaces are then changed by a decision.

## Figures, counts only (no text leaves the instance)

Per group and pass:
- the drop counts by field and reason (`drops` of every row, summed: `tools/reread_replies.drop_counts`),
  `several_objects_last_read` apart (a count, not a drop);
- answers read and not read, per form (advice rows with a reply object, audit and judge answers settled,
  validator mappings);
- after only: the constraint's counts per call (steps, interventions, first intervention step, dead ends) and
  the choice decisions' declared mass, ties (unsettled) and the share where the top answer was the model's
  own top token (`undeclared_top`);
- after only, per choice group (judge, system_audit): the distribution of the top answer's probability
  (its mass), as counts in the bins 0.33-0.5, 0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9-1.0, with the
  declared mass beside it, so that a threshold can be set from it;
- seconds per call and per group (the cost of the constraint's per-step mask).
The bar, written before the run: after, no drop of any reason on system_advice and validate except
`not_asked` (a schema reply can only be off by content, never by form), and no unsettled audit or judge
decision beyond ties; any dead end is reported by call id and is a failure of the bar.

## Cost forecast, two ways (A10, 1.29 USD an hour live on 8 November, times 1.3: 1.68 USD an hour)

| What | Without the saving measures (minutes) | With them (minutes) |
|---|---|---|
| Setup, one session | 15, plus 64 of asset upload if the copy reads MISSING | 15, asset copy MATCH |
| Preflight, two tokenizers | 1 | 1 |
| Before: system advice at up to 2,048 tokens (about 82 s an item) | 12 items: 16 | set 2's 4 items: 6 |
| Before: audit, judge and validator, with three loads | 12 items: 18 | 4 items: 7 |
| After: system advice under the constraint, planned at twice the free time | 12 items: 33 | 33 |
| After: audit and judge one forward pass each, validator under the constraint at twice | 18 | 18 |
| **All** | **101 min, 2.83 USD** (4.62 USD with the upload) | **80 min, 2.24 USD** |

The saving measures: set 1's before pass read from its saved replies (when the digests match); the asset copy
reused; the judge's calibration decisions in the same after pass (NEG_JUDGE_CALIBRATION.md: about 1 minute more,
inside the after rows). Launched with `--cap-usd 3`, so the guard stops it there. **Outside the cap, stated:** with
the upload the run passes 3 USD; the launch is then refused and the lead told, not run. The constrained
generation's true time is the one unknown: if the first constrained advice call exceeds 4 times the free time,
the session stops after it and reports, so the forecast is never exceeded silently.

## Before it can launch

- The full gate once on Lambda as arm G on the merge branch (lead: this lane, audit-fix and 9fb6a9e8, after
  A5's runs), and the re-seal on Lambda (D-668): the bound files neg_advisor.py, neg_advisor_prompt.json and the
  new scripts/schema_decoding.py changed.
- New prompts files for both passes (every advisor prompts digest changes with config_sha256: b1, system,
  cloud, judge and validate prompts SHA-256 in the configuration). The power record is untouched by 4e33a1d2
  (its code_sha256 is score_neg_advisor.py's, unchanged here; it changed at de578403).
- Role N's 12 development items (8 of set 1, 4 of set 2) and their SHA-256; for set 1, the saved pilot pass's
  reply records and the digest check of section "Items".
- Ready to launch after the next re-seal: the reader (`tools/output_side_read.py`, check 487) and the judge's
  calibration (`tools/neg_judge_calibration.py`, check 486) are built and proven on fixtures; nothing else is
  missing on the reading side.
