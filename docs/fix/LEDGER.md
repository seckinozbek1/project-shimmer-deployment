# Ledger: what the README must say, and what the image is behind on

Opened 2026-09-12. Kept because the operator moved the README pass and the image
rebuild to the end of a working run rather than before every commit (see README
section L, the discipline boundary at `9b4f027`). This is the record of what those
two deferred passes will have to catch up on, so neither has to be inferred from a
diff.

Two sections. **Owed before this run** is the backlog that already existed.
**This run** is appended to as each commit lands.

---

## Owed before this run started

Image last built at `139083a`. Seven commits have landed since. The image ships
`scripts/`, `config/`, `tools/` and `corpus_ingest/` only, so a commit touching
only `README.md` or `benchmark/` does not affect it.

| commit | what it changed | image affected |
|---|---|---|
| `dc6a271` | container figures recorded | no |
| `ce05cbd` | README figures pinned to their commit | no |
| `119bf60` | scorer checks a reason, not only a location; typed `claim` in the device key | **yes**: `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `015e062` | `quote` field on the contract; twin detector | **yes**: `config/agent_contracts.json`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `9b4f027` | advisory items withheld; typed amendments; deepening cap | **yes**: `scripts/agent_wrapper.py`, `scripts/paired_review.py`, `scripts/pipeline.py`, `tools/score_corpus.py`, `scripts/verify_session1.py` |
| `b17c4be` | discipline boundary named | no |
| `44e3168` | quote required on absence claims, forward only | **yes**: `scripts/paired_review.py`, `scripts/pipeline.py`, `scripts/verify_session1.py` |

**Four of the seven affect the image.** The gate total moved 228 to 234 across
them, so the container figure recorded in the README (`PASS=215 SKIP=7 FAIL=6
TOTAL=228`, measured at `139083a`) is stale by six checks and will need
remeasuring, not editing.

**README items already owed from those seven:** none. Each of the seven carried
its own README pass at the time, under the pre-`9b4f027` discipline. The boundary
starts at `9b4f027`, and `b17c4be` and `44e3168` both updated the README in the
same commit. So the backlog for the README is empty and the backlog for the image
is four commits.

---

## This run

Appended as each commit lands. Format: what the README will have to say, and
whether the image is affected.

### A prediction to be checked against a real run

The quote requirement (`44e3168`) predicts that on the next run **14 judged
absence claims** (5 on the flawed twin, 9 on the clean, from the saved pairing
maps) will either carry a quote or be refused and recorded under
`absence_refused`. The 7 computed absences are Python's own arithmetic and need
no quote.

This is a falsifiable prediction about model compliance, recorded here rather
than left in a report so the next run can be checked against it. If the model
complies, `absence_refused` stays empty and 14 findings carry quotes. If it does
not, the refused count says how often, and the refusal reason says which.

### 5496cff  Item ONE: operator verdict joined to its subject

**README will have to say:** a new durable store,
`durable/governance/operator_decisions.jsonl`, holding an operator verdict joined
to its subject; a timeout now recorded as DEFERRED rather than returned only in
memory; a sixth source, a sixth node type (`OperatorDecision`) and a sixth edge
type (`DECIDED_ON`) in the Tier-1 graph, the first edge whose source is not a
Provision and the first carrying a human judgement. Also that the tier2 literal
and the GNN node vocabulary are deliberately unchanged, and why. Gate total
moves 234 to 235.

**Image affected: YES.** `scripts/durable_paths.py`, `scripts/ontology_graph.py`,
the pipeline driver, `scripts/verify_session1.py`.

**Reasoning recorded at** `docs/fix/LEARNING_SIGNAL.md`, which the README should
point at rather than restate. Its headline for the README: the rows this
produces are not a training set (order of one DeltaProposal and zero conflicts
per run), and they are worth creating for audit and for conflict memory, not on
the argument that the GNN will learn from them.

### b146d82  Knowledge categories, and the reset hole they expose

**README will have to say:** three declared knowledge categories
(constitution-derived, rule-derived, usage-derived) with the membership test;
that `USAGE_DERIVED_PATHS` and `AUTHORITY_PATHS` in `durable_paths` are the
declared manifest and are asserted disjoint and covering; and, most importantly
for a reader, that **`--reset-snapshot` now clears `ontology/stores` as well**,
which it did not before, so the captured provisions, the Tier-1 graph and the
GNN state no longer survive a reset. That last point is a behaviour change to an
operator-facing command and belongs in the command's own documentation, not only
in a limitations note. Gate total moves 235 to 236.

**Image affected: YES.** `scripts/durable_paths.py`, `scripts/snapshot_manager.py`,
`scripts/verify_session1.py`.

**Reasoning recorded at** `docs/fix/KNOWLEDGE_CATEGORIES.md`. Its headlines for
the README: the isolation rule in concrete form (a user starts with the rules and
the constitution represented and nothing carried over from anyone's use), and the
corrected volume finding (usage-derived has the volume and lacks ground truth;
operator decisions have ground truth and lack volume; neither alone is a training
signal).

**Also records the reshaped item TWO proposal** (one relation, `[unless: <field>]`)
which is NOT yet built.

### f1f09cd  Item TWO: a rule condition points at a field AND at another rule

**README will have to say:** a third heading declaration, `[unless: <target>]`,
alongside `scope` and `requires`, with both target kinds decided from the
target's own shape; that an unrecognised declaration is now REFUSED
(`ConventionDeclarationError`) rather than absorbed as a subject tag, which is a
behaviour change an operator can hit by writing a declaration this parser does
not know; a new `unless` field on the convention registry entry; a new
`qualified_by` key in the paired payload; and a sixth graph edge type,
`QUALIFIED_BY`, the first between two Conventions. Gate total moves 236 to 237.

**Image affected: YES.** `scripts/convention_parser.py`, `scripts/paired_review.py`,
the pipeline driver, `scripts/ontology_graph.py`, `scripts/verify_session1.py`.
(`benchmark/fixtures/` is not shipped in the image.)

**Behaviour change worth calling out separately in the README:** the refusal.
Every shipped corpus was verified to still parse, but an operator's own
conventions file carrying, say, `[priority: 2]` would now stop the run where it
previously proceeded with that instruction silently reinterpreted.

---

### a499bfa  TWO-A, TWO-B, TWO-C: a usable refusal, a visible loss, a suspension that suspends

**README will have to say:** that the refusal introduced by `f1f09cd` now names
the offending declaration and LISTS the recognised ones, derived from the
parser's own regex rather than restated, and explains that `priority`,
`immutable` and `outranked_by` belong to the constitution and not to a
conventions file. An operator stopped without being told what IS allowed cannot
fix the file.

**Found while checking, and the most serious thing in this commit:** `unless`
was parsed, carried into the payload and drawn as a graph edge, and NEVER
EVALUATED. It suspended nothing at all. It now applies per unit in
`plan_calls`, so the same rule can be suspended on one entry and in force on the
next, which is what the declaration actually says. Anything that reported on the
`f1f09cd` feature before this commit was describing something inert.

**Two edges settled by registry membership rather than by shape:** a document
field literally named `conv-status` parsed as a rule condition, and is now
re-read as a field when it names no rule the registry holds; and a rule
condition naming a rule that does not exist resolves `unresolved` and NEVER
suspends, because a suspension that cannot be checked must not switch a rule off
silently.

**TWO-B:** excluding a qualified rule as a reattribution target can lose a
computed plan. That loss was counted under the generic not-judged reason, which
does not distinguish it from a rule nothing could act on. It is now named
(which rules blocked it), logged as `paired_review_reattribution_blocked`, and
carried on the not-judged entry.

**Image affected: YES.** `scripts/convention_parser.py`,
`scripts/paired_review.py`, the pipeline driver, `scripts/verify_session1.py`.
Gate total moves 236 to 237.

---

### 1721eb5  Item THREE: two rule sets, authority and information kept apart

**README will have to say:** that a second, separate rule set exists. The
operator's conventions carry AUTHORITY; a rule found outside carries only
INFORMATION. Where they do not conflict both apply; where they conflict the run
REFUSES that pair, names it and puts it to the operator, and the answer is
stored against a stable id so the same disagreement is never raised twice. An
external rule is a PROPOSAL until accepted, and acceptance records an OWNER and
is refused without one.

**This is what gives the conflict record its rows.** Item ONE joined an operator
verdict to its subject and the record had zero rows, because nothing in the
system raised a conflict. This raises them. The two were built to meet: the
answer vocabulary, the id shape and the unrecognised-answer rule are
`ontology_conflicts`' own, so one reader serves both.

**No discovery and no search, by decision.** Nothing reaches outside the
machine and no code path fetches an external rule. The only external rules in
existence are four hand-written entries in
`benchmark/fixtures/external_rules_fixture.json`, which declares itself a
fixture in its own first field and states that no real one exists. Check 238
pins that declaration, so a real rule cannot be slipped in under it.

**What counts as a conflict, deliberately narrow:** a shared declared subject
(scope plus requires, compared with the project's ONE tokeniser, so overlap is
whole-label and "Reading date" does not meet "Reading") AND a real disagreement
on severity, action, or a conditional suspension one side declares and the other
does not. Overlap plus agreement is not a conflict. Refusing more than this
would make the operator arbitrate questions nobody is asking.

**Image affected: YES.** `scripts/external_rules.py` (new),
`scripts/verify_session1.py`. Gate total moves 237 to 238.
(`benchmark/fixtures/` is not shipped in the image.)

**NOT wired into the pipeline.** The module and its gate are complete and
executed, but no pipeline phase calls `detect_external_conflicts` yet, because
there is no external rule for a real run to load. Wiring a loader that can only
ever find a fixture would be a zero-caller scaffold of the kind the gate's own
rules forbid. The decision and its reasoning are recorded here rather than left
implicit.

---

## Items still open at the end of this session

Recorded here because the working TODO does not survive the session.

**Closed this session:** ONE (both halves except the conflict rows, which travel
with THREE), TWO.

**Open, in the operator's stated order:**

- **THREE** the two rule sets: operator conventions and external rules kept
  separate, parallel application, conflict refusal put to the operator, and the
  answer stored so the same conflict is never raised twice. This is also what
  gives the conflict record its rows, so ONE is not fully closed until this is.
  Build no discovery and no search.
- **FOUR** PROCESSOR's extraction is thrown away every run. First establish
  whether paired review depends on those extractions (asked twice, never
  answered), then fix the loss.
- **FIVE** envelope-shape violations at source: strip the packaging, still refuse
  a genuinely malformed payload.
- **SIX** eight of eighteen agents never ran; say why each, and whether correct.
- **SEVEN** the scorer cannot tell not-asked from asked-and-found-nothing.
  Worsened by TWO and THREE landing, since more rules will legitimately not be
  asked.
- **EIGHT** whether the scorer surfaces a `date_window` finding.
- **NINE** whether Python now settles ROWAN by arithmetic (the prose band reader
  landed after that run).
- **TEN** the run directory cannot distinguish not-finished from
  finished-with-nothing.
- **ELEVEN** two harness parts read technically in both views.
- **TWELVE** two run_id formats.
- **THIRTEEN** the pattern behind six wrongly-passing checks: propose something
  cheap and structural.
- **FOURTEEN** whether the typed record now survives the amendment path for a
  real run, and which artifacts a scorer reads.
- **FIFTEEN** the pairing map's similarity fallback: what it catches that an
  exact match does not.
- **SIXTEEN** two checks that cannot pass in the container (analysis only, no
  container run).
- **SEVENTEEN** the image layer ordering (diagnose from records only, no
  rebuild).
- **EIGHTEEN** the payable README and image debt as one list (this file).
- **NINETEEN** decide the category of `document_dates.json` and let the manifest
  carry the ruling.
- **TWENTY** whether the GNN can learn at all: name a third source or recommend
  keeping it as a candidate finder. Answer only.
- **TWENTY-ONE** record the quote prediction where a run checks it (the
  prediction is already in this file, under "This run"; it still needs to be
  somewhere a run reads).
