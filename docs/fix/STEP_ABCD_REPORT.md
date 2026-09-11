# STEP A/B/C/D REPORT: four jobs from the token and rule analysis

Written 2026-09-12. Four jobs, run per the operator's sequencing (A and D independent
and could have run in parallel with each other; B independent of everything; C
depending on A for the bound). No pipeline run, no model loaded, no money spent at any
point. Every claim below is either a gate-proved assertion or a direct, reproducible
computation against real files on disk, both cited.

## TODO (kept, not deleted, so the steps are auditable)

- [x] Read `reference_tables.py`, `paired_review.py`, `pairing_map.py`, `agent_wrapper.py`,
      `pipeline.py` end to end for every call site touched by any of the four jobs
- [x] JOB A: extend the band reader to a labelled prose statement (a label, a colon,
      a range, in one sentence), proved on fixtures for accept and refuse
- [x] JOB A: check the real corpus's own Class-A/B/C sentences against the new reader
      and diagnose why they still do not mint a band (the shared tokenizer's word-length
      filter drops the single-letter suffix, a pre-existing limit, reproduced identically
      in a real markdown table with the same three labels)
- [x] JOB B: measure the real per-call-type token requirement from the run's own cost
      tracker and bus records, distinguishing a call that hit the cap from one that did not
- [x] JOB B: replace the blanket 1024 local ceiling with five named, evidence-sized budgets,
      and record a cut as a cut rather than parsing it as whole
- [x] JOB C: build a date-pair reader and a single-value prose bound reader, wire them into
      `compute_checks`/`plan_calls`, and diagnose why the real corpus's two duration rules
      still do not settle end to end (a singular/plural mismatch, a different one for each
      rule, in the shared word-containment test both new readers and the pre-existing
      readers use)
- [x] JOB C: while proving the fix, found and closed a pre-existing double-booking defect
      in `plan_calls`' fallback that also affected R1's own reference-table band mechanism,
      not only this job's new duration path
- [x] JOB D: judge whether the qualifying-role rule (D03) can be reduced to operator
      configuration without losing what the rule means; operator instruction: no, a phrase
      list has the identical silent-failure fault as a role list, one level down; D03 stays
      model work, folded into the judgment count with D06 and D08
- [x] Gate-prove every new behaviour: checks 215 (job A), 216 (job B), 217 (job C), each
      neutralise-and-restore, no regression against the 213/215 baseline
- [x] README checked start to finish before each commit: check-count lines, the
      `reference_tables.py` mechanism list, the "two recorded limits" paragraph, the
      fifth-corpus history paragraph, the scope-declaration duration-limit paragraph
- [x] One commit per job (three commits: `643d84f` job A, `10e33fa` job B, `79d9062` job C);
      job D produces no code, so its record is this report and the README status table below
- [x] Compute the pairing map plan for both twins, and the final "how many of eight settle"
      count, deterministically, no run
- [x] Write this report and stop; nothing pushed

---

## JOB A: a band stated in prose

`reference_tables.py` said plainly, at its own line 48, that a band stated in prose
rather than in a table is not read. On the device corpus that made zero of sixty-four
planned pairs computable (the H7-era measurement) and sent every one to a model,
although the reference states exact bounds as sentences: "Class-A sensor: standard
tolerance band 20 to 60 units," "Class-C sensor: standard tolerance band 70 to 110
units."

**What was built.** `parse_prose_band_sentence` reads the one shape asked for: a label,
a colon, and a range in the same sentence. `parse_prose_bands` groups every matching
sentence in a passage into a synthetic table (one column of labels, one of ranges,
headed by the words between the colon and the first figure), wired into `parse_tables`
itself, so `bands_for_unit` and both of its production callers in `pipeline.py` read a
labelled prose band with no new call site. The reference material was never rewritten:
the corpus's own sentences are read exactly as written.

**The refusal discipline holds.** Two unrelated figures in one sentence, a descending
pair, a colon ending a long clause rather than introducing a label, and a unit the
document under review never writes are each refused, proved in gate check 215.

**What was found, not fixed.** On `device_class_reference.md` itself, the three real
labels ("Class-A sensor," "Class-B sensor," "Class-C sensor") reduce to the identical
word set `{class, sensor}` once the shared tokenizer's `len(w) > 2` filter drops the
single-letter suffix. `match_row` correctly refuses to mint a band from that tie rather
than guessing which class a reading belongs to. This is proved to be a limit of the
SHARED tokenizer (`pairing_map._norm_label`), not something Job A's reader introduces:
check 215 reproduces the identical tie with a hand-built markdown table carrying the
same three labels, no prose reader involved. Fixing it would change how every label in
every corpus is read and is out of this job's scope.

