# Synthetic test generators

Seeded generators that write complete test bundles in the published input format
(`docs/INPUT_FORMAT.md`, version `input-format-v1-draft`). Standard library only. They
never import Shimmer's code: every figure they plant is checked by this package's own
reading of the format (`textrules.py`, `audit.py`).

## Use

```
py -3.12 benchmark/generators/generate.py suite dev          # benchmark/dev_suite/generated/
py -3.12 benchmark/generators/generate.py suite long_range   # benchmark/long_range/generated/
py -3.12 benchmark/generators/generate.py one f3 7 --out SOME_DIR [--long-range]
py -3.12 benchmark/generators/generate.py check benchmark/dev_suite/generated
```

The same family and seed always give byte-identical files. The gate check
`scripts/generator_checks.py` holds that, and the rest of the self-validation below.

## What one test is

One test is six bundles side by side in one folder (section 1 and 10 of the format):
the test, its clean twin, and the four perturbation probes of section 11. Folder and
file names are random letter tags, so no name says which is which; each key says
what its bundle is (`twin_of`, `probe`). `suite_listing.json`, next to the tests, maps
them for developers.

Each bundle holds `context/_review_targets.json`, the document, one reference file,
for some probes an earlier version, `conventions/rules_*.md` (or `mandate_*.md`),
and `answer_key.json` at the top. No per-test settings file is written: section 8
says none is read.

## Families

| Family | Module | Planted kinds | Distractors |
|---|---|---|---|
| f1 tabular result sheet | `family_result_sheet.py` | result above its reference range, below it, a total volume that does not add up, a missing analyst (computed absence), a blank aliquot cell | results exactly on a bound, decimal totals that add up |
| f2 declaration with arithmetic | `family_declaration.py` | line value not quantity times unit price (product), unit price above its band, below it (the ratio of line value to quantity agrees, so it duplicates and is not keyed), a consignment total that does not add up (cross-row sum), a missing country of origin | unit prices on a bound, decimal products, a total written with comma groups |
| f3 financial statement | `family_statement.py` | current-period subtotal wrong, prior-period subtotal wrong, period change above the band the rule states, below it, a missing preparer | a period change just inside a bound, a subtotal with comma groups |
| f4 contract terms across versions | `family_terms.py` | band breaches in the later version: unchanged, moved away into a breach, moved toward the band but still out, on a new term, on a renamed term, on a value in a different format | a term on its bound; the version changes below |
| f5 regulation-style provisions | `family_provisions.py` | a filing-to-notice gap over its window, a receipt-to-answer gap over its window, a filing fee above its band, below it, a definition without its source, an appeal provision without its appeal body | gaps exactly equal to the window, fees on a bound, filing provisions outside the appeal rule's pinned scope |
| f6 neighbour-dependent stock count | `family_ledger.py` | carry_in (the opening row mis-carried from the count before), carry_out (the stated closing wrong; the next count carries the right figure), shrinkage above the band, below it, a missing counter | the count after each carry_out, which looks mis-carried beside its neighbour and is not; a shrinkage on its bound |

Every test plants at least 10 flaws of at least three kinds (f1: 12 of 5, f2: 12 of 5,
f3: 11 of 5, f4: 10 of 6, f5: 11 of 6, f6: 11 of 5).

Family 4 is the two-version form, keyed as a negotiation-style test (section 9):
`prior_records` and `band_irregularities` are what the scorer reads. Between the two
versions it plants: terms unchanged, changed inside the band, moved toward the band
(also into it), moved away, a term renamed with its value unchanged (refused as a
possible rename, no record), a term renamed with its value moved (absent_since_prior
on the old label), a withdrawn term (absent_since_prior), a term new in the later
version (no record), sections reordered, and a value written with comma groups
(unchanged). `version_changes` in the key is the family's own plan of every record,
computed from its own figures; the validator requires the audit to agree with it. The
scorer reports no per-kind recall for a negotiation-style test, so f4's six kinds are
for development.

