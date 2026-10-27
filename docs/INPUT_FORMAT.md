# Shimmer input format

Version: `input-format-v1-draft`

This document tells you how to prepare a test for Shimmer. Every rule here describes what the code does today. All examples are invented. It is a draft: it is frozen as `input-format-v1` before any sealed test is written, and after the freeze it never changes (a change would be a new version).

## 1. What a test bundle is

A **test bundle** is one folder holding everything one test needs. It is **sealed** once written: nothing in it changes after a result on it has been seen.

```
<bundle>/
  context/
    _review_targets.json     the manifest (section 6)
    <document>.md            the document under review
    <earlier version>.md     optional (section 6)
    <reference>.md           the reference corpus, one or more files (section 7)
  conventions/
    <rules>.md               the conventions (sections 3 to 5)
  answer_key.json            the answer key (section 9)
```

- Only files directly inside `context/` and `conventions/` reach Shimmer. Subfolders are ignored.
- `answer_key.json` stays at the top of the bundle. Never put it, or any answer, in `context/`: a `.json` file there is read as a document.
- Write every file as UTF-8 Markdown (`.md`). Headings and tables are read from Markdown structure.
- A file whose name starts with `_` is never read as a document.
- **Neutral naming**:
  - File names, the bundle folder name, headings and labels use only ASCII letters, digits, `_` and `-`, with no spaces.
  - No name hints at the flaws, the answers, or which twin is clean. Write `price_list_k7.md`, never `price_list_flawed.md`.

## 2. Documents and units

Shimmer splits each document into **units**, the pieces a rule is applied to.

- A level-1 heading (`# Title`) is the title. It does not start a unit.
- Every heading of level 2 to 6 starts a unit, which runs to the next such heading. A `###` heading inside a `##` section starts its own unit, so use one heading level for entries.
- The **unit id** is built in three parts:
  - the letter `u`;
  - the heading's position among those headings, as two digits from `01`;
  - a hyphen, then the heading's **slug**: the heading lowercased, every run of characters other than `a-z` and `0-9` replaced by `-`, cut to 40 characters.

  So `## Item P-101` as the second heading has the id `u02-item-p-101`. Keep headings ASCII and distinct.
- **The preamble unit.** Text before the first unit heading becomes the unit `u00-<slug of the title>`. This happens only when that text holds something besides headings and rule lines (`---`). It never shifts the other ids.
- **A document with no unit headings** is split by its tables. One table gives one unit per row (`u01-row`, `u02-row`, ...). Several tables give one unit per table (`u01-table`, ...). Otherwise the whole document is one unit (`u01-document`). Prefer headings.

**Fields.** A unit's fields come from two places only.

1. **A label line**: `Label: value`, optionally after `- `.
   - The label starts with a letter and is 2 to 49 characters of letters, digits, spaces and `( ) / % . _ -`.
   - The label ends at the first colon. It cannot contain a comma.
   - A line with nothing after the colon is not a field: that field counts as absent.
2. **A table**: a header row, a separator row (`|---|---|`), then body rows.
   - Each header cell is a field label of the unit.
   - A **measure** in brackets at the end of a header, as in `Line total (EUR)`, is the column's unit of measurement. It is not part of the label.

**Normalised labels.** Labels are compared after **normalisation**:

- The label is lowercased and split on spaces and punctuation. A hyphen between two letters or digits keeps a word whole.
- Words of two characters or fewer are dropped, and so are small function words (a, the, of, and, per, each, must, and similar).
- One trailing plural `s` is removed, and `-ies` becomes `-y`. This does not happen after `ss`, `us` or `is`, nor on words of three letters or fewer.

So `Line totals` equals `line total`, and `Item ID` is just `item`.

**Figures.**

- The first number in a value is the field's figure.
- Thousands may be grouped with commas or spaces. A single comma with no point is a decimal comma: `12,5` is 12.5, while `1,250` is 1250.
- The measure is the token after the number (`4 box`, `12 EUR/box`, `45%`). It can also be a currency symbol or a 2 to 4 capital-letter code before the number (`€12`, `EUR 12`).
- Two figures compare only when their measure tokens agree: `€12` and `12 EUR` do not.
- In a label line, write the measure after the figure, never in brackets in the label.
- Write dates in ISO form (`2026-03-01` or `2026-03-01 09:30`).