**Net effect on this corpus:** D01 (`CONV-001`, the value-in-range rule) still does not
settle end to end here. The mechanism is proved correct on fixtures whose labels the
tokenizer can tell apart (`Alpha sensor` / `Beta sensor`).

## JOB B: an output budget per call type

Nine of sixteen calls on a real run against the device corpus
(`output/runs/20260911T123328Z__d5728e4b/logs/cost_tracker.jsonl`) hit exactly 1024
output tokens, `agent_wrapper.py`'s old blanket ceiling for every local call regardless
of what it was asked to produce. Four of those nine produced zero usable items
(`parse_trace` showed dozens of recovery candidates, mostly `empty_valid_skipped`, the
shape a response cut mid-item leaves behind), and the one preserved raw truncated
response (VERIFIER, a contract violation) lost its sixth finding entirely, cut
mid-string with no closing quote. The five PRACTICE_AUDITOR paired-judging calls that
did NOT hit the cap ranged 202 to 645 tokens, real evidence that call type's true
ceiling sits well under 1024.

**What was built.** `pipeline.py` now names five budgets, each wired to its real call
site (an AST walk in check 216 confirms the wiring, not a text search):
`PAIRED_JUDGING_MAX_TOKENS` (768, below the old 1024, with headroom above the largest
real, uncapped call observed), and `AUDIT_MAX_TOKENS` / `PRODUCTION_MAX_TOKENS` /
`DEEPEN_MAX_TOKENS` / `WIDE_REVIEW_MAX_TOKENS` (2048, raised rather than left at 1024
for every call type with direct evidence of losing output there; wide-mode review was
not exercised on the measured run, so it is carried forward unchanged rather than
guessed at). `agent_wrapper.LOCAL_MAX_OUTPUT_TOKENS` (4096) replaces the hardcoded 1024
as an outer backstop only, never the effective budget.

**A cut is recorded as a cut.** `call_local` and `call_qwen` compare the generated
length against the cap they were given (reaching the cap exactly is the whole test, no
text heuristic) and set `usage["truncated"]`. `run_task` carries it onto a
`CONTRACT_VIOLATION` post, onto an `AGENT_OUTPUT` post even when parsing succeeded (the
more dangerous silent case: a cut landing at the end of a complete item undercounts
what the agent actually had, with nothing before this saying so), and onto the returned
dict either way. Cloud calls do not yet carry this signal (a recorded gap, not closed).

Gate check 216 proves detection (a stubbed `generate()` at exactly the cap versus short
of it), propagation (a direct `run_task` fixture, both bus-post shapes, the returned
dict), the five constants' values against the evidence, and their wiring by name.

## JOB C: duration arithmetic

Two of the eight device rules say "state the two timestamps and the gap between them,"
an instruction to compute, not to judge. Nothing in this pipeline subtracted two dates
before this job.

