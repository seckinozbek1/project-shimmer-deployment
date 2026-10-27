# Shimmer input format

Version: `input-format-v1-draft`

This document tells you how to prepare a test for Shimmer. Every rule here describes what the code does today. All examples are invented. It is a draft: it is frozen as `input-format-v1` before any sealed test (section 1) is written, and after the freeze it never changes (a change would be a new version).

## 1. What a test bundle is

**Words used throughout.**

- **Shimmer**: the program under test. It reads a document and a set of rules and reports where the document breaks them.
- **Operator**: the person who runs Shimmer and writes its rules. When you prepare a test, you write as the operator.
- **Python** and **the model**: Shimmer has two kinds of worker. Python is fixed code: it reads figures, computes sums, products and comparisons, and gives the same answer every time. The model is a language model: it is asked questions in words, and its answers can vary.
- **Finding**: one record Shimmer writes about one piece of the document under one rule. It names a **relation** (the kind of problem, such as `product_mismatch`) and, where it can, the field and the two figures involved. Every finding has a **verdict**: `irregular` (a problem) or `ok` (information only).
- **Amendment**: a proposed change to the document. Shimmer builds one from an irregular finding (section 3 says when).
- **Run**: one execution of Shimmer on one bundle. A **result** is anything a run writes.
- **Scorer**: the program that compares a run's findings and amendments with your answer key.
- **Recall**: how many of your planted flaws the scorer finds in a run, out of all of them.
- **False positive**: an amendment on a part of the document where you planted no flaw (section 9 gives the exact count).
- **Band**: an allowed range for a figure, such as 8 to 15 (section 7).
- **Twin**: a second bundle identical to the first, with every flaw repaired (section 10).

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

- **Where bundles live.** One folder per bundle, and a bundle and its twin (section 10) side by side in the same parent folder. The scorer in this repository (`tools/score_corpus.py`) reads keys only from `benchmark/corpora/<bundle>/` and finds a twin by its folder name there, so a bundle is scored with it only when it sits there.
- Only files directly inside `context/` and `conventions/` reach Shimmer. Subfolders are ignored.
- `answer_key.json` stays at the top of the bundle. Never put it, or any answer, in `context/`: a `.json` file there is read as a document.
- **File types.** Documents, reference files and conventions are Markdown files (`.md`). The manifest and the answer key are JSON files (`.json`). Nothing else.
- **Encoding.** UTF-8 without a byte-order mark. A byte-order mark hides the heading on the first line: in a conventions file, the first rule is then lost without any warning. Use LF line endings; CRLF is read the same way.
- **Underscores.** In `context/`, a file whose name starts with `_` is never read as a document (the manifest relies on this). In `conventions/`, every file is read as rules, whatever its name. Put no notes there.
- **Neutral naming.**
  - File and folder names use only ASCII letters, digits, `_` and `-`, with no spaces.
  - Headings, labels and values (section 2) may contain spaces. Keep them ASCII (section 2 says why).
  - No file name, folder name, heading, label or value hints at the flaws, the answers, or which twin is clean. Write `price_list_k7.md`, never `price_list_flawed.md`. Write `## Item P-101`, never `## Item P-101 (wrong total)`.

## 2. Documents and units

Shimmer splits each document into **units**, the pieces a rule is applied to.

**Headings.** A heading is a line that starts with 1 to 6 `#` characters followed by a space. Shimmer does not recognise code blocks: a heading inside one still counts. Use no code blocks in documents.

- **The title.** A level-1 heading (`# Title`) before the first unit heading is the title. It does not start a unit. Write exactly one, as the first line.
- **Units.** Every heading of level 2 to 6 starts a unit, which runs to the next such heading. A `###` heading inside a `##` section starts its own unit, so use one heading level for entries.
- A level-1 heading after the first unit heading starts nothing: it becomes text of the unit above it. Do not write one.
- **The unit id** is built in three parts:
  - the letter `u`;
  - the heading's position among the level-2-to-6 headings, as two digits from `01`;
  - a hyphen, then the heading's **slug**.
- **The slug**: lowercase the heading; replace every run of characters other than `a-z` and `0-9` with one `-`; remove any `-` at either end; then keep the first 40 characters (so a cut can leave a `-` at the end). A heading with no `a-z` or `0-9` at all gets the slug `unit`. Letters outside ASCII are replaced, so keep headings ASCII.

  So `## Item P-101` as the second heading has the id `u02-item-p-101`, and `## Item (A)` as the first has the id `u01-item-a`. Keep headings distinct.
- **The preamble unit.** The text before the first unit heading becomes the unit `u00-<slug of the title>`, or `u00-preamble` when there is no title. This happens only when that text holds at least one line that is neither a heading nor a rule line (a line of only `-`, `*`, `_`, `=` and spaces). It never shifts the other ids.
- **A document with no unit headings** is split by its tables. A table here is a run of lines that each start and end with `|`.
  - Exactly one table of three or more lines: one unit per line after the second (`u01-row`, `u02-row`, ...).
  - Otherwise, one unit per table (`u01-table`, ...).
  - No table at all: the whole document is one unit (`u01-document`).

  In the first two cases, text outside the tables is in no unit. Prefer headings.

**Fields.** A unit's fields come from two places only.

