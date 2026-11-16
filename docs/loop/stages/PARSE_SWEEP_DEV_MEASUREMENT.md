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

## Items

Development items only (D-656 item 2): role N's track A items, or, until those are frozen, items from the
advisor's non-pilot development pool that role N names. Never the pilot's 18 frozen items (D-654) and never a
key or held-out item opened by this lane. Size: **8 items**, about 40 proposals, about 64 validator positions,
the judge on the counters the system writes (about 20). The item list and its SHA-256 are written by role N
before the run; this lane does not choose items.

## Two passes, one session

1. **Before:** the same 8 items with the configuration at cfcaa0b9 (free generation for every group, the
   bound text before D-672), its prompts built from that commit's neg_advisor_prompt.json.
2. **After:** the configuration at 4e33a1d2 (choice decisions and schema constraint).
Both passes' saved replies are read by `tools/reread_replies.py advisor` (the score-time reader, the same for
both), so the only difference between the two counts is the output side.

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

## Cost forecast (A10, 1.29 USD an hour live on 8 November, times 1.3: 1.68 USD an hour)

| What | Minutes | USD |
|---|---|---|
| Setup, asset copy MATCH, one session | 15 | 0.42 |
| Preflight, two tokenizers | 1 | 0.03 |
| Before: system advice, 8 items at up to 2,048 tokens (about 82 s) | 11 | 0.31 |
| Before: audit about 40 calls at 3 s, judge about 20 at 2 s, validator 64 at 3 s, with three loads | 12 | 0.34 |
| After: system advice under the constraint, planned at twice the free time (the mask is per step, in Python) | 22 | 0.62 |
| After: audit and judge as one forward pass each (about 1 s), validator under the constraint at twice | 12 | 0.34 |
| **All** | **73** | **2.06** |

Stays under 3 USD with 0.94 to spare; launched with `--cap-usd 3`, so the guard stops it there. **Outside the
cap, stated:** if the asset copy reads MISSING, the 64 minutes of upload (D-332, +1.79 USD) would pass 3 USD;
the launch is then refused and the lead told, not run. The constrained generation's true time is the one
unknown: if the first constrained advice call exceeds 4 times the free time, the session stops after it and
reports, so the forecast is never exceeded silently.

## Before it can launch

- The full gate once on Lambda as arm G on the merge branch (lead: this lane, audit-fix and 9fb6a9e8, after
  A5's runs), and the re-seal on Lambda (D-668): the bound files neg_advisor.py, neg_advisor_prompt.json and the
  new scripts/schema_decoding.py changed.
- New prompts files for both passes (every advisor prompts digest changes with config_sha256: b1, system,
  cloud, judge and validate prompts SHA-256 in the configuration). The power record is untouched by 4e33a1d2
  (its code_sha256 is score_neg_advisor.py's, unchanged here; it changed at de578403).
- Role N's 8 development items and their SHA-256.
