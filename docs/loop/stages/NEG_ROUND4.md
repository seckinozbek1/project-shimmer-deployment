# Negotiation round 4: the still-open answer's own stance, the early stop, the staged round (D-888)

21 November 2026, lane neg-r4 for the lead. Built and checked only: nothing launched, sealed, requested or spent; no
role folder, key, answer key or part item was opened.

## 1. The open stance (switch `open_stance`, scorer `open_stance_m4`)

Round 3 mapped the room fate answer "open" to counter, so M4 compared a counter with the key's kept or removed (D-877).
Now, behind the stepwise switch `open_stance` (false as shipped, boolean, needs `room_fate`, names one declared room
fate answer in `open_stance_answer` that sets counter), the piece of that answer carries `stance_kind` `{kind: open,
basis: inferred}` (benchmark/baselines/neg_advisor.py, `room_stance`). The piece's `stance` stays counter, so the
conflict, wording, red-line, audit, judge, M5, M6 and M10 readers are unchanged. The scorer (tools/score_neg_advisor.py
`item_parts`) reads the kind only when config/neg_advisor_dev.json `open_stance_m4` is true (false as shipped, the lead
sets it under a decision id before round 4's deciding read): an open-kind piece is then compared with the key's open fate
(open with open, a hit), and the key's open-fate rows enter M4 and M4 by fate. Every other fate compares as before
(accept with kept, counter with changed, reject with removed); an open-kind piece on a kept, removed or changed fate is a
miss. Off, rounds 2 and 3 replay unchanged.

## 2. The in-run early stop (tools/loop/fail_fast.py)

One importable decision and the whole watch loop for every launch folder's watch.py. It reads the live view's per-call
rows (status and item id only) after the first 3 returned items and every 6 more, and stops the part through
`launch.py stop` (TERMINATE_REQUEST, the controller's termination and evidence download) when more than 5 percent of the
returned items returned no answer (no call of the item passed), the first 3 items all returned none, refused calls pass
10 percent of the calls (the plan's bar line 5 limit), or crashed and out-of-memory calls pass 5 percent. The reason,
counts and, once ended, the cost go to FAIL_FAST_<part>.json in the launch folder. Not readable in the run: a piece the
audit calls unsupported (that is scored after the run); the run's own counts see refusals and no-answer items only.

## 3. Checks

Check 686 (tools/neg_round2_m4m10_checks.py) gains three proofs and seven neutralisations; check 695
(tools/loop/fail_fast_checks.py) proves the early stop and the watch loop with a fake empty run and a fake good run, ten
proofs and thirteen neutralisations, each failed, restored, passed.
