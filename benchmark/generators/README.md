# Synthetic test generators

Seeded generators that write complete test bundles in the published input format
(`docs/INPUT_FORMAT.md`, version `input-format-v1-draft`). Standard library only. They
never import Shimmer's code: every flaw they plant is checked by this package's own
reading of the format (`textrules.py`, `audit.py`, `ground_truth.py`).

**The suite measures Shimmer; it is never fitted to it (D-042).** Every key states the
ground truth the generator planted: what a correct reviewer should report, decided from
the facts the generator wrote, whether or not Shimmer computes it. No gate check asserts
that a key equals Shimmer's output. How far Shimmer agrees is a measurement, printed by
`py -3.12 scripts/generator_checks.py --agreement`.

## Use

```
py -3.12 benchmark/generators/generate.py suite dev          # benchmark/dev_suite/generated/
py -3.12 benchmark/generators/generate.py suite long_range   # benchmark/long_range/generated/
py -3.12 benchmark/generators/generate.py one f3 7 --out SOME_DIR [--long-range]
py -3.12 benchmark/generators/generate.py one f4 7 --out SOME_DIR --rounds 3
py -3.12 benchmark/generators/generate.py check benchmark/dev_suite/generated
```

The same family and seed always give byte-identical files. The gate check
`scripts/generator_checks.py` holds that, and the rest of the self-validation below.
`suite_listing.json`, written next to the tests, records the SHA-256 of the input-format
draft the suite was generated against (`input_format_sha256`).

**Retries.** A seed whose own draw cannot make a valid test (a build that raises, or a
test that fails its own validation) is retried inside the build, from a sub-seed
derived from the seed and the attempt number alone (`wordlists.make_rng`, up to
`MAX_ATTEMPTS` 20 in `__init__.py`), so the retry sequence, and the bytes, depend only
on the seed. The key's `generator.attempt` and the listing's `attempt` record the
attempt that was kept; a seed that builds at its own draw records none in the key and
gives exactly the bytes it gave before retries existed. Five such seeds are known (the
S3 round-3 adversarial sweep): f4 4003, 4007, 4020 and 4071 (a rename-probe check of
the reordered sections that does not hold) and f6 6097 (no carry mismatch that keeps
every row non-negative); each builds at attempt 1. No committed seed needs a retry.

## What one test is

One test is six bundles side by side in one folder (section 1 and 10 of the format):
the test, its clean twin, and the four perturbation probes of section 11. Folder and
file names are random letter tags, so no name says which is which; each key says
what its bundle is (`twin_of`, `probe`). `suite_listing.json`, next to the tests, maps
them for developers.

Each bundle holds `context/_review_targets.json`, the document, one reference file
(none in family 4), for some probes an earlier version, `conventions/rules_*.md` (or
`mandate_*.md`), and `answer_key.json` at the top. A family 4 bundle also carries
`case_manifest.json` at the top (the declared multi-round case, below), and holds only
case documents in `context/` (section 12). No per-test settings file is written:
section 8 says none is read.

## Families