1. **A label line**: `Label: value` on one line.
   - It may be indented, and may start with one `-`, `*` or `+` and a space. A numbered line (`1. Label: value`) is not a label line.
   - The label starts with a letter. It is 2 to 49 characters of letters, digits, spaces and `( ) / % . _ -`. It cannot contain a comma, a colon or any other character.
   - The label ends at the first colon. The value is the rest of the line.
   - A line with nothing after the colon is not a field: that field counts as absent.
   - Any line of this shape is a field, wherever it sits. The sentence `Note: the price changed.` is a field labelled `Note`. Avoid colons in prose.
   - State each label once per unit. If a label repeats, scope values (section 4) are read from its first line and figures from its last.
2. **A table**: a header row, a separator row (`|---|---|`), then at least one body row.
   - Each header cell is a field label of the unit.
   - A **measure** in brackets at the end of a header, as in `Line total (EUR)`, is the column's unit of measurement. It is not part of the label.
   - Put each table in its own paragraph, with a blank line before and after it. Never put `|` inside a cell.

**Normalised labels.** Labels are compared after **normalisation**:

1. Lowercase the label.
2. Split it into words at every character that is not a letter or a digit. `_` splits too. A `-` between two letters or digits does not split: `Class-A` stays one word, `class-a`.
3. Drop every word of two characters or fewer.
4. Drop every **stop word**. This is the complete list: a, above, all, also, an, and, another, any, are, as, at, be, been, being, below, between, both, but, by, can, could, did, do, does, down, each, for, from, had, has, have, her, his, how, if, in, into, is, it, its, least, less, may, might, more, most, must, no, not, of, on, only, onto, or, other, our, out, over, per, same, shall, should, such, than, that, the, their, then, these, this, those, to, under, up, was, were, what, when, where, which, who, whom, whose, why, will, with, without, would, your.
5. Fold one plural. A word longer than four letters that ends in `ies` ends in `y` instead (`series` becomes `sery`). Otherwise, a word longer than three letters that ends in `s` loses it, unless it ends in `ss`, `us` or `is`. Steps 3 and 4 run first, so `others` survives as `other`.
6. Keep the remaining words in their order.

So `Line totals` and `line total` both give `line total`. `Item ID` gives `item`. `Days for reply` gives `day reply`. Words in brackets in a label line stay in the label: `Line total (EUR): 65` gives `line total eur`.

The normalised words, joined by single spaces, are what the answer key's `field_label` holds (section 9).

**Figures.** Python reads one **figure** from a field: a number, with an optional measure.

- In a label line, the figure is the first number in the value. In a table, it is the first number in each body cell.
- **Reading a number.**
  - A `-` directly before the digits makes the number negative.
  - **Grouped form**: one to three digits, then one or more groups of one comma or one space followed by exactly three digits, then optionally a point or a comma and more digits. The commas and spaces are removed. So `1,250` is 1250, `12,500` is 12500, `1 250` is 1250, `1,250.75` is 1250.75, and `1 250,5` is 1250.5.
  - **Plain form**: digits, optionally followed by one point or one comma and more digits. A single comma with no point is a decimal mark: `12,5` is 12.5 and `1234,567` is 1234.567.
  - A point is never a thousands mark: `1.250,50` reads as 1.25.
  - Two numbers separated only by one space or one comma, the second of exactly three digits, read as one number: `3 400` is 3400. Never write that.
- **How to write figures.** Plain digits with a point for decimals (`5.5`, `1250.00`), or comma groups of three (`1,250`).
- **Every number counts, including numbers inside dates and identifiers.**
  - `2026-03-01` gives the figure 2026, with no measure.
  - `SR-101` gives -101 (the `-` is read as a minus sign). `A-201` gives -201.
  - `09:30` gives 9.

  A figure with no measure takes part in products and ratios (section 7, "Figure audit"). So never write a digit in a value that is not meant as a figure. Write identifiers with letters only (`SR-KX`). Write a date only where a date-window rule needs it (section 7). Headings are not values: `## Item P-101` is safe.
- **The measure** is read in this order:
  1. A currency symbol directly before the number, with at most one space between (`$12`, `$ 12`): the measure is the symbol.
  2. Otherwise, two to four capital letters A-Z not joined to a letter before them, then one or more spaces, then the number (`EUR 12`): the measure is that code.
  3. Otherwise, the token right after the number, with or without spaces between. It starts with a letter or `%`, continues with letters, digits and `/ % ^ -`, and may end with `/` and one more word (`4 box`, `12 EUR/box`, `12 EUR / box`, `45%`).

  A word of two to four capital letters before a number is always taken as its measure: `VAT 20%` has the measure `VAT`, not `%`.

  `12 EUR per box` has the measure `EUR`: `per` is not division. Write `12 EUR/box`.

  If a one-word measure is followed by the same one or two words after two or more figures in the document, the measure becomes the whole phrase: `5 box per pallet` written twice gives the measure `box per pallet`. Write nothing after the measure in a value.
- **When measures agree.** A measure is split at each `/`. In each part, only letters, `%` and currency symbols count: digits and other characters are dropped, and case is kept. A part after a `/` is a divisor. Two measures agree only when they have exactly the same parts with the same powers.
  - `EUR 12` and `12 EUR` agree. `12 EUR/box` and `12 EUR / box` agree.
  - `EUR` and `eur` do not. `box` and `boxes` do not. `$12` and `12 USD` do not.
  - `m2` and `m` agree, because the digit is dropped. Never put digits in a measure.
