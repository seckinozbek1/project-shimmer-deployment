> Historical design/audit record. Current implementation and endpoint names are in the [README](../../README.md#api-and-developer-entry-points) and [routing/UI audit](../fix/ROUTING_UI_AUDIT.md). Old route counts, success wording, write-only ontology claims and success-only findings visibility below are superseded. The console now reads findings/pairs for nonqueued runs, distinguishes process completion from review quality, and shows recorded activation evidence. Rule text is current-registry data, not a historical snapshot.

# Console language: developer view and human view, side by side

Read only. No code changes here. Every developer-side string below is quoted from the
live system: `scripts/ui/console.html`'s own copy where it already exists, or the exact
field names and codes from `scripts/server.py`, `scripts/pipeline.py`,
`config/agent_contracts.json` and `scripts/finding_record.py` where it does not. Nothing
below is invented vocabulary; where the human sentence needs a fact the developer view
does not currently show on screen (the operator's own wording for a rule, the reference
band's bounds), that gap is named, not papered over.

The rule this whole document is built to satisfy: **the human view is a rewording, never
a filtering.** Every fact on the developer side appears on the human side too, in
different words. Nothing awkward is dropped.

## Findings, one per relation

The Finding record's 13 relations (`config/agent_contracts.json`, `finding_record`
schema) split into two families: nine compare two figures WITHIN this document or
against a reference table; five compare a field with the SAME field in an earlier
version of the document (`INFRA-044`, `changed_from_prior` through `absent_since_prior`).
Every example below uses the same running example unit (`u01`, a figure the document
states) so the difference in wording is the only thing changing.

### `sum_mismatch`

**Developer view (current, verbatim table row):**
> Rule: CONV-B01 · Unit: u02 · Relation: sum_mismatch · Verdict: ok · Figures: 50 EUR / 50 EUR
> Explanation: The two figures agree once currency is normalised, within the configured tolerance.

**Human view:**
> **The total checks out.** Article 4's stated total, 50 EUR, matches what its parts add
> up to, 50 EUR, within the tolerance the rule allows. *(CONV-B01 · u02)*

### `above_band`

**Developer view:**
> Rule: CONV-A02 · Unit: u01 · Relation: above_band · Verdict: irregular · Figures: 120 tonnes / 100 tonnes
> Explanation: The stated figure exceeds the reference table's upper bound for this category.

**Human view:**
> **This figure is higher than the reference table allows.** Article 2 states 120 tonnes.
> The reference table's upper bound for this category is 100 tonnes. *(CONV-A02 · u01,
> "irregular")*

### `below_band`

**Developer view (constructed from the schema; no live example on screen today):**
> Rule: CONV-A05 · Unit: u04 · Relation: below_band · Verdict: irregular · Figures: 30 tonnes / 50 tonnes
> Explanation: The stated figure falls below the reference table's lower bound for this category.

**Human view:**
> **This figure is lower than the reference table allows.** Article 6 states 30 tonnes.
> The reference table's lower bound for this category is 50 tonnes. *(CONV-A05 · u04,
> "irregular")*

### `missing_field`

**Developer view:**
> Rule: CONV-C01 · Unit: u07 · Relation: missing_field · Verdict: irregular · Figures: (none) / (none)
> Explanation: The rule requires a licence reference for this unit; none was found.

**Human view:**
> **Something the rule requires is missing.** Article 9 does not state a licence
> reference, and the rule requires one. *(CONV-C01 · u07, "irregular")*

### `product_mismatch`

**Developer view:**
> Rule: CONV-D02 · Unit: u09 · Relation: product_mismatch · Verdict: irregular · Figures: 4200 EUR / 4000 EUR
> Explanation: Quantity times unit price does not equal the stated total.

**Human view:**
> **The stated total doesn't match the calculation behind it.** Article 11 states a total
> of 4200 EUR. Quantity times unit price works out to 4000 EUR. *(CONV-D02 · u09,
> "irregular")*

### `ratio_out_of_range`

**Developer view:**
> Rule: CONV-E01 · Unit: u11 · Relation: ratio_out_of_range · Verdict: irregular · Figures: 0.62 ratio / 0.30-0.50 ratio
> Explanation: The stated ratio falls outside the range this rule permits.

**Human view:**
> **This ratio is outside the range the rule allows.** Article 13 states a ratio of 0.62.
> The rule permits 0.30 to 0.50. *(CONV-E01 · u11, "irregular")*

