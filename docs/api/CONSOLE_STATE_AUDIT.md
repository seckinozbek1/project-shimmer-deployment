# Console state audit: every state/outcome against what may or may not exist

Read only. No code changed to produce this. Traced directly from `scripts/ui/console.html`
(`renderDetailBody`, `nextActionSentence`/`nextActionSentenceHuman`, `renderApprovalBlock`,
`renderDocuments`, `renderArchiveSection`, `loadFindings`, `loadPairs`) against
`scripts/server.py` (`_run_record`, `_documents_for_run`, `_pending_approval_for`, the
`findings`/`pairs`/`deliverables` routes) to establish what the server can actually return
for each combination, not assumed from the UI alone. Where a combination is reachable only
by direct evidence in the pipeline/server code (not rendered against a live fixture), that
evidence is cited; where it cannot be reached in practice, that is stated and why.

## The five things tracked per combination

- **Documents**: `run.documents[]`, non-empty once phase 5.5 has paired at least one unit
  for at least one document (`_documents_for_run`, keyed off the pairing map, not off
  `state`/`outcome` at all).
- **Findings**: whatever `GET /runs/{run_id}/findings` would return right now, from
  `<run>/logs/agent_bus.jsonl` (`_bus_findings`). Has no state/outcome guard on the server
  side; a Finding record can exist the moment an agent posts one, at any phase, and stays
  on the bus regardless of how the run later ends.
- **Pairing map**: whatever `GET /runs/{run_id}/pairs` would return right now, from
  `<run>/audit/pairing_map.json`. Same story: written once phase 5.5 pairs anything, kept
  regardless of what happens afterward.
