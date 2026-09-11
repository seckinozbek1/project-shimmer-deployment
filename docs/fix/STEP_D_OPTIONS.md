# STEP D OPTIONS: absence rules that are never asked

Decision document for the operator. No code was written for D. Everything below was traced
in code and in the stopped run's saved map; nothing was measured, and no option is known to
work until a run scores it.

## The gap, exactly

`pairing_map.pair_units` pairs a rule with a unit only when the unit carries EVERY field the
rule names (`needed = needed_fields(rule_text, vocabulary)`, `missing = needs - have`, any
missing field rejects the pair with the reason "unit lacks ..."). `needed_fields` marks a
document label as named by a rule when every word of the label appears in the rule's text.
An absence rule ("every Class-A entry must state a calibration authority signature") names
the very field whose absence it checks, so the entry that lacks it is rejected, and the
entry that carries it is paired: the rule is asked only where it cannot fire.

Two further mechanisms compound it, both visible in the stopped run's map
(`output/runs/20260911T123328Z__d5728e4b/audit/pairing_map.json`):

1. **Label containment.** The glossary unit carries the labels `calibration authority`,
   `fault window` and `service interval`. Any rule whose text contains the phrase
   "calibration authority signature" also "names" the shorter label `calibration
   authority` (its words are a subset), so D02 and D03 are read as requiring a GLOSSARY
   field on every entry: `CONV-D02 needs: calibration authority, calibration authority
   signature, class`. Even the four entries that carry a signature are rejected for
   lacking `calibration authority`. D04 is read as needing `fault window` and D05 `service
   interval`, both glossary labels no entry carries.
2. **The absence check exists but is unreachable.** `paired_review.compute_checks` computes a
   `missing_field` check ("the rule names X and this unit does not carry it") from the union
   of fields the unit's PAIRED rules name; a rule that was rejected is not paired, so its
   field is never in that union and the check never fires. `pairing_map.unmatched_findings`
   mints a `missing_field` finding only for a unit that NO rule paired with; on the device
   corpus every entry pairs with D01 or a board-only rule, so that path minted nothing
   (`missing_field_findings: []`).

Net effect on the stopped run: D02, D03, D04 and D05 paired with nothing (88 rejections);
the four rules that check the planted flaw kinds never reached a call. Step A does not
change this: it decides who judges a plan, not which plans exist.

## What every option shares

- Built without measurement, proved on fixtures and the saved map, scored only on the VM.
- No domain word enters code: every option reads field labels from the operator's own
  document and rule text, as the map does today.
- The pairing map keeps recording the reason for every pair and every rejection.

## Option 0: leave it, measure as is

What changes: nothing. The measurement runs on D01 (13 pairs) and the board-only rules'
absence (step A). Cost: none. What it answers: how the model does on the one rule it is
asked; it cannot answer the neighbour question for the flaw kinds D02 to D05 check, because
those rules never reach a call. Worst case: the number the VM produces is a number about
one rule in eight and gets read as a number about the mechanism.

## Option 1: fix label containment only (longest match)

What changes: `needed_fields` counts a label as named only when it is not wholly contained
in a longer label the same rule text also names (a rule mentioning "calibration authority
signature" needs that label, not also `calibration authority`). Cost: small, about an hour
with its gate check; one function, no new concept. What it catches: D02 and D03 would pair
with the four entries that CARRY a signature, so D03 (is the signing role valid) can be
asked at all; D04 would still need `fault window` and D05 `service interval`, which are
glossary labels, so both stay unpaired unless their rule text is reworded by the operator
to name only the entry's own fields (`fault logged`, `fault acknowledged`, `service
record`). What it misses: the absence case itself; an entry missing its signature is still
rejected by D02. Worst case: a rule that genuinely needs two overlapping labels loses the
shorter one; the map's reason line would show it. This option is a prerequisite for 2 and 3
rather than an alternative to them.

## Option 2: the operator declares each rule's scope

What changes: a rule states which field(s) identify the units it governs, in the rule's
own heading, the same bracket mechanism the subject tags use (for example `[scope: class,
device]`, the words being the operator's own labels, read structurally, never listed in
code). The map pairs a scope-tagged rule with every unit carrying the scope fields, and
treats the rule's other named fields as CHECKED fields: an entry lacking one yields a
computed `missing_field` plan on that unit (Python, no model), or, where the rule
conditions the requirement ("Class-A"), an uncomputable plan the model judges with the
entry's text. A rule with no scope tag pairs exactly as today. Cost: moderate, about half a
day: the parser (one more bracket form, kept apart from severity and subject), `pair_units`
(a second pairing path), `plan_calls` (the absence plan), the pairing map's reason lines, a
gate check per piece, the README. What it catches: D02, D04 and D05 on every entry,
including the ones missing the field; D03 on the entries with a signature. What it misses:
nothing structural for this corpus; the conditional part of D02 (only Class-A entries) is
handed to the model, not decided by Python. Worst case, taken deliberately: absence becomes
a question asked on every scoped unit, so on the clean twin every Class-B entry without a
signature is a model call that must answer "not required", and every wrong answer there is
a false positive the clean-twin figure will show. The cost in calls: roughly one extra plan
per scoped rule per entry (18 entries, three rules: about 54 more plans, most of them model
calls on this corpus, since its bands are prose). It needs the operator to tag the scopes,
as the subjects were tagged.

## Option 3: absence by structure, no operator input (anchor fields)

What changes: the map derives each rule's scope itself: of the fields a rule names, the
ones that most units carry are its anchors, the rest are checked fields; a unit carrying
the anchors and lacking a checked field gets the absence plan of Option 2. Cost: moderate,
about a third of a day (no parser change), but with a heuristic in the map. What it
catches: the same cases as Option 2 on this corpus (D02's `class` and `device` are carried
by 18 of 19 units; the checked fields by one or four). What it misses: any document where
the split between anchor and checked fields is not visible in the counts (two fields each
carried by half the units). Worst case: the heuristic decides the wrong way on another
corpus silently, which is exactly the kind of fix that looks like it works; the map's reason
line would say "anchor" or "checked", so it is not invisible, but it is inferred from
counts rather than declared. This project's own discipline argues against it; it is listed
because it is the cheapest option that reaches the absence case.

## Option 4: route absence rules to a whole-document call

What changes: a rule whose named fields are carried by fewer than N units is judged in wide
mode (one call with the whole document, or the document's entries in chunks) instead of
paired. Cost: moderate, about half a day, and it changes the shape of what is measured:
paired mode exists because the whole-document call summarised rules instead of checking
them. What it catches: everything the model can read; what it misses: the reason paired
mode was built. Worst case: the measurement measures wide mode's known failure, not the
neighbour mechanism.

## What the decision needs

Whether absence is a question for Python (a computed `missing_field` plan, which will be
wrong wherever a rule conditions the requirement) or for the model (an uncomputable plan
on the scoped unit, which costs a call per unit and will show on the clean twin); and
whether the scope is declared by the operator (Option 2) or derived (Option 3). Option 1
stands on its own and does not need that answer.

Nothing in the answer key was consulted for this document. The rules and the map speak
for themselves.