| Family | Module | Planted kinds | Distractors |
|---|---|---|---|
| f1 tabular result sheet | `family_result_sheet.py` | result above its reference range, below it, a total volume that does not add up, a missing analyst (computed absence), a blank aliquot cell, a unit mismatch (a result written in g/L against a range in mg/L, or a total volume in L against a column in mL; the figure is right in the right measure, and it breaks CONV-SE, which requires each result in its range's measure and each total in its column's measure) | results exactly on a bound, decimal totals that add up |
| f2 declaration with arithmetic | `family_declaration.py` | line value not quantity times unit price (product), unit price above its band, below it (the ratio of line value to quantity agrees, so it duplicates and is not keyed), a consignment total that does not add up, a missing country of origin, a duty due that is not the duty rate applied to the stated total (rate; CONV-DE says the duty follows the total as written, so a wrong total's duty is right), a freight share that is not the freight as a percentage of the stated total (ratio: a stated ratio that disagrees with the unit's own figures), a summary row that does not carry its declaration line's value (cross-row, between two units that each add up) | unit prices on a bound, decimal products, a total written with comma groups |
| f3 financial statement | `family_statement.py` | current-period subtotal wrong, prior-period subtotal wrong, period change above the band the rule states, below it, a missing preparer | a period change just inside a bound, a subtotal with comma groups |
| f4 contract terms across two or three versions | `family_terms.py` | band breaches in the later version: unchanged, moved away into a breach, moved toward the band but still out, on a new term, on a renamed term, on a value in a different format | a term on its bound; the version changes below |
| f5 regulation-style provisions | `family_provisions.py` | a filing-to-notice gap over its window, a receipt-to-answer gap over its window, a filing fee above its band, below it, a definition without its source, an appeal provision without its appeal body | gaps exactly equal to the window, fees on a bound, filing provisions outside the appeal rule's pinned scope |
| f5 long-range layout | `family_provisions.py` | a notice window, an answer window, a fee above and below its band, each decided by a figure stated only in a unit of the use's own track at least twelve units away (a window definition, or a fee table that is no definition; two of the six deciding units name the track and the figure in other words) | gaps equal to their window, a fee on a bound, a filing and a fee the other track would break |
| f6 neighbour-dependent stock count | `family_ledger.py` | carry_in (the opening row mis-carried, the unit's own sum then disagrees), carry_out (the stated closing wrong; the next count carries the column sum), carry_mismatch (the opening row differs from the column sum of the count before and the received row absorbs it: each count adds up on its own, only the pair is wrong), shrinkage above the band, below it, a missing counter. CONV-LA states what is computed: the closing quantity is the column sum, and the opening row carries the column sum of the count before | the count after each carry_out and after each carry_in (it carries the carry_in's column sum and absorbs the difference in its issued or received row), which look mis-carried beside their neighbour's stated closing and are not; a shrinkage on its bound |

Every test plants at least 10 flaws of at least three kinds (f1: 14 of 6, f2: 18 of 8,
f3: 11 of 5, f4: 10 of 6, f5: 11 of 6, the long-range layout: 11 of 4, f6: 13 of 6).

**Flaws Python does not compute** are keyed all the same (input format, section 9): the
unit mismatches (`unit_mismatch`), the rate errors (`rate_mismatch`), the ratio errors
(relation `rate_mismatch`, kind `ratio_mismatch`), the cross-row copies
(`copy_mismatch`, the source unit in `source_unit`), the neighbour-only carries
(`carry_mismatch`, the neighbour in `depends_on_unit`), and the long-range windows and
fees (`date_window`, `above_band`, `below_band`, with `related_unit`). Each family
declares how to find them in the key's `ground_truth_checks`, and `ground_truth.py`
finds every instance in the rendered text again, in every bundle (the reworded-labels
probe with its checks reworded too). Each is keyed under a rule its text breaks as
written. The unit-mismatch scanner takes a sample's reference row by the family's own
planted parameter, not by restating Shimmer's row matching.

### Family 4: version changes and rename probes

Family 4 is keyed as a negotiation-style test (section 9): `prior_records` and
`band_irregularities` are what the scorer reads. Between the prior and the target it
plants: terms unchanged, changed inside the band, moved toward the band (also into it),
moved away, a term renamed with its value unchanged, a term renamed with its value moved
(by a seeded 2.05 to 45 percent of the earlier figure: above 2/0.98 = 2.0408 percent, so
never within 2% of the larger figure; the twin's repair of it is such a move too), a
term renamed and moved to another section (also moved by 2.05 to 45 percent), a
withdrawn term, a withdrawn term beside an unrelated new term in the same section and
measure, terms new in the later version, sections reordered, and a value written with
comma groups (unchanged).

Every expectation is the ground truth (D-042):

- `prior_records` holds every change record the versions call for: each term both
  versions state under the same label, and both withdrawn terms (`absent_since_prior`).
  A renamed term is the same term and gets no row.
- `expected_refusals` lists each renamed term: its earlier and later label, the unit
  where its refusal sits, the two figures and their measure (`value_a` the later,
  `value_b` the earlier, `unit`), and the refusal kind its planted figures support,
  derived from them by section 6's definitions (`family_terms.expected_refusal_kind`):
  within 2% of the larger figure, `possible_rename`; moved further in the same section,
  `possible_successor` (every measure here is non-empty, so never
  `possible_successor_no_unit`); another section, `null`. A refusal on the row's unit or
  a matched rename satisfies a row; a `null` row (Python is expected to refuse nothing)
  only a matched rename; a withdrawal record on it is a false positive. Every key, single
  or negotiation-style, names its task in `task_given_to_the_pipeline`.
- `version_changes` is the family's own plan of every term (`expect`:
  `unchanged_from_prior`, `changed_from_prior`, `moved_toward`, `moved_away`,
  `absent_since_prior`, `not_withdrawn` or `none`), computed from its own figures.