**What was built.** `paired_review.date_pair_for_rule` reads a date pair from a unit by
the rule's own connecting words, in one of two shapes: two separate `label: value` lines
each holding one ISO date (UNIT-TEASEL's "Fault logged:" / "Fault acknowledged:"), or
one label line whose value holds two (UNIT-VETCH's "Service record: last calibration
visit ..., next calibration visit logged ..."). The connecting words are the label's own
words UNIONED with the value's own words (dates removed), not the label alone, so a
same-line pair's outer label need not share vocabulary with the rule.
`reference_tables.scalar_bound_from_entries` reads the matching single-value bound from
the reference corpus's own prose ("The standard fault window is 24 hours"), the sibling
of Job A's range reader for a sentence stating one number rather than two.
`compute_checks` emits a `date_window` Finding relation only when BOTH a pair and a
bound are found for the same rule.

**A pre-existing defect surfaced and was closed, in three places, not one.** An
externally supplied bound (this job's own `duration_bound`, and R1's own
reference-table band before this fix) was invisible to `plan_calls`' "nothing computed"
fallback, which re-derives from the rule's text alone and never receives the caller's
external bound. A DISAGREEING external bound therefore double-booked a call: a correct
plan from the per-rule loop, plus a spurious second one asking the model the same
question again. Reproduced with NO Job C code involved (a hand-built out-of-range table
band, the R1 mechanism exactly as it stood before this job), so this is not a defect Job
C introduced; it existed the moment R1 shipped and nothing had exercised a disagreeing
table band in a gate check until now. Closed by tracking every rule a band OR a
duration check reached ANY verdict for, agreeing or not, and excluding those rules from
the fallback. Measured directly: an agreeing table band now costs zero calls (it did
before too, by coincidence, since no gate fixture had tested a disagreeing one); a
disagreeing table band now costs exactly one call, where it cost two before this fix.

**A third instance of the same shape, one layer further in.** A rule that is BOTH
scoped (D, option 2: `[scope: fault logged]`) AND settled by a duration check used to
get its declared `absence_judged` plan (unconditional, minted by `absence_plans` before
the band/duration loop even runs) PLUS the correct `duration` plan, asking the model a
now-redundant generic question when Python had already answered the sharper one with
real figures. Not observed on the device corpus today, because D04's and D05's own
duration checks do not currently succeed there (see the wording gaps below), but it is
latent the moment either gap closes, whether by this session's future work or by an
operator's own correction to the corpus. Closed by dropping a scoped rule's declared
`absence_judged` plan whenever the band/duration loop settles that same rule, leaving
its `absence_computed` plans (a genuinely missing declared field) untouched, and
leaving the `absence_judged` fallback intact when duration or band finds nothing.
Proved with fixtures reproducing both the succeeding and the not-succeeding case.

**What was found, not fixed, and is the more important finding of this job.** Neither
device duration rule settles end to end on this corpus's exact wording, and BOTH
mechanisms this job built are independently proved correct on fixtures whose vocabulary
aligns:

| rule | date pair | bound | settles? | the exact mismatch |
|---|---|---|---|---|
| D04, fault window | FOUND | NOT FOUND | No | the reference states "fault **timestamp**" (singular); the rule says "state the two **timestamps**" (plural) |
| D05, service interval | NOT FOUND | FOUND | No | the document states "calibration **visit**" (singular, twice); the rule says "logged calibration **visits**" (plural) |

D05's bound was only found after a second, real fix: this corpus's task description
states plainly that "the document's own glossary section states the standard fault
window, service interval..." so the glossary lives INSIDE `device_log_flawed.md`
itself, not in the separate `device_class_reference.md` the way D01's class tolerance
bands do. The first version of `_duration_bound_for` copied Job A's `exclude_document_id`
pattern uncritically, which made D05 permanently unsolvable regardless of wording,
since the one document holding its bound was always excluded from the search. Fixed by
also searching the document under review's own text; the corpus was never rewritten.

Both mismatches are the same class of limitation check 215 already named for the
Class-A/B/C labels: exact word containment, with no stemming, is brittle against
ordinary morphological variation. No stemmer was added: the task instruction to refuse
rather than guess, and the codebase's own S5 discipline against inventing vocabulary,
both argue against it, and a phrase-matching fix carries the identical silent-failure
risk the operator named for Job D's own question (a fix that catches "timestamp"/
"timestamps" and misses the next unforeseen pair, silently).

## JOB D: the qualifying-role list

D03 turns on whether a signing role holds a current calibration certificate. The
reference states the principle and a negative example ("a signature from an
engineering, operations, or supervisory role that does not state a current certificate
is... not calibration-complete") but never enumerates which roles or which exact phrase
qualifies.

**The operator's judgment, recorded here as the durable answer to this job's own
question:** a config-driven pattern match on certificate-currency phrasing (a list of
phrases like "certificate current" in operator config, matched against the signature
line) was proposed and rejected. The rejection's reasoning: a phrase list has the exact
same fault as a role list, one level down. It would catch "certificate current" and
miss "holds a valid certificate" or "authorisation in force," and it would miss them
SILENTLY, a check that passes for the wrong reason (or, here, a check that never even
fires and is read as agreement) which is precisely the failure shape this project keeps
finding and building gate checks against. **D03 stays model work.** No code was written
for Job D.

## The count that matters: how many of eight settle without a model call

Two of eight (D06, neighbouring-entry; D08, no-speculation) were named up front as
genuine judgment and were not attempted. **D03 joins them by the operator's own
instruction in this session: three of eight, not two, are genuine judgment.**

Of the remaining five, verified directly against `benchmark/corpora/device_log_review`'s
own files with the current tree's code (`pairing_map.build_pairing_map`,
`paired_review.plan_calls`, no run):

| rule | mechanism | settles on THIS corpus? |
|---|---|---|
| D01, value-in-range | Job A, prose band | No: the Class-A/B/C label tie (pre-existing tokenizer limit); `plan_calls` kind = `uncomputable` |
| D02, calibration-signature | pre-existing scope/absence declaration (D, option 2, applied before this session) | **Yes**: `plan_calls` kind = `absence_computed`, no model call, verified directly |
| D03, calibration-authority | genuine judgment (Job D) | Model work by design, not attempted |
| D04, fault-window | Job C, duration arithmetic | No: the bound-reading half fails (timestamp/timestamps); already scoped, so falls back to `absence_judged` |
| D05, service-interval | Job C, duration arithmetic | No: the date-pairing half fails (visit/visits); already scoped, so falls back to `absence_judged` |
| D06, neighbouring-entry | genuine judgment | Model work by design, not attempted |
| D07, grounding | structural, board-only | Never paired at all (0 pairs on this corpus; an output-shape property, not a document comparison) |
| D08, no-speculation | genuine judgment | Model work by design, not attempted |

**One of the eight settles end to end on this corpus today: D02.** It was already
settling before this session (the scope/absence declarations were applied in an earlier
session), and none of this session's four jobs changed that fact one way or the other;
it is recorded here as the honest baseline the other seven are measured against, not as
this session's own result. D04 and D05 are BOTH already `[scope: ...]`-declared rules,
so on this corpus a failed duration check does not fall through to a wasted
`uncomputable` plan the way D01's does: it correctly falls back to the pre-existing
`absence_judged` model question, one call each, exactly as it did before this session
(this fallback ordering, and the double-booking it would otherwise have created the
moment either wording gap closes, is exactly what this session's fix to `plan_calls`
closes, described above).

This is a different, more honest number than "how many of eight are genuinely
computable in principle," which is five (D01, D02, D04, D05 by mechanism, plus D07's
shape check), against three (D03, D06, D08) that are not. The gap between "mechanism
exists" and "settles on this corpus" is entirely the wording mismatches this report
documents: two singular/plural gaps (Job C, on D04 and D05) and one label-suffix gap
(Job A, on D01), none of them fixed, all three named plainly rather than papered over
by adjusting the corpus.

