# Replay reply count with derived prompts (D-810), lane report

Written 19 November 2026 18:47 +0300 on branch `lane/reply-count-derived` (from lead/night-20261119 d44613f8).
Diagnosis: `docs/loop/stages/PARSE_SWEEP_FAILURE_20261119.md`. No paid run, no seal, no launch, no push.

## The change (bound file, CONTROLLER-BINDING: joins the grouped re-seal, not re-sealed here)

`tools/ordinary_final_run.py`:

- new `replay_derived(folder, prompt_count, calls)`: reads the pass's own `replay_measurement.json`. Only when it
  declares `derived` (the negotiation advisor's `run`, `benchmark/baselines/neg_advisor.py`) does it count
  derived prompts, and then it holds the figure to the pass's own record: `derived` must equal its rows of form
  `audit`, its `prompts` must equal the sealed `prompt_count`, and each audit row's `call_id` must be exactly one
  reply record. Any of these failing is a named problem (`replay_derived_rows`, `replay_prompts_declared`,
  `replay_derived_record`, `replay_derived_unreadable`) that fails the pass; it never lowers the count. A
  measurement without `derived` (every other replay workload) declares none, so the old rule holds unchanged.
- `replay_observation`: expected = `prompt_count * len(paths) + derived`; the problems join
  `items_without_one_record`; the observation also carries `derived`. `assess_b1` is unchanged.
- `expected_records` (progress total) is unchanged: derived prompts are unknown at sealing. Its docstring now says
  so; the live view already states when records exceed the total (`tools/ordinary_final_live.py:518`).

## Proofs

New test `test_a_replay_pass_counts_the_derived_prompts_it_declares_and_a_short_set_still_fails` in
`tools/ordinary_final_controller_checks.py` (run by `tools/ordinary_final_controller_gate.py`), two
neutralisations: derived not counted (the complete pass fails) and the declared figure taken on its word (the
inconsistent layouts pass). Passes: complete pass (2 prompts, 2 audits, 4 records) and no audits. Fails: a short
set, declared 3 with 2 audit rows, an audit row with no record, an audit row's record twice, a declared prompt
count other than the sealed one, extra records with nothing declared, no measurement.

Run alone (network denied, as the gate does): the new test, the R19 (v) B1 assessment test and the D-061 replay
test pass; all 5 neutralisation proofs on them neutralise, fail, restore, pass. The other `replay_observation`
callers pass unchanged: `tools/reasoning_methods_checks.py` (5 proofs), `tools/neg_synth_label_pass_checks.py`
(17), `scripts/choice_decision_checks.py` (64), `scripts/doc_judge_checks.py` (exit 0) and
`scripts/embed_records_checks.py` (44), each run alone. The whole gate was not run (lane rule).

## The fixed rule on the saved 18 November evidence

Both `collected_evidence.tar.gz` archives (`external/s05/NIGHT_parse_sweep/run_before/PS1116_BEFORE`,
`run_after/PS1116_AFTER`) extracted into a fresh scratch folder outside the repository; the fixed
`pass_observation` and `assess_b1` run on them with each pass's recorded exit code (0, from `evidence/result.json`).

| Pass | sealed prompts | derived (declared, joined) | records | expected, old rule | expected, fixed rule | assess_b1 |
|---|---|---|---|---|---|---|
| before | 25 | 41 | 66 | 25 (failed) | 66 | passed, no reasons |
| after | 128 | 118 | 246 | 128 (failed) | 246 | passed, no reasons |

The recorded result.json of both still names `b1_reply_record_missing` and `b1_reply_record_count`: the fix is
for runs after the re-seal; these two stay "runner integrity false by a counting defect, records complete" as
D-810 decided.

## Open

- The rule is in force only once the grouped re-seal binds the new runner hash.
