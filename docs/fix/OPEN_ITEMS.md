# Open items

Everything found and consciously NOT fixed, with the evidence that found it, the reason it
was left, and what would settle it. Nothing here is authorized, started, or scheduled. An
entry is a record, not a plan.

This file is WRITTEN AT THE END OF EVERY PASS and READ AND REPORTED AT THE START OF EVERY
PASS, before any work is proposed. An item leaves this file when it is fixed, when the
evidence that put it here is shown to be wrong, or when the operator closes it.

What does NOT belong here: work the operator deliberately deferred (that is the roadmap, and
the tuning backlog is in `docs/fix/TUNING_BACKLOG.md`), and anything that is merely undone
rather than found. A thing earns a place here by having been SEEN and PASSED OVER.

---

## 1. The preamble unit adds two fields read from prose that no rule names

**What it is.** `pairing_map.split_units` makes a preamble unit of the text above a
document's first body heading. On the clinical sheet that unit carries the fields `http` and
`two offer`, read out of ordinary prose by the structural label reader. No rule names either
label, so neither reaches a finding, but they sit in the pairing map as if they were declared
fields of the document.

**Evidence.** Run v12's `audit/pairing_map.json`, unit
`u00-returned-result-sheet-batch-review`. The same two labels appear in the v9 fixture
measurements taken when the preamble unit was built.

**Why it was left.** They are inert: no rule pairs on them, so they cannot mint a finding or
an amendment, and the preamble is excluded from `unmatched_findings` so they cannot become a
missing-field report either. Tightening the label reader to reject them is a change to a
reader that every corpus depends on, and the same tightening is entangled with item 6.

**What would settle it.** A measurement across all twelve corpus documents of what the label
reader admits from preamble prose, showing whether a stricter rule (a label must be followed
by a value on the same line, say) loses any real field on any document. That is a
fixture-only measurement; it needs no run.

---

## 2. Every run makes one uncomputable PRACTICE_AUDITOR call on the sheet header

**What it is.** The sheet header pairs with CONV-L03, whose `absence_path` is `judged`, so
every run spends exactly one model call asking a narrow question about a unit where Python
cannot compute an answer. The call returns something, the something is never promotable to an
amendment, and the next run makes the same call again.

**Evidence.** Run v12 `logs/call_evidence.jsonl`, call
`3fcb7361afdb4e1d947e9ac57af23724`, carrying rule CONV-003 (the registry id for CONV-L03) and
the preamble unit. The scorer's false-negative evidence class for the missed fifth entry is
`EVIDENCE_PRESENT_IN_MODEL_PAYLOAD`, which is this call.

**Why it was left.** It is one call, it is honest (the rule genuinely applies to that unit),
and suppressing it would mean suppressing the only path by which that rule could ever be
answered. The waste is real but small, and the alternative is a special case.

**What would settle it.** Either the comma decision in item 6 (which would make the figure
computable and the call unnecessary), or a measurement of how often a judged absence-path call
on a preamble unit produces anything usable across corpora. Neither is started.

---

## 3. Check 256 failed once and has never reproduced

**What it is.** Gate check 256 failed in one session and passed on every run before and since.
The cause was never found. Nothing watches for its return: if it fails again in six months, it
will look like a new failure rather than the second instance of a known one.

**Evidence.** Both logs are kept: the failing run and the immediately following passing run on
an unchanged tree. A probe written to reproduce it (`probe_256.py`, scratchpad) did not.

**Why it was left.** A fault that will not reproduce cannot be fixed, and a guess at the cause
would be a change with no evidence behind it. Recording it was judged better than either
ignoring it or fixing something at random.

**What would settle it.** A second occurrence with its log, which would give two data points
and probably the shared condition. Failing that, an instrumented version of the check that
records its inputs on every run, so the next failure arrives with its own evidence.

---

## 4. The filesystem must be deleted by hand, and the procedure is recorded but untested

**What it is.** `shimmer-filesystem` bills $4.00 a month for as long as it exists. The
provider adapter admits no filesystem endpoint, so nothing in this repository can delete it,
read its size, or confirm it still exists. The deletion obligation and the pre-deletion check
are written down in `docs/DEPLOYMENT_RESOURCES.md`. The console procedure itself is not, and
has never been performed.

**Evidence.** The adapter's allowlist, executed and refused during the v12 pass. Run v12's
`operator_post_cleanup_confirmation.json` records the filesystem as expected-to-persist and
its state as unreadable from this machine.

**Why it was left.** Widening the adapter to a delete endpoint is a larger change than the one
attach field the operator authorized, and a delete endpoint is the most dangerous thing that
allowlist could carry. A by-hand deletion with a written check was judged safer than an
automated one.

**What would settle it.** Either performing the deletion once and recording what the console
actually asks for, or an operator decision that the adapter should carry a delete endpoint
with its own confirmation. Neither is proposed here.

---

## 5. Rehearsal per-polarity directories survive between runs and read as complete

**What it is.** `tools/ordinary_final_rehearsal.py` writes each polarity into its own
directory under `.tmp/rehearsal`. Those directories are not cleared at the start of a run, so
between the moment a rehearsal begins and the moment a given polarity restarts, that
polarity's directory holds the PREVIOUS run's finished artifacts and reads as complete.
Anything inspecting mid-rehearsal can see a stale pass as a current one.

**Evidence.** Observed during the v12 rehearsal: the polarity directories carried v11 contents
until each polarity reached its own restart.

**Why it was left.** The rehearsal's own receipt (`rehearsal.json`) is written at the end and
is not affected, so no reported result was ever wrong. The fault is in what an observer sees
while the rehearsal is running, which mattered once, to me, mid-pass.

**What would settle it.** Clearing each polarity's directory at its start, or stamping each
with the run it belongs to so a stale one is recognisable. Either is small; neither was done,
because the change touches the rehearsal while the rehearsal was the thing being trusted.

---

## 6. The label reader and the comma: measured, refused, and contained

**What it is.** The clinical sheet's per-laboratory result counts are written with a comma
inside the label. The structural label reader does not admit a comma there, so the labels do
not parse, the sum has no addends, and CONV-L03 cannot be computed. This is why the fifth
planted entry is still missed after the preamble unit made the header reachable.

**Evidence.** Measured directly (`measure_comma.py`, scratchpad) and recorded in the UNITS-A
bullet in CLAUDE.md. Run v12's score: recall 4 of 5, the fifth entry's false-negative evidence
class `EVIDENCE_PRESENT_IN_MODEL_PAYLOAD`, so the evidence reaches the model and the failure is
the reader, not reachability.

**Why it was left.** Widening the reader to admit a comma inside a label is a decision that
applies to EVERY corpus, not just this one, and it would be taken here to reach one known
catch on one known document. That is the shape of mistake the domain-vocabulary rule and the
CLASSIFIER-B deletion both exist to prevent. The refusal is deliberate and is recorded in
CLAUDE.md so a later session does not "fix" it as an oversight.

**What would settle it.** A measurement across `benchmark/corpora/` of what a comma-admitting
label reader would gain and lose on documents that were never written with this catch in mind.
If it loses nothing on unseen corpora, the widening becomes an ordinary change rather than a
targeted one.

**Included here deliberately.** This is the one item that is also recorded in CLAUDE.md. It is
repeated because a future session looking for "what did we decide not to do" will look in this
file, and a rule-shaped bullet in an operating contract does not read as an open question.