Family 5 with `long_range` puts the four definitions first and every flaw at least
twelve units from the definition it needs. Every family 5 key entry names that unit in
`related_unit` (for a definition without its source, the farthest provision using it).

**TODO (family 4, multi-round).** The three-version (multi-round) case declaration is
written only after S2 merges, against S2's live case manifest (section 12 of the
format is still empty). Nothing here guesses that manifest. Once section 12 lands,
add the three-version form to `family_terms.py`, regenerate the suite and re-run the
generator gate check.

## How the twin and the probes are built

- **Twin**: every unit is built clean first; a flawed unit is a copy with one value
  changed or one line removed. The twin uses the clean units: same headings, labels,
  conventions, reference file, earlier version and roles, a different document name,
  `"planted": []` (f4: `"band_irregularities": []`, records recomputed), the same
  `clean` list, and both keys name each other.
- **Reworded labels**: one label that appears in a keyed reason is rewritten with other
  words of the same meaning in the document (and the earlier version for f4);
  conventions and reference unchanged; the key's `field_label` updated (section 11.1).
  This probe is checked for form only: by design, rules stop pairing through the label.
- **Reordered sections**: blocks of units are moved; the key's unit ids (and
  `depends_on_unit`, `related_unit`) are remapped; f6 cuts only between pairs, so a
  neighbour-dependent flaw stays beside its neighbour. Fully re-audited.
- **A term only in the later version**: f1, f2, f3, f5, f6 add an earlier version (the
  test's document less one figure-bearing line) declared as `prior`; f4 adds one new
  term line to the later version. Key unchanged. Fully re-audited.
- **A value in a different format**: one keyed figure rewritten with the same reading
  (`15.5` as `15.50`, `1500` as `1,500`, `45` as `45.0`). Key unchanged. Fully
  re-audited.

## Self-validation (S3 item 8)

`bundle.validate_test` runs before anything is written, and again in the gate check on
the written files. A test that fails writes nothing. It checks:

- at least 10 planted flaws and at least three kinds; every planted entry has a
  complete typed reason (unit, operator rule id, relation, kind, field label in
  normalised form, both figures as numbers);
- at least one clean distractor; the twin exists, plants nothing, names the test, and
  its audit finds no comparison at all; all four probes are present and each differs
  from the test exactly as section 11 says;
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
- for f6, the neighbour arithmetic: the carried figure read in both units disagrees
  exactly as the key says, every other neighbour pair carries it, and the whole twin
  chain is consistent;
- for f4, the change records computed from the audit equal the family's own plan,
  rename refusals included.

## Input-format questions, as settled (D-025)

The lane raised thirteen questions; the coordinator settled them from the code and the
format draft now states each answer (`input-format-v1-draft`, D-025). Ten of the lane's
readings stood; three changed the audit (9, 10, 13), and 11 is now stated more exactly.

1. **Neighbour-dependent flaws (f6).** Settled as read: Python computes every relation
   inside one unit, so a neighbour-dependent flaw is keyed only where it shows inside its
   own unit (here a `sum_mismatch`); the neighbour is named in `depends_on_unit`, an
   extra field the scorer ignores (section 9).
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
12. **"Unit mismatches" in family 1.** Settled as read: disagreeing measures are never
    compared and nothing is written, so there is nothing to key. Not planted.
13. **The rename window.** Changed. A new label's figure is a possible rename when it
    differs from the earlier figure by at most 2% of the larger of the two in absolute
    value, 2% included (from 100, 102.04 is refused and 97.96 is not). A label is new
    unless the earlier version states it, under any heading, with a successful lookup;
    a refused lookup counts as new. The audit and f4's own plan both use this; f4's
    renamed terms either stay equal or move more than 5%, so no seed changed.

## File names

No source file name matches `**/*key*`, `**/*config*.py`, `**/*secret*` or
`**/*credential*` (the gate check asserts it). The generated `answer_key.json` files
sit under the ignored `generated/` folders.
