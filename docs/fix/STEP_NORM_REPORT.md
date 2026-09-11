# STEP NORM REPORT: the two blockers, and what they cost in model calls

Written 2026-09-12, continuing the session that was cut off mid-edit. No pipeline run, no
generation model; offline encoding was permitted and not needed for this step. Every figure
below is a deterministic computation against the real corpora on disk, reproducible with the
current tree.

## What this step closes

Two blockers, both traced and proved in the previous step's report, both named there as the
sole source of the 44 percent figure. The rule-to-field matcher measured in between (bag of
words plus cosine) is not part of this and changed nothing on this corpus; that measurement
stands as recorded, and nothing was built from it.

### Blocker one: the shared normalisation function

`pairing_map._norm_label` split a hyphen and then dropped the single letter by its `len(w) > 2`
floor, so "Class-A sensor", "Class-B sensor" and "Class-C sensor" all reduced to
`('class', 'sensor')`. Three different tolerance bands were indistinguishable, and `match_row`
correctly refused to guess between them. There was no stem either, so a glossary saying "fault
timestamp" could never meet a rule saying "state the two timestamps". And two independent raw
word-bag builders served the rule side (`needed_fields`, `date_pair_for_rule`), already drifted
from each other and from `_norm_label` before either defect was found.

Fixed at that one shared layer:

- a hyphen between two word characters JOINS, using an ASCII sentinel substituted before the
  split. A Unicode look-alike hyphen was tried first and is NOT a word character under `re`'s
  own UNICODE classification, so it failed silently exactly as the raw split did; the
  placeholder's own `re.match` result was tested before it was trusted.
- `_stem` folds a trailing plural: strip trailing `s`, or `-ies` to `-y`. Two suffix rules,
  refusing after `ss`, `us`, `is`, or on a word of three characters or fewer. Checked against
  every word in the corpus rather than assumed: `class`, `corpus`, `diagnosis` and `guess` are
  protected; `timestamps`, `visits`, `dates`, `authorities` and `applies` fold correctly.
- the two duplicate rule-side builders are DELETED, not synchronised. A fold applied to one
  side of a subset test does nothing at all.

### Blocker two: connecting-word extraction

`_label_lines_with_dates` took the whole post-date remainder of a value line as connecting
vocabulary, so the service record offered "last", "next" and "record" as though the rule had
stated them. Those are how the document tells its two dates apart and what it calls its wrapper
label, not what the rule is about.

The words are now drawn PER DATE, from the window running from the previous date to this one,
and for a two-date line only their INTERSECTION is kept. A word describing what the pair IS
sits beside both dates; a word telling one date FROM the other sits beside only one. On the
real line the windows are `{last, calibration, visit}` and `{next, calibration, visit, logged}`
and the intersection is `{calibration, visit}`, exactly the concept the rule names. The
narrowing is positional: nothing knows that "last" is an ordinal, only that it sits beside one
date and not the other. No word list.

The line's own label and its date description are also kept as two independent routes rather
than unioned, since requiring a rule to name both meant "Service record" blocked a pair whose
description the rule states outright.

## The survey, run before the fixture was changed

The operator's instruction was to find every place a rule's prose is matched on a bare word a
hyphen would now bind, across all corpora on disk, and to report rather than absorb anything
that depended on the old split. Evidence: `docs/fix/HYPHEN_SURVEY.log`,
`docs/fix/HYPHEN_PAIRS_CHECK.log`.

Six corpora, roughly sixty distinct hyphenated tokens, including identifiers (`cat-alder`,
`res-birch`, `spec-cedar`, `unit-*`), compounds (`self-calibrating`, `calibration-complete`,
`in-range`, `item-level`, `dublin-core`, `one-time`) and the device classes themselves.

Named-field sets change in three corpora, and one of the three is not the hyphen at all:

- `catalogue_records`: eight rule/document combinations change, all from the STEM
  (`rights` to `right`, `requires` to `require`), not the hyphen.
- `negotiation_r2_to_r3` and `r3_to_r4`: `one time 401 contribution` becomes
  `one-time 401 contribution`; the label binds and still matches its rule.
- `device_log_review` and its clean twin: the intended Class-A/B/C change.

**The pair sets are byte-identical before and after on all twelve corpus documents.** The label
renames move both sides together, so nothing is lost or gained anywhere. The blast radius is
confined, now verified across six corpora rather than asserted from two.

## The three checks, decided by the operator

- **215** and **217** were written as markers that a blocker still existed. Their falsification
  is the result wanted, so both now pin the new behaviour: 215 asserts the band IS minted, with
  a Class-B unit binding to the 20-to-60 row and a Class-C unit to the 70-to-110 row, in prose
  and in a real markdown table alike; 217 asserts D04 finds both halves and settles.
- **208** encoded an assumption from before scope declarations existed, expecting a rule saying
  "Class-A" to name the bare `class` label. The fixture changed. It now pins BOTH facts:
  "Class-A" is one token and does not name `class`, while a rule that genuinely says "class"
  still does, so the join cannot silently swallow the real case.
- 217's D05 assertion was INVERTED when the extraction was narrowed, as its own failure message
  instructed, not deleted, and gained a neutralise-and-restore: with the connecting words taken
  as the whole remainder again, D05's pair goes away; restored, it comes back.

## The number

Both twins, recomputed with the current tree, deterministically, no run, against the baseline
this work started from:

| | flawed twin | clean twin |
|---|---|---|
| model calls before | 32 | 41 |
| model calls now | **17** | **23** |
| cut | 47% | 44% |

Per rule on the flawed twin: D01 moves from `uncomputable` to 6 computed `band` plans, D02
keeps its 5 `absence_computed`, D04 and D05 each become one computed `duration`, D03 keeps 4
`absence_judged` and D06 keeps 13 `uncomputable`. On the clean twin D01 yields 3 computed
bands, and both duration rules compute, AGREE (9 hours against a 24-hour window, 73 days
against a 90-day interval) and cost no call at all, which is why its settled count is lower
while its calls still fall.

What remains is genuine judgment by the operator's own decision: D03 (a qualifying role, where
a phrase list carries the same silent-failure fault as a role list) and D06 (neighbouring
entry). D07 and D08 are never paired at all, being properties of a finding's shape rather than
comparisons over a document's fields.

The 44 percent figure was predicted from tracing these two blockers alone, and it landed:
44 percent on the clean twin, 47 on the flawed.

## Gate

`PASS=216 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=218`, the two permanent pre-existing failures only
(check 01, missing `prompts`/`snapshots`; check 145, the missing contamination-probe fixture).
No checks added; three updated, each still proved by neutralise, fail, restore, pass.

## Commits

- `aae76b0` Normalisation: one shared tokeniser, hyphen joined, plural folded
- `bc57116` Connecting words drawn per date, so ordinal markers cannot enter

Nothing pushed.

---

STEP NORM COMPLETE (both blockers closed at the shared layer, surveyed across six corpora
before landing, gate green, 32 to 17 and 41 to 23)
