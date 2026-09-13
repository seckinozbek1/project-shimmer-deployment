> Historical design/audit record. Current implementation and endpoint names are in the [README](../../README.md#api-and-developer-entry-points) and [routing/UI audit](../fix/ROUTING_UI_AUDIT.md). Old route counts, success wording, write-only ontology claims and success-only findings visibility below are superseded. The console now reads findings/pairs for nonqueued runs, distinguishes process completion from review quality, and shows recorded activation evidence. Rule text is current-registry data, not a historical snapshot.

# Console layout plan: a screen that follows what the run produced

Read only. No code changed to produce this. Written for the two things the operator asked
to see before any build: the empty-section layout (item 5/6), and what an amendment would
look like on screen and cost to show (raised as a design question under item 5, not
approved for building).

## The rule (item 6, restated so the layout below can be checked against it)

Whatever a run actually produced, however partial, is shown, in both views, identically in
presence, differently only in wording. A section disappears only because it is genuinely
empty. It never disappears, and never shows a placeholder apology, because the outcome was
awkward (a crash, a stop, a cancellation). The only asymmetry allowed between the two views
is which words describe the same underlying fact.

## Every section, its true emptiness test, and what changes

The status block, the header, and the Steps ladder are unaffected by this plan; they always
have something to say (a state, a name, a position) and are not conditional sections in the
sense below. Six sections ARE conditional today; each gets one true test, checked once,
against real server fields, not against `state`/`outcome` as a proxy for content:

| Section | Current test (wrong) | Correct test | Source |
|---|---|---|---|
| Documents | `state` branches (stopped/cancelled/running), silent for queued/awaiting_approval (fixed this session to read the same everywhere, but still ALWAYS rendered, even with zero documents) | `run.documents.length > 0` | `run.documents` |
| Findings | fetched only for stopped+succeeded (fixed this session to fetch for every state but queued); heading always renders, "No findings." shown when empty | `findings.length > 0` (from the fetch already happening) | `GET /runs/{id}/findings` |
| Pairing map | same fetch fix as Findings; heading always renders | `documents.length > 0` in the `/pairs` response | `GET /runs/{id}/pairs` |
| Archive | gated to `state===stopped\|\|cancelled`, but always renders a heading (a button, or "Nothing to download yet" since this session's fix) | `anyDone` (already computed this session): at least one document `status:"done"` | `run.documents` |
| Pending approval | gated correctly to `state===awaiting_approval && pending_approval`; already only renders when real | already correct | `run.pending_approval` |
| Log | always renders a "Load log" button for `state===stopped\|\|cancelled`, regardless of whether a log file exists | `run.has_log` (new field, see below): known up front, stated plainly either way, never gated behind a click | `run.has_log` |

## Item 1, the log: fixture gap and a real console bug, both

Traced precisely. `_run_job` (server.py) creates `logs/pipeline_stdout.log` unconditionally
the moment the subprocess starts, before reading any output, so every REAL run that ever got
a subprocess (anything past `queued`) has a log file, even a run that crashed in its first
second. The 404s the operator saw are because five of this session's own test fixtures
(crashed, timed out, both governance stops, cancelled) never write a log file at all,
unrealistic test data, not a real gap in what the pipeline produces.

But the console's handling of a genuine 404 is wrong regardless of the fixture issue: it
shows "Could not load the log (404)" for every failure, never reading the server's own
`detail` (`"no log written yet for this run"`, a real, distinct string the route already
sends). And that wrongness compounds with the layout rule this whole plan rests on, in a way
the first draft of this document did not catch. On a governance stop, a crash, or a timeout
with nothing else to show (no documents, no findings, no archive, all genuinely absent, all
correctly dropped under this plan's own rule), the Log section was the only thing left on
the screen, rendered as a bare "Load log" button that reveals whether there is anything to
read only AFTER it is clicked. The one moment a reader most wants to know whether there is
somewhere to look, the exact moment a governance-stop or crash sentence says "see the log,"
the interface withheld that fact behind an action. That is the silent-absence failure this
document exists to name, reintroduced in the one section meant to explain every other one.

**Corrected: whether a log exists is known and stated up front, in every state, never gated
behind a click.** `_run_record` (server.py) already does an `is_dir`/`rglob` filesystem check
right next to where `log_url` is set (`_documents_for_run`, same function); adding
`record["has_log"] = log_path.is_file()` there costs nothing more than a second, no different
in kind from the other on-disk checks already made every time this record is built. Three
fixes, not two:

1. **Server**: `_run_record` adds `has_log` (`bool`), computed once, alongside `log_url`.
2. **Fixtures**: every terminal-state fixture in `tools/console_preview.py` gets a real,
   short `pipeline_stdout.log`, matching what a real run of that shape would have produced,
   so the preview harness stops lying about this; but the console must be correct even for
   the genuinely logless case (a queued run cancelled before it ever started, for one), so
   `has_log: false` is also exercised by at least one fixture on purpose.
3. **Console**: the Log section always renders, in both views, but its content is decided
   from `run.has_log` at render time, not from a click: `has_log: true` shows the existing
   "Load log" button; `has_log: false` shows the line **"There is no log for this run."**
   directly, no button, since there is nothing a click could reveal. If the button IS shown
   and the fetch somehow still 404s (a race: the file existed when the record was built and
   was rotated or removed before the click, or a genuinely unexpected server error), the
   failure branch reads `detailText(res.body)` (the helper already used everywhere else for
   this) rather than the bare status code, so even that unlikely path states a real reason
   instead of "Could not load the log (404)."

The Log section is still never removed the way Findings/Archive/Pairing map are when they
are empty: `has_log: false` is itself the content of the section, stated plainly, not an
absence of the section. A reader following "see the log" from a crash or governance-stop
sentence learns immediately, without an extra click, whether there is somewhere to look.

## Item 2, the phase 3 dangling reference: closed with a real answer, not a rewrite

Traced `PRODUCTION_AGENTS_PER_DOC` (`PROCESSOR`, `SPEECH_ACT_TAGGER`, `LEGAL_ANALYST`) and
`PRODUCTION_AGENTS_CORPUS_LEVEL` (`ARCHIVIST`, `INST_FINDER`, `CITATION_RESOLVER`) against
their contracts in `config/agent_contracts.json`. For a REVIEW task specifically (the
console's primary audience): `PROCESSOR`'s own contract (`item_kind: "extraction"`,
`draft_text`, `extraction_method`, `claims_referenced`) is a structural breakdown of the
document into sections and claims, not drafting; `LEGAL_ANALYST` checks whether each claim
is grounded and flags a legal mechanism common across the corpus but absent from this
document; the corpus-level agents build an index and resolve citations/institutions. None of
this is "content production" in the sense a reader would assume; genesis.md's own Phase 4
description ("PROCESSOR drafts with all gathered context") describes DRAFT mode, not review,
which is exactly the ambiguity the original gap named.

**Proposed replacement**, task-aware since the two tasks genuinely differ here:
- Review: `"Breaking the document into its parts and checking that its claims are grounded"`
- Draft: `"Drafting the memo from the question and the material gathered so far"`

This closes the gap for real rather than pointing at nothing; `PHASES`'s `human` field
becomes a function of `task`, not a fixed string, the one place in the phase table that
needs to branch on task. The dangling "see the gap noted below" is deleted either way.

## Item 3, CONV-001 vs CONV-A02: a real server gap, not a console-only fix

`_pairs_view` (server.py) only ever reads `p.get("rule_id")` for a paired/rejected entry,
never `source_rule_id`; the operator's own id is dropped before the pairing map response is
built, so no console change alone can recover it. Fix, using the pattern the codebase
already has (`finding_record.source_rule_id_for(rule_id, convention_registry)`, already used
for the identical purpose when a Finding record is built): `server.py` loads
`config/convention_registry.json` (the same file `convention_parser.write_registry` writes,
currently never read anywhere in `server.py`) once, and `_pairs_view` calls
`source_rule_id_for` for each paired/rejected `rule_id`, adding `source_rule_id` to the
entry exactly as `_project_finding` already does for findings. The console then renders
`p.source_rule_id || p.rule_id` for the chip label (the operator's own id when the registry
has one, the registry id as the only honest fallback when it does not, per
`source_rule_id_for`'s own documented empty-string case), in both views, since this was
never a reviewer/developer wording split, it is the same identifier either way.

## Item 4, the rule-text route: approved, two constraints from the operator

`GET /rules/{rule_id}` (top-level, not run-scoped: a rule's text does not vary per run;
querying by whichever id the caller has, registry or operator's own, the route accepts
either and looks up by whichever matches). Reads `config/convention_registry.json` (already
loaded once for item 3's fix, shared) and returns one rule's full record.

**The two constraints, both satisfied by construction, not left to hope:**
- **Displayed by the operator's own id, never the registry number.** The route returns the
  full record (`{id, source_rule_id, category, rule, severity, action, source_file,
  source_location}`, `id` the registry's, `source_rule_id` from the same lookup item 3
  already wires in); the console's rule-link click handler renders the panel headed by
  `source_rule_id || id`, the SAME fallback expression used everywhere else a rule id
  appears on screen after this batch of fixes, so there is exactly one naming rule in the
  whole console, not a third scheme introduced here.
- **An unregistered rule id is a fact, not a silent failure.** A finding or pairing-map
  entry can, in principle, cite a rule id the CURRENT registry no longer has (the registry
  regenerates at BOOT from `input/conventions/`, which could change between when a run
  executed and when someone reads it later). `GET /rules/{rule_id}` 404s with a `detail`
  naming this precisely (`"no rule with this id in the current registry"`, distinct from a
  malformed-id 404), and the console's click handler shows that sentence in the panel
  rather than nothing, so a reader learns something real: the rule this finding cites is not
  in the registry as it stands now, worth knowing on its own.

**Where it appears on screen**: every rendered rule id (a finding's citation parenthetical
in both views, the developer table's Rule column, a pairing-map chip) becomes a click
target opening a small inline panel (not a new route/page, since the identifier is already
in view and a full navigation away from the findings list would lose the reader's place)
showing the rule's own text, severity, and action, or the not-in-registry sentence above.

## Item 5, amendments: one route and one section, not a separate piece of work

Corrected framing, per the operator: this is not a harder question deferred by default, it
is the same shape as the rule-text route approved an hour earlier in this same plan. The
content already exists on disk, structured, and only needs an address. Calling it "harder"
because no route happens to expose it yet was the same mistake item 4 already answered.

The pipeline produces an amendment (a proposed correction, tied to a finding, carrying
`comment` (the human-facing sentence already led by computed figures, refine R2),
`proposed_text` (the corrected line, when a model supplied one) or `null`, `action` (always
`"flag"`, proposing, never auto-applying), `severity`, `convention_ref`/
`source_convention_ref`, `finding_unit_id`/`finding_rule_id` linking it back to its Finding).
It is written to `deliverables/<doc_id>/review_data.json`, rendered into `review_findings.md`
and `tracked_changes.docx`, and is real, structured, and already in every archive download,
right now, for every succeeded run with at least one irregular finding.

**The console never shows it, in either view, anywhere.** A reviewer who wants to see the
correction the system is actually proposing (not just that something disagreed, which is
all a Finding record states) has to download the archive and open `review_data.json` by
hand.

**Where it appears**: not a seventh top-level section. An amendment attaches to the Finding
it was built from (`finding_unit_id`+`finding_rule_id` matches a Finding's `unit_id`+
`rule_id`), so it belongs inside the existing Findings section: each irregular finding that
has a matching amendment gains a "Proposed correction" line directly beneath its own
sentence/row, in whichever wording that view already uses, carrying `comment` (developer:
verbatim; reviewer: the same fold-in pattern `approvalDetailHuman` already uses for
pending-approval payloads) and `proposed_text` when present ("the corrected line would read:
..." in the reviewer view; a labeled field in the developer table). An `ok`-verdict finding
never gets one (amendments exist only for `irregular`, `amendment_from_finding`'s own gate),
so this adds nothing to the majority of rows in a clean run.

**The real cost, stated as a fact, not an estimate:**
- **One new server route.** `GET /runs/{run_id}/amendments`, `_run_record`-adjacent but its
  own endpoint, reading `deliverables/<doc_id>/review_data.json` for every done document and
  returning the flat `amendments` list per document. Same non-mutating, read-only pattern
  `/findings` and `/pairs` already use; no new storage, no pipeline change, nothing written
  that is not already written. (A route addition needs a matching README table row, per
  check 167, same mechanical requirement every route on this branch has already met.)
- **One new console fetch.** Parallel to `loadFindings`/`loadPairs`, joined client-side by
  `unit_id`+`rule_id`, same `isPartial` treatment those already carry: an amendment from a
  document that finished before a later crash is exactly as partial as the finding it
  corrects, and says so the same way.
- **One rendering change.** The per-finding display logic in both `loadFindings`' table
  (developer) and list (reviewer) renderers, adding the one conditional line described above.

No new route category, no new section, no design question left open: this is the same
proportioned change as item 4, described in the same terms, so the decision is a yes or no
on this pass, not a deferral to a future one.

**Not built in this pass, per the operator's instruction to decide but not build it now.**

## What stays exactly as it is

The three-way separation of a crash, a governance stop, and a timeout; the finding
sentences; the no-recorded-basis approval warning. Nothing in this plan touches any of them.
