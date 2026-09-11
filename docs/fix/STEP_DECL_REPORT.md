# STEP DECL REPORT: the four declarations, checked against the code before applying

**Built without measurement. Everything here is a deterministic probe of the real parser,
pairing map and call planner on the two device corpus files; no model was called and no
run was started. No fix is known to be correct until a run scores it, and the worst-case
reading is the one to take.**

**Outcome: nothing applied.** The operator's instruction was to stop and say so if a scope
field name does not match what the parser reads off the entries, or if any of the four
cannot be expressed this way. One of the four (D02) does not match as written, and two
(D04, D05) can be written as declared but then express a different rule from the one on the
page. Both device corpus files are untouched; the four headings are as the subject-tag
commit left them.

## How this was checked

The four headings, byte for byte as the operator wrote them, were substituted for the
existing D02 to D05 headings of `device_conventions.md` (the two twins' files are
identical, verified with `diff`) and parsed with `convention_parser._parse_text_lines`.
The resulting rules were run through `pairing_map.build_pairing_map` and
`paired_review.plan_calls` on `device_log_flawed.md` and `device_log_clean.md`, exactly as
phase 5.5 calls them, with no ranker and no reference bands. Counts and labels only were
read; no document value is written here.

## What the parser reads off the entries

Every field label the four declarations name exists in both logs' label vocabulary:
`class` and `device` on 18 of 19 units (the glossary is the nineteenth), `calibration
authority signature` on 4 units (flawed) and 7 (clean), `fault logged` and `fault
acknowledged` on 1 unit, `service record` on 1 unit. Every unit's `class` line carries one
of three values, which normalise to `class-a sensor`, `class-b sensor`, `class-c sensor`
(8, 8 and 2 units).

## The four, one by one

### D02 `[scope: class=A] [requires: calibration authority signature]`: does not match

The parser reads the declaration correctly (`scope=[{"label": "class", "value": "a"}]`,
`requires=["calibration authority signature"]`). The pairing map then compares the declared
value with the unit's own value by equality after lowercasing and whitespace collapse
(`pairing_map.pair_units`, the `wrong` test, `have_values.get(lab) != v`). The document's
value is `class-a sensor`, the declaration's is `a`, and they are not equal. Result on both
corpora: 0 of 19 units paired; 18 rejected with "unit's class does not carry the value the
rule's scope declares", 1 (the glossary) rejected for lacking the field. D02 would pair
with nothing, exactly as it did before the declaration.

Written as `[scope: class=Class-A sensor]` (the value as the document writes it; the
comparison is case-insensitive) the same declaration pairs with the 8 Class-A entries on
both corpora and mints a computed absence, no call, on every Class-A entry with no
signature line: 5 on the flawed log, 2 on the clean twin (the two are `u04-entry-unit-cedar`
and `u18-entry-unit-teasel`, whose labels are class, device and note, or class, device,
reading and the two fault lines; whether the twin means them as clean is the key's to say,
and the key is not opened here).

The alternative is a change to the declaration, not to the code. A code change that made
`A` match `Class-A sensor` would be a containment test on a document value, which the
operator ruled out when scope was made declared rather than derived.

### D03 `[scope: calibration authority signature]`, no requires: expressible as written