- `rename_probes` is one typed row per rename-probe kind: `renamed_value_unchanged`,
  `renamed_value_moved`, `renamed_moved_to_other_section` (each `expect` `not_withdrawn`,
  `satisfied_by` a refusal or a matched rename, only a matched rename for the one moved
  to another section, `false_positive_if` `absent_since_prior`), `withdrawn` and `withdrawn_beside_newcomer` (each `expect`
  `absent_since_prior`), `new_in_later_version` (`none`), `value_in_different_format`
  (`unchanged_from_prior`) and `reordered_sections` (the target's unit ids in the prior's
  reading order). Each row names the earlier and later label, the target and prior unit,
  both figures, both written forms and `moved_percent`.

The validator reads the versions back with the audit, which states facts and decides
nothing about a vanished label: the comparisons of labels both versions state must be
the plan's, the vanished labels must be exactly the withdrawn and renamed terms with
their earlier figures, the new labels exactly the new and renamed ones, and every rename
probe row must hold in the text (same or other section, the newcomer beside the second
withdrawal unrelated and in the same measure, the moved percentage as stated and inside
2.05 to 45 percent in every bundle, the twin included, the refusal kind the one its
figures support). Only section 6's 2% line is restated here, to name the kind a
refusal should carry; whether a vanished label was renamed is never decided from it.
The rename probes are measured in the ordinary two-version review of a bundle (the same
files without `case_manifest.json`, INPUT_FORMAT section 12); a multi-round run writes
no change records.

The scorer reports no per-kind recall for a negotiation-style test, so f4's six breach
kinds are for development.

### Family 5 in the long-range layout (S3d)

Every provision belongs to a track (Ordinary or Expedited). Four window definitions (a
notice and an answer window per track) state their window length; two fee tables (one
per track, which are no definitions) hold the band for each fee class; the fee-class and
appeal-body definitions decide nothing. All of them sit anywhere in the document among
the uses, and the reference file carries no figure, so a planted flaw cannot be judged
without the deciding unit of its own track. Two of the six deciding units (seeded, about
a third) name their track as a procedure (`Procedure: Standard` for `Ordinary`,
`Accelerated` for `Expedited`) and their figure in other words (`Period allowed`, or a
`Charge range` column); the reference file says so in prose, with no figure. Every
planted use sits at least twelve units from its deciding unit; each key entry names it
in `related_unit`, states the `distance`, and says whether the use carries a
cross-reference line (`cross_reference_line`): about half the uses do, planted ones
included, so a cross-reference baseline is not perfect by construction. A positional
baseline (the first 4 units, or the first k, k the number of distinct related units),
two label-only baselines (the nearest, or the first, unit carrying the deciding label:
`Window length`, or the `Fee range` column) and a track-and-term baseline (the nearest
unit stating the use's term, `decided_by_term`, with the use's own `Track` value) each
score below 1 in every bundle (`family_provisions.baselines`; printed, with their range,
by `py -3.12 scripts/generator_checks.py --baselines`). See
`benchmark/long_range/README.md` for exactly what holds.

### Family 4 as a declared multi-round case

Family 4 writes two or three rounds (`rounds` in `SEEDS.json`, `--rounds` on the
command line, two by default). Every bundle of a family 4 test (the test, its twin and
the four probes) carries `case_manifest.json` at the top, beside `answer_key.json`: the
live case manifest a declared multi-round Review is sealed and run with
(`--multi-round --multi-round-manifest case_manifest.json`, the controller's
`MULTI_ROUND_ARGV`). Built in `multi_round_case.py`:

- the live schema: `schema_version` 1, only the live top-level fields, `fixture`
  false, `allow_recommendations` false, `decision_support_mode` `trajectory_only`;
