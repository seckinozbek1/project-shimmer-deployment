# What was planted in the host agreement case

**Not shown to any model.** This file is outside `workload/`, so neither the sealer nor a run
receives it. Do not copy it into `context/` or `conventions/`.

Synthetic. A demonstration, never benchmark evidence. Nothing here has been run on a model.
"Computed" below means the case was read by the project's own Python functions on this machine
with no model; it says what Python makes of the text, not what a run reports.

## The negotiation

The opening draft is the Secretariat's. Round 1 is the mark-up of the delegation of Sarvenna,
round 2 the counter of the delegation of the Organisation, round 3 the reply of the delegation
of Sarvenna. Each `.docx` under `workload/context/`, the run input, carries that delegation's changes against the state
before, and the first carries round 1's changes against the opening draft.

| Term | Opening | Round 1 (Sarvenna) | Round 2 (Organisation) | Round 3 (Sarvenna) |
|---|---|---|---|---|
| Entry to premises, Art. 4(2) | consent | consent or urgent circumstances | express consent, plus fire presumption | express consent kept |
| Free rent, Art. 3(2) | while the seat remains | ten years | while the seat remains | twenty years, renewable |
| Value added tax threshold, Art. 8(3) | none | 5,000 EUR | 1,000 EUR | 1,000 EUR |
| Refund decision, Art. 8(4) | none | 90 days | 60 days | paragraph removed |
| Visa decision, Art. 9(2) | 14 days | 30 days | 21 days | 21 days, renamed entry clearance |
| Dependants' work, Art. 9(3) | right to work | removed | may apply | removed |
| Execution, Art. 6(2) | no waiver | commercial exception | separate express waiver | kept |
| Disputes, Art. 13 | arbitration | diplomatic channel only | arbitration | arbitration accepted |
| Termination notice, Art. 14(3) | 24 months | 12 months | 18 months | 18 months |
| Total contribution, Annex II | 2,400,000 EUR | 2,000,000 EUR | 2,200,000 EUR | 2,200,000 EUR stated |

Moves a diplomat would name: Sarvenna concedes arbitration and express consent in round 3 and
hardens elsewhere (Art. 11(3), Art. 10(5)), so the headline concession is taken back in a
provision the note mentions only in passing. The Organisation's round 3 note welcomes Art. 4
without yet having studied Art. 11.

## Planted in round 3

1. **Two articles in contradiction, in words, no figures.** Art. 4(2) allows entry only with
   the Director-General's express consent. New Art. 11(3) lets the authorities enter without
   that consent where they consider public security so requires. Rule CONV-H01. Only a reader
   of both articles can see it, and they are seven units apart.
2. **A contradiction of periods.** Art. 9(2) decides every application within twenty-one days,
   and Annex I says 21 days. New Art. 10(5) gives officials and their dependants thirty days.
   Rule CONV-H03. In prose, so Python reads no figure.
3. **A broken cross-reference.** Paragraph 4 of Art. 8 is removed, and Art. 10(4) still sends
   officials to "the procedure in paragraph 4 of Article 8". Rule CONV-H02.
4. **A term a note asks for and the text does not deliver.** The Organisation's round 3 note
   asks that dependants may apply for a work authorisation, which the Host State accepted in
   principle in its round 2 note. Art. 9(3) is removed in round 3, and Art. 9 stays open.
   Rule CONV-H06.
5. **A total that no longer adds up.** Security services fall from 300,000 to 200,000 EUR in
   Annex II and the total stays at 2,200,000 EUR, while the Host State's note says the
   contribution "is maintained". Rule CONV-H05. Computed: `sum_mismatch` on Annex II, 2,100,000
   against 2,200,000, round 3 only. It is the only finding Python computes in the whole case.
6. **A renamed term.** "visa" becomes "entry clearance" in Art. 1(g), Art. 9(2), Art. 10(5) and
   Annex I. The rename itself is carried through consistently (no flaw under CONV-H04). The
   case manifest declares it as one issue, `entry-period`. Computed in the two-version review:
   `possible_rename` on `visa decision period`, 21 days.