**Paragraphs** are separated by blank lines.

Example:

```
# Spring price list

Issued by: Supply desk

## Item P-100

Item class: Bracket
Quantity: 4 box
Unit price: 12 EUR/box
Line total: 48 EUR
Supplier reference: SR-KX
```

This gives two units: `u00-spring-price-list` and `u01-item-p-100`.

## 3. Conventions

The **conventions** are the rules the document is reviewed against. Every file in `conventions/` is read as rules.

```
# Price list conventions

These rules govern the spring price list.

## CONV-P01 Line total [required] [conformance] [scope: item class]

The line total must equal the quantity times the unit price.
```

- **The operator's own id.** A **rule heading** carries it: the first token of the form `CONV-` plus letters and digits (hyphen-joined groups allowed), in any case, followed by a space. The answer key names rules by this id, so make each one unique.
- **The rule text.** The text under a heading is the rule.
  - Each paragraph is a separate rule, and so is each list item. All of them share the heading's declarations.
  - Write exactly one paragraph per heading.
  - A rule text shorter than 16 characters is dropped.
- **Before the first rule heading**, paragraphs are ignored, so a title and an introduction are fine. List items there do become rules, so use no lists there.
- **After the first rule heading**, give every heading an id. Text under a heading without an id becomes a rule with no id.
- **The registry id.** Shimmer also numbers every rule `CONV-001`, `CONV-002`, ... in reading order, with files taken in name order. Findings carry both ids; the key uses the operator's own.
- **Severity**: `[required]`, `[recommended]` or `[advisory]`.
  - The last one written wins. No severity means required.
  - Findings under a required or recommended rule produce an **amendment**, a proposed change to the document.
  - Findings under an advisory rule are reported without one.
- **Subject tags** are any other bracket without a colon, such as `[conformance]`. A tag routes the rule to a reviewer:

  | Tag | Who reads the rule |
  |---|---|
  | `conformance` | the rule-checking reviewer |
  | `wording` | the wording reviewer |
  | `editorial` | the editorial board only |
  | `redaction` | the privacy layer |
  | no tag | the rule-checking reviewer |

  A rule whose tags reach neither the rule-checking reviewer nor the wording reviewer gets no judging call. Its computed findings survive only if another rule governs the same unit. Tag checkable rules `[conformance]`, or leave them untagged.

## 4. Machine directives

A **directive** is a bracket on a rule heading whose first word ends in a colon. Inside it:

- Labels are written as the document writes them and are normalised the same way.
- Entries are separated by commas.

| Directive | What it does |
|---|---|
| `[scope: label, label=value]` | Names the units the rule governs. A unit is **in scope** when it carries every listed label. For a pinned entry (`label=value`), it must also have a label line whose whole value equals `value`, ignoring case and spacing. Pinned values are read from label lines only and cannot contain a comma. A scoped rule pairs on its scope alone: the labels its text mentions are not requirements. |
| `[requires: label, label]` | Lists fields every unit in scope must carry, as a label line or a table header. A missing one becomes a `missing_field` finding that Python decides with no model call (**computed absence**). Read only together with `[scope: ...]`. |
| `[unless: label]` | Suspends the rule on any unit that carries that label. |
| `[unless: CONV-X]` | Names another rule that qualifies this one. Python never suspends on it; the two rules go to the reviewer together. A name that matches no rule is read as a label if the unit carries it. Otherwise it is ignored. |

More about directives:

- **Judged absence.** A scoped rule without `[requires: ...]` becomes one narrow model question per unit in scope. The exception is a unit Python has already settled with a band or date computation.
- **Unknown directives stop the run.** Any other bracket of the form `[word: ...]` raises an error.
- Severity and subject tags are not directives.

**Pairing without a scope.** A rule **pairs** with a unit only when the unit carries every label the rule's text names.

- A label counts as named when all its normalised words appear in the rule text.
- When a shorter label is contained in a longer named label, only the longer one counts.
- A rule whose text names no label that any unit uses pairs with nothing.

## 5. The rule for applying directives

There is one rule, the same for every test. Apply it from each rule's own text, never from the planted flaws.

