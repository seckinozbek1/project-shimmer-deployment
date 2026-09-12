# What this system infers from prose keywords, and what consumes it

CLASSIFIER-A. A one-time inventory, not a fix list. The question behind it: the
same keyword table produced `severity` and `action`, and has now been shown
wrong on both, so how much of this system INFERS rather than READS?

Method: every module-level pattern table or keyword list in `scripts/` was
enumerated mechanically, then filtered to those that map PROSE to a LABEL (a
sentence splitter, a run-id shape, a key-detection regex and a markdown table
row matcher are structure, not inference, and are excluded). For each survivor,
consumption was traced rather than assumed.

## The inventory

| field | inferred by | consumed by | status |
|---|---|---|---|
| convention `severity` | `convention_parser._SEVERITY_PATTERNS` | **nothing, as of TWO-J** | retired from the decision; reported only |
| convention `action` | `convention_parser._ACTION_PATTERNS` | **nothing on the review path** | annotated `not consumed` (TWO-G); redaction now needs a DECLARED action |
| convention `category` | `convention_parser._CATEGORY_KEYWORDS` | **YES, heavily** | **the live one. See below.** |
| redaction intent | `sensitivity_layer.rules._REDACT_VERB_RE`, `_PROHIBITION_RE` | **YES** | narrowed by TWO-I; reviewer-restraint phrasing excluded |
| document date | `document_dating._TEXT_DATE_PATTERNS` | **YES** (the `content` tier) | third tier, behind filename and an explicit sidecar; refuses rather than guesses |
| institution names | `adaptive_spawn._INSTITUTION_PATTERNS` | **YES** (`search_router` direct-fetch) | live, and already documented as consumed |
| citation forms | `adaptive_spawn._CITATION_PATTERNS` | **nothing** | PRODUCE-ONLY, already labelled as such in the code |
| speech acts | `adaptive_spawn._SPEECH_ACT_PATTERNS` | **nothing** | PRODUCE-ONLY, already labelled as such in the code |
| claim kinds | `claim_classifier` (10 regexes) | **nothing: zero callers outside the gate** | dormant module; the gate is its only importer |

## The one that matters: `category`

`_CATEGORY_KEYWORDS` is the live inference, and it is the most load-bearing
field in the table. A convention's category is consumed by at least:

- `finding_record.source_rule_id_for` — attribution of a finding to the
  operator's own rule id
- `paired_review` and `pipeline` — rule matching and reattribution
- `ontology_graph` — the Convention node's category attribute
- `sensitivity_layer` (`redaction_detect`, `redaction_stage`) — the redaction
  category a span is masked under

**It is, however, already guarded, and the guard is the one CLAUDE.md names.**
The keyword table applies ONLY to a heading with no operator id. A heading that
carries the operator's own rule id keeps that id as its category and nothing
else is consulted. That guard exists because the table previously ran FIRST and
silently reclassified an operator slug containing the word "value", losing
attribution for every finding under that rule.

So the exposure is narrower than the consumption list suggests: it applies to
id-less headings only. **Measured: 0 of 44 headings across the six shipped
corpora are id-less**, so the keyword table decides nothing for any corpus that
exists today. It is reachable only by a conventions file written without rule
ids, which is a shape no shipped corpus uses.

That makes `category` the same kind of thing `severity` was before TWO-F: a
live consumer fed by an inference that nothing currently exercises. Unlike
`severity`, it is explicitly guarded and the guard has a recorded reason, so it
is listed here as measured-and-narrow rather than as an open defect.

## What the inventory shows

Nine inferred fields. Four are consumed (`category`, redaction intent, document
date, institution names), and two of those four (redaction intent, document
date) are already built to refuse rather than guess when unsure. Three were
never consumed and were already labelled as such by whoever wrote them. Two
(`severity`, `action`) were consumed or reachable and have been closed this
session.

The pattern worth naming: **every inferred field that was CONSUMED and not
explicitly guarded turned out to be wrong in a way nobody had measured.** The
three PRODUCE-ONLY assets were documented as unconsumed by their author at the
time of writing, and the two that caused trouble were not.

`claim_classifier` is a dormant module with ten prose regexes and no caller
outside the gate. It is not a hazard today, and it is the kind of thing that
becomes one the moment somebody wires it up.

## Found while working TWO-I, pre-existing, NOT fixed

`_PROHIBITION_RE` matches only the PASSIVE prohibition form. It covers
"must not be published" and does not cover the active "must not publish":

```
"The reviewer must not publish the client's address."   -> no trigger at all
"The address must not be published."                    -> triggers
```

Confirmed against `HEAD` before this session's changes, so it predates TWO-I and
was not introduced by it. The consequence is a genuine operator redaction rule
written in the active voice being silently ignored, which is the dangerous
direction.

**Not fixed here, deliberately.** Widening the prohibition regex changes what
compiles as a redaction rule, which is a change to redaction REACH under LAW-IV.
TWO-I asked me to stop review conventions becoming redaction rules, not to make
more things become them. Quietly expanding that set while closing a different
hole would be the wrong trade. Recorded for a decision.
