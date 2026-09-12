# WORDS-D: every place in this repository where meaning is decided from words

The complete list, swept across `scripts/`, `tools/`, `config/`,
`corpus_ingest/`, `maat_ingest/`, the sensitivity layer, the harness, the
server and the gate checks themselves.

**Wider than the earlier inventory.** That one looked for FIELDS inferred from
prose. This looks for DECISIONS: any place where the presence, absence or
similarity of words changes what the code does. A classification, a match, a
filter, a branch, a threshold, a suppression, a routing choice. It counts
whether or not the result is stored in a field, and whether or not anything
consumes it today.

## Method

A mechanical pass found 67 files carrying word-shaped constructs (literal word
lists, regexes of alternated words, membership tests against string literals,
lowercased comparisons): roughly 1200 raw hits. Most are **enum comparisons**
(`status in ("queued", "running")`, `backend == "local"`), which are not word
decisions at all: the vocabulary is the program's own, closed, and declared. The
list below is what survived reading each candidate.

## The three categories

**STRUCTURAL** stays as it is: declared syntax, ids, delimiters, formats,
run-id shapes, anything where text is READ rather than interpreted.

**SEMANTIC** converts to the five-voter ensemble under WORDS-A.

**REFUSES** stays as it is: a place that declines rather than guessing is
already correct and must not be converted into something that votes.

---

## STRUCTURAL (18)

| # | where | decides | words live | consumed by | wrong answer |
|---|---|---|---|---|---|
| S1 | `server._RUN_ID_RE` (7 call sites) | is this a well-formed run id | code | every run-scoped route | visible: 404 |
| S2 | `guard_secrets.*_RE` (11 patterns) | does this line hold a key | code | the pre-commit key scan | visible: a blocked commit |
| S3 | `embedding_store._TABLE_ROW_RE`, `_TABLE_SEP_RE` | is this a markdown table row | code | chunking | visible: a mangled chunk |
| S4 | `sensitivity_layer._PLACEHOLDER_RE` | is this value a typed placeholder | code | the masking rejoin | visible: an unmasked rejoin |
| S5 | `collect_baseline._PHASE_DONE_RE` etc | parse a log line's figures | code | the baseline collector | visible: a missing number |
| S6 | `convention_parser._HEADING_RULE_ID` | does this heading carry an operator id | code | attribution, `source_rule_id_for` | visible: wrong id on a finding |
| S7 | `convention_parser._DECLARATION_PREFIX` | is this a `scope:`/`requires:`/`unless:` declaration | code | the planner | visible: refused at parse |
| S8 | `convention_parser._SEVERITY_PATTERNS` bracket read | the declared severity token | code | amendment minting | visible: wrong severity |
| S9 | `document_dating._FILENAME_PATTERNS` | a date in a filename | code | the review cutoff | see R1 |
| S10 | `document_dating._TEXT_DATE_PATTERNS` | a date FORMAT in text | code | the review cutoff | see R1 |
| S11 | `adaptive_spawn._INSTITUTION_PATTERNS` | a capitalised name plus a marker noun | code | `search_router` direct fetch | visible: a bad fetch |
| S12 | `adaptive_spawn._CITATION_PATTERNS` | UN/ISO/RFC reference FORMATS | code | nothing (PRODUCE-ONLY) | none |
| S13 | `reference_tables` range/unit reading | two same-unit numbers in one cell | code | band checks | visible: a refused band |
| S14 | `pairing_map._norm_label` | tokenise a field label | code | every label comparison | visible: no pairing |
| S15 | `agent_wrapper` json fence strip | is this a ```json fence | code | envelope parsing | visible: a parse failure |
| S16 | `language_detect` | which language is this | library | model routing | visible: wrong model |
| S17 | `claim_classifier` date/currency/standard shapes | a FORMAT | code | nothing (unconsumed) | none |
| S18 | `search_router` `looks_like_api` | is this URL an API endpoint | code | fetch strategy | visible: a failed fetch |

## SEMANTIC (6)

Ordered here by WORDS-E's rule, worst first: damage and invisibility, not ease.

| # | where | decides | words live | consumed by | wrong answer | direction |
|---|---|---|---|---|---|---|
| **E1** | `sensitivity_layer.rules._REDACT_VERB_RE` + `_PROHIBITION_RE` | is this convention a redaction rule | code | the redactors, LAW-IV | **SILENT** | a false NO publishes protected content |
| **E2** | `sensitivity_layer.rules._REVIEWER_*_RE`, `_REDACTABLE_OBJECT_RE` | is this reviewer restraint rather than redaction | code | the same | **SILENT** | a false YES suppresses a redaction rule |
| **E3** | `redaction_detect` + `config/language_redaction_cues.json` | which spans are regular-shaped PII | **config** | the redactor | **SILENT** | a false NO leaves PII in the output |
| E4 | `convention_parser._ACTION_PATTERNS` | a convention's action | code | nothing on the review path | visible (marked unconsumed) | none today |
| E5 | `convention_parser._SEVERITY_PATTERNS` prose fallback | a severity suggestion | code | nothing (TWO-J retired it) | visible (marked unconsumed) | none today |
| E6 | `adaptive_spawn._SPEECH_ACT_PATTERNS` | a speech act's type | code | nothing (PRODUCE-ONLY) | none | none today |

**E1 and E2 are already converted** (TWO-K, commit `6877744`): the ensemble is
unioned with them, so both now have a second opinion that can only add
redaction. They remain listed because the regexes still run.

## REFUSES (5), and none may be converted

| # | where | why it is already correct |
|---|---|---|
| R1 | `document_dating` cascade | an undated document resolves `date_source: "unresolved"`, is reported by `unresolved_documents()`, the pipeline warns, and it costs the document its place in the review set. It declines; it does not guess. |
| R2 | `reference_tables` row matching | most specific wins, and **a tie is REFUSED rather than broken**. |
| R3 | `paired_review` prior-comparison rename | `config/rename_tolerance.json` is a numeric tolerance; anything unsettled (tie, unit mismatch, no citation, disagreeing bands) is refused on the record, never minted. |
| R4 | `relation_extract` + `config/relation_patterns.json` | the patterns are entirely operator-declared and `scripts/` holds none of its own. An empty list means no cross-reference is extracted, **an honest nothing rather than a guessed something**. |
| R5 | `semantic_ensemble.decide` | refuses when fewer than five voters can run, and names the missing ones. |

## Count

| category | count |
|---|---|
| STRUCTURAL | 18 |
| SEMANTIC | 6 (2 already converted, 3 unconsumed, 1 live and remaining) |
| REFUSES | 5 |
| **total decisions** | **29** |

Plus roughly 1200 raw hits that are enum comparisons over the program's own
closed vocabulary, which are not word decisions and are not listed.

## What WORDS-E has left to do

Of the six SEMANTIC entries, E1 and E2 are converted, and E4, E5 and E6 are
consumed by nothing and are marked as such, so a conversion would be building a
five-voter decision for a decision nobody makes.

**E3 is the one genuine remaining conversion**, and it ranks first on WORDS-E's
own criterion: it is consumed, a wrong answer is silent, and the wrong direction
leaves personal data in a delivered artifact.