## The pairing map plan, both twins, computed without a run

Using the current tree's code directly (`convention_parser._parse_text_lines`,
`pairing_map.build_pairing_map`, `paired_review.plan_calls`, all pure Python, no I/O
beyond reading the corpus files themselves):

| | `device_log_review` (flawed) | `device_log_review_clean` |
|---|---|---|
| units | 19 | 19 |
| rules | 8 | 8 |
| candidate pairs (unit x rule, structurally possible) | 40 paired of 114 candidates (74 rejected) | 49 paired of 114 candidates (65 rejected) |
| undecided | 38 | 38 |
| total plans (pairs, after the declared-scope split) | 37 | 43 |
| settled by Python, no call (`absence_computed`) | 5 | 2 |
| still needing the model (`uncomputable` + `absence_judged`) | 32 | 41 |

These figures match the command-cache memory's own record exactly ("40/49 pairs, 37/43
plans (flawed/clean), 32/41 model calls"), confirming the currently-applied D02-D05
scope declarations and this session's Job A/C additions together do not move this
specific corpus's call count: Job A's and Job C's mechanisms are real and gate-proved,
but on THIS corpus their own bound- or pair-reading half fails before either can reach
the `plan_calls` stage that would have reduced the 32/41 model-call figure. The 40/49
and 37/43 numbers were unchanged by this session's work, not because the work does
nothing, but because this corpus's specific wording sits just outside what either new
reader's word-containment test can reach.

## What would close the remaining gap, named without proposing to build it

Not built in this session, per the operator's own instruction to see the corpus as it
is before proposing a fix:

- D01 needs the shared label tokenizer (`pairing_map._norm_label`) to tell "Class-A"
  from "Class-B" apart, which the module's own docstring already names as a residual
  limit (the CJK two-character case) of the same word-length filter.
- D04 and D05 each need ONE of their two halves to tolerate a singular/plural
  difference between a rule's wording and a document's own label, without adopting a
  stemmer or a word list (the same domain-vocabulary risk the operator declined for D03).

Both are properties of shared infrastructure (`_norm_label`, `_words`), not of Job A's
or Job C's own new code, and changing shared infrastructure used by every existing
band, absence, and containment test in this codebase is a decision for the operator,
not a byproduct of this session's four jobs.

## Gate

`PASS=216 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=218`, the same two pre-existing failures as
every step before this one (check 01, missing `prompts`/`snapshots`; check 145, the
missing contamination-probe fixture). Three checks added (215, 216, 217), zero
regressions, each proved by neutralise-and-restore inside its own body.

## Commits

- `643d84f` Job A: read a band stated in labelled prose, not only in a table
- `10e33fa` Job B: an output budget per call type, and a cut recorded as a cut
- `79d9062` Job C: a gap between two timestamps, computed in Python

Nothing pushed. Job D produced no commit (no code change); its record is this report
and the corresponding paragraph in README.md's "Duration arithmetic" section.

---

STEP A/B/C/D COMPLETE (jobs A, B, C built and gate-proved; job D judged and left as
model work by operator instruction; one of eight rules, D02, settles end to end on this
corpus today, unchanged by this session's own work; three of eight confirmed genuine
judgment; the remaining four are genuinely computable in principle but blocked by
wording mismatches this report names and does not fix)
