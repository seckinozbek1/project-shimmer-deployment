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

A test is delivered as two separate things:

- the **test archive**: everything Shimmer needs to run the test, and nothing else;
- the **answer key** (section 9): one file, `answer_key.json`, delivered to the scorer by its own route. It is never inside the archive, and the machine that runs Shimmer never receives it.

Both are **sealed** once written: nothing in them changes after a result on the test has been seen. A multi-round case that is also scored as an ordinary two-version review is delivered as two test archives and one key (section 12, "The same bundle as an ordinary review").

**The test archive** is a tar file (compressed or not) whose members sit at these paths, and only these:

```
_review_targets.json     the manifest (section 6)
context/
  <document>.md          the document under review
  <earlier version>.md   optional (section 6)
  <reference>.md         the reference corpus, one or more files (section 7)
conventions/
  <rules>.md             the conventions (sections 3 to 5)
case_manifest.json       multi-round cases only (section 12)
```

- The manifest sits at the top of the archive, beside `context/`, not inside it. An archive without it is refused. When the test is prepared, the manifest is placed where Shimmer reads it, next to the documents.
- Do not also put a copy of the manifest inside `context/`: both copies land on the same file, and which one is kept depends on the order of the archive's members.
- Any other member refuses the whole archive: an `answer_key.json`, a notes file, anything at the top other than the two files shown. A member's path may start with `./`. A link, or `..` in a path, is refused.
- Put no subfolder inside `context/` or `conventions/`. Its files are carried to the machine that runs the test, but Shimmer never reads them.
- A multi-round case (section 12) reads no reference corpus: its `context/` holds only the case documents its rounds name, and no reference file.
- When the test is prepared, every CRLF line end in a text member (`.md`, `.json` and other plain-text files) becomes LF. `case_manifest.json` is kept byte for byte.

**The answer key.** Never put the key, or any answer, in the archive or in `context/`. A `.json` file in `context/` is read as a document, and a `.json` file at the top of the archive other than the two named above refuses the archive.

**The working folder.** To run a test on this machine and score it with the scorer in this repository, keep it as one folder:

```
<bundle>/
  context/
    _review_targets.json
    <document>.md
    <earlier version>.md
    <reference>.md
  conventions/
    <rules>.md
  answer_key.json
  case_manifest.json     multi-round cases only (section 12)
```

- Here the manifest sits inside `context/`: the staging tool (`tools/stage_corpus.py`) copies only the files directly inside `context/` and `conventions/` into Shimmer's input folders, so a manifest anywhere else is never seen. It does not copy `answer_key.json` or `case_manifest.json`.
- **Where working folders live.** One folder per test under `benchmark/corpora/`, and a test and its twin (section 10) side by side there. The scorer in this repository (`tools/score_corpus.py`) reads keys only from `benchmark/corpora/<bundle>/answer_key.json` and finds a twin's key by its folder name there, so a test is scored with its twin only when both sit there.
- **From working folder to archive.** Move `context/_review_targets.json` to the archive's top, leave `answer_key.json` out, and keep `case_manifest.json` at the top for a multi-round case. Change nothing else. Shimmer then reads the same manifest, documents and conventions in both forms.
- **Sealed tests.** Keep a sealed test's archive and key outside this repository, and keep no working folder of it under `benchmark/corpora/`. The cloud tool builds a sealed bundle only outside the repository and refuses to launch one inside it; it does not check where the archive itself is, so this part is the preparer's rule.

