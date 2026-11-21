# Amendments to the negotiation plans (NEG_ADVISOR_PLAN.md, the pilot; NEG_DRAFT_BENCH_PLAN.md, the benchmark)

Each amendment is written here before any score that uses it, with its date and decision. They bind both plans and are
folded into the plan files when the lanes merge. No amendment is applied to a score read before its date.

## AM-1 (D-662, 15 November 2026, 18:35 +0300): a checker field of one class

When the key and the checker both give the same single class on a field, kappa is undefined. The raw agreement is
reported, and at 100 percent the field counts as at the bar, labelled "single class, kappa undefined". Below 100 percent
on a single-class field, the field is below the bar. Applies to the bar's line 4 and to M9's validation alike.

## AM-2 (D-665, 15 November 2026, 18:39 +0300): red lines measured two ways

- **Declared red line:** the party says so in the record ("cannot accept" and the like). The system's extraction is
  scored against the labels, as now (`red_line` per proposal).
- **Held red line:** did it hold in the next round? Computed in Python from the fate the scorer already computes: a
  proposal resting on a declared red line that the party later accepts, or lets through (its fate `kept` or `changed`
  toward the proposal with no recorded objection of that party), counts as not held; one the party keeps opposing, or
  that is removed, counts as held. Reported as the held share: a finding on which declared red lines were real and which
  were bargaining positions. It is a property of the record, the same for every arm; beside it, each arm's agreement
  with "held" on the red lines it extracted.
- **Arms and items:** the system, B1 and the cloud reference, on development and track A items. The frozen pilot is
  only re-scored with it, never tuned on.
- **Source:** every red line carries its source field, for now only "from the document" (D-664).

**Note (D-693, 16 November 2026, the lead):**
- **Open is its own count.** A declared red line whose proposal is still bracketed in the next round (fate
  `open`) is reported as `open`, beside held (fate `removed`) and not held (`kept` or `changed`), never folded
  into held. The held share is held over held and not held.
- **The "no recorded objection" clause cannot fire on these items:** `check_build` refuses any position after
  round k, so no objection of the next round is on record, and `kept` or `changed` counts as not held.
- **The re-score is opening k=2** at alpha 0.0125, with a fresh power record made with `power --k 2` from the
  unchanged frozen set and seed. The k=1 score stays the headline; the re-score is reported as a re-score.
- **The frozen pilot is never rebuilt:** `build` refuses a set whose FREEZE.json is recorded, and keys built
  before the `red_line_source` field read as "from the document" (neg_advisor_checks test_40, test_37).
- **Built in** tools/score_neg_advisor.py (AM-1: `agreement`, `at_bar`; AM-2: `held_red_line`,
  `red_line_outcome`, `red_line_part`, the report's `red_lines`), proofs neg_advisor_checks test_36, 37, 40.
- **The benchmark scorer (NEG_DRAFT_BENCH_PLAN.md):** not in this lane's tree and outside its scope; carrying
  AM-1 and AM-2 into it is open item 114 in docs/fix/OPEN_ITEMS.md.

## Note (#281 gap 8, D-666, D-667, 16 November 2026, lane audit-redaction-neg): unbracketed numbered options

The plan's proposals rule (NEG_ADVISOR_PLAN.md section 4.1: one proposal per top-level bracket span, or the whole
unagreed article) read an unagreed article that numbers two or more options ("Option 1: ... Option 2: ...") with no
bracket as one proposal, silently. `build` now refuses such an article visibly, the item and article named, and writes
nothing; the builder brackets each proposal. Nothing is split by guess, and no other article's proposals change.
Built in tools/score_neg_advisor.py (`unbracketed_options`, `refuse_unbracketed_options`), proof neg_advisor_checks
test_41. The frozen pilot is never rebuilt, so its keys are untouched. The scorer's code digest changes with this
file, so a new opening needs its own power record (as every opening does).
## AM-3 (16 November 2026, 20:15 +0300, the operator's request through the lead): M10, open-point detection

Written before any code or score that uses it. **Indicator only:** never a claim, never in the bar (section 7.1)
until the operator says so.

- **Key class**, per proposal with a fate (the existing `fate()` diff, stored in `key.proposals[pid].fate`):
  `movable` when the fate is `open` or `changed`; `settled` when it is `kept` or `removed`.
- **Prediction:** `movable` when the arm's stance is `counter`; `settled` when it is `accept` or `reject`. No stance
  is a miss, counted by reason (ANSWER-FORM-A drop counts): no reply, a withheld piece, no piece for the proposal, a
  piece with no stance; beside them the arm's parser drop counts of `proposals.stance` and `reply`.
- **Score:** Macro-F1 over the two classes, in pure Python, with the same item-cluster bootstrap interval as M1
  (BCa over items, seed 20261113, the headline items), per arm, and the system-minus-B1 difference where both arms
  exist (the paired BCa, jackknife and permutation of `test_claim`, reported as an indicator). A class with no row in
  the key and none predicted has no F1, and the figure is then undefined (left out of the bootstrap, its mass
  reported, plan section 6.5).
- **Opening:** M10 is read only on an opening the lead commits before any read, a re-score of the saved answers,
  never a re-run, with its own power record from the unchanged frozen set and seed. The k=1 score stays the headline.
  AM-3 changes no rule: plan section 7.4 allows at most two openings and the scorer refuses k=3 (`MAX_OPENINGS` 2,
  neg_advisor_checks test_11); a third opening (k=3, alpha 0.00625) needs its own operator decision first.

**Correction (16 November 2026, 20:25 +0300, the lane, before any code or score):** the first text of the
opening line above raised section 7.4's cap to three; under the operator's order of 20:13 (no rule changes) that
sentence is withdrawn and the cap stays two.

**Note (D-710, Seckin 20:27, 16 November 2026, the lane):** the operator granted the third opening: the old
24-item pilot (set 6a8af3c7...) alone, indicator only, at alpha 0.00625, re-reading its saved answers, 0 USD. The
limit stays two for every other set. Built in tools/score_neg_advisor.py: `EXTRA_OPENINGS` names the one set by
its digest, `max_openings` gives each set its limit to `refuse`, and `opening_claim_status` makes A1 an indicator on
any opening beyond two whatever its power record says. Proofs: neg_advisor_checks test_11 (k=3 refused on any other
set, k=4 on the pilot, the set the ledger's first neg-advisor line names) and test_29 (the third opening's alpha).

## AM-4 (D-878, 21 November 2026, 03:52 +0300): an audit-unsupported piece kept and marked
Plan section 5 item 2 withheld every piece the system's audit called unsupported, and the piece scored no_answer.
On the round 3 pilot the audit withheld 43 of 152 pieces (28 percent), so the coverage rule (D-871: over 5 percent
withheld refuses the figure) refuses M1, M10, M4 and M5 as scored. From the next round on, on items not yet seen,
the system's figure reads each such piece as the system wrote it, marked "audit: unsupported" (HONEST-OUTPUT-A), and
the withheld reading is reported beside it from the same replies; a piece a system-mode check refuses stays withheld.
Switch: config/neg_advisor_dev.json audit_unsupported_kept, false until set true under a decision id before that
round's deciding read. Bar line 3 (withheld share at most 0.30) is reported unchanged. Fixed before any figure of that
round; the pilot figures that showed the loss (D-877) are same-item readings and labelled so.