1. **Scope.** A rule that governs only some units declares them with `[scope: ...]`. It names labels, pinned to values where needed, that exactly those units carry.
2. **Completeness.** A rule whose text says fields must be present declares every such field in `[requires: ...]`, using the document's own label.
   - It also declares `[scope: ...]`, because requirements are checked only on units in scope.
   - A field required once per document is required of the one unit meant to hold it. For example, scope on a label that only the preamble carries.
3. **Everything else.** A rule that governs every unit and requires nothing declares neither directive.
4. **Coverage.** Every unit except the preamble is in scope of, or pairs with, at least one rule.

**Why.**

- Without a scope, pairing follows the rule's wording. A unit missing a named field never pairs, so a completeness rule without `[requires: ...]` cannot see the very unit that breaks it.
- A rule worded with labels that other units also carry spreads to those units.
- A unit that no rule pairs with receives a "no rule applies" `missing_field` finding against the closest rule. On a clean unit, that is a false positive.
- Declaring scope and requirements from the rule's own text makes what is checked a property of the rule, not of how one test happens to be worded. A catch therefore never depends on a directive written for one test.

## 6. The manifest, the mandate, and the earlier version

`context/_review_targets.json` says which file plays which role. Name every file in `context/`: any file it does not name is assigned by a repository-wide date cutoff.

```json
{
  "targets": ["offer_2026_06.md"],
  "grounding": ["fee_reference.md", "offer_2026_05.md"],
  "prior": ["offer_2026_05.md"],
  "source": "operator",
  "resolved_at": ""
}
```

- `targets`: the document under review. Use one.
- `grounding`: the reference corpus, including any earlier version.
- `prior`: the **earlier version** of the target, which is compared with it. A file listed in both `targets` and `prior` is reviewed, not compared.

**Negotiation-style tests.**

- The documents are successive versions of an offer. The latest is the target; the one before it is the prior.
- The conventions file is the **mandate**: the reviewing side's own rules, one per term.
- Each mandate rule names its term with the label the offers use, then does one of two things:
  - it states the band that side wants, with two figures in the same measure ("The annual fee must lie between 2% and 4%."); or
  - it requires the term to be stated, in which case section 5 applies.
- Keep the same headings across versions.

**What Python compares.** For every figure whose normalised label appears in both versions, Python writes one record:

| Relation | When |
|---|---|
| `unchanged_from_prior` | the figure is the same |
| `moved_toward`, `moved_away` | the figure differs, and exactly one band, from a rule naming the field, orients the change |
| `changed_from_prior` | the figure differs, with no single band to orient it |
| `absent_since_prior` | the earlier version stated it under a heading the target still has, and no unit states it now |

These records are information (verdict ok), never amendments. Edge cases:

- A label stated earlier with different figures in two places is matched by its heading slug. If that does not settle it, the comparison is refused.
- A label that vanished, with a new label in the same section whose figure is within 2% in the same measure, is refused as a possible rename.
- A term that is new in the later version gets no record.
- A band breach in the target is still a finding.

## 7. The reference corpus

The **reference corpus** is every grounding file. Each paragraph becomes one passage with a **REF id**. A finding cites the passage its evidence came from.

Write bands as tables:

```
| Item class | Price band (EUR/box) |
|---|---|
| Bracket | 8 to 15 |
| Hinge | 3 to 6 |
```

- **Ranges.** A **range** cell holds exactly two figures, low first, separated by a few non-numeric characters (`8 to 15`). A column whose every non-empty cell is a range is a range column.
- **Measure.** The measure comes from a short token in the header bracket, or from the cell. It must match the document's figure.
- **Key column.** A **key column** is a text column whose cells are all different. If the rule names a key column's header words, that column is used.
- **Row matching.** A unit matches a row when every word of the row's key cell appears among the unit's label-line values (`Item class: Bracket`). The most specific row wins; a tie is refused.
- **Naming.** The rule must name the range column's header words ("price band"). Name the key column's header words too, to choose it.
- **What is compared.** Every figure in the unit with the band's measure is compared with the band. So is every ratio of two figures whose measures divide to it. In such units, keep one figure per measure.
- **Size.** Put each table in its own paragraph, under about 900 characters; longer tables lose rows. Prose passages keep only their first 200 characters.

**Other ways to state a bound.**

