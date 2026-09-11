# STEP W6 REPORT: measure

## Status: STOPPED by the operator. The measurement is still owed.

At 08:27:17Z on 2026-09-11 the operator stopped the flawed-corpus run mid-way through its
paired review, on the judgment that measuring the current shape at 101 planned pairs was not
worth another hour when convention distribution (the W2 decision, below) will change the call
count anyway. This report records what the run produced up to that point, the incident that
contaminated part of it, what the scorer could and could not score, and the new order of the
chain. It is marked STOPPED, not COMPLETE, so the chain records that W6's numbers have not been
produced. The clean-twin run was never started.

## What was run

Corpus `device_log_review` (W1's flawed document, 19 units, 8 authored rules) staged with
`tools/stage_corpus.py --corpus device_log_review` at 07:15:36Z and restored with
`--restore output/staged_inputs/20260911T071536Z__replaced_by_device_log_review` after the
kill (`input/` was empty before staging and is empty again). Every launch went through
`tools/run_local_demo.py` (S7) with `--non-interactive --skip-confirmation --review-mode
paired`, local backend profile, no cloud call at any point (S3; the model gate skipped all 18
agents as local, the cost estimate printed by the pipeline is a cloud-price projection it
prints regardless and no money was spent).

| attempt | run id | launched | outcome |
|---|---|---|---|
| 1 | `3df0ca98` | 07:16:20Z | refused to start: sensitivity-layer hard stop (INFRA-041, layer inactive). Expected operator-sovereignty gate, not a defect. Needed `--sensitivity-layer-inactive-override`. |
| 2 | `efd7c4df` | 07:16:30Z | passed the sensitivity gate, refused at the redaction hard stop (no operator redaction rule in force; the device conventions carry none). Expected gate. Needed `--no-redaction-override`. |
| 3 | `3d3142c8` | 07:16:45Z, BOOT on the bus 07:16:51Z | both overrides given. **The first and only real run.** Killed by operator instruction at 08:27:17Z. |
| 4 | `b38a42cb` | 07:17:11Z | a duplicate, launched in error (next section). Stopped at 07:43:47Z. |

## The duplicate-launch incident

After attempt 3 started, I judged it crashed and launched attempt 4 as the single restart W6
permits for a driver fault. The judgment was wrong on three counts: the background shell call
returned as soon as the shell forked, not when the pipeline ended; the shared log had no
closing `[wrapper]` line yet because the run was still going; and `ps aux` under Git Bash
cannot see Windows-native processes, so an empty listing was read as "no process". No driver
fault occurred at any point tonight; the one permitted restart was never legitimately
triggered.

Consequences, all stated beside the figures they affect below:

- Two local runs shared the one 8 GB card from 07:17:11Z to 07:43:47Z (26 min 36 s). Attempt
  4 never got past its 18 dispatch REQUESTs (zero agent output in 26 minutes). Attempt 3's wall
  clock is contaminated for that window.
- Attempt 4 truncated `output/w6_flawed_run.log` (its line 6 names `b38a42cb`) while attempt 3
  kept writing into the same file at a stale offset, so that log is interleaved and is not a
  usable record of attempt 3. The per-run files under
  `output/runs/20260911T071648Z__3d3142c8/` are the record used here.
- `output/w6_flawed_mem.json` was rewritten by both wrappers until the stop; the peaks below
  are the surviving wrapper's own after that point.
- Found from the Windows process table (`Get-CimInstance Win32_Process`), confirmed by
  `nvidia-smi` showing one compute process after the stop.

## What the run produced up to the kill

**Wall clock.** BOOT 07:16:51Z to kill 08:27:17Z: 70 min 26 s. Of that, 26 min 36 s
(07:17:11Z to 07:43:47Z) was shared with the duplicate and is contaminated; 43 min 50 s was a
single run on the card. The run was killed during the paired phase, so this is not a
whole-run wall clock. The wrapper's own figures at its last sample (08:27:16Z): elapsed
4227.6 s, peak RAM 4.08 GB, peak VRAM 6601 MB (a 15.7 GB RAM peak read from the shared log
during the contaminated window came from two processes and is not attributed to this run).

**Model calls made: 86**, read from `logs/cost_tracker.jsonl`. 616,118 input tokens, 27,905
output tokens, all local.

| agent | calls | note |
|---|---|---|
| ARCHIVIST | 1 | 07:25:30Z, corpus level, under contention |
| INST_FINDER | 1 | 07:45:27Z, first call after the duplicate stopped |
| CITATION_RESOLVER | 1 | contract violation (below) |
| PROCESSOR | 1 | |
| SPEECH_ACT_TAGGER | 1 | |
| LEGAL_ANALYST | 6 | 1 phase-3 call producing 5 findings, then 5 calls, one per finding: D6, the local-profile two-pass split (`pipeline.py` `_deepen_legal_analyst_findings_local`, serial, bounded by the pass-one count). Not a retry. |
| VERIFIER | 1 | contract violation |
| FACT_CHECKER | 1 | |
| PRACTICE_AUDITOR | 73 | the paired phase, 08:00:07Z to 08:27:02Z, one call per pair, 73 of the 101 pairs the map planned |
| STYLE_GUARDIAN | 0 | not reached |

**Against the pairing-map count.** W6 asked for the calls made against "the pairing-map
count you recorded in W2". W2 stopped at its premise check and recorded no count; the count
here is this run's own `audit/pairing_map.json`: 19 units, 10 registry rules, **101 pairs
planned**, 89 rejected, 0 undecided, no unmatched unit. 73 pair calls were made before the
kill (72 percent of the plan), all to PRACTICE_AUDITOR; STYLE_GUARDIAN's share of the plan
had not started. How the 101 pairs were made, from the map's own per-pair reasons:

| pairs | reason recorded on the pair |
|---|---|
| 57 | "no field the rule names is used by this document; ranked by similarity among the undecided" (the similarity fallback, not a field match) |
| 18 | "unit carries every field the rule names: device" (a rule naming only `device` matches every entry) |
| 13 | "unit carries every field the rule names: class, device, reading" |
| 13 | "unit carries every field the rule names: device, reading" |

This is the shape the operator's decision is about: more than half the plan rests on
similarity ranking because the rule names no field the document uses, and a rule that names
only the entry's identifier pairs with everything.

**Python computed nothing.** 0 posts with `backend=paired`, `missing_field_findings: []` in
the map, no `band_conditions` on any unit, no `prior_comparisons` (no earlier version was
declared). Every one of the 101 pairs was therefore a model call. The structural reason: the
reference file states its class bands in prose, not in a table, so `reference_tables` had no
table to read, and the conventions state no band of their own. The arithmetic path was never
exercised on this corpus; the neighbour mechanism, when it is measured, will be measured on
the model path alone unless the reference's bands are also written as a table.

**Contract violations: 4**, none retried (harness part 9 confirmed live: each is posted to
the bus, written under `audit/contract_violations/`, and the pair or phase moves on).

| time | agent | what the raw output shows |
|---|---|---|
| 07:46:49Z | CITATION_RESOLVER | a well-formed envelope preceded by echoed instruction text and a ```json fence |
| 07:58:51Z | VERIFIER | a well-formed envelope preceded by a `## Response` markdown header |
| 08:10:14Z | PRACTICE_AUDITOR | paired phase |
| 08:22:46Z | PRACTICE_AUDITOR | paired phase |

All four are "not a canonical envelope {agent:str, doc_id:str, items:list}" where the envelope
is present and the wrapping around it is what the parser refused. This is the same shape as
the name mismatches closed in W5, one boundary further out: the producer wraps, the consumer
refuses the wrapper, the content is lost. Reported here, not fixed in a measurement step.

**Agents that did not fire: 9 of 18.** STYLE_GUARDIAN, AMENDMENT_DRAFTER, EDITOR_CLERK,
EDITOR_HEAD_OF_UNIT, EDITOR_HEAD_OF_SECTION, EDITOR_HEAD_OF_DEPARTMENT, EDITOR_DEPUTY_DG and
EDITOR_DG did not fire because their phases were never reached before the kill (the run died
inside phase 5.5). REDACTOR did not fire because redaction was waived by
`--no-redaction-override` (logged to `redaction_waivers.jsonl`) and the sensitivity layer was
inactive by override (logged to `sensitivity_overrides.jsonl`). Nine fired; none fired from
the W3 "nothing assigned" condition, which does not exist yet.

**The registry the run reviewed against carried 10 rules, not 8.** `config/
convention_registry.json` after BOOT: CONV-004 to CONV-011 are the eight authored rules
(categories `conv-d01` to `conv-d08`, the operator's own ids preserved), and CONV-001 and
CONV-002 are the two preamble paragraphs of `device_conventions.md` ("Operator-authored rules
for reviewing device log entries..." and "The reviewer is a quality function...") minted as
rules with category `review`. CONV-003 is absent (minted and dropped, or skipped; not traced
tonight). The two preamble pseudo-rules drew 25 of the model's 71 findings (CONV-002: 14,
CONV-001: 11) and were paired to units 57 times by the similarity fallback. A parser that
turns a preamble into a rule is a defect in the parser, not in the corpus; noted for the
operator.

**What the model's findings look like.** 71 typed Finding records on the bus, all from
PRACTICE_AUDITOR, all `record_verdict: irregular`, all `relation: missing_field`, item ids
minted from the same reference (`PRACTICE_AUDITOR:finding:REF-0148:0` recurs across pairs),
rule ids CONV-002 (14), CONV-010 (14), CONV-011 (14), CONV-001 (11), CONV-004 (9), CONV-009
(9): three of the six most-cited "rules" are the preamble and the two meta-rules (grounding,
no speculation). And **`unit_id` is absent from every one of the 71 items**, not null, absent:
the model never wrote it. In paired mode the pipeline knows the unit by construction (a pair
is one unit and one rule), so the unit id could be stamped by Python rather than asked of a
7B model; that it is not is the single change that would have made this partial output
scorable, and it follows the repo's own rule that arithmetic outranks the model where
arithmetic can decide. Reported; not built in W6.

## What the scorer could score

`tools/score_corpus.py` refused a run with no `review_data.json` (no deliverable exists,
since synthesis was never reached). It was changed to score the bus findings alone in that
case and to print a NOTE saying so, with amendments = 0 (so `via_rule`, attribution, false
positives and distractor hits are necessarily 0 and mean nothing). It was also changed, before
the run ended, to report recall per flaw `kind`, which W6 requires and which the scorer did
not do; a key without `kind` prints exactly as before apart from a `kind` column in the table.
Both changes were dry-run on synthetic keys in a temporary directory with the real key closed
(S6). No gate check covers `tools/score_corpus.py`; that dry-run is the only executed proof.

Result on the stopped run, verbatim figures:

```
recall          : 0/9
  recall, neighbour-dependent, reads sound alone but contradicted by its neighbour : 0/3
  recall, long-range, term defined near the start conflicts with its use near the end : 0/3
  recall, self-contained, visible in one unit alone : 0/3
false positives : 0      (0 amendments: meaningless)
distractor hits : 0      (0 amendments: meaningless)
attribution     : 0 of 0
```

Against the wheat baseline the operator supplied (6 of 9, not reproduced here): 0 of 9, on a
run stopped before synthesis, from findings that name no unit. The zero is real and it is
not a measurement of the mechanism: a finding without a unit cannot match any planted unit
whatever the model saw. The clean twin was not run, so there is no false-positive figure.

## Did the neighbour mechanism catch the neighbour-dependent flaws?

Not determined. On this run's evidence the score is 0 of 3, and that figure is void rather
than negative: the run was stopped before any deliverable, Python computed nothing on this
corpus, and none of the model's findings carries a unit id, so the answer key had nothing to
match against. A zero on a void measurement is not the negative result W6 asked to be
reported plainly; it is no result. The measurement is owed and is scheduled below.

## Findings about the pipeline made during the run, none fixed here

1. D6's two-pass split makes LEGAL_ANALYST fire once plus once per pass-one finding under the
   local profile. `config/agent_harness.json` (W4) says "once per its fixed phase" for it;
   that part 8 entry is incomplete. Owed: a W4 correction commit adding the D6 clause in
   `scripts/build_agent_harness.py` and regenerating. Part 9 (re-fire limit 0 on a
   violation) stands: pass two is a designed second task, not a retry.
2. Pass two's deepened item is stitched to the original `item_id` with `revision+1` in the
   in-process result only; the bus keeps the fresh id at revision 1 (`pipeline.py` lines
   1037-1045 call this a known audit-trail gap). Deliverables read `results`, not the bus. The
   repo's own rule is that a record living only in a return value is not a record. For the
   operator's list.
3. Four contract violations, all a valid envelope inside a wrapper the parser refuses.
4. `unit_id` never stamped by Python in paired mode, though known by construction.
5. Two preamble paragraphs minted as rules; CONV-003 missing from the sequence.
6. Prose reference bands mean nothing is computable on this corpus; the arithmetic path is
   idle here.
7. 57 of 101 pairs made by similarity fallback; a rule naming only `device` pairs with every
   entry.

## Gate result

`PASS=195 WARN=0 SKIP=0 FAIL/ERROR=2 TOTAL=197`, run after the kill with the card free,
identical to W5's line: no check added (the only code change is in `tools/`, which no gate
check covers), no regression, the same two pre-existing failures as every step of this chain
(check 01, `missing dirs: ['prompts', 'snapshots']`; check 145, `tests/fixtures/
planted_figure_hashes.json is missing`). The gate was not run while the pipeline was on the
card: check 193 loads a local model and would have contended with the run.

## The new order of the chain, recorded here so nothing is lost

Set by the operator on 2026-09-11 after this stop. Every step still happens; nothing is
dropped. The W2 decision the operator gave this morning (a one-way subject label on each side,
compared by code that knows no subject name; an unmatched rule surfaced never dropped; the
agent-side list is data not code; assignment once at load) moves to the front.

1. Write `docs/api/CONVENTION_ASSIGNMENT_DESIGN.md` exactly as that decision specified (where
   the agent-side subject list lives, what a convention's subject field looks like, how the
   comparison works, what happens to an unmatched rule on both sides, the smallest subject set
   covering the eighteen agents, proposed not decided, what the operator still has to settle,
   what W3 becomes, which of W4's unresolved harness parts it closes). Then STOP for the
   operator to read it. Nothing is built before approval.
2. After approval: build the distribution (W2).
3. W3, which depends on it (firing, and the fourth visible state).
4. Rerun W6 on the new call count: both runs, flawed and clean twin, scored by the scorer,
   with the numbers this report could not produce.
5. W7 (ontology foundations).
6. W8 (the console).
7. W9 (close).

Also owed and not in that list because they are corrections, not steps: the W4 harness
correction (finding 1 above).

## Files

- `output/runs/20260911T071648Z__3d3142c8/`: `logs/agent_bus.jsonl` (105 events at the kill),
  `logs/cost_tracker.jsonl` (86 rows), `audit/pairing_map.json`, `audit/reference_index.json`,
  `audit/contract_violations/` (4 files). No `deliverables/`.
- `output/runs/20260911T071713Z__b38a42cb/`: the duplicate, BOOT plus 18 dispatch events, left
  in place as the record of the incident.
- `output/w6_flawed_run.log`: interleaved, not a record of either run (see the incident).
- `tools/score_corpus.py`: per-kind recall; partial-run scoring with a printed NOTE.

## The rerun, stopped a second time (2026-09-11, 12:33Z to 13:19Z)

Run against the committed tree at `dccec5f` (the eight device rules carrying the operator's
own subject tags: D01 to D05 `[conformance]`, D06 to D08 `[editorial]`; D03 belongs under
basis semantically, but basis has no rule-consuming path today, so conformance is its honest
home, recorded here as the operator asked). Flawed corpus staged with `tools/stage_corpus.py`,
the tier-1 manifest naming `device_log_flawed.md` as the target and the class reference as
grounding, paired mode, local models, no pair cap. Run `20260911T123328Z__d5728e4b`, BOOT
12:33:28Z, stopped by the operator at 13:19:40Z (46 min 12 s), during the paired phase,
before any deliverable. The clean twin was not run. Inputs restored afterwards. What the
partial run established, from its own artifacts:

- **The assignment, real for the first time.** BOOT: `convention_assignment rules=8
  untagged=0 unassigned=0`; `audit/convention_assignment.json` matches the offline
  computation exactly: D01 to D05 on PRACTICE_AUDITOR, D06 to D08 on the six EDITOR ranks,
  every rule `assigned`. STYLE_GUARDIAN is the first real entry the firing gate keeps from
  running (`not_firing`); REDACTOR appears among the agents no tagged rule reached, not in
  the not-firing list, since the gate is scoped to the convention-review agents (answer 6)
  and REDACTOR is kept from running by the inactive LAW-IV layer in any case.
- **64 pairs planned from 8 rules** (`paired_review pairs=64 dropped_by_cap=0 calls=64
  saved=0`; 19 units, 88 rejections, 0 undecided, no unmatched unit, no
  `missing_field_findings`, no `band_conditions`). Down from 101 on the first attempt, and
  the drop is the preamble fix (8 rules parsed where 10 were minted), not the tags: the
  pairing map never reads the assignment. Python computed nothing again (the class bands
  are prose), so every pair was a model call.
- **D02 to D05 paired with nothing.** Pairs by rule: D01 13, D06 13, D07 19, D08 19, and
  zero for D02, D03, D04 and D05, the four rules that check the planted flaw kinds. The
  reason, from the map's own rejection lines: the pairing map pairs a rule with a unit only
  when the unit carries every field the rule names, and those rules name `calibration
  authority`, `calibration authority signature`, `fault logged`, `fault acknowledged`,
  `fault window` and `service interval`, labels the entries mostly do not carry (each
  appears once, in the glossary unit; four entries carry `calibration authority signature`;
  every entry carries `class`, `device`, `reading` and most carry `note`). An absence flaw
  hides the very field the pairing needs, so a rule about a missing signature can never
  pair with the entry that is missing it. 38 of the 64 pairs were made by the similarity
  fallback ("no field the rule names is used by this document"), and 51 of the 64 belong to
  the three board-only rules.
- **The board-only gap, as the operator recorded it.** The convention distribution reaches
  wide mode (the firing gate) and not the paired path: D06 to D08, assigned to the editorial
  board and to no convention-review agent, are still paired and judged by PRACTICE_AUDITOR as
  the fallback (`pipeline._paired_judging_agent`, its own docstring). Measured as is, on the
  operator's decision, because changing what is measured immediately before measuring it is
  how three days passed with no number. It is the next piece of work after this: a plan
  whose rule has no convention-review consumer makes no call and is recorded in the pairing
  map as assigned to the board only, never silently dropped, with wide mode's registry
  excerpt filtered the same way.
- **Calls at the stop: 16**, all local, all `ok`: six phase-3 producers (ARCHIVIST,
  INST_FINDER, CITATION_RESOLVER, PROCESSOR, SPEECH_ACT_TAGGER, LEGAL_ANALYST), three
  LEGAL_ANALYST pass-two calls (D6, one per pass-one finding), VERIFIER and FACT_CHECKER in
  phase 5, and 5 of the 64 paired calls (56, 113, 52, 53 and 38 s each). 95,988 input tokens,
  12,266 output tokens. One contract violation (VERIFIER, 13:11:26Z). Phase 3-4 took 34 min
  15 s; the producer calls ran 190 to 263 s each, the paging pace (1.5 GB available at
  launch; the machine peak the progress line reported was 15.45 GB; the run's own process
  peaked at 2.7 GB RAM and 6.6 GB VRAM).
- **Scorer: not run.** No deliverable and no paired findings post existed at the stop, so
  there is nothing the scorer could score beyond the void zero the first attempt produced.
- **Did the neighbour mechanism catch the neighbour-dependent flaws?** Still not
  determined, and this run adds a reason it could not have been through the rules built to
  find them: D02 to D05 never reached a model. The question stays open until the pairing
  map can pair an absence rule with the unit that lacks the field, or the wide path is the
  one measured.

**The standing rule from this stop.** No pipeline run of any kind is started from this
laptop, and none is asked for, until development moves to a rented GPU box; every proof is
built on fixtures, mocks, deterministic paths and the artifacts already saved on disk
(written into `CLAUDE.md`). The stopped run's artifacts stay on disk for exactly that use:
`output/runs/20260911T123328Z__d5728e4b/` (`audit/convention_assignment.json`,
`audit/pairing_map.json`, `audit/reference_index.json`, `audit/contract_violations/`,
`logs/agent_bus.jsonl`, `logs/cost_tracker.jsonl`), `output/w6r_flawed.log`,
`output/w6r_flawed_mem.json`.

---

STEP W6 STOPPED (twice: by the operator at 08:27:17Z on the untagged corpus, and at
13:19:40Z on the tagged one; measurement owed; no further run from this machine)
