# WORDS-B: the inventory converted, one field at a time

Per field: what decides it today, what decides it after, the measurement on the
44 shipped rules, and how many rules change behaviour.

---

## The four consumed fields

### 1. `category` (CLASSIFIER-B) - VERDICT: DELETE THE INFERENCE

**Today:** `_CATEGORY_KEYWORDS`, a seven-bucket English keyword table, applied to
a heading with NO operator rule id. A heading that carries an id keeps it
verbatim and the table is not consulted.

**After:** the table is deleted. A heading with no rule id keeps its own first
word, which is read rather than interpreted.

**Measurement on the 44:** the table fires on **0 of 44**. Every shipped heading
carries an operator rule id, so it decided nothing for any corpus that exists.
Two further defects found while measuring:

- **order-dependent and not self-consistent.** `"Borrowing and attribution"`
  returned `citation_style`, not `borrowing`, because whichever dict key came
  first won.
- **the original defect survived in the no-id path.** `"Naming and values"`
  returned `value_alignment`, the ethics bucket, by the same "value" match that
  once lost attribution for an entire corpus.

**Why deleted rather than converted:** converting would build a five-voter
decision, against reference text nobody has written, for a decision nothing
makes. Deleting replaces a wrong answer with the operator's own word.

**Rules changing behaviour: 0 of 44.** Verified: all 44 still parse, every
category identical. The two example headings above now return `borrowing` and
`naming`, both strictly better than before.

### 2. redaction intent - VERDICT: CONVERTED (TWO-K, commit 6877744)

**Today:** four triggers, unioned. Keyword category, redaction phrasing,
DECLARED action, and the five-voter ensemble.

**Measurement on the 44:** 0 of 44 compile as redaction intent, before or after.

**Rules changing behaviour: 0 of 44.**

### 3. document date - VERDICT: REFUSES, LEAVE IT

**Today:** a four-tier cascade (sidecar, filename, content, metadata) over
numeric and calendar-format patterns.

**Why it is not converted, on two independent grounds:**

- **it is STRUCTURAL, not semantic.** `_TEXT_DATE_PATTERNS` matches date
  FORMATS: `2026-09-12`, `12 September 2026`, `09/12/2026`. It reads a format,
  it does not interpret meaning. Regex keeps everything structural.
- **it already REFUSES.** An undated document resolves `date_source:
  "unresolved"`, is reported by `unresolved_documents()`, the pipeline warns,
  and it costs the document its place in the review set. WORDS-D's rule is
  explicit: a place that declines rather than guessing is already correct and
  must not be converted into something that votes.

**Rules changing behaviour: 0.** Nothing touched.

### 4. institution names - VERDICT: STRUCTURAL, LEAVE IT

**Today:** `_INSTITUTION_PATTERNS`, capitalised multi-word names ending in a
marker noun (Council, Commission, Agency, Ministry), plus a standalone-acronym
shape.

**Why it is not converted:** it matches a NAME SHAPE, not a meaning:
capitalisation, word count, and a suffix. It is the same kind of reading as a
run-id pattern. It also hardcodes no institution, by deliberate design, so the
domain-agnosticism rule is already satisfied.

**Rules changing behaviour: 0.** Nothing touched.

---

## The five unconsumed fields

An unconsumed inferred field reads like a decision and is not one. One verdict
each.

### 5. `severity` - VERDICT: KEEP, MARKED UNCONSUMED (and see WORDS-C)

Retired from the decision in TWO-J: computed, reported, and marked
`prose_suggestion_consumed: False`. **Not rebuilt as an ensemble, by WORDS-C's
standing rule:** 28 of 28 declared severities are `required`, so there is no
negative example to calibrate any voter against, and five methods fitted on one
label are right by constant exactly as the keyword table was. It stays retired
until a corpus holds a rule that is genuinely not required, and writing that is
the operator's job.

### 6. `action` - VERDICT: KEEP, MARKED UNCONSUMED (TWO-G)

Every registry entry carries `action_status` saying plainly that it is not
consumed on the review path. It is kept because several display surfaces render
it and because the sensitivity layer consumes a DECLARED action, which is a
different field reached by a different path.

### 7. citation forms - VERDICT: KEEP, ALREADY MARKED UNCONSUMED

`adaptive_spawn._CITATION_PATTERNS` spawns `durable/learnings/
citation_convention.json`. Its author labelled it PRODUCE-ONLY in the code, at
the call site, before this sweep existed. Also largely STRUCTURAL: UN document
symbols, ISO/IEC/RFC references, and similar are formats.

### 8. speech acts - VERDICT: KEEP, ALREADY MARKED UNCONSUMED

`adaptive_spawn._SPEECH_ACT_PATTERNS`, same call site, same PRODUCE-ONLY label
by the same author. Genuinely semantic, and genuinely consumed by nothing.
**If it is ever wired to a consumer it converts under WORDS-A first**, and that
is recorded here so the next person does not have to rediscover it.

### 9. claim kinds - VERDICT: KEEP, MARK IT UNCONSUMED

`claim_classifier` holds ten prose regexes and has **zero callers outside the
gate**. Unlike 7 and 8 it carried no marking at all, so a reader would take it
for live machinery. Marked now.

**Not deleted**, deliberately, and this is the conservative direction: it is a
whole module with a gate check exercising it, and deleting a module to tidy an
inventory is a wider change than this item asks for. Marked, recorded, and left
for the operator to remove if they want it gone.

---

## Count

| verdict | fields |
|---|---|
| converted to the ensemble | 1 (redaction intent) |
| inference deleted | 1 (category) |
| structural, left alone | 2 (document date, institution names) |
| refuses, left alone | 1 (document date, same field, both grounds) |
| kept and marked unconsumed | 5 (severity, action, citation forms, speech acts, claim kinds) |

**Total rules changing behaviour across all nine fields: 0 of 44.**