- **Multiplying and dividing measures.** Multiplying adds powers and dividing subtracts them: `box` times `EUR/box` is `EUR`, and `EUR` divided by `box` is `EUR/box`. A figure with no measure leaves the other measure unchanged: 4 times `12 EUR` is in `EUR`, and `12 EUR/box` divided by 2026 is in `EUR/box`.
- In a label line, write the measure after the figure, never in brackets in the label.

**Paragraphs** are separated by blank lines. A line holding only spaces counts as blank.

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

This gives two units: `u00-spring-price-list` and `u01-item-p-100`. The figures of `u01-item-p-100` are 4 `box`, 12 `EUR/box` and 48 `EUR`. `Item class` and `Supplier reference` are text fields.

## 3. Conventions

The **conventions** are the rules the document is reviewed against. Every file in `conventions/` is read as rules, in file-name order.

```
# Price list conventions

These rules govern the spring price list.

## CONV-P01 Line arithmetic [required] [conformance]

The line total must equal the quantity times the unit price.

## CONV-P02 Price band [required] [conformance]

The unit price must lie within the price band for the item class.

## CONV-P03 Supplier reference [required] [conformance] [scope: item class] [requires: supplier reference]

Every item entry must state a supplier reference.
```

- **The operator's own id.** A **rule heading** is a heading (any level from 1 to 6) that carries this id. The id is the first match in the heading, in any case, of `CONV-` followed by letters and digits, optionally followed by more groups of `-` and letters and digits.
  - Write the id first, then a space or the end of the line. `## CONV-P01` alone is a valid rule heading. `## CONV-P01-Line total` gives the id `CONV-P01-LINE`.
  - The answer key names rules by this id. Make each one unique.
- **The rule text.** The text under a heading is the rule. The heading's own words are not part of the rule text.
  - A paragraph is a run of non-blank lines. Its lines are joined with spaces.
  - Each paragraph is a separate rule, and so is each list item. A list item is a line that starts with `-`, `*` or `+` and a space, or with digits, then `.` or `)`, and a space. A list line inside a paragraph splits it.
  - Write exactly one paragraph per rule heading, with no line that starts like a list item.
  - A rule text shorter than 16 characters is dropped.
- **Before the first rule heading**, paragraphs are ignored, so a title and an introduction are fine. List items there do become rules, so use no lists there.
- **After the first rule heading**, make every heading a rule heading. Text under a heading without an id becomes a rule with no operator id, which no key can name.
- **Each heading resets** severity, subject tags and directives. They apply to every rule under that heading, up to the next heading.
- **The registry id.** Shimmer also numbers every rule `CONV-001`, `CONV-002`, ... in reading order. A dropped short rule still uses up a number. Findings carry both ids; the key uses the operator's own.

**Brackets on a heading.** Every `[...]` on a heading line is read, in any case.

- **Severity**: `[required]`, `[recommended]` or `[advisory]`. The last one written wins. No severity means required. A finding under a required or recommended rule produces an amendment. A finding under an advisory rule is still reported, but produces no amendment.
- **Directive**: a bracket whose first word is `scope`, `requires` or `unless`, followed by a colon (section 4).
- **Any other bracket of the form `[word: text]`** (a word of letters, `_` or `-`, a colon, then more text) stops the run with an error. This applies to every heading in every conventions file, the title included. It does not apply to rule text, documents or reference files, where brackets are plain text.
- **Subject tag**: any other bracket, such as `[conformance]`.

**Subject tags and reviewers.** A **reviewer** is a model agent that is asked about one rule and one unit at a time. There are two: the **rule-checking reviewer** and the **wording reviewer**. The tags decide which one gets a rule:

| Tag | Who reads the rule |
|---|---|
| `conformance` | the rule-checking reviewer |
| `wording` | the wording reviewer |
| no tag | the rule-checking reviewer |
| `editorial` | only the editorial board, a group of agents that reads rules later in the run, not unit by unit |
| `redaction` | only the privacy layer, which hides sensitive text |
| any other | no one |

- A rule tagged both `conformance` and `wording` goes to the rule-checking reviewer.
- A rule whose tags reach neither reviewer is never put to one. Then:
  - its band, date-window and absence findings (sections 4 and 7) are lost;
  - a sum, product or blank-cell finding attributed to it (section 9) moves to another rule paired (section 4) with the same unit that does reach a reviewer and has no `[unless: ...]`. With no such rule, it is lost too.
- So tag every rule that Python can check `[conformance]`, or leave it untagged. Never invent a tag such as `[arithmetic]` or `[band]`.

A reviewer is asked about a figure only after Python has computed it. The finding carries Python's figures whatever the reviewer says.

## 4. Machine directives

A **directive** is a bracket on a rule heading whose first word is `scope`, `requires` or `unless`, followed by a colon. Inside it:

- Entries are separated by commas.
- Labels are normalised exactly as document labels are (section 2), so case does not matter. Use the document's own words. A label that normalises to nothing (such as `ID`) is ignored.

| Directive | What it does |
|---|---|
| `[scope: label, label=value]` | Names the units the rule governs. A unit is **in scope** when it carries every listed label, as a label line or a table header. For a pinned entry (`label=value`), the unit's first label line with that label must also have a whole value equal to `value`, ignoring case and runs of spaces. Pinned values are read from label lines only and cannot contain a comma. A scoped rule pairs on its scope alone: the labels its text mentions are not requirements. |
| `[requires: label, label]` | Lists fields every unit in scope must carry, as a label line with a value or as a table header. Each one missing becomes a `missing_field` finding that Python decides with no model call (**computed absence**). It works only together with `[scope: ...]`; alone, it does nothing. |
| `[unless: label]` | Suspends the rule on any unit that carries that label, as a label line or a table header. |
| `[unless: CONV-X]` | Names another rule that qualifies this one. Python never suspends on it; the other rule's text goes to the reviewer together with this rule. A name that matches no rule is read as a label if the unit carries it. Otherwise it is ignored. |