### `date_window`

**Developer view:**
> Rule: CONV-F03 · Unit: u14 · Relation: date_window · Verdict: irregular · Figures: 2026-11-30 / 2026-09-30
> Explanation: The stated date falls outside the window this rule requires.

**Human view:**
> **This date is outside the window the rule requires.** Article 16 states 30 November
> 2026. The rule requires a date on or before 30 September 2026. *(CONV-F03 · u14,
> "irregular")*

### `licence_missing`

**Developer view:**
> Rule: CONV-G01 · Unit: u16 · Relation: licence_missing · Verdict: irregular · Figures: (none) / (none)
> Explanation: This unit requires an accompanying licence citation; none is present.

**Human view:**
> **A required licence citation is missing.** Article 18 needs an accompanying licence
> citation, and none is present. *(CONV-G01 · u16, "irregular")*

### `changed_from_prior`

**Developer view:**
> Relation: changed_from_prior · Verdict: ok · Field: quota volume · Figures: 120 tonnes / 100 tonnes · Delta: +20 tonnes
> Explanation: This figure changed from the earlier version of the document.

**Human view:**
> **This changed since the earlier draft.** The quota volume was 100 tonnes; this version
> states 120 tonnes, an increase of 20 tonnes. This is not a problem, only a change worth
> knowing about. *(u01, compared to the earlier version)*

### `unchanged_from_prior`

**Developer view:**
> Relation: unchanged_from_prior · Verdict: ok · Field: quota volume · Figures: 100 tonnes / 100 tonnes
> Explanation: This figure is the same as the earlier version of the document.

**Human view:**
> **This is unchanged since the earlier draft.** The quota volume was 100 tonnes and
> still is. *(u01, compared to the earlier version)*

### `moved_toward`

**Developer view:**
> Relation: moved_toward · Verdict: ok · Field: quota volume · Figures: 105 tonnes / 120 tonnes · Band distance change: -5 tonnes
> Explanation: This figure moved closer to the reference band since the earlier version.

**Human view:**
> **This moved closer to what the reference table allows.** The quota volume was 120
> tonnes, now 105 tonnes: 5 tonnes closer to the band the rule states. *(u01, compared to
> the earlier version)*

### `moved_away`

**Developer view:**
> Relation: moved_away · Verdict: ok · Field: quota volume · Figures: 130 tonnes / 120 tonnes · Band distance change: +10 tonnes
> Explanation: This figure moved further from the reference band since the earlier version.

**Human view:**
> **This moved further from what the reference table allows.** The quota volume was 120
> tonnes, now 130 tonnes: 10 tonnes further from the band the rule states. This is not
> flagged as irregular by itself; it is a direction worth watching. *(u01, compared to
> the earlier version)*

### `absent_since_prior`

**Developer view:**
> Relation: absent_since_prior · Verdict: ok · Field: quota volume · Figures: (none) / 100 tonnes
> Explanation: This field was present in the earlier version and is no longer present.

**Human view:**
> **This is no longer in the document.** The earlier version stated a quota volume of
> 100 tonnes. The current version does not state one at all. *(u01, compared to the
> earlier version; this is reported as a withdrawal only when the system found nothing
> that looks like the same field renamed, see the gap noted at the end of this document)*

## Run state and outcome, all seven combinations

The developer view already carries a plain-English label and a shape (see
`CONSOLE_PLAN.md`'s state table); what it does not carry is what any of it MEANS for the
person waiting, or what they submitted. The human view adds both.

### `queued`

**Developer view:** "Queued" (hollow circle) · next-action copy: "Waiting for the run
ahead of it to finish. Nothing to do: this page updates on its own."

**Human view:** **Waiting to start.** Another review is running first; this one will
begin as soon as it finishes. Nothing to do. *(state: queued)*

### `running`

**Developer view:** "Running, phase 5.5, Convention review" (filled circle, pulsing) ·
next-action copy: "Nothing to do yet. This page updates on its own; you can leave and
come back."

**Human view:** **In progress: checking the document against the rules.** This page
updates on its own; it's fine to leave and come back. *(state: running, phase 4 of 8,
"Convention review")*

### `awaiting_approval`

**Developer view:** "Awaiting your decision" (filled circle with a ring) · body:
`pending_approval.message` verbatim, e.g. "The verification agent found a figure that
disagrees with the reference table by more than the configured tolerance. Approve
continuing with the model's reading, or deny to stop the run here." plus a raw
`unit_id`/`rule_id`/`value_a`/`value_b` table.

