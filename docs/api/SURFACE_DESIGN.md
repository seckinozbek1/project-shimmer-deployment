# Server surface design (built)

This document was written as a proposal before any code existed and is now a RECORD of
what was built, kept in this shape because it still explains the reasoning behind the
surface. It followed `docs/api/SURFACE_INVENTORY.md`, which described the original
11-route surface this one replaced.

The build happened in five stages on the `api` branch: B1 (the run resource and its
status, commit `9e0b8ab`), B2 (cancellation, `ccb7aa9`), B3 (approvals, `44ab800`), B4
(deliverables and the log route, `0d0ba21`), and B5 (fixing six inconsistencies a
fresh-eyes read of the finished surface found, including a full route-naming rename).
Every route below is now live in `scripts/server.py`; nowhere in this document should
"proposed" be read as "not yet built" unless a passage explicitly says so.

## Reconciliation with what B5 changed

B5 made five changes this document did not originally specify, each because a
fresh-eyes stranger-read of the finished B1-B4 surface found a real inconsistency.
Everywhere below that still describes the pre-B5 shape is superseded by this list,
kept here rather than silently rewritten throughout so the "why" survives:

- **`status` was dropped entirely from `GET /runs/{run_id}` and `GET /runs`.** This
  document's field notes (below) never explicitly said whether the raw internal
  `status` string would still appear alongside `state`/`outcome`/`stop_reason`; B1's
  actual implementation kept both, which meant a caller could read `status="blocked"`
  next to `state="stopped", outcome="governance_stop"` with nothing saying which
  vocabulary to trust. B5 removed `status` from these two routes' HTTP response only;
  the field itself is unchanged everywhere else (the internal job dict, `status.json`
  on disk, `_STATUS_FIELDS`, every place that decides `state`/`outcome`).