**Judged absence.** A scoped rule without `[requires: ...]` puts one narrow question to the model for every unit in scope. The only exception is a unit on which Python already settled that rule with a band or date-window comparison. Section 5 forbids this form.

**Pairing without a scope.** A rule without `[scope: ...]` **pairs** with a unit only when the unit carries every label the rule's text names.

- **The label universe** is every label of the document under review: the label lines and table headers of all its units, the preamble included. Reference files and the earlier version add nothing to it.
- The rule text is normalised the same way as labels. A label counts as named when all its normalised words appear anywhere in the normalised rule text, in any order, not necessarily next to each other. So "the price of each item" names both `price` and `item`, if the document uses those labels. Check every rule against every label for such accidents.
- When all of a shorter named label's words are inside a longer named label, only the longer one counts.
- A rule whose text names no label of the universe pairs with nothing. It also switches off the "no rule applies" finding (section 5) on every unit.

## 5. The rule for applying directives

There is one rule, the same for every test. Apply it from each rule's own text, never from the planted flaws.

1. **Completeness rules.** A rule whose text requires that a field be stated or present declares both:
   - `[requires: ...]`, listing every such field with the document's own label; and
   - `[scope: ...]`, naming labels (pinned to values where needed) that exactly the units meant to hold the field carry.

   A field required once per document is required of the one unit meant to hold it. For example, scope on a label that only the preamble carries.
2. **Every other rule** (arithmetic, bands, date windows, wording) declares no directive. Its text names the labels of the fields it governs, and it pairs with the units that carry them all. A rule is not a completeness rule just because it says "must".
3. **Never** write `[scope: ...]` without `[requires: ...]`.
4. **Every rule names at least one document label, or declares a scope.**
5. **Coverage.** Every unit except the preamble is in scope of, or pairs with, at least one rule. The preamble needs no scope to exclude it: a rule pairs with the preamble only if the preamble carries every label the rule names. Keep the labels your rules name out of the preamble, unless a rule is meant for it.
6. **Scope values must sit in label lines.** If the units in scope differ from the others only by a value, give every unit a label line that states that value, and pin the scope to it. A value that appears only in a table cell cannot be used.

**Why.**

- Without a scope, pairing follows the rule's wording. A unit missing a named field never pairs, so a completeness rule without `[requires: ...]` cannot see the very unit that breaks it.
- A scoped rule without `[requires: ...]` hands each unit in scope to the model, whose answers vary and can be false positives.
- A rule worded with labels that other units also carry spreads to those units.
- A unit that no rule pairs with receives a "no rule applies" `missing_field` finding, under the rule that misses the fewest labels on that unit. It states no field and no figures, so it can never confirm a planted flaw. On a clean unit, it is a false positive. It is never raised on the preamble, and never raised at all while some rule names no document label (rule 4 prevents that case).
- Declaring scope and requirements from the rule's own text makes what is checked a property of the rule, not of how one test happens to be worded. A catch therefore never depends on a directive written for one test.

## 6. The manifest, the mandate, and the earlier version

`context/_review_targets.json` says which file plays which role.

```json
{
  "targets": ["offer_2026_06.md"],
  "grounding": ["fee_reference.md", "offer_2026_05.md"],
  "prior": ["offer_2026_05.md"],
  "source": "operator",
  "resolved_at": ""
}
```

- The file must hold one JSON object. If it is missing or cannot be read, it is ignored and every file falls to the date cutoff (section 8).
- `targets`: the document under review. Use one.
- `grounding`: the reference corpus. Listing the earlier version here too is allowed but not needed.
- `prior`: the **earlier version** of the target, which is compared with it. A prior is always treated as grounding. A file listed in both `targets` and `prior` is reviewed, not compared.
- `source`: write `"operator"`. Never write `"system_draft"`: at the end of such a run Shimmer deletes the target files and the manifest.
- `resolved_at`: not read. Write `""`.
- Name every file in `context/` except the manifest itself. Never list the target in `grounding`. A file the manifest does not name is placed by the date cutoff, and may end up under review.

**Grounding** means every file in `context/` that is not under review.

**Negotiation-style tests.**

- The documents are successive versions of an offer. The latest is the target; the one before it is the prior.
- The conventions file is the **mandate**: the reviewing side's own rules, one per term.
- Each mandate rule names its term with the label the offers use, then does one of two things:
  - it states the band that side wants, with two figures in the same measure ("The annual fee must lie between 2% and 4%."); or
  - it requires the term to be stated, in which case section 5, rule 1 applies.
- Keep the same headings across versions: Python matches the two versions by heading slug.

**What Python compares.** Python writes change records unit by unit, in both review modes (section 8).

- Only label-line figures of the target are compared. Text values (`Item class: Bracket`) and table cells of the target never get a record.
- The earlier figure is found by normalised label anywhere in the earlier version: in a label line, or in a table row whose key cell (section 7) normalises to exactly the label, in a table with exactly one value column.
- If the earlier version states the label with different figures in several places, only the statements under the heading with the same slug are kept. If they still differ, the comparison is refused.
- Both figures must have the same measure, and it must not be empty. Otherwise the comparison is refused: a date, or any other figure with no measure, never gets a change record.
- A record needs a rule to cite: for `absent_since_prior`, any rule whose text names the label, or else a rule paired with that unit; for the others, a rule paired with that unit. A unit with no such rule gets refusals, not records.
- A record also needs the earlier statement's REF id (section 7). A figure past the indexed paragraphs is refused.
- Two figures are the same when they differ by at most 0.000000001, or by at most one millionth of the larger.