- **File types.** Documents, reference files and conventions are Markdown files (`.md`). The manifest, the case manifest and the answer key are JSON files (`.json`). Nothing else.
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
   - A **measure** in brackets at the end of a header, as in `Line total (EUR)`, is the column's unit of measurement. It is not part of the label. The bracket holds 1 to 16 characters: a letter, `%` or a currency symbol first, then only letters, digits, `/`, `%`, `*` and `-`. A bracket in words, such as `(cubic metres)`, gives no measure, and is still left out of the label.
   - In the document under review, a cell's own measure replaces the header's for that cell: under `Volume (mL)`, the cell `7 L` is 7 `L`. Only a cell with no measure of its own takes the header's. Write table cells as plain numbers. A reference table is read the other way round (section 7).
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
- **Disagreeing measures are never compared.** A sum is not computed when the cells of its column do not all agree, or when the total's measure differs from theirs. A product is not computed when no third figure has the measure the two multiply to. A figure is not compared with a band in another measure. Nothing is written in any of these cases: no finding and no refusal, so there is nothing to key. Only a change record (section 6) is refused visibly when the two versions' measures differ.
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
| `[unless: label]` | Suspends the rule on any unit that carries that label, as a label line with a value or a table header, whatever the value says. On that unit the rule is not applied at all: no band, date-window or absence finding comes from it, and no sum, product or blank-cell finding is attributed to it. |
| `[unless: CONV-X]` | Names another rule that qualifies this one. Python never suspends on it; the other rule's text goes to the reviewer together with this rule. A name that matches no rule is read as a label if the unit carries it. Otherwise it is ignored. A rule with any `[unless: ...]` never receives a moved finding (section 3). |

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
4. **Every rule names at least one document label, or declares a scope.** A document label is a label of the document under review: in a test with an earlier version, the target's; in a multi-round case, the last round's document. So a rule names a renamed term by its later label, and need not name the earlier one (section 9, "Multi-round keys", says how an earlier round's statement is keyed).
5. **Coverage.** Every unit of the document under review (in a multi-round case, the last round's document) except the preamble is in scope of, or pairs with, at least one rule. The preamble needs no scope to exclude it: a rule pairs with the preamble only if the preamble carries every label the rule names. Keep the labels your rules name out of the preamble, unless a rule is meant for it.
6. **Scope values must sit in label lines.** If the units in scope differ from the others only by a value, give every unit a label line that states that value, and pin the scope to it. A value that appears only in a table cell cannot be used.
7. **No `[unless: ...]`.** No rule declares one. A field condition switches the whole rule off on every unit that carries the label, and a rule condition is never checked by Python, so either would make a catch depend on a directive written for one test. State a condition in the rule's text instead:
   - A condition on a field. If the rule is a completeness rule, the units it governs are named by its scope (rule 1), pinned to a value where needed. If the rule's band comes from a reference table or a labelled sentence, naming the field in its text makes the low side conditional on units that carry it (section 7). Otherwise Python does nothing with it.
   - A condition on another rule. Name that rule in the text ("Read with CONV-P02."). Python does nothing with it; only a reviewer reads it.

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
- A mandate may also hold other rules, such as one requiring a total to equal a sum, in a negotiation-style test and in a multi-round case. The negotiation-style scoring (section 9) reads only change records and band findings, so the findings of such rules count neither as found rows nor as false positives there. In a multi-round case they are round findings like any other (section 9, "Multi-round keys").
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
- no label new in that unit of the target has a figure in the same measure, except a new label that a rename within 2% (below) has claimed for another earlier label. Two figures with no measure count as the same measure here.

A label is **new** in a unit unless the earlier version states it somewhere, under any heading, with one figure and a REF id; a label whose earlier statements were refused (a tie, or no REF id) counts as new. Only label-line figures of the target unit are tested. When a new label in the same measure blocks the record, the refusal says which case it is:

- **Possible rename** (`reason_kind` `possible_rename`): a new label in the same **non-empty** measure has a figure that differs from the earlier figure by at most 2% of the larger of the two in absolute value, 2% included. That new label is then claimed by this earlier label and blocks no other earlier label as a possible successor. From an earlier 100 `box`, a new 102.04 `box` is a possible rename (1.9992% of 102.04), and 97.96 `box` is not (2.04% of 100).
- **Possible successor** (`possible_successor`, or `possible_successor_no_unit` when neither figure has a measure): otherwise, a new label in the same measure that no rename has claimed. From 100 `box`, 97.96 `box` and 140 `box` are both possible successors; 140 `kg` blocks nothing, and the label is `absent_since_prior`.

A refused label is never withdrawn. Section 9 says how a key states which refusal it expects.

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
  - With a header measure, a measure written in a cell is ignored: under `Price band (EUR/box)`, the cell `8 USD to 15 USD` is read as 8 to 15 `EUR/box`. Write range cells as two plain numbers.
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

A band the rule states itself (below) never has a conditional low side: its `below_band` is always firm, whatever other labels the rule names and the unit carries. "The shrinkage must lie between 1% and 4% unless a recount note is filed." gives a firm `below_band` on a unit with `Shrinkage: 0.5 %` and `Recount note: none filed`. The low-side test applies only to bands from reference tables and labelled sentences.

**Other ways to state a bound.**

- **A rule may state its own band**: two or more figures with the same measure in its text. The lowest and the highest are the bounds. The band applies to the fields the rule names that the unit holds as figures; if the unit holds none of them as figures, it applies to every figure with that measure. Ratios of every pair of label-line figures are compared as for a table band. Never write two figures with the same measure in a rule unless they are its band.
- **A labelled sentence** in a grounding file, of the shape `Label: words 8 to 15 EUR/box.` (label at most 48 characters, exactly two numbers after the colon, a measure the document writes), is read as one row of a band table. The label is the key cell and the words before the first number are the column header the rule must name. Do not write this shape anywhere in grounding files, the earlier version included, unless you mean a band.
- **A date window** needs all of these:
  - a unit with two dates the rule names: either two label lines each holding exactly one ISO date (`2026-03-01` or `2026-03-01 09:30`), or one label line holding exactly two. The rule must name each line's label. If the rule names both shapes, or three or more such lines, there is no window;
  - a **bound sentence**: a sentence (defined below) holding exactly one number in all, measured in `hours` or `days` (written exactly so), whose other words, normalised, all appear in the rule: "The standard reply window is 48 hours." It may sit in a grounding file, within the first 200 characters of its paragraph, or in the document under review;
  - among all sentences holding exactly one number in all, with a measure of any kind, whose other words the rule all uses, in the grounding files and in the document, the bound sentence must have the most words. A tie means no window, whatever the figures say. Two copies of the same sentence tie, whether they sit in two grounding files, twice in one file, or in a grounding file and the document. An earlier version is a grounding file, so a sentence it shares with the document always ties. If the winning sentence's measure is not `hours` or `days`, there is no window either. Write the bound sentence once, in one reference file, and write no other such sentence anywhere.
  - **What a sentence is.** The document under review is read whole; a grounding file only as its stored passages (so a prose paragraph's first 200 characters). Each paragraph (a run of non-blank lines) is read like this: lines that start, after any spaces, with `|` or `#` are dropped; the other lines are joined with single spaces; the result is split after every `.`, `?` or `!` that is followed by a space. A label line is therefore not a sentence of its own: the lines of one paragraph join into one sentence until one of them ends with `.`, `?` or `!`. `Window note: standard` above `Window length: 48 hours` in one paragraph is the one sentence `Window note: standard Window length: 48 hours`, with one number and the words `window note standard window length`. A label line alone in its paragraph, such as `Fee: 45 EUR`, is a sentence too. An ISO date counts as three numbers (`2026-03-01` gives 2026, -3 and -1).

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
- **The review mode**: `paired` (one unit and one rule at a time, with Python's arithmetic) or `wide` (the model sees the whole document at once). A run started by hand uses `--review-mode` when given; without it, the mode follows the backend profile: `paired` under the local profile (`tools/run_local_demo.py` adds it), `wide` otherwise. The cloud tool always passes `--review-mode paired`, so every cloud run, ordinary or multi-round, is paired. Sections 4, 5 and 7 describe the paired mode. In the wide mode, Python computes only the change records of section 6.
- **The pair cap** (`--pairs-per-unit`, off unless the run sets it): when set, rules past the cap on a unit are not reviewed.

Changing one of these for one test is a code change.

## 9. The answer key

`answer_key.json` is read only by the scorer, never by Shimmer. It travels apart from the test archive (section 1). It must exist before any run.

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

**Key forms and their required top-level fields.** Every key names the task in one field, `task_given_to_the_pipeline`, whatever its form.

| Key form | Required top-level fields | Also, when it applies |
|---|---|---|
| Single-version | `document`, `task_given_to_the_pipeline`, `planted`, `clean` | `twin_of` (a test with a twin, and that twin); `probe` (a probe, section 11) |
| Negotiation-style (below) | `document`, `task_given_to_the_pipeline`, `prior_records`, `band_irregularities` | `expected_refusals` (renamed terms, below); `twin_of`; `probe` |
| Multi-round case that is not negotiation-style | the single-version fields, with `planted` and `clean` entries scoped by round ("Multi-round keys", below) | `archives` (a sealed case scored both ways, section 12) |
| Negotiation-style and multi-round | the negotiation-style fields and `multi_round` | `expected_refusals`; `archives` |

Older keys under `benchmark/corpora/` name the task `task` in a negotiation-style key. The repository's scorer prints `task` for a negotiation-style test and `task_given_to_the_pipeline` for a single-version one, and prints an empty line when that field is absent. The task is only printed, never scored.

**A planted entry** has these fields:

- `unit`: the full unit id. It is matched as a case-insensitive substring of a finding's unit id.
- `rule`: the operator's own id of the rule the finding will be attributed to (below).
- `relation`: always write it, equal to `claim.relation`. A finding must carry it to locate the flaw.
- `kind`: your own category label. Recall is reported per kind.
- `claim`: the **typed reason**, with four parts:
  - `relation`;
  - `field_label`, the normalised label exactly as section 2 and the table below produce it;
  - `value_a` and `value_b`, the two figures as numbers, as the table below defines them.
- Any other field in a planted entry, and any other top-level field of the key, is ignored by the scorer.

**A key states the truth, not what Shimmer computes.** Key every flaw a correct reviewer should report, whether or not Python computes it. Never write a key from a Shimmer result: a test measures Shimmer, and a key fitted to it measures nothing.

- A flaw Python computes is keyed with Python's relation and figures (the table below).
- A flaw Python's relations describe but Python does not compute in this test is keyed with that relation all the same. For example, a `date_window` whose bound is stated in another unit of the document, in a sentence whose other words the rule does not all use (or in one that ties with another candidate): the bound search of section 7 reads the document too, but finds no winning bound sentence there, so Python computes no window.
- A flaw no Python relation describes is keyed with one of the four relations Python never writes: `unit_mismatch`, `rate_mismatch`, `copy_mismatch` and `carry_mismatch` (table below). Shimmer writes none of these today, so the scorer can confirm such a flaw's reason only if a finding with that relation ever appears, and can locate it only by an amendment on its unit under its rule. It counts as missed otherwise.
- Key every flaw under a rule whose text it breaks as written. A figure in the wrong measure breaks no band or sum rule (Python compares nothing across measures), so a test that plants one also states a rule requiring the measure ("Each result must be written in the measure in which its parameter's range is given."), and keys the flaw under that rule. Word such a rule so it takes no band and no sum attribution from the others (sections 7 and 9).

**Flaws that depend on another unit.** Python computes every relation inside one unit; no relation compares two units. A reviewer asked about a unit is also shown the units just before and after it, as context, but it is asked only where Python found a disagreement on that unit, or computed nothing there. Key the flaw on the unit that is wrong, and name the other unit in an extra field of the planted entry: `depends_on_unit` for the unit just before or after, `source_unit` for a unit a figure was copied from, `related_unit` for a distant unit whose figure or condition decides it. A carried figure that also makes the unit's own column disagree with its stated total is a `sum_mismatch` Python computes; one that leaves each unit adding up on its own is a `carry_mismatch`.

**How the scorer counts a single-version test.**

- **Located**: a finding whose unit id contains `unit` and whose relation equals `relation`; or an amendment on that unit under the rule `rule`.
- **Detected** (reason confirmed, the figure that counts): among the located findings, one whose relation equals `claim.relation`, whose `field_label` is exactly the same text as `claim.field_label`, and whose two figures include both claim figures. A finding with no field label passes the label test. Figures are rounded to 6 decimal places and must then be equal; their order does not matter.
- **Attribution**: whether the amendment for a located flaw carries the rule `rule`. The rule is not used to locate a finding or to confirm its reason.
- **False positives**: every amendment on a unit that is not a planted unit. Only one amendment is built per unit and rule. Findings that make no amendment never count: `ok` records (section 6), findings under advisory rules, and conditional `below_band` findings.
- **Which findings count.** The repository's scorer locates and confirms with every finding on the bus, whoever wrote it: a model's finding counts as much as Python's, and a judged absence counts in both of its copies (`docs/OUTPUT_FORMAT.md`, sections 5.4 and 5.5). It reports the relations only a model wrote apart. A scorer that must not be moved by model text confirms a reason only from Python's findings and from Python's stamped copy of a judged absence, reports locations only a model found separately, and counts a judged absence once.
- **Distractor hits**: amendments on units listed in `clean`. An amendment on an unlisted unflawed unit is a false positive all the same; `clean` only adds this second count. List the units you built to look flawed.
- **An earlier version in a single-version test.** Change records are ignored by this format, so a single-version test that declares a prior still uses `planted` and `clean`, with no `prior_records`. A key that contains `prior_records`, even an empty list, is scored as a negotiation-style test, and its `planted` and `clean` are ignored.
- **Where it lives.** A single-version test may declare an earlier version or not; its twin declares the same file (section 10). Probe 3 (section 11) adds one to a test that has none, and then only the probe has one. Its change records never become amendments, but it is a grounding file and so part of the reference corpus (section 7): its tables and labelled sentences can become bands, and its sentences compete in the date-window bound search. An earlier version made from the document repeats the document's text, so audit it as a reference file.

**Which rule a finding is attributed to.**

- A band, date-window or computed-absence finding: the rule that produced it.
- A sum, product or blank-cell finding: Python computes it once per unit, on any unit paired with at least one rule. It is attributed among the rules paired with that unit, in reading order, leaving out any rule suspended there by `[unless: ...]`:
  - For each rule, take the **set** of words of all the labels its text names (section 4, longest match only). A scoped rule counts the labels its text names, not its scope. A word that two named labels share counts once.
  - The rule scores 2 for each of those words that is in the finding's field label, plus 1 for each that is in the finding's **basis**, a fixed sentence split at spaces: `sum of N values under <column label>` for a sum, `<first label> times <second label>` for a product, and `<column label> is filled in N of M rows` for blank cells, where N and M are counts. So for blank cells each word of the column label scores 3, and the words `sum` and `filled`, and a count of three or more digits, score too when a named label holds them.
  - The highest score wins. A tie goes to the rule that comes first in reading order. If every score is 0, the first rule in reading order takes the finding.
  - If the winner reaches no reviewer, the finding moves (section 3) to the first other paired rule, in reading order, that reaches a reviewer, has no `[unless: ...]`, and whose text, lowercased and split at spaces only, contains every word of the field label. With none, it moves to the first rule that reaches a reviewer and has no `[unless: ...]`. This test does not normalise: `totals` or `total.` in a rule's text does not contain `total`.

So the rule you name in `rule` must name the result's label and the labels it is computed from, and every other rule paired with that unit must score strictly lower. Do not rely on reading order to break a tie, and make sure the named rule reaches a reviewer.

**What each relation's figures mean:**

| Relation | Planted by | `value_a` | `value_b` | `field_label` |
|---|---|---|---|---|
| `sum_mismatch` | A table column of two or more figures that share one non-empty measure, whose sum differs from a label-line figure in the same unit, with the same measure, whose normalised label holds every word of the column label and at least one more (`Sum of line totals: 80 EUR` under a `Line total (EUR)` column). | the computed sum | the stated total | the total's label (`sum line total`) |
| `product_mismatch` | Two label-line figures whose measures multiply to a third label-line figure's measure (`4 box` times `12 EUR/box` against `52 EUR`). | the computed product | the stated figure | the stated figure's label |
| `above_band`, `below_band` | A figure, or a ratio of two figures, outside a band (section 7). | the figure or ratio | the bound crossed | The figure's label. A table cell adds ` row` and a number (`line total row2`); the number counts, from the top, only the cells of that column that hold a number. A ratio has no field label. |
| `missing_field`, declared | A field named in `[requires: ...]` that a unit in scope lacks. | 0 | 1 | the label as written in the directive, normalised |
| `missing_field`, blank cells | Blank cells in a column whose header has a measure, or whose non-empty cells all hold numbers. | the number of cells holding a number | the number of body rows | the column's label |
| `date_window` | Two dates further apart than the bound (section 7). | the gap | the bound | the first date's label |
| `unit_mismatch` | Never written by Python. A figure written in a measure other than the one its rule, its reference table or its table column uses (`0.0452 g/L` where the range is in `mg/L`). Add `claim.unit_a` and `claim.unit_b`, the two measures as written. | the figure as written | the same figure in the measure the rule uses | the figure's label |
| `rate_mismatch` | Never written by Python. A figure that is not a stated percentage of another figure of the unit (`Duty due` is not `Duty rate` percent of `Total line value`), or a stated percentage that is not one figure of the unit as a percentage of another (a ratio error: `Freight share` is not `Freight` as a percentage of `Total line value`). | the rate applied, or the ratio computed, rounded to 6 decimal places | the stated figure | the stated figure's label |
| `copy_mismatch` | Never written by Python. A figure copied into one unit's table from another unit, that differs from it. Name the other unit in `source_unit`. | the figure in the source unit | the figure in the table | the column's label with ` row` and a number, as for a table cell above |
| `carry_mismatch` | Never written by Python. A figure carried from the unit before that differs from that unit's figure, while each unit adds up on its own. Name the unit before in `depends_on_unit`. | the figure in the unit before | the figure carried | the carried cell's label, as for a table cell above |

A sum, product or date window agrees with the stated figure when they are the same within the tolerance of section 6; a band has no tolerance. A computed product, sum or ratio is rounded to 6 decimal places: write it so in the key. A planted band breach often also produces a ratio finding with the same figures on the same unit. Plant no separate entry for it.

**A blank cell in a summed column.** Only cells that hold a number are summed: a blank cell, or a cell with no number in it, adds nothing, and a sum needs at least two cells that hold a number. The blank-cell finding is computed separately. So a blank cell in a column with a stated total always gives the blank-cell `missing_field` finding, and also gives a `sum_mismatch` (with `value_a` the sum of the filled cells) whenever the total differs from that sum. If you plant a blank cell there, either write the total as the sum of the filled cells, or key both findings.

**Negotiation-style test.** Instead of `planted` and `clean`, give two lists (and `task_given_to_the_pipeline`, one line, printed only, as every key does):

- `prior_records`: one row per change record the two versions call for (section 6): one per label-line figure per unit that both versions state under the same label, unchanged ones included, and one per term truly withdrawn (`absent_since_prior`), also when an unrelated new term in the same measure sits in its section, where Python refuses it as a possible successor. A term only renamed is not withdrawn and gets no row: list it in `expected_refusals` (below). Each row has:
  - `field_label`, the label in any form (it is normalised before comparison);
  - `relation`;
  - `value_a`, the figure now (`null` for `absent_since_prior`);
  - `value_b`, the earlier figure;
  - `unit`, the measure of the earlier figure (not a unit id; `""` when there is none).
- `band_irregularities`: one row per irregular `above_band` or `below_band` finding, with `field_label`, `relation`, `value_a` (the figure), and `rule` (the operator's own id). These rows are the planted flaws of a negotiation-style test.
- Every row of both lists must have `field_label` and `relation`, or the scorer stops with an error. Any other field in a row (a unit id, the bound crossed, your own kind) is ignored. Recall is not reported per kind in a negotiation-style test.

**How the scorer counts a negotiation-style test.**

- A `prior_records` row is found when a record has the same normalised label, the same relation, both figures the same (within the tolerance of section 6) and the same measure. The unit id is not compared, so one record can satisfy several identical rows. Two units with the same label, relation, figures and measure cannot be told apart: give them different figures.
- **False positives**: every change record whose normalised label is not in `prior_records`, or appears there only with other relations.
- **Stray refusals**: refusals and orphans for labels the key does not list. They are counted apart, not as false positives.
- A `band_irregularities` row is found when an irregular band finding has the same relation, the same normalised label and the same `value_a` within the tolerance of section 6. The unit and `value_b` are not compared, so one finding satisfies every row with the same label, relation and figure: give such rows different figures. A conditional `below_band` (section 7) is found like any other. Its attribution is correct when that finding's operator id equals `rule`.
- **Band false positives**: every irregular band finding whose label is not listed, conditional ones included. A ratio finding has no label and always counts here. So in a negotiation-style test, never put two figures whose measures divide to a band's measure in one unit.
- **Which findings count.** The repository's scorer reads change records whose `provenance` is `computed`: Python sets that on its change records, and a model can write the field too (`docs/OUTPUT_FORMAT.md`, section 5.4). It reads band findings from every irregular band finding on the bus, whoever wrote it, so a model's band finding can satisfy a `band_irregularities` row and counts as a band false positive. No other finding (a sum, a product, an absence) is counted in a negotiation-style test. A scorer that must not be moved by model text reads both lists only from findings written by `python` (`docs/OUTPUT_FORMAT.md`, section 5.4), and reports what only a model wrote separately.

**Renamed terms and expected refusals.** A term the later version states under a new label, with its figure unchanged or moved, in its own section or another, is the same term: a correct reviewer does not call it withdrawn. Python cannot tell a rename from a withdrawal by structure, so it refuses where section 6 says, and the refusal carries a typed `reason_kind` (`docs/OUTPUT_FORMAT.md`, section 7.1). List every renamed term in `expected_refusals`. It is a top-level field of a negotiation-style key only, beside `prior_records`; a single-version key has none, and a key that is also a multi-round case keeps it at the top, never inside `multi_round`.

```json
"expected_refusals": [
  {"field_label": "annual fee", "later_field_label": "yearly fee",
   "unit_id": "u03-clause-wren", "reason_kind": "possible_rename",
   "value_a": 3.1, "value_b": 3.1, "unit": "%"}
]
```

| Field | Meaning |
|---|---|
| `field_label` | The earlier label, normalised. |
| `later_field_label` | The label the later version uses for the same term, normalised. |
| `unit_id` | The unit of the later version whose heading the earlier statement sat under: where the refusal is recorded. |
| `reason_kind` | The kind of refusal the evidence supports, decided from the two figures as section 6 defines the kinds, so one of the three kinds `docs/OUTPUT_FORMAT.md` section 7.1 gives a vanished label: `possible_rename` when the later figure is within 2% of the larger of the two in the same non-empty measure; `possible_successor` when it moved further and the new label is in the same section; `possible_successor_no_unit` when it moved further, the new label is in the same section and neither figure has a measure. `null` when the new label sits in another section: Python is expected to refuse nothing there, and only a matched rename satisfies the row. Plant a moved figure clear of the 2% line: move it by more than 2.05% of the earlier figure. Such a move is never within 2% of the larger, whichever way it moves (the exact limit is 2/98 = 2.0408...%). |
| `value_a`, `value_b`, `unit` | The figure now and the earlier figure, and their measure (`""` when there is none), as in `prior_records`: the figures a matched rename compares. |

How a row is counted:

- **A refusal** satisfies the row when `reason_kind` is not `null` and `prior_refusals` (`docs/OUTPUT_FORMAT.md`, section 7.1) holds an entry whose `label` normalises to `field_label` and whose `unit_id` equals the row's `unit_id`. A refusal whose kind differs from `reason_kind` still satisfies the row; report the kind beside it.
- **A matched rename** satisfies the row whatever its `reason_kind`: a change record (`docs/OUTPUT_FORMAT.md`, section 6.5) on `later_field_label` with any relation other than `absent_since_prior`, whose `value_a` is the row's `value_a` (the later figure) and whose `value_b` is the row's `value_b` (the earlier figure), both within the tolerance of section 6, in the row's measure `unit`. Such a record is then not a false positive.
- An `absent_since_prior` on `field_label` is a false positive (a fabricated withdrawal).
- A refusal of a label the key lists here is not a stray refusal.

The repository's scorer does not read `expected_refusals` yet, and counts a matched rename's record as a false positive.

**`unit_mismatch` names two different things.** As a planted relation it is `claim.relation` of a planted entry (the table of relations above); as a refusal it is a `reason_kind` in `prior_refusals` (`docs/OUTPUT_FORMAT.md`, section 7.1). They are different fields and are never compared with each other.

**Rename probes are measured in the ordinary two-version review** of the bundle: the last version reviewed against its declared prior (section 6). A multi-round run writes no change records (section 12), so it measures no rename probe. Section 12, "The same bundle as an ordinary review", says how that run is made from a multi-round bundle.

**Multi-round keys.** A multi-round case (section 12) is scored from the Python round findings of each round (`docs/OUTPUT_FORMAT.md`, section 10.2), with these additions to the single-version form:

- Every `planted` entry and every `clean` entry carries `round_id` and `document_id`: the round and the document it is about. `unit` is that document's unit id. A `clean` entry is then an object with those three fields.
- Key every round, not only the last: a figure that breaks its rule in an earlier round is a planted flaw of that round. When the case manifest declares a renamed term as one issue (section 12), a correct reviewer reads the earlier label of an earlier round under the rule that names the later label, so key it under that rule (Python's round review pairs by the label's words and will not); an `issue_id` in the entry, ignored by the scorer, says which issue it is.
- A bundle that is both a negotiation-style test and a multi-round case keeps its negotiation-style lists at the top of the key and puts the multi-round entries in a top-level `multi_round` object holding `planted` and `clean`, which the ordinary scorer ignores.
- A finding counts for an entry only when its round and document match. A finding reused into a later round (section 12) belongs to the round it is posted in: key it again for that round if the flaw is still there.
- **How an entry is matched.** The round findings are the items posted on bus channel `multi_round` (`docs/OUTPUT_FORMAT.md`, section 10.2): the envelope's `doc_id` is the document id, and each item carries `round_id`. A finding **locates** an entry when its `round_id` equals the entry's `round_id`, its envelope's `doc_id` equals the entry's `document_id`, the entry's `unit` is a case-insensitive substring of the finding's unit id (as for a single-version entry), and its relation equals the entry's `relation`. A multi-round run writes no amendments, so an entry is located only by a finding, never by an amendment. A located entry's reason is **confirmed** as for a single-version entry: the same `field_label` and both figures.
- **False positives** are the irregular round findings on a (round, document, unit) that no planted entry names. A multi-round run writes no amendments, so false positives are counted on findings.
- **Distractor hits** are the irregular round findings on the (round, document, unit) of a `clean` entry.
- `twin_of` names a twin case with every flaw repaired in every round. A twin that repairs only the last round (so that its earlier versions stay the test's, as an ordinary two-version twin needs) is not such a twin: leave `twin_of` out of the multi-round entries then.
- Round findings carry the registry id, not the operator's own id (`docs/OUTPUT_FORMAT.md`, section 10.2): to check `rule`, give the scorer the case's conventions and number the rules as section 3 does.
- The repository's scorer does not score multi-round cases yet.

## 10. The clean twin

The **clean twin** is a second bundle identical to the first, except that every planted flaw is repaired.

- Keep headings, labels, conventions, reference corpus, the earlier version's file name and the manifest roles the same, so the unit ids line up.
- Repair a flaw by changing values. Repair a missing field by adding its label line, with a value. Adding a label line changes no unit id. A blank `Label:` line still counts as absent.
- Give the twin's document a different neutral file name, because the scorer finds a twin's run by that name. Update `targets` to match.
- The twin's key has `"planted": []`, its own `document`, a `twin_of` naming the first bundle, and the same `clean` list. The first bundle's key names the twin. Both working folders sit side by side under `benchmark/corpora/` (section 1).
- Every amendment on the twin is a false positive.

**The twin check.** The scorer takes the twin's newest run (by run folder name) and lists the claims (relation, field label and the finding's explanation sentence) worded identically in both runs. A claim worded identically in both twins' runs did not come from the document.

## 11. Perturbation probes

A **perturbation probe** is a copy of a bundle with one controlled change, shipped as its own bundle with its own key. No code reads a probe declaration: this is a convention of this format. Record which probe it is in a top-level `probe` field of the key, which the scorer ignores. A probe's key has no `twin_of`: a probe has no twin of its own, and a `twin_of` naming the test would make the twin check (section 10) compare two flawed runs.

1. **Reworded labels.** Rewrite one label in other words with the same meaning, everywhere it appears in the document files (the target and the earlier version). Leave conventions, directives and reference files unchanged. Update `field_label` in the key to the new label's normalised form. Rules match labels by their words, so expect this: a rule that named the old words no longer pairs through that field, and a `[requires: ...]` naming the old label reports `missing_field` on every unit in scope. The probe measures exactly this dependence.
2. **Reordered sections.** Move sections. Unit ids carry position, so update every moved unit's id in the key. The earlier version is matched by slug, so its records are unaffected. Keep any flaw that depends on a neighbouring unit next to that neighbour. A move also makes new neighbour pairs: make sure none of them breaks a rule (for a figure carried from unit to unit, join units whose figures agree), or key what it breaks.
3. **A term only in the later version.** The target states a figure the earlier version does not, and the earlier version is declared as `prior`. The key lists no record for that term. A single-version test hosts this probe by adding an earlier version that lacks the term. Choose a term that carries a planted flaw, so the probe measures whether a flaw on a new term is still caught; its planted entry stays in the key. A single-version test ignores change records (section 9), so a probe on a term with no flaw measures nothing.
4. **A value in a different format.** Write a figure differently with the same reading: `1250`, `1,250`, `1 250` or `1250.00` (section 2). Never `1.250`, which reads as 1.25. The key is unchanged. Changing the measure token (`$` for `USD`) is a different measure, not a different format.

## 12. How a multi-round case is declared

<!-- Sources (loop/s03, commit 990ed88): tools/ordinary_final_run.py (CASE_MANIFEST, LIVE_CASE_FIELDS, validate_live_case_manifest, case_corpus_documents, admit_workload, MULTI_ROUND_ARGV, assess); tools/prepare_ordinary_final_run.py (workload_members, prepare: root _review_targets.json required and not parsed, case manifest kept byte for byte and validated against the bound pipeline's _load_corpus; test_seal and prepare: test_archive_sha256 in seal.json and execution_manifest.json); tools/ordinary_final_cloud.py (admit: the bundle hash compared with the seal); tools/ordinary_final_bound_cloud.py (run_folder: seal.json copied into the session folder); scripts/run_context.py (RunContext.ensure: deliverables/ created for every run; multi_round_path); scripts/multi_round.py (begin, write_record); tools/ordinary_final_cloud.py (admit: validate_live_case_manifest at launch); scripts/multi_round.py (identifier, validate_manifest, normalize_request, bind_sources, STATES); scripts/strategic_support.py (MODES, mode); scripts/multi_round_phase.py (execute: fixture refusal, independent_review_unavailable, models given the case and the evidence only); scripts/multi_round_rounds.py (review_rounds, review_document, _findings_for_plans, unit_signature, SIGNATURE_INPUTS, PYTHON_PLAN_KINDS); scripts/pipeline.py (main: final-mode block, multi-round request parsing and exit 2, multi_round.begin right after the SHIMMER_INST_FINDER guard and its exit 9, exit 8 branches, case documents loaded by _load_corpus from input/context); scripts/text_extract.py (_extract_plaintext). -->

A **multi-round case** is a test that reviews two or more versions of a document set in order. Each version belongs to a **round**. The case is declared in one extra file, the **case manifest**. Everything in sections 1 to 5 still applies to the documents and the conventions.

The test archive of a multi-round case (section 1):

```
_review_targets.json       the manifest of section 6 (required; not read in this mode, below)
case_manifest.json         the case manifest (this section)
context/
  <round 1 document>.md
  <round 2 document>.md
conventions/
  <rules>.md
```

- An archive that holds `case_manifest.json` is prepared and run as a multi-round case. An archive without it is an ordinary test.
- The file name is exactly `case_manifest.json`, at the top of the archive. It holds one JSON object, in UTF-8 without a byte-order mark. A byte-order mark makes the file unreadable: the preparation fails, and a run started by hand stops before it starts. The file travels byte for byte; its line ends are not rewritten.
- In a working folder (section 1), keep `case_manifest.json` at the folder's top, beside `context/`. A run on this machine is given its path with `--multi-round --multi-round-manifest <path>` (both options together).
- **Which files are case documents.** In a multi-round run Shimmer does not read `_review_targets.json`. Every file directly inside `context/` that Shimmer reads as text (`.md`, and also `.txt`, `.rst`, `.log`, `.json`, `.pdf`, `.docx`, `.html`, `.htm`), whose name does not start with `_` and whose text is not empty, is a case document. Write case documents as Markdown only (section 1).
- **The targets manifest.** Keep it anyway: the preparation tool refuses a test without one, and does not read it. Write it as section 6 describes, with the last round's document as the target, the round before it as the `prior`, and every other case document as grounding. The same files can then also be run as an ordinary two-version review (below).
- **No reference corpus.** A multi-round run reads no grounding files: no reference tables, no labelled sentences, no bound sentences. A file in `context/` that no round names is loaded and then not used. Put only case documents in `context/`.
- **Document ids.** A case document's id is its file name without the extension: `quote_r1.md` has the id `quote_r1`. If two files share a name and differ only in extension, each gets the id `<name>__<extension>` (`quote_r1__md`). Avoid that: give every file its own name.
- **Conventions.** `conventions/` must hold at least one rule. With none, the round review records `no_conventions` and a cloud run fails its health check.
- **A renamed term as one issue.** When a later round states a term under a new label, declare it as one issue: the term's source in each round quotes that round's own line (the earlier label in the earlier round, the new label in the later one), and every one of those sources carries the same `issue_id`. Two labels on one issue is what tells a multi-round run that they are one term.

**The same bundle as an ordinary review.** An archive that holds `case_manifest.json` is always prepared and run as a multi-round case. The ordinary two-version review of the same files (the last round's document against its declared prior, section 6) is a second run, on a second archive:

1. The **ordinary-review archive** holds exactly the same members as the multi-round archive, without `case_manifest.json`. Shimmer then reads `_review_targets.json` and runs an ordinary review.
2. For a **sealed** test, seal both archives (section 1), and name both in the key, in a top-level `archives` object: `{"ordinary_review": "<SHA-256 of the ordinary-review archive's bytes>", "multi_round": "<SHA-256 of the multi-round archive's bytes>"}`. A run is scored only against the lists of the archive it was made from (item 4), and only when that archive's hash is the one the key names. A cloud run records that hash in its session folder (`docs/OUTPUT_FORMAT.md` section 11): the file `seal.json`, field `test_archive_sha256`, the SHA-256 of the bytes of the test archive the sealed bundle was prepared from (written by `tools/prepare_ordinary_final_run.py` when the bundle is sealed; `execution_manifest.json` in the same folder carries the same field and value). Compare it with the two values in `archives`: it equals at most one of them. An exposed cloud run's `seal.json` has no `test_archive_sha256` (its `test_manifest_sha256` is the text `exposed, no manifest`), and a run on this machine records no archive hash at all, so neither can be matched to `archives`.
3. In a **working folder** (section 1), the staging tool copies no `case_manifest.json`, so a run without `--multi-round` is the ordinary review, and a run given `--multi-round --multi-round-manifest case_manifest.json` is the multi-round run.
4. **Which key lists are scored from which run.** `prior_records`, `band_irregularities` and `expected_refusals` are scored from the ordinary review. The round-scoped entries (the `multi_round` object, or the top-level `planted` and `clean` of a multi-round key that is not negotiation-style) are scored from the multi-round run. One file in the run folder tells the two runs apart: `audit/multi_round.json`. A multi-round run writes it as soon as the run starts, before any review, and also when the run then stops early; an ordinary review never writes it. (One multi-round run does not write it: a run refused at start with exit code 9, the `SHIMMER_INST_FINDER` check of `docs/OUTPUT_FORMAT.md` section 4.2, stops before it. That run reviews nothing, so there is nothing in it to score.) So a run folder that holds `audit/multi_round.json` is the multi-round run, and a run folder without it is the ordinary review. Do not decide by `deliverables/`: every run creates that folder when its run folder is made, a multi-round run included, and a multi-round run leaves it empty (`docs/OUTPUT_FORMAT.md` sections 2 and 10). Whether the run finished is a separate question, answered by `audit/run_completion.json` (`docs/OUTPUT_FORMAT.md` section 4).

**Example.** Two rounds of an invented supply quote. `context/quote_r1.md`:

```
# Supply quote

## Item A-KX

Supplier: North desk
Unit price: 12 EUR/box
Quantity: 4 box
Line total: 48 EUR
```

`context/quote_r2.md` is the same text with `Unit price: 11 EUR/box` and `Line total: 44 EUR`. `case_manifest.json`:

```json
{
  "schema_version": 1,
  "case_id": "supply-quote-k3",
  "fixture": false,
  "rounds": [
    {"round_id": "r1", "sequence": 1, "document_ids": ["quote_r1"]},
    {"round_id": "r2", "sequence": 2, "document_ids": ["quote_r2"]}
  ],
  "actors": [{"actor_id": "supplier"}, {"actor_id": "buyer"}],
  "issues": [{"issue_id": "unit-price"}],
  "sources": [
    {"source_id": "s1", "round_id": "r1", "actor_id": "supplier", "issue_id": "unit-price",
     "document_id": "quote_r1", "unit_id": "u01-item-a-kx",
     "char_start": 51, "char_end": 73, "quote": "Unit price: 12 EUR/box", "state": "accepted"},
    {"source_id": "s2", "round_id": "r2", "actor_id": "supplier", "issue_id": "unit-price",
     "document_id": "quote_r2", "unit_id": "u01-item-a-kx",
     "char_start": 51, "char_end": 73, "quote": "Unit price: 11 EUR/box", "state": "accepted"}
  ]
}
```

In both files the line `Unit price: ...` starts at character 51 (the title line, a blank line, the heading line, a blank line and the `Supplier` line come before it, each with its line end) and is 22 characters long, so it ends at 73.

**Fields.** An **identifier** below is 1 to 128 characters, each an ASCII letter, a digit, `_`, `-` or `.`. Every field is required except the two marked optional; `sources` is required and may be an empty list. Leave the two optional fields out: their defaults are what a test needs.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | Always `1`. |
| `case_id` | identifier | The case's own name. Make it neutral (section 1): the models are shown the case manifest, so every id in it (case, round, actor, issue, source) and every quote must reveal nothing about the flaws. |
| `fixture` | boolean | Always `false`. `true` is refused, and so is a manifest without the field (below). |
| `allow_recommendations` | boolean, optional | Whether the models may write recommendations. Default `false`. Leave it out. |
| `decision_support_mode` | string, optional | One of `trajectory_only` (the default), `decision_support`, `strategic_options`, `recommendation`. `recommendation` also needs `allow_recommendations: true`. Leave it out. |
| `rounds` | list of objects | The rounds, two or more. |
| `rounds[].round_id` | identifier | The round's name, unique in the case. |
| `rounds[].sequence` | integer | The round's place in time, 1 to 10000, unique in the case. Rounds are read in this order, not in list order. A gap (1, 3) is allowed. |
| `rounds[].document_ids` | list of identifiers | The ids of this round's documents, no repeats. A document belongs to one round only. Give every round at least one document. |
| `actors` | list of objects | The parties, one or more. Each has a unique `actor_id` (identifier). |
| `issues` | list of objects | The subjects the parties take positions on, one or more. Each has a unique `issue_id` (identifier). |
| `sources` | list of objects | The evidence spans (below). The list may be empty, but then no position can be accepted. |
| `sources[].source_id` | identifier | The span's name, unique in the case. |
| `sources[].round_id` | identifier | A declared round. |
| `sources[].actor_id` | identifier | A declared actor: whose position the span states. |
| `sources[].issue_id` | identifier | A declared issue: which subject the span is about. |
| `sources[].document_id` | identifier | A document of that same round. |
| `sources[].unit_id` | identifier | The unit the span sits in. Shimmer checks only that it is an identifier and stores it with the span. Write the unit id of section 2. |
| `sources[].char_start`, `sources[].char_end` | integers | Where the span starts and ends in the document's text (below). `0 <= char_start < char_end`. |
| `sources[].quote` | string, not empty | The exact text of the span. |
| `sources[].state` | string | Your standing for this evidence: `accepted`, `rejected`, `refused`, `unresolved`, `insufficient_evidence`, `not_comparable` or `unknown`. A position the models propose can end up `accepted` only when every span it rests on is `accepted`. Write `accepted` for every span that quotes its document exactly. The models see the states, so a state other than `accepted` on a span with a planted flaw gives the answer away: never use the state to mark a flaw. |

No other top-level field is allowed: one more field is refused. Inside rounds, actors, issues and sources, other fields are not checked and not used. Write none.

**Character positions.** `char_start` and `char_end` count characters, not bytes, from 0, in the document's text as Shimmer reads it: UTF-8 decoded, with every CRLF line end, and every lone CR, turned into LF. `char_end` is the position just after the last character. The quote must equal the text from `char_start` up to `char_end` exactly. A letter outside ASCII counts as one character, and so would a byte-order mark; keep documents ASCII and without a byte-order mark (sections 1 and 2), and count with a tool.

**The rules the manifest must meet.** A broken rule is refused with a one-line reason that names the rule, never the content:

1. The file is one JSON object whose top-level fields are among those above, with `fixture` present and set to `false`.
2. `schema_version` is 1, `case_id` is an identifier, and every optional field has an allowed value.
3. There are at least two rounds, at least one actor and at least one issue. Every id is an identifier and unique in its list.
4. Every round has a whole-number `sequence` from 1 to 10000, unique in the case, and a list of document ids with no repeats. No document belongs to two rounds.
5. Every source names a declared round, actor and issue, and a document of its own round. Its `unit_id` is an identifier, `0 <= char_start < char_end`, `quote` is not empty, and `state` is an allowed value.
6. Every document a round names is a case document of the archive.
7. Every source's quote equals its document's text between `char_start` and `char_end`.

**When the rules are checked.** On the cloud path, all seven are checked when the bundle is sealed and again at launch, against the documents exactly as the run will load them, so a broken manifest is refused before any machine starts. A run started by hand on this machine checks rules 2 to 5 at start (it then stops with an argument error and writes no run folder), refuses a fixture with exit code 8, and checks rule 7, and rule 6 for every document a source names, when it binds the spans (exit code 8). It does not check rule 1's field list. A round document that no source names and that is missing is only recorded as missing.

**Why a fixture is refused.** A **fixture** is a manifest with `fixture: true`. The repository's own fixture carries synthetic spans and model answers written in advance, and keeps its documents inside the file instead of in `context/`. A live run with answers written in advance would measure nothing. So a fixture is refused when the bundle is sealed, again at launch, and again by the run itself, which stops with exit code 8 and the reason `fixture_requires_offline_test_adapter`.

**What a multi-round run does.** This decides what a test can expect to find in the results.

- The cloud tool runs a multi-round case with fixed settings: a Review, the paired review, the two flags that declare the run non-sensitive (`--sensitivity-layer-inactive-override` and `--no-redaction-override`), English output, and the case manifest. A test cannot change them. A run with redaction on, or without both of those flags, is refused with exit code 8; a run started by hand must pass both. The two model agents used (the producer and the reviewer) must differ in both backend and model, or the run is refused with exit code 8.
- Each source span gets a REF id (section 7). The models are shown the case manifest and the spans, never the documents themselves.
- **The Python round review.** Python reviews the rounds in `sequence` order, and each round's documents, unit by unit, against the conventions, with the paired machinery of sections 2 to 5. Each round's document is paired on its own: the label universe of section 4 is that document's labels, not the case's. It computes sums, products, blank cells, bands the rule states itself, and declared absences (`[requires: ...]`). It does **not** compute, in a multi-round run: reference-table or labelled-sentence bands, date windows, the change records of section 6, or the "no rule applies" finding. A pair that needs a model (a judged absence, or a pair where nothing can be computed) is recorded as needing a model and not asked.
- **Reuse.** A unit whose own text, paired rules, document label set and document measures are all identical to a unit of an earlier round is not computed again. Its findings are copied from the earliest round that computed them, under the new unit id. A unit that moved position is still recognised, because the unit id is not part of the comparison.
- Then the producer model proposes typed position records from the spans, and the reviewer model accepts, rejects or withholds each one. Nothing in a multi-round run becomes an amendment, and the run writes no deliverables. The round findings carry the registry id of their rule, not the operator's own id. `docs/OUTPUT_FORMAT.md` describes what the run writes.

**Scoring a multi-round case.** Section 9, "Multi-round keys", gives the key: planted and clean entries scoped by round and document, scored on the Python round findings. Rename probes are measured in the ordinary two-version review of the same files (above, "The same bundle as an ordinary review"), not in a multi-round run. The repository's scorer scores neither yet.

## 13. Glossary

- **Amendment**: a proposed change to the document, made from an irregular finding under a required or recommended rule.
- **Answer key**: `answer_key.json`; it states the planted flaws and is read only by the scorer; it never travels in the test archive.
- **Band**: an allowed range for a figure, from a rule's text or a reference table; both bounds included.
- **Clean distractor**: a correct unit built to look like a flaw.
- **Clean twin**: the same bundle with every flaw repaired.
- **Computed absence**: a missing required field, decided by Python.
- **Conditional finding**: a `below_band` finding from a reference-table or labelled-sentence band that the rule qualifies (section 7); recorded, never an amendment. A band the rule states itself never gives one.
- **Conventions**: the rules in `conventions/`.
- **Date cutoff**: the repository-wide date that decides the role of a file the manifest does not name.
- **Directive**: a heading bracket whose first word is `scope`, `requires` or `unless`, followed by a colon.
- **Document under review (target)**: the file named in `targets`.
- **Earlier version (prior)**: the file named in `prior`, compared with the target.
- **Expected refusal**: a renamed term a key lists in `expected_refusals`, which a refusal or a matched rename satisfies and a withdrawal record breaks (section 9).
- **False positive**: an amendment on a unit with no planted flaw; in a negotiation-style test, a record the key does not give; in a multi-round case, an irregular round finding on a unit no planted entry names.
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
- **Test archive**: the tar file holding everything Shimmer needs to run one test (section 1).
- **Working folder**: one test kept as a folder for local runs and the repository's scorer, with the manifest inside `context/` and the key at its top (section 1).
- **Typed reason (claim)**: the relation, field label and figures of a planted flaw.
- **Unit**: the piece of a document that a rule is applied to.
- **Unit id**: `u`, a two-digit position, a hyphen, and the heading's slug.
- **Verdict**: `irregular` (a problem) or `ok` (information only).