- rounds `r1`..`rN` in version order, one document each, named by its document id (the
  file's stem, as the pipeline's corpus loader names it): two rounds are the prior and
  the target; three rounds put the **earliest version** first. The earliest version is
  the prior with three ordinary terms (in three different sections) at other figures,
  same labels, same section order, drawn from its own random stream. It is a grounding
  file, never a declared prior (the ordinary review compares the target with the prior
  only), and only the case manifest names it;
- `context/` holds only the round documents and the targets manifest (section 12);
- one actor (`counterparty`, the party whose versions they are); one issue per term,
  keyed by its earliest label (`issue-<slug>`), so a renamed term keeps one issue
  across the rename. That is an operator declaration: a multi-round run is told the
  identity a blind two-version review has to refuse;
- one source per label line of every round document (state `accepted`), quoting the
  whole line, its span measured on the document text and its `unit_id` the unit that
  holds it.

The key adds `case_manifest`, `rounds` (`round_id`, `sequence`, `version`:
`earliest`, `prior`, `target`), `round_reuse` (the units whose text, label set and
measures repeat a unit of an earlier round), for three rounds `round_changes` (each term
at another figure in the earliest version), and `multi_round`: the multi-round form of
section 9, `planted` and `clean` entries scoped by `round_id` and `document_id` on that
document's unit id. Every round is keyed: in each, every term outside the band of the
mandate rule that governs it is a planted entry (the target round's entries are the
`band_irregularities` with their kinds; an earlier round's carry the kind
`breach_in_earlier_round`), a renamed term's earlier label under the rule naming its
later label (the case declares them one issue; `issue_id` says which), and the clean
entry is the unit holding the term on its bound. The twin repairs the last round only,
so its earlier rounds keep their breaches and no multi-round `twin_of` is named (open
item 26). The ordinary scorer reads none of these fields.

The validator restates the controller's `validate_live_case_manifest` rules
(`multi_round_case.validate`) and checks the declaration itself: rounds in version
order, only case documents in `context/`, a source for every label line on its unit, a
renamed term on one issue, the reuse and round changes as the documents show. The gate
check proves the restatement agrees with the controller (every generated manifest
accepted by both, every mutation in its list refused by both): the controller's
published rules, not Shimmer's review.

**Sealing a bundle.** The controller's sealer reads a test folder with
`_review_targets.json` at its top, `context/`, `conventions/` and `case_manifest.json`
only: drop `answer_key.json` and move `context/_review_targets.json` to the top.

## How the twin and the probes are built

- **Twin**: every unit is built clean first; a flawed unit is a copy with one value
  changed or one line removed (a carry_mismatch changes two cells of one unit; a copy
  error also changes its summary's total and duty). The twin uses the clean units: same
  headings, labels, conventions, reference file, earlier version and roles, a different
  document name, `"planted": []` (f4: `"band_irregularities": []`, its own plan), the
  same `clean` list, and both keys name each other.
- **Reworded labels**: one label that appears in a keyed reason is rewritten with other
  words of the same meaning in the document (and the earlier versions for f4);
  conventions and reference unchanged; the key's `field_label` updated (section 11.1),
  table cells of it too (`<label> rowN`), and the labels the `ground_truth_checks` name.
  The figure audit is skipped (by design, rules stop pairing through the label); the
  ground-truth scan runs, since every planted flaw is still there.
- **Reordered sections**: blocks of units are moved; the key's unit ids (and
  `depends_on_unit`, `source_unit`, `related_unit`, `distance`) are remapped; f6 cuts
  only between pairs, so a neighbour-dependent flaw stays beside its neighbour, and
  moves one block by a rotation whose only new neighbour pair is the last count before
  the first, which carries (the last count closes at the first count's opening, and no
  carry_in is the last count), so no new pair breaks the chain; the long-range layout retries the move until every distance
  stays at least twelve and every baseline below 1, and the key states the true
  distances. Fully re-audited, the carry scanner included.
- **A term only in the later version**: the term carries a keyed flaw in every family.
  f1, f2, f3, f5, f6 add an earlier version (the test's document less that term's line)
  declared as `prior`; f4 drops a term with a keyed breach from every earlier version
  (target unchanged), so its plan and `prior_records` lose that term's record. Fully
  re-audited.
- **A value in a different format**: one keyed figure rewritten with the same reading
  (`15.5` as `15.50`, `1500` as `1,500`, `45` as `45.0`). Key unchanged. Fully
  re-audited.

