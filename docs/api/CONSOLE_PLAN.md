> Historical design/audit record. Current implementation and endpoint names are in the [README](../../README.md#api-and-developer-entry-points) and [routing/UI audit](../fix/ROUTING_UI_AUDIT.md). Old route counts, success wording, write-only ontology claims and success-only findings visibility below are superseded. The console now reads findings/pairs for nonqueued runs, distinguishes process completion from review quality, and shows recorded activation evidence. Rule text is current-registry data, not a historical snapshot.

# Console design plan (proposed, not built)

Read only. No code exists yet. This document is the design pass the operator asked to
see before any HTML is written. It is grounded entirely in the live routes in
`scripts/server.py` on this branch (`console`, branched from `api` at `9fbe050`): every
field name, status code, and response shape cited below was read directly from that
file, not assumed. Where the API cannot honestly support something the brief asks for,
that gap is named rather than papered over.

## What this is for, restated so the design decisions below can be checked against it

A review desk, not a dashboard. A person submits documents, a governed pipeline checks
them against operator-written rules, and the output is findings tied to a rule and a
source passage. The interface's job: make legible what was checked, what was found,
what was refused, and why. One reviewer at a time, professional context, most of the
session spent waiting on a run that takes 18-60 minutes locally.

## The palette (revised: six total, not nine)

The operator does not have `project_shimmer_cover.png` in this snapshot repository (it
is excluded from what was copied into the public deployment, confirmed by its absence
here), so this palette is built from the operator's own written description: lavender,
periwinkle, mint, pale peach, rose, on black, heavily desaturated, rather than sampled
from pixels I cannot see. Named here as the ground truth for the build; if the actual
file is available when this is implemented, worth a five-minute check that these read as
plausible desaturations of it, but the file was not available for this pass.

**The ground is not fully black (see the revised masthead decision below)** for how the
cover's own black-and-iridescent identity is kept without making the whole reading
surface dark.

The first draft named nine tokens: three in the grey family (`ink`, `paper`, `rule`) plus
a fourth neutral (`quiet`) doing a grey's job under a fifth name, and six hues where two
pairs did not need to be visually distinct hues at all. Cut to six, by two real
decisions, not by softening the distinctions:

1. **One grey family, not three.** `--rule` (hairlines) and `--quiet` (queued/cancelled)
   were both just muted derivations of `--ink` wearing separate names. Hairlines and the
   neutral "nothing is happening" states are now `--ink` at a fixed low opacity
   (`rgba(28, 27, 31, 0.14)` for hairlines, `rgba(28, 27, 31, 0.55)` for the
   queued/cancelled dot and label): one chosen hue, two computed derivations, not three
   chosen hexes. This loses nothing: a hairline was never meant to carry its own meaning
   distinct from "this is structure, not content," and queued/cancelled are genuinely
   the two states where nothing is being asserted about the run, a neutral tint of the
   text colour itself is the correct way to say that, not a fourth named grey.
2. **`--lavender` (awaiting-approval) folds into `--periwinkle` (running).** Both were
   "something is in progress" states in the same cool blue-violet family to begin with;
   the first draft split them into two hues mainly because two hues were available, not
   because the meaning required it. The distinction between "running, nothing to do" and
   "waiting on you specifically" is exactly the kind of thing shape and text should
   carry, not colour: the plan already uses shape to keep governance-stop and crashed
   apart (a square vs. a triangle) for precisely this reason, so the same principle now
   applies here: running is a filled circle, awaiting-approval is a filled circle with a
   ring around it (still `--periwinkle`, same hue, a second visual cue layered on, never
   a second name). This is consistent with the plan's own stated rule that colour is
   reinforcement and shape+text carry the meaning: applying it here removes a token
   instead of adding one.

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#1C1B1F` | Primary text; also the source for the two computed neutrals (hairlines and queued/cancelled) via opacity, so no separate grey hex is chosen. |
| `--paper` | `#FBFAF8` | Page background for the reading surface (the working page below the masthead, see the revised layout section). Warm-neutral off-white, closer to uncoated paper than to pure `#FFF` or to Anthropic's `#F4F1EA` cream (checked directly against that hex to confirm this is visibly different). |
| `--periwinkle` | `#5E7AA0` | State: **running**, and (same hue, ringed shape) **awaiting a decision**. Cool blue-violet, calm, "something is in motion." |
| `--mint` | `#4B8272` | Outcome: **completed / succeeded**. Desaturated toward teal, not a bright SaaS green, so it reads as "correct" rather than "celebratory." |
| `--peach` | `#B8804A` | Outcome: **governance stop**. The one the brief calls out by name: a run stopped by a rule is not an error. Peach/ochre sits nowhere near the red family: "attention, by design," not "something broke." The palette's one deliberately-argued colour; see the boldness section. |
| `--rose` | `#A8495A` | Outcome: **crashed / timed out**. The only hue pushed toward true alarm-adjacent territory, and still muted: a crash is worse than a governance stop, and the two must never share a colour family. |

Six named hex values, exactly at the top of the requested range, all of them doing real
work: two structural (ink, paper), four meaning (periwinkle, mint, peach, rose). Every
distinction the brief asked for, running vs. awaiting vs. succeeded vs.
governance-stopped vs. crashed vs. queued/cancelled, six real states, still exists;
three of those six are now carried by shape and text on a shared hue rather than by a
seventh, eighth, and ninth named colour.

## Typography (revised: vendored, not system)

**Decision, reversed from the first draft: vendor a real typeface.** The system-stack
argument was technically sound and reached the wrong conclusion: a system stack means
the console looks different on every machine (Segoe on Windows, San Francisco on a Mac,
something else on Linux), which is the opposite of what the named institutions do. WIPO
and WEF carry their own type across every surface; that consistency is part of why they
read as serious, not an incidental style choice. The "offline" framing that made
vendoring sound costly does not apply either: a font file sits inside the built image and
needs no network at runtime, same as the two Python model checkpoints this project
already bakes in under `BAKE_WEIGHTS`. Vendoring is copying a file, not adding a
dependency.

**Chosen: [Public Sans](https://github.com/uswds/public-sans), version 2.001.** Built by
the U.S. General Services Administration's design system (18F/USWDS) specifically as a
neutral, institutional typeface for federal government digital products, deliberately
engineered to carry no personality of its own, which is the correct register here: not
a corporate brand face (ruled out IBM Plex for this reason, which carries IBM's own
identity), not an editorial serif (ruled out Source Serif / Newsreader, see below), a
face built by an institution, for institutions, to look the same everywhere. It is a fork
of Libre Franklin, a grotesque sans in the Univers/Helvetica register the brief already
asks for, not the humanist or rounded territory it rules out.

**Licence: SIL Open Font License, Version 1.1**, with GSA's own modifications
additionally released as CC0 (the more restrictive OFL terms govern the combined work in
practice, per the project's own `LICENSE.md`, fetched and vendored alongside the font
files). OFL explicitly permits bundling, embedding, and redistribution; no attribution
requirement beyond keeping the licence file, which this plan vendors verbatim.

**Files, fetched from the tagged `v2.001` release and verified (WOFF2 magic bytes
checked directly, not assumed from the file extension) before being placed in the
repository:**

- `scripts/ui/fonts/PublicSans-Regular.woff2` (33,612 bytes)
- `scripts/ui/fonts/PublicSans-SemiBold.woff2` (33,636 bytes)
- `scripts/ui/fonts/PublicSans-LICENSE.md` (the project's full licence file, fetched
  verbatim from the same tag)

Two static weights, not the variable font: Public Sans ships its variable axis only as a
`.ttf` in this release (no variable `.woff2`), and a `.ttf` is markedly larger than a
weight-subset `.woff2` for the two weights this design actually uses. Two static files
at ~33KB each is a smaller total footprint than one variable file, for the two weights
the design calls for (Regular for body/UI text, SemiBold for headings, state labels, and
emphasis, no bold, no italic anywhere in this design, so nothing else is fetched).

**System fallback, for the case the file fails to load, not as the design target:**
`"Public Sans", -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif`. The
design is drawn for Public Sans; the fallback chain exists so a missing or corrupted
font file degrades to something in the same register rather than the browser's serif
default, but every spacing and sizing decision in this plan is made for Public Sans's
actual metrics, not for whatever the fallback happens to render as.

- **Numerals and identifiers**: `ui-monospace, "Cascadia Code", "SF Mono", Consolas,
  monospace`, used ONLY for run IDs, rule IDs, byte-exact figures (`value_a`/`value_b`
  with units), and the log stream. Never for a label or a heading (the brief's own
  warning: monospace-for-technical-flavour is a tell). This one stays a system stack,
  deliberately: vendoring a monospace face for a handful of numeric columns is exactly
  the "second family for contrast, not for a reason" the brief warns against, and every
  platform's default monospace is legible enough for aligned digits and hex-suffixed run
  IDs.
- No serif anywhere. A serif was the first instinct for "institutional register" and is
  one of the things rewritten out, see the self-review at the end of this document,
  which now also records the reversal on vendoring itself.

## Layout concept (revised: a dark masthead over a light working surface)

**The identity question, resolved.** The cover art is iridescent on black, and that is
the project's identity, but a wholly dark console was already ruled out in the first
draft, correctly, for reasons that still stand (sustained reading comfort, and the
register of a printed institutional document rather than a terminal). The correction:
those two things are not actually in tension. A dark masthead, a fixed band across the
top of every view, black or near-black ground, carrying the project name and the five
meaning-hues at small scale as the only place they are allowed to appear together, puts
the identity where a person sees it once per view and then reads past it, while the
actual reading surface below stays `--paper`. This is not a compromise invented to
satisfy the request: it is the same pattern the named institutions themselves use, a
dark or coloured header band carrying the mark, white content beneath. Worth naming
where the analogy is imperfect: a UN-family masthead usually carries a wordmark or seal,
which this project has no equivalent of yet (no logo file exists in this repository); the
masthead here carries the project name in the vendored SemiBold and, in the run-detail
view only, the current run's state token, rendered against the dark ground rather than
the light one, which turns out to be a genuine improvement over a wholly light page, not
just an identity concession: the single most important piece of information on the
working view (is this run running, waiting on you, or finished, and if finished, how)
now sits in the one place that's visually constant across every scroll position, in the
one place on the page dark enough for the five hues to read at full, undesaturated
intensity against black, closer to how they'd read against the actual cover art, while
the reading surface below stays calm and light for the findings, the pairing map, and
the log, which is where sustained reading actually happens.

A strict grid, generous margins, one column of real content width (not full-bleed) on
anything wider than a narrow screen, closer to a printed page's measure than to an
app's edge-to-edge panel, governs the light surface below the masthead. Structural
elements (the run list, the phase ladder, the findings table) are ruled with hairlines
(`border: 1px solid` the computed `--ink`-at-14%-opacity token, see the palette
revision above), never shadowed cards, never `box-shadow`. No border-radius above 2px
anywhere except the state pills themselves (a deliberate, small, singular exception,
see boldness below); table cells, panels, and buttons are square-cornered, because a
uniform 8-12px radius on every element regardless of what it is is exactly the tell the
brief names.

Two primary views, both under the same masthead:

1. **The run list** (default view on load / on returning to the console): every run,
   newest first, each row showing `run_id`, `task`, `state`, `outcome` if terminal, and
   `submitted_at`. A filter bar above it (client-side only, `GET /runs` returns the
   full unfiltered list, confirmed directly in `server.py:1904-1914`, no query
   parameters exist, so filtering by state/task/date happens in the browser after the
   fetch). Clicking a row opens the run detail. A "submit" affordance sits at the top of
   this view, not as a separate page: submitting is the start of the same story this
   view already tells.

2. **The run detail / working view**: everything about one run. This is where the
   waiting experience lives, and where most of a session's time is actually spent.

```
+----------------------------------------------------------------------------+
|## SHIMMER                                            [ token: xxxxxxx ]##|  <- dark masthead
|## ------------------------------------------------------------------ ##|    (--ink ground,
|##  Runs            Submit                                            ##|     --paper text)
+----------------------------------------------------------------------------+

  RUN LIST VIEW
  +------------------------------------------------------------------------+
  |  Filter:  [ state v ]  [ task v ]  [ search run id ]                    |
  +------------------------------------------------------------------------+
  |  * running     20260910_140212__a1b2c3   review   submitted 09:41      |
  |  o awaiting    20260910_133005__f0e1d2   review   submitted 09:12      |
  |  o governance  20260909_221900__9c8b7a   draft    submitted yesterday  |
  |  o crashed     20260909_190044__11223c   review   submitted yesterday  |
  |  o completed   20260909_162210__aabbcc   review   submitted yesterday  |
  |  ...                                                                    |
  +------------------------------------------------------------------------+

  RUN DETAIL / WORKING VIEW  (state = running)
  +------------------------------------------------------------------------+
  |  < Runs        20260910_140212__a1b2c3                    [ Cancel ]  |
  |  review . paired . submitted 09:41                                     |
  +------------------------------------------------------------------------+
  |  * Running, phase 5.5, convention review                              |
  |                                                                         |
  |  ############............................  41 of ~99 pairs settled    |
  |                                                                         |
  |  31 pairs closed by arithmetic alone . 13 model calls made             |
  |  Estimated remaining: rough, ~14 min (from 3 comparable past runs)     |
  |                                                                         |
  |  Nothing to do yet. This screen updates on its own; you can leave      |
  |  and come back.                                                        |
  +------------------------------------------------------------------------+
  |  Phases                                                                |
  |  v 1  Situation assessment                                             |
  |  v 3  Content production                                               |
  |  v 5  Verification & fact-check                                        |
  |  > 5.5 Convention review               <- currently here               |
  |  . 6  Synthesis                                                        |
  |  . 6.5 Editorial review                                                |
  |  . 7  Audit synthesis                                                  |
  |  . 9  Redaction screening                                              |
  +------------------------------------------------------------------------+
  |  Documents                                                             |
  |  (none finished yet, documents appear here once phase 5.5              |
  |   has paired them; nothing to show before that)                        |
  +------------------------------------------------------------------------+
```

When `state = awaiting_approval`, the same view replaces the progress block with the
pending question and a decision control (below). When `state = stopped`, it replaces the
progress block with the outcome block (below) and the Documents section becomes real:
per-document rows, each with a link to its own deliverables zip once `status: "done"`,
plus the whole-run archive with its partial/complete signal.

## The working view in detail

**Where the progress proportion comes from, exactly, and why it is honest.**
`_emit_progress` in `pipeline.py` (`TOTAL_PHASES = 9`, confirmed at `pipeline.py:403`)
emits phase numbers `1, 3, 5, 5.5, 6, 6.5, 7, 9`, non-contiguous by design (there is no
phase 2, 4, or 8), and phase 5.5 is conditional on conventions existing at all
(`pipeline.py:3267`, `else: phase_skipped phase=5.5`). A literal `current_phase / 9` bar
would therefore be dishonest: reaching phase 9 does not mean 9/9 of the *actual* work
units happened, because two of the nine numbers were never going to fire. The plan does
NOT draw a bar keyed to the raw phase number. Two options were considered:

1. **A fixed ordinal position in the real phase sequence** (index into
   `[1, 3, 5, 5.5, 6, 6.5, 7, 9]`, 8 real steps, so "phase 5.5" is honestly "position 4
   of 8," not "5.5 of 9"). This is truthful about ORDER but says nothing about how much
   WORK each phase actually represents: phase 3 (content production) and phase 9
   (redaction) are not equal-sized units of time.
2. **The pair-settlement proportion**, when in paired review mode: `pairs_planned`,
   `pairs_arithmetic_only`, and `model_calls` are all real, live counters
   (`_review_progress`, `server.py:1034-1058`, confirmed reading from the run's own
   pairing map and cost ledger on every call). `pairs_arithmetic_only` is explicitly
   `null` in wide mode (server.py:1053-1055) because the subtraction is not meaningful
   there, the design respects that null exactly, see below.

**Decision: show both, not one alone, because neither is honest by itself.** The phase
ladder (option 1) is always drawable and always true, it answers "how far along in the
SEQUENCE." The pair bar (option 2, paired mode only) is drawable only once phase 5.5 is
running and only in paired mode, and it answers "how much of the reviewable WORK inside
this phase is done", the two questions are different and the brief asks for both ("which
phase, what that phase does, what has finished, what is left").

**The bar itself.** Only drawn when there is a real denominator: `pairs_planned` (an
int, always present once the pairing map exists) as the denominator, `pairs_planned -
(pairs the review has yet to settle)`, concretely, `model_calls made so far toward
phase 5.5's own pairs` is not separately exposed, so the honest number available is
`pairs_arithmetic_only` (pairs ALREADY settled without a model, a strict lower bound on
"finished pairs," since every model-judged pair that has already returned an answer is
also finished but is not separately counted from ones still in flight) plus a running
count of model calls attributable to phase 5.5 specifically, which the API also does
not separate from total `model_calls` across ALL phases (`_model_call_counts` sums
`total_calls` across every phase, `server.py`'s `_REVIEW_PHASE = "5.5"` constant is used
only to compute `pairs_arithmetic_only`'s subtraction, not exposed as its own field).
**Given that gap, the bar is drawn as: settled-with-no-model-call (a real, exact lower
bound) out of pairs_planned, labeled explicitly as "at least this many settled" rather
than implying it is the live edge of progress.** Before phase 5.5 starts, or in wide
mode, no bar is drawn at all, the phase ladder alone carries the "which phase" story,
per the brief's own rule: if the bar cannot be honest, do not draw one.

**The remaining-time estimate, exactly how it is derived, and its honesty label.**
`GET /runs` (server.py:1904-1914) returns every past run with `submitted_at`,
`started_at`, `completed_at`, `task`, `review_mode`, `sensitive`. On loading the working
view, the console additionally fetches `GET /runs` once, filters client-side to runs
sharing this run's `task` and `review_mode` and `state == "stopped"` with
`outcome == "succeeded"`, and computes each one's wall-clock duration
(`completed_at - started_at`). If there are **zero** comparable finished runs, no
estimate is shown at all, not a guess, not a generic number, nothing. If there are
**one or two**, the estimate is shown with the sample size stated plainly ("~40 min,
based on 1 earlier run, treat this loosely") because a single data point is not a
statistic, it is an anecdote, and the copy says so. At **three or more**, the median of
those durations minus this run's own elapsed time (`now - started_at`) is shown as the
estimate, still labeled "rough" in the copy always, there is no per-phase timing
exposed by any route (`log_phase_done`'s `duration_ms` lands only in the raw
`pipeline_stdout.log` text via `GET /runs/{run_id}/log`, never in a structured field;
parsing that log client-side for a live estimate was considered and rejected, it would
require the console to parse pipeline internals out of free-text log lines, which is
exactly the kind of prose-parsing the API layer was built specifically to make
unnecessary elsewhere on this surface, and doing it only here for an estimate would be
inconsistent with that principle), so even a three-plus-sample median is an
across-different-content estimate, not a same-document forecast, and the copy never
promises more precision than that.

**What it says when it cannot estimate honestly.** Exact copy, see the copy section
below, the short version: it says nothing rather than inventing a number, per the
brief's explicit instruction.

## State and outcome, expressed visually

`state` (server.py's `_state_for_job`, five values) is the PRIMARY visual signal, a
small filled/hollow dot plus a text label, never colour alone (contrast/colour-blindness:
shape and text always carry the meaning, colour reinforces it). `outcome` (populated only
once `state` is `"stopped"` or `"cancelled"`, five values:
`succeeded`/`governance_stop`/`crashed`/`timed_out`/`cancelled`) becomes the SECOND line
of the same status block once a run is terminal.

| `state` | Dot | Colour | Label |
|---|---|---|---|
| `queued` | hollow circle | `--ink` @ 55% (computed neutral, not a named hue, see the revised palette) | "Queued" |
| `running` | filled circle, pulses only if `prefers-reduced-motion: no-preference` | `--periwinkle` | "Running, phase X, {phase name}" |
| `awaiting_approval` | filled circle with a ring around it (same hue as `running`, distinguished by shape, not a second colour, see the revised palette's fold of `lavender` into `periwinkle`) | `--periwinkle` | "Awaiting your decision" |
| `stopped` + `outcome: succeeded` | filled circle | `--mint` | "Completed" |
| `stopped` + `outcome: governance_stop` | filled square (deliberately NOT a circle, see below) | `--peach` | "Stopped by a rule" |
| `stopped` + `outcome: crashed` / `timed_out` | filled triangle (deliberately NOT a circle) | `--rose` | "Crashed" / "Timed out" |
| `cancelled` | hollow square | `--ink` @ 55% (same computed neutral as `queued`) | "Cancelled" |

**Keeping a governance stop distinct from a failure, concretely, at three levels, not
one:** (1) colour family, peach is nowhere near rose or any red; (2) SHAPE, not just
colour, so the distinction survives greyscale printing or a colour-blind reader, a
governance stop is a square, a crash is a triangle, success is a circle; this is the
single most load-bearing visual decision in the whole design and it is deliberately
redundant across two channels, not one; (3) copy, a governance stop's detail line names
the actual rule (`stop_reason.code`, one of `stopped_model_approval` /
`stopped_redaction_gate` / `blocked` / `refused_sensitivity_layer_inactive`, rendered as
a full sentence, never the bare code) and explains what happens next (see copy below); a
crash's detail line shows `stop_reason.detail`, which per the server's own comment
(`server.py:1252-1253`) can be a short phrase or up to a 2000-character subprocess log
tail, the console truncates this visually to a few lines with a "view full log" link to
`GET /runs/{run_id}/log`, never dumps the raw tail inline the way the current console's
error column does.

## The one element spent boldness on, and what stays quiet around it

**Boldness spent on:** the governance-stop state. It gets the one non-square-cornered
shape exception (a filled square with a 2px radius, visually distinct from every other
corner treatment on the page, which is otherwise uniformly square) and the peach hue,
which is the warmest, most attention-taking colour in the whole palette after rose. This
is deliberate: the brief calls this distinction "the most important thing the interface
says," so it is the one place the design spends visual weight that isn't purely
structural. Everything else about a governance-stop row, its typography, its spacing,
its position in the list, is otherwise identical to every other row; the boldness is
narrowly the shape+colour token, not a special layout.

**The masthead is not a second bold element.** It is structural and constant, the same
dark band, in the same place, on every view, whether the run is queued or crashed, so it
never competes for attention with the one state that's supposed to stand out. It carries
identity, not emphasis; the governance-stop square-and-peach treatment remains the only
place in the design where colour and shape are used to make one specific thing louder
than its neighbours.

**What stays quiet:** literally everything else. The run list is one typeface size for
all rows differing only by the state token. The findings table has no colour beyond a
thin left-rule per `record_verdict` (irregular vs. ok), reusing the SAME mint/rose-family
tokens rather than inventing a third meaning for colour. The submit form is unstyled
beyond the grid and the hairlines, no call-to-action button treatment beyond a solid
`--ink` fill on `--paper` text, no hover glow, no icon library. The token entry field is
a plain password input with no decoration. Nothing on the page uses a shadow, a
gradient, or an animation beyond the reduced-motion-gated pulse on the "running" dot and
a plain CSS transition on focus rings.

## Copy

**Empty state (run list, nothing submitted yet):**
> No runs yet. Submit documents to start a review, or a question to start a draft.

**One error (network/auth failure calling a route, e.g. token rejected, 401):**
> The token was not accepted. Check it against the one the operator gave you, and try
> again.

(Not "Oops!", not an apology, not an exclamation mark, a flat statement of what
happened and what to do.)

**One refusal (submitting with `review_mode` the server rejects, 400, or cancelling an
already-terminal run, 409, the copy reads the server's own `detail` string and frames
it, it does not invent a nicer one, since `detail` is already a full sentence at every
call site checked in `server.py`):**
> {server's `detail` text, verbatim}. Nothing was changed.

**Next-action sentence, one per state, always the last line of that state's block:**

- `queued`: "Waiting for the run ahead of it to finish. Nothing to do: this page
  updates on its own."
- `running`: "Nothing to do yet. This page updates on its own; you can leave and come
  back."
- `awaiting_approval`: "This run is waiting on you. {message from `pending_approval`}
  Decide below, or come back to it later; the run will not continue until you do."
- `stopped` / `succeeded`: "Finished. Start with the findings below, or download the
  full archive."
- `stopped` / `governance_stop`: "Stopped by {rule name, from `stop_reason`}. This was
  not an error: the pipeline refused on purpose. {what happens next: for
  `stopped_model_approval`/`stopped_redaction_gate`, this reads as historical, since a
  live pending decision would instead show `state: awaiting_approval`, a terminal
  governance_stop means the run's approval-wait window closed without an answer, so the
  copy says so: "No decision was recorded before this run's wait window closed."}."
- `stopped` / `crashed` or `timed_out`: "The run did not finish. {detail, truncated,
  with a link to the full log}. You can submit it again."
- `cancelled`: "Cancelled{, before it started / while running, from `stop_reason.detail`
  verbatim, which the server already phrases as one of exactly those two strings}."

## New capabilities, and where each one lives

- **Cancelling a run**: a single "Cancel" button in the run-detail header, visible only
  while `state` is `queued` or `running`. Calls `POST /runs/{run_id}/cancel`; the
  response is a full `_run_record` (confirmed `server.py:1484` and the running-path
  return later in the same function), so the view re-renders directly from the response
  body with no extra fetch. A confirmation step (not a native `confirm()` dialog, styled
  inline, matching the rest of the page) before the call fires, since this is
  irreversible in the sense that it stops real work.
- **Answering a pending approval**: the `awaiting_approval` state's working-view block
  shows `pending_approval.message` as the question, and `pending_approval.payload`
  rendered as a small key/value table (structured detail, kept visually separate from
  the prose message, the human/machine field split the API itself makes, per
  `server.py:1085-1088`'s own comment, is preserved rather than flattened into one
  block). Two buttons, "Approve" / "Deny" (free-text `decision` under the hood, but the
  console does not expose arbitrary strings, per the API's own design note that
  `_is_approved` only recognizes a narrow set of approving words, the console sends
  exactly `"APPROVE"` or `"DENY"`, never inventing a third option the pipeline could not
  interpret), plus an optional rationale field. `POST /runs/{run_id}/approval` returns
  `202` with `recorded: true`, the console's own confirmation banner says exactly that:
  "Recorded. The run has not resumed yet: this page will update once it does," never
  "Approved," because the route itself never claims that (`server.py`'s own comment:
  "never claims the decision was approved, only that it was recorded").
- **Reading findings**: a table under the terminal-state working view, one row per
  Finding, columns for `rule_id` / `source_rule_id`, `unit_id`, `relation`,
  `record_verdict`, both figures with units, and `explanation` truncated with expand.
  Monospace for the figures and IDs, per the typography section.
- **Seeing the pairing map**: a secondary, collapsed-by-default panel per document
  (`GET /runs/{run_id}/pairs`), since this is an audit trail a reviewer consults when
  justifying a finding, not the first thing they read, paired/rejected/undecided rules
  per unit, each with its reason, exactly the shape `_pairs_view` returns.
  `prior_hit_count`/`prior_check_count`/`prior_refused_count` shown as three small
  numbers, not expanded further (they are already reduced to counts server-side for a
  reason, no attempt to reconstruct the underlying comparison here).
- **Downloading one document**: each row in the Documents section of a terminal-state
  working view has its own "Download" link once `status: "done"`, pointing directly at
  `deliverables_url` (a real route now, `GET /runs/{run_id}/deliverables/{doc_id}`,
  confirmed `server.py:1721`), a real anchor `href`, not a JS-driven fetch-and-blob,
  since the token has to travel as a header and a plain anchor cannot carry one; this
  needs a small fetch-then-download pattern (fetch with the Authorization header,
  receive the blob, create an object URL, trigger the download) rather than a bare
  `<a href>`, which is a real implementation detail to flag now rather than discover
  during the build.
- **Downloading the whole archive, honestly labeled when partial**:
  `GET /runs/{run_id}/deliverables` is called the same way; the response's
  `X-Shimmer-Partial` header (confirmed `server.py`'s deliverables route) and the
  filename's `_partial`/`_deliverables` suffix are both read, and the console's download
  button itself is labeled from that fact BEFORE the click, not just after, if the run
  is not `stopped`/`succeeded`, the button reads "Download partial archive" from the
  start (derivable client-side from `state`/`outcome` already on the page, without
  waiting for the response), so a reviewer never discovers partiality only after the
  file lands on their disk.
- **Browsing past runs**: the run list view itself, described above, with client-side
  filter/search since the server has no query parameters on `GET /runs`.

## The waiting page's persistence requirement

"Nothing important may live only in the browser's memory," and separately the token must
"never be stored anywhere it would persist." These two constraints are in tension and
resolved as follows: the run being watched is identified by its `run_id` in the URL
(`#/runs/{run_id}`, a hash route, so a reload or a link sent to another device lands
directly on the right run without any client-side state at all), that satisfies
persistence for everything except the token. The token itself goes in
`sessionStorage`, not `localStorage`: it survives a same-tab reload (so a reviewer who
reloads the page mid-run does not have to re-type it) but is cleared when the tab or
browser closes and is never sent anywhere but the `Authorization` header of this
origin's own requests, never a URL, never a cookie, never `localStorage` (which would
persist indefinitely across restarts, closer to "stored" than the brief's "kept only in
page memory" language allows for the ORIGINAL console; `sessionStorage` is a deliberate,
narrow widening of that rule specifically to satisfy the NEW "reload and return on
another device" requirement, a different device needs its own token entry regardless,
since `sessionStorage` cannot follow a person across devices, and that is correct: the
token was always meant to be entered per session, this only stops a same-tab reload from
discarding it).

---

## Self-review: what I rewrote because my first instinct was the generic default

Read back against the brief's own "what to avoid" list, three real changes from an
initial draft:

1. **First instinct was a dark console** (dark background, light text, the state colours
   as bright accents against black, closer to the cover art itself, and closer to what
   "professional tool" defaults to in 2026). Rewritten to a light, paper-toned ground
   once I re-read "an annotated legal instrument, a regulator's decision notice", those
   are printed documents, not terminals. A dark UI was the tool-builder's default, not
   the institution's.

2. **First instinct was to vendor a serif, then I over-corrected to a system stack, and
   that second call was wrong, I did not catch it myself.** The serif instinct and its
   rejection (below) both still hold: "institutional register" reading as "give it a
   serif" was a real reflex, and a decorative editorial serif would have been exactly
   that. But the conclusion I drew from rejecting it, reach for the system stack
   instead, was the actual mistake, and it took the operator naming it directly to
   surface: a system stack looks different on every machine, which is the opposite of
   what a real institution's type does, and the "offline" argument I used to justify it
   didn't hold up against a font file baked into the same image as the model checkpoints
   this project already vendors. This is the one item in this list I would not have
   caught on a second read of my own draft; it needed to be told to me.

3. **First instinct for the progress bar was a single `phase / 9` fraction** because
   that is the obvious reading of "the server reports the phase", it took actually
   reading `_emit_progress`'s call sites to notice phases 2/4/8 never fire and that a
   naive fraction would silently lie about how much of the run remains. Rewritten to the
   two-part phase-ladder-plus-pair-count design above, and to refusing to draw a bar at
   all before phase 5.5 or in wide mode, which was not my first instinct, the first
   instinct was to draw SOME bar rather than admit the data does not support one yet.

4. **First instinct on the palette was to land at nine tokens and call it "six meaning
   colours plus three structural,"** treating the brief's four-to-six number as a budget
   for one category and exempting the other. That was motivated reasoning, not a design
   decision, the honest question was never asked until the operator asked it: does
   every one of these hexes earn a separate name, or are some of them the same idea
   wearing a different label? Once asked, two didn't (`--rule` and `--quiet` were both
   just `--ink`, quieter) and two more didn't need separate HUES, only separate shapes
   (`--lavender` and `--periwinkle` were both "in progress"). This is not caught by
   re-reading the avoid-list, the way items 1 and 3 were, it's caught only by
   re-counting and asking what each thing is actually for, which I did not do
   unprompted.

Everything else in this document was tested against "would this appear on any
SaaS-template review site" and rejected if so (no gradient hero, no rounded-card grid,
no tracked-out eyebrow labels, no dot-joined meta strings, no arrow-suffixed links, no
fade-and-slide), those were caught before a first draft existed, since the brief's "hard
avoid" list was read before any layout sketch was made, not after.