**Human view:** **Paused: needs your decision.** {`pending_approval.message`, unchanged:
this sentence is already written for a person, so it carries over as-is} The figure in
question is `value_a` against `value_b` in article {looked up from `unit_id`}. The review
will not continue until you answer. *(rule CONV-014, unit u07)*

### `stopped` + `succeeded`

**Developer view:** "Completed" (filled circle, mint) · next-action copy: "Finished.
Start with the findings below, or download the full archive."

**Human view:** **Finished. No problems stopped the review.** {N} findings below,
{M} of them flagged for a closer look. Download the full set, or read the findings
here first. *(state: completed)*

### `stopped` + `governance_stop`

**Developer view:** "Stopped by a rule" (filled square, peach) · detail box: code
`stopped_model_approval`, sentence "A deprecated model assignment needed operator
approval and the run's wait window closed before one was recorded." · next-action:
"Stopped by a rule. This was not an error: the pipeline refused on purpose. {sentence}"

**Human view:** **Stopped on purpose, before finishing. This is not an error.** The
system refused to keep going without a decision from the operator running it, and none
came in time. Nothing you submitted was lost; if you resubmit, the review restarts from
the beginning. *(governance code: stopped_model_approval)*

### `stopped` + `crashed`

**Developer view:** "Crashed" (filled triangle, rose) · detail box: raw
`stop_reason.detail`, e.g. "Traceback (most recent call last): File
\"scripts/pipeline.py\", line 512, in run raise RuntimeError('...')" · next-action: "The
run did not finish. See the detail below, or the full log. You can submit it again."

**Human view:** **The review stopped before it finished, because of a fault in the
system, not in your document.** Nothing you submitted was lost. You can submit it again;
if it fails the same way twice, that's worth reporting. *(the technical detail is in the
developer view and the full log, for whoever needs to diagnose it)*

### `stopped` + `timed_out`

**Developer view:** "Timed out" (filled triangle, rose, same shape and colour family as
`crashed`) · detail box: `stop_reason.detail` · next-action (currently shared with
`crashed`): "The run did not finish. See the detail below, or the full log. You can
submit it again."

**Human view:** **The review did not finish in time and was stopped.** This is a
failure, not a refusal: nothing about your document caused it to be turned away, it
simply ran longer than the system allows and had to be cut off. Nothing you submitted
was lost. You can submit it again. *(run timeout, not a governance rule: this outcome
sits with "crashed," never with "stopped by a rule," because the system did not choose
to stop on purpose here the way it does for a governance stop; it failed to finish)*

The wording matters here specifically because `timed_out` shares a shape and colour with
`crashed` (both triangle, rose) and could easily drift, in translation, toward sounding
like `governance_stop`'s language ("stopped on purpose," "refused") since both outcomes
use the word "stopped" in their state name. An earlier draft of this sentence read
"Stopped, it ran past its limit," which reads as a rule doing its job exactly like a
governance stop's "stopped by a rule" does, the one distinction this interface exists to
preserve. The corrected sentence leads with "did not finish in time," a failure verb,
and states plainly that it is not a refusal, rather than leaving the reader to infer that
from the word "stopped" alone.

### `cancelled`

**Developer view:** "Cancelled" (hollow square) · next-action: "Cancelled: {detail}."
where detail is one of exactly two server-supplied strings, "cancelled before it
started" or "cancelled while running."

**Human view:** **Cancelled, at your request.** {"It had not started yet." / "It had
already begun; whatever finished before the cancellation is still available below."}
*(state: cancelled)*

## A run identifier

**Developer view:** `20260910_140000__f19d01`

**Human view:** **{first submitted filename}, submitted 10 September 2026, 14:00.**
*(20260910_140000__f19d01)*. The identifier stays visible, smaller, next to the name,
because a reviewer citing this run to someone else needs the exact reference, not the
friendly name.

If more than one file was submitted (`files` can hold several), the human name reads
**"{first filename} and {N-1} more, submitted ..."**, since a run is one submission with
possibly several documents, not one document.

A `task=draft` run has no uploaded file at all (the memo comes from a question, not a
document); its name is the question itself, truncated if long: **"{question, truncated
to about 60 characters}, submitted 10 September 2026, 14:00."** *(20260910_140000__f19d01)*