- **A rule may state its own band**: two figures with the same measure in its text. The band applies to the fields the rule names, or to every figure with that measure if it names none. Never write two figures with the same measure in a rule unless they are its band.
- **A date window** needs two things:
  - a reference sentence with exactly one figure in `hours` or `days`, whose other words all appear in the rule ("The standard reply window is 48 hours."); and
  - a unit with two ISO dates whose labels the rule names.

**Two further behaviours.**

- If a figure falls below a reference-table band, and the rule also names another field the unit carries, the low side is sent to the model as conditional. It is not stated as a firm finding.
- An earlier version's tables are read as reference tables too.

## 8. Per-test settings

A **per-test setting** changes how one test runs and nothing else. If one exists, it applies to that test only and is part of the sealed bundle.

Today Shimmer reads no settings file from a bundle. Everything a test controls is in the files described above.

The following values are repository-wide. They apply to every test, are not per-test settings, and a test must not depend on changing them:

- the date cutoff (avoid it by naming every file in the manifest);
- the withheld audit agents;
- the 2% rename tolerance;
- the run's review mode.

Changing one of these for one test is a code change.

## 9. The answer key

`answer_key.json` is read only by the scorer, never by Shimmer. It must exist before any run.

**Single-version test:**

```json
{
  "document": "price_list_k7.md",
  "task_given_to_the_pipeline": "Review the price list against the conventions.",
  "twin_of": "bundle_m2",
  "planted": [
    {"unit": "u02-item-p-101", "rule": "CONV-P01", "relation": "product_mismatch",
     "kind": "arithmetic",
     "claim": {"relation": "product_mismatch", "field_label": "line total",
               "value_a": 48, "value_b": 52}}
  ],
  "clean": ["u01-item-p-100"]
}
```

| Field | Meaning |
|---|---|
| `document` | The file name of the document under review. |
| `task_given_to_the_pipeline` | One line describing the task. It is only displayed. |
| `twin_of` | The folder name of the twin bundle (section 10). |
| `planted` | One entry per **planted flaw**. |
| `clean` | The unit ids of **clean distractors**: units that look like flaws but are correct. |

**A planted entry** has these fields:

- `unit` (where): matched as a case-insensitive substring of the finding's unit id. Use the full unit id.
- `rule`: the operator's own id of the rule that is broken.
- `relation` (optional): when given, a finding must carry it to locate the flaw.
- `kind`: your own category label. Recall is reported per kind.
- `claim`: the **typed reason**, with four parts:
  - `relation`;
  - `field_label`, in normalised form, with words joined by single spaces;
  - `value_a` and `value_b`, the conflicting figures as numbers (order does not matter).

A flaw counts as detected only when a finding on that unit states the same relation, the same field label and both figures.

**What each relation's figures mean:**

| Relation | Planted by | `value_a` | `value_b` | `field_label` |
|---|---|---|---|---|
| `sum_mismatch` | A table column whose figures do not add up to a figure whose label holds the column label's words and more (`Sum of line totals: 80 EUR` under a `Line total (EUR)` column). | the computed sum | the stated total | the total's label |
| `product_mismatch` | Two figures whose measures multiply to a third figure's measure (`4 box` times `12 EUR/box` against `52 EUR`). | the computed product | the stated figure | the stated figure's label |
| `above_band`, `below_band` | A figure outside a band. | the figure | the bound crossed | The figure's label. A table cell adds ` row` and its row number (`line total row2`). None for a ratio. |
| `missing_field` | A required field that is absent, or blank cells in a column of figures. | 0, or the number of cells filled | 1, or the number of rows | the field's label |
| `date_window` | Two dates further apart than the bound. | the gap | the bound | the first date's label |

**Negotiation-style test.** Instead of `planted` and `clean`, give `task` (one line, displayed only) and two lists:

- `prior_records`: one row for every label that both versions state, unchanged ones included. Any record not listed is a false positive. Each row has:
  - `field_label`, written as in the document;
  - `relation`;
  - `value_a`, the figure now (`null` for `absent_since_prior`);
  - `value_b`, the earlier figure;
  - `unit`, the measure.
