# STEP CONVASSIGN 1 REPORT: the parser change

The first of four commits in the operator-approved convention assignment build, per the
order given with the ten answers: parser change, then assignment, then W3, then the harness
regeneration. This commit is the parser change alone: bracket subject tags, severity read
from the same bracket (answer 4, deliberately kept in this one commit rather than split
further, since both come from the same bracket scan and the operator's own instruction was
to separate the severity fix from the ASSIGNMENT commit, not from the tag-reading commit),
and the preamble defect (answer 10, explicitly required to land in the same change as the
parser work since it is the source of the phantom rules in the W6 pair count).

## What changed, precisely

`scripts/convention_parser.py`:

- `ConventionRule` gains a `subjects: list` field (default `[]`), written by `as_dict`.
- A new bracket scanner, `_HEADING_BRACKET` (`re.compile(r"\[([^\[\]]+)\]")`) and
  `_heading_bracket_tags(heading)`: every `[...]` on a heading is read structurally. A
  token equal to one of this module's own three severity labels
  (`_SEVERITY_LABELS = frozenset(label for label, _rx in _SEVERITY_PATTERNS)`, i.e.
  `required`/`recommended`/`advisory`, the names the parser already knew) sets that rule's
  severity directly, overriding the text classification; every other token is the
  operator's own subject tag, lowercased, order preserved, duplicates dropped. No subject
  vocabulary is declared anywhere: the module learns the bracket SHAPE and the three words
  it already had, nothing else.
- `_parse_text_lines` threads `current_severity`/`current_subjects` state alongside
  `current_category`, set from `_heading_bracket_tags(line)` at every heading. `flush()`
  and the list-item branch now apply that severity as an override
  (`severity or _classify_severity(joined)`) and carry `subjects` onto every
  `ConventionRule` they mint.
- **The preamble fix**: a new `before_first_operator_heading` flag, true until the first
  heading whose `_normalize_category` result matches `_HEADING_RULE_ID` (an operator id).
  While true, a flushed PARAGRAPH is preamble prose, not a rule, and is dropped. A LIST
  ITEM is never suppressed by this flag, regardless of position, since an operator who
  writes a list item plainly means it as a rule. This is narrower than my first two
  attempts (see "what I got wrong," below) and is the version that survives every real
  corpus and the gate's own seed text.
- `_parse_json` reads an optional `subjects` list per item, lowercased, defaulting to `[]`.

## What I got wrong before landing this, traced honestly

Two real design errors, found by testing against real files rather than trusting the
design doc's own diagnosis at face value, per this codebase's own discipline (read-only
trace before any structural change; every claim proven, not assumed).

**First attempt**: suppress any paragraph flushed while `current_section == "preamble"`,
the parser's own initial state string. This never fires on `device_conventions.md`,
because that file's very first line IS a markdown heading (`# Review conventions:
fleet monitoring log entries`), which immediately overwrites `current_section` away from
`"preamble"` before any prose is ever flushed. Caught by a synthetic test reproducing the
real file's shape; the two prose paragraphs still minted as CONV-001/CONV-002.

**Second attempt**: suppress any paragraph under the file's FIRST heading, unconditionally
(`in_title_section = not seen_any_heading`). This fixed the device corpus, but broke
`check_32_convention_parser`'s own seed text, whose first heading is `# Terminology`, an
id-less but genuinely rule-bearing section with two list items directly under it: my
change suppressed both, since the list-item branch also checked `not in_title_section`.
The gate did not catch this (`check_32` only asserts `ids` and `severities` are
non-empty, not the rule count, so 1 rule where 3 were expected still nominally "passed"),
found only by a direct synthetic re-run of the exact seed text.

**Landed version**: suppress a paragraph only while no heading carrying the operator's own
id has appeared yet, and never suppress a list item at all. This is the version proven
against all three shapes: the device corpus (prose before the first `CONV-D01` heading,
suppressed), the gate's own seed (an id-less heading with list items, unaffected), and a
mid-file id-less heading appearing AFTER a real operator-id heading (not suppressed, since
by then an operator id has already appeared and the file is past its title).

## Proof against every shipped corpus, not only the one corpus the design doc traced