**The name is available from the first moment, not once the pipeline reports something.**
The corrected first draft of this document hedged with "or 'a document' if none is on
record," which was wrong to write: `POST /submit`'s own handler captures the uploaded
filenames (`files`) or, for a draft run with no upload, the question text (`question`)
synchronously, before the job is even queued (`server.py:1339-1418`), and both are
already part of `_STATUS_FIELDS`, already returned by `GET /runs` and
`GET /runs/{run_id}` in every state including `queued`. Validation guarantees one of the
two is always present (`task=review` requires at least one file, `task=draft` requires a
question, `server.py:1341-1344`), so there is no submission this route accepts that
lacks a name to show. No server change was needed here: the field was already captured
and already served: the console template was the only thing that needed correcting, not
the server.

## A phase label

**Developer view:** `phase=5.5/9` → rendered today as "phase 5.5, Convention review"

**Human view:** **"Checking the document against the rules"** (still paired with its
position, "step 4 of 8," since a reader waiting a long time benefits from knowing there
IS a fixed number of steps, just not the code's own numbering for them.) The full set,
developer phase number retained beside each because it is already a short, stable
label a person could search a log for:

| Code | Developer label (current) | Human label |
|---|---|---|
| 1 | Situation assessment | Reading the document and understanding what it covers |
| 3 | Content production | (internal drafting step; see the gap noted below) |
| 5 | Verification & fact-check | Checking facts and figures for internal consistency |
| 5.5 | Convention review | Checking the document against the rules |
| 6 | Synthesis | Putting the findings together |
| 6.5 | Editorial review | A second pass over the findings for quality |
| 7 | Audit synthesis | Preparing the final summary and record |
| 9 | Redaction screening | Checking for anything that should stay private |

## A crash

Already translated above under "stopped + crashed." Repeated here because the brief
names it explicitly: the developer view's raw Python traceback (file, line number,
exception class, message) never appears in the human view at all. The human view states
three things and stops: the review did not finish, nothing submitted was lost, resubmit
is available. The traceback, the exit code, and the "view full log" link stay exactly
where they are, in the developer view.

## A governance stop

Already translated above under "stopped + governance_stop." The two things the human
sentence must never do: call it an error (the developer copy already gets this right and
the human copy keeps it), and go so vague that the reader can't tell one governance code
from another if they ever need to compare two stopped runs. That's why the human view
keeps the code in parentheses, the same way the identifier stays beside the friendly run
name.

## A pending approval

Already translated above under "awaiting_approval." The one real change from the
developer view: `pending_approval.payload`'s raw key/value table (`unit_id`, `rule_id`,
`value_a`, `value_b`) is folded into the sentence rather than shown as a second, separate
block, because a reviewer deciding Approve/Deny needs to read one coherent statement of
the disagreement, not reassemble it from a table the way a finding's table row makes them
do today.

## A partial archive

**Developer view:** button label "Download partial archive" · note: "This run did not
finish successfully: the archive contains only the documents that completed."

**Human view:** **Download what's finished so far.** This review did not complete, so
some documents may be missing from this download. *(nothing else changes: the button
label itself is already close to plain language and needed only a small softening of
"did not finish successfully," which is accurate but reads as a verdict on the reviewer
rather than on the run)*

---

## Where the switch lives, and why

**In the masthead, as a labeled two-position control (Reviewer / Developer), next to the
run-state indicator, remembered in the same `sessionStorage` the token already uses (a
separate key, `shimmer_console_view`, so clearing one does not clear the other).**

Reasoning:

- It has to be visible on every screen, not just the run list, because a reviewer who
  drills into a governance stop or a crash is exactly the moment they most need to
  confirm which vocabulary they're reading. A page-local toggle (only on the run detail
  view, say) would leave the run list itself always in one language, which breaks "the
  interface says plainly which view is showing" for half the interface.
- The masthead is the one element that is "structural and constant... the same dark
  band, in the same place, on every view" (`CONSOLE_PLAN.md`'s own boldness section).
  Putting the switch there costs nothing in visual weight the masthead doesn't already
  spend, and it means the switch is never buried inside a screen the reviewer has to
  scroll to find.
- `sessionStorage`, not `localStorage`, for the same reason the token uses it: this
  console has no login and no per-user account, so "remembered between visits" here
  means the same tab across reloads, which is exactly what `sessionStorage` already
  gives the token. A person who always uses the human view will not need to reset it
  every reload; a person who closes the tab and returns starts from the default again,
  which is the correct default (see below), not a loss.