- `band_irregularities`: one row per band breach, with `field_label`, `relation` (`above_band` or `below_band`), `value_a`, and `rule` (the operator's own id).

## 10. The clean twin

The **clean twin** is a second bundle identical to the first, except that every planted flaw is repaired.

- Keep headings, labels, conventions, reference corpus and manifest roles the same, so the unit ids line up.
- Give the twin's document a different neutral file name, because the scorer finds a twin's run by that name. Update the manifest to match.
- The twin's key has `"planted": []`, its own `document`, and a `twin_of` naming the first bundle. The first bundle's key names the twin.

A claim worded identically in both twins' runs did not come from the document.

## 11. Perturbation probes

A **perturbation probe** is a copy of a bundle with one controlled change, shipped as its own bundle with its own key. No code reads a probe declaration: this is a convention of this format. Record which probe it is in a top-level `probe` field of the key, which the scorer ignores.

1. **Reworded labels.** Rewrite a label in other words with the same meaning, everywhere it appears. Leave rules and directives unchanged. Update `field_label` in the key.
2. **Reordered sections.** Move sections. Unit ids carry position, so update every moved unit's id in the key. Keep any flaw that depends on a neighbouring unit next to that neighbour.
3. **A term only in the later version.** A later version states a field the earlier one does not; declare the earlier one as `prior`. The key lists no record for that term. A single-version test meets this probe by adding a later version.
4. **A value in a different format.** Write a figure differently with the same reading: `1250`, `1,250`, `1 250` or `1250.00`. The key is unchanged. Changing the measure token (`€` for `EUR`) is a different measure, not a different format.

## 12. How a multi-round case is declared

This section is completed after the multi-round case manifest is final (loop stage S2).

## 13. Glossary

- **Amendment**: a proposed change to the document, made from a finding under a required or recommended rule.
- **Answer key**: `answer_key.json`; it states the planted flaws and is read only by the scorer.
- **Band**: an allowed range for a figure, from a rule's text or a reference table.
- **Clean distractor**: a correct unit that looks like a flaw.
- **Clean twin**: the same bundle with every flaw repaired.
- **Computed absence**: a missing required field, decided by Python.
- **Conventions**: the rules in `conventions/`.
- **Directive**: a heading bracket whose first word ends in a colon: `scope`, `requires` or `unless`.
- **Document under review (target)**: the file named in `targets`.
- **Earlier version (prior)**: the file named in `prior`, compared with the target.
- **Field**: a label and its value, from a label line or a table header.
- **Finding**: a typed record stating a unit, a rule, a relation and figures.
- **Grounding**: any file in `context/` that is not under review.
- **Judged absence**: one model question about one unit and one scoped rule.
- **Key column**: a table column whose distinct cells identify rows.
- **Label line**: a line of the form `Label: value`.
- **Manifest**: `_review_targets.json`, which assigns file roles.
- **Mandate**: the conventions file of a negotiation-style test.
- **Measure**: a figure's unit of measurement, such as `EUR`, `box` or `%`.
- **Neutral naming**: names that reveal nothing about flaws or answers.
- **Normalised label**: a label reduced to its comparable words (section 2).
- **Operator's own id**: the `CONV-...` id written on a rule heading.
- **Pairing**: deciding that a rule applies to a unit.
- **Per-test setting**: a value that changes one test only (none is read today).
- **Perturbation probe**: a bundle copy with one controlled change.
- **Planted flaw**: a deliberate error recorded in the key.
- **Preamble unit**: the text before the first unit heading, id `u00-...`.
- **Range**: two figures in one cell, low first.
- **REF id**: the id of one reference passage, which is one paragraph.
- **Reference corpus**: the grounding files that bands and citations come from.
- **Registry id**: Shimmer's sequential `CONV-001`-style id for a rule.
- **Relation**: the kind of disagreement a finding records.
- **Scope**: the units a rule governs.
- **Sealed**: unchangeable once any result on the bundle has been seen.
- **Severity**: required, recommended or advisory.
- **Slug**: the lowercased, hyphenated form of a heading.
- **Subject tag**: a bracket word that routes a rule to a reviewer.
- **Test bundle**: the folder holding one complete test.
- **Typed reason (claim)**: the relation, field label and figures of a planted flaw.
- **Unit**: the piece of a document that a rule is applied to.
- **Unit id**: `u`, a two-digit position, a hyphen, and the heading's slug.