| corpus | rules before | rules after | note |
|---|---|---|---|
| `device_log_review` | 10 | 8 | 2 phantom preamble rules (CONV-001/CONV-002, category `review`) removed |
| `device_log_review_clean` | 10 | 8 | same fix, same corpus shape |
| `catalogue_records` | 7 | 7 | first heading already carries an operator id; unaffected |
| `clinical_reference` | 5 | 5 | unaffected |
| `negotiation_r2_to_r3` | 8 | 8 | unaffected; this corpus's headings carry no brackets at all, confirming the change is inert with nothing to read |
| `negotiation_r3_to_r4` | 8 | 8 | unaffected |

Every one of `device_log_review`'s 8 real rules now carries `severity: required`, matching
every heading's own `[required]` tag exactly (previously CONV-006, heading `CONV-D03
[required]`, was recorded `advisory` because its paragraph text carries no severity word).
No corpus's operator-id detection (`_HEADING_RULE_ID`, the R6 fresh-eyes fix) is affected:
confirmed directly, `_normalize_category("## CONV-Q07 , conv-value-in-range [required]
[conformance]")` still returns `conv-q07`, unaffected by the bracket read.

Consequence for W6, recorded per answer 1: the shipped `device_log_review` corpus carries
no bracket subject tags yet (every heading in the source file has only `[required]`, no
subject token), so this change alone does not affect W6's pairing shape or call count at
all. Tagging that corpus, and re-measuring, is separate work the operator named
explicitly: "the W1 measurement corpus needs tagging before W6 can measure the new call
count." Not done in this commit.

## Gate check 197

`check_197_convention_heading_brackets_read_subject_and_severity`, added to
`scripts/verify_session1.py`. Three sites, each against real code:

1. A synthetic heading set covering multiple tags, a single tag, and no bracket at all,
   confirming severity override, subject capture, and the fallback path all work and that
   the title's prose paragraph is dropped while its own `## CONV-*` rules are not.
2. `check_32`'s own exact seed shape (an id-less first heading with two list items),
   confirming the fix does not touch it, run directly against the real
   `convention_parser` module rather than asserted from the design doc's description.
3. The real `benchmark/corpora/device_log_review/conventions/device_conventions.md` file
   on disk: 8 rules (not 10), CONV-D03 reads `required` (not `advisory`), no rule carries
   category `review` (the phantom-preamble signature).

Neutralise and restore: `convention_parser._HEADING_BRACKET` is replaced with a regex
that matches nothing, the real corpus file is re-parsed, and CONV-D03's severity is
confirmed to fall back to `advisory` (the pre-fix behavior); restored, `required` returns.
This proves the check inspects the live bracket-reading code path, not a cached
assumption about its output.

## README

Section E (conventions) updated: the bracket-tag mechanism (severity override, subject
capture), and that the parser's title heading is never itself a rule section.

## Gate result

`PASS=196 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=198`, up from the prior commit's `PASS=195
TOTAL=197` by exactly one check (197), zero regressions. Same two pre-existing failures as
every step this chain: check 01 (`missing dirs: ['prompts', 'snapshots']`) and check 145
(`tests/fixtures/planted_figure_hashes.json is missing`).

## What this does not do

No `subjects` value is written into `config/agent_registry.json` yet (that is the
assignment commit). No consumer reads `ConventionRule.subjects` yet; it is carried, not
acted on. No shipped corpus's `.md` file was edited to add a bracket subject tag; only the
parser that would read one, if written, changed. `config/convention_registry.json` itself
is regenerated at the next BOOT and is gitignored, so no stale copy needed updating.

## Things found on the way, not fixed here (per the operator's own instruction)

Recorded again, unchanged from the design document, not touched in this commit: two em
dashes in `config/agent_registry.json:127` (EDITOR_DG's first `does` entry); the missing
`previous_domain` vocabulary family in `config/domain_vocabulary.json`, referenced by a
comment and by `verify_session1._previous_domain_pattern` but never declared; and the
unkept genesis Section C promise of a category filter for STYLE_GUARDIAN.

---

STEP CONVASSIGN 1 COMPLETE (parser: bracket tags, severity-from-bracket, preamble fix;
gate check 197; README current; proven against every shipped corpus)
