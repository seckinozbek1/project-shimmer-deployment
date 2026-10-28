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

## 20. Frozen tuning launchers do not pass the loop budget guard (found at loop S2) (issue #25)

- **What it is.** Sixteen frozen tuning and evaluation launchers in `tools/` (`auditor_blocker_closure_cloud`, `auditor_canonical_cloud`, the three `auditor_classifier_lora*_cloud`, `auditor_feature_cloud`, `auditor_final_cloud`, `auditor_final_retry_cloud`, `auditor_linear_cloud`, `auditor_optuna_hpo_cloud`, `auditor_v2_cloud`, `checkpoint120_cloud`, `checkpoint120_v21_cloud`, `producer_v3_cloud`, `run_first_real_tuning`, `second_tuning_pilot`) can send a launch request through the provider adapter without the loop budget guard or the general path's refusals, and their instance names do not start with `shimmer-loop-`, so the reaper would not end one.
- **Evidence.** S2 checker round 2 (adversarial item 15) and the controller fix lane's read-only inventory: every launch request goes through `LambdaExperiment.request` (`tools/lambda_experiment_provider.py`); the only common barrier is each launcher's refusal when its `docs/fix/<run>/LAUNCH_INTENT.json` exists (all exist and are tracked); most also require HEAD to equal an old commit (for example `tools/auditor_final_cloud.py` around lines 40 to 42); `auditor_blocker_closure_cloud`, `auditor_final_retry_cloud` and `run_first_real_tuning` have no HEAD check (the last checks only its marker and two hashes; its frozen source commit is only written into its manifest).
- **Why it was left.** They are frozen tools, bound to past runs; S2c item 16 keeps frozen tools as they are, and changing what a frozen record would do is not the loop's to decide (P9 reason a: needs an operator decision). The loop never runs them.
- **What would settle it.** An operator decision either to retire them (an archive folder outside `tools/`, keeping the records), or to route every remaining launcher through the loop guard.

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

## 24. A judged absence can be counted twice, and a refused answer can locate a flaw (found at loop S3, OUTPUT_FORMAT section 13 point 2) (issue #32)

- **What it is.** For a judged absence the model's raw reply stays on the bus beside Python's stamped copy, including answers Python refused. The repository's scorer counts every bus finding, so one absence counts in both copies, and a refused answer can locate a planted flaw.
- **Evidence.** `scripts/pipeline.py`, `_paired_convention_review` (line 2702, `advisory = plan.get("kind") != "absence_judged"`); `tools/score_corpus.py`, `_load_bus_findings` (line 97). `docs/OUTPUT_FORMAT.md` sections 5.5 and 13 point 2; `docs/INPUT_FORMAT.md` section 9 ("Which findings count") tells a scorer that must not be moved by model text to read only the stamped copy.
- **Why it was left.** Which copy a scorer reads is a scoring decision for role C's scorer and the S5 measurement, not something the format can settle; changing the repository's scorer is outside S3 (P16).
- **What would settle it.** A decision that a scorer reads only Python's stamped copy (and counts refused answers apart), then the repository's scorer changed to match, with a gate check on a fixture bus holding both copies and a refused answer.

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
