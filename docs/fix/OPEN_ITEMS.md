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

## 1. The preamble unit adds two fields read from prose that no rule names (issue #1)

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

## 2. Every run makes one uncomputable PRACTICE_AUDITOR call on the sheet header (issue #2)

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

## 3. Check 256 failed once and has never reproduced (issue #3)

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

**Second occurrence (loop S5, 2026-10-28).** The full gate at `loop/s05` `1c4daac` (worktree) failed check 256 with the same message; the check alone on the same tree passed. Reading the check (`scripts/startup_readiness_checks.py`, lines 85 to 157): `forbidden` grows whenever any thread calls `socket.create_connection` or `subprocess.Popen` inside the window, and the message names a model probe whatever the operation was. So the likely shared condition is a thread left running by an earlier check. The instrumented version (operation, thread and caller recorded) is the S6 sweep's.

---

## 4. The filesystem must be deleted by hand, and the procedure is recorded but untested (issue #4)

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

- **Closed (2026-10-30, D-S13 item 1, D-109).** The operator decided the filesystem stays as the warm start for later runs; it is never deleted, it is kept current with the latest asset archive (D-S4), and the final report states its monthly storage cost.

## 5. Rehearsal per-polarity directories survive between runs and read as complete (issue #5)

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

## 6. The label reader and the comma: measured, refused, and contained (issue #6)

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

## 7. Gate check 252 fails on the Dockerfile's own text (found at loop S0, 2026-10-27) (issue #7)

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

**Closed at loop S10 (2026-11-01, commit `49194bc`, lane s10-image, D-165).** The Dockerfile line is restored to exactly `RUN python scripts/ship_gate.py`; the image's `python` is the runtime environment's (`ENV PATH=/opt/shimmer-runtime/bin:$PATH`). Check 252 alone: FAIL before, PASS after; the check was not changed.

---

## 8. (Closed 2026-10-27, loop S1 commit C3.) Gate check 112 and a log-event name

The event in `scripts/agent_wrapper.py` that check 112 refused (its name contained the word
`prompt`) is now `call_structure_write_error`; no reader used the old name. Kept here only so
item numbers do not shift.

---

## 9. The final-integration side gate rewrites a tracked file (found at loop S0) (issue #8)

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

## 10. A docstring cites the wrong gate check for LAW-III (found at loop S1) (issue #9)