## Self-validation (S3 item 8)

`bundle.validate_test` runs before anything is written, and again in the gate check on
the written files. A test that fails writes nothing. It checks:

- at least 10 planted flaws and at least three kinds; every planted entry has a
  complete typed reason (unit, operator rule id, relation, kind, field label in
  normalised form, both figures as numbers); every key carries the required top-level
  fields of its form (INPUT_FORMAT section 9);
- every keyed entry's rule, read from the bundle's own conventions file, still states
  what that entry's kind breaks (each family's `RULE_STATEMENTS`): a rule reworded back
  to something the planted flaw does not break (a duty "on the summed line values", a
  carry of "the closing quantity" where the column sum is what is carried) is caught;
- every prose sentence of every reference file is read as its family declares (each
  family's `REFERENCE_READINGS`: a pattern the whole sentence matches, and a reader that
  names the units breaking it by plain string handling, or the reason the sentence states
  no condition on a unit), and no unit the key plants no flaw in breaks one
  (`bundle.check_reference_texts`); a sentence no reading declares is refused. f6's count
  procedure states CONV-LA's column-sum reading (each count opens with the sum of the
  quantity column of the count before it, and closes at the sum of its own); it used to
  say each count opens with the closing quantity of the count before it, which the clean
  count after every carry_out and carry_in breaks, and the gate check restores that
  sentence to show it caught;
- at least one clean distractor; the twin exists, plants nothing, names the test, and
  neither its audit nor the ground-truth scanners find any flaw in it; all four probes
  are present, probe 3's term carries a keyed flaw, and each probe differs from the test
  exactly as section 11 says;
- the figure audit of section 7, by this package's own code, on every unit: the audit
  reads the rendered Markdown, computes every product, sum, blank cell, band (table
  and rule-stated, with ratios and the low-side condition), date window and computed
  absence Python would compute, attributes each to a rule, and requires the result to
  equal the key exactly (a ratio finding that duplicates a planted band breach is the
  one tolerated extra, as section 9 says); no digit in a non-figure value; ids from its
  own slug rule; the directive rule of section 5 (scope only with requires, no
  `[unless: ...]`, every rule names a document label or declares a scope, every unit
  but the preamble covered); grounding files under 120 paragraphs, table passages
  within 900 characters, no unintended band sentence;
- the ground-truth scan (`ground_truth.py`): every flaw of the kinds the key's
  `ground_truth_checks` declares, found in the rendered text, equals the keyed entries
  of those kinds exactly, so a dropped entry and a flawed twin are both caught;
- for f6, the neighbour arithmetic: the carried figure read in both units disagrees
  exactly as the key says, every other count's first row is the column sum of the count
  before, and the whole twin chain is consistent; the gate check also reads CONV-LA a
  second time with plain string handling (`family_ledger.units_breaking_carry_rule`)
  and requires exactly the keyed units, and no clean unit, in every bundle;
- for f4, the version facts and the rename probes as above, and the case manifest: the
  controller's rules restated, the rounds the key names in version order, only case
  documents in `context/`, a source for every label line and one issue per renamed term,
  the key's reuse and round changes as the round documents show, and the `multi_round`
  key read back from the round documents, the conventions and the case manifest alone;
- for the long-range layout, in every bundle, probes included: every planted entry's
  related unit at its stated true distance and at least twelve units away,
  `definitions_first` as the text shows, related units both definitions and not,
  cross-reference lines on some planted uses and not on others and on 30 to 70 percent
  of all uses, every baseline below 1, and no figure in the reference file.

Each of the validator's messages that the round-3 adversarial check found never shown to
fire (the related units all definitions or none, a baseline at 1, the target round's
multi-round entries not the band breaches, a multi-round clean entry in the wrong
round), and a keyed rule's text reverted, is produced by its own mutation of a valid
test (`VALIDATOR_MUTATIONS` in the gate check; `--mutations` prints each).

## Agreement with Shimmer (a measurement)

`py -3.12 scripts/generator_checks.py --agreement` prints, per family and kind, how
many keyed flaws Shimmer's Python review of the document confirms
(`multi_round_rounds.review_document`, which computes no reference-table band, no date
window and no change record), and, per family 4 rename probe, what Shimmer's
`absent_checks` does with the earlier label against the ground truth (agrees, a missed
withdrawal, or a false withdrawal). It is never a pass condition.