| Relation | When | `value_a` | `value_b` |
|---|---|---|---|
| `unchanged_from_prior` | the figure is the same | the figure now | the earlier figure |
| `moved_toward`, `moved_away` | the figure differs, and exactly one band orients the change (below) | the figure now | the earlier figure |
| `changed_from_prior` | the figure differs, with no band to orient it, or with no change in distance to the band | the figure now | the earlier figure |
| `absent_since_prior` | see below | none | the earlier figure |

**Orienting a change.** The bands considered come from the rules paired with the unit whose text names the field: a band the rule states itself, and a reference-table band the unit matches for that rule (section 7). Only bands in the figure's measure count.

- Exactly one distinct range: Python compares each figure's distance to it (0 inside the range, bounds included; otherwise the distance to the nearer bound). Smaller now: `moved_toward`. Larger now: `moved_away`. Equal, for example both inside: `changed_from_prior`. So 5 moving to 7 against a range of 3 to 6 is `moved_away`.
- No range: `changed_from_prior`.
- Two or more distinct ranges: no orientation (the record stays `changed_from_prior` or `unchanged_from_prior`), and a refusal is logged as well.

**`absent_since_prior`** is written only when all of these hold:

- the earlier version states the label with a figure, under a heading whose slug a unit of the target still has;
- no unit of the target carries that label at all, as a label line with any value or as a table header;
- no label that is new in that unit of the target has a figure within 2% of the earlier figure, in the same non-empty measure (that case is refused as a possible rename).

The record sits on the target unit with that slug. A label with a text value never gets one. A figure with no measure (from an identifier such as `SR-101`) can still get one. A label stated earlier under a heading the target no longer has is refused as an **orphan**.

These records have the verdict `ok`: they are information, never amendments. A term that is new in the later version gets no record. A band breach in the target is still an irregular finding.

## 7. The reference corpus

The **reference corpus** is every grounding file, the earlier version included. Each paragraph becomes one passage with a **REF id**. Only the first 120 paragraphs of each grounding file get one: keep every grounding file, the earlier version included, under 120 paragraphs. A finding cites the passage its evidence came from.

**Stored size.** Python reads the stored form of each passage:

- A table passage keeps its header and separator, then whole rows while the passage stays within 900 characters (each line counts its length plus one). Later rows are lost.
- Any other passage keeps only its first 200 characters.

**Bands in tables.** A **band** is an allowed range for a figure. Write bands as tables:

```
| Item class | Price band (EUR/box) |
|---|---|
| Bracket | 8 to 15 |
| Hinge | 3 to 6 |
```

- **Table.** A header row, a separator row, at least one body row, alone in its paragraph.
- **Column kinds.** A column whose every non-empty cell is a range is a **range column**. A column whose every non-empty cell holds exactly one number is a **value column**. Every other column is a **text column**.
- **Range.** A cell holding exactly two numbers, low first (equal is allowed), with at most 12 characters between them and no digit among those characters. `8 to 15`, `8-15` and `8 - 15` all work.
- **Measure.** The column's measure comes from the bracket at the end of its header. Write it compactly: 1 to 16 characters, starting with an ASCII letter or `%`, holding only ASCII letters, digits, `/`, `%`, `-` and `*` (`(EUR/box)`).
  - A currency symbol or a letter outside ASCII in that bracket is not read. Use letter codes (`EUR`, `USD`) for measures in reference tables.
  - A bracket in words (`(EUR per box)`, at most 32 characters, two to four words) works only when its first and last words are measures the document under review writes, and they combine, in exactly one order, into a measure the document also writes. Avoid it.
  - With no header measure, the measure after the second number counts (`8 to 15 EUR/box`). A range with no measure is ignored.
  - The band's measure must agree with the document's figure (section 2).
- **Unit column.** A text column whose every cell is a measure the document under review writes gives the measure of its row.
- **Key column.** A text column with at least two non-empty cells, all different. If the rule's text names every word of some key column's header, only those named key columns are used. Otherwise every key column is used.
- **Row matching.** Normalise every key cell of a row (section 2). A unit matches the row when all those words appear among the normalised words of the values of all the unit's label lines.
  - A row whose key cells normalise to nothing (such as `A` or `B2`) never matches.
  - The row with the most words wins. A tie between rows is refused: there is no band.
  - Key-cell words must not occur in the unit's other values. A key cell `Box` would match every unit whose quantity is in `box`.
- **Naming.** The rule must name every word of the range column's header, without its measure ("price band"). Naming the key column's header words too makes the choice of key column explicit.

**Which figures are compared with a band.**

- Every figure in the unit with the band's measure: every label-line figure and every table cell.
- Every ratio of two label-line figures whose measures divide to the band's measure. A figure with no measure divides into anything without changing its measure, so a date or a digit-bearing identifier creates ratios (`12 EUR/box` divided by 2026 is compared with a band in `EUR/box`).
- A figure is inside when it is at least the low bound and at most the high bound. There is no tolerance. Above the high bound: `above_band`. Below the low bound: `below_band`. Inside gives no finding.