Pairs with the 4 (flawed) and 7 (clean) signature-bearing entries and plans one
`absence_judged` question per entry, each a model call on that unit alone. What the judged
payload carries, stated precisely because a miss on the VM run would be read against it: the
unit's own text, its two immediate neighbours, the document map (titles only) and the
reference excerpt, which in paired mode is the embedding-store selection over every file in
`input/context/`, the log itself included (nothing excludes the document under review from
the hits, and with no embedding store the fallback is the log's own paragraphs), each prose
excerpt clipped at 200 characters (`reference_builder.PROSE_EXCERPT_CHARS`). So the
glossary's calibration-authority definition can reach a judged call two ways: as a clipped
reference passage from the log's own `u01`, and for `u02` alone as `preceding_unit_text`.
Neither is guaranteed for a given call, since the selection is by embedding similarity and
the clip is 200 characters. Which passages actually reached each call is what
`call_evidence.jsonl` records (`reference_ids`, and the subset the renderer kept whole), and
that is the file to read before blaming the model for a D03 miss.

### D04 `[scope: device] [requires: fault logged, fault acknowledged]`: expressible, but a different rule

Pairs with all 18 device entries on both corpora and mints 34 computed absences on each:
17 entries lack `fault logged` and 17 lack `fault acknowledged`. The counts are identical
on the flawed log and the clean twin, because the twin carries the fault lines on the same
single entry. The one entry that carries both fields (`u18-entry-unit-teasel`) receives
no plan at all: a scoped rule with a declared requires never reaches the judged path, never
reaches the uncomputable path (`plan_calls` skips scoped rules there by design), and
Python computes no gap between two timestamps (its relations are `missing_field`,
`sum_mismatch`, `product_mismatch`, the three band relations, and the prior-comparison
relations; nothing subtracts two times or two dates).

So under this declaration the rule on the page ("a device's own logged fault must be
acknowledged within the standard fault window") is never asked of the one entry it is
about, while 17 entries that logged no fault are each reported twice for not logging one.
The declaration expresses "every device entry must log a fault and acknowledge it", which is
not D04.

The expressible form of D04's own condition is `[scope: fault logged]` with no requires:
the entry that logged a fault is in scope, and the model is asked, on that unit alone,
whether the acknowledgement fell within the window. That is one judged call on `u18`, on
both corpora, and the same 200-character reference-excerpt limitation as D03 applies to
the glossary's window figure (the glossary is `u01`; `u18`'s neighbours are `u17` and
`u19`). It is still a model judgement of a duration, which nothing in Python checks.

### D05 `[scope: device] [requires: service record]`: expressible, the same shape as D04

Pairs with all 18 device entries on both corpora, 17 computed absences on each, and the
one entry carrying a service record (`u19-entry-unit-vetch`) receives no plan. The rule on
the page (the gap between two calibration visits must not exceed the service interval) is
never asked of that entry. The expressible form of its own condition is
`[scope: service record]` with no requires: one judged call on `u19`.

## The totals, for the plan-count decision

| declaration set | corpus | pairs | plans | of which absence_computed | absence_judged |
|---|---|---|---|---|---|
| the four as written | flawed | 66 | 81 | 51 (D04 34, D05 17; D02 0) | 4 (D03) |
| the four as written | clean | 75 | 90 | 51 (identical) | 7 (D03) |
| D02 as `class=Class-A sensor`, rest as written | flawed | 74 | 86 | 56 (D02 5) | 4 |
| D02 as `class=Class-A sensor`, rest as written | clean | 83 | 92 | 53 (D02 2) | 7 |

The other plans are D01 and D06 uncomputable calls (13 flawed, 16 clean, each), unchanged
by the declarations. The stopped W6 run had 64 pairs from 8 rules with D02 to D05 pairing
with nothing; the rise the operator expected (about 54) is the 51 computed absences of D04
and D05, and it lands on the clean twin in full.

## What is waiting on the operator

1. D02: `[scope: class=Class-A sensor]` (the document's value, case-insensitive), or
   another value form the operator prefers. The parser and the map handle a value with a
   space and a hyphen; the probe proves it.
2. D04 and D05: keep the declarations as written, knowing they express a presence rule
   and leave the gap unasked, or write them as `[scope: fault logged]` and
   `[scope: service record]` with no requires, so the one entry each is about gets a judged
   call and nothing else fires. Or a third form.
3. D03: apply as written; the limitation above is recorded, not fixed.

The probe script is in the session scratchpad and reads nothing but the two corpus files
and the modules under `scripts/`.

## The operator's decision, and what was applied

The operator answered the same evening, recording the three errors in their own words: D02
was a value that matches nothing, since the test is equality on the normalised value and the
document says Class-A sensor; D04 and D05 turned a duration rule into a presence rule, which
is why they minted 34 and 17 absences identical on the clean twin while the one entry each
rule is actually about got no plan at all; their own condition is about the gap between two
timestamps, not about whether the fields exist, so they carry a scope and no requires, and
the judgment goes to the model. The four headings applied, byte for byte, to both corpus
files (the twins remain identical, verified with `diff`):

```
## CONV-D02 , conv-calibration-signature [required] [conformance] [scope: class=Class-A sensor] [requires: calibration authority signature]
## CONV-D03 , conv-calibration-authority [required] [conformance] [scope: calibration authority signature]
## CONV-D04 , conv-fault-window [required] [conformance] [scope: fault logged]
## CONV-D05 , conv-service-interval [required] [conformance] [scope: service record]
```

The probe re-run on the files as applied, no substitution:

| | flawed | clean twin |
|---|---|---|
| pairs (was 34 / 46 at HEAD with no declaration) | 40 | 49 |
| plans (was 34 / 46) | 37 | 43 |
| D02: paired with the 8 Class-A entries; computed absences, no call | 5 | 2 |
| D02: in scope, signature present, no plan (nothing to flag) | 3 | 6 |
| D03: judged, one call per signature-bearing entry | 4 | 7 |
| D04: judged, one call, on the one entry that logged a fault (`u18`) | 1 | 1 |
| D05: judged, one call, on the one entry with a service record (`u19`) | 1 | 1 |
| D01 and D06 uncomputable calls, unchanged | 13 + 13 | 16 + 16 |
| model calls in the review phase (plans minus computed absences) | 32 (was 34) | 41 (was 46) |

So the declared form costs FEWER calls than the undeclared tree, not the fifty-odd more the
presence form would have: D02's four (flawed) and seven (clean) uncomputable calls became
Python-decided absences with no call, and D04 and D05, which paired with nothing before, now
each buy exactly one narrow call on the entry they are about. The two D02 absences on the
clean twin (`u04-entry-unit-cedar`, `u18-entry-unit-teasel`, Class-A entries with no
signature line) stand as the declaration says they should; whether the twin's key counts
them is the scorer's to say on the VM.

Gate check 197 (the corpus site asserts the eight rules and CONV-D03's bracket severity) was
run alone on the applied file: it passes, because a declaration bracket is skipped by the
subject reader and the rules' subjects are unchanged. The full suite runs once for this
commit and the README commit together, since both were in the tree it read.

Everything here is a deterministic count of what the planner would do. No run has scored it.
The D03, D04 and D05 questions go to the model with the reference excerpt's 200-character
prose clips, which may or may not carry the glossary passage each question turns on
(recorded above); that is where a miss on the VM run would come from first, and
`call_evidence.jsonl` is what settles it after the fact.

---

STEP DECL COMPLETE (four declarations applied to both twins on the operator's corrected
wording; 37 and 43 plans, 32 and 41 calls, D04 and D05 reach the model once each; built
without measurement, the run is owed)