- **Archive**: whether `GET /runs/{run_id}/deliverables` would return a zip (200) or 404
  (`server.py`'s own check: 404 when `deliverables/` does not exist or is empty).
- **Pending approval**: `run.pending_approval`, non-null only while `state ==
  "awaiting_approval"` (`_pending_approval_for` is only even called in that state,
  `_run_record`'s own line).

## The governing fact that produces every contradiction below

**The console fetches findings and the pairing map ONLY when
`state === "stopped" && outcome === "succeeded"`** (`renderDetailBody`, the
`loadFindings(run.run_id); loadPairs(run.run_id);` call, gated on that exact condition, no
other call site exists for either). But the SERVER has no such gate: findings and the
pairing map are written to disk (and answerable by the API) the moment phase 5.5 produces
them, independent of what the run does afterward. A run can crash, time out, get stopped by
a governance rule, get cancelled, or sit awaiting approval, AFTER phase 5.5 has already
posted real findings and built a real pairing map for one or more documents. In every one of
those cases the console never asks the server whether findings or a pairing map exist: it
assumes not, because the run did not end in `succeeded`.

This is not a promise of something absent; it is the opposite defect, a **silent hide** of
something that may genuinely be there. The reviewer view and the developer view hide it
identically, because both call the same gated fetch (or rather, neither calls it outside
that one condition).

## Reachability of the outcomes that carry this gap

- **`crashed` or `timed_out` with prior findings**: reachable. Phase 5.5 runs before phase 6
  (synthesis) and phase 7 (audit synthesis); a crash or timeout in EITHER of those later
  phases, or in phase 6.5 (editorial review), or from the run timeout firing at any point
  after 5.5 completed, leaves phase 5.5's findings and pairing map on disk untouched. Not
  fabricated for this audit: this is exactly the shape `_bus_findings`' own docstring
  describes ("a Finding record can exist the moment an agent posts one"), and nothing in
  `_run_job` clears the bus or the pairing map on a later failure.
- **`governance_stop` with prior findings**: reachable the same way, for the same reason,
  for three of the four governance codes (`stopped_model_approval`, `stopped_redaction_gate`,
  `blocked`) which can all fire after phase 5.5; not reachable for
  `refused_sensitivity_layer_inactive`, which refuses to start the pipeline subprocess at
  all (`server.py`'s own comment on that override), so phase 5.5 never runs and no findings
  can exist for that one code specifically.
- **`cancelled` with prior findings**: reachable. `POST /runs/{run_id}/cancel` terminates
  the subprocess at whatever point it has reached; if that point is after phase 5.5, the
  findings and pairing map already written survive the termination (cancelling "deletes
  nothing on disk," `_run_record`'s own docstring).
- **`awaiting_approval` with prior findings, concurrently with a DONE document**: reachable.
  `--max-concurrent-docs` (default 4, `server.py:671`) runs multiple documents concurrently
  within one submission; a governed pause on one document's processing (a deprecated-model
  swap, README's own example) can fire while a SIBLING document has already completed phase
  5.5 and even finished entirely, appearing in `documents[]` with `status: "done"` and a
  working per-document download link, while the run's overall `state` is still
  `awaiting_approval`.
- **Not reachable**: `queued` with any of these five present. Nothing has run yet; the
  server can produce none of them before the subprocess starts.

## The table

State/outcome combinations first, then within each the documents/findings/pairing-map/
archive/approval combinations that combination can actually produce, per the reachability
notes above. "�" marks something the interface asserts or implies that is not actually
there; "hidden" marks something real that exists but is never shown or fetched.

| # | State / outcome | Documents | Findings (on disk) | Pairing map (on disk) | Archive | Pending approval | Reviewer view says | Developer view says | Contradiction |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `queued` | none | none | none | 404 | none | "Waiting to start... Nothing to do." No Documents/Archive section shown at all. | "Waiting for the run ahead of it to finish." Same, no sections. | None. Nothing claimed, nothing to hide; not reachable any other way. |
| 2 | `running`, no documents yet | none | none | none | 404 (Archive not shown; gated to stopped/cancelled) | none | "In progress: {phase}." Documents section shows "None finished yet..." | Same shape, different wording. | None. |
| 3 | `running`, one document done | 1 done, rest in_progress | possible (phase 5.5 already ran for the done document) | possible | 404 (Archive still not shown, correctly, since state isn't stopped/cancelled) | none | Per-document Download link shown for the done document (correct, `renderDocuments` isn't outcome-gated). Findings/pairing map for that document: never fetched, never mentioned. | Same. | **Hidden.** A live run that has already produced real findings for a finished document shows none of them. The status line never says "partial findings exist for finished documents"; a reviewer has no way to know from this screen that anything is readable yet. |
| 4 | `awaiting_approval`, no documents finished yet | none | none or possible per the phase the paused document reached | same | not shown (state isn't stopped/cancelled) | present | Status box: short "Paused: needs your decision" (correctly generic, fixed for the earlier duplication bug). Approval block: full detail. No Documents heading at all (falls through every branch in the Documents if/else chain: not `.length`, not `stopped`/`cancelled`, not `running`). No Phases/Steps heading either (that section is gated to `running`/`queued` only, `renderDetailBody`'s own condition; `awaiting_approval` is internally still `status: "running"` on the server, `_state_for_job`'s own logic, so `run.progress` is populated and simply never read here). | Same Documents gap, same missing Phases/Steps section. | **Inconsistent, not false**, on Documents (see below). **A real, separate gap** on phase visibility: a reviewer deciding Approve/Deny has no way to see which phase the run had reached when it paused, even though that data exists on the same run record every other live state already reads. `running` with zero documents explicitly says "None finished yet"; `awaiting_approval` with zero documents says nothing, the heading itself is absent. Not a promise of something absent, but an unexplained asymmetry between two live states that should read the same way when both have nothing yet. |
| 5 | `awaiting_approval`, a SIBLING document already done | 1+ done, 1 paused/in_progress | real, for the done document | real, for the done document | not shown (state gate) | present | Done document's Download link shown and works. Findings/pairing map for it: never fetched. Status box and approval block say nothing about the finished document's results. | Same. | **Hidden**, same shape as #3, worse in practice: the reviewer is actively asked to make a decision (Approve/Deny) while real findings from a sibling document sit unmentioned one section away. |
| 6 | `stopped` / `succeeded`, documents present (the common case) | present | present (or empty; both legitimate) | present (or empty) | 200, real zip | none | "Finished. Start with the findings below, or download the full archive." Findings/pairing map fetched and shown; archive offered. | Same shape. | None. This is the one combination both `loadFindings`/`loadPairs` and the archive check were built for, and it is the only one that gets them. |
| 7 | `stopped` / `succeeded`, documents empty | none | none (nothing to have produced them) | none | 404 | none | "Finished, but nothing was checked... nothing to read below and nothing to download." (fixed this session) | Same shape, own wording. Archive section: "No deliverables exist yet for this run." (fixed this session) | None, as of the fix approved and committed this session. Recorded here to close the row, not because it is still open. |
| 8 | `stopped` / `governance_stop`, no prior findings (the common case: stopped before phase 5.5, or `refused_sensitivity_layer_inactive` which never starts) | none | none | none | 404, but Archive section still renders (gated to `stopped`/`cancelled`, not to whether anything exists) | none | "Stopped on purpose, before finishing... Nothing you submitted was lost." Archive section offers a download button. | Same shape (detail box adds the raw code + `stop_reason.detail`). Archive section, same button. | **False promise.** `renderArchiveSection`'s own `anyDone` check (added this session) only looks at `run.documents`; with `documents` empty, `anyDone` is false, so the fixed code already shows "Nothing to download yet" here too, correctly, not a button. Recorded because it was the second bug fixed this session, not because it is still open, but flagging: this depends on the SAME fix as row 7, and the two share one code path (`renderArchiveSection`), so this row is only closed because that fix landed for both reasons at once, not because governance_stop was separately audited before now. |
| 9 | `stopped` / `governance_stop`, WITH prior findings (phase 5.5 ran, then a later phase paused for a model-gate decision that timed out, `stopped_model_approval`/`stopped_redaction_gate`/`blocked`) | present (at least the documents phase 5.5 reached) | real | real | 404 unless a document also finished (possible, see #5's concurrency logic); Archive section correctly reflects whichever is true, per the row 8 fix | none (the state is `governance_stop`, not `awaiting_approval`; the approval WAS asked and its window closed unanswered) | "Stopped on purpose... Nothing you submitted was lost; if you resubmit, the review restarts from the beginning." No mention that findings already exist. Documents section shows whichever documents got as far as `done`, with working links. Findings/pairing map: never fetched. | Same gap. | **Hidden.** "The review restarts from the beginning" is not literally false (a resubmission IS a fresh run) but reads as "nothing survives," when real findings from before the stop are sitting on the bus and answerable via the API, just never surfaced by this screen. |
| 10 | `stopped` / `crashed`, no prior findings | none | none | none | 404, Archive section correctly says nothing to download (row 7/8 fix covers this too) | none | "The review stopped before it finished, because of a fault in the system, not in your document." | "The run did not finish. See the detail below, or the full log." | None. |
| 11 | `stopped` / `crashed`, WITH prior findings (crashed in phase 6, 6.5, 7, or 9, after 5.5 had already run) | present for whichever documents got that far | real | real | depends, same as #9 | none | "The review stopped before it finished... Nothing you submitted was lost." No mention that findings exist. | "The run did not finish. See the detail below, or the full log." Same gap; "the full log" points at raw stdout text, not at the structured findings the API can already serve. | **Hidden**, same shape as #9. Arguably the sharpest case: a crash specifically invites the reader to think nothing usable came out of the run, when partial, real, typed findings may already exist and be one API call away. |
| 12 | `stopped` / `timed_out`, WITH prior findings | present for whichever documents got that far | real | real | depends, same as #9 | none | "The review did not finish in time... You can submit it again." No mention of existing findings. | "The run did not finish. See the detail below, or the full log." Same gap. | **Hidden**, same shape as #11. |
| 13 | `cancelled`, cancelled before it started | none | none | none | 404, Archive section correctly empty (covered by the row 7/8 fix, since `cancelled` is in the same gate as `stopped`) | none | "Cancelled, at your request. It had not started yet." | "Cancelled: cancelled before it started." | None. |
| 14 | `cancelled`, cancelled while running, no prior findings | none | none | none | 404, correctly empty | none | "Cancelled, at your request. It had already begun; whatever finished before the cancellation is still available below." | "Cancelled: cancelled while running." | **Slightly overstated, reviewer view only.** "Whatever finished... is still available below" is true of DOCUMENTS (the Documents section is not outcome-gated) but not of findings or the pairing map for those documents, which are never fetched for a `cancelled` run at all. The sentence's "available below" reads as a blanket claim; it is only true for the document-level download, not for the structured review of what that document found. |
| 15 | `cancelled`, cancelled while running, WITH prior findings for a finished document | 1+ done | real | real | 200 if any document is `done` (the row 8 fix's `anyDone` check correctly offers the button here) | none | Same sentence as #14, now genuinely wrong in a sharper way: "whatever finished... is still available below" is read naturally as covering everything about that document, including what was found, and the archive really is downloadable this time, which makes the missing findings/pairing map feel like an oversight rather than a boundary, since the reader just confirmed the archive claim was true. | Same underlying gap; no equivalent sentence overstates it, the developer view's "cancelled while running" line makes no claim about availability either way. | **Hidden, and the reviewer-view sentence actively invites the wrong inference here**, more than in row 14: the archive being real makes the implicit "everything is here" reading more convincing, not less. |

## Combinations named but not separately rowed

- **`awaiting_approval` with a pending approval AND zero payload/message content**
  (`pa.message`/`pa.topic` both empty, `pa.payload` empty): `approvalDetailHuman` returns an
  empty string; the Approve/Deny buttons would render with no explanation above them, in the
  reviewer view. Not a promise/hide contradiction in the sense asked for (nothing claims
  content exists), but worth naming: this shape depends on what a governed pause is ALLOWED
  to omit, which is a server/pipeline question this audit did not chase down, since it is a
  completeness gap, not a stated-vs-actual one.
- **`refused_sensitivity_layer_inactive`** is the one governance code that can never carry
  prior findings (see reachability above); it is otherwise identical to row 8.
- **Wide review mode** (`review_mode: "wide"`) changes what `pairs_planned`/
  `pairs_arithmetic_only` mean (the latter is `null`) but does not change anything in this
  table: the pairing map and findings routes behave identically regardless of mode, and
  `pairBarHtml` already returns nothing in wide mode (verified earlier this session, not
  re-verified here since it is unrelated to the promise/hide question).

## Summary

Three distinct defects, not one:

1. **The empty-succeeded contradiction** (rows 7, 8, 10, 13, 14 where nothing exists): fixed
   this session, in both views, for both the status sentence and the archive button. Closed.
2. **The hidden-findings gap** (rows 3, 5, 9, 11, 12, and the sharper reading of row 15): NOT
   fixed. The console only ever asks the server for findings and the pairing map when
   `state === "stopped" && outcome === "succeeded"`, but the server can and does produce
   real findings and a real pairing map for a run that later crashes, times out, gets
   stopped by a governance rule, gets cancelled, or is sitting paused for an approval, as
   long as phase 5.5 ran before whatever happened next. In every one of those cases, real
   structured findings exist, are answerable by `GET /runs/{run_id}/findings` and
   `GET /runs/{run_id}/pairs` right now, and the console never asks. This is the more
   serious of the two defects: it is not a wrong sentence, it is real information a person
   making a decision (resubmit? escalate? trust the partial result?) never sees on the one
   screen built to show it to them.
3. **The missing phase for a paused run** (row 4): NOT fixed. `awaiting_approval` is
   internally still `status: "running"` on the server (`_state_for_job`), so `run.progress`
   is populated exactly as it is for `running`, but `renderDetailBody` only renders the
   Phases/Steps section for `state === "running" || state === "queued"`, never for
   `awaiting_approval`. A reviewer deciding whether to Approve or Deny cannot see how far
   the run had gotten when it paused, data the server already sends on every response for
   this state and the console already knows how to render for the state right next to it.

Nothing has been changed in `scripts/ui/console.html` to produce this document.
