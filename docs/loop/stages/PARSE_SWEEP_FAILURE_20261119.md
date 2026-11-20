# Parse sweep (NIGHT_parse_sweep) integrity failure, diagnosis

Written 19 November 2026 18:37, read-only. Measurement: D-663, D-672, D-674, D-689; folder
`external/s05/NIGHT_parse_sweep`. Passes PS1116_BEFORE and PS1116_AFTER ran on 18 November (A10, bundle source
commit a51124ba), both `workload_return.json` exit_code 2, observed cost 0.563 + 1.076 USD (seal 0.387 before that).

## Verdict

No reply is missing. The pass wrote MORE records than the runner's counting rule expects. The cause is a
counting rule that expects another layout: the runner counts one reply record per prompt per path, while the
negotiation advisor replay pass also writes one record per derived audit prompt, built at run time from the
system's advice and not in the sealed prompts file.

| Pass | prompts (sealed `prompt_count`) | derived audits | records on disk | `expected_records` |
|---|---|---|---|---|
| before | 25 | 41 | 66 | 25 |
| after | 128 | 118 | 246 | 128 |

Every record is accounted for: in both passes each measurement row has a `call_id`, each `call_id` is exactly one
file under `audit/model_replies` (66 of 66, 246 of 246, no duplicates, no orphans), every record `backend_ok`
true, no row `failure`, `replay_measurement.json` `complete: true`. Not a writer that did not run, not a path
mismatch, not a pass under another name, not a crash.

## Trace

- `tools/ordinary_final_run.py:655-664` `replay_observation`: `expected = prompt_count*len(paths)`;
  `items_without_one_record = [] if records == expected else ['replay']`, `items=expected`.
- `tools/ordinary_final_run.py:684-687` `assess_b1`: a non-empty `items_without_one_record` gives
  `b1_reply_record_missing:<name>`; `reply_records != items` gives `b1_reply_record_count:<name>`. Both fire.
- `tools/ordinary_final_run.py:1003`: integrity false returns 2 (the watch log's `workload_return exit_code 2`).
- `tools/ordinary_final_run.py:952-958` `expected_records` writes the same figure to
  `evidence/b1/expected_records` (25 and 128).
- `benchmark/baselines/neg_advisor.py:1886-1891` `run`: after the prompt groups, `audit_prompts` of every
  `system_advice` reply go through the `system_audit` group; each is written by `reply_records.write` at
  `neg_advisor.py:1798` into the same pass folder (REPLIES-A holds: one record per call).
- `benchmark/baselines/replay_prompts.py:1088` prints the split. Log lines (evidence `workload.stdout.log`):
  before `"prompts": 25, "derived": 41, "seconds": 442.299`; after `"prompts": 128, "derived": 118,
  "seconds": 1974.504`. `workload.stderr.log` holds model loads only (Qwen2.5-7B, phi-4, Phi-3.5-mini), no error.
- No gate check exercises `replay_observation` on a negotiation advisor pass: the callers are
  `scripts/choice_decision_checks.py:647`, `scripts/doc_judge_checks.py:389,509` and
  `scripts/embed_records_checks.py:290`, none with derived prompts.

## Can the measurement be read without a new paid run

Yes. ANSWER-FORM-A applies as is. The sealed `replay_prompts.json` in each archive matches
`inputs/PS_before_prompts.json` (4075aa4b...) and `inputs/PS_after_prompts.json` (1b4478ff...), the same SHA-256 the
measurement records. A trial into the scratchpad (no model, saved records only):

    py -3.12 -X utf8 tools/reread_replies.py advisor --prompts <archive>/replay_prompts.json --run <archive>/evidence/b1/<pass> --out <scratch>/reread_<pass>.json

before: 25 rows, drops `proposals.id not_declared` 2; after: 128 rows, drops `reply no_json_object` 1. Both
exit 0. The integrity verdict can be recomputed offline by the corrected rule against the measurement rows (all
records joined), so the scoring may go ahead on these two passes, recorded as "runner integrity false by a
counting defect, records complete by row join" (a decision for the operator to name).

## If a rerun is wanted anyway

Fix first (bound file, CONTROLLER-BINDING: re-seal after): `replay_observation` should take the expected count
from the pass's own `replay_measurement.json` for a negotiation advisor pass (prompt rows plus `derived` plus
`steps`, every row's `call_id` one file), or the sealed manifest should carry the derived count; `expected_records`
(line 952) the same, and a gate check on a fixture advisor pass with derived audits. Cost by
`tools/loop/step_cost.py` (inventory of 18 November, A10 1.29 USD an hour, x1.3):

| Step | without measures | with asset copy |
|---|---|---|
| step_two_before.json | 93 min, 2.60 USD | 29 min, 0.81 USD |
| step_two_after.json | 131 min, 3.66 USD | 67 min, 1.87 USD |

Plus a re-seal job (step_seal.json, about 25 min, 0.70 USD). All within the 5 USD step pre-approval. Not needed for
the measurement itself.

Scratch copies: `<USER_HOME>\AppData\Local\Temp\claude\98615fb4d64ceccf\8fee59db-05ba-4f74-b566-421805410a26\scratchpad\ps_diag`.