- **`POST /approvals/{run_id}` is now genuinely gone**, not merely superseded. This
  document's own mapping table (below) always proposed replacing it with `POST
  /runs/{run_id}/approval` — that part was never in question. What changed: stage B3's
  actual implementation (which built `POST /runs/{run_id}/approval`) left the old route
  running alongside the new one, staged deliberately so console-breakage stayed visible
  one stage at a time rather than all at once. B5 is what finally deleted it, once the
  operator's route-naming decision ("nothing calls this server but a console that does
  not exist yet... it will never be this cheap again") made clear that no interim
  coexistence period was needed.
- **`GET /approvals` now returns the SAME shape as `pending_approval`** (`message`,
  `default_on_timeout`, `timeout_at` alongside `topic`/`payload`/`asked_at`), not the
  thinner shape this document's own route entry for `GET /approvals` describes below.
  `_pending_approvals()` now genuinely delegates to `_pending_approval_for()`.
- **`GET /status/{run_id}`, `GET /queue`, `GET /results/{run_id}`, `GET
  /findings/{run_id}` and `GET /pairs/{run_id}` are all gone, not merged-with-a-legacy-
  alias.** This document's mapping table (below) already proposed removing/renaming
  all five; B1-B4 built the replacements but left the old names live alongside them
  (explicitly, stage by stage, so console-breakage stayed staged and visible). B5
  finished the rename outright: no alias, no back-compat route, per the operator's
  explicit instruction that keeping both names "makes the mess permanent."
- **`documents[].deliverables_path` is `documents[].deliverables_url`,** and it was
  built as a real fetchable route in B4 (`GET /runs/{run_id}/deliverables/{doc_id}`),
  not the display-only string this document's original field notes describe. The
  rename from `_path` to `_url` reflects that it is now genuinely a URL, not a path
  fragment meaningful only inside a downloaded zip.

Everything else below — the field-by-field reasoning for `state`/`outcome`/
`stop_reason`/`pending_approval`, the governance constraints, the calling sequence, the
console-impact list — was built as specified and is unchanged by B5.

It followed four decisions made by the operator, restated here so the design can be
checked against them:

1. `GET /status/{run_id}` becomes complete: one call answers state, stop reason (if
   stopped), per-document output locations, and nothing further is needed to understand
   that answer.
2. Cancelling a run is a new capability.
3. Backward compatibility does not matter. The console is the only caller. Routes may be
   removed and merged freely.
4. The console itself is out of scope. This document proposes the server surface only.

Two constraints apply throughout:

- A governance outcome (the pipeline stopped itself on purpose: a model-approval gate, a
  redaction gate, an inactive sensitivity layer) must be as legible as a success, and
  must never be reported the same way as a crash.
- Structured data for a program and prose for a person are never mixed in one field.

## Proposed routes

### `POST /runs`

- Accepts: multipart form, same fields `/submit` accepts today — `files`, `task`,
  `question`, `sensitive`, `review_mode` — unchanged in meaning and validation (file
  count/size caps, task/review_mode enum checks, contract validation of uploaded
  files). Renamed from `/submit` to `/runs` so the resource the whole surface is built
  around (a run) has one consistent noun: you `POST /runs` to create one, `GET
  /runs/{run_id}` to read one, `GET /runs` to list them, `POST /runs/{run_id}/cancel` to
  stop one.
- Returns, `201`, shape:
  ```
  {"run_id": "20260910_140000__a1b2c3",
   "status": "queued",
   "task": "review",
   "sensitive": false,
   "review_mode": "paired"}
  ```
  (No `files` echo — the caller already has the list it sent; nothing here a caller
  cannot already reconstruct from its own request.)
- Status codes: `201` (queued), `400` (the same rejection reasons `/submit` has today:
  bad `task`/`review_mode`, missing `question` for draft, missing files for review,
  over-count, over-size, contract validation failure, upload-staging exception).
- Why: creating a run is the one write that starts everything else; `201` (a resource
  was created) replaces `202` (accepted for later processing) because the run record
  exists and is immediately readable the instant this call returns, which `202`
  historically signals is not yet true.

### `GET /runs/{run_id}`

- Accepts: path parameter `run_id`, nothing else.
- Returns, `200`, shape (the "complete status" decision):
  ```
  {"run_id": "20260910_140000__a1b2c3",
   "task": "review",
   "sensitive": false,
   "review_mode": "paired",
   "question": "",
   "submitted_at": "2026-09-10T14:00:00+00:00",
   "started_at": "2026-09-10T14:00:03+00:00",
   "completed_at": null,
   "state": "running",
   "outcome": null,
   "stop_reason": null,
   "exit_code": null,
   "pending_approval": null,
   "progress": "phase=5.5 doc=2/3",
   "counters": {"pairs_planned": 40, "pairs_arithmetic_only": 31, "model_calls": 12},
   "documents": [
     {"doc_id": "case_a", "status": "done", "deliverables_path": "case_a/"},
     {"doc_id": "case_b", "status": "in_progress", "deliverables_path": null},
     {"doc_id": "case_c", "status": "not_started", "deliverables_path": null}
   ],
   "log_url": "/runs/20260910_140000__a1b2c3/log"}
  ```
  The same route on the same run a moment later, once a governed decision has come up
  mid-run (`state` and `pending_approval` are the only fields that differ from the
  shape above; everything else — `progress`, `counters`, `documents` — stays exactly as
  it was the instant the run paused, since nothing further executes until a decision is
  recorded):
  ```
  {"run_id": "20260910_140000__a1b2c3",
   ...,
   "state": "awaiting_approval",
   "outcome": null,
   "stop_reason": null,
   "exit_code": null,
   "pending_approval": {
     "topic": "MODEL_DEPRECATED",
     "message": "Agent LEGAL_ANALYST is assigned model 'claude-opus-3'; retired by the provider. Proposed current replacement: 'claude-opus-4-8'.",
     "payload": {"agent": "LEGAL_ANALYST", "backend": "anthropic",
                  "dead_model": "claude-opus-3", "proposed_replacement": "claude-opus-4-8"},
     "asked_at": "2026-09-10T14:03:10+00:00",
     "default_on_timeout": "DEFERRED",
     "timeout_at": "2026-09-10T15:03:10+00:00"},
   ...}
  ```
  Field notes, since this is the route the "complete" decision lands on:
  - `state` replaces today's overloaded `status` string for the coarse machine-branch:
    one of `"queued"`, `"running"`, `"awaiting_approval"`, `"stopped"`, `"cancelled"`.
    Five values, a closed set, so a caller's switch statement is exhaustive by
    construction. `"running"` and `"awaiting_approval"` are deliberately distinct rather
    than one state with a flag: `"running"` means the run is making progress on its own
    and will reach a terminal state unattended; `"awaiting_approval"` means it is
    stalled and will stay stalled until a person calls `POST
    /runs/{run_id}/approval` — a caller (or the console) needs to behave differently in
    each case, showing progress in one and a decision control in the other, and a
    boolean bolted onto `"running"` would let a caller miss it. `"stopped"` covers every
    terminal case that is not a live cancel — success, governance halt, or crash — and
    `outcome` (below) is what tells those three apart. This directly answers the
    governance-vs-crash constraint: a governance halt and a crash are never both spelled
    `"failed"` the way `"blocked"` and unmapped exit codes both collapse into
    poorly-differentiated strings today (`_EXIT_STATUS_MAP` /
    `SURFACE_INVENTORY.md` Question d).
  - `outcome` is populated only once `state` is `"stopped"`: one of `"succeeded"`,
    `"governance_stop"`, `"crashed"`, `"timed_out"`. Four values, closed set. This is the
    field a caller branches on to know whether to treat the run as done-and-good,
    done-on-purpose-but-not-what-was-asked, or broken.
  - `stop_reason` is populated only when `outcome` is `"governance_stop"` or
    `"crashed"` or `"timed_out"`; null when `"succeeded"`. It is a typed object, not
    prose: `{"code": "stopped_model_approval", "detail": "..."}` where `code` is one of
    the four governance codes carried over unchanged from `_EXIT_STATUS_MAP`
    (`stopped_model_approval`, `stopped_redaction_gate`,
    `refused_sensitivity_layer_inactive`, and `blocked` split into two distinct codes,
    see below) or `"crashed"` / `"run_timeout"`. `detail` is the short structured reason
    (for `blocked`, which fields), never the raw stdout tail.
  - The exit-code-5 ambiguity (`blocked` meaning either a redaction-gate block or a
    draft-mode phase-0 generation failure, `SURFACE_INVENTORY.md` Question d) is resolved
    structurally here, not left to the caller to guess from a log tail: the pipeline
    subprocess is expected to distinguish which of the two happened (it already knows,
    internally, which branch it took) and report it as one of two distinct `stop_reason.code`
    values, `"blocked_redaction_gate"` or `"blocked_draft_generation"`, rather than the
    single overloaded `"blocked"`. This is the one place the design asks for a behavior
    change beyond re-routing (see "What the current server does that this design would
    lose" below, which flags it honestly rather than hiding it as a free rename).
  - `exit_code` is kept as a raw integer for anyone who wants it, but is no longer the
    field a caller is expected to branch on; `state`/`outcome`/`stop_reason` are.
  - `pending_approval` is populated only when `state` is `"awaiting_approval"`; null
    otherwise. It is what a person needs to decide, delivered by the same call that told
    them a decision is needed, so no second call is required to act — matching the "no
    second call" decision for this case specifically. Its fields:
    - `topic`: the governed-decision type (today's two are `"MODEL_DEPRECATED"` and
      `"CONSTITUTION_AMENDMENT_GUARD"`, unchanged from what the pipeline's operator
      handler already writes into `pending_approval.json`).
    - `message`: the one prose sentence explaining what is being asked, carried over
      unchanged from the pipeline's own `payload["message"]` (the model-gate and
      constitution-guard call sites already build this string today; the server does not
      author it). This is prose for a person, deliberately separate from `payload` below.
    - `payload`: the structured detail behind the question (e.g. for a
      `MODEL_DEPRECATED` topic: `agent`, `backend`, `dead_model`,
      `proposed_replacement`) — carried through unchanged from what the pipeline writes,
      for a caller that wants to render its own decision UI rather than just display
      `message` verbatim.
    - `asked_at`: when the question was raised, unchanged from today's field of the same
      name.
    - `default_on_timeout`: always the literal string `"DEFERRED"` — what happens if
      nobody decides (the pipeline's file handler already falls back to `DEFERRED` on
      timeout, unconditionally, regardless of topic; this field states that existing
      behavior rather than changing it, so "what happens if they do nothing" is
      answered directly on the object instead of left for the caller to know from
      reading the pipeline source).
    - `timeout_at`: `asked_at` plus `SHIMMER_APPROVAL_WAIT_S` (default 3600s), computed
      by the server from the same environment variable the pipeline subprocess already
      reads for this purpose, so a caller can show a countdown without needing to know
      the env var itself.
    A caller does not need `GET /runs/{run_id}/approval` to see any of this; that route
    (kept, see below) exists for a caller that only ever wants the pending-approval
    question in isolation, without the rest of the run object.
  - `documents` is new: one entry per document the run is processing, each with its own
    `status` (`"not_started"` / `"in_progress"` / `"done"` / `"failed"`) and
    `deliverables_path`, non-null once that document's output exists. This is what
    answers "which documents were processed and where their results are" without a
    second call. Sourced from the run's own pairing map / deliverables directory listing
    (the data already exists on disk per document, `SURFACE_INVENTORY.md`'s description
    of `_pairing_map` and the BP-16 `deliverables/<doc_id>/` layout; today it is not
    surfaced as a per-document list anywhere).
  - `progress` and `counters` are carried over unchanged from today's `/status`
    (`_progress_string`, `_review_progress`).
  - `log_url` replaces the console's client-constructed, never-fetchable
    `run_id + '/logs/pipeline_stdout.log'` string (`SURFACE_INVENTORY.md` Question e)
    with an actual route (`GET /runs/{run_id}/log`, below) that serves the file. This is
    new capability, not a rename: today that path is displayed but never fetchable over
    HTTP at all.
- Status codes: `200`, `404` (unknown or malformed `run_id`).
- Why: this is the single route the "no second call" decision is built around; every
  fact needed to understand a run's outcome is a field on this one object.

### `GET /runs`

- Accepts: nothing (no filter/pagination parameters proposed; see "what the current
  server does that this design would lose" for why that gap is named rather than
  silently closed).
- Returns, `200`:
  ```
  {"runs": [ <same per-run object GET /runs/{run_id} returns, one per run>, ... ]}
  ```
  oldest `submitted_at` first, unchanged ordering from today's `/queue` and `/runs`.
- Status codes: `200` only.
- Why: replaces both `/queue` and `/runs` (identical bodies today,
  `SURFACE_INVENTORY.md` Question a) with one list route, and now returns the same rich
  per-run shape as the single-run route rather than a thinner one, so a caller never has
  to cross-reference the list against a detail call just to see `state`/`outcome`.

### `POST /runs/{run_id}/cancel`

- Accepts: path parameter `run_id`, no body.
- Behavior: if the run's `state` is `"queued"`, it is removed from the queue without
  ever starting (no subprocess exists yet, nothing to terminate). If `state` is
  `"running"`, the pipeline subprocess is sent the same terminate-then-kill sequence the
  existing run-timeout path already uses (`proc.terminate()`, then `proc.kill()` on a
  grace-period timeout, per `SURFACE_INVENTORY.md`'s reading of the current
  `_on_timeout` handler) — cancellation reuses that exact mechanism, triggered by a
  caller instead of a clock. If `state` is already `"stopped"` or `"cancelled"`, this is
  a no-op that still returns `200` (cancelling a run that is already over is not an
  error; it is a caller racing the run's own completion, which must not surface as a
  failure).
- Returns, `200`:
  ```
  {"run_id": "20260910_140000__a1b2c3", "state": "cancelled"}
  ```
  (or the run's actual terminal `state`/`outcome` if it had already finished before the
  cancel request landed — the response always reflects the true current state, never a
  promise).
- Status codes: `200`, `404` (unknown or malformed `run_id`).
- Why: this is decision two, cancellation, stated as its own route. A queued job and a
  running job are cancelled through the same call because the caller should not need to
  know which one it is dealing with; the server already does.
- Implementation note carried into this design rather than hidden: today's `_run_job`
  holds its `Popen` object as a local variable, reachable only by the timeout timer's own
  closure (`SURFACE_INVENTORY.md` confirms no other reference to it exists). Building
  this route means giving that process handle a place to live that an HTTP-thread
  handler can also reach — a `run_id -> Popen` registry guarded by the same lock `JOBS`
  already uses. This is a structural change to `_run_job`, not just a new decorator; it
  is the one place this design requires touching code that is not purely additive.

### `GET /runs/{run_id}/findings`

- Unchanged from today's `GET /findings/{run_id}`: same query, same
  `_project_finding` shape, same superseded-revision handling, same empty-list-not-404
  behavior for a run with nothing yet. Renamed only for path consistency under
  `/runs/{run_id}/...`.
- Returns, `200`:
  ```
  {"run_id": run_id, "count": len(records), "findings": records}
  ```
  (`records` shape unchanged, per `SURFACE_INVENTORY.md`'s `/findings` entry.)
- Status codes: `200`, `404` (malformed or unknown `run_id`).
- Why: the structured review itself, kept exactly as today's audit showed it working
  correctly (typed records, revision supersession, no document text).

### `GET /runs/{run_id}/pairs`

- Unchanged from today's `GET /pairs/{run_id}`, renamed only for path consistency.
- Returns, `200`: identical shape to today's `/pairs/{run_id}`
  (`document_count`, `documents[]`, each with `units[]`).
- Status codes: `200`, `404` (malformed or unknown `run_id`).
- Why: the pairing-decision record, kept as-is; nothing about it was found broken or
  overlapping with anything else.

### `GET /runs/{run_id}/deliverables`

- Accepts: path parameter `run_id`.
- Behavior: unchanged from today's `/results/{run_id}` — zips `deliverables/` (or the
  whole run tree as fallback), streamed. Renamed for path consistency and to use the
  name the codebase's own BP-16 layout already calls this directory
  (`SURFACE_INVENTORY.md`'s citation of `deliverables/<doc_id>/`), rather than the more
  generic `results`.
- Behavior change: no longer `400`s before completion. Because `GET
  /runs/{run_id}` now exposes a per-document `status`/`deliverables_path`
  (`"done"` documents have a non-null path), a caller can already tell, from the status
  call, which documents (if any) have output ready; this route now returns whatever
  exists on disk at call time — a zip of just the documents marked `"done"` if the run is
  still in progress, or the full set once `state` is `"stopped"` with `outcome ==
  "succeeded"`. A run with zero completed documents yet returns `404` with
  `detail="no deliverables yet"` rather than the `400` used today, since "not completed"
  is no longer a single boolean the run either has or hasn't crossed.
- Returns: `StreamingResponse`, `application/zip`, unchanged `Content-Disposition`
  naming pattern.
- Status codes: `200` (zip stream, partial or complete), `404` (malformed/unknown
  `run_id`, or no deliverables exist yet).
- Why: kept as the one prose/binary-bearing route, per the human-vs-machine
  constraint; loosening its completion requirement follows directly from `documents[]`
  now existing on the status call, so a caller who already knows (from `GET
  /runs/{run_id}`) that two of three documents are done is never blocked from fetching
  those two just because the third is still running.

### `GET /runs/{run_id}/log`

- Accepts: path parameter `run_id`.
- Returns: the run's `pipeline_stdout.log` file, `200`, `text/plain`, streamed (not
  loaded fully into memory — the file can be long-running and large, per
  `SURFACE_INVENTORY.md`'s note that today's code deliberately avoids buffering it fully
  even server-side).
- Status codes: `200`, `404` (malformed/unknown `run_id`, or no log written yet).
- Why: this is new capability, closing the gap `SURFACE_INVENTORY.md` named directly
  ("Retrieve the run's log file over HTTP" was listed as something a caller could not
  currently do). It exists so `log_url` on the status object is not a dangling promise.

### `GET /runs/{run_id}/approval`

- Accepts: path parameter `run_id`.
- Returns, `200`, if a governed decision is pending for this run: the same
  `pending_approval` object documented under `GET /runs/{run_id}` above, wrapped with
  the `run_id`:
  ```
  {"run_id": run_id,
   "pending_approval": {"topic": "...", "message": "...", "payload": {...},
                          "asked_at": "...", "default_on_timeout": "DEFERRED",
                          "timeout_at": "..."}}
  ```
  or `200` with `{"run_id": run_id, "pending_approval": null}` if nothing is pending
  (mirrors today's `/findings` empty-but-200 convention: "nothing pending" and "no such
  run" are different answers, and only the latter is `404`).
- Status codes: `200`, `404` (malformed or unknown `run_id`).
- Why: scopes the pending-approval question to the one run a caller already has open,
  rather than requiring a scan of every run's pending approvals to find the one that
  matters, for a caller that wants only this object without the rest of the run's status
  (see the next route for the cross-run list, kept separately since "every run awaiting a
  decision, across the whole server" is a genuinely different question than "is this run
  I'm already looking at waiting on me"). In practice `GET /runs/{run_id}` already
  answers this — this route exists for a caller that only ever wants the question in
  isolation.

### `GET /approvals`

- Accepts: nothing.
- Returns, `200`, AS BUILT (B5 corrected this from the design's original nested
  `{"pending_approval": {...}}` shape to a FLAT one, `dict(pending, run_id=...)`
  in `_pending_approvals()`, matching how every other field on this surface is
  addressed — one level, no wrapper object for a single embedded record):
  ```
  {"approvals": [{"run_id": ..., "topic": ..., "message": ..., "payload": ...,
                    "asked_at": ..., "default_on_timeout": "DEFERRED",
                    "timeout_at": ...}, ...]}
  ```
  each entry carrying the same six fields as `GET /runs/{run_id}`'s `pending_approval`
  object, flattened alongside `run_id` rather than nested under a `pending_approval`
  key, so a caller reading this cross-run list and a caller reading one run's detail
  parse the same field values under the same names, just at a different nesting depth
  (top-level here, one level down on `GET /runs/{run_id}`, where it sits beside
  `state`/`outcome`/other run fields that need their own nesting to avoid a naming
  collision this route never has).
- Status codes: `200` only.
- Why: kept as the one cross-run query the design retains outside `/runs`, because
  "what needs a human right now, across every run" is an operator workflow (driving the
  console's approvals table) that a per-run-scoped route cannot answer without polling
  every run individually.

### `POST /runs/{run_id}/approval`

This is the new route closing the gap named by the operator: today, nothing in the HTTP
surface lets a caller answer a pending approval — the only route that touches
`approval_decision.json` at all is today's `POST /approvals/{run_id}`, but nothing in
the current 11-route surface *reads* the file the pipeline actually watches back to a
caller in a form that confirms the decision took effect, and the current route's own
response (`{"run_id", "decision", "rationale"}`) does not distinguish "this was written
down" from "this was approved," which is the distinction the operator has now required
explicitly.

- Accepts: path parameter `run_id`, JSON body:
  ```
  {"decision": "APPROVE", "rationale": "checked against the vendor's own deprecation notice"}
  ```
  `decision` required, non-empty after stripping (`400` otherwise). `rationale`
  optional, defaults to `""`. The value of `decision` is passed through verbatim to
  `approval_decision.json`; this route does not constrain it to a fixed enum, because
  the code that reads it back (`model_registry._is_approved`,
  `constitution_guard._is_approved`) does not require one either — it pattern-matches a
  small set of approving strings and treats everything else, including `DENY`, `DEFER`,
  or free text, as not-approved. This route does not encode that matching logic a second
  time; see the two governance constraints below.
- Behavior: writes `<run>/audit/approval_decision.json` atomically (temp file then
  replace, unchanged mechanism from today's `POST /approvals/{run_id}`), with
  `{"decision": decision, "rationale": rationale, "decided_at": now}`, the exact record
  shape the pipeline's `_make_file_operator_handler` already polls for and reads back
  (`decision_path.read_text` / `json.loads`, unchanged). `404` if `run_id` is malformed
  or if there is no `pending_approval.json` for it (nothing to answer). This route
  performs no evaluation of `decision` beyond the presence check: it does not call
  `_is_approved`, does not decide whether the run proceeds, and does not itself change
  `state` — the pipeline subprocess, polling for this file exactly as it does today,
  is what reads the decision, calls the same `_is_approved` it always has, and acts on
  it. This is the first governance constraint, stated as an implementation boundary, not
  just a sentence in this document: the server is a mail slot, not a judge, identical to
  how `POST /approvals/{run_id}` already behaves today (`SURFACE_INVENTORY.md`'s note
  that the existing route "never itself evaluates whether the decision is an approval").
- Returns, `202`, immediately after the file write, before the pipeline subprocess has
  necessarily noticed it (the subprocess polls every 2 seconds per
  `_make_file_operator_handler`'s `poll_s`, so there is a real gap between "recorded" and
  "acted on"):
  ```
  {"run_id": "20260910_140000__a1b2c3",
   "recorded": true,
   "decision": "APPROVE",
   "rationale": "checked against the vendor's own deprecation notice",
   "decided_at": "2026-09-10T14:05:41+00:00",
   "run_state": "awaiting_approval"}
  ```
  This is the second governance constraint: the response says `"recorded": true` and
  echoes `run_state` as it stood the instant this write completed — still
  `"awaiting_approval"`, because the pipeline has not yet had the chance to poll, read,
  evaluate, and act. The response never says `"approved"`, never says `"accepted"` in a
  way that could be read as a verdict, and does not itself flip `run_state` to
  `"running"` or `"stopped"` as a side effect of this call — that would be the server
  claiming a governance outcome it did not decide. A caller who wants to see the *effect*
  of the decision (whether the run resumed, and if it resumed which way the gate went)
  polls `GET /runs/{run_id}` afterward, exactly like any other state change on this
  surface; this route's own response only confirms the write, truthfully, and nothing
  more.
- Status codes: `202` (recorded), `404` (malformed `run_id`, or no pending approval for
  it), `400` (`decision` missing or empty).
- Why: this is the gap the operator named. A person must be able to unblock a run
  through the API the caller is already using, not by reaching the server's filesystem;
  this route is the one write in the whole surface that can change a stalled run's
  future without the server making the governance call itself.

### `GET /health`

- Unchanged in every respect from today: ungated, returns
  `{"status": "ok", "version": ..., "backend_profile": ..., "default_review_mode": ...}`.
- Status codes: `200` only.
- Why: nothing about it was found overlapping, ambiguous, or in need of redesign; kept
  as-is, still the one ungated liveness probe.

### `GET /console`

- Out of scope per decision four. Left as a placeholder entry only so the full 11 or
  so routes of the deployed server are all accounted for somewhere in this document; not
  redesigned, not renamed, not discussed further here. If the console itself is later
  redesigned, this route's shape (an ungated static-HTML server) will need its own pass.

## Route count

Twelve routes replace eleven: `/runs` (POST, GET), `/runs/{run_id}` (GET),
`/runs/{run_id}/cancel` (POST), `/runs/{run_id}/findings` (GET),
`/runs/{run_id}/pairs` (GET), `/runs/{run_id}/deliverables` (GET),
`/runs/{run_id}/log` (GET), `/runs/{run_id}/approval` (GET, POST), `/approvals` (GET),
`/health` (GET), `/console` (GET, unchanged, out of scope). The count grows by one
route (cancellation, wholly new) despite two routes merging away (`/queue` folded into
`/runs`), because the design also splits the single "am I awaiting approval" question
into a run-scoped read (`GET /runs/{run_id}/approval`) that did not exist as its own
thing before, on top of the retained cross-run list. `POST /runs/{run_id}/approval`
occupies the same path today's `POST /approvals/{run_id}` would have moved to, but is
not a rename of it: see that route's entry above for why its behavior is new, not
carried over.

## Mapping: every current route to what replaces it

| Current route | Replaced by | What changed, and why |
|---|---|---|
| `POST /submit` | `POST /runs` | Renamed only; same fields, same validation, same rejection reasons. `202` becomes `201` (see that route's entry) — a status-code correction, not a behavior change. |
| `GET /status/{run_id}` | `GET /runs/{run_id}` | Expanded, not renamed-only. Gains `state`/`outcome`/`stop_reason` (replacing the single ambiguous `status` string), `documents[]` (new), `log_url` (new). This is the route decision one is built on. |
| `GET /findings/{run_id}` | `GET /runs/{run_id}/findings` | Renamed only, for path consistency under the run resource. No behavior change. |
| `GET /pairs/{run_id}` | `GET /runs/{run_id}/pairs` | Renamed only, same reason. No behavior change. |
| `GET /queue` | `GET /runs` | Merged away. `/queue` and `/runs` returned byte-identical bodies today (`SURFACE_INVENTORY.md` Question a); keeping both was already acknowledged in the current code as deliberate duplication for a historical reason (naming a past spec's acceptance checks) that decision three explicitly says no longer has to be honored. |
| `GET /results/{run_id}` | `GET /runs/{run_id}/deliverables` | Renamed, and its completion gate loosened (see that route's entry): today's hard `400` before `status == "completed"` is replaced by a per-document partial-zip answer, now that `documents[]` on the status route makes "which documents are actually ready" a real, checkable fact instead of an all-or-nothing flag. |
| `GET /console` | `GET /console` | Unchanged; out of scope per decision four. |
| `GET /health` | `GET /health` | Unchanged. Nothing about it needed to change. |
| `GET /runs` (STEP 6 name) | `GET /runs` | Merged with `/queue` into one list route; see the `/queue` row above. |
| `GET /approvals` | `GET /approvals` | Shape enriched: each entry gains `message`, `default_on_timeout`, `timeout_at` alongside the unchanged `topic`/`payload`/`asked_at`, matching the `pending_approval` object added to `GET /runs/{run_id}`. |
| `POST /approvals/{run_id}` | `POST /runs/{run_id}/approval` | Not a rename. Moved under the run resource and rebuilt to satisfy the operator's two governance constraints: the response now says `"recorded": true` rather than echoing `decision` as if it were a verdict, returns `202` instead of `200` to signal the pipeline has not yet acted on it, and its own entry above states explicitly that the route still never evaluates the decision. This is the route that closes the gap named directly by the operator: today no route in the surface lets a caller answer a pending approval in a way the response itself confirms was recorded, as distinct from approved. |
| *(none — new)* | `POST /runs/{run_id}/cancel` | Wholly new. Decision two. |
| *(none — new)* | `GET /runs/{run_id}/log` | Wholly new. Closes a gap `SURFACE_INVENTORY.md` named directly: no route served this file before. |
| *(none — new)* | `GET /runs/{run_id}/approval` | New as a run-scoped read; the data already existed (via `GET /approvals`, filtered client-side) but not as its own addressable answer to "is this specific run waiting on me." |

## Calling sequence: running a review start to finish

1. `POST /runs` — multipart upload of case files plus the sidecar, `task=review`.
   Returns `201` with `run_id` and the resolved `task`/`sensitive`/`review_mode`.
2. Poll `GET /runs/{run_id}` on whatever interval the caller chooses. Each response is
   self-sufficient: `state` says queued/running/awaiting_approval/stopped/cancelled;
   while running, `progress` and `counters` move; `documents[]` shows which individual
   documents have already finished and where.
3. If a governed decision comes up mid-run, `state` becomes `"awaiting_approval"` and
   `pending_approval` on that same object carries the question, the structured detail,
   and what happens if nobody answers — the caller does not need a second call to know a
   decision is needed or to understand it. A caller (or the console) branches on `state`
   here specifically: `"running"` means keep showing progress and keep polling on the
   same cadence; `"awaiting_approval"` means stop expecting progress and show a decision
   control instead, because nothing further will happen until one. The caller answers
   with `POST /runs/{run_id}/approval` (or reads the identical object in isolation via
   `GET /runs/{run_id}/approval`, useful for a caller that only tracks pending
   approvals and not full run status). The response to that `POST` confirms only that
   the decision was recorded, not that it was approved (see that route's own entry); the
   caller returns to polling `GET /runs/{run_id}` to see `state` leave
   `"awaiting_approval"` once the pipeline subprocess has actually picked the decision up
   and acted on it.
4. Once `GET /runs/{run_id}` reports `state: "stopped"`:
   - if `outcome: "succeeded"`, call `GET /runs/{run_id}/deliverables` for the zip, or
     `GET /runs/{run_id}/findings` / `GET /runs/{run_id}/pairs` for the structured
     records, using `documents[].deliverables_path` to know which per-document folders
     exist inside the zip.
   - if `outcome: "governance_stop"`, `stop_reason` on the same object already explains
     which gate stopped it and why; no further call is needed to understand that (this is
     the point of decision one).
   - if `outcome: "crashed"` or `"timed_out"`, `stop_reason.detail` carries the failure
     detail; `GET /runs/{run_id}/log` is available for the full trace if the caller wants
     more than the summary.
5. At any point before step 4, `POST /runs/{run_id}/cancel` stops the run; the next `GET
   /runs/{run_id}` reflects `state: "cancelled"`.

Five steps (submit, poll, optionally decide, read outcome, optionally cancel), against
today's: submit, poll `/status`, separately poll `/approvals` to notice a pending
decision (nothing on `/status` today points at it), decide, poll `/status` again for
`exit_code`, then separately call `/results` and get a `400` if the completion check was
wrong, then separately call `/findings` and `/pairs` if the structured data was wanted
too. The new flow removes two of the previously-separate calls (spotting a pending
approval, and guessing whether `/results` will succeed) by folding their answers into the
one status object.

## What the console will have to change (named, not built)

- Every `fetch()` call target changes: `/submit` → `/runs`, `/status/{id}` (was never
  called by the console) is irrelevant, `/runs` and `/queue` both existed as console-used
  and console-unused names respectively and collapse to one, `/approvals/{run_id}` POST
  → `/runs/{run_id}/approval` POST.
- `refreshRuns()`'s row rendering (`console.html:143-165`) reads `j.status` today for
  `statusClass()`; it must be rewritten to read `j.state` and `j.outcome` instead, and
  `statusClass()`'s three hand-maintained arrays (`console.html:135-141`) can be deleted
  entirely in favor of a four-way switch on `outcome` plus a `"queued"`/`"running"`/
  `"awaiting_approval"` branch on `state` — simpler than today's array-membership
  checks, but a rewrite, not a find-replace. The `"awaiting_approval"` branch is new
  behavior, not just a new label: today's console shows every non-terminal run the same
  way (a status word in a table cell); this design requires it to show something
  actionable instead — decision two's cancel button, described two bullets below, needs
  the same row-level distinction, since cancelling a run that is merely running and
  cancelling one that is stalled waiting on a person are the same call
  (`POST /runs/{run_id}/cancel`) but a different thing for the operator to be looking at
  when they press it.
- The log column (`console.html:152`, `94-98`) currently displays a constructed,
  unfetchable path with a note telling the operator to open it on the server's own
  filesystem. With `GET /runs/{run_id}/log` now real, this becomes an actual link or
  fetch-and-display; a genuine feature addition to the console, not just a rename.
- A cancel button/action needs to be added to the runs table; today there is no UI
  surface for it at all, since the capability did not exist.
- `refreshRuns()`'s fallback `data.jobs || data.runs` (`console.html:149`) can be
  simplified to just `data.runs`, since the new `GET /runs` always uses that key and the
  ambiguity that fallback was hedging against no longer exists.
- The submit handler (`console.html:206-230`) needs its target URL changed and should
  start sending `review_mode` (today it never does, per `SURFACE_INVENTORY.md` Question
  e), though sending it was already possible before this redesign and is not caused by
  it — worth doing at the same time since the console is being touched anyway, but not a
  requirement of this design.
- The approvals table (`console.html:167-201`) changes more than its POST target.
  `refreshApprovals()`'s read side (`console.html:167-201`) currently reads
  `a.run_id`/`a.topic`/`a.asked_at` directly off each list entry; under the new
  `GET /approvals` shape those move one level deeper, under `a.pending_approval.topic`
  etc., and the console gains access to `a.pending_approval.message` (a sentence it does
  not currently show at all — today's table displays only the raw `topic` string) and
  `a.pending_approval.timeout_at`, which it could use to show a countdown that has no
  equivalent today. The POST target itself moves (`/approvals/{run_id}` →
  `/runs/{run_id}/approval`) and the button handlers (`console.html:180-189`) must stop
  treating the response as a verdict: the handler today does nothing with the response
  body beyond calling `refreshApprovals()`/`refreshRuns()` on any resolved promise, so
  this is a small change, but a real one — the new response's `"recorded": true` is not
  interchangeable with the approval actually having taken effect, and the console's
  refresh-after-post pattern is what makes that distinction visible to the operator,
  since the row will still show `"awaiting_approval"` for a couple of seconds after the
  click until the pipeline subprocess's own poll catches up.

This is the cost of decision three (freely renaming/merging) landing on the one existing
caller: every route the console touches changes its URL, and the status-row rendering
logic is a genuine rewrite, not a search-and-replace. Nothing here is built; this is the
inventory of what would need to change, for the operator to weigh against the cleaner
surface.

## What the current server does that this design would lose

- **The `blocked` exit-code ambiguity is resolved by asking the pipeline subprocess to
  report more than it does today**, not by anything the server alone can infer. The
  design's `stop_reason.code` split (`blocked_redaction_gate` vs.
  `blocked_draft_generation`) requires the pipeline to communicate which one happened
  (today it does not; the console's own note says to check the log tail,
  `SURFACE_INVENTORY.md` Question d). Until that upstream change exists, this design's
  `stop_reason` for exit code 5 can only carry the same ambiguity forward under a new
  name, which would make the "complete status" promise (decision one) false for exactly
  this one case. This is flagged as a real gap between what this document promises and
  what is buildable without also touching the pipeline side, not glossed over.
- **The literal `202 Accepted` semantics are gone.** Today's `/submit` returning `202`
  is arguably more correct HTTP for "the work has not happened yet, poll for it";
  `POST /runs` returning `201 Created` asserts the run resource itself now exists and is
  readable, which is true, but a caller relying on `202`'s specific "retry-after" framing
  loses that signal (no route in either design returned a `Retry-After` header, so this
  is a small, honest note rather than a functional loss).
- **No filter or pagination on `GET /runs` is proposed**, matching today's `/queue` and
  `/runs` (SURFACE_INVENTORY.md's "cannot currently do" list named this gap already, and
  this design does not close it — every run, unfiltered, oldest-first, same as today).
  As the number of runs grows this remains exactly as unscalable as it is now; the design
  does not make it worse, but it also does not fix it, and decision three's "remove and
  merge freely" was not read as license to add unrequested filtering.
- **`GET /runs/{run_id}/deliverables` no longer gives a caller a clean single boolean
  ("is this run's output ready, yes or no") the way today's `400`-until-`completed` gate
  did.** The loosened, partial-zip behavior (see that route's entry) is more useful but
  also more ambiguous: a caller must now inspect `documents[].status` to know whether the
  zip it just received is the complete output or a partial one, where today a `200`
  always meant complete. This is a real trade, not a pure improvement, and is named as
  such rather than presented as strictly better.
- **The distinct governance codes lose one bit of the original exit-code mapping's
  compactness.** Today, six governance/terminal statuses map from exactly six integer
  exit codes with no other state needed (`_EXIT_STATUS_MAP`). The new `state`/`outcome`/
  `stop_reason` triple carries strictly more information but is three fields instead of
  one string; any caller that wants to persist or log a single compact status value must
  now choose which of the three fields, or some derived combination, to use for that,
  where today there was one unambiguous answer (`status`).
- **`rationale` on a decision remains free text with no validation**, same as today; this
  design does not add any structure to it, so nothing is lost there, but it is also not
  gained — worth noting since a reader might expect "the redesign fixed everything," and
  this is one place it deliberately did not touch anything.
- **`POST /runs/{run_id}/approval` cannot tell a caller whether the decision was
  accepted, only that it was written down.** This is a direct consequence of the first
  governance constraint (the server never evaluates the decision) and is stated here as
  a genuine limit, not a defect: a caller who wants to know whether `decision: "APPROVE"`
  actually caused the run to resume must make a second call, `GET /runs/{run_id}`,
  after this one. That second call is unavoidable under the constraint as given — an API
  that both records-without-judging and reports-the-judgment in the same response would
  have to evaluate the decision to know what to report, which is exactly what the
  constraint forbids.
- **A decision can be recorded for a run that has already stopped by other means**
  (the run timed out, or was cancelled, in the roughly-2-second window between the
  pipeline's polls). The route as designed does not check the run's live `state` before
  writing `approval_decision.json` — matching today's behavior (`SURFACE_INVENTORY.md`'s
  description of the current route performing no such check either) — so this is not a
  new gap this design introduces, but it is now more visible: the response's
  `"run_state": "awaiting_approval"` field could be stale by the time the caller reads
  it, in that specific race. The response is honest about what it observed at write
  time; it does not claim to be current a moment later.

## Decisions recorded from the operator's review

- **A paused-for-approval run gets its own `state`, `"awaiting_approval"`, distinct from
  `"running"`.** `"running"` means the run is making progress and will finish
  unattended; `"awaiting_approval"` means it is stalled and will not finish until a
  person decides something through `POST /runs/{run_id}/approval`. This closed the
  design fork this document originally left open: `state` is now a five-value set
  (`queued` / `running` / `awaiting_approval` / `stopped` / `cancelled`), and the
  distinction is visible directly on `GET /runs` (the list route), not only on a
  per-run detail call, so the console can show a decision control on exactly the rows
  that need one without polling each run individually.
- **`POST /runs/{run_id}/approval` was added** to close the gap that nothing in the
  surface let a caller answer a pending approval; see that route's full entry above.
  Built to the two stated governance constraints: it writes the decision to the same
  file the pipeline already polls and evaluates nothing itself (first constraint), and
  its response says `"recorded": true` with the run's state as observed at write time,
  never a claim that the decision was approved (second constraint).
- **The `pending_approval` object was added to `GET /runs/{run_id}`** (and, in the same
  shape, to `GET /runs/{run_id}/approval` and each entry of `GET /approvals`), carrying
  `topic`, `message`, `payload`, `asked_at`, `default_on_timeout`, and `timeout_at` — what
  is being asked, in both prose and structured form, and what happens on no action —
  so a caller learns of a pending decision from the same call that reports the run is
  waiting, per the "no second call" decision this document was built on in the first
  place.