**What it is.** The docstring of `_withheld_audit_agents` in `scripts/pipeline.py` (around line
1440 at the loop's start) says LAW-III enforcement is held by check 148. Check 148 is "tolerant
recovery prefers a populated envelope"; the LAW-III checks are 87 and 127.

**Evidence.** `scripts/verify_session1.py` CHECKS list (entries 87, 127 and 148).

**Why it was left.** Changing a docstring changes the function's pinned code hash, so it goes
through the pinned-baseline path; the loop's S1 stage was told not to change it.

**What would settle it.** The corrected docstring with a pinned-baseline amendment, in the loop's
open-item sweep (S6).

---

## 11. Exit 9 (an unratified INST_FINDER switch) shows as "failed" in the server (found at loop S1) (issue #10)

**What it is.** The pipeline refuses a run with `SHIMMER_INST_FINDER=off` and no ratified
amendment with exit code 9. The server's exit-status map in `scripts/server.py` has no entry for
9 (nor for 8), so the console shows such a refusal as a plain failure.

**Evidence.** The Part 7 lane's trace of `scripts/server.py` (`_EXIT_STATUS_MAP`).

**Why it was left.** `scripts/server.py` was outside the S1 lane's files; the console and its
status labels are loop stage S7's work.

**What would settle it.** A governance status for exit 9 (and a label for 8) in the server and
the console, with its gate check, in S7.

- **Closed at loop S7 (2026-11-01, lane `s07-exitcodes`).** `scripts/server.py` maps exit 8 to `refused_multi_round` and exit 9 to `refused_inst_finder_unratified`, both in `GOVERNANCE_STATUSES`, so both reach the `governance_stop` outcome. The console carries a developer and a plain sentence for each, with a Turkish row in `scripts/ui/localization_catalog.js`; `scripts/ui/localization_checks.js` now renders every governance code and requires both rows. Gate check 108 proves the two mappings, reads by AST that `pipeline.py` `main()` returns 9 on the `_inst_finder_startup_guard` refusal and 8 on its two multi-round refusals (and `multi_round_phase.execute` 8 on its own), requires an entry for every constant exit code those return, and removes exit 9's entry and 8's governance membership to show it fails before restoring. The entry above is kept as written.

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

## 13. Two narrow gaps in the staged-archive guard (found at loop S1) (issue #11)

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

**Closed (2026-11-02, loop S11, D-183).** The bz2 and xz tars are decompressed by the guard's
own forward reader: what follows a stream must be another whole stream of the same format, or
the archive is refused as unreadable (gzip already refused non-zero trailing bytes). The
unreadable suffixes now include `.lz`, `.tlz`, `.lzma`, `.Z`, `.taz` and the other common
formats the guard has no reader for. Check 275 has a case for each, each with a neutralisation
(Python's own BZ2File and LZMAFile put back; the suffix list as it was) that passes the archive
unseen, then fails restored. A suffix in no list is still not recognised as an archive.

## 15. Converted SummEdits data is tracked in the repository (found at loop S4)

- **What it is.** `tuning/auditor_external_relation_v1/` tracks files built from the SummEdits and SummExecEdit releases (for example `examples.jsonl`, `document_registry.jsonl`), from a task before the loop. The loop's rule for third-party data (S4b) says never commit third-party data, raw or converted.
- **Evidence.** `git ls-files tuning/auditor_external_relation_v1`; `docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md`; `docs/fix/AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md` (CC BY 4.0 attribution).
- **Why it was left.** The files predate the rule, carry their attribution and licence, and are a frozen record of a quarantined experiment (TCR-010). Removing them from the tree does not remove them from history, and deleting a frozen record is not the loop's call (H12). SummEdits is rejected for sealed use instead (D-019).
- **What would settle it.** The operator's decision: keep as an attributed record, or remove from the tree and include the paths in the S13 history-rewrite rules.

## 15 (closed at loop S4, 2026-10-27 12:18 +0300). Converted third-party data tracked in the repository

- **Closed by the operator's decision D-S7 (Annex D of the loop specification).** The SummEdits-derived files under `tuning/auditor_external_relation_v1/` stay as an attributed record; `PROVENANCE.md` in that folder names the source, the licence (CC BY 4.0, research purposes only) and that the files predate the loop; S13 does not remove them. SummEdits stays rejected as a benchmark (D-019).
- **Correction.** The entry above cites TCR-010 for "quarantined"; TCR-010 says the folder is superseded by v2. The quarantine is stated in `docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md`.
- **Also covered (S4 checker H18).** `tuning/auditor_external_relation_v2/` likewise tracks converted third-party data (PAWS, WikiAtomicEdits, PEER) from before the loop, with its own licence record. Decided by the profile, by analogy with D-S7 (P13): it stays as an attributed record and is not removed by S13; no benchmark uses it.
## 14. No per-test settings are read from a test bundle (found at loop S3) (issue #27)

- **What it is.** The test-preparation plan lists per-test settings among a bundle's parts, and `docs/INPUT_FORMAT.md` section 8 says none is read: the date cutoff, the withheld audit agents, the 2% rename tolerance and the review mode are repository-wide.
- **Evidence.** `scripts/role_resolution.py` reads the manifest and `config/review_scope.json`; no bundle-level settings file is opened by the pipeline or by `tools/score_corpus.py`.
- **Why it was left.** A new reader is a product change outside S3; the manifest already removes the one per-test dependency (the date cutoff) when it names every file. Decision D-018.
- **What would settle it.** A test that genuinely needs a different value for one of these settings; then a reader, a gate check and a format version bump.

## 16. Ten parser and scorer defects found while settling the input format (found at loop S3) (issue #28)

- **What it is.** Settling the code-blind checker's guesses against the code (S3a item 4) found ten behaviours that are wrong, not merely undocumented. `docs/INPUT_FORMAT.md` tells preparers how to avoid each one; none is fixed.
  1. A `date_window` finding's field label joins a Python `set`, so its word order changes between processes (`scripts/paired_review.py`, `date_pair_for_rule`); the scorer compares labels as exact text.
  2. Dates and identifiers with digits are read as figures with no measure (`2026-03-01` gives 2026, `SR-101` gives -101) and then enter products and ratios (`_QUANTITY`, `compute_checks`, `_band_comparisons`); probes produced a false `below_band` and a false `product_mismatch` on correct units. This matters for the S4 adapters: filings and contracts are full of dates.
  3. A UTF-8 byte-order mark drops content: files are decoded as `utf-8`, not `utf-8-sig` (`scripts/text_extract.py`, `scripts/convention_parser.py`); a conventions file starting with one yields zero rules, silently.
  4. A table header measure with a currency symbol or a non-ASCII letter passes `paired_review._header_unit` and fails `reference_tables.resolve_unit`, so that table's bands are ignored.
  5. The negotiation scorer turns a missing field label into the word `none`, so every ratio band breach is a false positive no key can list (`tools/score_corpus.py`, `score_rounds`).
  6. A label repeated in one unit is read two ways: scope pins take the first value, figures the last.
  7. Rules dropped as shorter than 16 characters still consume registry ids.
  8. `pipeline._reattribute_computed_plan` splits rule text raw instead of using `pairing_map._norm_label` (a second tokeniser, against the one-tokeniser rule).
  9. `paired_review.prior_index` attributes a paragraph repeated under two headings to the first.
  10. `[note:]` and `[2026: x]` are absorbed as subject tags instead of refused.
- **Evidence.** Probes on invented strings, to be recorded with file and function in the S3 closure table (`docs/loop/stages/S03_REPORT.md`, when written). Where each sits, at `loop/s03` commit `0b25902`: 1, `scripts/paired_review.py` `date_pair_for_rule` (line 336); 2, the same file's `_QUANTITY` (line 93), `_band_comparisons` (line 600) and `compute_checks` (line 649); 3, `scripts/text_extract.py` lines 105 and 126 and `scripts/convention_parser.py` line 340 (`encoding="utf-8"`, not `utf-8-sig`); 4, `paired_review._header_unit` (line 496) against `scripts/reference_tables.py` `resolve_unit` (line 162); 5, `tools/score_corpus.py` `score_rounds`; 6, `scripts/pairing_map.py` (scope pins) against `paired_review.extract_fields` (figures); 7, `scripts/convention_parser.py` `_parse_text_lines` (line 344); 8, `scripts/pipeline.py` `_reattribute_computed_plan`; 9, `paired_review.prior_index` (line 1716, the first unit whose text holds the paragraph); 10, `convention_parser._heading_bracket_tags`.
- **Why it was left.** S3 changed three of these files for one purpose only: commit `1b7cc06` (D-042 decision 10) added a typed `reason_kind` to every refusal of a change record in `scripts/paired_review.py`, `scripts/reference_tables.py` and `scripts/pipeline.py`, and touched none of the ten behaviours. Fixing any of them changes product behaviour that needs its own proof and gate check, outside S3's scope (P16); the S6 open-item sweep owns them. Items 1, 2 and 3 can make a correct detection fail or a correct unit flag, so they lead that sweep, and item 2 is weighed by the S4 adapters (units built so no date shares a unit with a compared figure where avoidable) and by S5.
- **What would settle it.** A fix with a gate check per item, and a new input-format draft where a workaround becomes unnecessary.

## 17. The scorer reads keys only from benchmark/corpora/ (found at loop S3) (issue #29)

- **What it is.** `tools/score_corpus.py` hardcodes `benchmark/corpora/<bundle>/answer_key.json` and finds twins there. The development suite (S3c) lives in `benchmark/dev_suite/generated/` and sealed tests live in role folders, so neither can be scored with it as it stands. It also reads none of the key parts D-042 added to `docs/INPUT_FORMAT.md` section 9: `expected_refusals` (it counts a matched rename's record as a false positive and cannot tell a refusal kind), the multi-round key (entries scoped by round and document), and the four relations Python never writes (`unit_mismatch`, `rate_mismatch`, `copy_mismatch`, `carry_mismatch`), which it can only ever count as missed.
- **Evidence.** `tools/score_corpus.py` line 75 (`CORPORA = ROOT / "benchmark" / "corpora"`); `--corpus` takes a name, not a path.
- **Why it was left.** S3 does not score; the first scoring of generated bundles is S5, and the sealed scorer is role C's own. Recorded in `docs/INPUT_FORMAT.md` section 1.
- **What would settle it.** A `--corpora-root` option (with a gate check) before S5 scores the development suite, and readers for the section 9 parts above (role C's scorer, or the repository's) before S5 measures the rename probes.

- **Closed at loop S5 (2026-10-30, D-098).** Both halves landed: `--key`, `--twin-key` and `--twin-run` (R21, check 285), and the three section 9 key parts (`c48d977`, `ca1a253`, check 293). Keys without those parts score byte for byte as before (62 of 116 saved pairs identical; the rest differ only by added lines on keys that carry a part). Limitation: the `expected_refusals` reader is proven on check 293's fixtures only; no saved run carried prior records it could read. The entry above is kept as written.

## 22. The pairing map reports a firm low side as conditional (found at loop S3) (issue #30)

- **Number.** Recorded as item 20 in D-025 on `loop/s03`; renumbered 22 when the S2 merge brought another item 20 (D-041).

- **What it is.** `reference_tables.band_conditions_for_unit` leaves the compared field out of the fields it treats as used, so a unit's `band_conditions` record in `audit/pairing_map.json` says the low side goes to the model (conditional) for a comparison the finding itself treats as firm. Findings, amendments and scores are unaffected; only the audit record misreports.
- **Evidence.** `scripts/reference_tables.py`, `band_conditions_for_unit` (lines 835 to 862 at `loop/s03` commit `0b25902`), passes only the band's `key_labels` as used to `low_side_condition` (lines 849 and 850; the test itself is lines 675 to 701), while the finding path, `scripts/paired_review.py` `compute_checks`, passes the key labels and the compared field (line 854: `used = set(band.get("key_labels") or ()) | set(labels)`). Reproducible with the committed probe `py -3.12 scripts/generator_checks.py --probe-open-item-22` (`generator_checks.probe_open_item_22`), on the shape of the input format's own unit-price example in neutral words (a gauge rate of 5 `zed/box` against the band 8 to 15 for its part group): it prints `([('model', ['gauge rate'])], [None])`, the map's record conditional on `gauge rate` and the finding with no `conditional_on`.
- **Why it was left.** S3 changed `scripts/reference_tables.py` only to type the refusals of `prior_values_for_scalars` with a `reason_kind` (commit `1b7cc06`, D-042 decision 10), not `band_conditions_for_unit`; correcting the record changes what `audit/pairing_map.json` says on every run with a reference band and needs its own gate check, outside S3's scope (P16). The misreport affects an audit record, not a result.
- **What would settle it.** Count the compared field as used, with a gate check on the format's example; S6 sweep.

## 12 (closed at loop S2). The execution seal and FINAL_STATUS now handle the INST_FINDER setting

- **Closed.** Both halves landed in S2c (plan revision R11): `tools/prepare_ordinary_final_run.py` refuses to seal an unratified `SHIMMER_INST_FINDER=off`, using the pipeline's own ratification test, and the run report written by `tools/analyze_ordinary_final_run.py` states the setting. Proofs in `tools/ordinary_final_controller_checks.py` (`test_unratified_inst_finder_off_refuses_to_seal`, `test_report_states_every_11_12_field`). The entry above is kept as written.

## 18. Em and en dashes remain in 32 files under scripts/, tools/ and config/ (found at loop S2) (issue #12)

- **What it is.** The repository's hard rule is no em dashes anywhere. S2 removed them from every file it changed that reaches a reader (`amendment_render.py`, `summary_generators.py`, `audit_synthesizer.py`, two catalog keys). 32 files under `scripts/`, `tools/` and `config/` still hold em or en dashes (for example `scripts/preflight.py`, `scripts/snapshot_manager.py`, `scripts/agent_wrapper.py`, `scripts/sensitivity_layer/rules.py`), and `config/constitution.json` holds 16.
- **Evidence.** `git grep -c` for U+2014 and U+2013 over `scripts tools config` at `loop/s02`.
- **Why it was left.** None of these files is changed by S2 (P16). `config/constitution.json` is append-only and its existing entries are never edited (H9), so its dashes stay. One catalog key in `scripts/ui/localization_catalog.js` keeps a dash because it must match an agent description in `config/agent_registry.json` word for word.
- **What would settle it.** An S6 sweep over the other files (each reader-facing string checked against its catalog row), and a registry edit with its catalog key together.

## 19. Three reader-check items left after S2's last round (found at loop S2) (issue #13)

- **What it is.** (1) The run summary's absence-quote prediction section is developer telemetry in reader-facing text ("**PASS**", "the forecast of fourteen claims", untranslated in Turkish runs). (2) The deliverable `reviewed_document.md` is a per-agent technical record, not the reviewed document; only its heading was retitled. (3) The document summary prints Python's stored figures ("61.0") rather than the figures as the source writes them.
- **Evidence.** `docs/loop/private` reader checks rounds 1 and 2 (RC17, RD10, RD18); `scripts/absence_prediction.py`; check 253 asserts "**PASS**" and "14 judged and 7 computed"; `run_context.DELIVERABLE_FILENAMES`.
- **Why it was left.** Three reader-check rounds are the limit (IV.4); (1) needs check 253 changed with its owner file; (2) changes a deliverable name used by routes, docs and readers; (3) the summary writer has no unit text at hand.
- **What would settle it.** (1) rewording with check 253 updated in the same commit; (2) a rename with the route table, docs and console updated (S7 console work is the natural place); (3) passing the unit text to the summary writer.

## Corrections to items 12, 18 and 19 (loop S2 checker round 1)

- **Item 12 (closed).** "Both halves landed" overstates the report half: the run report states the setting sealed in the manifest (`tools/analyze_ordinary_final_run.py`), not the setting the run observed in `audit/agent_switches.json`. The seal refuses an unratified `off`, so the sealed value is the run's value; reading the run's own record as a cross-check is left for S6.
- **Item 18.** "None of these files is changed by S2" is wrong for one file: `scripts/ui/localization_catalog.js` was changed by S2 and still holds the one dash whose key must match the agent registry word for word (stated in the same item).
- **Item 19 (1).** The absence-prediction section is translated in Turkish runs (`scripts/absence_prediction.py` localizes each sentence); only the raw status token is untranslated.

## Corrections after S2 checker round 2 (2026-10-27)

- **Item 18.** `scripts/docx_builder.py` was changed in S2 too; its two em dashes (a docstring and a comment) were removed in S2 checker round 2, so it no longer holds one.
- **Item 19 (1) and (3) closed.** The absence-quote section of the run summary now reads as plain sentences in both languages, with check 253's two phrases kept; the document summary prints figures as the unit writes them, through the one formatter `finding_record.figure_text`. Part (2), renaming `reviewed_document.md`, stays open for S7.
- **2026-11-01, sweep 3 over S7 (D-158).** Part (2) will be settled by the parallel track's PATCH_2 (lane/readable: `reviewed_document.md` becomes the document itself, the per-agent record moves to `agent_record.md`) when it merges as a lane after v1 (D-137); it is not merged yet, so part (2) stays open; issue #13 moved to S6.

## 20. Frozen tuning launchers do not pass the loop budget guard (found at loop S2) (issue #25)

- **What it is.** Sixteen frozen tuning and evaluation launchers in `tools/` (`auditor_blocker_closure_cloud`, `auditor_canonical_cloud`, the three `auditor_classifier_lora*_cloud`, `auditor_feature_cloud`, `auditor_final_cloud`, `auditor_final_retry_cloud`, `auditor_linear_cloud`, `auditor_optuna_hpo_cloud`, `auditor_v2_cloud`, `checkpoint120_cloud`, `checkpoint120_v21_cloud`, `producer_v3_cloud`, `run_first_real_tuning`, `second_tuning_pilot`) can send a launch request through the provider adapter without the loop budget guard or the general path's refusals, and their instance names do not start with `shimmer-loop-`, so the reaper would not end one.
- **Evidence.** S2 checker round 2 (adversarial item 15) and the controller fix lane's read-only inventory: every launch request goes through `LambdaExperiment.request` (`tools/lambda_experiment_provider.py`); the only common barrier is each launcher's refusal when its `docs/fix/<run>/LAUNCH_INTENT.json` exists (all exist and are tracked); most also require HEAD to equal an old commit (for example `tools/auditor_final_cloud.py` around lines 40 to 42); `auditor_blocker_closure_cloud`, `auditor_final_retry_cloud` and `run_first_real_tuning` have no HEAD check (the last checks only its marker and two hashes; its frozen source commit is only written into its manifest).
- **Why it was left.** They are frozen tools, bound to past runs; S2c item 16 keeps frozen tools as they are, and changing what a frozen record would do is not the loop's to decide (P9 reason a: needs an operator decision). The loop never runs them.
- **What would settle it.** An operator decision either to retire them (an archive folder outside `tools/`, keeping the records), or to route every remaining launcher through the loop guard.
- **Closed (loop S6, 2026-10-31, D-S13 item 2).** Retired, none routed: a read-only trace found nothing live that calls any of the sixteen (no gate check, no `scripts/` module, no loop tool, the container or a document outside the run records). Commit b61e9bd moves them with `git mv`, bytes unchanged, to `archive/frozen_launchers/` with the nineteen frozen companions that import a launcher or read its source, so nothing left in the tree points at a moved file; the folder's `README.md` says what they are and why they were retired, its `.gitattributes` keeps their attributes, and every record under `docs/fix/` is unchanged. From there a launcher cannot import the provider adapter. Frozen post-run checks that re-hash a moved file at its old `tools/` path (for example `tuning/second_tuning_eval_runtime_v2_1/legacy_checks.py` test_01, which reads `tools/checkpoint120_cloud.py`) would now not find it; nothing live runs them, and the recorded hash still holds at the new path.

## 21. An in-range value under a range the rule states costs a model call (found at loop S2) (issue #26)

- **What it is.** For a range stated in the rule itself, a value inside the range yields no agreeing check (`scripts/paired_review.py`, around lines 791 to 792, `continue`), so the planner marks the pair uncomputable and spends a judging call on a value Python already found in range. A range read from a reference table does give an agreeing check (the comment around lines 620 to 627 covers only that case).
- **Evidence.** S2 reader tie-break on the mocked run from `45aaaea`: a unit reading 12 units under a rule stating 10 to 60 units was sent to the model, and the deliverables said Python could compute nothing (that sentence was reworded in S2, D-037). Check 278's proofs expect two judging calls on the clean mocked sheet, where every value is in range.
- **Why it was left.** Fixing it changes what a review does (fewer model calls, a new agreeing check) and the proofs built around it; it does not make any output dishonest after the rewording. P16 sends such defects to the S6 sweep.
- **What would settle it.** An in-range value under a rule-stated range gives an agreeing check, so the pair counts as settled and costs no call; a check that fails when a pair whose figure was read is reported as uncomputable; the proofs updated; measured on a development run in S6 (cost per verified finding).

## 23. Nothing hands a sealed run's folder to the scorer (found at loop S3, OUTPUT_FORMAT section 13 point 1) (issue #31)

- **What it is.** A sealed cloud run keeps its session folder outside the repository and prints counts only; nothing in the code delivers `downloaded/evidence/run/` to a scorer, and the repository's own scorer looks for a twin's run only under `output/runs/`, where no cloud run folder lands. So a sealed test can be run but not scored without a hand step nobody has written down.
- **Evidence.** `tools/ordinary_final_bound_cloud.py`, `run_folder` (line 69) and `refuse_sealed_bundle_in_repository` (line 61); `tools/ordinary_final_cloud.py`, `execute`; `tools/score_corpus.py`, `twin_findings` (line 230, `glob` over `ROOT / "output" / "runs"`). Stated as open point 1 in `docs/OUTPUT_FORMAT.md` section 13.
- **Why it was left.** How a sealed result reaches role C's scorer is a role-separation decision (who may see the run folder, where it is copied, when), not a format question; S3 writes the formats and changes no controller or scorer (P16).
- **What would settle it.** A decision on the hand-over (who copies what, to where), then a scorer option that reads a run folder by path, with a gate check that scores a fixture run folder outside `output/runs/`; before the first sealed run is scored (S5).

- **Re-dated (2026-10-30, D-092 item 28).** Its settle-by ("before the first sealed run is scored (S5)") passed with no sealed run; it is settled in S6a, before S8b.

## 24. A judged absence can be counted twice, and a refused answer can locate a flaw (found at loop S3, OUTPUT_FORMAT section 13 point 2) (issue #32)

- **What it is.** For a judged absence the model's raw reply stays on the bus beside Python's stamped copy, including answers Python refused. The repository's scorer counts every bus finding, so one absence counts in both copies, and a refused answer can locate a planted flaw.
- **Evidence.** `scripts/pipeline.py`, `_paired_convention_review` (line 2702, `advisory = plan.get("kind") != "absence_judged"`); `tools/score_corpus.py`, `_load_bus_findings` (line 97). `docs/OUTPUT_FORMAT.md` sections 5.5 and 13 point 2; `docs/INPUT_FORMAT.md` section 9 ("Which findings count") tells a scorer that must not be moved by model text to read only the stamped copy.
- **Why it was left.** Which copy a scorer reads is a scoring decision for role C's scorer and the S5 measurement, not something the format can settle; changing the repository's scorer is outside S3 (P16).
- **What would settle it.** A decision that a scorer reads only Python's stamped copy (and counts refused answers apart), then the repository's scorer changed to match, with a gate check on a fixture bus holding both copies and a refused answer.

- **Split at loop S5 (2026-10-30, D-092).** The adapters' half is settled: one record reader for every benchmark adapter (R22) reads Python's stamped copy and counts refused answers apart. The repository scorer's half stays open as written above.

## 25. An amendment's severity is always "required" (found at loop S3, OUTPUT_FORMAT section 13 point 3) (issue #33)

- **What it is.** The amendment built from a finding carries the fixed string `required` in `severity`, even under a `[recommended]` rule; the rule's own severity is read only to decide whether an amendment is made at all.
- **Evidence.** `scripts/paired_review.py`, `amendment_from_finding` (line 2205; the literal `"severity": "required"` at line 2397), against `ensure_amendments_for_findings`, which reads `severity_of_rule` and `_severity_makes_amendment` (lines 2878 to 2896) and records the rule's severity only on a refusal. `docs/OUTPUT_FORMAT.md` section 13 point 3.
- **Why it was left.** Whether the field should carry the rule's severity, or is meant as "this amendment is required to resolve the finding", is not decided anywhere; no scorer reads it today. Changing it changes every amendment record and is outside S3 (P16).
- **What would settle it.** A decision on the field's meaning; if it is the rule's severity, `amendment_from_finding` takes it from the rule, with a gate check on a `[recommended]` rule, in the S6 sweep.

## 26. Family 4's twin is not a multi-round twin (found at loop S3 checker round 2) (issue #34)

- **What it is.** Each family 4 test now carries its multi-round key (`multi_round`, entries scoped by `round_id` and `document_id`, `docs/INPUT_FORMAT.md` section 9), earlier rounds included. Its twin repairs only the last round: its earlier versions are the test's, so the ordinary two-version twin's change records line up. The earlier rounds' breaches therefore stay in the twin, its own `multi_round` key lists them, and neither key names a multi-round `twin_of`.
- **Evidence.** `benchmark/generators/bundle.py`, `multi_round_key` and `_check_multi_round_key`; `benchmark/generators/family_terms.py`, `build` (the twin's values, the prior shared). The gate check `scripts/generator_checks.py` (`test_multi_round_keys_in_the_round_form`).
- **Why it was left.** A twin clean in every round needs earlier versions of its own, which changes the ordinary twin's prior and its change records; no scorer reads a multi-round key yet (item 17), so nothing measures the difference today.
- **What would settle it.** A family 4 multi-round twin with its own repaired earlier versions (a seventh bundle, or the twin's prior repaired with its plan recomputed), named in `multi_round.twin_of`, before any multi-round case is scored.

- **Update (2026-10-30, D-098).** The repository scorer now reads a multi-round key (check 293), but it runs no twin check on a multi-round run and reads no `twin_of` inside `multi_round`, so this item still decides whether a family 4 twin's multi-round result can be read as a clean twin's. L7 runs the family 4 tests and twins multi-round (D-097); their twins are reported as this item says, not as clean twins.

## 27. The general cloud path's score command cannot find its key (found at loop S5) (issue #35)

- **What it is.** `tools/prepare_cloud_run.py` (around line 437) writes `score.sh` with a relative `--corpus project/benchmark/corpora/clinical_reference`; `tools/score_corpus.py` joins that under its own corpora folder, so the command looks for `.../corpora/project/benchmark/corpora/...` and finds no key.
- **Evidence.** The S5 cases lane (lane/s05-cases) found it while keeping `--corpus` unchanged; the join is `CORPORA / corpus` in `tools/score_corpus.py`.
- **Why it was left.** It predates the loop, sits on the general cloud path the loop does not use for its runs, and `--corpus` was to stay unchanged (R21). P9 reason (c): outside S5's items.
- **What would settle it.** Write `--key` (R21) into `score.sh` with the bundle's own key path, with a check that the generated command scores a fixture; S6 sweep.

## 28. B2 does not run the comparison with an earlier version (found at loop S5) (issue #36)

- **What it is.** `benchmark/baselines/python_only.py` reads a manifest's `prior` but does not run the earlier-version comparison, so B2 cannot measure the rename probes or any change record (S5 plan R4, R11).
- **Evidence.** `python_only.py` docstring (around line 28) and its status record `not_reproduced.prior_comparison: true`.
- **Why it was left.** The comparison is the pipeline's, not a baseline arm's; adding it to B2 is outside S5's items (P16, P9 reason c).
- **What would settle it.** A decision that B2 must cover change records; then B2 calls the pipeline's own prior-comparison functions with a check.

## 29. Five gaps left by D-068 (found at loop S5) (issue #37)

- **What it is.** (1) `paired_review.judging_call_counts` still counts uncomputable calls among calls that could carry a note on a Python finding; they cannot. (2) The judged-absence stamping keeps a rule id the model wrote, while the D-068 path replaces it with the plan's. (3) D-068 keeps only items with the Finding record's shape; an item carrying only an UNCERTAIN marker or no declared relation is dropped and counted (`not_finding_shaped`). (4) A D-068 call's reply-record outcome stays `advisory_not_record` and `mark_not_promoted` does not mark it. (5) The reading that `item_calls_failed` (D-066) replaces only silence is for the final preregistration checker to attack; item 12.11 decides whether it is applied.
- **Evidence.** lane/s05-defect report (commits d18cf93, 0e77433, 7e9f16f); `scripts/paired_review.py`; `benchmark/adapters/common/mapping.py`.
- **Why it was left.** Each is outside D-068's declared scope or needs the verification run's counts first (P16, P9 reason e until measured).
- **What would settle it.** (1) count them apart in the summaries and the tr catalog, with check 278 updated; (2) apply the plan's rule to judged absences, with a pinned amendment; (3) the verification run's `not_finding_shaped` count, then a decision; (4) carry the call id on the stamped result; (5) the final preregistration attack.

## 30. The reading agent's claim slot needs claim ids that real documents never carry (found at loop S5, item 7 diagnostics) (issue #38)

- **What it is.** The compact extraction contract accepts a claim only by an id written in the span text (`scripts/compact_contracts.py` around line 64). No development document under review carries such ids, so every PROCESSOR reply that writes a claim is refused as "Ungrounded claim id" and the accepted extractions are empty spans. Downstream, the classifier pairs an empty extraction with its source, so the clinical sheet's pairs are all labelled OMISSION.
- **Evidence.** Saved replies of L1, L4a and L5v (development, exposed): refusals for an ungrounded claim id in 5 calls on the device log, 3 on its clean twin, 2 and 1 on two L4a documents; not one source span carries a claim id; classifier labels OMISSION on every pair whose extraction was empty. Recorded in the S5 report, item 7.
- **Why it was left.** Placing claim ids in spans by Python (as EXTRACTION-B does for reference ids) changes the input the frozen Producer checkpoint was evaluated on; it needs its own evidence run and is a product change for S6a, not a dry-run fix (P16, P11).
- **What would settle it.** A general rule for where claim ids come from (placed by Python, or not required), measured on development tests that are not benchmarks before any benchmark use.

## 31. An amendment with no reference id raises validator errors, and amendments carry no agent (found at loop S5, item 7 diagnostics) (issue #39)

- **What it is.** Amendments built from computed findings in L1 and L5v carry an empty `ref_ids` list in some cases, which leaves `_validator_errors` on them (the comment then lacks a CONV and REF id), and every amendment's `agent` field is null.
- **Evidence.** L5v device log 4 validator errors, L5v clinical sheet 2, L1 2 (saved `review_data.json`).
- **Why it was left.** Found by a read-only diagnostic during S5's cloud runs; the fix belongs to the amendment path (S6a), after the dry runs (P16).
- **What would settle it.** Trace why a computed finding reaches amendments with no REF id (the unit's passage placement, `paired_review.unit_passage_refs`), fix generally, and hold it with a check.

## 32. The scorer's twin comparison cannot read a Python-only run (found at loop S5) (issue #40)

- **What it is.** `tools/score_corpus.py --twin-run` reads the twin run's bus (`logs/agent_bus.jsonl`). B2 (`benchmark/baselines/python_only.py`) writes no bus, so a B2 twin cannot be passed; S5 scored each B2 twin as its own run (false positives counted) instead.
- **Evidence.** S5 B2 runs on the development suite (`external/s05/B2_suite/`, ignored): "no bus at ...".
- **Why it was left.** A scorer change is attacked by a checker before use (III.2); the workaround gives the same false-positive count (P16).
- **What would settle it.** Read the twin's findings from `review_data.json` when the run has no bus, with a check.

## 33. Gate check 256 fails now and then inside a long gate run (found at loop S5, INC-021) (issue #3)

- **What it is.** Check 256 ("startup readiness is explicit and non-mutating") patches `socket.create_connection` and `subprocess.Popen` for the whole process and counts any call during its window as forbidden. In two of five chunked runs on 29 October it failed with "sensitive health imported a model probe while inactive"; alone, and in the shorter range 200 to 256, it passed every time.
- **Evidence.** Gate logs of `8c2392d` and `ee2f1ed` (private); INC-021.
- **Why it was left.** A test-infrastructure flake, not product behaviour; finding the thread needs an instrumented gate run, which belongs to the S6a sweep (P16).
- **What would settle it.** Record the calling thread and stack in `refuse()` on a failing run, then either stop that thread at its own check's end or scope the check to its own calls; neutralise, fail, restore, pass.

## 34. A model's figure relation is kept on a unit with no figures (found at loop S5, L6 model-text review) (issue #41)

- **What it is.** Under D-068 the shared refusals screen absence claims (a quote must be in the unit) but not figure relations: a model answer with relation `sum_mismatch` on a unit that states no figures is kept as a model-written record.
- **Evidence.** L6 model-text review (development, exposed): 3 of 3 kept records sampled were such answers on ContractNLI units, all wrong.
- **Why it was left.** A screen change after development outputs are seen; sensitivity S-8 (DEV-012) reports B3 without model-written records instead (D-080; P16).
- **What would settle it.** Refuse a model's figure relation when the unit carries no figure the relation names (`paired_review.model_item_notes` already notes "figures not in its unit"), measured on tests that are not benchmarks, with a check.

## 35. The multi-round phase's reading-agent call runs to its output cap (found at loop S5, INC-023)

- **What it is.** In final mode the multi-round phase sends PROCESSOR a long free-form prompt; the reply runs to the 4,096-token cap and the phase refuses the case (`agent_output_unavailable`), so no multi-round case has been reviewed on real execution.
- **Evidence.** L6m (development, exposed): the synthetic family 4 case, prompt 15,795 tokens, cap hit after 944 seconds, exit 8; round reuse worked (round 2 reused 8 of 11 units).
- **Why it was left.** A design change (which agent or which prompt shape the phase uses, within what the frozen checkpoint was evaluated on) plus a measured run; beyond S5's money (P9 b).
- **What would settle it.** A general rule for the phase's call shape, built in S6a, measured on the synthetic and the negotiation cases, outcome `reviewed`.
- **Added 2026-10-29 (S5 checker round 3, D-088).** One more thing to read before the fix is called done: in L6m's synthetic case, round 3 recomputed all 11 units (`audit/round_reuse.json`), although round 2 reused 8 of 11; why every unit counted as changed in round 3 is not yet known, and S6a reads it from the saved round signatures (`SIGNATURE_INPUTS`) before the re-run.

- **Settled in code (2026-10-30, D-092, lane s05-mr `d2bb6f3`, merged `8110336`).** The multi-round phase's position and movement records are computed in Python from the operator's declared sources; no model is asked (the checkpoint was evaluated on no narrower shape in this phase); every refusal before the records is kept. Round 3's full recompute was a defect: the round signature's vocabulary input covered the whole document's labels; it now covers the labels each paired rule names (reuse 0/11, 8/11, 3/11 on the saved L6m case, findings equal to a fresh computation). Replayed locally on the saved L6m inputs, both cases reach `reviewed` and `activated` with no model call. The item closes when L7 (both cases on real execution) reads `reviewed`.

- **Closed at loop S5 (2026-10-30, D-100, D-103).** On real execution (L7) all nine multi-round entries reached `reviewed` and `activated`. The runner's model-call requirement failed them, fixed in D-101; their re-run is in L9a.

- **Correction (2026-10-30, D-121).** The re-run of the nine multi-round entries moved from L9a to L12 (D-112).

## 36. The S8 report must carry D-069's blind acceptance test, the clean twin's model records, and S-8 as the control (found at loop S5, checker rounds 1 and 2) (issue #42)

- **What it is.** D-069's acceptance test for D-068 asked whether a D-068 record on the clean twin was scored as a false positive, but `tools/score_corpus.py` counts false positives over amendments only and a D-068 record is never an amendment, so the test could not fail on what it was meant to catch. D-070's "verified" means only that clinical recall did not fall and that no amendment changed. The frozen preregistration does not say this, and the benchmark reader lets a model-written record decide an item, so B3 can carry model-driven false flags.
- **Evidence.** L5v (development, exposed): the clean twin carried 8 kept model-written records and 20 model-only relations (missing_field 11, sum_mismatch 9), each a false alarm on a document with no planted flaw; the L6 model-text review found 3 of 3 sampled kept answers wrong (open item 34). D-086, D-087; the S5 report, below item 8; the dated note after DEV-020 in `docs/benchmarks/DEVIATIONS.md`.
- **Why it was left.** The preregistration is frozen (D-085), and a limitation is not a rule change; changing how D-068 records are screened is open item 34's work (P16).
- **What would settle it.** The S8 report states, beside the primary B3 result: (1) D-069's acceptance test was blind to D-068 records; (2) the clean twin's model-written records and model-only relations in L5v, with their counts; (3) sensitivity S-8 (B3 and B4 as if every model-written record were absent, DEV-012, DEV-015) as the control, reported beside the primary. The item leaves this file when the S8 report carries all three.
- **Added 2026-10-29 (S5 checker round 3, D-088).** The units in the evidence above, stated exactly: in L5v the clean twin carried 10 model-written records, 8 of them answers kept under D-068 (of 32 judging calls), and 20 model-only relations; "8 kept model-written records" above means those 8 kept answers.

## 37. The peak disk in use on the instance is not recorded (found at loop S5, item 9; S5 checker round 3)

- **What it is.** S5 item 9 asks for disk among the measurements kept for S6, S8 and S9. The records hold the sealed asset archive's size, the instance's free disk at hardware admission and each run folder's size, but not the peak disk in use on the instance during a run (environment, wheels, model cache and run folder together).
- **Evidence.** `assets_transfer_archive.json` and `hardware_admission.json` of every S5 launch; S5's records hold no disk reading after admission. The S5 report, item 9, "Disk"; D-086 (which named P9 reason e), corrected in D-088.
- **Why it was left.** P9 reason (b): the reading needs a launch, and S5's allocation is closed (D-083); the instances of S5 are gone. Reason (e) was wrong, because the reading can be obtained in this loop.
- **What would settle it.** In S6, before S8a's seal: the controller records a disk reading (`df` of the run root) before the workload and after evidence packing as a phase receipt, proven locally with neutralise, fail, restore, pass; the figure is read at the first launch after it (S6, from S5's unused allocation, or the first S8 run).

- **Settled in code (2026-10-30, D-092, lane s05-meas `1ca2f7c`, merged `2e97296`).** The runner records disk in use before the workload, a 15-second sampled peak during it, and after it (`evidence/disk_usage.json`); the evidence packer records it after packing (`disk_after_evidence.json`); the analyser reports a "Disk on the instance" row. The peak is sampled, not continuous. The item closes when L7's report row is read (D-S12 overruled the deferral to S6).

- **Closed at loop S5 (2026-10-30, D-100).** L7 read 45.24 GB in use before the first workload on a 1,455 GB filesystem, about 0.28 GB more per entry, 48.33 GB after the twelfth.

## 38. The time in the pipeline's phases before phase 3 is not recorded (found at loop S5, item 9; S5 checker round 3)

- **What it is.** The telemetry records phase latencies only from phase 3 on, so the time in start, ingestion and roles (phases 0 to 2) is not in any S5 record; item 9's per-phase time is incomplete for them.
- **Evidence.** `phase_latencies` in each B3 entry's telemetry summary of every S5 launch; the S5 report, item 9, "Pipeline phases in B3"; D-086 (P9 e), corrected in D-088.
- **Why it was left.** P9 reason (c): it needs a telemetry change in a pipeline file S5 did not otherwise change; under P16 that is S6's work. Reason (e) was wrong, because the figure can be obtained in this loop.
- **What would settle it.** In S6: phase latencies for phases 0 to 2 written to the telemetry summary, held by a gate check run on a fixture; the figures are then read from the next run that carries them (S6 or S8). Until then, workload minutes less the recorded phases bound them from above (model load included).

- **Settled in code (2026-10-30, D-092, lane s05-meas `6a232e3`, check 294).** Four contiguous spans before phase 3 in `main` (start; ingestion and roles; boot and index; phase 1) are in `phase_latencies`; genesis phase 2 has no code boundary and is reported absent, not zero; the time before `main` (process start, imports) is still outside. `main`'s reference pin was amended in both pinned baselines with `tools/loop/amend_pinned_baselines.py`. The item closes when L7's telemetry is read.

- **Closed at loop S5 (2026-10-30, D-100).** L7's catalogue run: start 0.28 s, ingestion and roles 0.06 s, boot and index 21.75 s, phase 1 0.003 s.

## 39. The phase latencies of the two L6m multi-round cases are not recorded (found at loop S5, item 9; S5 checker round 3) (issue #43)

- **What it is.** Both L6m cases were refused at the multi-round phase before any phase latency was written, so item 9 has no per-phase time for a multi-round run.
- **Evidence.** L6m (development, exposed): `analysis/model_telemetry_summary.json` of both entries; the S5 report, item 9 ("none recorded"); INC-023; D-086 (P9 e), corrected in D-088.
- **Why it was left.** P9 reason (b): the latencies need a re-run of the two cases after open item 35's fix, and S5's allocation is closed (D-083). Reason (e) was wrong, because the re-run is planned in this loop.
- **What would settle it.** The re-run of the synthetic and the negotiation multi-round cases in S6a after open item 35 is fixed, with their phase latencies recorded beside S5's item 9 tables.

- **Brought back (2026-10-30, D-S12, D-097).** Open item 35's fix is merged; both cases are re-run in L7. The item closes when L7's phase latencies are read.

- **Update (2026-10-30, D-101).** A multi-round run has no topology runtime, so its own step times are recorded in `audit/multi_round.json` (`timings`); the re-run of the nine multi-round entries moved from L7 to L9a. The item closes when L9a's timings are read.

- **Update (2026-10-30, D-121).** The re-run moved to L12 (D-112); the item closes when L12's timings are read. Issue #43 stays open until then.

- **Closed at loop S5 (2026-10-31, D-128).** L12 re-ran both multi-round cases and the seven family 4 bundles after D-101: all reviewed, and each records its own step times (`timings` in `audit/multi_round.json`: each round reviewed in a few milliseconds, for example 0.011, 0.004 and 0.006 seconds for the three rounds of the synthetic family 4 case).

## 40. The cost per verified finding on the benchmarks is not recorded (found at loop S5, item 9; S5 checker round 3)

- **What it is.** Item 9 asks for the cost per verified finding. S5 has it for the exposed tests (L1 and L5v) but not for the benchmarks (cost per correct FLAG item).
- **Evidence.** The S5 report, item 9, "Exposed tests"; D-086 (P9 e), corrected in D-088.
- **Why it was left.** P9 reason (c): the figure needs scored results, which belong to S8; computing one now would read development scores only for a cost figure (P11). Reason (e) was wrong, because S8 obtains it.
- **What would settle it.** In S8d: C's scored results (correct FLAG items per benchmark) divided into the S8 ledger cost per benchmark, reported in the S8 report beside cost per document and per decision.

- **Closed at loop S5 (2026-10-30, D-096).** Settled on development items only, after preregistration version 2's freeze: ContractNLI B3 2.86 USD per correct FLAG (1 of 3), B1 tuned 0.27 (1 of 4); SciTab B3 0.08 (2 of 4), B1 tuned 0.13 (1 of 4); ContraDoc no correct FLAG in either arm. Development, a handful of documents, no inference. The S8 report gives the sealed figures beside them.

- **Note (2026-10-31, S5 close).** D-104 pooled D-096's sets with L11 and L10; the S5 report uses D-104's figures: ContractNLI B3 2.57 USD per correct FLAG (2 correct), B1 tuned 0.51 (1); SciTab B3 0.061 (7), B1 tuned 0.061 (4); ContraDoc B3 none, B1 tuned 0.09 (1); CUAD B3 none, B1 tuned 0.0087 (24). Development only.

## 41. Preregistration section 13: duties for the S8 report (found at loop S5, after checker round 3) (issue #44)

- **What it is.** A fresh attack on section 13 found that B1 and B3 locate planted flaws by different tests (B3 by any rule and relation; B1 through the planted rule's item and its quoted sentences, capped when one rule has several flaws), that the unit text for synthetic documents is not defined in the text, and six minor gaps (private s5_sec13_attack.md).
- **Evidence.** D-088; C0 run 3 agreed with the adapter on all 176 synthetic score blocks.
- **Why it was left.** The preregistration is frozen and C0's three runs are used (S5 item 10); a change would be a new version and a new scorer (P18).
- **What would settle it.** The S8 report prints both location readings with the difference stated, location recall on rules with one planted flaw, and the unit-text reading C used; a later preregistration version fixes the text before any later sealed run.

- **Dated addition (2026-10-29 23:39 +0300, D-089).** Tie-break: S3 and S4 confirmed. C0 never tested C's reading of the synthetic unit text (no synthetic B1 output existed), so D-088's "matches in practice" is withdrawn. The S8 report must also give: the count of B1 synthetic location disagreements between C and the adapter and the reading reported; the count of B1 FLAG items whose quotes locate no unit beside the quotes matching several units; an exploratory B1 location under section 3.2's two-way containment, labelled not preregistered; location recall on rules with exactly one planted flaw for every arm; B3's attributed count beside B1's located count.

## 42. A batch launched with `--output-dir` is always refused (found at loop S5, INC-014) (issue #45)

- **What it is.** `tools/ordinary_final_cloud.py` refuses `--output-dir` for every batch launch, so a batch's run folders always sit inside the session bundle.
- **Evidence.** `tools/ordinary_final_cloud.py` around line 160; INC-014 (L2's first attempt, refused before any provider call); the first sweep (D-092 item 17).
- **Why it was left.** No S5 launch needed an output folder outside the bundle: the bundles live under the ignored `external/`. Whether a sealed S8 batch needs one (SEALED-RUN-A puts sealed output outside the repository, which a bundle under the test archive already is) is not shown.
- **What would settle it.** In S6a, before S8a: either allow `--output-dir` for a batch (each entry's run folder under it), with a controller check, or record that S8's sealed batches need none.

## 43. The multi-round strategic layer still sends the whole case in one unbounded call (found at loop S5, lane s05-mr) (issue #46)

- **What it is.** After open item 35's fix, the multi-round phase asks no model, but an explicit `strategic_options` or recommendation request still sends PROCESSOR the whole case in one call with no bound, as the phase did before; on the L6m case that call ran to its cap after about 15 minutes. A failure is recorded as `recommendation_unavailable` and cannot take the case down. The pipeline's confirmation prompt ("Proceed with multi-round model calls (unmeasured)?") and the console hint now describe only that layer.
- **Evidence.** `scripts/multi_round_phase.py` (the strategic layer); the lane report (private, D-092); INC-023.
- **Why it was left.** No development case asks for it; bounding it is a design change of its own (which question, in which shape the checkpoint was evaluated on), outside open item 35's fix (P16).
- **What would settle it.** In S6a: a bounded strategic question, or the layer refused in final mode, with a check; the prompt and hint texts brought in line (check 279 pins the prompt's statement).

## 44. The multi-round scorer does not check the operator's rule id (found at loop S5, lane s05-scorer) (issue #47)

- **What it is.** Round findings carry registry ids only, so `tools/score_corpus.py` prints "attribution: not checked" for a multi-round run; `docs/INPUT_FORMAT.md` section 9 says a scorer needs the case's conventions numbered as section 3 does to check the operator's id.
- **Evidence.** `tools/score_corpus.py` (`score_multi_round`); check 293; D-098.
- **Why it was left.** Renumbering would reimplement the convention parser's numbering (dropped short rules included), outside the lane (P16).
- **What would settle it.** A `--conventions` option that numbers the rules with the pipeline's own parser, with a gate check, in S6a.

## 45. The multi-round records are posted with payload agent PROCESSOR (found at loop S5, D-S12 checker) (issue #48)

- **What it is.** Since open item 35's fix the multi-round phase computes its records in Python, but posts them with payload `"agent": "PROCESSOR"`; only the envelope's `backend` and `model` (and `written_by: python` on each record) say Python wrote them (P5, who wrote what).
- **Evidence.** `scripts/multi_round_phase.py` (the bus post of the computed records); D-103.
- **Why it was left.** Bus readers key agents by name; changing the payload agent touches every reader of the multi-round channel and the scorer's round reader (P16), and `written_by` already says Python.
- **What would settle it.** In S6a: a payload agent naming Python (or the phase), with every reader and the scorer's round reader brought along, held by a check.

## 46. A rule that names a document label pairs only with units carrying that label (found at loop S5, lane s05-cuadclaim) (issue #49)

- **What it is.** The pairing map pairs a rule with a unit only when the unit carries every document label the rule's text names. A CUAD claim whose wording names a label such as "Source", "Name" or "Date" pairs only with units holding that label line, so a clause elsewhere in the contract is never asked about and reads as absent.
- **Evidence.** On the CUAD development side, 109 of 3,936 (contract, claim) pairs name a label beyond the passage; one claim alone matches the `Source:` lines of 42 contracts; about 5 percent of unit-rule pairs are lost (457,769 of 482,119). The lane's measurement, gold-free, from Shimmer's own pairing map (D-113).
- **Why it was left.** A property of the input format and the pairing map, for every corpus, not of one adapter (P16).
- **What would settle it.** In S6a: a decision whether a label word inside a rule's prose is a pairing declaration (today it is read as one), with a gate check, measured on the corpora before and after.


## 47. The envelope constraint can force a PRACTICE_AUDITOR explanation that never ends within 768 tokens (found at loop S5, L12b and R2a) (issue #102)

- **What it is.** When PRACTICE_AUDITOR on the local auditor would close an item without its required `explanation`, the envelope constraint (DECODING-B, check 297) keeps the item open; in three replies the explanation it then writes runs to the 768-token allowance (`PAIRED_JUDGING_MAX_TOKENS`), so the envelope never closes and the call is a contract violation.
- **Evidence.** L12b entry `f1_s1101_cvjx` (two calls, first intervention at steps 168 and 169, 16 and 14 interventions, both to 768); R2a prompt `p0030` (15 interventions, to 768). D-132, D-138.
- **Why it was left.** A fix (a larger PRACTICE_AUDITOR allowance, or a bound on the forced explanation) changes what every review asks of that agent and must be measured on development runs; D-S18 item 2a records it and lets v1 go on.
- **What would settle it.** A replay of these prompts with a larger allowance or a bounded explanation, under a rule written before the measurement, then a decision with its D-number.

## 48. VERIFIER's one-item-per-reference list can run past 4,096 tokens (found at loop S5, R2c and L12b) (issue #103)

- **What it is.** VERIFIER sometimes writes one item for each reference in the draft and does not stop; at 4,096 new tokens (D-134) most replies now end, but some still reach the allowance and the envelope never closes.
- **Evidence.** R2c: 4 of 8 capped prompts still at 4,096. L12b: `cuad_527255a5c970` (one intervention) and `f3_s3102_vwmj` (none) at 4,096; three other entries expected to stay capped ended on their own. L12c: `f1_s1102_mstx` at 4,096 (no intervention). D-134, D-138, D-146.
- **Why it was left.** A larger allowance is unmeasured and the lists look unbounded; a structural bound (no more items than distinct references) needs a decision measured on development runs (P16).
- **What would settle it.** A bound on VERIFIER's item count tied to its input (or a measured larger allowance), proven by a replay of these prompts, then a decision.

## 49. A false Python missing_field amendment on a summary table read from its header only (found at loop S5, L7, D-106) (issue #104)

- **What it is.** In the negotiation r2 to r3 comparison, Python posted a `missing_field` amendment for CONV-N01 on the u06 summary table: the table's fields are read only from its header row (term, figure), and the comment says the field is absent from the unit's text although the table's first row states the figure.
- **Evidence.** L7 entry 03 (`external/s05/L7`), the L7 analysis (private `analysis/an_l7_report.md`), D-106. The round scorer does not count it, so no score shows it.
- **Why it was left.** A change to how a table's fields are read touches every corpus's pairing (P16); found in S5 analysis, after the S5 code was settled.
- **What would settle it.** A rule that a table unit's fields include its row labels, or that an absence on a table unit is checked against its cells, with a gate check, measured on the corpora before and after.

## 50. The multi-round strategic VERIFIER call is decoded under an envelope grammar no measurement covered (found at loop S5 close, lane s05-c279) (issue #105)

- **What it is.** Since the envelope constraint (D-129), every VERIFIER call on the local auditor is decoded under a grammar built from the contract its wrapper carries. The multi-round strategic layer replaces the wrapper's contract (`multi_round_phase._call`), so its VERIFIER call is constrained by the strategic contract's own keys, a shape the R2 measurements never saw.
- **Evidence.** Lane s05-c279's report: check 279's stand-in tokenizer could not build the token table, which is how the path was found; on the fixture the call now records `decoding_constraint` with 0 interventions.
- **Why it was left.** The grammar follows the same contract the validator checks, so it admits only replies that contract accepts; whether the decision-support call should be constrained is a scope decision without a measurement (P9 reason b).
- **What would settle it.** A replay of saved strategic VERIFIER prompts on sdpa and sdpa_constrained under a rule written before the measurement, or a decision to exempt that call, with a gate check.

## 51. Under the envelope constraint PRACTICE_AUDITOR's forced explanation is mostly wrong (found at loop S5 close, the seeded review of intervened replies) (issue #106)

- **What it is.** When PRACTICE_AUDITOR would close an item without its required `explanation`, the envelope constraint (D-129) keeps it open and the model writes one; the reply then passes its validator. Read against the unit, those forced explanations are mostly wrong.
- **Evidence.** The S5 close review of intervened replies (L12b, seed recorded before reading): of 8 accepted PRACTICE_AUDITOR replies with interventions, 1 correct, 3 partly correct, 4 wrong; all 3 on uncomputable plans were wrong and kept as model-written records under D-068. The S5 report, "Intervened replies".
- **Why it was left.** Whether to keep PRACTICE_AUDITOR under the constraint (more complete runs, more wrong advice) or take it out (contract failures return) is a product decision that needs a measurement on development runs (P9 reason b); v1 reports it as it is.
- **What would settle it.** A development measurement of benchmark-mode precision with and without PRACTICE_AUDITOR's envelope constraint, under a rule written before it, then a decision with its D-number.

## 52. Arm L counts only the Python children that report themselves (found at loop S7 close, adversarial checker) (issue #108)

- **What it is.** Arm L's network accounting (`launcher_network`) counts processes from the logs its sitecustomize writes. A Python child that never loads it (`-I`, `-S`, `-E`, a dropped PYTHONPATH) leaves no log and is not counted; native code and non-Python children pass the Python-level denial unblocked and unrecorded. ARM-L-A and check 311 now say exactly that.
- **Evidence.** `tools/ordinary_final_run.py` (the launcher network reading and the pass rule), `tools/cloud_run_observer.py`; D-148; lane s07-fix2's report.
- **Why it was left.** The fix changes `tools/ordinary_final_run.py`, a bound controller file, while L14 is being re-sealed (P9 reason b); it is taken up in S6, after L14b (sweep 3, D-158).
- **What would settle it.** The sitecustomize logs every interpreter start; the runner counts child processes independently (sampling its session's process group); the pass rule requires the two counts of Python children to match and records non-Python children by name; a neutralisation hides one child from the sitecustomize; check 311.

## 53. The replies view does not show decoding-constraint intervention counts (found at loop S7 close, lane s07-fix2) (issue #109)

- **What it is.** Every constrained call records `decoding_constraint` (steps, interventions, dead end) on its reply record and in its usage; the console's replies view shows the reply metadata only, so where the constraint changed a token is not visible there.
- **Evidence.** Lane s07-fix2's per-feature review of S5's later additions (private `analysis/lane_s07_fix2_report.md`); `scripts/console_views.py` (`REPLY_FIELDS`).
- **Why it was left.** Developer detail per call, not needed for v1 (D-S18 item 3; P9 reason b).
- **What would settle it.** The intervention count per call in the replies view, with a check, in S6.

## 54. `shimmer.sh` fails at `dirname` when started from a non-login Git Bash with no `/usr/bin` on PATH (found at loop S7 final pass, lane s07-final) (issue #110)

- **What it is.** A person starting Git Bash gets a login shell with `/usr/bin` on PATH; a scripted caller without it stops at `dirname` before the menu. The gate's launcher checks were fixed by putting the bash folder on PATH; the launcher itself was not.
- **Evidence.** Lane s07-final's report (private `analysis/lane_s07_final_report.md`); lane s07-fix2 (checks 307 and 308).
- **Why it was left.** It affects scripted callers only, not a person (P9 reason b).
- **What would settle it.** `shimmer.sh` finding its own folder without external tools (or adding Git's `usr/bin` itself), with a check that starts it with that PATH, in S6.

- **Closed at loop S7 round 3 (2026-11-01, commit `b2b2fb1`, lane s07-r3fix).** The "P9 reason b" above was wrong: the fix costs no money. `shimmer.sh` reads its own folder by parameter expansion on `$0` (no `dirname`), and appends `/usr/bin` to PATH only where the directory exists and PATH does not name it, for the tools reached after that (the venv's activate calls `cygpath` on Git Bash; the menu calls `cat` and `rm`); a PATH that names it is left as it is. Check 308 (`scripts/launcher_checks.py`) starts the launcher from another folder with PATH holding only the python stand-in's folder and requires its menu; neutralised by putting the `dirname` line back (stops at `dirname`, exit 1, no menu) and by dropping the append (the activate stand-in's tool is not found): FAIL; restored: PASS. The entry above is kept as written.
- **Since lane s07-r4fix (2026-11-01, D-160).** The append adds no empty entry (an empty or colon-ended PATH gained one, which bash reads as the repository root after the cd); check 308 starts it with PATH empty and a `python3` planted in its folder, neutralised by the former line (the planted `python3` runs): FAIL; restored: PASS.

## 55. Wording and fixture defects on the console's sealed pages (found at loop S7 close, sweep 3 and the screenshot checker) (issue #113)

- **What it is.** `scripts/ui/console.html` renders the count before a fixed plural sentence, so a count of 1 reads "1 model-written findings were kept, none promoted and none checked by Python." (and its Turkish row the same way). The screenshot checker found four more, none a leak: the sealed note says the Annex B.4 reasons "are shown" in sections that do not show them; on the multi-round page the note comes after "No valid recorded case output." instead of under the heading; the note's "Withheld:" list omits document, file and target names, which the page withholds; and the replies page's counts come from the reply records written at render time and disagree with the committed fixture's `agent_activation.json` and `cost_tracker.jsonl`.
- **Evidence.** Private `analysis/s7_shots_checker.md`; `docs/loop/ui/run_detail_sealed_model-findings_1280.png` and `_390.png`; `scripts/ui/console.html` (the sentence) and `scripts/ui/localization_catalog.js`.
- **Why it was left.** Cosmetic; the fix needs a singular sentence and its Turkish row, and a re-render of the screenshots (P9 reason b, inside v1's date).
- **What would settle it.** A singular form chosen by count, the sealed note naming where the B.4 reasons are shown and listing names among the withheld items, the note directly under each heading, the fixture's activation and cost records made to agree with its reply records, their catalog rows and localization checks, and the sealed screenshots re-rendered, in S6.

- **Closed at loop S7 round 3 (2026-11-01, commit `b2b2fb1`, lane s07-r3fix).** The "P9 reason b" above was wrong: the fix costs no money. All five: (a) a count of 1 reads "1 model-written finding was kept, not promoted and not checked by Python." with its own Turkish row; (b, d) the sealed note (`run_report_text.SEALED_NOTE`, the console's fallback and its Turkish row) lists document, file and target names among the withheld items and says the B.4 reasons are shown under Agent switches, the one section that lists them; (c) on the multi-round section the note sits directly under the heading, once; (e) the committed fixture's `call-0003` is a failed call in `audit/agent_activation.json` (state `execution_failure`, outcome `backend_failure`, PRACTICE_AUDITOR's aggregate state with it) and in `logs/cost_tracker.jsonl` (`ok` false), agreeing with its reply records; fixture files only, no key. Checks 298 and 306 (`scripts/console_view_checks.py`) and the localization side gate (`scripts/ui/localization_checks.js`, 17 checks) hold each with neutralise, fail, restore, pass; since lane s07-r4fix, (b, d) has a neutralisation of its own (the former note as `SEALED_NOTE`, as the console's fallback and with its former Turkish row) whose FAIL is asserted to be the twelve (b, d) messages alone, the scan that keeps the B.4 reasons out of every other sealed section covers the Turkish views with each reason's Turkish row, and (e) also requires the three records to name the same calls (neutralised by one more cost line, and by one more activation row, for a call with no reply record). The ten sealed screenshots in `docs/loop/ui/` were re-rendered (two renders byte-identical); the exposed, Turkish and test-change-request shots did not change. The entry above is kept as written.

## 56. A gate leaves an empty `durable/` tree behind, so check 01's result depends on whether a gate ran in that tree before (found at loop S7 close, the tip gate) (issue #114)

- **What it is.** After a full gate in a tree with no `durable/`, the tree holds `durable/cache`, `durable/global`, `durable/learnings` and `durable/reference` (empty, no `governance`). The next gate's check 01 (Directory structure) then reports FAIL ("missing required dirs: ['durable/governance']") where a tree with no `durable/` reports SKIP. Gate checks must not mutate the tree (CLAUDE.md, The verify gate). Check 32 did the same with `input/`; lane s07-r4fix fixed that one (D-160).
- **Evidence.** The s07-lead worktree: `durable/` created at 04:20 +0300 on 1 November during the gate at `02fae41`, its four subfolders touched again at 15:45 during the gate at `07e84e8`, no file in any of them; check 01 SKIP at `02fae41`, FAIL at `07e84e8` (private `gate_logs/s07_07e84e8/main_gate.log`). The writer is not yet found: `durable_paths.ensure_dirs` creates all five subfolders, including `governance`, so another path creates four and leaves them.
- **Why it was left.** The defect sits in gate checks or modules S7 did not touch, it changes no product output and no check other than 01, and the folders it leaves are empty (P16: recorded for S6).
- **What would settle it.** The check or module that creates the four folders found (a gate run with a watcher on `durable/`), made to remove what it created as check 32 now does, with a neutralise, fail, restore, pass proof, in S6.

## 57. The chat window loads the local model on the first request with no memory guard (found at loop S7 close and S10, lanes) (issue #115)

- **What it is.** The chat window loads the local model on the first request with no memory guard.
- **Evidence.** `scripts/chat.py:553` (`_qwen_parse`) loads the model at the first plain-language request; the window has no memory limit of its own. On the laptop the 7B model loads from full-size weights and took free memory from 4.84 to 0.98 GB on its first file (private `analysis/s7_6e_plain_language.md`, D-162).
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** A check of free memory against the model's measured need before the first load, with a plain message when it is not enough, and a gate case.

## 58. The chat window sends the model raw text, not the instruct model's chat template (found at loop S7 close and S10, lanes) (issue #116)

- **What it is.** The chat window sends the model raw text, not the instruct model's chat template.
- **Evidence.** `scripts/chat.py:558` passes the request as plain text to an instruction-tuned model (lane s10-fix1's report).
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** The prompt built through the tokenizer's own chat template, with a check on the built input.

## 59. The chat window offers the model no `qa` action (found at loop S7 close and S10, lanes) (issue #117)

- **What it is.** The chat window offers the model no `qa` action.
- **Evidence.** `scripts/chat.py:57-63`: the action list given to the model has no `qa`, so a question such as why something was flagged reaches the run search only through the keyword fallback.
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** `qa` added to the model's action list, with a check case.

## 60. A review mode the model proposes replaces the mode the person set (found at loop S7 close and S10, lanes) (issue #118)

- **What it is.** A review mode the model proposes replaces the mode the person set.
- **Evidence.** `scripts/chat.py:583`: `cmd.setdefault("mode", self.pending_mode)` keeps a model-supplied mode over the person's earlier choice.
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** The person's mode wins, or the window asks; a check case.
- **Closed (2026-11-02, loop S11, D-183).** Once the person sets a mode, a review request keeps it whatever mode the request was read as (proposed by the model, or defaulted to normal by the keyword parser), and the window says so before asking to proceed. Check 310 drives both cases and neutralises the test.

## 61. The chat window's set cutoff writes a tracked config file (found at loop S7 close and S10, lanes) (issue #119)

- **What it is.** The chat window's set cutoff writes a tracked config file.
- **Evidence.** `scripts/chat.py:282` onward (`write_cutoff`) writes `config/review_scope.json`, a tracked file.
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** The cutoff written where operator settings for a run belong, or the tracked file's role stated in the docs; a check case.

## 62. `shimmer.sh` hands `/tmp` paths to Python, which a Windows Python cannot open when Git Bash's path conversion is off (found at loop S7 close and S10, lanes) (issue #120)

- **What it is.** `shimmer.sh` hands `/tmp` paths to Python, which a Windows Python cannot open when Git Bash's path conversion is off.
- **Evidence.** `shimmer.sh` lines 234, 258 and 310 (at `7021a4a`) pass `${TMPDIR:-/tmp}/...` paths (the draft and review flags, the token-hash file). Read from the code by lane s10-fix1, not run. INC-030's failure needed path conversion off, which the loop's own hidden start had set (`MSYS_NO_PATHCONV=1`).
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** A launcher case under conversion off that answers 1 and D, and paths a Windows Python can open.

## 63. A comment in `pipeline.main` calls the draft model the strong Claude model (found at loop S7 close and S10, lanes) (issue #121)

- **What it is.** A comment in `pipeline.main` calls the draft model the strong Claude model.
- **Evidence.** `scripts/pipeline.py` about line 4873: wrong under the local profile since INC-031's fix (D-165). `main` is pinned (IV.7), so the comment waits for the next change that needs an amendment of `main`.
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** The comment corrected together with the next amendment of `main`.

## 64. The loop's pinned-baseline helper writes a fixed date (found at loop S7 close and S10, lanes) (issue #122)

- **What it is.** The loop's pinned-baseline helper writes a fixed date.
- **Evidence.** `tools/loop/amend_pinned_baselines.py` writes `"date": "2026-10-27"` for every amendment (lane s10-fix1's report); the S10 amendment was written by hand with its real date (D-165).
- **Why it was left.** It does not change what a review finds or reports; v1 comes first (P16: recorded for S6).
- **What would settle it.** The date taken from the clock or an argument, with a fixture check.

## 65. `shimmer.sh`: a child process can consume piped input meant for the backend question (found at loop S10, D-S13 item 6b) (issue #123)

- **What it is.** With its answers piped in, a child that `shimmer.sh` starts during the install (pip or Python) reads the buffered input, so the backend question finds end of input and takes the Cloud default.
- **Evidence.** The 6b re-run on a fresh clone of loop/s10 at `74408d3` under Git Bash with input `L`: install finished (723 s, the CUDA torch build), menu reached, but the log says "Backend profile: cloud"; `shimmer.bat` with the same input chose Local (D-160, D-167).
- **Why it was left.** It affects scripted callers only, not a person at a terminal; v1 comes first (P16: recorded for S6).
- **What would settle it.** The install's children started with standard input closed, and a launcher check that pipes `L` through a full install path.

## 66. A local draft under the final profile is written by the tuned extraction adapter (found at loop S10 close, adversarial checker) (issue #124)

- **What it is.** After INC-031's fix the draft memo goes through the drafter's backend; for `local_producer` in final mode that is `call_local`, which loads `final_models.resident('producer')`, the Producer adapter trained for compact extraction (`scripts/agent_wrapper.py:1101-1104`, `scripts/pipeline.py:779-785`). L14c ran the launcher with base models (`SHIMMER_MODEL_MODE=base`), so its memo came from the base model (`unsloth/Qwen2.5-7B-Instruct-bnb-4bit`); a final-mode draft would use the adapter. The README and the console say only "a local model".
- **Evidence.** The S10 adversarial checker (private `analysis/s10close-round1.md`); L14c's reply record (model id, base mode).
- **Why it was left.** Which weights write a memo is a model choice (P12: changing the default models is the operator's); Local Draft is already marked not yet proven.
- **What would settle it.** The operator's choice of the draft's local weights in final mode, then a check that asserts the identity and the README naming it.

## 67. A draft memo cut at its output cap goes to review with nothing saying so (found at loop S10 close, adversarial checker) (issue #125)

- **What it is.** `scripts/pipeline.py` about 788 to 790 marks the memo `free_text` even when the call's usage says it was truncated; L14c's memo reached the 4,096-token cap.
- **Evidence.** L14c (D-167): 4,096 output tokens; the S10 adversarial checker.
- **Why it was left.** The function is pinned; a change needs an amendment and a run to see whether the memo is in fact cut (L14d, after v1).
- **What would settle it.** A truncated memo marked in its outcome and the run summary, with a check, at L14d.

## 68. Under the local profile a web-enabled agent can still reach the web (found at loop S10 close, lane s10-fix2) (issue #126)

- **What it is.** Under the local profile a web-enabled agent can still reach the web.
- **Evidence.** `scripts/search_router.py:201-274` opens web URLs with `urllib.request` for agents whose registry flag allows the web (`may_use_web`). It is not a provider client, so the S10 provider sweep (check 313) leaves it; under the local profile a review with a web-enabled agent would still reach the network (lane s10-fix2's report).
- **Why it was left.** An operator choice (P12); recorded for S6 (P16).
- **What would settle it.** The operator's choice: whether the local profile refuses the web, then a check either way.
- **Closed (2026-11-02, D-180).** The operator chose that the local profile refuses the web (D-S23 item 1). Commit 0e2b387 (lane s11-noweb): `SearchRouter.search` refuses every caller, roster agents and system callers alike, under any profile but cloud, before the query masker and every engine; the refusal is logged, and the run summary and the console state the profile and whether web access was open; gate check 316 (`scripts/web_access_checks.py`). Left out: `scripts/corpus_validator.py`'s corpus download (`_attempt_download`, urlopen) is an operator corpus tool that no agent and no run calls, so it is outside the profile rule.

## 69. Check 313 copies the local remap of `pipeline.main` instead of calling it (found at loop S10 close, lane s10-fix2) (issue #127)

- **What it is.** Check 313 copies the local remap of `pipeline.main` instead of calling it.
- **Evidence.** Check 313 reproduces `main`'s inline local remap (the same table and overwrite) because `main` is pinned; if that remap changes, 313 still checks the table, not the new code (lane s10-fix2's report).
- **Why it was left.** `main` is pinned (IV.7), so the change needs an amendment of `main`; recorded for S6 (P16). The S10 round 2 adversarial checker adds: 313 builds the drafter with `pipeline._build_wrapper`, while `main` builds AMENDMENT_DRAFTER's wrapper directly from its own registry choice (`scripts/pipeline.py` about 4886 to 4901), so a change there would not reach 313 either.
- **What would settle it.** The remap and the drafter's construction factored into functions when a change to `main` needs an amendment anyway, and 313 calling them.

## 70. Gate check 256 fails now and then inside the full gate and passes alone (found at loop S11 close) (issue #128)

- **What it is.** Gate check 256 fails now and then inside the full gate and passes alone.
- **Evidence.** Check 256 (startup readiness is explicit and non-mutating) failed with "sensitive health imported a model probe while inactive" in the full gate at `f1e7e2f` (S7) and at `dca0f4a` (S11), passed alone each time and in every other full gate; nothing it covers changed in S7 or S11. Most likely a thread left by an earlier check makes a socket or process call inside 256's patched window (the same kind of leftover as INC-029's Tk abort).
- **Why it was left.** It changes no product output and has not been reproduced alone (P16: recorded for S6).
- **What would settle it.** The leftover thread found (a run with each check's thread list recorded before and after), the earlier check made to stop its threads, and 256 passing in five full gates in a row.

## 71. Corrections to the format drafts held for the next preregistration version (found at loop S11 close) (issue #129)

- **What it is.** Corrections to the format drafts held for the next preregistration version.
- **Evidence.** Lane s11-readme's third pass verified 16 corrections to `docs/INPUT_FORMAT.md` (5) and `docs/OUTPUT_FORMAT.md` (11) against the code (private `analysis/lane_s11_readme_report.md`, "Format corrections held for the next version"): among them exit code 4's unreachable-Qwen cause, every exit 2 shown as `snapshot_conflict`, the full B1 and arm L reason lists, and that only `strategic_options` and `recommendation` call a model. S3a item 5 allows only additions the scorer does not read after C0's last run, so they were put back (D-172).
- **Why it was left.** P9 reason d: until C0 run 5 the output format may change only by additions the scorer does not read (S3a item 5).
- **What would settle it.** Applied in the format drafts together with preregistration version 3 and C0 run 5, if a new version is still allowed (D-S13 item 10, D-S18 item 5), before the formats freeze. If no new version is allowed, the formats freeze as they are and each correction is a post-freeze defect reported beside the S8 results (P9 reason d).

## 72. Two figures on the results page differ from the S5 report (found at loop S11 close) (issue #130)

- **What it is.** Two figures on the results page differ from the S5 report.
- **Evidence.** `docs/RESULTS.md` gives the L11 ContractNLI first run as 8 of 34 where `docs/loop/stages/S05_REPORT.md` (about line 198) says 9 of 34, and CUAD B1 as "answered 40" where the S5 report says 41 of 41 parsed. Settling them needs the run's label files, which are not committed (lane s11-readme's third pass).
- **Why it was left.** It changes no product behaviour (P16: recorded for S6).
- **What would settle it.** Both figures re-derived from the runs' label files and the page or the report corrected.
- **Closed (2026-11-02 01:40 +0300, D-177).** Both are consistent once each figure's reading is named: the L11 ContractNLI first run is 8 of 34 in benchmark mode and 9 of 34 under the earlier as-shipped reading (private `analysis/an_l11_report.md`, the table at about line 132); CUAD's B1 parsed all 41 replies with 1 undecided, so 40 answered (private `analysis/an_l10_report.md`, about line 266). The results page now names both readings.

## 73. The README names the synthetic adapter's command differently from the code (found at loop S11 close) (issue #131)

- **What it is.** The README names the synthetic adapter's command differently from the code.
- **Evidence.** The README's adapter command list says `build` where `benchmark/adapters/synthetic/adapter.py` (about lines 555 to 568) takes `items` (lane s11-readme's report).
- **Why it was left.** It changes no product behaviour (P16: recorded for S6).
- **What would settle it.** The README naming the command the adapter takes.
- **Closed (2026-11-02 01:40 +0300, D-177).** The external adapters do take `build`; only the synthetic suite's adapter takes `items`. The README now says so.

## 74. `scripts/claim_classifier.py` builds an OpenAI client that check 313 does not cover (found at the S10 outside audit) (issue #132)

- **What it is.** `ClaimExtractor._gpt_extract` (about line 118) builds an OpenAI client when given a key. Only gate check 16 imports the module, so no run path reaches it; if a run path ever used it, check 313 would not see it unless that path were among its cases.
- **Evidence.** The S10 outside audit, finding 2; the S10 provider sweep (D-169).
- **Why it was left.** Unconsumed today, so no output changes (P16: recorded for S6).
- **What would settle it.** A check 313 case for it, or the module kept out of every run path by a check.
- **Closed (2026-11-02, loop S11, D-183).** `ClaimExtractor.extract` builds no OpenAI client under the local backend profile, key or not; it reads with its regex patterns only. Check 313 has a `claim extractor` case (a placeholder key, a raising client) and a neutralisation that removes the guard and fails with an OpenAI client built.

## 75. `scripts/model_registry.py` builds provider clients directly, outside the path check 313 covers (found at the deferral sweep of 2 November 2026, sweep row B-36) (issue #136)

- **What it is.** `model_registry.list_available_models` builds an Anthropic or OpenAI client itself, not through the agent wrapper, to list a provider's models for the start-of-run model gate.
- **Evidence.** D-169 and D-170 (the provider sweep); `CHANGELOG.md` dev7.
- **Why it was left.** The sweep found no local-profile path that reaches it, so no output changes (Annex D D-S23 item 7 (c)).
- **What would settle it.** A check 313 case that fails if a local-profile path builds a cloud client through it.
- **Closed (2026-11-02, loop S11, D-183).** The model gate is the one run path that reaches the module, and check 313's `model gate` case runs `enforce_current_models` over the local-profile registry with raising clients. A new neutralisation gives the gate the registry as shipped (the profile applied after the gate instead of before) and the case fails with both clients built.