**The low side.** A `below_band` from a reference table is **firm** when every document label the rule's text names is either a label being compared (the figure's own label, or the two labels of a ratio) or the header label of a key column used for the row. Otherwise, if the unit carries one of the remaining named labels, the finding is **conditional**: it is still recorded with its figures, and the scorer can still detect it, but it never becomes an amendment.

Example: "The unit price must lie within the price band for the item class", with the key header `Item class`, gives a firm `below_band` on `unit price`. The ratio of line total to quantity is conditional, because the rule also names `unit price`, which that ratio does not use.

**Other ways to state a bound.**

- **A rule may state its own band**: two or more figures with the same measure in its text. The lowest and the highest are the bounds. The band applies to the fields the rule names that the unit holds as figures; if the unit holds none of them as figures, it applies to every figure with that measure. Ratios of every pair of label-line figures are compared as for a table band. Never write two figures with the same measure in a rule unless they are its band.
- **A labelled sentence** in a grounding file, of the shape `Label: words 8 to 15 EUR/box.` (label at most 48 characters, exactly two numbers after the colon, a measure the document writes), is read as one row of a band table. The label is the key cell and the words before the first number are the column header the rule must name. Do not write this shape anywhere in grounding files, the earlier version included, unless you mean a band.
- **A date window** needs all of these:
  - a unit with two dates the rule names: either two label lines each holding exactly one ISO date (`2026-03-01` or `2026-03-01 09:30`), or one label line holding exactly two. The rule must name each line's label. If the rule names both shapes, or three or more such lines, there is no window;
  - a **bound sentence**: a sentence with exactly one number, measured in `hours` or `days` (written exactly so), whose other words, normalised, all appear in the rule: "The standard reply window is 48 hours." It may sit in a grounding file, within the first 200 characters of its paragraph, or in the document under review;
  - among all sentences with exactly one measured number whose other words the rule all uses, in the grounding files and in the document, the bound sentence must have the most words. A tie means no window. Write no other such sentence.

  The gap between the two dates, ignoring direction and measured in the bound's measure, is compared with the bound. A larger gap is a `date_window` finding. Give the first date's label exactly one word after normalisation (for example `Logged:`): a label of two or more words comes out in an unpredictable word order in the finding. Dates are figures too (section 2), so keep other figures out of a date-window unit.

**Two further behaviours.**

- An earlier version's tables are read as reference tables too.
- The tables of the document under review are never read as reference tables.

**Figure audit.** Before sealing a bundle, list for every unit:

1. Every figure, with its measure. Remove every figure with no measure that is not meant as a figure (dates, identifiers, times).
2. Every **product**: any two label-line figures whose measures multiply to a third label-line figure's measure are compared with it. This happens on every unit that pairs with at least one rule, whatever the rules say. A figure with no measure multiplies with everything: `Quantity: 4` with `Unit price: 12 EUR` and `Line total: 48 EUR` gives the false comparison 4 times 48 against 12.
3. Every **sum** (section 9).
4. Every band that applies, and every figure and ratio it is compared with.
5. Every blank cell in a column of figures.

Every planted flaw must produce exactly the comparison you intend, and every other unit must produce none that disagrees. In particular, never put a band and a column total in the same measure in one unit: the total is compared with the band too.

## 8. Per-test settings

A **per-test setting** changes how one test runs and nothing else. If one exists, it applies to that test only and is part of the sealed bundle.

Today Shimmer reads no settings file from a bundle. Everything a test controls is in the files described above.

The following values are repository-wide. They apply to every test, are not per-test settings, and a test must not depend on changing them:

- **The date cutoff** (`cutoff_date` in `config/review_scope.json`): a file the manifest does not name is put under review when its date is on or after the cutoff. Avoid it by naming every file in the manifest.
- **The withheld audit agents** (`withheld_audit_agents` in the same file): agents the run does not call.
- **The 2% rename tolerance** (`config/rename_tolerance.json`, section 6).
- **The review mode**: `paired` (one unit and one rule at a time, with Python's arithmetic; the default for local runs) or `wide` (the model sees the whole document at once; the default for cloud runs). Sections 4, 5 and 7 describe the paired mode. In the wide mode, Python computes only the change records of section 6.
- **The pair cap** (`--pairs-per-unit`, off unless the run sets it): when set, rules past the cap on a unit are not reviewed.

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
| `document` | The file name of the document under review. The scorer finds a twin's run by this name without its extension, so the twins' names must differ. |
| `task_given_to_the_pipeline` | One line describing the task. The scorer prints it. Shimmer never sees it. |
| `twin_of` | The folder name of the twin bundle (section 10). |
| `planted` | One entry per **planted flaw**. |
| `clean` | The unit ids of **clean distractors**: units built to look like flaws that are correct. |

**A planted entry** has these fields:

- `unit`: the full unit id. It is matched as a case-insensitive substring of a finding's unit id.
- `rule`: the operator's own id of the rule the finding will be attributed to (below).
- `relation`: always write it, equal to `claim.relation`. A finding must carry it to locate the flaw.
- `kind`: your own category label. Recall is reported per kind.
- `claim`: the **typed reason**, with four parts:
  - `relation`;
  - `field_label`, the normalised label exactly as section 2 and the table below produce it;
  - `value_a` and `value_b`, the two figures as numbers, as the table below defines them.

**How the scorer counts a single-version test.**

- **Located**: a finding whose unit id contains `unit` and whose relation equals `relation`; or an amendment on that unit under the rule `rule`.
- **Detected** (reason confirmed, the figure that counts): among the located findings, one whose relation equals `claim.relation`, whose `field_label` is exactly the same text as `claim.field_label`, and whose two figures include both claim figures. A finding with no field label passes the label test. Figures are rounded to 6 decimal places and must then be equal; their order does not matter.
- **Attribution**: whether the amendment for a located flaw carries the rule `rule`. The rule is not used to locate a finding or to confirm its reason.
- **False positives**: every amendment on a unit that is not a planted unit. Only one amendment is built per unit and rule. Findings that make no amendment never count: `ok` records (section 6), findings under advisory rules, and conditional `below_band` findings.
- **Distractor hits**: amendments on units listed in `clean`. An amendment on an unlisted unflawed unit is a false positive all the same; `clean` only adds this second count. List the units you built to look flawed.
- **An earlier version in a single-version test.** Change records are ignored by this format, so a single-version test that declares a prior still uses `planted` and `clean`, with no `prior_records`. A key that contains `prior_records` is scored as a negotiation-style test, and its `planted` and `clean` are ignored.

**Which rule a finding is attributed to.**

- A band, date-window or computed-absence finding: the rule that produced it.
- A sum, product or blank-cell finding: Python computes it once per unit, on any unit paired with at least one rule. It is attributed to the paired rule whose named labels share the most words with the finding's field label (each counted twice) and with the labels it was computed from (each counted once). A tie goes to the rule that comes first in reading order. If that rule reaches no reviewer, the finding moves (section 3).

So the rule you name in `rule` must name the result's label and the labels it is computed from, and no other rule paired with that unit may name more of them.

**What each relation's figures mean:**

| Relation | Planted by | `value_a` | `value_b` | `field_label` |
|---|---|---|---|---|
| `sum_mismatch` | A table column of two or more figures that share one non-empty measure, whose sum differs from a label-line figure in the same unit, with the same measure, whose normalised label holds every word of the column label and at least one more (`Sum of line totals: 80 EUR` under a `Line total (EUR)` column). | the computed sum | the stated total | the total's label (`sum line total`) |
| `product_mismatch` | Two label-line figures whose measures multiply to a third label-line figure's measure (`4 box` times `12 EUR/box` against `52 EUR`). | the computed product | the stated figure | the stated figure's label |
| `above_band`, `below_band` | A figure, or a ratio of two figures, outside a band (section 7). | the figure or ratio | the bound crossed | The figure's label. A table cell adds ` row` and a number (`line total row2`); the number counts, from the top, only the cells of that column that hold a number. A ratio has no field label. |
| `missing_field`, declared | A field named in `[requires: ...]` that a unit in scope lacks. | 0 | 1 | the label as written in the directive, normalised |
| `missing_field`, blank cells | Blank cells in a column whose header has a measure, or whose non-empty cells all hold numbers. | the number of cells holding a number | the number of body rows | the column's label |
| `date_window` | Two dates further apart than the bound (section 7). | the gap | the bound | the first date's label |

A sum, product or date window agrees with the stated figure when they are the same within the tolerance of section 6; a band has no tolerance. A computed product, sum or ratio is rounded to 6 decimal places: write it so in the key. A planted band breach often also produces a ratio finding with the same figures on the same unit. Plant no separate entry for it.

**Negotiation-style test.** Instead of `planted` and `clean`, give `task` (one line, printed only) and two lists:

- `prior_records`: one row per record Python will write (section 6): one per label-line figure per unit that both versions state, unchanged ones included, and one per `absent_since_prior`. Each row has:
  - `field_label`, the label in any form (it is normalised before comparison);
  - `relation`;
  - `value_a`, the figure now (`null` for `absent_since_prior`);
  - `value_b`, the earlier figure;
  - `unit`, the measure of the earlier figure (not a unit id; `""` when there is none).
- `band_irregularities`: one row per irregular `above_band` or `below_band` finding, with `field_label`, `relation`, `value_a` (the figure), and `rule` (the operator's own id).

**How the scorer counts a negotiation-style test.**

- A `prior_records` row is found when a record has the same normalised label, the same relation, both figures the same (within the tolerance of section 6) and the same measure. The unit id is not compared, so one record can satisfy several identical rows. Two units with the same label, relation, figures and measure cannot be told apart: give them different figures.
- **False positives**: every change record whose normalised label is not in `prior_records`, or appears there only with other relations.
- **Stray refusals**: refusals and orphans for labels the key does not list. They are counted apart, not as false positives.
- A `band_irregularities` row is found when an irregular band finding has the same relation, the same normalised label and the same `value_a`. Its attribution is correct when that finding's operator id equals `rule`.
- **Band false positives**: every irregular band finding whose label is not listed, conditional ones included. A ratio finding has no label and always counts here. So in a negotiation-style test, never put two figures whose measures divide to a band's measure in one unit.

## 10. The clean twin

The **clean twin** is a second bundle identical to the first, except that every planted flaw is repaired.

- Keep headings, labels, conventions, reference corpus, the earlier version's file name and the manifest roles the same, so the unit ids line up.
- Repair a flaw by changing values. Repair a missing field by adding its label line, with a value. Adding a label line changes no unit id. A blank `Label:` line still counts as absent.
- Give the twin's document a different neutral file name, because the scorer finds a twin's run by that name. Update `targets` to match.
- The twin's key has `"planted": []`, its own `document`, a `twin_of` naming the first bundle, and the same `clean` list. The first bundle's key names the twin. Both folders sit side by side in the same parent folder (section 1).
- Every amendment on the twin is a false positive.

**The twin check.** The scorer takes the twin's newest run (by run folder name) and lists the claims (relation, field label and the finding's explanation sentence) worded identically in both runs. A claim worded identically in both twins' runs did not come from the document.

## 11. Perturbation probes

A **perturbation probe** is a copy of a bundle with one controlled change, shipped as its own bundle with its own key. No code reads a probe declaration: this is a convention of this format. Record which probe it is in a top-level `probe` field of the key, which the scorer ignores.

1. **Reworded labels.** Rewrite one label in other words with the same meaning, everywhere it appears in the document files (the target and the earlier version). Leave conventions, directives and reference files unchanged. Update `field_label` in the key to the new label's normalised form. Rules match labels by their words, so expect this: a rule that named the old words no longer pairs through that field, and a `[requires: ...]` naming the old label reports `missing_field` on every unit in scope. The probe measures exactly this dependence.
2. **Reordered sections.** Move sections. Unit ids carry position, so update every moved unit's id in the key. The earlier version is matched by slug, so its records are unaffected. Keep any flaw that depends on a neighbouring unit next to that neighbour.
3. **A term only in the later version.** The target states a figure the earlier version does not, and the earlier version is declared as `prior`. The key lists no record for that term. A single-version test hosts this probe by adding an earlier version that lacks the term.
4. **A value in a different format.** Write a figure differently with the same reading: `1250`, `1,250`, `1 250` or `1250.00` (section 2). Never `1.250`, which reads as 1.25. The key is unchanged. Changing the measure token (`$` for `USD`) is a different measure, not a different format.

## 12. How a multi-round case is declared

A **multi-round case** is a test that spans more than two versions of one document. This section is completed after S2 merges (S2 is the development stage that settles how such a case is declared).

## 13. Glossary

- **Amendment**: a proposed change to the document, made from an irregular finding under a required or recommended rule.
- **Answer key**: `answer_key.json`; it states the planted flaws and is read only by the scorer.
- **Band**: an allowed range for a figure, from a rule's text or a reference table; both bounds included.
- **Clean distractor**: a correct unit built to look like a flaw.
- **Clean twin**: the same bundle with every flaw repaired.
- **Computed absence**: a missing required field, decided by Python.
- **Conditional finding**: a `below_band` finding that the rule qualifies; recorded, never an amendment.
- **Conventions**: the rules in `conventions/`.
- **Date cutoff**: the repository-wide date that decides the role of a file the manifest does not name.
- **Directive**: a heading bracket whose first word is `scope`, `requires` or `unless`, followed by a colon.
- **Document under review (target)**: the file named in `targets`.
- **Earlier version (prior)**: the file named in `prior`, compared with the target.
- **False positive**: an amendment on a unit with no planted flaw; in a negotiation-style test, a record the key does not give.
- **Field**: a label and its value, from a label line or a table header.
- **Figure**: the first number of a field's value, with its measure.
- **Finding**: a typed record stating a unit, a rule, a relation, a verdict and, where it can, a field and figures.
- **Grounding**: every file in `context/` that is not under review.
- **Judged absence**: one model question about one unit and one scoped rule.
- **Key column**: a text column of a reference table whose cells are all different.
- **Label line**: a line of the form `Label: value`.
- **Label universe**: every label of the document under review.
- **Manifest**: `_review_targets.json`, which assigns file roles.
- **Mandate**: the conventions file of a negotiation-style test.
- **Measure**: a figure's unit of measurement, such as `EUR`, `box` or `%`.
- **Model**: the language model Shimmer asks questions in words.
- **Neutral naming**: names, headings, labels and values that reveal nothing about flaws or answers.
- **Normalised label**: a label reduced to its comparable words (section 2).
- **Operator**: the person who runs Shimmer and writes its rules.
- **Operator's own id**: the `CONV-...` id written on a rule heading.
- **Pairing**: deciding that a rule applies to a unit.
- **Per-test setting**: a value that changes one test only (none is read today).
- **Perturbation probe**: a bundle copy with one controlled change.
- **Planted flaw**: a deliberate error recorded in the key.
- **Preamble unit**: the text before the first unit heading, id `u00-...`.
- **Python**: Shimmer's fixed code, which computes every figure and comparison.
- **Range**: two figures in one cell, low first.
- **Recall**: the planted flaws a run detects, out of all of them.
- **REF id**: the id of one reference passage, which is one paragraph.
- **Reference corpus**: the grounding files that bands and citations come from.
- **Registry id**: Shimmer's sequential `CONV-001`-style id for a rule.
- **Relation**: the kind of disagreement a finding records.
- **Reviewer**: a model agent asked about one rule and one unit; the rule-checking reviewer or the wording reviewer.
- **Scope**: the units a rule governs.
- **Scorer**: the program that compares a run with the answer key.
- **Sealed**: unchangeable once any result on the bundle has been seen.
- **Severity**: required, recommended or advisory.
- **Slug**: the lowercased, hyphenated form of a heading.
- **Subject tag**: a heading bracket word that routes a rule to a reviewer.
- **Test bundle**: the folder holding one complete test.
- **Typed reason (claim)**: the relation, field label and figures of a planted flaw.
- **Unit**: the piece of a document that a rule is applied to.
- **Unit id**: `u`, a two-digit position, a hyphen, and the heading's slug.
- **Verdict**: `irregular` (a problem) or `ok` (information only).