7. **A status that does not hold (Art. 8).** Round 3 proposes Art. 8 as agreed ad referendum,
   while the Organisation's round 3 note will not agree to moving the refund procedure before it
   sees the arrangement. Rule CONV-H06.
8. **A status that does not hold (Art. 4).** Round 3 proposes Art. 4 as agreed ad referendum,
   while new Art. 11(3) undercuts it. The same contradiction as item 1, seen from the status.
   Rule CONV-H01.

Status convention: each round is one delegation's mark-up, so "agreed ad referendum" appears
only where both delegations have recorded it, and a status one delegation alone puts forward
reads "proposed as agreed ad referendum". Art. 1 is agreed in round 2 and reopened in round 3,
which Sarvenna's round 3 note explains: not a flaw.

## Look-alikes that are not flaws

- Art. 4(3), presumed consent in a fire, qualifies Art. 4(2) and does not contradict it.
- Art. 11(2), precautions after consultation, does not on its own authorise entry.
- Sixty days appears in Art. 13(2) and Annex I for the same purpose, and they agree.
- Ninety days in Art. 13(1) has nothing to do with the deleted ninety days of round 1.

## What Python makes of it, computed on this machine with no model

**The two contradictions in words are likely missed.** Items 1 (Art. 4(2) against Art. 11(3)) and 2
(Art. 9(2) against Art. 10(5)) can be found only by comparing two articles, and the shipped
configuration has no step that does: the passage comparison (`[compare: passages]`) was measured
and not adopted (D-294), so the rule that declared it was removed. What is left is the ordinary
unit-by-unit judging, where a model sees one article with only the articles beside it, and Art. 4
and Art. 11 are seven units apart. Item 2's articles are neighbours, so it has a better chance.

Multi-round (`multi_round_rounds.review_document`, all nine documents): every article and annex
pairs with rules, the position notes pair with none, no unit is reused in round 2 (every article's
text or status moves) and 4 are in round 3, and the one finding is item 5. Items 1 to 4 are recorded as pairs needing a model, and a
multi-round run does not ask them.

Two-version review of round 3 against round 2 (`paired_review.prior_index`, `prior_lookup`,
`prior_checks`, `absent_checks`, with stand-in REF ids): `unchanged_from_prior` on the other
Annex I figures and the total; `possible_rename` on the visa period; `absent_since_prior` on the
refund decision period, which is true.

**A change Python does not state.** Security services fall from 300,000 to 200,000 EUR in Annex
II, and the two-version review writes no change record for it, because a table cell of the
document under review never gets one (`docs/INPUT_FORMAT.md` section 6). The row is correctly
not reported as withdrawn. Only item 5's `sum_mismatch` shows that something moved there.

## Not built

`decision_support_mode` is left out, so it is `trajectory_only`, and the free-form strategic path
makes no call. Toward or away, and suggested wording for the Organisation on the open issues, are
`scripts/case_questions.py`, wired through the driver. Until `agent` in
`config/case_questions.json` names one, and for a movement until a threshold is measured, every
movement record a run writes says `unknown` and `case_positions.md` holds only Python's selections,
each row saying why. No suggestion has been produced on this case.

The manifest declares the Organisation as the supported party and five issues open, with the
articles that hold each, the Organisation's own position and fallback on each, and the units both
sides recorded as agreed (Arts. 2, 5, 7 and 12), which a suggestion may not reopen. It keeps one
source per (round, actor, issue), a party's note or the text where it wrote no note on that issue:
with two sources for one triple a position stays `unresolved`. It holds 41 sources.

Positions toward or away are keyed in `EXPECTED_MOVEMENT.json`, written before any code computing a
gap existed. Entry period, termination notice and the contribution are stated as figures by both
parties in consecutive rounds, so their gaps can be computed: entry and termination converge, and
the contribution converges in round 2 and diverges in round 3. The Organisation's round 1 note
quotes Sarvenna's 5,000 EUR in order to reject it, a trap for any reader of figures.
