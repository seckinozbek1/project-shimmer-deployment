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

---

## 7. Gate check 252 fails on the Dockerfile's own text (found at loop S0, 2026-10-27)

**What it is.** Check 252 requires the exact Dockerfile line `RUN python scripts/ship_gate.py`.
`Dockerfile:153` reads `RUN /opt/shimmer-runtime/bin/python scripts/ship_gate.py`, so the check
fails on the host whatever the interpreter. Inside the image there is no Dockerfile, so the check
passes there.

**Evidence.** The loop's S0 baseline (`docs/loop/GATE_BASELINE.md`), and the check's source
(`scripts/verify_session1.py`, `check_252_document_dates_have_an_executed_shipping_ruling`). The
earlier comparison record put this red down to the missing `fastapi`; it is not.

**Why it was left.** S0 changes no product file. The Dockerfile is changed in S10 or S11.

**What would settle it.** In the stage that changes the Dockerfile, either restore the exact line
(if the image's `python` resolves to the runtime environment) or correct the check under the
loop's evidence rule for gate checks, with its own neutralise, fail, restore, pass proof.

---

## 8. (Closed 2026-10-27, loop S1 commit C3.) Gate check 112 and a log-event name

The event in `scripts/agent_wrapper.py` that check 112 refused (its name contained the word
`prompt`) is now `call_structure_write_error`; no reader used the old name. Kept here only so
item numbers do not shift.

---

## 9. The final-integration side gate rewrites a tracked file (found at loop S0)

**What it is.** `scripts/final_integration_no_generation_gate.py:32` writes
`docs/fix/final_model_integration/no_generation_tests.log`, which is tracked. Running the side
gate changes the working tree (one line differed at S0, a timing figure). Gates are meant to be
non-mutating.

**Evidence.** `git status` after the S0 side-gate run; restored with `git checkout`.

**Why it was left.** It changes no product behaviour, and the loop restores the file after every
side-gate run. Changing the gate's output location is a test-infrastructure change.

**What would settle it.** The gate writing its log to a temporary or ignored folder, with the
tracked log kept as the historical record it is.

---

## 10. A docstring cites the wrong gate check for LAW-III (found at loop S1)

**What it is.** The docstring of `_withheld_audit_agents` in `scripts/pipeline.py` (around line
1440 at the loop's start) says LAW-III enforcement is held by check 148. Check 148 is "tolerant
recovery prefers a populated envelope"; the LAW-III checks are 87 and 127.

**Evidence.** `scripts/verify_session1.py` CHECKS list (entries 87, 127 and 148).

**Why it was left.** Changing a docstring changes the function's pinned code hash, so it goes
through the pinned-baseline path; the loop's S1 stage was told not to change it.

**What would settle it.** The corrected docstring with a pinned-baseline amendment, in the loop's
open-item sweep (S6).

---

## 11. Exit 9 (an unratified INST_FINDER switch) shows as "failed" in the server (found at loop S1)

**What it is.** The pipeline refuses a run with `SHIMMER_INST_FINDER=off` and no ratified
amendment with exit code 9. The server's exit-status map in `scripts/server.py` has no entry for
9 (nor for 8), so the console shows such a refusal as a plain failure.

**Evidence.** The Part 7 lane's trace of `scripts/server.py` (`_EXIT_STATUS_MAP`).

**Why it was left.** `scripts/server.py` was outside the S1 lane's files; the console and its
status labels are loop stage S7's work.

**What would settle it.** A governance status for exit 9 (and a label for 8) in the server and
the console, with its gate check, in S7.

---

## 12. The execution seal does not check the INST_FINDER ratification, and FINAL_STATUS does not state the setting (found at loop S1)

**What it is.** `tools/prepare_ordinary_final_run.py` writes `SHIMMER_INST_FINDER` into the
manifest's environment but does not check, at seal time, that an `off` value is ratified; such a
bundle would refuse only on the rented instance. `tools/analyze_ordinary_final_run.py`, which
writes `FINAL_STATUS.json`, does not yet read `audit/agent_switches.json`.

**Evidence.** The Part 7 lane's report.

**Why it was left.** Both are run-controller and run-report work, which is loop stage S2c (items
3 and 4: the report template and the manifest parameters).

**What would settle it.** A seal-time refusal for an unratified `off`, and the setting in the
report template, both in S2c.

---

## 13. Two narrow gaps in the staged-archive guard (found at loop S1)

**What it is.** `scripts/guard_secrets.py --staged` reads staged tar and zip archives and refuses
one with a seal manifest or saved model reply inside. Two cases are not covered: bytes after a
valid bz2 or xz stream are skipped by Python's decompressors, so the tar check never sees them;
and a compression format outside the guard's list (`.lz`, `.lzma`, `.Z`) is neither read nor
refused.

**Evidence.** The S1 round-3 fix lane's report (commit `3b864f0`); `docs/THREAT_MODEL.md` names
the second gap.

**Why it was left.** The realistic case, the controller's `.tar.gz` evidence archive, is fully
covered, and S1 had used its three checker rounds (D-016).

**What would settle it.** Refusing any archive with trailing data after its last compressed
stream, and refusing unrecognised compressed suffixes, each with a gate-check case, in the S6
open-item sweep.

## 15. Converted SummEdits data is tracked in the repository (found at loop S4)

- **What it is.** `tuning/auditor_external_relation_v1/` tracks files built from the SummEdits and SummExecEdit releases (for example `examples.jsonl`, `document_registry.jsonl`), from a task before the loop. The loop's rule for third-party data (S4b) says never commit third-party data, raw or converted.
- **Evidence.** `git ls-files tuning/auditor_external_relation_v1`; `docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md`; `docs/fix/AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md` (CC BY 4.0 attribution).
- **Why it was left.** The files predate the rule, carry their attribution and licence, and are a frozen record of a quarantined experiment (TCR-010). Removing them from the tree does not remove them from history, and deleting a frozen record is not the loop's call (H12). SummEdits is rejected for sealed use instead (D-019).
- **What would settle it.** The operator's decision: keep as an attributed record, or remove from the tree and include the paths in the S13 history-rewrite rules.