## Input-format questions, as settled (D-025, revised by D-042)

The lane raised thirteen questions; the coordinator settled them from the code and the
format draft now states each answer (`input-format-v1-draft`, D-025). Ten of the lane's
readings stood; three changed the audit (9, 10, 13), and 11 is now stated more exactly.
D-042 then changed what a key may hold (1, 12 and 13 below).

1. **Neighbour-dependent flaws (f6).** Settled by D-042: a key states the ground truth,
   so a flaw wrong only beside its neighbour is keyed (`carry_mismatch`, the neighbour
   in `depends_on_unit`) although Python computes no relation between two units. The
   carry_in and carry_out kinds still show inside their own unit as a `sum_mismatch`.
2. **`[unless: ...]`.** Settled as read: section 5, rule 7 now forbids it outright. The
   condition on a field is the pinned scope of a completeness rule
   (`[scope: provision type=Appeal]`); the condition on another rule is in the text
   only (`Read with CONV-RD, ...`), which only a reviewer reads.
3. **Planted flaws in a two-version test (f4).** Settled as read: the
   `band_irregularities` rows are the planted flaws; `unit_id`, `value_b` and `kind`
   are ignored by the scorer, which reports no per-kind recall for such a test, so f4's
   kinds serve development only. Rows must differ in (label, relation, figure); the
   validator checks it.
4. **`twin_of` on a probe.** Settled as read: a probe's key has none (section 11).
5. **Where the single-version earlier version lives.** Settled as read: only probe 3
   declares one. The earlier version is a grounding file, so it is audited as reference
   material (its tables and sentences take part in bands and the bound search).
6. **A blank cell in a summed column.** Settled: the sum runs over the filled cells
   and both findings are computed independently. Reading kept: never planted together.
7. **The low side of a band the rule states itself.** Settled as read: always firm
   (section 7). f3, f4 and f6 `below_band` entries stand.
8. **Identical bound sentences.** Settled as read: two copies tie wherever they sit.
   Bound sentences stay in the reference file only.
9. **What a sentence is.** Changed. The audit now reads as section 7 says: per
   paragraph, lines starting with `|` or `#` are dropped, the rest joined with single
   spaces and split after `.`, `?` or `!`; a grounding file (the earlier version
   included) only as its stored passages (a prose paragraph's first 200 characters);
   the document whole. A candidate holds exactly one number in all (a date counts as
   three) and that number has a measure. The winner must be unique by word count and by
   distinct-word count. Re-checked on every family 5 bundle of both suites: each window
   rule has exactly one candidate, its intended sentence.
10. **Attribution.** Changed. The score is the code's: the set of the named labels'
    words, 2 for each in the field label, 1 for each in the basis sentence split at
    spaces (`sum of N values under <column>`, `<a> times <b>`,
    `<column> is filled in N of M rows`), so `sum`, `filled` and counts of three or more
    digits score when a named label holds them. The planted rule must still win
    strictly, under that count and under a per-label count, never by reading order or
    the all-zero default.
11. **The measure of a table cell.** Settled: in a document table a cell's own measure
    replaces the header's; in a reference table the header's wins. Every cell written
    here is a plain number (or a plain range), and the audit refuses any other cell.
12. **"Unit mismatches" in family 1.** Settled by D-042: Python compares nothing in
    another measure, but a correct reviewer reports the measure, so unit mismatches are
    planted and keyed (`unit_mismatch`, both measures in the claim) from the family's
    ground truth and found again by the ground-truth scanner.
13. **The rename window.** Settled by D-042: no key follows Shimmer's rename refusal.
    Whether a vanished label was renamed or withdrawn is the family's ground truth;
    section 6 of the format states Shimmer's own rule, and section 9 how a key lists the
    refusals it expects (`expected_refusals`). Revised in S3 checker round 2: the kind
    a refusal should carry is derived from the planted figures by section 6's 2% line,
    and a moved rename moves by 2.05 to 45 percent, so it never sits within 2% of the
    larger figure.

## File names

No source file name matches `**/*key*`, `**/*config*.py`, `**/*secret*` or
`**/*credential*` (the gate check asserts it). The generated `answer_key.json` files
sit under the ignored `generated/` folders.