- **The default is the human view on every first load, unconditionally**, per the
  brief. This needs stating plainly because it is a real reversal of how the token
  works: the token has no default (the page is unusable without one), but the view does,
  and that default is fixed, not learned from whether a token happens to already be
  saved. A developer opening the console for the first time also sees the human view
  first and switches deliberately, which is the correct behavior for a page that a
  reviewer might also open at that same URL.

## What I decided about the token control, and why

**Move it out of the masthead into its own small screen, reached by a persistent but
quiet "Not signed in" / "Signed in" link in the masthead's own corner, not a text input
sitting there permanently.**

Reasoning:

- The brief's own observation is correct and I should not talk around it: a reviewer
  enters the token once, and it then does nothing for the rest of the session except
  compete for space with everything else in the masthead, which is exactly what forced
  the narrow-screen wrapping fix earlier in this project. A control used once per
  session-open does not earn a permanent input box on every screen.
- It cannot disappear entirely, though, for two real reasons the current design already
  had to solve: `sessionStorage` clears on tab close (so a person WILL need to re-enter
  it, just not every screen), and the console has no login flow to redirect to, so
  there must always be a way back to the entry screen without reloading the page from
  a bookmark.
- The masthead keeps a link, not a field: "Not signed in" when there's no token (styled
  quietly, not as an error, since an unentered token on first load is not a fault), or
  "Signed in" once one is saved. Clicking either opens the same small entry screen the
  console already has for the no-token state (`renderNeedsToken()` already exists and
  is exactly this screen; it becomes reachable at will instead of only automatically).
  This keeps the masthead's committed real estate down to a single short link instead of
  an input, a button, and a status span, which is the entire crowding problem named in
  the brief, solved by removing the input from the masthead rather than by shrinking it
  further.
- This also reads correctly for the developer view, which needs the token exactly as
  often (once per tab) and gets no separate treatment: the same link, the same screen,
  in both views.

## What I could not translate without losing meaning

- **`absent_since_prior`'s own uncertainty.** The developer view already refuses to mint
  this relation outright when a renamed-not-removed field is detected within tolerance
  (the CLAUDE.md-documented rename-tolerance guard); when it DOES fire, it is asserting
  "this is gone," not "this might be gone." The human sentence above states that
  plainly and correctly, but I could not find a way to also carry, in one sentence, that
  the system already tried and failed to find a renamed twin before concluding this. I
  added a parenthetical rather than either dropping the nuance or bloating the primary
  sentence with a caveat about the system's own internal check; a full second sentence
  for that nuance may be the more honest fix, and that's a real decision for the plan,
  not something I should silently pick.
- **Phase 3 and phase 7 ("Content production," "Audit synthesis").** I could find no
  screen-facing copy anywhere in the current console, and no operator-facing sentence in
  `pipeline.py`'s own comments, that states in plain terms what phase 3 does for the
  document under review (the closest is `pipeline.py`'s internal description of what the
  agents in that phase produce, which is itself pipeline-internal language: "content
  production" for a REVIEW task, not a DRAFT task, is confusing on its face, since
  review mode does not produce new document content in the reviewer-facing sense at
  all). My placeholder above is a reasonable guess, not a grounded translation, and I am
  flagging it rather than presenting it as settled: this phase's actual reviewer-facing
  meaning needs to come from you or from tracing what PROCESSOR actually does to a
  document under `--task review` specifically, which this pass did not do.
- **The reference band's bounds, for `above_band`/`below_band`/`ratio_out_of_range`.**
  The developer view already shows both figures (`value_a`, `value_b`) so the human
  sentence above can state them directly with no loss. But the RULE's own wording (what
  the operator actually wrote in `review_conventions.md` for CONV-A02, versus its
  registry id) is not visible anywhere in the console today, developer or human. The
  brief asks for "the rule in the operator's own words rather than its identifier";
  `source_rule_id` gets the console halfway there (the operator's OWN ID, not the
  registry's renumbered one), but the operator's own SENTENCE for the rule is not part
  of any Finding record or any route response I found, only in the convention registry
  file itself. Surfacing rule TEXT, not just the two ids, needs either a new field on
  the Finding record or a new route reading the registry by rule id, and that is a real
  scope decision, not a wording one, named here rather than assumed.
